# Feature Specification: Betrieb in Claude Cloud

**Feature Branch**: `013-claude-cloud`

**Created**: 2026-10-22

**Status**: Implemented (Kit 0.4.0; SC-003 Abnahme durch Betreiber offen)

**Input**: Erster Lauf von ImmoAgent in einer Claude-Code-Cloud-Sitzung am 2026-10-21. Der Builder lief, aber specboard zeigte nichts. Befunde:
- `doctor` meldete `dashboard: … Tunnel connection failed: 403 Forbidden`. Das ist der ausgehende Proxy der Cloud-Umgebung (Netzzugriff „Trusted“), nicht specboard.
- Die gitignorierte `.spec-agent/dashboard.key` fehlt im Cloud-Klon. Deshalb lehnt `sak push` ab.
- uv und die Hooks funktionieren in der Cloud (`hook_probe` ok).

Recherche (Doku „Configure cloud environments“, code.claude.com/docs/en/cloud-environments):
- Umgebungsvariablen sind für jeden Nutzer der Umgebung und für den Agenten lesbar.
- Ein **Network Secret** wird vom Proxy außerhalb der VM als `Authorization: Bearer …` an Anfragen zu gelisteten Hosts gehängt und ist in der VM nicht sichtbar.
- Hosts mit Network Secret umgehen die Allowlist.
- Cloud-Sitzungen dürfen Branches pushen (keine Tags, kein Branch-Löschen).

## Clarifications

### Session 2026-10-22

- Q: Wie kommt der Projekt-Schlüssel in Cloud-Läufe? → A: Bevorzugt über ein Network Secret für `specboard`-Host (Bearer). Das Kit unterstützt dazu einen Modus ohne lokalen Schlüssel. Die Umgebungsvariable `SAK_DASHBOARD_TOKEN` bleibt als einfache Alternative für persönliche Umgebungen.
- Q: Wie wird der Modus gewählt? → A: Per Config `dashboard.auth: key | proxy` (Default `key`). Zusätzlich gilt eine Laufzeit-Übersteuerung über die Umgebungsvariable `SAK_DASHBOARD_AUTH=proxy`, damit lokale Läufe (mit Schlüsseldatei) und Cloud-Läufe (Network Secret) dieselbe eingecheckte Config nutzen können.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Push in der Cloud ohne Schlüssel in der VM (Priority: P1)

**Acceptance Scenarios**:
1. **Given** `SAK_DASHBOARD_AUTH=proxy` (oder `dashboard.auth: proxy`) und kein lokaler Schlüssel, **When** `sak push` läuft, **Then** sendet das Kit die Anfrage ohne eigenen `Authorization`-Header. Antwortet das Dashboard mit 401, lautet die Meldung: „Kein Network Secret für <host> in der Cloud-Umgebung hinterlegt (Typ Bearer)“.
2. **Given** Modus `key` ohne Schlüssel, **When** gepusht wird, **Then** gilt das bisherige Verhalten (Ablehnung mit Hinweis). Neu ist der Zusatz-Hinweis auf den Proxy-Modus, falls eine Cloud-Sitzung erkannt wurde.
3. **Given** ein Proxy-Modus mit zusätzlich vorhandenem lokalem Schlüssel, **When** gepusht wird, **Then** wird der lokale Schlüssel NICHT gesendet (eindeutiges Verhalten) und eine Warnung ausgegeben.

### User Story 2 – Verständliche Diagnose (Priority: P1)

`sak doctor` und `sak dashboard status` erkennen typische Cloud-Fehler und erklären sie:
- „Tunnel connection failed: 403“ bzw. Proxy-Ablehnung → „Netzzugriff der Cloud-Umgebung erlaubt <host> nicht: Network access auf Custom stellen und <host> eintragen, oder ein Network Secret für <host> anlegen (umgeht die Allowlist).“
- Gesetzte Proxy-Variablen (`HTTPS_PROXY`, `https_proxy`) werden als Kontext angezeigt (nur ob gesetzt, nie Werte mit Zugangsdaten).
- `dashboard` gilt im Proxy-Modus als ok, wenn `/healthz` erreichbar ist (kein Schlüssel nötig).
- **TLS:** Scheitert die Verbindung an einem Zertifikatsfehler hinter dem Proxy, nennt die Meldung `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`. Die Engine nutzt eine CA-Bundle-Umgebungsvariable, falls gesetzt (siehe FR-004).

### User Story 3 – Anleitung „Kit in Claude Cloud“ (Priority: P2)

README-Abschnitt (und `docs/cloud.md`):
1. Netzzugriff einstellen (Custom + Host, oder Network Secret).
2. Network Secret anlegen (Host `specboard.prozessfit.de`, Typ Bearer, Wert = Projekt-Schlüssel), in der Umgebung `SAK_DASHBOARD_AUTH=proxy` setzen.
3. Alternative Umgebungsvariable `SAK_DASHBOARD_TOKEN` mit Hinweis auf die Sichtbarkeit (Agent und Umgebungsnutzer).
4. Push-Rechte auf GitHub für `autonomy.push: after_merge` und Empfehlung Branch-Protection bzw. Rulesets.
5. Dass Hooks und Board in der Cloud im Container laufen (lokale Monitore sehen nichts) und dass das Ergebnis erst nach Push auf GitHub liegt.

## Requirements *(mandatory)*

- **FR-001**: Contract-Erweiterung `sak.config/1`: optional `dashboard.auth: key | proxy` (Default `key`).
- **FR-002**: Laufzeit-Übersteuerung `SAK_DASHBOARD_AUTH` (`key`|`proxy`) hat Vorrang vor der Config. Ungültige Werte führen zu Fehler mit Hinweis.
- **FR-003**: Push-Client: Im Proxy-Modus wird kein Authorization-Header gesendet. Die bestehenden Schutzregeln (keine Weiterleitungen, https-Pflicht außer Loopback) bleiben.
- **FR-004**: TLS hinter Proxy: Ist `SSL_CERT_FILE` oder `REQUESTS_CA_BUNDLE` gesetzt, nutzt der HTTP-Client dieses Bundle zusätzlich zum System-Store. Ohne Variable bleibt das bisherige Verhalten.
- **FR-005**: `doctor`, `dashboard status`, `dashboard connect` kennen den Proxy-Modus.
  - `connect --auth proxy` schreibt nur URL und Modus, keinen Schlüssel.
  - `status` zeigt `auth: proxy|key`.
  - Die Diagnosen aus US2 werden in `status.problems` bzw. im `doctor`-Detail ausgegeben.
- **FR-006**: Cloud-Erkennung ist eine Heuristik ohne undokumentierte Annahmen: Proxy-Variablen gesetzt UND Fehlerbild „Tunnel connection failed“ / HTTP 403 vom Proxy. Die Erkennung ändert kein Verhalten, nur Meldungen.
- **FR-007**: Doku nach US3. Kit-Version 0.4.0.

## Success Criteria *(mandatory)*

- **SC-001**: Tests mit lokalem Test-Server: Im Proxy-Modus fehlt der Authorization-Header nachweislich, die 401-Meldung nennt das Network Secret, und ein vorhandener lokaler Schlüssel wird nicht gesendet.
- **SC-002**: Simulierter Proxy-Fehler (Test-Proxy, der CONNECT mit 403 beantwortet) ergibt die Diagnose aus US2.
- **SC-003**: Nach Einrichtung durch den Betreiber zeigt ein Cloud-Lauf von ImmoAgent seine Events auf specboard. Das ist die manuelle Abnahme durch den Betreiber.
