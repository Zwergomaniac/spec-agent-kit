"""Läufe: Lauf-ID, ``run.json``, Auflösung von Lauf-ID, Spec-Verzeichnis und Spec-Nummer, Sperre.

Der Zustand liegt unter ``.spec-agent/state/runs/<run_id>/`` (Spec 003 FR-003) und ist gitignored.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from spec_agent_kit.pipeline import RefusedError

STATE_RELATIVE: Final[str] = ".spec-agent/state"
ACTIVE_STATES: Final[frozenset[str]] = frozenset({"building", "reviewing", "approved", "escalated"})
TERMINAL_STATES: Final[frozenset[str]] = frozenset({"merged", "reviewed", "aborted"})
"""``paused`` ist ruhend: weder aktiv (keine Sperre) noch beendet."""

_RUN_ID = re.compile(r"^[0-9]{3}-[0-9]{8}-[0-9]{6}(?:-[a-z0-9]{1,8})?$")
_SPEC_NUMBER = re.compile(r"^[0-9]{1,3}$")


def utcnow() -> datetime:
    """Aktuelle UTC-Zeit. Tests ersetzen diese Funktion, um Zeit zu simulieren."""
    return datetime.now(UTC)


def format_ts(moment: datetime) -> str:
    """RFC 3339 mit Sekundengenauigkeit und ``Z``."""
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def state_dir(root: Path) -> Path:
    return root / STATE_RELATIVE


def runs_dir(root: Path) -> Path:
    return state_dir(root) / "runs"


def run_dir(root: Path, run_id: str) -> Path:
    return runs_dir(root) / run_id


def spec_number(spec: str) -> str:
    return spec.split("-", 1)[0]


def new_run_id(root: Path, spec: str, now: datetime) -> str:
    """``NNN-YYYYMMDD-HHMMSS`` (UTC); bei Kollision in derselben Sekunde mit Suffix ``-b``."""
    base = f"{spec_number(spec)}-{now.astimezone(UTC):%Y%m%d-%H%M%S}"
    if not run_dir(root, base).exists():
        return base
    for suffix in "bcdefghijklmnopqrstuvwxyz":
        candidate = f"{base}-{suffix}"
        if not run_dir(root, candidate).exists():
            return candidate
    raise RefusedError(f"keine freie Lauf-ID für {base}")  # pragma: no cover


def read_run(root: Path, run_id: str) -> dict[str, Any]:
    path = run_dir(root, run_id) / "run.json"
    if not path.is_file():
        raise RefusedError(f"Lauf {run_id} nicht gefunden")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RefusedError(f"run.json von {run_id} ist nicht lesbar") from exc
    if not isinstance(loaded, dict):
        raise RefusedError(f"run.json von {run_id} ist kein Objekt")
    return loaded


def write_text_atomic(path: Path, text: str) -> None:
    """Schreibt über eine Temp-Datei und ``os.replace``, damit nie eine halbe Datei liegt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def write_run(root: Path, run: dict[str, Any]) -> None:
    run["updated_at"] = format_ts(utcnow())
    write_text_atomic(
        run_dir(root, run["run_id"]) / "run.json",
        json.dumps(run, ensure_ascii=False, indent=2) + "\n",
    )


def all_runs(root: Path) -> list[dict[str, Any]]:
    """Alle lesbaren Läufe, älteste zuerst (Lauf-IDs sind nach Startzeit sortierbar)."""
    runs: list[dict[str, Any]] = []
    base = runs_dir(root)
    if not base.is_dir():
        return runs
    for path in sorted(base.glob("*/run.json")):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(loaded, dict) and isinstance(loaded.get("run_id"), str):
            runs.append(loaded)
    runs.sort(key=lambda r: (str(r.get("started_at", "")), r["run_id"]))
    return runs


def active_run(root: Path) -> dict[str, Any] | None:
    """Der Lauf, der die Sperre belegt (building, reviewing, approved, escalated)."""
    for run in all_runs(root):
        if run.get("state") in ACTIVE_STATES:
            return run
    return None


def paused_runs(root: Path) -> list[dict[str, Any]]:
    return [r for r in all_runs(root) if r.get("state") == "paused"]


def resolve_spec(root: Path, token: str) -> str:
    """Spec-Verzeichnis ``NNN-slug`` aus Verzeichnisname oder Nummer."""
    specs = root / "specs"
    if (specs / token).is_dir():
        return token
    if _SPEC_NUMBER.match(token):
        prefix = token.zfill(3)
        matches = sorted(p.name for p in specs.glob(f"{prefix}-*") if p.is_dir())
        if len(matches) == 1:
            return matches[0]
        raise RefusedError(f"Spec '{token}' nicht eindeutig gefunden ({len(matches)} Treffer)")
    raise RefusedError(f"Spec '{token}' nicht gefunden")


def resolve_run(
    root: Path,
    token: str,
    *,
    include_finished: bool = False,
    only_states: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Lauf aus Lauf-ID, Spec-Verzeichnis oder Spec-Nummer (Spec 003 FR-002).

    Bei Spec-Angabe gilt der jüngste nicht beendete Lauf; mit ``include_finished`` der jüngste
    Lauf überhaupt, mit ``only_states`` der jüngste Lauf in einem dieser Zustände.
    """
    if _RUN_ID.match(token) and (run_dir(root, token) / "run.json").is_file():
        return read_run(root, token)  # Eine Lauf-ID ist eindeutig, der Zustand zählt hier nicht.
    known = {r.get("spec") for r in all_runs(root)}
    if token in known:
        spec = token
    elif _SPEC_NUMBER.match(token):
        prefix = token.zfill(3) + "-"
        candidates = sorted(s for s in known if isinstance(s, str) and s.startswith(prefix))
        if not candidates:
            raise RefusedError(f"kein Lauf für '{token}'")
        if len(candidates) > 1:
            raise RefusedError(f"Spec-Nummer '{token}' ist nicht eindeutig: {candidates}")
        spec = candidates[0]
    else:
        raise RefusedError(f"kein Lauf für '{token}'")
    runs = [r for r in all_runs(root) if r.get("spec") == spec]
    if only_states is not None:
        runs = [r for r in runs if r.get("state") in only_states]
    elif not include_finished:
        runs = [r for r in runs if r.get("state") not in TERMINAL_STATES]
    if not runs:
        raise RefusedError(f"kein passender Lauf für {spec} (preflight zuerst)")
    return runs[-1]


def idle_info(
    run: dict[str, Any],
    last_event: datetime | None,
    *,
    idle_minutes: int,
    stale_hours: int,
    now: datetime,
) -> dict[str, Any]:
    """``idle`` und ``stale`` eines aktiven Laufs (Spec 001 FR-012, berechnet, kein Zustand)."""
    if run.get("state") not in ACTIVE_STATES:
        return {"idle": False, "stale": False, "last_event_at": _fmt(last_event)}
    reference = last_event or parse_ts(str(run.get("updated_at") or run.get("started_at")))
    age = now - reference
    return {
        "idle": age >= timedelta(minutes=idle_minutes),
        "stale": age >= timedelta(hours=stale_hours),
        "last_event_at": format_ts(reference),
    }


def _fmt(moment: datetime | None) -> str | None:
    return format_ts(moment) if moment else None


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}
