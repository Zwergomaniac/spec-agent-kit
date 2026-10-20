"""Das Board-Dokument ``sak.board/1`` (Spec 006 FR-005 bis FR-007).

``build_board`` stürzt bei unlesbaren Eingaben nie ab: jede Quelle wird einzeln abgesichert, Fehler
werden zu Einträgen in ``notes``. Das fertige Dokument wird vor der Rückgabe gegen das Schema
geprüft (FR-007). Einzelne ungültige Listeneinträge (z. B. ein Lauf mit unbekanntem Zustand aus
einem anderen Kit-Stand) werden verworfen und als Hinweis gemeldet; ist das Dokument sonst ungültig,
folgt ``BoardError`` mit Pfad. Das wäre ein Bug.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, TypeVar

from spec_agent_kit import __version__, contracts
from spec_agent_kit.board import BoardError
from spec_agent_kit.board.git_history import GitHistory
from spec_agent_kit.board.runs_view import (
    RUNS_MAX,
    EventLog,
    attention_for_runs,
    collect_runs,
    read_event_log,
)
from spec_agent_kit.board.specs import DONE_STAGES, SpecInfo, scan_specs
from spec_agent_kit.config import EffectiveConfig
from spec_agent_kit.pipeline import runs as run_store
from spec_agent_kit.pipeline.events import clip
from spec_agent_kit.push import outbox

NOTES_MAX: Final[int] = contracts.LIMITS["NOTES_MAX"]
TICKER_MAX: Final[int] = contracts.LIMITS["TICKER_MAX"]
MARKERS_MAX: Final[int] = 100
_NOTE_MAX_CHARS: Final[int] = 300
_LIST_SECTIONS: Final[tuple[str, ...]] = ("specs", "attention", "runs", "markers", "ticker")
_KIND_ORDER: Final[tuple[str, ...]] = (
    "escalation",
    "stale_run",
    "approval",
    "clarification",
    "operator_task",
    "blocker",
    "decision",
)

T = TypeVar("T")


def _guard(label: str, notes: list[str], default: T, fn: Callable[[], T]) -> T:
    """Führt ``fn`` aus. Jede Ausnahme wird zu einem Hinweis, der Rest des Boards bleibt."""
    try:
        return fn()
    except Exception as exc:  # das Board stürzt nie ab (Spec 006 US1)
        notes.append(clip(f"{label} nicht auswertbar ({type(exc).__name__}: {exc})", 280))
        return default


def _attention_sort_key(item: dict[str, str], recency: dict[str, int]) -> tuple[int, int, str]:
    kind = _KIND_ORDER.index(item["kind"]) if item["kind"] in _KIND_ORDER else len(_KIND_ORDER)
    return (kind, recency.get(item.get("spec", ""), len(recency)), item["reason"])


def _ticker(
    history: GitHistory, numbers: dict[int, str], share_text: bool, snapshot: bool
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in history.ticker[:TICKER_MAX]:
        item: dict[str, Any] = {"ts": entry["ts"], "kind": entry["kind"]}
        number = entry.get("number")
        if isinstance(number, int) and number in numbers:
            item["spec"] = numbers[number]
        text = str(entry.get("text") or "").strip()
        if share_text and not snapshot and text:
            item["text"] = clip(text, 200)
        items.append(item)
    return items


def _markers(history: GitHistory) -> list[dict[str, Any]]:
    return [
        {"kind": m.kind, "specs": list(m.specs), "ts": m.ts, "commit": m.commit}
        for m in history.marker_commits[:MARKERS_MAX]
    ]


def _git_note(history: GitHistory, root: Path) -> str:
    reason = f" ({history.error})" if history.error else ""
    advice = ""
    if "dubious ownership" in history.error:
        advice = f' - Abhilfe: git config --global --add safe.directory "{root.as_posix()}"'
    return clip(
        f"Git nicht verfügbar{reason}: keine Durchlaufzeit, keine Marker, kein Ticker{advice}", 295
    )


def _push_notes(root: Path) -> list[str]:
    notes: list[str] = []
    cursor = outbox.read_cursor(root)
    if cursor.skipped:
        notes.append(
            f"{cursor.skipped} defekte Zeile(n) in events.jsonl übersprungen (nicht gesendet)"
        )
    rejected = outbox.count_rejected(root)
    if rejected:
        notes.append(f"{rejected} Event(s) vom Dashboard abgelehnt (siehe push-rejected.jsonl)")
    if cursor.last_error:
        notes.append(clip(f"Letzter Push fehlgeschlagen: {cursor.last_error}", 295))
    return notes


def _repair(doc: dict[str, Any]) -> None:
    """Verwirft einzelne ungültige Listeneinträge; alles andere wäre ein Bug (``BoardError``)."""
    notes: list[str] = doc["notes"]
    for _ in range(200):
        problems = contracts.validate_board(doc)
        if not problems:
            return
        path, _, detail = problems[0].partition(": ")
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] in _LIST_SECTIONS and parts[1].isdigit():
            items: list[Any] = doc[parts[0]]
            index = int(parts[1])
            if index < len(items):
                del items[index]
                if len(notes) < NOTES_MAX:
                    notes.append(clip(f"{parts[0]}[{index}] verworfen, ungültig: {path}", 295))
                continue
        raise BoardError(path, detail)
    raise BoardError("<root>", "zu viele ungültige Einträge")  # pragma: no cover


def _metrics(specs: list[SpecInfo], attention: list[dict[str, str]]) -> dict[str, Any]:
    leads = [s.lead_time_days for s in specs if s.lead_time_days is not None]
    return {
        "in_progress": sum(1 for s in specs if s.stage == "implementing"),
        "done": sum(1 for s in specs if s.stage in DONE_STAGES),
        "blocked": 0,
        "waiting": len(attention),
        "mean_lead_time_days": round(sum(leads) / len(leads), 1) if leads else None,
    }


def build_board(
    root: Path,
    cfg: EffectiveConfig,
    source: str = "live",
    *,
    share_text: bool | None = None,
) -> dict[str, Any]:
    """Das Board-Dokument aus Spec-Dateien, Git, Läufen und Events.

    ``share_text``: Commit-Betreffe im Ticker. ``None`` übernimmt
    ``dashboard.share_commit_subjects`` (Standard für den Push); die lokale Ansicht übergibt
    ``True``. ``source="snapshot"`` lässt Läufe,
    Eskalationen und Commit-Texte weg (ADR E2).
    """
    notes: list[str] = []
    snapshot = source == "snapshot"
    if share_text is None:
        share_text = bool(cfg.data["dashboard"]["share_commit_subjects"])
    now = run_store.utcnow()
    stages = {k: bool(v) for k, v in cfg.data["stages"].items()}

    history = _guard("Git-Verlauf", notes, GitHistory(), lambda: GitHistory.read(root))
    if not history.available:
        notes.append(_git_note(history, root))
    log = _guard("events.jsonl", notes, EventLog(), lambda: read_event_log(root))
    if log.skipped:
        notes.append(f"{log.skipped} unlesbare Zeile(n) in events.jsonl übersprungen")

    all_runs = _guard("Läufe", notes, [], lambda: collect_runs(root, cfg, log, now, notes))
    started_specs = {r["spec"] for r in all_runs}
    specs = _guard(
        "Specs", notes, [], lambda: scan_specs(root, history, stages, started_specs, notes)
    )

    runs = [] if snapshot else all_runs[:RUNS_MAX]
    stale_hours = int(cfg.data["pipeline"]["stale_hours"])
    attention: list[dict[str, str]] = [a for s in specs for a in s.attention]
    if not snapshot:
        attention += attention_for_runs(all_runs, stale_hours)
    recency = {s.dir: i for i, s in enumerate(specs)}
    attention.sort(key=lambda a: _attention_sort_key(a, recency))

    numbers = {s.number: s.dir for s in specs}
    ticker = _guard("Ticker", notes, [], lambda: _ticker(history, numbers, share_text, snapshot))
    markers = _guard("Marker", notes, [], lambda: _markers(history))
    notes.extend(_guard("Push-Status", notes, [], lambda: _push_notes(root)))

    project = cfg.data["project"]
    doc: dict[str, Any] = {
        "schema": "sak.board/1",
        "generated_at": run_store.format_ts(now),
        "source": source,
        "kit_version": __version__,
        "project": {
            "key": project["key"],
            "name": project.get("name") or project["key"],
            "base_branch": project.get("base_branch") or "main",
        },
        "metrics": _metrics(specs, attention),
        "specs": [s.to_board() for s in specs],
        "attention": attention,
        "runs": runs,
        "markers": markers,
        "ticker": ticker,
        "notes": [],
    }
    seen: set[str] = set()
    for note in notes:
        text = clip(note, _NOTE_MAX_CHARS)
        if text and text not in seen:
            seen.add(text)
            doc["notes"].append(text)
    if len(doc["notes"]) > NOTES_MAX:
        extra = len(doc["notes"]) - (NOTES_MAX - 1)
        del doc["notes"][NOTES_MAX - 1 :]
        doc["notes"].append(f"{extra} weitere Hinweise unterdrückt")
    _repair(doc)
    # Nach dem Verwerfen ungültiger Einträge stimmen die Kennzahlen noch.
    kept = {s["dir"] for s in doc["specs"]}
    final_specs = [s for s in specs if s.dir in kept]
    doc["metrics"] = _metrics(final_specs, doc["attention"])
    problems = contracts.validate_board(doc)
    if problems:
        path, _, detail = problems[0].partition(": ")
        raise BoardError(path, detail)
    return doc


def board_json(doc: dict[str, Any], *, indent: int | None = 2) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=indent)
