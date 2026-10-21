"""Plugin ``legacy-status``: Blocker, Entscheidungen und zurückgestellte Specs (altes Board).

Formate des alten Boards (Skript ``.specify/scripts/python/feature_status.py``), nur gelesen:

- ``.specify/blockers.yml``: ``blockers: {<spec-dir>: {type, ref, detail, actionable}}``. Jeder
  Eintrag setzt ``blocked`` an der Spec. Einen ``blocker``-Aufmerksamkeitseintrag gibt es nur bei
  ``actionable: blocked`` oder ``partial`` (wie im alten Board).
- ``.specify/deferred-decisions.md``: Tabellen mit Zeilen ``| DQ-nn | Frage | Betrifft | ... |``
  unter den Überschriften „Offen“ und „Gelöst“. Offene Zeilen werden zu ``decision``-Einträgen.
- ``.specify/feature-status.yml``: ``feature_status_report.specs[]`` mit ``status: descoped``.

Optionen (alle optional, Pfade relativ zur Projektwurzel): ``blockers_file``, ``decisions_file``,
``status_file``. Eine fehlende oder unlesbare Datei ergibt einen Hinweis, nie einen Fehler.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import yaml

from spec_agent_kit.pipeline.events import clip
from spec_agent_kit.plugins import NOTE_MAX_CHARS, PluginContext, PluginResult

DEFAULT_BLOCKERS: Final[str] = ".specify/blockers.yml"
DEFAULT_DECISIONS: Final[str] = ".specify/deferred-decisions.md"
DEFAULT_STATUS: Final[str] = ".specify/feature-status.yml"
ACTIONABLE_ATTENTION: Final[frozenset[str]] = frozenset({"blocked", "partial"})
_REASON_MAX: Final[int] = 300

_DQ_ROW = re.compile(r"^\|\s*(DQ-\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|")
_DQ_RESOLVED = re.compile(r"✅\s*\*\*(beantwortet|gelöst|erledigt)\*\*")
_SPEC_REF = re.compile(r"Spec\s+(\d{3})")


def _note(result: PluginResult, text: str) -> None:
    result.notes.append(clip(f"legacy-status: {text}", NOTE_MAX_CHARS))


def _resolve(ctx: PluginContext, option: str, default: str, result: PluginResult) -> Path | None:
    """Pfad der Quelldatei; nur innerhalb des Projekts. ``None`` bei ungültiger Angabe."""
    relative = ctx.options.get(option, default)
    if not isinstance(relative, str) or not relative.strip():
        _note(result, f"Option '{option}' muss ein Pfad sein")
        return None
    root = ctx.root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        _note(result, f"Option '{option}' zeigt aus dem Projekt hinaus und wird ignoriert")
        return None
    return path


def _read(path: Path, label: str, result: PluginResult) -> str | None:
    if not path.is_file():
        _note(result, f"{label} fehlt")
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _note(result, f"{label} nicht lesbar ({type(exc).__name__})")
        return None


def _load_yaml(text: str, label: str, result: PluginResult) -> Any:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        _note(result, f"{label} ist kein gültiges YAML")
        return None


def read_blockers(text: str, spec_dirs: list[str], result: PluginResult) -> None:
    data = _load_yaml(text, "blockers.yml", result)
    entries = data.get("blockers") if isinstance(data, dict) else None
    if not isinstance(entries, dict):
        if data is not None:
            _note(result, "blockers.yml enthält keinen Abschnitt 'blockers'")
        return
    known = set(spec_dirs)
    for spec_dir, entry in entries.items():
        if not isinstance(entry, dict) or str(spec_dir) not in known:
            continue
        result.blocked.add(str(spec_dir))
        if str(entry.get("actionable", "unknown")) in ACTIONABLE_ATTENTION:
            detail = " ".join(str(entry.get("detail") or "").split())
            result.attention.append(
                {
                    "kind": "blocker",
                    "spec": str(spec_dir),
                    "reason": clip(detail or str(entry.get("type") or "Blocker"), _REASON_MAX),
                    "source": "blockers.yml",
                }
            )


def read_decisions(text: str, spec_dirs: list[str], result: PluginResult) -> None:
    resolved_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip().lower()
            if "offen" in heading or "deferred" in heading:
                resolved_section = False
            elif "gelöst" in heading or "resolved" in heading:
                resolved_section = True
            continue
        match = _DQ_ROW.match(line)
        if not match:
            continue
        dq_id, question_raw, affects, extra = (g.strip() for g in match.groups())
        if resolved_section or _DQ_RESOLVED.search(question_raw) or _DQ_RESOLVED.search(extra):
            continue
        question = question_raw.split("——")[0].split("—")[0].strip()
        question = re.sub(r"~~(.*?)~~", r"\1", question).strip()
        reason = f"{clip(question, 200)} ({dq_id})"
        entry = {
            "kind": "decision",
            "reason": clip(reason, _REASON_MAX),
            "source": "deferred-decisions.md",
        }
        number = _SPEC_REF.search(affects)
        if number:
            target = next(
                (d for d in sorted(spec_dirs) if d.startswith(f"{number.group(1)}-")), None
            )
            if target:
                entry["spec"] = target
        result.attention.append(entry)


def read_descoped(text: str, spec_dirs: list[str], result: PluginResult) -> None:
    data = _load_yaml(text, "feature-status.yml", result)
    report = data.get("feature_status_report") if isinstance(data, dict) else None
    specs = report.get("specs") if isinstance(report, dict) else None
    if not isinstance(specs, list):
        if data is not None:
            _note(result, "feature-status.yml enthält keine Liste feature_status_report.specs")
        return
    known = set(spec_dirs)
    for item in specs:
        if (
            isinstance(item, dict)
            and item.get("status") == "descoped"
            and str(item.get("spec_dir")) in known
        ):
            result.descoped.add(str(item["spec_dir"]))


def run(ctx: PluginContext) -> PluginResult:
    result = PluginResult()
    sources = (
        ("blockers_file", DEFAULT_BLOCKERS, "blockers.yml", read_blockers),
        ("decisions_file", DEFAULT_DECISIONS, "deferred-decisions.md", read_decisions),
        ("status_file", DEFAULT_STATUS, "feature-status.yml", read_descoped),
    )
    for option, default, label, reader in sources:
        path = _resolve(ctx, option, default, result)
        if path is None:
            continue
        text = _read(path, label, result)
        if text is not None:
            reader(text, ctx.spec_dirs, result)
    return result
