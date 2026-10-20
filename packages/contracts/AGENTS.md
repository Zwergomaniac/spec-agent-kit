# AGENTS.md

Contracts sind Source of Truth (Constitution I, Spec 001 und 002).

- Die Quelle ist `schema/`: `vocabulary.json`, `labels/de.json`, `limits.json` und die `*.schema.json`.
  Änderungen passieren nur dort.
- Ein neuer Enum-Wert steht an zwei Stellen: Schema (`common.schema.json`) und `vocabulary.json` samt Label.
  Tests erzwingen die Übereinstimmung.
- `src/generated/` und `packages/engine/src/spec_agent_kit/schemas/` werden nie von Hand geändert.
  Erzeugen mit `pnpm contracts:gen`, prüfen mit `pnpm contracts:check`. Das Ergebnis wird eingecheckt.
- In Schema-Mustern (`pattern`) keine Backslashes verwenden (`[0-9]` statt `\d`, `[.]` statt `\.`):
  der Zod-Generator verdoppelt sie nicht. `gen-zod.mjs` bricht sonst ab.
- Nur rückwärtskompatible Änderungen innerhalb von `/1` (Spec 002 FR-008). Alles andere braucht eine neue Hauptversion.
