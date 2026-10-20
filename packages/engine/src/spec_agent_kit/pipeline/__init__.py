"""Pipeline-Engine (Spec 003): Läufe, Zustandsmaschine, Schutz, Urteile, Hooks.

Alles Mechanische der Agenten-Pipeline liegt hier, damit Orchestrator-Skill und Agents kurz bleiben.
Die Befehle erscheinen als ``sak run``, ``sak hook`` und ``sak event`` (siehe ``cli.py``).
"""

from __future__ import annotations


class RefusedError(Exception):
    """Eine Regel wurde verletzt (Exit 1). ``extra`` wird in die JSON-Antwort übernommen."""

    def __init__(self, message: str, **extra: object) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra


class UsageError(Exception):
    """Der Befehl wurde falsch aufgerufen (Exit 2)."""
