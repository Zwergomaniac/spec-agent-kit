"""``sak migrate legacy-pipeline``: alte Pipeline-Historie ins v1-Format (Spec 010 FR-005).

Quelle: ``<dir>/events.jsonl`` und ``<dir>/runs/*/run.json`` (Default ``.specify/pipeline``).
Ziel: ``.spec-agent/state/events.jsonl`` und ``.spec-agent/state/runs/<run_id>/run.json``.
Die Zuordnung der Werte folgt Spec 001, Anhang A.

Eigenschaften:

- Ohne ``apply`` wird nichts geschrieben; das Ergebnis ist der Plan.
- Lauf-ID: ``NNN-YYYYMMDD-HHMMSS`` aus Spec-Nummer und Zeit von ``run_started`` (UTC); ohne dieses
  Event aus ``started_at`` der ``run.json``.
- Event-IDs sind ULIDs aus Zeit und einem Hash des alten Eintrags (mit Zählung gleicher Einträge).
  Ein zweiter Import findet die IDs wieder und schreibt nichts. Vorhandene Läufe bleiben unberührt.
- ``aborted`` bleibt ``aborted``; es gibt keine Umdeutung zu ``paused``.
- Alles, was sich nicht abbilden lässt, wird gezählt und gemeldet, nie stillschweigend verworfen.
- Pro Spec gibt es genau einen Lauf (den aus ``run.json``); alle Events der Spec gehören dazu.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from spec_agent_kit import contracts
from spec_agent_kit.config import EffectiveConfig
from spec_agent_kit.migrate import MigrateError
from spec_agent_kit.pipeline import runs as run_store
from spec_agent_kit.pipeline.events import NAME_MAX, REASON_MAX, clip, events_path
from spec_agent_kit.pipeline.git import resolve_commit

DEFAULT_SOURCE: Final[str] = ".specify/pipeline"
ZERO_SHA: Final[str] = "0" * 40
IMPORT_MARK: Final[str] = "legacy-pipeline"
_SPEC_DIR = re.compile(r"[0-9]{3}-[a-z0-9][a-z0-9-]{0,80}")
_RUN_ID = re.compile(r"[0-9]{3}-[0-9]{8}-[0-9]{6}")

ROLE_MAP: Final[dict[str, str]] = {
    "builder": "builder",
    "code": "code_review",
    "ui": "ui_review",
    "security": "security_review",
    "docs": "docs",
    "integrator": "integrator",
    "code_review": "code_review",
    "ui_review": "ui_review",
    "security_review": "security_review",
}
VERDICT_MAP: Final[dict[str, str]] = {
    "ok": "approve",
    "änderung": "changes_requested",
    "aenderung": "changes_requested",
    "mensch prüft": "needs_human",
    "mensch prueft": "needs_human",
    "approve": "approve",
    "changes_requested": "changes_requested",
    "needs_human": "needs_human",
}
SIMPLE_KINDS: Final[dict[str, str]] = {
    "approved": "run.approved",
    "merged": "run.merged",
}
REASON_KINDS: Final[dict[str, str]] = {
    "aborted": "run.aborted",
    "released": "run.released",
}
KNOWN_KINDS: Final[frozenset[str]] = frozenset(
    {
        "run_started",
        "round_started",
        "station_started",
        "station_finished",
        "verdict",
        "escalated",
        "hook_debug",
        *SIMPLE_KINDS,
        *REASON_KINDS,
    }
)


@dataclass
class LegacyRun:
    spec: str
    data: dict[str, Any]
    run_id: str
    state: str
    started_ts: datetime


@dataclass
class Plan:
    source: Path
    project: str
    runs: list[dict[str, Any]] = field(default_factory=list)
    new_runs: list[tuple[dict[str, Any], Path]] = field(default_factory=list)
    """``(run.json-Inhalt, Zielpfad)`` der noch nicht vorhandenen Läufe."""
    new_events: list[dict[str, Any]] = field(default_factory=list)
    events_read: int = 0
    events_mapped: int = 0
    events_present: int = 0
    by_type: Counter[str] = field(default_factory=Counter)
    unknown_kinds: Counter[str] = field(default_factory=Counter)
    skipped: Counter[str] = field(default_factory=Counter)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self, *, applied: bool) -> dict[str, Any]:
        return {
            "ok": True,
            "mode": "applied" if applied else "plan",
            "source": self.source.as_posix(),
            "project": self.project,
            "runs": self.runs,
            "events": {
                "read": self.events_read,
                "mapped": self.events_mapped,
                "new": len(self.new_events),
                "already_present": self.events_present,
                "skipped": sum(self.skipped.values()),
                "by_type": dict(sorted(self.by_type.items())),
            },
            "unknown_kinds": dict(sorted(self.unknown_kinds.items())),
            "skipped": [{"reason": k, "count": v} for k, v in sorted(self.skipped.items())],
            "warnings": self.warnings,
            "next": (
                "Import geschrieben. Mit 'sak push' gehen die Events ans Dashboard."
                if applied
                else "Nichts geschrieben. Mit --apply umsetzen."
            ),
        }


def _parse(value: Any) -> datetime | None:
    try:
        moment = run_store.parse_ts(str(value))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def _short(value: Any, limit: int = NAME_MAX) -> str:
    return str(value or "")[:limit]


def _is_sha40(value: str) -> bool:
    return len(value) == 40 and all(c in "0123456789abcdef" for c in value)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _read_legacy_events(path: Path, plan: Plan) -> list[dict[str, Any]]:
    if not path.is_file():
        plan.warnings.append(f"{path.name} fehlt: nur Läufe aus run.json werden übernommen")
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        plan.events_read += 1
        try:
            item = json.loads(line)
        except ValueError:
            plan.skipped["Zeile ist kein JSON"] += 1
            continue
        if not isinstance(item, dict) or not isinstance(item.get("kind"), str):
            plan.skipped["Eintrag ohne 'kind'"] += 1
            continue
        entries.append(item)
    return entries


def _read_legacy_runs(
    source: Path, plan: Plan, started: dict[str, datetime]
) -> dict[str, LegacyRun]:
    runs: dict[str, LegacyRun] = {}
    base = source / "runs"
    allowed = set(contracts.vocabulary()["run_state"])
    for path in sorted(base.glob("*/run.json")) if base.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            plan.warnings.append(f"runs/{path.parent.name}/run.json nicht lesbar: übersprungen")
            continue
        if not isinstance(data, dict):
            plan.warnings.append(f"runs/{path.parent.name}/run.json ist kein Objekt: übersprungen")
            continue
        spec = str(data.get("spec") or path.parent.name)
        if not _SPEC_DIR.fullmatch(spec):
            plan.warnings.append(f"runs/{path.parent.name}/run.json: ungültige Spec, übersprungen")
            continue
        state = str(data.get("state") or "")
        if state not in allowed:
            plan.warnings.append(f"Lauf {spec}: Zustand '{state}' unbekannt, Lauf übersprungen")
            continue
        moment = started.get(spec) or _parse(data.get("started_at"))
        if moment is None:
            plan.warnings.append(f"Lauf {spec}: keine Startzeit, Lauf übersprungen")
            continue
        run_id = f"{spec[:3]}-{moment.astimezone(UTC):%Y%m%d-%H%M%S}"
        if not _RUN_ID.fullmatch(run_id):  # pragma: no cover - durch spec und moment gesichert
            plan.warnings.append(f"Lauf {spec}: ungültige Lauf-ID, übersprungen")
            continue
        runs[spec] = LegacyRun(spec, data, run_id, state, moment)
    return runs


def _run_json(legacy: LegacyRun, root: Path, cfg: EffectiveConfig, plan: Plan) -> dict[str, Any]:
    data = legacy.data
    base_branch = _short(data.get("base_branch")) or str(cfg.data["project"]["base_branch"])
    raw_commit = str(data.get("base_commit") or "").strip()
    commit: str | None = raw_commit if _is_sha40(raw_commit) else None
    if commit is None and raw_commit:
        try:
            commit = resolve_commit(root, raw_commit)
        except Exception:  # Git fehlt oder Ref unbrauchbar: dann greift der Ersatzwert
            commit = None
    if commit is None:
        plan.warnings.append(
            f"Lauf {legacy.spec}: base_commit '{raw_commit}' nicht auflösbar, 40 Nullen eingesetzt"
        )
        commit = ZERO_SHA
    started = run_store.format_ts(legacy.started_ts)
    updated = _parse(data.get("updated_at"))
    try:
        rnd = max(1, int(data.get("round") or 1))
    except (TypeError, ValueError):
        rnd = 1
    return {
        "run_id": legacy.run_id,
        "spec": legacy.spec,
        "kind": "pipeline",
        "state": legacy.state,
        "paused_from": None,
        "round": rnd,
        "max_rounds": max(rnd, int(cfg.data["pipeline"]["max_rounds"])),
        "branch": _short(data.get("branch")) or legacy.spec,
        "base_branch": base_branch,
        "base_commit": commit,
        "started_at": started,
        "updated_at": run_store.format_ts(updated) if updated else started,
        "escalation": None,
        "origin": {"branch": base_branch},
        "imported_from": IMPORT_MARK,
    }


def map_event(item: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Ein alter Eintrag als ``{"type", "data"}`` oder ``(None, Grund)``.

    Die Hülle (``event_id``, ``ts``, Lauf-Bezug) setzt der Aufrufer. Für ``run_started`` liefert die
    Funktion leere ``data``; der Aufrufer füllt sie aus dem Lauf.
    """
    kind = item["kind"]
    rnd = _int(item.get("round"))
    if kind == "run_started":
        return {"type": "run.started", "data": {}}, ""
    if kind == "round_started":
        if rnd is None or rnd < 1:
            return None, "round_started ohne gültige Runde"
        return {"type": "round.started", "data": {"round": rnd}}, ""
    if kind in {"station_started", "station_finished"}:
        role = ROLE_MAP.get(str(item.get("station")))
        agent = _short(item.get("agent"))
        if role is None or not agent or rnd is None or rnd < 1:
            return None, f"{kind} ohne gültige Station, Agent oder Runde"
        data: dict[str, Any] = {"round": rnd, "role": role, "agent": agent}
        if kind == "station_started":
            for key in ("model", "effort"):
                if item.get(key):
                    data[key] = _short(item[key])
            return {"type": "station.started", "data": data}, ""
        duration = item.get("duration_s")
        if not isinstance(duration, int | float) or isinstance(duration, bool) or duration < 0:
            return None, "station_finished ohne duration_s"
        data["duration_s"] = duration
        return {"type": "station.finished", "data": data}, ""
    if kind == "verdict":
        role = ROLE_MAP.get(str(item.get("station")))
        verdict = VERDICT_MAP.get(str(item.get("verdict") or "").strip().casefold())
        must = _int(item.get("muss_count"))
        may = _int(item.get("kann_count", 0))
        if role is None or verdict is None or rnd is None or rnd < 1 or must is None or may is None:
            return None, "verdict mit unbekannter Station, Urteil oder Zählern"
        if verdict == "changes_requested" and must < 1:
            return None, "Urteil 'Änderung' ohne Muss-Befund ist in v1 ungültig"
        return {
            "type": "verdict.recorded",
            "data": {
                "round": rnd,
                "role": role,
                "verdict": verdict,
                "must_count": must,
                "may_count": may,
            },
        }, ""
    if kind == "escalated":
        if rnd is None or rnd < 1:
            return None, "escalated ohne gültige Runde"
        reason = clip(str(item.get("reason") or ""), REASON_MAX) or "Eskaliert (ohne Begründung)"
        return {"type": "run.escalated", "data": {"round": rnd, "reason": reason}}, ""
    if kind in SIMPLE_KINDS:
        return {"type": SIMPLE_KINDS[kind], "data": {}}, ""
    if kind in REASON_KINDS:
        reason = clip(str(item.get("reason") or ""), REASON_MAX)
        return {"type": REASON_KINDS[kind], "data": {"reason": reason} if reason else {}}, ""
    if kind == "hook_debug":
        keys = item.get("keys")
        phase = item.get("phase")
        if phase not in {"start", "stop"} or not isinstance(keys, list):
            return None, "hook_debug ohne phase oder keys"
        return {
            "type": "diag.hook",
            "data": {"phase": phase, "keys": [str(k)[:100] for k in keys[:50]]},
        }, ""
    return None, ""


def _event_id(item: dict[str, Any], moment: datetime, occurrence: int, project: str) -> str:
    seed = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return contracts.deterministic_ulid(
        int(moment.timestamp() * 1000), f"legacy-pipeline|{project}|{seed}|{occurrence}"
    )


def _existing_event_ids(root: Path) -> set[str]:
    path = events_path(root)
    found: set[str] = set()
    if not path.is_file():
        return found
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and isinstance(event.get("event_id"), str):
            found.add(event["event_id"])
    return found


def build_plan(root: Path, cfg: EffectiveConfig, source: Path | None = None) -> Plan:
    """Liest die alte Pipeline und plant den Import. Schreibt nichts."""
    directory = source if source is not None else Path(DEFAULT_SOURCE)
    if not directory.is_absolute():
        directory = root / directory
    if not directory.is_dir():
        raise MigrateError(f"Quellverzeichnis nicht gefunden: {directory.as_posix()}")
    project = str(cfg.data["project"]["key"])
    plan = Plan(source=directory, project=project)
    entries = _read_legacy_events(directory / "events.jsonl", plan)

    started: dict[str, datetime] = {}
    starts: Counter[str] = Counter()
    for item in entries:
        if item["kind"] == "run_started":
            spec = str(item.get("spec") or "")
            starts[spec] += 1
            moment = _parse(item.get("ts"))
            if moment is not None and spec not in started:
                started[spec] = moment
    for spec, count in sorted(starts.items()):
        if count > 1:
            plan.warnings.append(
                f"{spec}: {count} run_started-Einträge, aber nur ein run.json; "
                "alle Events gehören zu einem Lauf"
            )
    legacy_runs = _read_legacy_runs(directory, plan, started)

    existing_ids = _existing_event_ids(root)
    run_dicts: dict[str, dict[str, Any]] = {}
    rows: dict[str, dict[str, Any]] = {}
    for spec, legacy in legacy_runs.items():
        run = _run_json(legacy, root, cfg, plan)
        run_dicts[spec] = run
        target = run_store.run_dir(root, legacy.run_id) / "run.json"
        exists = target.is_file()
        if not exists:
            plan.new_runs.append((run, target))
        if legacy.state in run_store.ACTIVE_STATES:
            plan.warnings.append(
                f"Lauf {legacy.run_id} ist {legacy.state} und belegt nach dem Import die "
                "Pipeline-Sperre"
            )
        rows[spec] = {
            "run_id": legacy.run_id,
            "spec": spec,
            "state": legacy.state,
            "round": run["round"],
            "status": "exists" if exists else "new",
            "events": 0,
        }
        plan.runs.append(rows[spec])

    work: list[tuple[datetime, int, dict[str, Any]]] = []
    for index, item in enumerate(entries):
        moment = _parse(item.get("ts"))
        if moment is None:
            plan.skipped["Eintrag ohne gültigen Zeitpunkt"] += 1
            continue
        work.append((moment, index, item))
    # Läufe ohne altes run_started (zum Beispiel von Hand angelegt) bekommen ein synthetisches.
    for spec, legacy in legacy_runs.items():
        if starts.get(spec, 0) == 0:
            synthetic = {"kind": "run_started", "spec": spec, "ts": run_dicts[spec]["started_at"]}
            work.append((legacy.started_ts, -1, synthetic))
    work.sort(key=lambda w: (w[0], w[1]))

    seen: Counter[str] = Counter()
    for moment, _index, item in work:
        kind = item["kind"]
        if kind not in KNOWN_KINDS:
            plan.unknown_kinds[kind] += 1
            continue
        spec = str(item.get("spec") or "")
        run = run_dicts.get(spec)
        has_run = kind != "hook_debug"
        if has_run and run is None:
            plan.skipped[f"{kind} ohne passenden Lauf (kein run.json)"] += 1
            continue
        mapped, reason = map_event(item)
        if mapped is None:
            plan.skipped[reason] += 1
            continue
        if kind == "run_started" and run is not None:
            mapped["data"] = {
                "kind": "pipeline",
                "base_branch": run["base_branch"],
                "base_commit": run["base_commit"],
                "max_rounds": run["max_rounds"],
            }
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        occurrence = seen[key]
        seen[key] += 1
        event: dict[str, Any] = {
            "schema": "sak.event/1",
            "event_id": _event_id(item, moment, occurrence, project),
            "type": mapped["type"],
            "ts": run_store.format_ts(moment),
            "project": project,
        }
        if has_run and run is not None:
            event["run_id"] = run["run_id"]
            event["spec"] = run["spec"]
            event["origin"] = {"branch": run["origin"]["branch"]}
        event["data"] = mapped["data"]
        problems = contracts.validate_event(event)
        if problems:
            plan.skipped[f"{kind}: nach v1 ungültig ({problems[0][:120]})"] += 1
            continue
        plan.events_mapped += 1
        plan.by_type[event["type"]] += 1
        if event["event_id"] in existing_ids:
            plan.events_present += 1
            continue
        plan.new_events.append(event)
        if has_run:
            rows[spec]["events"] += 1
    return plan


def apply_plan(root: Path, plan: Plan) -> None:
    """Schreibt neue Läufe und hängt neue Events (älteste zuerst) an ``events.jsonl`` an."""
    for run, target in plan.new_runs:
        run_store.write_text_atomic(target, json.dumps(run, ensure_ascii=False, indent=2) + "\n")
    if plan.new_events:
        path = events_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            for event in plan.new_events:
                handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
