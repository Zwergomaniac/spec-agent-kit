---
name: "sak-init"
description: "Führt durch die Einrichtung des Spec Agent Kit in einem Zielprojekt: Fragen stellen, Plan zeigen, nach Bestätigung anwenden, doctor ausführen, nächste Schritte erklären."
argument-hint: "Optional: Zielpfad"
compatibility: "Nur im Kit-Repo (spec-agent-kit) benutzbar; braucht uv und das Zielprojekt als Git-Repo mit spec-kit."
user-invocable: true
disable-model-invocation: true
---

# sak-init: Kit in ein Projekt einrichten

Dieser Skill ist nur die Bedienoberfläche. **Die gesamte Logik steckt im CLI** (`sak init`, `sak doctor`).
Du schreibst selbst keine Dateien ins Zielprojekt, du bearbeitest keine Settings und keine Config von
Hand, und du committest nie.

Abkürzung: `SAK` = `uv run --project packages/engine sak`, aufgerufen aus dem Wurzelverzeichnis des
Kit-Repos.

## Grundsätze

- Plan vor Apply: erst ohne `--apply` aufrufen, den Plan zeigen, dann auf eine ausdrückliche Bestätigung
  des Betreibers warten.
- Nichts wird überschrieben. Konflikte erscheinen als `<datei>.sak-new`. Erkläre das, wenn der Plan
  Konflikte nennt.
- Das Ziel muss ein sauberes Git-Repo mit spec-kit sein. Fehlt spec-kit, nennt das CLI den genauen
  `specify init`-Befehl; gib ihn dem Betreiber, führe ihn nicht ungefragt aus.
- Den Dashboard-Schlüssel fragst du nicht ab und liest ihn nie. Er gehört nicht in den Chat und nicht in die Config.
- Läuft die Einrichtung gegen ein echtes Projekt des Betreibers, bestätigt er den Zielpfad vorher ausdrücklich.

## Ablauf

### 1. Fragen (5 bis 8, in einer Runde)

Frage nur, was fehlt. Ein übergebener Zielpfad zählt als beantwortet.

1. Zielpfad des Projekts (Git-Wurzel).
2. Projektschlüssel (2 bis 40 Zeichen: a-z, 0-9, Bindestrich; beginnt mit einem Buchstaben).
3. Anzeigename (1 bis 80 Zeichen).
4. Basis-Branch (Vorschlag: `main`).
5. Hat das Projekt eine Web-UI? Ja: UI-Prüfung aktiv (Platzhalter in `ui.command` und `ui.base_url` werden gesetzt und müssen
   danach angepasst werden). Nein: `--no-ui`.
6. Testbefehle: schnell (`--test-fast`, `{paths}` ist optional), vollständig (`--test-full`), Lint (`--lint`). Mehrfach angebbar.
7. Dashboard-URL (`https://…`, `http://` nur für localhost) oder keine.

### 2. Plan zeigen

```text
SAK init <ziel> --key <schlüssel> --name "<name>" --base-branch <branch> [--no-ui] [--test-fast "<befehl>"] [--test-full "<befehl>"] [--lint "<befehl>"] [--dashboard-url <url>]
```

Zeige die Kurzfassung (Anzahl neu, gemergt, Konflikte), alle Konflikte und jede Warnung im Wortlaut.
Weise besonders hin auf:

- eine Warnung zum `defaultMode` des Ziels (bleibt unverändert; Risiko liegt beim Zielprojekt),
- Konflikte mit eigenen Dateien (`.sak-new`),
- Platzhalter der UI-Prüfung.

Bei einer Ablehnung (Exit 1) nennst du den Grund und fragst nach der Korrektur. Es wurde nichts geschrieben.

### 3. Anwenden

Nur nach ausdrücklicher Bestätigung denselben Aufruf mit `--apply` wiederholen. Das CLI führt danach `uv sync` im
Engine-Ordner und `config check` aus. Ein unsauberer Arbeitsstand wird abgelehnt; `--allow-dirty` bietest du nur an, wenn
der Betreiber es verlangt und keine geplante Aktion eine geänderte Datei berührt.

### 4. Prüfen

```text
SAK doctor <ziel>
```

Gib die Liste der Prüfungen wieder. Bei einer fehlgeschlagenen Pflichtprüfung erklärst du den Befund
und den Weg zur Behebung (zum Beispiel `uv sync --project .spec-agent/engine` im Zielprojekt).

### 5. Nächste Schritte erklären

1. Ergebnis im Ziel durchsehen (`git status`, `git diff`; `settings.json` ist die einzige geänderte Bestandsdatei).
2. Konflikte klären: je `.sak-new` die Kit-Fassung mit der eigenen vergleichen, übernehmen oder verwerfen.
3. Committen. Nenne den Vorschlag `suggested_commit` aus dem Bericht; **der Betreiber führt ihn aus**, du nicht.
4. `.spec-agent/config.yml` durchsehen (Rollen, Befehle, geschützte Pfade, Prüfthemen) und danach `sak config check`.
5. Im Dashboard ein Projekt mit demselben Schlüssel anlegen. Den dort ausgestellten Dashboard-Schlüssel legt der Betreiber selbst ab:
   in der Umgebungsvariable `SAK_DASHBOARD_TOKEN` oder in der gitignorierten Datei `.spec-agent/dashboard.key`.
6. Später: `SAK upgrade <ziel>` (erst Plan, dann `--apply`) bringt das Kit auf eine neue Version, ohne lokale Änderungen
   zu überschreiben.

## Abgrenzung

Pipeline-Läufe (`sak run …`) gehören dem Skill `sak-pipeline` im Zielprojekt, nicht diesem Skill.
