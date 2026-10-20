# AGENTS.md

Default-Route ist Portfolio. Jede Kernansicht ist direkt verlinkbar (Hash-Router auf Basis von `@sak/contracts` Deep Links).

- Alle angezeigten Vokabularwerte laufen über `labelOf()` (`src/labels.ts`). Unbekannte Werte erscheinen als „unbekannt (wert)“.
- Keine eigenen Statusbegriffe erfinden: Vokabular und Labels kommen aus `packages/contracts`.
- Komponenten unter `src/components/ui` sind shadcn-Bausteine (eingecheckt). Neue per `components.json` ergänzen.
- Tailwind v4: Design-Tokens stehen in `src/index.css` (`:root` und `.dark`). Statusfarben: `success`, `warning`, `danger`, `info`.
- Dev: `pnpm --filter @sak/dashboard-web dev` (Proxy auf die API unter `SAK_API_URL`, Default `http://localhost:3000`).
- E2E: `pnpm --filter @sak/dashboard-web e2e` (siehe `e2e/`). Screenshots landen in `e2e/screenshots/` und werden nicht committet.
