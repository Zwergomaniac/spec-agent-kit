# Anleitung: Deploy über GitHub Actions mit Freigabe

Ziel: Ein Repo deployt auf den VPS, ohne dass dein PC laufen muss und ohne dass ein Agent den SSH-Schlüssel sieht. Ein Agent (lokal oder in Claude Cloud) startet nur den Workflow. Du gibst den Lauf auf GitHub frei, auch per Mail oder Handy-App. Der Runner deployt.

Wiederhole die Schritte **je Repo**. Jedes Repo bekommt einen **eigenen** Schlüssel, damit du ihn einzeln sperren kannst.

> Kosten: Öffentliche Repos haben GitHub Actions kostenlos. Private Repos haben im Free-Plan ein monatliches Minutenkontingent (Stand Okt. 2026: 2.000 Linux-Minuten). Den aktuellen Stand siehst du unter *Settings → Billing*. Ein Deploy-Lauf braucht meist wenige Minuten.

Platzhalter in dieser Anleitung:

| Platzhalter | Beispiel |
|---|---|
| `<REPO>` | `ImmoAgent` (GitHub-Name) |
| `<NAME>` | `immoagent` (kurz, für Dateinamen) |
| `<VPS>` | `188.68.58.51` |
| `<USER>` | `root` |
| `<ADMIN_KEY>` | `~/.ssh/immoagent_vps_root` (dein bestehender Zugang) |

Alle Befehle laufen in **Git Bash**, nicht in der Windows-Konsole. Das Windows-OpenSSH unter `System32` ist zu alt für aktuelle Server.

## 1. Eigenen Deploy-Schlüssel erzeugen (PC)

```bash
ssh-keygen -t ed25519 -N "" -C "github-deploy-<NAME>" -f ~/.ssh/<NAME>_github_deploy
```

Es entstehen zwei Dateien:
- `~/.ssh/<NAME>_github_deploy` (privat): kommt NUR in das GitHub-Secret.
- `~/.ssh/<NAME>_github_deploy.pub` (öffentlich): kommt auf den VPS.

## 2. Öffentlichen Schlüssel auf dem VPS eintragen (vom PC aus)

```bash
ssh -i <ADMIN_KEY> <USER>@<VPS> 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys' < ~/.ssh/<NAME>_github_deploy.pub
```

So prüfst du, ob es geklappt hat (muss `ok` ausgeben):

```bash
ssh -i ~/.ssh/<NAME>_github_deploy -o IdentitiesOnly=yes <USER>@<VPS> 'echo ok'
```

## 3. Host-Schlüssel des VPS festhalten (PC)

```bash
ssh-keyscan -t ed25519 <VPS> 2>/dev/null | grep -v '^#'
```

Die Ausgabe ist eine Zeile der Form `<VPS> ssh-ed25519 AAAA…`. Vergleiche sie mit dem Eintrag, den deine bisherigen Verbindungen kennen (`ssh-keygen -F <VPS>`). Weichen sie ab, brichst du ab. Die Zeile ist für alle Repos auf demselben VPS gleich.

## 4. GitHub-Environment mit Freigabe anlegen (Browser)

Im Repo unter *Settings → Environments → New environment*, Name `production`:

1. **Required reviewers:** dich selbst eintragen. Das ist dein Freigabe-Knopf.
2. Optional bei *Deployment branches and tags*: nur `main` erlauben.
3. **Environment secrets** anlegen:

| Secret | Inhalt |
|---|---|
| `VPS_HOST` | `<VPS>` |
| `VPS_USER` | `<USER>` |
| `VPS_SSH_KEY` | kompletter Inhalt der **privaten** Datei `~/.ssh/<NAME>_github_deploy` (inklusive der Zeilen `-----BEGIN…`/`-----END…`) |
| `VPS_KNOWN_HOSTS` | die Zeile aus Schritt 3 |

Danach kannst du die private Datei auf dem PC behalten oder löschen. GitHub braucht sie nicht mehr von dir.

## 5. Workflow im Repo anlegen

Datei `.github/workflows/deploy.yml`. Den Schritt „Deploy“ passt du an das Deploy-Skript des Repos an:

```yaml
name: deploy
on:
  workflow_dispatch:
    inputs:
      spec:
        description: "Spec-Nummer(n) für den Marker, z. B. 084 oder 084,085"
        required: true
permissions:
  contents: write
concurrency:
  group: deploy-production
  cancel-in-progress: false
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: SSH vorbereiten
        run: |
          mkdir -p ~/.ssh && chmod 700 ~/.ssh
          printf '%s\n' "${{ secrets.VPS_SSH_KEY }}" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          printf '%s\n' "${{ secrets.VPS_KNOWN_HOSTS }}" > ~/.ssh/known_hosts
      - name: Deploy
        env:
          VPS_HOST: ${{ secrets.VPS_HOST }}
          VPS_USER: ${{ secrets.VPS_USER }}
        run: |
          # Beispiel für Repos mit deploy/deploy-vps.sh + deploy/vps.env (ImmoAgent-Stil):
          printf 'VPS_HOST=%s\nVPS_USER=%s\nVPS_PORT=22\nVPS_SSH_KEY=%s\n' \
            "$VPS_HOST" "$VPS_USER" "$HOME/.ssh/deploy_key" > deploy/vps.env
          bash deploy/deploy-vps.sh
      - name: Deploy-Marker setzen
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git commit --allow-empty -m "deploy(${{ inputs.spec }}): via GitHub Actions"
          git push origin HEAD:main
```

Regeln: Nie `set -x` in Schritten mit Secrets, keine Secrets in `echo`. GitHub maskiert Secrets in Logs, zusätzliche Vorsicht schadet aber nicht.

## 6. Agent anbinden (spec-agent-kit)

In `.spec-agent/config.yml` des Repos:

```yaml
deploy:
  methods:
    github:
      command: gh api -X POST repos/<OWNER>/<REPO>/actions/workflows/deploy.yml/dispatches -f ref=main -f "inputs[spec]={spec}"
      marker: workflow
    local:                      # optional: das bisherige Deploy per SSH bleibt möglich
      command: bash deploy/deploy.sh
      marker: agent
      local_only: true
  default: github
autonomy:
  push: after_merge
  deploy: after_approval
```

- „deployen“ nimmt den Default (`github`), „deployen lokal“ den Weg `local`. `deploy.command` allein (alte Form) gilt weiter als ein Weg `default` mit `marker: agent`.
- `{spec}` wird durch die Spec-Nummer ersetzt (bei mehreren `084,085`). Was passieren würde, zeigt `sak deploy plan [--method <name>] <spec>`; der Befehl führt nichts aus.
- `local_only: true` lehnt der Agent in einer Cloud-Sitzung ab (SSH vom Rechner des Betreibers fehlt dort). Die Erkennung nutzt die Proxy-Variablen; `SAK_ENVIRONMENT=cloud|local` übersteuert sie.

- Lokal braucht der Agent dafür das angemeldete `gh`. In Claude Cloud erledigt das der GitHub-Proxy der Sitzung. Benutze dort `gh api` (REST), weil GraphQL gesperrt ist.
- Der Agent startet den Workflow nur nach deinem „deployen“. Danach wartet der Lauf auf GitHub zusätzlich auf deine Freigabe.
- Den Marker `deploy(NNN)` setzt der Workflow, nicht der Agent (`marker: workflow`). Der Agent berichtet nur „angestoßen, wartet auf Freigabe auf GitHub“.

## 7. Erster Testlauf

1. Workflow manuell starten: *Actions → deploy → Run workflow*, `spec` z. B. `000`.
2. Freigabe erteilen (Benachrichtigung oder *Review deployments*).
3. Log prüfen: SSH ok, Deploy ok, Marker-Commit gepusht.

## Sperren und Erneuern

- **Repo-Schlüssel sperren:** Auf dem VPS die Zeile mit `github-deploy-<NAME>` aus `~/.ssh/authorized_keys` löschen und das GitHub-Secret entfernen.
- **Erneuern:** Schritte 1, 2 und 4 (nur das Secret `VPS_SSH_KEY`) wiederholen, dann den alten Schlüssel sperren.
- **Nie** einen SSH-Schlüssel als Umgebungsvariable in einer Claude-Cloud-Umgebung ablegen. Dort kann ihn jeder Agent lesen.

## Checkliste je Repo

- [ ] Eigener Schlüssel erzeugt (`<NAME>_github_deploy`)
- [ ] Öffentlicher Schlüssel auf dem VPS, Test `echo ok` erfolgreich
- [ ] Host-Schlüssel geprüft
- [ ] Environment `production` mit dir als Reviewer
- [ ] 4 Secrets angelegt
- [ ] `deploy.yml` committet und gepusht
- [ ] Testlauf mit Freigabe erfolgreich
- [ ] `deploy.command` in `.spec-agent/config.yml` (falls das Repo das Kit nutzt)
