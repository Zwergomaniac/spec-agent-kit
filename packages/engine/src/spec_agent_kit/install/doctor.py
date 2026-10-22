"""``sak doctor``: Gesundheitscheck eines initialisierten Projekts (Spec 005 FR-008)."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

from spec_agent_kit.agent_env import get_agent_environment
from spec_agent_kit import __version__
from spec_agent_kit.config import AuthModeError, ConfigError, key_source, load_config, resolve_auth
from spec_agent_kit.config.check import check as check_config
from spec_agent_kit.install import InstallError
from spec_agent_kit.install.kit import (
    ENGINE_TARGET,
    LAUNCHER_SH_TARGET,
    LOCK_TARGET,
    SETTINGS_TARGET,
    sha256_of,
)
from spec_agent_kit.install.lock import Lock, read_lock
from spec_agent_kit.install.probe import probe_commands
from spec_agent_kit.install.settings import (
    ENGINE_MARKER,
    STARTER_MARKER,
    unsafe_mode_in,
    unsafe_mode_warning,
)
from spec_agent_kit.install.speckit import detect_version
from spec_agent_kit.install.tools import find_sh
from spec_agent_kit.parity import parity_for
from spec_agent_kit.push import cloud

DASHBOARD_TIMEOUT_SECONDS: Final[float] = 3.0
HOOK_TIMEOUT_SECONDS: Final[float] = 10.0
PROBE_PAYLOAD: Final[str] = (
    '{"hook_event_name": "SubagentStart", "agent_type": "sak-doctor-probe", "session_id": "probe"}'
)
REQUIRED_HOOK_EVENTS: Final[tuple[str, ...]] = ("SubagentStart", "SubagentStop")
OPTIONAL_HOOK_EVENTS: Final[tuple[str, ...]] = ("SessionStart",)
"""Hooks, die nur eine Warnung auslösen, wenn sie fehlen (seit Kit 0.2.0)."""
SESSION_PROBE_PAYLOAD: Final[str] = (
    '{"hook_event_name": "SessionStart", "source": "compact", "session_id": "probe"}'
)
REQUIRED_DENY: Final[tuple[str, ...]] = (
    "Bash(git push)",
    "Bash(git push *)",
    "Read(./.env*)",
    "Edit(./.env*)",
    "Read(./.spec-agent/dashboard.key)",
    "Edit(./.spec-agent/dashboard.key)",
)
"""Pflicht-Deny-Regeln; ein Test hält sie deckungsgleich mit ``settings.fragment.json``."""
IGNORE_PROBES: Final[tuple[str, ...]] = (
    ".spec-agent/state/events.jsonl",
    ".spec-agent/dashboard.key",
)

Check = dict[str, Any]


def _entry(name: str, ok: bool, detail: str, required: bool = True) -> Check:
    return {"check": name, "ok": ok, "detail": detail, "required": required}


def _check_agent_parity(root: Path) -> Check:
    try:
        config = load_config(root)
        environment = str(config.data.get("agent_environment", "claude"))
    except ConfigError:
        environment = "claude"
    entries = parity_for(environment)
    approximate = [entry["capability"] for entry in entries if entry["parity_level"] == "approximate"]
    if not approximate:
        check = _entry("agent_parity", True, f"{environment}: alle Agent-Bausteine als full klassifiziert")
    else:
        check = _entry(
            "agent_parity",
            True,
            f"{environment}: Paritaet dokumentiert; approximate fuer " + ", ".join(approximate),
        )
    check["items"] = entries
    return check


def _detect_environment_switch(lock: Lock, environment: str) -> str | None:
    locked_paths = set(lock.files)
    has_claude = any(path.startswith(".claude/") for path in locked_paths)
    has_copilot = any(
        path.startswith(".github/copilot/") or path.startswith(".vscode/") for path in locked_paths
    )
    if environment == "copilot" and has_claude and not has_copilot:
        return "claude"
    if environment == "claude" and has_copilot and not has_claude:
        return "copilot"
    return None


def _check_switch_migration(root: Path) -> Check | None:
    try:
        lock = read_lock(root)
    except InstallError:
        return None
    if lock is None:
        return None
    try:
        config = load_config(root)
        environment = str(config.data.get("agent_environment", "claude"))
    except ConfigError:
        return None
    previous = _detect_environment_switch(lock, environment)
    if previous is None:
        return None
    parity = parity_for(environment)
    approximate = [item["capability"] for item in parity if item["parity_level"] == "approximate"]
    detail = [f"Switch erkannt: {previous} -> {environment}"]
    if approximate:
        detail.append("bewusste Copilot-Approximationen: " + ", ".join(approximate))
    if environment == "copilot":
        detail.append("Betreiberaktion: VS-Code-Tasks fuer Hook-Ersatz und verbleibende Claude-Abweichungen pruefen")
    else:
        detail.append("Betreiberaktion: Claude-Hooks und Zielpfade nach der Rueckmigration pruefen")
    entry = _entry("switch_migration", True, "; ".join(detail), required=False)
    entry["warning"] = True
    entry["from_environment"] = previous
    entry["to_environment"] = environment
    return entry


def _check_lock(root: Path) -> Check:
    try:
        lock = read_lock(root)
    except InstallError as exc:
        return _entry("lock", False, exc.errors[0]["message"])
    if lock is None:
        return _entry("lock", False, f"{LOCK_TARGET} fehlt: nicht initialisiert (sak init)")
    missing: list[str] = []
    modified: list[str] = []
    for path, digest in lock.files.items():
        file = root / path
        if not file.is_file():
            missing.append(path)
        elif sha256_of(file.read_bytes()) != digest:
            modified.append(path)
    if missing:
        shown = ", ".join(missing[:3])
        return _entry("lock", False, f"{len(missing)} verwaltete Dateien fehlen, z. B. {shown}")
    note = f"; {len(modified)} lokal geändert (erlaubt)" if modified else ""
    engine_files = sum(1 for path in lock.files if path.startswith(f"{ENGINE_TARGET}/"))
    other_files = len(lock.files) - engine_files
    explanation = (
        f"davon {engine_files} Dateien der vendorten Engine und {other_files} Agents, Skills, "
        "Starter; config.yml, lock.json und settings.json sind nicht im Lock"
    )
    return _entry(
        "lock",
        True,
        f"Kit {lock.kit_version}, {len(lock.files)} Dateien im Lock ({explanation}){note}",
    )


def _check_config(root: Path) -> Check:
    result = check_config(root)
    if result["ok"]:
        return _entry("config", True, f"gültig ({len(result['warnings'])} Hinweise)")
    first = result["errors"][0]
    return _entry("config", False, f"{first['path']}: {first['message']}")


def _check_engine(root: Path, engine_running_from: Path | None) -> Check:
    engine = root / ENGINE_TARGET
    if not (engine / "pyproject.toml").is_file() or not (engine / "src").is_dir():
        return _entry("engine", False, f"{ENGINE_TARGET} fehlt oder ist unvollständig")
    try:
        running = engine_running_from is not None and engine_running_from.samefile(engine)
    except OSError:
        running = False
    if running:
        return _entry("engine", True, "läuft (dieser Aufruf kommt aus der vendorten Engine)")
    if not (engine / ".venv" / "pyvenv.cfg").is_file():
        return _entry(
            "engine", False, f"keine Umgebung: uv sync --project {ENGINE_TARGET} ausführen"
        )
    return _entry("engine", True, "Umgebung vorhanden")


def _check_settings(root: Path) -> Check:
    try:
        config = load_config(root)
        spec = get_agent_environment(str(config.data.get("agent_environment", "claude")))
    except ConfigError:
        spec = get_agent_environment("claude")
    path = root / spec.settings_path
    if not path.is_file():
        return _entry("hooks_and_deny", False, f"{spec.settings_path} fehlt")
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _entry("hooks_and_deny", False, f"{spec.settings_path} ist kein gültiges JSON")
    if spec.name == "copilot":
        tasks_path = root / spec.hook_target_path
        if not tasks_path.is_file():
            return _entry("hooks_and_deny", False, f"{spec.hook_target_path} fehlt")
        try:
            tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            return _entry("hooks_and_deny", False, f"{spec.hook_target_path} ist kein gültiges JSON")
        labels = {
            str(task.get("label", ""))
            for task in tasks.get("tasks", [])
            if isinstance(task, dict)
        }
        required = {
            "sak: hook subagent-start",
            "sak: hook subagent-stop",
            "sak: hook session-start",
        }
        missing = sorted(required - labels)
        if missing:
            return _entry(
                "hooks_and_deny",
                False,
                "Copilot-Hook-Ersatz unvollständig: fehlende VS-Code-Tasks: " + ", ".join(missing),
            )
        return _entry(
            "hooks_and_deny",
            True,
            "Copilot-Settings und Hook-Ersatz über VS-Code-Tasks vorhanden (approximate, native integriert)",
        )
    problems: list[str] = []
    warnings: list[str] = []
    hooks = settings.get("hooks", {}) if isinstance(settings, dict) else {}
    for event in REQUIRED_HOOK_EVENTS:
        entries = hooks.get(event) if isinstance(hooks, dict) else None
        commands = [
            str(hook.get("command", ""))
            for entry in (entries if isinstance(entries, list) else [])
            if isinstance(entry, dict)
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict)
        ]
        if any(STARTER_MARKER in c and ENGINE_MARKER not in c for c in commands):
            continue
        if any(ENGINE_MARKER in c for c in commands):
            warnings.append(
                f"Hook {event} ruft uv direkt auf (scheitert still, wenn uv nicht im PATH der "
                "Sitzung liegt); sak upgrade stellt ihn auf den Starter um"
            )
        else:
            problems.append(f"Hook {event} fehlt")
    for event in OPTIONAL_HOOK_EVENTS:
        entries = hooks.get(event) if isinstance(hooks, dict) else None
        if not any(
            STARTER_MARKER in str(hook.get("command", ""))
            for entry in (entries if isinstance(entries, list) else [])
            if isinstance(entry, dict)
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict)
        ):
            warnings.append(
                f"Hook {event} fehlt (der Lauf-Kontext übersteht ein Kompaktieren nicht); "
                "sak upgrade ergänzt ihn"
            )
    permissions = settings.get("permissions", {}) if isinstance(settings, dict) else {}
    deny = permissions.get("deny", []) if isinstance(permissions, dict) else []
    missing = [
        rule for rule in REQUIRED_DENY if rule not in (deny if isinstance(deny, list) else [])
    ]
    if missing:
        problems.append("Deny-Regeln fehlen: " + ", ".join(missing))
    if problems:
        return _entry("hooks_and_deny", False, "; ".join(problems))
    if warnings:
        entry = _entry("hooks_and_deny", True, "Warnung: " + "; ".join(warnings))
        entry["warning"] = True
        return entry
    return _entry("hooks_and_deny", True, "Hooks (über den Starter) und Deny-Regeln vorhanden")


def _probe_env(sh: str) -> dict[str, str]:
    """Minimale Umgebung wie bei einem Hook ohne uv im PATH: nur die Verzeichnisse der Shell."""
    shell_dir = Path(sh).resolve().parent
    dirs = [shell_dir]
    if os.name == "nt":  # Git Bash: dirname & Co. liegen in usr/bin neben bin/
        dirs += [
            d for d in (shell_dir.parent / "usr" / "bin", shell_dir / "usr" / "bin") if d.is_dir()
        ]
    else:
        dirs += [Path("/usr/bin"), Path("/bin")]
    env = {"PATH": os.pathsep.join(dict.fromkeys(str(d) for d in dirs))}
    for name in (
        "HOME",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "SystemRoot",
        "TEMP",
        "TMP",
        "SAK_UV",
    ):
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def _check_hook_probe(root: Path) -> Check:
    """Führt den Starter wie ein Hook aus (minimaler PATH, Beispiel-Payload auf stdin)."""
    try:
        config = load_config(root)
    except ConfigError:
        config = None
    if config is not None and str(config.data.get("agent_environment", "claude")) == "copilot":
        return _entry(
            "hook_probe",
            True,
            "Copilot-Hooks werden ueber native VS-Code-Tasks integriert; Shell-Hook-Probe nicht erforderlich",
        )
    starter = root / LAUNCHER_SH_TARGET
    if not starter.is_file():
        return _entry("hook_probe", False, f"{LAUNCHER_SH_TARGET} fehlt (Starter für die Hooks)")
    sh = find_sh()
    if sh is None:
        return _entry(
            "hook_probe",
            False,
            "keine POSIX-Shell (sh) gefunden (PATH und die Orte von Git for Windows geprüft); "
            "Hooks brauchen sie. Git for Windows installieren oder sh in den PATH aufnehmen",
        )
    env = _probe_env(sh)
    env["CLAUDE_PROJECT_DIR"] = str(root)

    def run(*args: str, stdin: str | None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sh, starter.as_posix(), *args],
            cwd=root,
            env=env,
            input=stdin,
            stdin=None if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=HOOK_TIMEOUT_SECONDS,
            check=False,
        )

    started = time.monotonic()
    try:
        hook = run("hook", "subagent-start", stdin=PROBE_PAYLOAD)
    except subprocess.TimeoutExpired:
        return _entry(
            "hook_probe", False, f"Hook-Probe brauchte länger als {HOOK_TIMEOUT_SECONDS:.0f} s"
        )
    except OSError as exc:
        return _entry("hook_probe", False, f"Starter nicht ausführbar: {exc}")
    elapsed = time.monotonic() - started
    if hook.returncode != 0:
        reason = (hook.stderr or "").strip().splitlines()
        hint = f": {reason[0]}" if reason else ""
        return _entry(
            "hook_probe",
            False,
            f"Starter endete im Hook-Test mit Exit {hook.returncode} (minimaler PATH, ohne uv"
            f"-Verzeichnis){hint}. Hooks erzeugen so keine Events; SAK_UV setzen oder uv "
            "installieren",
        )
    if (hook.stdout or "").strip():
        return _entry(
            "hook_probe", False, "Der Hook schreibt etwas auf stdout; Hooks müssen still bleiben"
        )
    if elapsed >= HOOK_TIMEOUT_SECONDS:
        return _entry("hook_probe", False, f"Hook-Probe dauerte {elapsed:.1f} s (Limit 10 s)")
    try:
        version = run("version", stdin=None)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _entry("hook_probe", False, f"sak version über den Starter scheiterte: {exc}")
    shown = (version.stdout or "").strip()
    session_problem = _session_probe(run)
    if session_problem is not None:
        return _entry("hook_probe", False, session_problem)
    try:
        reported = json.loads(shown).get("version")
    except (ValueError, AttributeError):
        reported = None
    if version.returncode != 0 or reported != __version__:
        return _entry(
            "hook_probe",
            False,
            f"sak version über den Starter lieferte Exit {version.returncode} und "
            f"{shown[:80]!r}, erwartet Kit-Version {__version__}",
        )
    return _entry(
        "hook_probe",
        True,
        f"Starter läuft im Hook-Test (minimaler PATH), Kit {__version__}, {elapsed:.1f} s",
    )


def _session_probe(run: Any) -> str | None:
    """``hook session-start`` mit Beispiel-Payload: Exit 0, still oder gültiges JSON (US8)."""
    try:
        proc = run("hook", "session-start", stdin=SESSION_PROBE_PAYLOAD)
    except subprocess.TimeoutExpired:
        return f"hook session-start brauchte länger als {HOOK_TIMEOUT_SECONDS:.0f} s"
    except OSError as exc:
        return f"hook session-start nicht ausführbar: {exc}"
    if proc.returncode != 0:
        return f"hook session-start endete mit Exit {proc.returncode}"
    text = (proc.stdout or "").strip()
    if not text:
        return None
    try:
        output = json.loads(text)["hookSpecificOutput"]
        if output["hookEventName"] != "SessionStart" or not isinstance(
            output["additionalContext"], str
        ):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return (
            "hook session-start schreibt keine gültige Hook-Ausgabe (JSON mit hookSpecificOutput)"
        )
    return None


def _check_default_mode(root: Path) -> Check | None:
    """Warnt, wenn ``defaultMode`` auf dem gefährlichen Modus steht (Befund 7); sonst ``None``."""
    hits: list[str] = []
    for relative in (SETTINGS_TARGET, ".claude/settings.local.json"):
        path = root / relative
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        except (OSError, ValueError):
            continue
        if unsafe_mode_in(data):
            hits.append(relative)
    if not hits:
        return None
    entry = _entry("default_mode", True, "Warnung: " + unsafe_mode_warning(", ".join(hits)), False)
    entry["warning"] = True
    return entry


def _check_commands(root: Path, probe: bool) -> Check:
    """Befehle aus ``commands.*``: Programm auffindbar; mit ``probe`` auch ausgeführt (Spec 011)."""
    try:
        commands = load_config(root).data["commands"]
    except ConfigError:
        return _entry("commands", True, "übersprungen (Config ungültig)", required=probe)
    items = probe_commands(root, commands, run=probe)
    if not items:
        return _entry("commands", True, "keine Befehle konfiguriert", required=probe)
    failed = [i for i in items if not i["ok"]]
    mode = "ausgeführt (--collect-only bzw. --version)" if probe else "nur Auffindbarkeit"
    if failed:
        shown = "; ".join(f"{i['command']}: {i['detail']}" for i in failed[:3])
        detail = f"{len(failed)} von {len(items)} Befehlen nicht in Ordnung ({mode}): {shown}"
    else:
        detail = f"{len(items)} Befehle in Ordnung ({mode})"
    entry = _entry("commands", not failed, detail, required=probe)
    entry["items"] = items
    return entry


def _check_gitignore(root: Path) -> Check:
    unignored: list[str] = []
    for probe in IGNORE_PROBES:
        try:
            proc = subprocess.run(
                ["git", "check-ignore", "-q", "--no-index", probe],
                cwd=root,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            return _entry("gitignore", False, "git ist nicht aufrufbar")
        if proc.returncode != 0:
            unignored.append(probe)
    if unignored:
        return _entry("gitignore", False, "nicht gitignored: " + ", ".join(unignored))
    return _entry("gitignore", True, ".spec-agent/state/ und dashboard.key sind gitignored")


def _check_speckit(root: Path) -> Check:
    try:
        return _entry("speckit", True, f"spec-kit {detect_version(root)} wird unterstützt")
    except InstallError as exc:
        return _entry("speckit", False, exc.errors[0]["message"])


def _check_dashboard(root: Path, url: str) -> Check:
    """Erreichbar und Schlüssel vorhanden (Spec 011 B15); ohne Schlüssel ist es nicht ok.

    Im Proxy-Modus (Spec 013) genügt ein erreichbares ``/healthz``: der Schlüssel liegt dann beim
    Proxy. Typische Cloud-Fehler (Proxy-Ablehnung, TLS) werden erklärt.
    """
    target = url.rstrip("/") + "/healthz"
    host = urlsplit(url).hostname or "das Dashboard"
    try:
        cfg = load_config(root)
        mode, _source = resolve_auth(cfg)
        source = key_source(root, cfg)
    except AuthModeError as exc:
        return _entry("dashboard", False, str(exc), required=False)
    except ConfigError:
        mode, source = "key", None
    try:
        # Eigener Opener: urlopen() merkt sich den Opener samt Proxy-Umgebung prozessweit, sodass
        # ein früherer Aufruf spätere Änderungen von HTTPS_PROXY verdeckt.
        handlers: list[urllib.request.BaseHandler] = []
        context = cloud.ssl_context()
        if context is not None:
            handlers.append(urllib.request.HTTPSHandler(context=context))
        opener = urllib.request.build_opener(*handlers)
        with opener.open(target, timeout=DASHBOARD_TIMEOUT_SECONDS) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except (urllib.error.URLError, OSError, ValueError) as exc:
        explained = cloud.explain(exc, host)
        if explained:
            return _entry("dashboard", False, explained, required=False)
        return _entry("dashboard", False, f"{target} nicht erreichbar: {exc}", required=False)
    reachable = status < 500
    if mode == "proxy":
        suffix = "; auth: proxy (Network Secret beim Proxy)"
        if source is not None:
            suffix += "; der lokale Schlüssel wird nicht gesendet"
        return _entry(
            "dashboard", reachable, f"{target} antwortet mit {status}{suffix}", required=False
        )
    if reachable and source is None:
        return _entry(
            "dashboard",
            False,
            f"{target} antwortet mit {status}, aber es gibt keinen Schlüssel "
            "(sak dashboard connect oder die Umgebungsvariable setzen)" + cloud.proxy_mode_hint(),
            required=False,
        )
    suffix = f"; Schlüssel vorhanden ({source})" if source else ""
    return _entry(
        "dashboard", reachable, f"{target} antwortet mit {status}{suffix}", required=False
    )


def run_doctor(
    root: Path, engine_running_from: Path | None = None, probe_commands: bool = False
) -> dict[str, Any]:
    """Alle Prüfungen. ``ok`` ist falsch, sobald eine Pflichtprüfung fehlschlägt.

    Mit ``probe_commands`` laufen die Testbefehle probeweise und zählen als Pflichtprüfung.
    """
    checks = [
        _check_lock(root),
        _check_config(root),
        _check_engine(root, engine_running_from),
        _check_settings(root),
        _check_agent_parity(root),
        _check_hook_probe(root),
        _check_gitignore(root),
        _check_speckit(root),
        _check_commands(root, probe_commands),
    ]
    mode = _check_default_mode(root)
    if mode is not None:
        checks.append(mode)
    try:
        url = load_config(root).data["dashboard"]["url"]
    except ConfigError:
        url = None
    if url:
        checks.append(_check_dashboard(root, str(url)))
    switch = _check_switch_migration(root)
    if switch is not None:
        checks.append(switch)
    ok = all(c["ok"] for c in checks if c["required"])
    return {"ok": ok, "checks": checks}
