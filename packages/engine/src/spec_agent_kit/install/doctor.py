"""``sak doctor``: Gesundheitscheck eines initialisierten Projekts (Spec 005 FR-008)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Final

from spec_agent_kit import __version__
from spec_agent_kit.config import ConfigError, load_config
from spec_agent_kit.config.check import check as check_config
from spec_agent_kit.install import InstallError
from spec_agent_kit.install.kit import (
    ENGINE_TARGET,
    LAUNCHER_SH_TARGET,
    LOCK_TARGET,
    SETTINGS_TARGET,
    sha256_of,
)
from spec_agent_kit.install.lock import read_lock
from spec_agent_kit.install.settings import ENGINE_MARKER, STARTER_MARKER
from spec_agent_kit.install.speckit import detect_version

DASHBOARD_TIMEOUT_SECONDS: Final[float] = 3.0
HOOK_TIMEOUT_SECONDS: Final[float] = 10.0
PROBE_PAYLOAD: Final[str] = (
    '{"hook_event_name": "SubagentStart", "agent_type": "sak-doctor-probe", "session_id": "probe"}'
)
REQUIRED_HOOK_EVENTS: Final[tuple[str, ...]] = ("SubagentStart", "SubagentStop")
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
    return _entry("lock", True, f"Kit {lock.kit_version}, {len(lock.files)} Dateien im Lock{note}")


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
    path = root / SETTINGS_TARGET
    if not path.is_file():
        return _entry("hooks_and_deny", False, f"{SETTINGS_TARGET} fehlt")
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _entry("hooks_and_deny", False, f"{SETTINGS_TARGET} ist kein gültiges JSON")
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
    starter = root / LAUNCHER_SH_TARGET
    if not starter.is_file():
        return _entry("hook_probe", False, f"{LAUNCHER_SH_TARGET} fehlt (Starter für die Hooks)")
    sh = shutil.which("sh")
    if sh is None:
        return _entry("hook_probe", False, "keine POSIX-Shell (sh) gefunden; Hooks brauchen sie")
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


def _check_dashboard(url: str) -> Check:
    target = url.rstrip("/") + "/healthz"
    try:
        with urllib.request.urlopen(target, timeout=DASHBOARD_TIMEOUT_SECONDS) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return _entry("dashboard", False, f"{target} nicht erreichbar: {exc}", required=False)
    ok = status < 500
    return _entry("dashboard", ok, f"{target} antwortet mit {status}", required=False)


def run_doctor(root: Path, engine_running_from: Path | None = None) -> dict[str, Any]:
    """Alle Prüfungen. ``ok`` ist falsch, sobald eine Pflichtprüfung fehlschlägt."""
    checks = [
        _check_lock(root),
        _check_config(root),
        _check_engine(root, engine_running_from),
        _check_settings(root),
        _check_hook_probe(root),
        _check_gitignore(root),
        _check_speckit(root),
    ]
    try:
        url = load_config(root).data["dashboard"]["url"]
    except ConfigError:
        url = None
    if url:
        checks.append(_check_dashboard(str(url)))
    ok = all(c["ok"] for c in checks if c["required"])
    return {"ok": ok, "checks": checks}
