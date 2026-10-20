# AGENTS.md

Der Blueprint besteht aus den Vorlagen unter `templates/`. Sie werden nur über `sak init` und
`sak upgrade` (Spec 005) in Zielprojekte installiert. Ein anderer Weg (Kopierskripte, Handarbeit)
ist nicht vorgesehen.

## Struktur der Templates

| Quelle | Ziel im Zielprojekt | Behandlung |
|---|---|---|
| `templates/claude/agents/*` | `.claude/agents/` | verwaltet (Lock-Hash) |
| `templates/claude/skills/*` | `.claude/skills/` | verwaltet (Lock-Hash) |
| `templates/claude/settings.fragment.json` | `.claude/settings.json` | additiver Merge, nie ersetzt |
| `templates/config/config.yml` | `.spec-agent/config.yml` | einmaliger Seed, danach nie angefasst |
| `templates/config/examples/*` | nirgends | Beispiele für Betreiber, nicht installiert |
| `templates/spec-agent/gitignore` | `.spec-agent/.gitignore` | verwaltet |
| `packages/engine/**` (ohne `tests/`, `.venv/`, Caches) | `.spec-agent/engine/` | verwaltet, vendort |

Welche Dateien verwaltet sind, bestimmt allein `spec_agent_kit.install.kit.Kit.managed_files()`.
Eine neue Datei unter `templates/claude/` oder im Engine-Ordner wird automatisch Teil von Init und
Upgrade und steht danach im Lockfile.

## Regeln

- Plan vor Apply. Kein Kit-Befehl überschreibt eine fremde oder lokal geänderte Datei: bei Konflikten
  entsteht `<datei>.sak-new` daneben (Constitution III).
- `config.yml` wird nie verwaltet. Neue Schlüssel meldet `sak upgrade`, er trägt sie nicht ein.
- Der Settings-Merge ist additiv. Das Fragment enthält nie `defaultMode` und nie den Modus, der
  Rückfragen abschaltet (Constitution IV). Deny-Regeln des Fragments und `REQUIRED_DENY` in
  `install/doctor.py` müssen deckungsgleich bleiben (Test).
- Vorlagen sind projektneutral: keine Projektnamen, Pfade oder Befehle. Alles Projektspezifische
  gehört in `config.yml` (Spec 004). Ein Grep-Test erzwingt das für `templates/claude/` und die
  Config-Vorlage.
- Ändert sich eine Vorlage, ändert sich die Kit-Version in `packages/engine/src/spec_agent_kit/__init__.py`
  (Quelle der Lock-Version). Ohne neue Version erkennt `sak upgrade` Änderungen trotzdem über die Hashes.
- Der Init-Skill für das Kit-Repo selbst liegt unter `.claude/skills/sak-init/` im Repo-Wurzelverzeichnis
  und ist keine Vorlage für Zielprojekte.
- Platzhalter in `config.yml` heißen `__PROJECT_KEY__`, `__PROJECT_NAME__` und `__BASE_BRANCH__`. Neue
  Platzhalter brauchen eine Ersetzung in `install/plan.py` (`render_config`) und einen Test.
