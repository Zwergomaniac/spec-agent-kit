"""Installationsplan für ``sak init`` und ``sak upgrade`` (Spec 005 FR-001 bis FR-007).

Ein Plan schreibt nichts. Er enthält die Aktionen samt Inhalt; ``apply.apply_plan`` setzt genau
diesen Plan um.
"""

from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

import yaml

from spec_agent_kit.agent_env import get_agent_environment
from spec_agent_kit import contracts
from spec_agent_kit.config import ConfigError, read_raw, schema_errors
from spec_agent_kit.config.defaults import defaults
from spec_agent_kit.install import InstallError, detect
from spec_agent_kit.install.kit import (
    CONFIG_TARGET,
    LOCK_TARGET,
    SETTINGS_TARGET,
    Kit,
    sha256_of,
    version_tuple,
)
from spec_agent_kit.install.lock import Lock, read_lock
from spec_agent_kit.install.settings import (
    MergeResult,
    allow_entries,
    dumps_settings,
    merge_settings_detailed,
    parse_settings,
    unsafe_mode_in,
    unsafe_mode_warning,
)
from spec_agent_kit.install.speckit import detect_version

CREATE: Final = "create"
MERGE: Final = "merge"
REPLACE: Final = "replace"
DELETE: Final = "delete"
CONFLICT: Final = "conflict"
SKIP: Final = "skip"
WRITING: Final[frozenset[str]] = frozenset({CREATE, MERGE, REPLACE, DELETE})

SAK_NEW_SUFFIX: Final[str] = ".sak-new"
NAME_MAX: Final[int] = 80
_LOCAL_HOSTS: Final[frozenset[str]] = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass
class Action:
    """Eine geplante Aktion. ``expect`` ist der Hash der Zieldatei zur Planung (None = fehlt)."""

    kind: str
    path: str
    reason: str
    content: bytes | None = None
    expect: str | None = None
    quiet: bool = False
    hint: str | None = None

    def to_dict(self) -> dict[str, str]:
        entry = {"action": self.kind, "path": self.path, "reason": self.reason}
        if self.kind == CONFLICT:
            entry["new_file"] = self.path + SAK_NEW_SUFFIX
        if self.hint:
            entry["hint"] = self.hint
        return entry


@dataclass
class Plan:
    command: str
    target: Path
    kit_version: str
    actions: list[Action] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    config_keys: list[dict[str, Any]] = field(default_factory=list)
    speckit_version: str | None = None
    lock: Lock | None = None
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    permissions: dict[str, Any] | None = None
    """Allow- und Deny-Regeln des Kits mit Herkunft (Spec 011 US6 Befund 9, B13)."""
    settings_allow: list[str] = field(default_factory=list)

    def changes(self) -> list[Action]:
        """Alle Aktionen außer ``skip``."""
        return [a for a in self.actions if a.kind != SKIP]

    @property
    def is_empty(self) -> bool:
        return not self.changes()

    @property
    def conflicts(self) -> list[Action]:
        return [a for a in self.actions if a.kind == CONFLICT]

    def summary(self) -> dict[str, int]:
        counts = dict.fromkeys((CREATE, MERGE, REPLACE, DELETE, CONFLICT, SKIP), 0)
        for action in self.actions:
            counts[action.kind] += 1
        return counts

    def text(self) -> list[str]:
        """Lesbare Kurzfassung; Engine-Dateien werden zusammengefasst."""
        counts = self.summary()
        lines = [
            f"sak {self.command} (Plan) für {self.target}",
            f"Kit {self.kit_version}: {counts[CREATE]} neu, {counts[REPLACE]} ersetzt, "
            f"{counts[MERGE]} gemergt, {counts[DELETE]} gelöscht, {counts[CONFLICT]} Konflikte, "
            f"{counts[SKIP]} unverändert",
        ]
        marks = {CREATE: "+", MERGE: "~", REPLACE: "~", DELETE: "-", CONFLICT: "!", SKIP: "="}
        engine_prefix = ".spec-agent/engine/"
        grouped: dict[str, int] = {}
        for action in self.actions:
            if action.quiet:
                continue
            if action.path.startswith(engine_prefix) and action.kind in (CREATE, REPLACE, DELETE):
                grouped[action.kind] = grouped.get(action.kind, 0) + 1
                continue
            lines.append(
                f"  {marks[action.kind]} {action.kind:<8} {action.path}  ({action.reason})"
            )
        for kind, count in grouped.items():
            lines.append(f"  {marks[kind]} {kind:<8} {engine_prefix} ({count} Dateien)")
        for key in self.config_keys:
            lines.append(f"  ? Config-Schlüssel {key['path']} fehlt (Default: {key['default']!r})")
        lines.extend(self.permission_lines())
        lines.extend(f"WARNUNG: {w}" for w in self.warnings)
        lines.extend(f"VORSCHLAG: {item['text']}" for item in self.suggestions)
        if self.is_empty:
            lines.append("Nichts zu tun.")
        else:
            lines.append("Zum Anwenden: dieselbe Zeile mit --apply wiederholen.")
        return lines

    def permission_lines(self) -> list[str]:
        """Die einzelnen Regeln samt Geltungsbereich (Befund 9)."""
        info = self.permissions
        if info is None:
            return []
        lines = [
            "Permissions in .claude/settings.json (gelten für das ganze Projekt, nicht nur für "
            "Pipeline-Läufe):"
        ]
        for kind in ("allow", "deny"):
            for rule in info[kind]["add"]:
                lines.append(f"  + {kind:<5} {rule}")
            for rule in info[kind]["present"]:
                lines.append(f"  = {kind:<5} {rule}  (bereits vorhanden)")
        for rule in info["allow"]["remove"]:
            lines.append(f"  - allow {rule}  (Kit-Eintrag, nicht mehr gewünscht)")
        return lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "mode": "plan",
            "command": self.command,
            "target": str(self.target),
            "kit_version": self.kit_version,
            "speckit_version": self.speckit_version,
            "empty": self.is_empty,
            "summary": self.summary(),
            "actions": [a.to_dict() for a in self.actions if not a.quiet],
            "conflicts": [a.path for a in self.conflicts],
            "config_keys": self.config_keys,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "permissions": self.permissions,
            "text": self.text(),
        }


# ---------------------------------------------------------------------------
# Validierung (FR-002)
# ---------------------------------------------------------------------------


def validate_key(key: str) -> str | None:
    pattern = contracts.load_schema("common")["$defs"]["projectKey"]["pattern"]
    if re.fullmatch(pattern, key) is None:
        return (
            f"ungültiger Projektschlüssel {key!r}: 2 bis 40 Zeichen aus a-z, 0-9 und Bindestrich, "
            "beginnt mit einem Buchstaben und endet nicht mit Bindestrich"
        )
    return None


def validate_name(name: str) -> str | None:
    if not 1 <= len(name) <= NAME_MAX:
        return f"ungültiger Name: 1 bis {NAME_MAX} Zeichen erforderlich (gefunden: {len(name)})"
    if any(unicodedata.category(c) in {"Cc", "Zl", "Zp"} for c in name):
        return "ungültiger Name: keine Steuerzeichen oder Zeilenumbrüche erlaubt"
    return None


def validate_url(url: str) -> str | None:
    if any(c.isspace() for c in url):
        return f"ungültige Dashboard-URL {url!r}: Leerzeichen sind nicht erlaubt"
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
    except ValueError:
        return f"ungültige Dashboard-URL {url!r}"
    local = host in _LOCAL_HOSTS or host.endswith(".localhost")
    if parts.scheme == "https" and host:
        return None
    if parts.scheme == "http" and local:
        return None
    return f"ungültige Dashboard-URL {url!r}: https erforderlich (http nur für localhost)"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=root,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except OSError as exc:
        raise InstallError.single("git", f"git ist nicht aufrufbar: {exc}") from exc


def is_repo_root(target: Path) -> bool:
    if not target.is_dir():
        return False
    proc = _git(target, "rev-parse", "--show-toplevel")
    top = proc.stdout.decode("utf-8", "replace").strip()
    if proc.returncode != 0 or not top:
        return False
    try:
        return Path(top).resolve() == target.resolve()
    except OSError:
        return False


def branch_exists(target: Path, branch: str) -> bool:
    for ref in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"):
        if _git(target, "rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return True
    return False


def dirty_paths(target: Path) -> set[str]:
    """Geänderte und unversionierte Dateien (POSIX-Pfade) laut ``git status``."""
    proc = _git(target, "status", "--porcelain=v1", "-z", "-uall")
    entries = proc.stdout.decode("utf-8", "replace").split("\0")
    paths: set[str] = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        paths.add(entry[3:])
        if entry[0] in "RC":  # Umbenennung/Kopie: danach folgt der alte Pfad
            if index < len(entries) and entries[index]:
                paths.add(entries[index])
            index += 1
    return paths


def _check_dirty(
    target: Path, actions: Sequence[Action], allow_dirty: bool, errors: list[dict[str, str]]
) -> None:
    dirty = dirty_paths(target)
    if not dirty:
        return
    sample = ", ".join(sorted(dirty)[:3])
    if not allow_dirty:
        errors.append(
            {
                "path": "<git>",
                "message": (
                    f"Arbeitsstand nicht sauber ({len(dirty)} geänderte Dateien, z. B. {sample}). "
                    "Erst committen oder stashen; --allow-dirty ist nur erlaubt, wenn keine "
                    "geplante Aktion eine geänderte Datei berührt."
                ),
            }
        )
        return
    touched = {a.path for a in actions if a.kind in WRITING}
    touched |= {a.path + SAK_NEW_SUFFIX for a in actions if a.kind == CONFLICT}
    clash = sorted(touched & dirty)
    if clash:
        errors.append(
            {
                "path": "<git>",
                "message": "--allow-dirty abgelehnt: geplante Aktionen berühren geänderte Dateien: "
                + ", ".join(clash),
            }
        )


# ---------------------------------------------------------------------------
# Config-Seed (FR-003)
# ---------------------------------------------------------------------------


def _quote(value: str) -> str:
    """Zeichenkette als YAML-Doppelstring (JSON-Escapes sind gültiges YAML)."""
    return json.dumps(value, ensure_ascii=False)


def ui_placeholders(template: str) -> tuple[str, str]:
    """Beispielwerte für ``ui.command`` und ``ui.base_url`` aus dem kommentierten ``ui``-Block.

    Die Werte stehen nur in der Vorlage, nie in der Engine (Constitution VIII).
    """
    command = re.search(r"^#\s+command:\s*(.+?)\s*$", template, flags=re.MULTILINE)
    base_url = re.search(r"^#\s+base_url:\s*(\S+)", template, flags=re.MULTILINE)
    if command is None or base_url is None:
        raise InstallError.single(CONFIG_TARGET, "die Vorlage enthält keinen ui-Beispielblock")
    return command.group(1), base_url.group(1)


def render_config(
    template: str,
    *,
    key: str,
    name: str,
    base_branch: str,
    agent_environment: str,
    dashboard_url: str | None,
    ui: bool,
    test_fast: Sequence[str] = (),
    test_full: Sequence[str] = (),
    lint: Sequence[str] = (),
    clean_ignore: Sequence[str] = (),
) -> str:
    """Ersetzt die Platzhalter der Vorlage und trägt die Optionen ein. Kommentare bleiben."""
    text = template.replace("__PROJECT_KEY__", key)
    text = text.replace("__PROJECT_NAME__", _quote(name))
    text = text.replace("__BASE_BRANCH__", _quote(base_branch))
    text = re.sub(
        r"^(agent_environment:)\s+\S+",
        lambda m: f"{m.group(1)} {agent_environment}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if agent_environment == "copilot":
        replacements = (
            ("model: sonnet", "model: gpt-5"),
            ("model: opus", "model: gpt-5"),
        )
        for old, new in replacements:
            text = text.replace(old, new)
    for field_name, commands in (
        ("test_fast", test_fast),
        ("test_full", test_full),
        ("lint", lint),
        ("clean_ignore", clean_ignore),
    ):
        if not commands:
            continue
        items = "".join(f"\n    - {_quote(c)}" for c in commands)
        text = re.sub(
            rf"^(  {field_name}:) \[\]([ \t]*#.*)?$",
            lambda m, items=items: f"{m.group(1)}{m.group(2) or ''}{items}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
    if dashboard_url:
        text = re.sub(
            r"^(  url:) null",
            lambda m: f"{m.group(1)} {_quote(dashboard_url)}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
    if ui:
        text = re.sub(
            r"^(    ui_review:\s+\{ enabled:) false,",
            lambda m: f"{m.group(1)} true, ",
            text,
            count=1,
            flags=re.MULTILINE,
        )
        command, base_url = ui_placeholders(template)
        block = (
            "ui:\n"
            f"  command: {_quote(command)}     # Platzhalter aus der Vorlage: anpassen\n"
            f"  base_url: {base_url}     # Platzhalter aus der Vorlage: anpassen\n\n"
        )
        text = text.replace("guard:\n", block + "guard:\n", 1)
    return text


def check_rendered(text: str) -> list[str]:
    """Schemafehler der erzeugten Config (sollte nie vorkommen)."""
    if "__PROJECT_" in text or "__BASE_BRANCH__" in text:
        return ["Platzhalter in der Config nicht ersetzt"]
    loaded = yaml.safe_load(text)
    return [f"{e['path']}: {e['message']}" for e in schema_errors(loaded)]


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes() if path.is_file() else None
    except OSError:
        return None


def _hash(data: bytes | None) -> str | None:
    return None if data is None else sha256_of(data)


def _diff_hint(path: str) -> str:
    return f"Vergleichen: git diff --no-index -- {path} {path}{SAK_NEW_SUFFIX}"


def _settings_action(
    kit: Kit,
    target: Path,
    extra_allow: list[str],
    plan: Plan,
    owned_allow: list[str] | None,
    environment: str,
) -> Action:
    """Merge des Fragments in ``.claude/settings.json``; trägt Regeln und Warnungen in den Plan."""
    spec = get_agent_environment(environment)
    fragment = json.loads(kit.settings_fragment(environment).decode("utf-8"))
    raw = _read(target / spec.settings_path)
    if not spec.settings_merge:
        if raw is None:
            return Action(CREATE, spec.settings_path, "aus der Vorlage angelegt", content=dumps_settings(fragment).encode("utf-8"))
        if parse_settings(raw.decode("utf-8")) == fragment:
            return Action(SKIP, spec.settings_path, "bereits identisch")
        return Action(REPLACE, spec.settings_path, "aus der Vorlage aktualisiert", content=dumps_settings(fragment).encode("utf-8"), expect=_hash(raw))
    existing: dict[str, Any] | None = None
    if raw is not None:
        try:
            existing = parse_settings(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise InstallError.single(SETTINGS_TARGET, f"ungültig, keine Änderung: {exc}") from exc
    result = merge_settings_detailed(existing, fragment, extra_allow, owned_allow)
    plan.warnings.extend(result.warnings)
    plan.warnings.extend(_local_settings_warnings(target))
    plan.permissions = _permission_info(result)
    plan.settings_allow = result.allow_owned
    if result.legacy_lock and result.allow_removed:
        plan.warnings.append(
            "Das Lockfile kennt noch keine settings_allow (Altbestand vor Kit 0.2.0): ersetzt "
            "werden nur bekannte Kit-Muster ("
            + ", ".join(result.allow_removed)
            + "). Andere allow-Einträge bleiben, auch frühere Testbefehle des Kits."
        )
    content = dumps_settings(result.merged).encode("utf-8")
    if existing is None:
        return Action(CREATE, spec.settings_path, "aus dem Fragment angelegt", content=content)
    if result.merged == existing:
        return Action(SKIP, spec.settings_path, "Fragment bereits enthalten")
    return Action(
        MERGE,
        spec.settings_path,
        "ergänzt (Hooks und Permissions); fremde Einträge bleiben"
        + ("; veraltete Kit-Einträge ersetzt" if result.allow_removed else ""),
        content=content,
        expect=_hash(raw),
    )


def _permission_info(result: MergeResult) -> dict[str, Any]:
    return {
        "scope": "gesamtes Projekt (.claude/settings.json), nicht nur Pipeline-Läufe",
        "allow": {
            "add": result.allow_added,
            "present": result.allow_present,
            "remove": result.allow_removed,
        },
        "deny": {"add": result.deny_added, "present": result.deny_present, "remove": []},
    }


def _local_settings_warnings(target: Path) -> list[str]:
    """Der gefährliche Modus in ``settings.local.json`` gilt ebenfalls (Befund 7)."""
    raw = _read(target / ".claude" / "settings.local.json")
    if raw is None:
        return []
    try:
        local = parse_settings(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return []
    return [unsafe_mode_warning(".claude/settings.local.json")] if unsafe_mode_in(local) else []


def _finish(
    plan: Plan,
    kit: Kit,
    old: Lock | None,
    files: dict[str, str],
    now: str,
) -> None:
    """Berechnet das neue Lockfile und hängt die Lock-Aktion an (zuletzt)."""
    fragment_hash = sha256_of(kit.settings_fragment())
    allow = list(plan.settings_allow)
    if old is None:
        new = Lock(kit.version, now, None, files, fragment_hash, allow)
        plan.lock = new
        plan.actions.append(Action(CREATE, LOCK_TARGET, "Lockfile sak.lock/1", content=new.dumps()))
        return
    changed = (
        old.kit_version != kit.version
        or old.files != files
        or old.settings_fragment_hash != fragment_hash
        or old.settings_allow != allow
    )
    if not changed:
        plan.lock = old
        return
    new = Lock(kit.version, old.installed_at, now, files, fragment_hash, allow)
    plan.lock = new
    plan.actions.append(
        Action(
            REPLACE,
            LOCK_TARGET,
            "Lockfile aktualisiert",
            content=new.dumps(),
            expect=_hash(_read(plan.target / LOCK_TARGET)),
        )
    )


# ---------------------------------------------------------------------------
# Init (FR-001 bis FR-003)
# ---------------------------------------------------------------------------


def _init_suggestions(
    target: Path,
    commands: Sequence[str],
    clean_ignore: Sequence[str],
    rules: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Vorschläge aus der Projekt-Erkennung (Spec 011 US2, US4). Es wird nichts geschrieben."""
    found: list[dict[str, Any]] = []
    for tool in detect.detect_artifact_tools(target, rules):
        missing = [e for e in tool["entries"] if e not in clean_ignore]
        if not missing:
            continue
        where = f"{tool['directory'] or '.'}: {tool['evidence']}"
        option = " ".join(f"--clean-ignore {e}" for e in missing)
        found.append(
            {
                "kind": "clean_ignore",
                "tool": tool["id"],
                "entries": missing,
                "reason": f"{tool['label']} erkannt ({where})",
                "text": (
                    f"{tool['label']} erkannt ({where}); dessen Ausgabeordner ließen sonst jeden "
                    f"Prüflauf mit review_integrity eskalieren. guard.clean_ignore ergänzen: "
                    f"{option}"
                ),
            }
        )
    for command in dict.fromkeys(commands):
        suggestion = detect.suggest_command(command, target)
        if suggestion is not None:
            found.append(
                {
                    "kind": "command",
                    "command": suggestion["command"],
                    "suggested": suggestion["suggested"],
                    "reason": suggestion["reason"],
                    "text": (
                        f"Befehl '{suggestion['command']}' wahrscheinlich nicht lauffähig: "
                        f"{suggestion['reason']}. Vorschlag: {suggestion['suggested']}"
                    ),
                }
            )
    return found


def build_init_plan(
    kit: Kit,
    target: Path,
    *,
    key: str,
    name: str,
    base_branch: str = "main",
    dashboard_url: str | None = None,
    ui: bool = True,
    test_fast: Sequence[str] = (),
    test_full: Sequence[str] = (),
    lint: Sequence[str] = (),
    clean_ignore: Sequence[str] = (),
    allow_dirty: bool = False,
    now: str | None = None,
    agent_environment: str = "claude",
) -> Plan:
    """Plan für ``sak init``. Wirft ``InstallError`` bei Verstößen gegen FR-002; schreibt nie."""
    errors: list[dict[str, str]] = []
    for path, problem in (
        ("--key", validate_key(key)),
        ("--name", validate_name(name)),
        ("--dashboard-url", validate_url(dashboard_url) if dashboard_url else None),
        ("--base-branch", None if base_branch.strip() else "darf nicht leer sein"),
    ):
        if problem:
            errors.append({"path": path, "message": problem})
    if errors:
        raise InstallError(errors)

    target = target.resolve()
    if not is_repo_root(target):
        raise InstallError.single(
            str(target), "Ziel ist kein Git-Repository (oder nicht dessen Wurzelverzeichnis)"
        )
    if read_lock(target) is not None:
        raise InstallError.single(
            LOCK_TARGET, "bereits initialisiert: bitte `sak upgrade` verwenden"
        )
    if not branch_exists(target, base_branch):
        raise InstallError.single("--base-branch", f"der Branch '{base_branch}' existiert nicht")
    plan = Plan("init", target, kit.version)
    plan.speckit_version = detect_version(target)
    spec = get_agent_environment(agent_environment)

    stamp = now or contracts.now_rfc3339()
    files: dict[str, str] = {}
    for path, source in kit.managed_files(spec.name).items():
        data = source.read_bytes()
        digest = sha256_of(data)
        local = _read(target / path)
        if local is None:
            plan.actions.append(Action(CREATE, path, "neu", content=data))
            files[path] = digest
        elif sha256_of(local) == digest:
            plan.actions.append(Action(SKIP, path, "bereits identisch", quiet=True))
            files[path] = digest
        else:
            plan.actions.append(
                Action(
                    CONFLICT,
                    path,
                    "existiert mit anderem Inhalt und ist nicht im Lock; Kit-Fassung daneben",
                    content=data,
                    expect=sha256_of(local),
                    hint=_diff_hint(path),
                )
            )

    config_text = render_config(
        kit.config_template(),
        key=key,
        name=name,
        base_branch=base_branch,
        agent_environment=spec.name,
        dashboard_url=dashboard_url,
        ui=ui,
        test_fast=test_fast,
        test_full=test_full,
        lint=lint,
        clean_ignore=clean_ignore,
    )
    problems = check_rendered(config_text)
    if problems:
        raise InstallError([{"path": CONFIG_TARGET, "message": p} for p in problems])
    if (target / CONFIG_TARGET).exists():
        plan.actions.append(Action(SKIP, CONFIG_TARGET, "existiert; die Config wird nie verwaltet"))
    else:
        plan.actions.append(
            Action(CREATE, CONFIG_TARGET, "aus der Vorlage", content=config_text.encode("utf-8"))
        )
    if ui:
        placeholder_command, placeholder_url = ui_placeholders(kit.config_template())
        plan.warnings.append(
            "ui_review ist aktiv; ui.command und ui.base_url sind Platzhalter "
            f"({placeholder_command}, {placeholder_url}). In .spec-agent/config.yml anpassen "
            "oder mit --no-ui initialisieren."
        )

    plan.suggestions.extend(
        _init_suggestions(target, [*test_fast, *test_full, *lint], clean_ignore, kit.detectors())
    )

    extra = allow_entries([*test_fast, *test_full, *lint])
    plan.actions.append(_settings_action(kit, target, extra, plan, owned_allow=[], environment=spec.name))
    _finish(plan, kit, None, files, stamp)

    errors = []
    _check_dirty(target, plan.actions, allow_dirty, errors)
    if errors:
        raise InstallError(errors)
    return plan


# ---------------------------------------------------------------------------
# Upgrade (FR-007)
# ---------------------------------------------------------------------------


def missing_config_keys(root: Path) -> list[dict[str, Any]]:
    """Schlüssel der wirksamen Defaults, die in der Config-Datei fehlen (nur Meldung, FR-007)."""
    try:
        raw = read_raw(root)
    except ConfigError:
        return []
    found: list[dict[str, Any]] = []

    def walk(default: dict[str, Any], actual: dict[str, Any], prefix: str) -> None:
        for name, value in default.items():
            path = f"{prefix}{name}"
            if name not in actual:
                found.append({"path": path, "default": value})
            elif isinstance(value, dict) and isinstance(actual[name], dict):
                walk(value, actual[name], f"{path}.")

    walk(defaults(), raw, "")
    return found


def _config_commands(root: Path) -> list[str]:
    try:
        commands = read_raw(root).get("commands", {})
    except ConfigError:
        return []
    if not isinstance(commands, dict):
        return []
    result: list[str] = []
    for name in ("test_fast", "test_full", "lint"):
        value = commands.get(name)
        if isinstance(value, list):
            result.extend(c for c in value if isinstance(c, str))
    return result


def build_upgrade_plan(
    kit: Kit,
    target: Path,
    *,
    allow_dirty: bool = False,
    now: str | None = None,
) -> Plan:
    """Plan für ``sak upgrade``. Wirft ``InstallError``; schreibt nie."""
    target = target.resolve()
    if not is_repo_root(target):
        raise InstallError.single(
            str(target), "Ziel ist kein Git-Repository (oder nicht dessen Wurzelverzeichnis)"
        )
    old = read_lock(target)
    if old is None:
        raise InstallError.single(
            LOCK_TARGET, "nicht initialisiert: das Lockfile fehlt. Zuerst `sak init` ausführen"
        )
    if version_tuple(old.kit_version) > version_tuple(kit.version):
        raise InstallError.single(
            LOCK_TARGET,
            f"Downgrade abgelehnt: das Projekt hat Kit {old.kit_version}, dieses Kit ist "
            f"{kit.version}",
        )
    plan = Plan("upgrade", target, kit.version)
    stamp = now or contracts.now_rfc3339()
    raw_config = read_raw(target)
    spec = get_agent_environment(str(raw_config.get("agent_environment", "claude")))
    managed = kit.managed_files(spec.name)
    files = dict(old.files)

    for path, source in managed.items():
        data = source.read_bytes()
        new_hash = sha256_of(data)
        local = _read(target / path)
        local_hash = _hash(local)
        locked = old.files.get(path)
        if local is None:
            plan.actions.append(Action(CREATE, path, "fehlt lokal, wird wiederhergestellt", data))
            files[path] = new_hash
        elif locked is None:
            if local_hash == new_hash:
                plan.actions.append(Action(SKIP, path, "bereits identisch; ins Lock übernommen"))
                files[path] = new_hash
            else:
                plan.actions.append(
                    _conflict(path, data, local_hash, "neue Kit-Datei, lokal vorhanden")
                )
        elif local_hash == locked:
            if new_hash == locked:
                plan.actions.append(Action(SKIP, path, "unverändert", quiet=True))
            else:
                plan.actions.append(
                    Action(REPLACE, path, "lokal unverändert, Kit neuer", data, local_hash)
                )
                files[path] = new_hash
        elif new_hash == locked:
            plan.actions.append(Action(SKIP, path, "lokal geändert, Kit unverändert", quiet=True))
        elif local_hash == new_hash:
            plan.actions.append(
                Action(SKIP, path, "lokal bereits auf Kit-Stand; Lock aktualisiert")
            )
            files[path] = new_hash
        else:
            plan.actions.append(_conflict(path, data, local_hash, "lokal geändert und Kit neuer"))

    for path, locked in sorted(old.files.items()):
        if path in managed:
            continue
        local = _read(target / path)
        if local is None:
            plan.actions.append(Action(SKIP, path, "entfällt im Kit und fehlt lokal; aus dem Lock"))
            del files[path]
        elif sha256_of(local) == locked:
            plan.actions.append(
                Action(DELETE, path, "entfällt im Kit, lokal unverändert", expect=sha256_of(local))
            )
            del files[path]
        else:
            plan.actions.append(
                Action(SKIP, path, "entfällt im Kit, bleibt wegen lokaler Änderung")
            )
            plan.warnings.append(
                f"{path} entfällt im Kit, wurde aber lokal geändert und bleibt (manuell entfernen)."
            )

    if (target / CONFIG_TARGET).is_file():
        plan.actions.append(
            Action(SKIP, CONFIG_TARGET, "die Config wird nie verwaltet", quiet=True)
        )
        plan.config_keys = missing_config_keys(target)
    else:
        plan.warnings.append(f"{CONFIG_TARGET} fehlt (wird von upgrade nicht angelegt)")
    extra = allow_entries(_config_commands(target))
    plan.actions.append(_settings_action(kit, target, extra, plan, owned_allow=old.settings_allow, environment=spec.name))
    _finish(plan, kit, old, files, stamp)

    errors: list[dict[str, str]] = []
    _check_dirty(target, plan.actions, allow_dirty, errors)
    if errors:
        raise InstallError(errors)
    return plan


def _conflict(path: str, data: bytes, local_hash: str | None, reason: str) -> Action:
    return Action(
        CONFLICT,
        path,
        f"{reason}; die Datei bleibt, die Kit-Fassung liegt daneben",
        content=data,
        expect=local_hash,
        hint=_diff_hint(path),
    )
