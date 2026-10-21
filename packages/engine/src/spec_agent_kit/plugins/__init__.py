"""Plugins für das Board (Spec 010 FR-006, ADR 0001 E6).

Ein Plugin liefert zusätzliche Fakten aus Dateien des Projekts: zurückgestellte Specs, blockierte
Specs und Aufmerksamkeitseinträge. Aktiviert wird es in der Config (``plugins: [{name: ...}]``).

Ein Plugin darf das Board nie zum Absturz bringen: ``run_plugins`` fängt jede Ausnahme ab und macht
daraus einen Hinweis in ``notes``. Ein fehlerhaftes Plugin liefert dann nichts, die anderen laufen
weiter.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from spec_agent_kit.pipeline.events import clip

NOTE_MAX_CHARS: Final[int] = 280


@dataclass
class PluginContext:
    """Eingaben eines Plugins: Projektwurzel, ``options`` der Config, Spec-Verzeichnisse."""

    root: Path
    options: dict[str, Any]
    spec_dirs: list[str]


@dataclass
class PluginResult:
    """Ausgabe eines Plugins.

    ``descoped``: Spec-Verzeichnisse. ``blocked``: Spec-Verzeichnisse. ``attention``: fertige
    Einträge im Format von ``sak.board/1`` (``kind``, ``reason``, ``source``, optional ``spec``).
    ``notes``: Hinweise für das Board (zum Beispiel eine fehlende Datei).
    """

    descoped: set[str] = field(default_factory=set)
    blocked: set[str] = field(default_factory=set)
    attention: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def merge(self, other: PluginResult) -> None:
        self.descoped |= other.descoped
        self.blocked |= other.blocked
        self.attention.extend(other.attention)
        self.notes.extend(other.notes)


PluginFn = Callable[[PluginContext], PluginResult]


def registry() -> dict[str, PluginFn]:
    """Bekannte Plugins nach Name. Das Schema der Config (Enum) hält diese Liste synchron."""
    from spec_agent_kit.plugins.legacy_status import run as legacy_status

    return {"legacy-status": legacy_status}


def list_spec_dirs(root: Path) -> list[str]:
    base = root / "specs"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir())


def run_plugins(
    root: Path,
    configured: list[dict[str, Any]],
    spec_dirs: list[str],
    *,
    plugins: dict[str, PluginFn] | None = None,
) -> PluginResult:
    """Führt die konfigurierten Plugins aus. Fehler werden zu Hinweisen, nie zu Ausnahmen."""
    result = PluginResult()
    try:
        known = registry() if plugins is None else plugins
    except Exception as exc:  # ein kaputtes Plugin-Modul darf das Board nicht stoppen
        result.notes.append(
            clip(f"Plugins nicht ladbar ({type(exc).__name__}: {exc})", NOTE_MAX_CHARS)
        )
        return result
    for entry in configured:
        name = str(entry.get("name"))
        options = entry.get("options")
        function = known.get(name)
        if function is None:
            result.notes.append(
                clip(f"Plugin '{name}' ist unbekannt und wird übersprungen", NOTE_MAX_CHARS)
            )
            continue
        try:
            context = PluginContext(
                root=root,
                options=dict(options) if isinstance(options, dict) else {},
                spec_dirs=spec_dirs,
            )
            result.merge(function(context))
        except Exception as exc:  # Plugin-Fehler bleiben isoliert (Spec 010 FR-006)
            result.notes.append(
                clip(
                    f"Plugin '{name}' fehlgeschlagen ({type(exc).__name__}: {exc})", NOTE_MAX_CHARS
                )
            )
    return result
