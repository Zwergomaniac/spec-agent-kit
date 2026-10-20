"""Events in der v1-Hülle (Spec 002) nach ``.spec-agent/state/events.jsonl``.

Ein Event entsteht nur, wenn ``contracts.validate_event`` es akzeptiert (Constitution I). Ungültige
Events werden nicht geschrieben; ``EventError`` trägt den Grund. Geschrieben wird nur angehängt,
zeilenweise und mit ``flush``.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from spec_agent_kit import contracts
from spec_agent_kit.pipeline import runs

EVENTS_FILE: Final[str] = "events.jsonl"
REASON_MAX: Final[int] = contracts.LIMITS["REASON_MAX_CHARS"]
NAME_MAX: Final[int] = contracts.LIMITS["ORIGIN_FIELD_MAX_CHARS"]


class EventError(Exception):
    """Das Event verletzt den Vertrag und wurde nicht geschrieben."""


def clip(text: str, limit: int = REASON_MAX) -> str:
    """Kürzt Freitext auf ``limit`` Zeichen (mit Auslassungszeichen), Zeilenumbrüche entfallen."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def events_path(root: Path) -> Path:
    return runs.state_dir(root) / EVENTS_FILE


def build(
    etype: str,
    *,
    project: str,
    run: dict[str, Any] | None = None,
    spec: str | None = None,
    **data: Any,
) -> dict[str, Any]:
    """Baut die Event-Hülle. ``None``-Werte in ``data`` entfallen."""
    event: dict[str, Any] = {
        "schema": "sak.event/1",
        "event_id": contracts.new_ulid(),
        "type": etype,
        "ts": runs.format_ts(runs.utcnow()),
        "project": project,
    }
    if run is not None:
        event["run_id"] = run["run_id"]
        event["spec"] = run["spec"]
        origin = run.get("origin") or {}
        if origin.get("branch"):
            event["origin"] = {"branch": str(origin["branch"])[:NAME_MAX]}
    elif spec is not None:
        event["spec"] = spec
    event["data"] = {k: v for k, v in data.items() if v is not None}
    return event


def emit(
    root: Path,
    etype: str,
    *,
    project: str,
    run: dict[str, Any] | None = None,
    spec: str | None = None,
    **data: Any,
) -> dict[str, Any]:
    """Validiert und hängt ein Event an. Wirft ``EventError``, ohne etwas zu schreiben."""
    event = build(etype, project=project, run=run, spec=spec, **data)
    problems = contracts.validate_event(event)
    if problems:
        raise EventError(f"{etype}: {problems[0]}")
    path = events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
    return event


def read_events(root: Path, run_id: str | None = None) -> list[dict[str, Any]]:
    """Alle lesbaren Events, optional nur die eines Laufs. Defekte Zeilen werden übersprungen."""
    path = events_path(root)
    if not path.is_file():
        return []
    found: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and (run_id is None or event.get("run_id") == run_id):
                found.append(event)
    return found


def last_event_at(root: Path, run_id: str) -> datetime | None:
    """Zeitpunkt des letzten Events eines Laufs, ``None`` ohne Events."""
    latest: datetime | None = None
    for event in read_events(root, run_id):
        try:
            ts = runs.parse_ts(str(event["ts"]))
        except (KeyError, ValueError):
            continue
        if latest is None or ts > latest:
            latest = ts
    return latest
