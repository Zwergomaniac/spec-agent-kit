# AGENTS.md

Default-Route ist Portfolio. Jede Kernansicht ist direkt verlinkbar (Hash-Router auf Basis von `@sak/contracts` Deep Links).

- Alle angezeigten Vokabularwerte laufen über `labelOf()` (`src/labels.ts`). Unbekannte Werte erscheinen als „unbekannt (wert)“.
- Keine eigenen Statusbegriffe erfinden: Vokabular und Labels kommen aus `packages/contracts`.
- Komponenten unter `src/components/ui` sind shadcn-Bausteine (eingecheckt). Neue per `components.json` ergänzen.
- Tailwind v4: Design-Tokens stehen in `src/index.css` (`:root` und `.dark`). Statusfarben: `success`, `warning`, `danger`, `info`.
- Dev: `pnpm --filter @sak/dashboard-web dev` (Proxy auf die API unter `SAK_API_URL`, Default `http://localhost:3000`).
- E2E: `pnpm --filter @sak/dashboard-web e2e` (siehe `e2e/`). Screenshots landen in `e2e/screenshots/` und werden nicht committet.
- Routen: Contracts-Deep-Links (`#/portfolio`, `#/project/:key?tab=board|runs|attention|conflicts`, `#/run/:key/:runId`) plus die UI-Routen `#/login` (mit `?next=`) und `#/admin` in `src/router.ts`. Der Tab `conflicts` ist in v1 nur ein Hinweis, bis es Parallelbetrieb gibt.
- Tests: `pnpm --filter @sak/dashboard-web test` (vitest). E2E braucht vorher `pnpm build` (Server auf Port 3100) und läuft nicht in der CI.
- Warnungstexte des Portfolios (`idle`, `no_push_24h`) sind UI-Texte in `ProjectCard.tsx`, kein Vokabular (siehe `docs/follow-ups.md`).
- Lokaler Modus (Spec 010): /api/meta mit mode: "local" und project_key (vor dem ersten Rendern in src/mode.tsx erkannt) schaltet Portfolio, Admin und Login ab; Start ist #/project/<key>. Es gibt dann keine Auth-Aufrufe.
- pnpm board:build (uild:local, Vite-Mode oard-local) baut die UI mit relativen Pfaden nach packages/engine/src/spec_agent_kit/board/web/ (eingecheckt, generiert, nicht von Hand ändern). pnpm board:check baut neu und prüft per git diff, dass es aktuell ist.
- Tooltips: Definitionen zentral in src/definitions.ts, Komponente src/components/Tip.tsx (Hover und Fokus, Escape schließt).
- E2E lokal: 2e/mock-board-server.ts imitiert sak board serve; 2e/local-mode.spec.ts prüft Modus, Ticker-Hover, Tooltips und den Screenshot-Vergleich lokal gegen online.
