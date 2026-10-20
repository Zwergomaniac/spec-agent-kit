# CLAUDE.md

## Überblick

Dieses Repository ist ein Mixed Repo aus:

- wiederverwendbarem Spec-Agent-Blueprint
- Mehrprojekt-Dashboard

Beide Bereiche sind absichtlich gemeinsam versioniert.

## Architekturregeln

1. `packages/contracts` ist die Source of Truth für Eventformen, Projektregistrierung und Statusbegriffe (Ziel; Stand siehe README „Status je Baustein“).
2. Dashboard-UI muss Deep Links unterstützen.
3. Default-Startansicht des Dashboards ist Portfolio.
4. Dashboard speichert nur Metadaten.
5. Caddy wird extern betrieben und hier nicht verwaltet.

## Arbeitsweise

- Specs entstehen mit spec-kit unter `specs/NNN-*` (Dogfooding).
- Die Hauptsitzung plant (Specs, Pläne, ADRs); Umsetzung erfolgt durch Subagents.
- Umsetzung erst nach ausdrücklichem „umsetzen“ des Betreibers je Spec.
- Referenzimplementierung: `D:\Dev Department\Project Repos\ImmoAgent` (nur lesen). Pilotprojekt: `AI-Forge`.
- Kein `bypassPermissions` als Default in Templates.
