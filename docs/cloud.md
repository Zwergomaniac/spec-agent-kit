# Kit in Claude Cloud betreiben

Stand: Kit 0.4.0, Spec 013. Dieses Dokument beschreibt, wie ein Projekt mit dem Spec Agent Kit in einer Claude-Code-Cloud-Sitzung läuft und trotzdem Events ans Dashboard (specboard) liefert. Grundlage ist die Anthropic-Doku „Configure cloud environments“ (code.claude.com/docs/en/cloud-environments).

## Was in der Cloud anders ist

- Die Sitzung läuft in einer VM mit einem frischen Klon des Repos. Gitignorierte Dateien fehlen, also auch `.spec-agent/dashboard.key`.
- Ausgehende Verbindungen gehen über einen Proxy der Umgebung (Variablen `HTTPS_PROXY`/`https_proxy`). Bei „Network access: Trusted“ lässt er nur gelistete Hosts durch. Ein anderer Host scheitert mit `Tunnel connection failed: 403 Forbidden`. Das ist der Proxy, nicht das Dashboard.
- Umgebungsvariablen der Umgebung sind für jeden Nutzer der Umgebung und für den Agenten lesbar.
- Ein **Network Secret** wird vom Proxy außerhalb der VM als `Authorization: Bearer …` an Anfragen zu gelisteten Hosts gehängt und ist in der VM nicht sichtbar. Hosts mit Network Secret umgehen die Allowlist.
- Hooks, Pipeline und Board laufen im Container. Lokale Monitore (`board serve` auf dem eigenen Rechner) sehen nichts davon.

## Einrichtung (empfohlen: Network Secret)

1. **Network Secret anlegen.** Host `specboard.prozessfit.de`, Typ Bearer, Wert = Projekt-Schlüssel (`sak_…`). Damit ist auch der Netzzugriff zu diesem Host freigegeben. Alternativ „Network access“ auf Custom stellen und den Host eintragen; ohne Secret braucht es dann trotzdem einen Schlüssel (siehe unten).
2. **Modus setzen.** In der Umgebung die Variable `SAK_DASHBOARD_AUTH=proxy` anlegen. Sie übersteuert die Config, sodass lokale Läufe (mit Schlüsseldatei) und Cloud-Läufe (mit Network Secret) dieselbe eingecheckte `.spec-agent/config.yml` nutzen.
3. **Oder fest in der Config:** `sak dashboard connect --url https://specboard.prozessfit.de --auth proxy --yes` trägt URL und `dashboard.auth: proxy` ein und legt keinen Schlüssel an. Das gilt dann für alle Läufe dieses Projekts, auch lokale (dort fehlt der Bearer, solange kein Proxy ihn ergänzt). Mit der Umgebungsvariable `SAK_DASHBOARD_AUTH=key` lässt sich das lokal übersteuern.

Im Proxy-Modus sendet das Kit **nie** einen eigenen `Authorization`-Header, auch nicht, wenn ein lokaler Schlüssel existiert (`SAK_DASHBOARD_TOKEN` oder `.spec-agent/dashboard.key`). In dem Fall erscheint nur eine Warnung. Antwortet das Dashboard mit 401, lautet die Meldung: „Kein Network Secret für <host> in der Cloud-Umgebung hinterlegt (Typ Bearer)“. Die Schutzregeln bleiben: keine Weiterleitungen, HTTPS Pflicht (HTTP nur für localhost und 127.0.0.1).

Prüfen:

```sh
sak dashboard status   # zeigt auth: proxy|key, ob Proxy-Variablen gesetzt sind (nie ihre Werte), letzten Push-Fehler
sak doctor             # Check "dashboard": im Proxy-Modus genügt ein erreichbares /healthz
```

## Alternative: Umgebungsvariable mit dem Schlüssel

Für persönliche Umgebungen genügt `SAK_DASHBOARD_TOKEN=<Projekt-Schlüssel>` im Modus `key` (Default). **Achtung:** Umgebungsvariablen sind für den Agenten und für alle Nutzer der Umgebung lesbar. Ein Schlüssel dort ist so sichtbar wie jedes andere Geheimnis in der VM. Für geteilte Umgebungen ist das Network Secret die bessere Wahl. Der Schlüssel erlaubt nur das Senden von Metadaten für genau ein Projekt.

## TLS hinter dem Proxy

Terminiert der Proxy TLS mit einer eigenen CA, braucht der HTTP-Client deren Bundle. Ist `SSL_CERT_FILE` oder `REQUESTS_CA_BUNDLE` gesetzt und zeigt auf eine Datei, nutzt das Kit dieses Bundle zusätzlich zum System-Store. Ohne die Variablen bleibt das Verhalten unverändert. Scheitert die Verbindung an einem Zertifikatsfehler, nennt die Meldung beide Variablen.

## Diagnose

| Meldung | Bedeutung | Abhilfe |
| --- | --- | --- |
| „Netzzugriff der Cloud-Umgebung erlaubt <host> nicht …“ | Der Proxy lehnt den Tunnel mit 403 ab (`Tunnel connection failed`) und Proxy-Variablen sind gesetzt. | Network access auf Custom stellen und den Host eintragen, oder ein Network Secret für den Host anlegen (umgeht die Allowlist). |
| „Kein Network Secret für <host> … hinterlegt (Typ Bearer)“ | Modus `proxy`, das Dashboard antwortet 401. | Secret mit Typ Bearer und dem Projekt-Schlüssel für genau diesen Host anlegen. |
| „TLS-Zertifikat von <host> nicht vertrauenswürdig …“ | Zertifikatsfehler hinter dem Proxy. | `SSL_CERT_FILE` oder `REQUESTS_CA_BUNDLE` auf das CA-Bundle der Umgebung setzen. |
| „Schlüssel fehlt …“ plus Hinweis auf `SAK_DASHBOARD_AUTH=proxy` | Modus `key`, kein Schlüssel im Cloud-Klon, Proxy-Variablen gesetzt. | Proxy-Modus mit Network Secret einrichten oder `SAK_DASHBOARD_TOKEN` setzen. |

Die Cloud-Erkennung ist eine Heuristik (gesetzte Proxy-Variablen und das Fehlerbild des Proxys). Sie ändert nie das Verhalten, nur die Meldungen. Von den Proxy-Variablen wird nur angezeigt, ob sie gesetzt sind; Werte können Zugangsdaten enthalten und erscheinen nirgends.

## Push-Rechte auf GitHub

Cloud-Sitzungen dürfen Branches pushen, aber keine Tags setzen und keine Branches löschen. Für `autonomy.push: after_merge` (`sak run push` schiebt den Basis-Branch) muss die Sitzung also auf den Basis-Branch pushen dürfen. Empfehlung: Branch-Protection bzw. Rulesets für den Basis-Branch so einstellen, dass genau das gewollt ist (z. B. keine Force-Pushes, Pflicht-Checks), und `autonomy.push` nur dort auf `after_merge` stellen, wo das tragbar ist. Der Standard `manual` bleibt der sichere Weg: Der Betreiber pusht selbst.

## Wo liegt das Ergebnis?

Alles, was die Pipeline in der Cloud erzeugt (Merges, Marker-Commits, Events in `.spec-agent/state/`), liegt zunächst nur in der VM. Auf GitHub erscheint es erst nach einem Push. Specboard erhält Events und Board unabhängig davon über `sak push`, solange der Netzzugriff steht.

## Abnahme (manuell)

Nach der Einrichtung zeigt ein Cloud-Lauf seine Events auf specboard (Spec 013, SC-003). Das prüft der Betreiber.
