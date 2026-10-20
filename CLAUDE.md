# CLAUDE.md

## Überblick

Dieses Repository ist ein Mixed Repo aus:

- wiederverwendbarem Spec-Agent-Blueprint
- Mehrprojekt-Dashboard

Beide Bereiche sind absichtlich gemeinsam versioniert.

## Architekturregeln

1. `packages/contracts` ist die Source of Truth für Eventformen, Projektregistrierung und Statusbegriffe.
2. Dashboard-UI muss Deep Links unterstützen.
3. Default-Startansicht des Dashboards ist Portfolio.
4. Dashboard speichert nur Metadaten.
5. Caddy wird extern betrieben und hier nicht verwaltet.
