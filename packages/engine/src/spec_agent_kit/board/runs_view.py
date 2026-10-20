"""Läufe und Events -> ``runs[]`` des Board-Dokuments (Spec 006 FR-004).

Quelle sind ``runs/*/run.json`` und ``events.jsonl``. Zustand, Runde und Rundenlimit kommen aus der
``run.json``; Stationen, Urteile und Eskalationen aus den Events. „Inaktiv“ und „verwaist“ werden
aus dem letzten Event berechnet (Spec 001 FR-012), nie gespeichert.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final

from spec_agent_kit import contracts
from spec_agent_kit.config import EffectiveConfig
from spec_agent_kit.pipeline import runs as run_store
from spec_agent_kit.pipeline.events import clip, events_path

RUNS_MAX: Final[int] = contracts.LIMITS["RUNS_MAX"]
_CLOSING: Final[frozenset[str]] = frozenset(
    {"run.released", "run.returned", "run.approved", "run.aborted", "run.taken_over", "run.merged"}
)


@dataclass
class EventLog:
    """Alle lesbaren Events nach Lauf-ID sortiert, plus die Zahl übersprungener Zeilen."""

    by_run: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    skipped: int = 0
    present: bool = False


def read_event_log(root: Path) -> EventLog:
    """Liest ``events.jsonl`` tolerant: kaputte Zeilen werden gezählt und übersprungen."""
    log = EventLog()
    path = events_path(root)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return log
    log.present = True
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            log.skipped += 1
            continue
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            log.skipped += 1
            continue
        run_id = event.get("run_id")
        if isinstance(run_id, str):
            log.by_run.setdefault(run_id, []).append(event)
    return log


def _ts(value: Any) -> datetime | None:
    try:
        return run_store.parse_ts(str(value))
    except ValueError:
        return None


def _add_station(
    stations: list[dict[str, Any]], event: dict[str, Any], data: dict[str, Any]
) -> None:
    entry: dict[str, Any] = {
        "round": data.get("round"),
        "role": data.get("role"),
        "agent": data.get("agent"),
        "state": "running",
        "started_at": event.get("ts"),
    }
    if data.get("model"):
        entry["model"] = data["model"]
    stations.append(entry)


def _find_station(
    stations: list[dict[str, Any]], *, rnd: Any, role: Any = None, agent: Any = None, running: bool
) -> dict[str, Any] | None:
    for entry in reversed(stations):
        if entry["round"] != rnd:
            continue
        if role is not None and entry["role"] != role:
            continue
        if agent is not None and entry["agent"] != agent:
            continue
        if running and entry["state"] != "running":
            continue
        return entry
    return None


def _apply_events(
    run: dict[str, Any], events: list[dict[str, Any]], cfg: EffectiveConfig
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(stations, escalations)`` aus den Events eines Laufs."""
    stations: list[dict[str, Any]] = []
    escalations: list[dict[str, Any]] = []
    for event in events:
        etype = event.get("type")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if etype == "station.started":
            _add_station(stations, event, data)
        elif etype == "station.finished":
            entry = _find_station(
                stations, rnd=data.get("round"), agent=data.get("agent"), running=True
            )
            if entry is None:
                seconds = float(data.get("duration_s") or 0)
                end = _ts(event.get("ts"))
                started = (
                    run_store.format_ts(end - timedelta(seconds=seconds))
                    if end
                    else event.get("ts")
                )
                entry = {
                    "round": data.get("round"),
                    "role": data.get("role"),
                    "agent": data.get("agent"),
                    "state": "running",
                    "started_at": started,
                }
                stations.append(entry)
            entry["state"] = "finished"
            if data.get("duration_s") is not None:
                entry["duration_s"] = data["duration_s"]
        elif etype == "verdict.recorded":
            role = data.get("role")
            entry = _find_station(stations, rnd=data.get("round"), role=role, running=False)
            if entry is None:
                # Urteil ohne Hook-Station (z. B. Nur-Prüfung): Station aus der Config ergänzen.
                agent = (
                    str(cfg.role(role)["agent"]) if role in cfg.data["pipeline"]["roles"] else role
                )
                entry = {
                    "round": data.get("round"),
                    "role": role,
                    "agent": agent,
                    "state": "finished",
                    "started_at": event.get("ts"),
                }
                stations.append(entry)
            entry["verdict"] = data.get("verdict")
            entry["must_count"] = data.get("must_count")
            entry["may_count"] = data.get("may_count")
        elif etype == "run.escalated":
            item: dict[str, Any] = {
                "ts": event.get("ts"),
                "round": data.get("round"),
                "reason": clip(str(data.get("reason") or "")) or "Eskaliert",
                "open": True,
            }
            if data.get("gate"):
                item["gate"] = data["gate"]
            escalations.append(item)
        elif etype in _CLOSING:
            for item in escalations:
                item["open"] = False
    # Eine Eskalation bleibt offen, solange der Lauf eskaliert ist (auch pausiert aus `escalated`).
    still_open = run.get("state") == "escalated" or (
        run.get("state") == "paused" and run.get("paused_from") == "escalated"
    )
    if not still_open:
        for item in escalations:
            item["open"] = False
    return stations, escalations


def build_run(
    run: dict[str, Any],
    events: list[dict[str, Any]],
    cfg: EffectiveConfig,
    now: datetime,
) -> dict[str, Any]:
    """Ein ``runs[]``-Eintrag. Wirft bei unbrauchbarer ``run.json``; der Aufrufer fängt das ab."""
    pipeline = cfg.data["pipeline"]
    last: datetime | None = None
    for event in events:
        moment = _ts(event.get("ts"))
        if moment is not None and (last is None or moment > last):
            last = moment
    info = run_store.idle_info(
        run,
        last,
        idle_minutes=int(pipeline["idle_minutes"]),
        stale_hours=int(pipeline["stale_hours"]),
        now=now,
    )
    started = str(run["started_at"])
    updated = str(run.get("updated_at") or started)
    stations, escalations = _apply_events(run, events, cfg)
    item: dict[str, Any] = {
        "run_id": run["run_id"],
        "spec": run["spec"],
        "kind": run.get("kind", "pipeline"),
        "state": run["state"],
        "round": int(run["round"]),
        "max_rounds": int(run["max_rounds"]),
        "active": run["state"] in run_store.ACTIVE_STATES,
        "started_at": started,
        "updated_at": updated,
        "last_event_at": info["last_event_at"] or updated,
        "idle": bool(info["idle"]),
        "stale": bool(info["stale"]),
        "stations": stations,
        "escalations": escalations,
    }
    origin = run.get("origin")
    if isinstance(origin, dict) and origin:
        item["origin"] = {k: str(v)[:100] for k, v in origin.items() if v and k != "source"}
        if origin.get("source") in {"local", "cloud"}:
            item["origin"]["source"] = origin["source"]
        if not item["origin"]:
            del item["origin"]
    return item


def collect_runs(
    root: Path, cfg: EffectiveConfig, log: EventLog, now: datetime, notes: list[str]
) -> list[dict[str, Any]]:
    """Alle Läufe als ``runs[]``-Einträge, neueste zuerst und ohne Begrenzung."""
    items: list[dict[str, Any]] = []
    for run in run_store.all_runs(root):
        try:
            items.append(build_run(run, log.by_run.get(run["run_id"], []), cfg, now))
        except (KeyError, TypeError, ValueError) as exc:
            notes.append(clip(f"Lauf {run.get('run_id')} nicht lesbar ({type(exc).__name__})", 280))
    items.sort(key=lambda r: (r["started_at"], r["run_id"]), reverse=True)
    return items


def attention_for_runs(runs: list[dict[str, Any]], stale_hours: int) -> list[dict[str, str]]:
    """``escalation``- und ``stale_run``-Einträge (Spec 006 FR-003)."""
    entries: list[dict[str, str]] = []
    for run in runs:
        source = f"runs/{run['run_id']}"
        if run["state"] == "escalated":
            open_items = [e for e in run["escalations"] if e["open"]]
            reason = open_items[-1]["reason"] if open_items else "Eskaliert"
            entries.append(
                {"kind": "escalation", "spec": run["spec"], "reason": reason, "source": source}
            )
        if run["active"] and run["stale"]:
            entries.append(
                {
                    "kind": "stale_run",
                    "spec": run["spec"],
                    "reason": clip(
                        f"Lauf {run['run_id']} ohne Ereignis seit mehr als {stale_hours} h "
                        f"(zuletzt {run['last_event_at']})"
                    ),
                    "source": source,
                }
            )
    return entries
