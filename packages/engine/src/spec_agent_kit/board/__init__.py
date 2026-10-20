"""Collector (Spec 006): Board-Dokument ``sak.board/1`` aus Spec-Dateien, Git, Läufen und Events.

Es gibt keine zweite Status-Quelle: alles wird bei jedem Aufruf aus dem Repo abgeleitet.
"""

from __future__ import annotations


class BoardError(Exception):
    """Das erzeugte Board-Dokument verletzt den Vertrag (ein Bug). ``path`` nennt die Stelle."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message
