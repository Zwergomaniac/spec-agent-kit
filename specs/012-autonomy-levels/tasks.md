# Tasks: Autonomie-Stufen

**Input**: [spec.md](spec.md). Ein Strang, Branch `012-autonomy`. Constitution 1.1.0 (Amendment IV) liegt bereits auf main. Die Agents haken nicht ab.

- [ ] T001 Contracts: `autonomy` in `config.schema.json` (FR-001); `run.pushed` im Vokabular, Label DE „Gepusht“, Event-Schema `data` (FR-002); Beispiele; `pnpm contracts:gen`; Tests TS und Python.
- [ ] T002 Engine: Config-Defaults; `sak run push` (FR-003) inklusive Event und Aufmerksamkeitseintrag bei Ablehnung; Tests mit Bare-Remote in `tmp_path` (SC-001, SC-002).
- [ ] T003 Board: `run.pushed` in der Lauf-Ableitung (Feld `pushed` bzw. Event im Log); „Push abgelehnt“ als Aufmerksamkeit (FR-006).
- [ ] T004 Web: Anzeige „gepusht“ in der Lauf-Ansicht und im Agenten-Panel; `board:build`.
- [ ] T005 Vorlagen: Skill `sak-pipeline` (FR-005, US2, US3), `config.yml` (FR-007), Beispiel ImmoAgent `push: after_merge`.
- [ ] T006 Version 0.3.0; README (Abschnitt Autonomie-Stufen); alles grün (`pytest`, `ruff`, `pnpm -r test`, `contracts:check`, `board:check`).
