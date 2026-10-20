# Offene Punkte nach v1

Stand 2026-10-20, nach Umsetzung der Specs 001 bis 007. Jeder Punkt nennt die Herkunft und einen Vorschlag. Verbindliche Entscheidungen treffen der Betreiber und die jeweilige Spec.

## Qualität und Betrieb

1. **CI lief noch nie auf einem Remote.**
   Herkunft: Spec 005 T014, Spec 006. Ein `origin` ist eingetragen (GitHub), enthält aber nur den ersten Commit; die Arbeit der Specs 001 bis 007 ist nicht gepusht.
   Vorschlag: Nach Freigabe des Betreibers pushen und den Workflow `.github/workflows/ci.yml` (TS, Python, Smoke-Test, Ubuntu und Windows) einmal real laufen lassen; Fehler beheben.

2. **Playwright-E2E nicht in der CI.**
   Herkunft: Spec 007 T020. Die Tests laufen lokal (`pnpm build`, dann `pnpm --filter @sak/dashboard-web e2e`); in der CI fehlt die Browser-Installation.
   Vorschlag: Eigener CI-Job mit `playwright install --with-deps chromium`, nur auf Ubuntu.

3. **`docker build` und SC-003 ungetestet.**
   Herkunft: Spec 007 T018, T021. Auf der Entwicklungsmaschine gibt es kein Docker. Das Dockerfile wurde nie gebaut, Startzeit unter 5 s und RAM unter 150 MB (SC-003) wurden nicht gemessen.
   Vorschlag: Build und Messung auf einer Maschine mit Docker, Ergebnis in `deploy/dashboard/README.md` festhalten; optional ein CI-Job für den Build.

4. **Generierter Zod-Code ist unformatiert.**
   Herkunft: Spec 002 T012 (`packages/contracts/src/generated`).
   Vorschlag: Generator-Ausgabe durch einen Formatter schicken, solange `contracts:check` deterministisch bleibt.

5. **Python-Suite dauert etwa 5 Minuten.**
   Herkunft: Specs 003 bis 006 (viele Git- und Prozess-Tests).
   Vorschlag: `pytest-xdist` prüfen (`-n auto`); Tests mit Git-Fixtures müssen dafür unabhängig sein. Langsame Tests mit einem Marker abtrennen.

## Vokabular und Darstellung

6. **Portfolio-Warnungen sind kein Vokabular.**
   Herkunft: Spec 007 T010, T013. `idle` und `no_push_24h` kommen aus der API; die Texte „Lauf inaktiv“ und „Kein Push seit über 24 Std.“ stehen in `apps/dashboard-web/src/components/ProjectCard.tsx`.
   Vorschlag: Eine Vokabular-Ebene `portfolio_warning` samt Labels in `packages/contracts` einführen (Constitution I) und die UI-Texte entfernen.

7. **Deutsche Labels vom Betreiber gegenlesen lassen.**
   Herkunft: Spec 002 T006. Labels ohne Vorgabe (Gate-Arten, Ereignisarten, `run_source`, `marker_kind`, `ticker_kind`, `board_source`, `hook_phase`, `diag.hook`) sind nach dem Muster der Spec-Tabellen formuliert.
   Vorschlag: Gegenlesen in `packages/contracts/schema/labels/de.json`.

8. **Optional: Event für `building → reviewing`.**
   Herkunft: Spec 003 T003. Das Vokabular kennt keinen Ereignistyp dafür, der Wechsel bleibt ohne Event (wie in der Referenz).
   Vorschlag: Nur aufnehmen, wenn das Dashboard den Wechsel zeitlich darstellen soll. Zuerst Vokabular und Schema, dann Engine (Constitution I).

## Erweiterungen

9. **Parallelbetrieb.**
   Herkunft: Constitution VIII, Spec 001 FR-013, Spec 007 (Tab `conflicts` ist ein Hinweis). Fehlt: Worktrees, Integrator-Rolle (in der Config reserviert, nicht aktivierbar), Konflikt-Radar mit Daten für den Tab, Lauf-ID-Suffix bei gleichzeitigen Starts.
   Vorschlag: Eigene Spec; Daten für `conflicts` zuerst im Board-Vertrag festlegen.

10. **Lauf-Art `manual`.**
    Herkunft: Spec 001 FR-025. Der Wert ist im Vokabular reserviert, die Engine erzeugt keine solchen Läufe.
    Vorschlag: Erst modellieren, wenn Arbeit der Hauptsitzung außerhalb der Pipeline im Board erscheinen soll.

11. **Plugins.**
    Herkunft: ADR 0001 E6, Constitution VIII, Spec 006 T005. `plugins: []` ist nur reserviert. Offen: graphify, impeccable und Queue/Blocker/Entscheidungen, die `blocker`- und `decision`-Einträge im Board erzeugen sollen; `metrics.blocked` ist bis dahin immer 0.
    Vorschlag: Plugin-Schnittstelle in einer eigenen Spec; der Kern bleibt ohne Plugins lauffähig.

## Rollout

12. **Pilot AI-Forge (Spec 008) steht aus.**
    Herkunft: Spec 008, Spec 004 T009. Offen sind der Init gegen ein echtes Projekt, Board-Plausibilität, ein Pipeline-Lauf und `evaluation.md`. Die Werte in `examples/ai-forge.config.yml` sind ungeprüft (zum Beispiel `stages` bei `deploy.command: null`). Zu klären sind außerdem Unterschiede zu spec-kit 0.12 (Artefaktnamen, `init-options.json`).
    Vorschlag: Mit Freigabe des Betreibers auf dem Branch `sak-pilot` (Spec 008 T001 ff.).

13. **Rückmigration von ImmoAgent.**
    Herkunft: Spec 001 Anhang A, Spec 002 SC-003. Die Zuordnungstabelle liegt vor; ImmoAgent nutzt weiterhin sein eigenes `pipeline.py` und `dev_board.py`.
    Vorschlag: Nach dem Pilot eine Spec für die Umstellung (Umbenennung laut Anhang A).

14. **Verteilung per `uvx --from git+…`.**
    Herkunft: Spec 005 T002 (Kit-Wurzel). Init und Upgrade laufen nur aus dem Kit-Repo (`kit_root()`); die vendorte Kopie im Zielprojekt kann sie nicht ausführen.
    Vorschlag: Braucht ein erreichbares Remote (siehe Punkt 1); danach prüfen, wie die Kit-Wurzel dort gefunden wird.

## Kleinigkeiten

15. **Port 5192 kollidiert lokal mit dem ImmoAgent-Board.**
    Herkunft: Spec 006 T008. `sak board serve` nutzt den Default 5192 (`DEFAULT_PORT` in `packages/engine/src/spec_agent_kit/board/serve.py`); belegte Ports ergeben Exit 2. Workaround: `--port`.
    Vorschlag: Einen anderen Default-Port wählen.
