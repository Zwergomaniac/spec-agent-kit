# Tasks: Deploy-Wege

**Input**: [spec.md](spec.md). Ein Strang, Branch `014-deploy`. Die Agents haken nicht ab.

- [ ] T001 Contracts: `deploy.methods`, `deploy.default` (FR-001), Beispiele valid/invalid, `pnpm contracts:gen`, Tests TS und Python.
- [ ] T002 Engine: Config-Normalisierung (Altform → `methods.default`), `config check` (SC-002), `sak deploy plan` (FR-002, US2) inklusive `SAK_ENVIRONMENT`. Tests SC-001.
- [ ] T003 Skill `sak-pipeline` Deploy-Abschnitt (FR-003); Vorlage `config.yml`, Beispiel ImmoAgent, `docs/howto/github-actions-deploy.md` Schritt 6 (FR-004).
- [ ] T004 Kit-Version 0.5.0; README; alles grün: EIN pytest-Lauf (wie CI), ruff, `pnpm -r test`, `contracts:check`, `board:check`.
