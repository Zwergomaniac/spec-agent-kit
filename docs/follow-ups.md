# Offene Punkte nach v1

Stand 2026-10-21, nach Umsetzung der Specs 001 bis 007, 009 und 011. Die Befunde des ImmoAgent-Trials (Spec 011) sind umgesetzt und hier gestrichen. Jeder Punkt nennt die Herkunft und einen Vorschlag. Verbindliche Entscheidungen treffen der Betreiber und die jeweilige Spec.

## Qualität und Betrieb

1. **CI lief noch nie auf einem Remote.**
   Herkunft: Spec 005 T014, Spec 006. Ein `origin` ist eingetragen (GitHub), enthält aber nur den ersten Commit; die Arbeit der Specs 001 bis 007 ist nicht gepusht.
   Vorschlag: Nach Freigabe des Betreibers pushen und den Workflow `.github/workflows/ci.yml` (TS, Python, Smoke-Test, Ubuntu und Windows) einmal real laufen lassen; Fehler beheben.

2. **Playwright-E2E nicht in der CI.**
   Herkunft: Spec 007 T020. Die Tests laufen lokal (`pnpm build`, dann `pnpm --filter @sak/dashboard-web e2e`); in der CI fehlt die Browser-Installation.
   Vorschlag: Eigener CI-Job mit `playwright install --with-deps chromium`, nur auf Ubuntu.

3. **Generierter Zod-Code ist unformatiert.**
   Herkunft: Spec 002 T012 (`packages/contracts/src/generated`).
   Vorschlag: Generator-Ausgabe durch einen Formatter schicken, solange `contracts:check` deterministisch bleibt.

4. **Python-Suite dauert etwa 5 Minuten.**
   Herkunft: Specs 003 bis 006 (viele Git- und Prozess-Tests).
   Vorschlag: `pytest-xdist` prüfen (`-n auto`); Tests mit Git-Fixtures müssen dafür unabhängig sein. Langsame Tests mit einem Marker abtrennen.

## Vokabular und Darstellung

5. **Portfolio-Warnungen sind kein Vokabular.**
   Herkunft: Spec 007 T010, T013. `idle` und `no_push_24h` kommen aus der API; die Texte „Lauf inaktiv“ und „Kein Push seit über 24 Std.“ stehen in `apps/dashboard-web/src/components/ProjectCard.tsx`.
   Vorschlag: Eine Vokabular-Ebene `portfolio_warning` samt Labels in `packages/contracts` einführen (Constitution I) und die UI-Texte entfernen.

6. **Deutsche Labels vom Betreiber gegenlesen lassen.**
   Herkunft: Spec 002 T006. Labels ohne Vorgabe (Gate-Arten, Ereignisarten, `run_source`, `marker_kind`, `ticker_kind`, `board_source`, `hook_phase`, `diag.hook`) sind nach dem Muster der Spec-Tabellen formuliert.
   Vorschlag: Gegenlesen in `packages/contracts/schema/labels/de.json`.

7. **Optional: Event für `building → reviewing`.**
   Herkunft: Spec 003 T003. Das Vokabular kennt keinen Ereignistyp dafür, der Wechsel bleibt ohne Event (wie in der Referenz).
   Vorschlag: Nur aufnehmen, wenn das Dashboard den Wechsel zeitlich darstellen soll. Zuerst Vokabular und Schema, dann Engine (Constitution I).

## Erweiterungen

8. **Parallelbetrieb.**
   Herkunft: Constitution VIII, Spec 001 FR-013, Spec 007 (Tab `conflicts` ist ein Hinweis). Fehlt: Worktrees, Integrator-Rolle (in der Config reserviert, nicht aktivierbar), Konflikt-Radar mit Daten für den Tab, Lauf-ID-Suffix bei gleichzeitigen Starts.
   Vorschlag: Eigene Spec; Daten für `conflicts` zuerst im Board-Vertrag festlegen.

9. **Lauf-Art `manual`.**
    Herkunft: Spec 001 FR-025. Der Wert ist im Vokabular reserviert, die Engine erzeugt keine solchen Läufe.
    Vorschlag: Erst modellieren, wenn Arbeit der Hauptsitzung außerhalb der Pipeline im Board erscheinen soll.

10. **Plugins.**
    Herkunft: ADR 0001 E6, Constitution VIII, Spec 006 T005. `plugins: []` ist nur reserviert. Offen: graphify, impeccable und Queue/Blocker/Entscheidungen, die `blocker`- und `decision`-Einträge im Board erzeugen sollen; `metrics.blocked` ist bis dahin immer 0.
    Vorschlag: Plugin-Schnittstelle in einer eigenen Spec; der Kern bleibt ohne Plugins lauffähig.

## Rollout

11. **Pilot AI-Forge (Spec 008) steht aus.**
    Herkunft: Spec 008, Spec 004 T009. Offen sind der Init gegen ein echtes Projekt, Board-Plausibilität, ein Pipeline-Lauf und `evaluation.md`. Die Werte in `examples/ai-forge.config.yml` sind ungeprüft (zum Beispiel `stages` bei `deploy.command: null`). Zu klären sind außerdem Unterschiede zu spec-kit 0.12 (Artefaktnamen, `init-options.json`).
    Vorschlag: Mit Freigabe des Betreibers auf dem Branch `sak-pilot` (Spec 008 T001 ff.).

12. **Rückmigration von ImmoAgent.**
    Herkunft: Spec 001 Anhang A, Spec 002 SC-003. Die Zuordnungstabelle liegt vor; ImmoAgent nutzt weiterhin sein eigenes `pipeline.py` und `dev_board.py`.
    Vorschlag: Nach dem Pilot eine Spec für die Umstellung (Umbenennung laut Anhang A).

13. **Verteilung per `uvx --from git+…`.**
    Herkunft: Spec 005 T002 (Kit-Wurzel). Init und Upgrade laufen nur aus dem Kit-Repo (`kit_root()`); die vendorte Kopie im Zielprojekt kann sie nicht ausführen.
    Vorschlag: Braucht ein erreichbares Remote (siehe Punkt 1); danach prüfen, wie die Kit-Wurzel dort gefunden wird.

## Kleinigkeiten

14. **`docker builder prune --keep-storage` ist veraltet.**
    Herkunft: Spec 009 B06. Neuere Docker-Versionen kennen die Option nur noch als veraltet; `deploy-vps.sh --prune` nutzt sie noch.
    Vorschlag: Das Skript auf die neue Option umstellen (und gegen die Docker-Version auf dem VPS prüfen).

15. **Build-Cache auf dem VPS dauerhaft begrenzen.**
    Herkunft: Spec 009 C03. Die Platte lief dort mit 50 GB Build-Cache voll; `--prune` räumt nur beim Deploy auf.
    Vorschlag: Eine feste Grenze über `daemon.json` setzen. Das braucht einen Neustart von Docker, also mit dem Betreiber abstimmen.

16. **`sak upgrade` lehnt bei uncommitteten Kit-Dateien ab.**
    Herkunft: Spec 009 C03. Das ist eine Schutzregel; bei Pilot-Tests (AI-Forge, Starter uncommittet) war deshalb ein Neu-Init nötig.
    Vorschlag: Einen expliziten Modus wie `--include-uncommitted-kit-files` erwägen.

17. **Lokale Pfade in Specs und Doku sind öffentlich.**
    Herkunft: Das Repo ist öffentlich; Specs und Doku enthalten Pfade wie `D:\Dev Department\…`.
    Vorschlag: Optional durch Platzhalter ersetzen.
- **Programmatisches Kompaktieren** (Herkunft: Betreiber 2026-10-21, Spec 011 US8). Claude Code bietet innerhalb einer Sitzung keinen Weg, `/compact` aus Hooks oder Skills auszulösen. Vorschlag: prüfen, ob sich eine Sitzung von außen kompaktieren lässt (Claude Agent SDK bzw. `claude --resume` mit `/compact` als Nachricht) und ob ein Orchestrator-Wrapper das zwischen Läufen automatisch tun kann. Die Kontext-Wiederherstellung nach einem Kompaktieren (Spec 011 US8, `sak hook session-start`) ist umgesetzt; offen bleibt nur das programmatische Auslösen. Das Kit empfiehlt dem Betreiber nie, `/compact` auszuführen.

- **Auth-Probe im doctor** (Herkunft: Spec 011 B15, optional). `doctor` und `dashboard status` melden das Dashboard erst mit vorhandenem Schlüssel als ok, prüfen aber nicht, ob das Dashboard den Schlüssel akzeptiert. Vorschlag: eine Probe ohne Datenänderung, sobald die API einen passenden Endpunkt bietet.
- **Worktree-Verwaltung durch sak** (Herkunft: Spec 011 US3, Nachtrag). In 011 gilt nur die Erkennung samt Erben von URL und Schlüssel sowie die Preflight-Warnung. Eigene Worktrees unter `<repo>.sak-runs/<lauf-id>`, Board-Anzeige und `doctor`-Meldung übrig gebliebener Worktrees gehören zur Spec „Parallelbetrieb“ (Punkt 8).
