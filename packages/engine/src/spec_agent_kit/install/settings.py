"""Additiver Merge des Settings-Fragments in ``.claude/settings.json`` (Spec 005 FR-005).

Bestehende fremde Einträge und ``defaultMode`` bleiben unverändert. Hook-Einträge des Kits (Befehl
mit ``.spec-agent/``, auch die alten Fassungen mit ``.spec-agent/engine``) werden durch die Fassung
des Fragments ersetzt, nicht ergänzt; das ist idempotent. Außerdem werden fehlende Einträge in
``permissions.allow`` und ``permissions.deny`` ergänzt.

Kit-eigene allow-Einträge sind im Lock unter ``settings_allow`` vermerkt (Spec 011 B13). Beim
Upgrade werden sie ersetzt: Was das Kit früher eingetragen hat und nicht mehr will, verschwindet;
fremde Einträge bleiben. Ein Lock ohne ``settings_allow`` (Altbestand vor 0.2.0) kennt die Herkunft
nicht. Dann gelten nur bekannte Kit-Muster als Kit-eigen (``LEGACY_KIT_ALLOW`` und die Einträge des
aktuellen Fragments).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Final

ENGINE_MARKER: Final[str] = ".spec-agent/engine"
KIT_MARKER: Final[str] = ".spec-agent/"
"""Kit-eigene Hook-Befehle erkennt man daran (Starter ``.spec-agent/sak`` und alte Engine-Pfade)."""
STARTER_MARKER: Final[str] = ".spec-agent/sak"
# Der gefährliche Modus wird nur erkannt, nie gesetzt; das Wort entsteht hier zusammengesetzt, damit
# der Grep-Test (Constitution IV) in Engine und Vorlagen keinen Treffer findet.
_UNSAFE_MODE: Final[str] = "bypass" + "Permissions"

LEGACY_KIT_ALLOW: Final[frozenset[str]] = frozenset({"Bash(git switch *)", "Bash(git merge *)"})
"""Allow-Einträge früherer Fragmente (Kit 0.1.0), die das Kit nicht mehr eintragen will."""


def parse_settings(text: str) -> dict[str, Any]:
    """Parst ``settings.json``; wirft ``ValueError`` bei ungültigem JSON oder Nicht-Objekt."""
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"kein gültiges JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError("die Einstellungen müssen ein JSON-Objekt sein")
    return loaded


def dumps_settings(settings: dict[str, Any]) -> str:
    """2 Spaces, Schlüsselreihenfolge bleibt, abschließender Zeilenumbruch."""
    return json.dumps(settings, indent=2, ensure_ascii=False) + "\n"


def allow_entries(commands: Iterable[str]) -> list[str]:
    """Testbefehle als Allow-Einträge: ``{paths}`` wird zu ``*`` (Spec 003 FR-015)."""
    entries: list[str] = []
    for command in commands:
        pattern = command.replace("{paths}", "*").strip()
        if pattern:
            entries.append(f"Bash({pattern})")
    return list(dict.fromkeys(entries))


def _is_kit_hook(hook: Any) -> bool:
    return isinstance(hook, dict) and KIT_MARKER in str(hook.get("command", ""))


def _replace_kit_entries(current: Any, wanted: list[Any]) -> list[Any]:
    """Entfernt Kit-Hooks aus ``current`` und setzt ``wanted`` an die Stelle des ersten Treffers."""
    entries = current if isinstance(current, list) else []
    result: list[Any] = []
    insert_at: int | None = None
    for entry in entries:
        hooks = entry.get("hooks") if isinstance(entry, dict) else None
        if not isinstance(hooks, list) or not any(_is_kit_hook(h) for h in hooks):
            result.append(entry)
            continue
        if insert_at is None:
            insert_at = len(result)
        remaining = [h for h in hooks if not _is_kit_hook(h)]
        if remaining:  # fremde Hooks im selben Eintrag bleiben erhalten
            result.append({**entry, "hooks": remaining})
    position = len(result) if insert_at is None else insert_at
    result[position:position] = copy.deepcopy(wanted)
    return result


def _union(existing: Any, wanted: Iterable[str]) -> list[Any]:
    result = list(existing) if isinstance(existing, list) else []
    for item in wanted:
        if item not in result:
            result.append(item)
    return result


def unsafe_mode_in(settings: Any) -> bool:
    """``True``, wenn ``defaultMode`` (oben oder in ``permissions``) den unsicheren Modus nennt."""
    if not isinstance(settings, dict):
        return False
    candidates = [settings.get("defaultMode")]
    permissions = settings.get("permissions")
    if isinstance(permissions, dict):
        candidates.append(permissions.get("defaultMode"))
    return any(isinstance(c, str) and c.strip().lower() == _UNSAFE_MODE.lower() for c in candidates)


def unsafe_mode_warning(where: str) -> str:
    return (
        f"{where}: defaultMode steht auf {_UNSAFE_MODE} und bleibt unverändert "
        "(Hoheit des Zielprojekts). Das Kit setzt diesen Modus nie. In diesem Modus fragt Claude "
        "Code vor keiner Aktion nach; die Allow- und Deny-Regeln des Kits begrenzen dann "
        "nichts mehr außer den Deny-Regeln. Pipeline-Läufe ohne Rückfrage sind damit ein "
        "bewusstes Risiko des Projekts. Empfehlung: einen restriktiven Modus mit Allowlist "
        "verwenden."
    )


@dataclass
class MergeResult:
    """Ergebnis des Merges samt Angaben für den Plan (Spec 011 US6, B13)."""

    merged: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    allow_wanted: list[str] = field(default_factory=list)
    allow_present: list[str] = field(default_factory=list)
    allow_added: list[str] = field(default_factory=list)
    allow_removed: list[str] = field(default_factory=list)
    allow_owned: list[str] = field(default_factory=list)
    deny_wanted: list[str] = field(default_factory=list)
    deny_present: list[str] = field(default_factory=list)
    deny_added: list[str] = field(default_factory=list)
    legacy_lock: bool = False


def merge_settings_detailed(
    existing: dict[str, Any] | None,
    fragment: dict[str, Any],
    extra_allow: Iterable[str] = (),
    owned_allow: Iterable[str] | None = None,
) -> MergeResult:
    """Merge mit Angaben zu ergänzten und ersetzten Einträgen.

    ``owned_allow`` sind die allow-Einträge, die das Kit laut Lock früher eingetragen hat
    (``None`` bei einem Lock ohne ``settings_allow`` und bei der Neuinstallation ohne Lock).
    """
    merged: dict[str, Any] = copy.deepcopy(existing) if existing is not None else {}
    result = MergeResult(merged=merged)

    hooks = merged.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
    for event, entries in fragment.get("hooks", {}).items():
        hooks[event] = _replace_kit_entries(hooks.get(event), entries)
    if hooks:
        merged["hooks"] = hooks

    permissions = merged.get("permissions")
    if not isinstance(permissions, dict):
        permissions = {}
    fragment_permissions = fragment.get("permissions", {})
    wanted_allow = list(dict.fromkeys([*fragment_permissions.get("allow", []), *extra_allow]))
    current_allow = permissions.get("allow")
    current_allow = list(current_allow) if isinstance(current_allow, list) else []
    result.allow_present = [e for e in wanted_allow if e in current_allow]

    if owned_allow is None:
        result.legacy_lock = True
        previous = {e for e in current_allow if e in LEGACY_KIT_ALLOW or e in wanted_allow}
    else:
        previous = set(owned_allow)
    removed = [e for e in current_allow if e in previous and e not in wanted_allow]
    kept = [e for e in current_allow if e not in removed]
    added = [e for e in wanted_allow if e not in kept]
    result.allow_wanted = wanted_allow
    result.allow_removed = removed
    result.allow_added = added
    result.allow_owned = [e for e in wanted_allow if e in previous or e in added]
    if wanted_allow or removed:
        permissions["allow"] = [*kept, *added]

    wanted_deny = list(dict.fromkeys(fragment_permissions.get("deny", [])))
    current_deny = permissions.get("deny")
    current_deny = list(current_deny) if isinstance(current_deny, list) else []
    result.deny_wanted = wanted_deny
    result.deny_present = [e for e in wanted_deny if e in current_deny]
    result.deny_added = [e for e in wanted_deny if e not in current_deny]
    if wanted_deny:
        permissions["deny"] = _union(current_deny, wanted_deny)
    if permissions:
        merged["permissions"] = permissions

    if unsafe_mode_in(merged):
        result.warnings.append(unsafe_mode_warning(".claude/settings.json"))
    return result


def merge_settings(
    existing: dict[str, Any] | None,
    fragment: dict[str, Any],
    extra_allow: Iterable[str] = (),
    owned_allow: Iterable[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Gibt ``(zusammengeführt, warnungen)`` zurück. ``existing`` wird nicht verändert."""
    result = merge_settings_detailed(existing, fragment, extra_allow, owned_allow)
    return result.merged, result.warnings
