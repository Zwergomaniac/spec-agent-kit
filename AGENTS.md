# AGENTS.md

## Repo-Typ

Monorepo mit zwei Produkten in einem gemeinsamen System:

- Agent Blueprint / Init / Integrationen
- Dashboard API / Web

## Wichtige Invarianten

- `packages/contracts` ist führend.
- Dashboard muss per URL direkt auf `portfolio`, `project` und `run` navigierbar sein.
- Portfolio ist die Default-Ansicht.
