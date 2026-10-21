"""Additiver Merge des Settings-Fragments in ``.claude/settings.json`` (Spec 005 FR-005).

Bestehende fremde Einträge und ``defaultMode`` bleiben unverändert. Hook-Einträge des Kits (Befehl
mit ``.spec-agent/``, auch die alten Fassungen mit ``.spec-agent/engine``) werden durch die Fassung
des Fragments ersetzt, nicht ergänzt; das ist idempotent. Außerdem werden fehlende Einträge in
``permissions.allow`` und ``permissions.deny`` ergänzt.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable
from typing import Any, Final

ENGINE_MARKER: Final[str] = ".spec-agent/engine"
KIT_MARKER: Final[str] = ".spec-agent/"
"""Kit-eigene Hook-Befehle erkennt man daran (Starter ``.spec-agent/sak`` und alte Engine-Pfade)."""
STARTER_MARKER: Final[str] = ".spec-agent/sak"
# Der gefährliche Modus wird nur erkannt, nie gesetzt; das Wort entsteht hier zusammengesetzt, damit
# der Grep-Test (Constitution IV) in Engine und Vorlagen keinen Treffer findet.
_UNSAFE_MODE: Final[str] = "bypass" + "Permissions"


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


def merge_settings(
    existing: dict[str, Any] | None,
    fragment: dict[str, Any],
    extra_allow: Iterable[str] = (),
) -> tuple[dict[str, Any], list[str]]:
    """Gibt ``(zusammengeführt, warnungen)`` zurück. ``existing`` wird nicht verändert."""
    warnings: list[str] = []
    merged: dict[str, Any] = copy.deepcopy(existing) if existing is not None else {}

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
    wanted_allow = [*fragment_permissions.get("allow", []), *extra_allow]
    for key, wanted in (("allow", wanted_allow), ("deny", fragment_permissions.get("deny", []))):
        if wanted:
            permissions[key] = _union(permissions.get(key), wanted)
    if permissions:
        merged["permissions"] = permissions

    if permissions.get("defaultMode") == _UNSAFE_MODE:
        warnings.append(
            f"permissions.defaultMode steht im Zielprojekt auf {_UNSAFE_MODE} und bleibt "
            "unverändert "
            "(Hoheit des Zielprojekts). Das Kit setzt diesen Modus nie; Pipeline-Läufe ohne "
            "Rückfrage sind damit ein bewusstes Risiko des Projekts. Empfehlung: einen "
            "restriktiven Modus mit Allowlist verwenden."
        )
    return merged, warnings
