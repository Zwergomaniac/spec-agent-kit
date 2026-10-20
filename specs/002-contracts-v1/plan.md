# Implementation Plan: Contracts v1 (umfasst die Umsetzung von Spec 001)

**Branch**: `002-contracts-v1` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md), [../001-domain-model-vocabulary/spec.md](../001-domain-model-vocabulary/spec.md)

## Summary

Spec 001 (Vokabular) und Spec 002 (Schemas) werden gemeinsam in `packages/contracts` umgesetzt. Zugleich entsteht das Monorepo-Tooling, das alle Folge-Specs brauchen: pnpm-Workspace, Python-Engine-Skelett mit uv, echte `lint`-, `test`- und `build`-Skripte und CI.

## Technical Context

- **Language/Version:** TypeScript 5.x (Node 22+), Python ≥ 3.11
- **Primary Dependencies:**
  - TS: `zod` (v3), `json-schema-to-zod` (dev), `ajv` + `ajv-formats` (dev, für Tests), `vitest`, `typescript`
  - Python: `jsonschema` (mit format-checker), `pyyaml`; dev: `pytest`, `ruff`
- **Storage:** keine
- **Testing:** vitest (TS), pytest (Python), gemeinsame Beispieldateien
- **Target Platform:** Windows, Linux, macOS
- **Project Type:** Bibliothek (Contracts) und Monorepo-Gerüst
- **Constraints:** Generierter Code wird eingecheckt. Der Check `contracts:check` schlägt fehl, wenn die Generierung nicht aktuell ist.

## Constitution Check

| Prinzip | Erfüllt durch |
|---|---|
| I Contracts zuerst | JSON Schema als Quelle, Generierung, Gleichheitstest Python ↔ Schema |
| II Nur Metadaten | `additionalProperties: false`, Größenlimits, `reason` ≤ 500 Zeichen |
| III Hoheit des Zielprojekts | nicht betroffen |
| IV Sicherer Default | Ingest-Schema mit Limits; Auth in Spec 007 |
| V Planen und Umsetzen getrennt | Umsetzung durch Subagent |
| VI Erprobtes übernehmen | Felder aus ImmoAgent 092/093 übernommen, Mapping in Spec 001 Anhang A |
| VII Testbar und ehrlich | Tests in beiden Sprachen, CI, README-Matrix |
| VIII Generisch | keine Projektwerte im Schema |

## Project Structure

```text
package.json                 # echte Skripte: lint, test, build, contracts:gen, contracts:check
pnpm-workspace.yaml          # packages/contracts, apps/* (agent-blueprint ist kein npm-Paket)
tsconfig.base.json
.github/workflows/ci.yml     # pnpm install, pnpm -r test, uv sync + pytest + ruff in packages/engine
packages/contracts/
  package.json               # name @sak/contracts, type module, exports ./src/index.ts
  schema/
    vocabulary.json          # {"version":1,"levels":{"stage":[...],"run_state":[...],"run_kind":[...],"verdict":[...],"severity":[...],"attention_kind":[...],"event_type":[...],"role":[...],"gate":[...],"station_state":[...],"run_source":["local","cloud"],"marker_kind":["deploy","verified"],"ticker_kind":["commit","deploy","verified"]}}
    labels/de.json           # {"stage":{"specified":"Spec",...},...} vollständig
    common.schema.json       # $defs: projectKey, runId, specDir, ulid, timestamp, sha40, reason, origin
    event.schema.json        # oneOf je type mit if/then oder discriminator auf type
    board.schema.json
    ingest.schema.json       # Anfrage und Ergebnis
  examples/
    valid/  invalid/         # je Schema; Dateiname beschreibt den Fall
  scripts/
    gen-zod.mjs              # schema → src/generated/*.ts (Zod) ; prettier-unabhängig, deterministisch
    sync-python.mjs          # kopiert schema/ → packages/engine/src/spec_agent_kit/schemas/
  src/
    index.ts                 # re-export Zod, Typen, vocabulary, labels, deepLinks
    generated/               # eingecheckt
    deep-links.ts
  test/
    schemas.test.ts          # ajv validiert examples; vocabulary ↔ enum-Abgleich; labels vollständig
    zod.test.ts              # Zod beurteilt examples wie ajv
    deep-links.test.ts
packages/engine/
  pyproject.toml             # name spec-agent-kit, requires-python >=3.11, deps jsonschema,pyyaml; [project.scripts] sak = "spec_agent_kit.cli:main"; package data schemas/**
  src/spec_agent_kit/
    __init__.py              # __version__ = "0.1.0"
    cli.py                   # argparse-Gerüst, UTF-8-reconfigure, Exit-Konventionen; Unterbefehl `sak version`
    contracts.py             # load_schema(name), validate_event(obj), validate_board(obj), new_ulid(), now_rfc3339(), vocabulary(), label(level, value, locale="de")
    schemas/                 # Kopie (sync)
  tests/
    test_contracts.py        # examples valid/invalid; Kopie == packages/contracts/schema (byte-gleich); ULID-Format/Monotonie
```

**Strukturentscheidung:**
- Ein einziges Python-Paket `spec_agent_kit`. Die Folge-Specs ergänzen Unterpakete.
- Die alten Mock-Dateien aus `apps/` bleiben in diesem Schritt, außer `routes.ts`, das gelöscht wird. Sie werden in Spec 007 ersetzt.
- `examples/event-payloads/` wird gelöscht.

## Wichtige Details für die Umsetzung

- **Event-Schema:**
  - Hülle mit `type` als Enum.
  - `data` per `allOf` mit `if: {properties: {type: {const: X}}} then: {properties: {data: {$ref: "#/$defs/data_X"}}}`.
  - `run_id` ist Pflicht für alle Typen außer `diag.hook`.
- **Regex-Formate:**
  - projectKey: `^[a-z](?:[a-z0-9-]{0,38}[a-z0-9])$`
  - runId: `^\d{3}-\d{8}-\d{6}(?:-[a-z0-9]{1,8})?$` (Suffix für späteren Parallelbetrieb)
  - specDir: `^\d{3}-[a-z0-9][a-z0-9-]{0,80}$`
  - ulid: `^[0-9A-HJKMNP-TV-Z]{26}$`
  - timestamp: `format: date-time` plus Pattern mit Pflicht-Zeitzone
- **Größenlimits** (8 KB, 512 KB, 2 MB) sind nicht per Schema ausdrückbar. Sie werden als Konstanten `LIMITS` exportiert, in beiden Sprachen gleich, und mit Tests abgesichert.
- **Die Labels `de`** stammen aus Spec 001: Tabellen in FR-006, FR-010, FR-015, FR-017, FR-021, dazu Anhang A. Für `event_type` gilt `run.started` → „Lauf gestartet“ usw.

## Complexity Tracking

Keine Verstöße.
