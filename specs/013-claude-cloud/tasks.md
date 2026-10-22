# Tasks: Betrieb in Claude Cloud

**Input**: [spec.md](spec.md). Ein Strang, Branch `013-cloud`. Die Agents haken nicht ab.

- [X] T001 Contracts: `dashboard.auth` (FR-001), Beispiele, `pnpm contracts:gen`, Tests TS und Python.
- [X] T002 Engine: Auflösung des Modus (Config + `SAK_DASHBOARD_AUTH`, FR-002); Push-Client ohne Header im Proxy-Modus (FR-003); CA-Bundle aus Umgebung (FR-004). Tests SC-001.
- [X] T003 Diagnose: Erkennung von Proxy-Fehlern (FR-006), Meldungen in `doctor` und `dashboard status` (US2), `connect --auth proxy` (FR-005). Tests SC-002 mit einem Test-Proxy in tmp, der CONNECT mit 403 beantwortet.
- [X] T004 Doku: `docs/cloud.md`, README-Abschnitt, Vorlage `config.yml` (kommentiert `auth`). Kit-Version 0.4.0.
- [X] T005 Alles grün: pytest in zwei Teilen, ruff, `pnpm -r test`, `contracts:check`, `board:check`.
