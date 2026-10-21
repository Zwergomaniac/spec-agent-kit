"""Einmalige, wiederholbare Übernahme alter Daten (Spec 010)."""

from __future__ import annotations


class MigrateError(Exception):
    """Der Import kann nicht starten (zum Beispiel fehlt das Quellverzeichnis)."""
