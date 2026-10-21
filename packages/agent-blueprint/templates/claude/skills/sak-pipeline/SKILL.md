---
name: "sak-pipeline"
description: "Führt eine freigegebene Spec durch die Agenten-Pipeline (Builder, danach alle aktiven Prüfer parallel, begrenzte Runden, Eskalation an den Betreiber). Startet nur nach ausdrücklichem „umsetzen“ für genau diese Spec."
argument-hint: "<spec> | --release <spec> | --return <spec> | --abort <spec> | --pause <spec> | --resume <spec>"
compatibility: "Braucht .spec-agent/config.yml, die Agents der aktiven Rollen unter .claude/agents/ und die Engine unter .spec-agent/engine (uv)."
metadata:
  author: "spec-agent-kit"
user-invocable: true
disable-model-invocation: false
---

## Rolle

Du bist der **Orchestrator**: die Haupt-Sitzung. Du sprichst mit dem Betreiber (Deutsch), verteilst die Arbeit an die Subagenten und bekommst von ihnen nur **Kurzberichte und Urteile** zurück. Dadurch bleibt dein Kontext klein. Code schreibst du in diesem Ablauf **nicht** selbst. Aktionen aus `orchestrator_only` (zum Beispiel Deploy) bleiben bei dir und laufen nur nach Freigabe des Betreibers.

Abkürzung: `SAK` = `uv run --project .spec-agent/engine sak`. Jeder Befehl gibt JSON aus. `ok: false` heißt abgelehnt, der Grund steht in `error` oder `errors`. Exit 0 ist Erfolg, 1 eine fachliche Ablehnung, 2 ein Bedienfehler.

Projektspezifische Werte (Rollen, Agent-Namen, Testbefehle, Schutzpfade, Themen) stehen nie in diesem Skill. Du liest sie aus `SAK config show` und aus der Antwort von `preflight`.

## Vorbedingungen (alle prüfen, sonst abbrechen und dem Betreiber sagen, was fehlt)

1. **Ausdrückliche Freigabe**: Der Betreiber hat für **genau diese** Spec „umsetzen“ (oder Gleichwertiges) gesagt. Eine Freigabe für eine andere Spec gilt nicht. Fehlt sie, brich ab und frage nach. Die Regel „Stopp vor der Implementierung“ des Projekts gilt unverändert; dieser Skill ersetzt sie nicht.
2. `specs/<spec>/tasks.md` existiert (Specify, Clarify, Plan und Tasks sind erledigt).
3. `SAK config check` meldet `ok: true`. Dort steht auch, ob die Agent-Dateien der aktiven Rollen fehlen oder von der Config abweichen.
4. `/agents` kennt die Agents der aktiven Rollen. Fehlen sie, bitte den Betreiber, die Sitzung neu zu starten.

## Aufrufe mit Option

Nur nach ausdrücklicher Entscheidung des Betreibers für den genannten Lauf. `<run>` ist eine Lauf-ID, ein Spec-Verzeichnis oder eine Spec-Nummer.

- `--release <spec>`: `SAK run release <run> --reason "<Grund>"`, dann weiter bei **Abschluss**.
- `--return <spec>`: `SAK run return <run> --reason "<Auftrag an den Builder>"`, dann weiter bei Schritt 2 (nächste Runde, nur unterhalb des Rundenlimits).
- `--abort <spec>`: `SAK run abort <run> --reason "<Grund>"`. Der Branch bleibt unverändert bestehen. Der Befehl entfernt Links und Junctions im Lauf-Ordner selbst. Informiere den Betreiber.
- `--pause <spec>`: `SAK run pause <run> --reason "<Grund>"`.
- `--resume <spec>`: `SAK run resume <run>`, dann weiter an der unterbrochenen Station (Schritt 2 bei `building`, Schritt 4 bei `reviewing`, Eskalation bei `escalated`).

## Ablauf

**1. Start.** `SAK run preflight <spec> [--base <branch>]`. Bei einer Ablehnung meldest du den Grund und erzwingst nichts: Ein unsauberer Arbeitsstand wird nicht „aufgeräumt“. Notiere aus der Antwort `run_id`, `branch`, `base_commit`, `max_rounds`, `roles` (aktive Rollen mit Agent-Namen, Modell und Effort) und `commands`.
   - Nennt die Antwort oder Ablehnung einen verwaisten Lauf (`stale_runs`), sage es dem Betreiber. Übernimm ihn nur auf ausdrückliche Anweisung mit `SAK run preflight <spec> --takeover "<Grund>"`.
   - Für bereits umgesetzte Arbeit, etwa aus der Hauptsitzung, gibt es die Nur-Prüfung: `SAK run preflight <spec> --review-only --base-commit <sha>`. Es gibt dann keinen Builder und keinen Branch-Wechsel; weiter bei Schritt 4.

   Ab jetzt schreiben die Hooks Start, Ende und Dauer jeder Station nach `.spec-agent/state/events.jsonl`. Zustandswechsel und Eskalationen erzeugen ihre Ereignisse selbst.

**2. Builder.** Starte den Agent der Rolle `builder` (Agent-Werkzeug, `subagent_type` = Agent-Name aus `roles.builder.agent`). Der Prompt enthält: Spec-Verzeichnis, Runde, `base_commit`, die Befehle aus `commands` (einschließlich `prepare`) und ab Runde 2 die `[must]`-Befunde im Wortlaut. Seine Antwort ist ein Bericht im Pflichtformat.
   - Ist die Rolle `docs` aktiv, starte danach (nicht parallel) deren Agent mit dem Bericht des Builders.
   - Meldet ein Agent offene Fragen oder Abweichungen von der Spec, die das Ergebnis verändern: `SAK run state <run> escalated --reason "<kurz>"` und weiter bei **Eskalation**.
   - Sonst: `SAK run state <run> reviewing`.

**3. Wächter.** `SAK run guard <run>`.
   - `escalate: true` (geschützter Pfad angefasst): **keine Prüfer starten.** `SAK run state <run> escalated --gate protected_paths --reason "<reason>: <protected_hits>"`, weiter bei **Eskalation**.
   - Sonst merke die `hints` für den Code-Prüfer.

**4. Prüfer, parallel.** `SAK run snapshot` und den Wert `snapshot` merken. Starte dann **alle aktiven Prüfrollen** (`code_review`, `ui_review`, `security_review`, soweit in `roles`) **in einer einzigen Nachricht**, also mehrere Agent-Aufrufe zugleich. Der Prompt je Prüfer enthält: Spec-Verzeichnis, `run_id`, Runde, `base_commit`, die Befehle aus `commands` (einschließlich `prepare`), den **Bericht des Builders im Wortlaut** (die Prüfer wiederholen die Voll-Suite nur bei Lücken im Bericht), beim Code-Prüfer die `hints` und den Satz „Ändere nichts im Repo“.
   Danach `SAK run reviewer-check <snapshot>`. Wird abgelehnt, ist der Lauf bereits mit dem Gate `review_integrity` eskaliert: Zeige dem Betreiber `git status`, setze **nichts selbst zurück** und gehe zu **Eskalation**.

**5. Urteile ablegen.** Schreibe die Antwort jedes Prüfers mit dem Write-Werkzeug nach `.spec-agent/state/runs/<run_id>/answer-<rolle>.md` und rufe `SAK run verdict <run> <rolle> <datei>` auf. Bei ungültigem Format fordere das Urteil **einmal** neu an (mit Hinweis auf das Pflichtformat). Bleibt es ungültig, gilt `needs_human`: `SAK run state <run> escalated --gate review_integrity --reason "Urteil ungültig"` und weiter bei **Eskalation**.

**6. Entscheiden.** `SAK run combine <run>` bildet das Gesamturteil über alle aktiven Prüfrollen und setzt den Zustand. Fehlt das Urteil einer Rolle, lehnt der Befehl ab; hole es nach.
   - `approved`: weiter bei **Abschluss**.
   - `building` (Runde +1): zurück zu Schritt 2 mit **nur** den Befunden aus `must`, im Wortlaut.
   - `escalated`: weiter bei **Eskalation**. Das Gate steht in der Antwort (`round_limit` bei weiterem Änderungsbedarf in der letzten Runde).
   - `reviewed` (nur Nur-Prüfung): weiter bei **Bericht**.

   `combine` entfernt dabei Links und Junctions im Lauf-Ordner (`runs/<run_id>/`), ohne ihnen zu folgen. Am Ende eines Laufs (nach `merge` oder `reviewed`) rufst du zusätzlich `SAK run cleanup <run>` auf.

**Eskalation.** Der Lauf wartet auf den Betreiber. Berichte kurz auf Deutsch: Spec, Lauf-ID, Runde, Gate und Grund, offene `[must]`-Befunde mit Datei und Zeile, Pfad der Urteile. Nenne die Entscheidungen: `--release` (freigeben), `--return` mit Auftrag (zurück an den Builder, nur unterhalb des Rundenlimits), `--abort` (verwerfen) oder `--pause` (zurückstellen). Dann **stoppen und warten**. Du setzt eine Eskalation nie selbst zurück.

**Unterbrechung.** Bei API-Limit, Sitzungsende oder einer anderen Unterbrechung ruf `SAK run pause <run> --reason "<Grund>"` auf. Das gibt die Sperre frei; ein anderer Lauf kann starten. Fortsetzen: `SAK run resume <run>`, nur bei freier Sperre und sauberem Arbeitsstand.

**Abschluss (nur bei `approved`).** Lies die Stufe aus `SAK config show` (`autonomy.push`, `autonomy.deploy`). Wenn die Stufe einen Schritt erlaubt, führst du ihn **ohne Rückfrage** aus.
1. Sichten: `git log --oneline <base_commit>..HEAD` und `git diff --stat <base_commit>..HEAD`. Wiederhole die Tests nicht, wenn Builder und Code-Prüfer übereinstimmend grün gemeldet haben.
2. Aufräumen: `SAK run cleanup <run>` (entfernt nur Links; Ziele bleiben).
3. Mergen: `SAK run merge <run>` (Merge-Commit mit `--no-ff` in den Basis-Branch; `merge` selbst macht kein Push). Das geschieht automatisch, ohne Rückfrage. Bei einem Konflikt bricht der Befehl den Merge ab und eskaliert den Lauf; dann gehe zu **Eskalation**.
4. Pushen, je nach `autonomy.push`:
   - `after_merge`: `SAK run push <run>` direkt nach dem Merge, ohne Rückfrage. Der Befehl pusht nur den Basis-Branch, nur fast-forward, ohne Force und ohne Tags. Wird er abgelehnt (zum Beispiel non-fast-forward), versuchst du **nichts** zu reparieren: kein Pull, kein Rebase, kein Merge, kein Force. Der Lauf bekommt einen Aufmerksamkeitseintrag; melde den Grund im Kurzbericht, die Klärung bleibt beim Betreiber.
   - `manual` (Default): Nicht pushen. `SAK run push` lehnt in dieser Stufe ab. Weise im Bericht darauf hin, dass der Betreiber selbst pusht.
5. Kurzbericht an den Betreiber (Deutsch): was gebaut wurde, Testzahlen, `[may]`-Hinweise der Prüfer, Merge-Commit und Push-Ergebnis (gepusht mit Commit, abgelehnt mit Grund, oder „nicht gepusht, `autonomy.push: manual`“). Zum Deploy:
   - `autonomy.deploy: after_approval` (Default): „noch nicht deployt“ und die Frage, ob du deployen sollst.
   - `autonomy.deploy: never`: „noch nicht deployt, Deploy nur manuell“ und keine Frage.

**Bericht (Nur-Prüfung).** Fasse die Urteile und Befunde zusammen. Der Lauf endet mit `reviewed`; es gibt keinen Merge.

## Deploy

Nur auf **ausdrückliche Anweisung** des Betreibers für diese Spec, und nur bei `autonomy.deploy: after_approval`. Bei `autonomy.deploy: never` deployst du nie, auch nicht auf Anweisung: Verweise auf den Betreiber, der selbst deployt. Ein Merge oder Push gilt nie als Deploy-Freigabe.

Lies `deploy.command` aus `SAK config show`; ist es `null`, gibt es keinen Deploy. Führe den Befehl selbst aus (er steht in `orchestrator_only`, kein Subagent führt ihn aus). Committe nach erfolgreichem Deploy einen Marker mit dem Betreff `deploy(NNN): <kurz>`, wobei `NNN` die Spec-Nummer ist. Eine Live-Prüfung markierst du auf Anweisung mit `verified(NNN): <kurz>`. Das Dashboard liest diese Marker; sie müssen nach dem letzten Task-Commit der Spec liegen.

Bei `autonomy.push: after_merge` pushst du den Marker danach ohne Rückfrage mit `SAK run push <run>` (der Basis-Branch muss den Merge-Commit des Laufs enthalten). Bei `manual` bleibt der Marker lokal; sage es im Bericht.

## Regeln

- Subagenten liefern Kurzberichte und Urteile, keine Roh-Logs. Du gibst dem Betreiber nur Zusammenfassungen weiter.
- Ein Lauf zur Zeit. Prüfer laufen parallel, der Builder nie parallel zu Prüfern.
- Änderungen an den Dateien dieser Pipeline (Kern-Schutz und `guard.protected_paths`) macht nie die Pipeline selbst. Sie gehen immer an den Betreiber.
- Kein direktes `git push` (die Deny-Regel sperrt es), kein `--no-verify`. Gepusht wird ausschließlich mit `SAK run push`, nur bei `autonomy.push: after_merge`, nie mit Force. Subagenten pushen nie. Aktionen aus `orchestrator_only` führst nur du aus, und nur nach Freigabe.
- Fachliche Themen, das Rundenlimit, ein abgelehnter Push und jede andere Eskalation bleiben beim Betreiber; `autonomy` lockert nur Merge, Push und Deploy nach `approved`.
- **Nach einem Kompaktieren** (der Kontext wurde automatisch oder manuell gekürzt) liefert der Hook `SessionStart` eine Kurzfassung des aktiven Laufs (Lauf-ID, Spec, Zustand, Runde, Rollen, Muss-Befunde, nächster Schritt). Arbeite danach ohne Rückfrage an dieser Stelle weiter. Gibt es keine Kurzfassung, hole dir den Stand mit `SAK run list` und `SAK run show <run>`. Du empfiehlst dem Betreiber nie, den Kontext zu kompaktieren.
- Ereignisse und Berichte tragen nur Metadaten, nie Code, Diffs, Prompts oder Secrets.
- Bei Unklarheit nie raten: eskalieren.
