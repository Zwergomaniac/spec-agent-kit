> Protokoll einer Stack-Beratung (Stand 2026-10-20). Verbindliche Entscheidungen: siehe docs/adr/0001-framework-grundsatzentscheidungen.md.

Ja — dafür lässt sich jetzt schon eine ziemlich klare Empfehlung geben. Für dein Ziel „ein Repo, modern, hübsch, ressourcenschonend, nicht overengineered, einfacher Auth, SQLite wenn ausreichend“ würde ich **TypeScript als Einheitssprache** wählen und das Repo als leichtes Monorepo aufbauen; Hono ist ein schlanker TypeScript-Framework-Kandidat, und React + Vite + Tailwind/shadcn ist ein gängiger, moderner Stack für Admin-Dashboards. [dev](https://dev.to/deepak_kumar_1605/why-vite-is-the-right-call-for-a-modern-react-admin-panel-1k8k)

## Stack-Empfehlung

Ich halte **diesen Stack** für am sinnvollsten:

| Bereich | Empfehlung | Warum |
|---|---|---|
| Monorepo | pnpm workspace | leichtgewichtig, gut für `apps/` + `packages/`  [deepwiki](https://deepwiki.com/asudbury/modern-monorepo-template/12-repository-configuration) |
| API | Hono + TypeScript | klein, schnell, TS-first, kein schweres Framework nötig  [hono](https://hono.dev/) |
| UI | React + Vite + TypeScript | schneller Dev-Loop, passend für Dashboard-UI  [dev](https://dev.to/deepak_kumar_1605/why-vite-is-the-right-call-for-a-modern-react-admin-panel-1k8k) |
| Styling | Tailwind CSS + shadcn/ui | modern, hübsch, ohne zu viel Eigenbau  [dev](https://dev.to/deepak_kumar_1605/why-vite-is-the-right-call-for-a-modern-react-admin-panel-1k8k) |
| DB | SQLite | sehr passend für wenige Projekte, read-heavy Admin-Board, geringer Betriebsaufwand  [coddy](https://coddy.tech/docs/sqlite/when-to-use-sqlite) |
| Validation | Zod | Contracts/Inputs sauber absichern; shared contract package ist gängiges Muster  [github](https://github.com/Youssef548/ts-monorepo-template) |
| Charts | Recharts | für Dashboard leicht genug und verbreitet in React-Admin-Stacks  [adminlte](https://adminlte.io/blog/free-dashboard-templates/) |
| Auth | einfacher Session-/Passwortschutz | ausreichend für internes Admin-Board |
| Deploy | ein Container für App/API, bestehender Caddy davor | sauber zu deinem VPS-Setup passend  [github](https://github.com/cmdock/server/blob/main/docs/manuals/installation-and-setup-guide.md) |

Das wäre modern, schnell zu bauen und trotzdem nicht unnötig schwer.

## Warum ich das für dich bevorzuge

Ich würde **kein Next.js**, kein großes ORM-Monster und keinen Microservice-Zoo nehmen. Für ein internes Mehrprojekt-Dashboard mit Agent-Kit sind RAM, Einfachheit und Wartbarkeit wichtiger als maximale Framework-Magie; genau da passen leichte TS-Stacks besser als schwere Fullstack-Frameworks. [hono](https://hono.dev/docs/)

Wenn du es noch einfacher willst, wäre auch **ein einziger Hono-Service**, der API und gebaute React-App ausliefert, attraktiv. Dieses Muster ist in leichten TypeScript-Setups üblich und spart dir zusätzlichen Infrastruktur- und Containerballast. [github](https://github.com/pigontech/inkvoice/blob/main/CLAUDE.md)

## SQLite

Ja, **SQLite reicht dir sehr wahrscheinlich**. Für ein kleines Admin-Dashboard mit wenigen Projekten, überwiegend Lesezugriffen und gelegentlichen Statusschreibvorgängen ist SQLite ein sehr guter Fit; die typischen Grenzen liegen eher bei vielen gleichzeitigen Schreibern oder verteilten Mehrserver-Setups. [coddy](https://coddy.tech/docs/sqlite/when-to-use-sqlite)

Für deinen Fall spricht dafür:

- nur eine Handvoll Projekte,
- wenige Admin-Nutzer,
- viele Reads, wenige Writes,
- alles auf einem VPS,
- kein Bedarf an separatem DB-Server.

Das spart Ressourcen und Betriebskomplexität. SQLite serialisiert Writes, aber bei deinem Event-Volumen dürfte das kaum ein Problem sein; WAL-Modus erhöht die Praxistauglichkeit zusätzlich für parallele Leser. [coddy](https://coddy.tech/docs/sqlite/when-to-use-sqlite)

## UI-Stil

„Hübsch und modern, aber nicht overengineered“ heißt für mich:

- React + Vite
- Tailwind
- shadcn/ui-Komponenten
- Lucide Icons
- Recharts für 2–3 gute Diagramme
- Dark Mode
- Fokus auf klare Informationshierarchie statt Animationstricks

Das ist ein gängiges, modernes Dashboard-Muster und deutlich leichter als ein hochabstrakter Enterprise-Stack. [adminlte](https://adminlte.io/blog/react-templates/)

## Blueprint-Rollout

Bei Punkt 4 würde ich **nicht** mit reinem Copy-Paste starten. Das wird schnell unsauber, weil projektweise Namen, Pfade, Branchkonventionen, Secrets, Deploy-Details und geschützte Dateien angepasst werden müssen.

Meine Empfehlung ist eine **zweistufige Lösung**:

### Phase 1: Template + Init-CLI
Schnell gut funktioniert:
- Blueprint-Dateien liegen im Repo als Templates.
- Ein kleines CLI oder Setup-Skript kopiert sie in ein Zielprojekt.
- Dabei werden Platzhalter ersetzt und die Projektkonfig erzeugt.

Das ist schneller umsetzbar als ein vollwertiger Installer-Service und viel robuster als manuelles Kopieren.

### Phase 2: Agent-Skill oben drauf
Danach kann ein Agent-Skill denselben Installer benutzen:
- Agent fragt 5–8 Dinge ab.
- CLI schreibt Dateien.
- Agent prüft Ergebnis.
- Agent erklärt nächste Schritte.

So bleibt die eigentliche Logik im Installer/Template-System und der Skill ist nur die **Benutzerschicht**. Das ist meist besser, als die Installation nur als Prompt-Wissen zu kodieren.

## Was ich konkret nehmen würde

Meine klare Präferenz für v1:

### Gesamtstack
- **pnpm workspace Monorepo**
- **Hono API**
- **React + Vite UI**
- **Tailwind + shadcn/ui**
- **SQLite**
- **Zod Contracts**
- **ein Container**
- **bestehender Caddy davor**

### Blueprint-Ausrollung
- **Template-Dateien + kleines Init-CLI**
- später zusätzlich **Agent-Skill**, der das CLI benutzt

Das ist für Geschwindigkeit, Wartbarkeit und geringe VPS-Last aus meiner Sicht der beste Kompromiss.

## Warum kein Copy-Paste only

Copy-Paste scheitert meistens an:
- inkonsistenten Anpassungen,
- vergessenen Hooks,
- falschen Pfaden,
- divergierenden Contract-Versionen,
- fehlender Nachrüstbarkeit.

Ein kleines Initializer-Tool plus zentrale Templates vermeidet genau das und ist trotzdem deutlich einfacher als ein „vollautomatisches Plattformprodukt“.

## Meine konkrete Empfehlung je Punkt

1. **Stack:** TypeScript überall, Hono + React/Vite + Tailwind/shadcn. [hono](https://hono.dev/)
2. **DB:** SQLite ja, für deinen Umfang sehr wahrscheinlich ausreichend und ressourcenschonend. [coddy](https://coddy.tech/docs/sqlite/when-to-use-sqlite)
3. **UI:** modern und schön, aber bewusst leichtgewichtig mit Standardbausteinen. [adminlte](https://adminlte.io/blog/free-dashboard-templates/)
4. **Rollout:** nicht Copy-Paste, sondern Template + Init-CLI; Agent-Skill optional als Bedienebene darüber.  
5. **Auth:** einfacher Admin-Schutz reicht für v1.

## Meine eine nächste Frage

Ich empfehle also für v1 ganz klar: **TypeScript-Monorepo mit Hono, React/Vite, Tailwind/shadcn und SQLite.**

Soll ich auf dieser Basis als Nächstes die **konkrete Repo-Struktur und die v1-Dateiliste** für das Mixed Repo entwerfen?