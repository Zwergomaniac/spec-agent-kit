"""Hooks ``SubagentStart`` und ``SubagentStop`` (Spec 003 FR-012).

Die Hooks melden Stationen als ``station.started`` und ``station.finished``. Sie machen keinen
Netzwerkzugriff, enden immer still und lassen nie eine Ausnahme nach außen (Exit-Code immer 0).
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final, TextIO

from spec_agent_kit.config import load_config
from spec_agent_kit.pipeline import runs
from spec_agent_kit.pipeline.events import NAME_MAX, emit, read_events

PHASES: Final[tuple[str, ...]] = ("start", "stop")
_MAX_PAYLOAD: Final[int] = 1_000_000
_LOCK_WAIT_S: Final[float] = 0.5
_LOCK_STALE_S: Final[float] = 5.0
_MAX_KEYS: Final[int] = 50


def agent_type(payload: dict[str, Any]) -> str | None:
    """Agent-Typ aus ``agent_type``, ``subagent_type`` oder ``tool_input.subagent_type``."""
    for key in ("agent_type", "subagent_type"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        value = tool_input.get("subagent_type")
        if isinstance(value, str) and value:
            return value
    return None


@contextlib.contextmanager
def _locked(path: Path) -> Iterator[None]:
    """Kurze Dateisperre, damit parallel startende Prüfer sich nicht überschreiben.

    Bei Zeitüberschreitung läuft der Hook ohne Sperre weiter (lieber ein Event als keines).
    """
    lock = path.with_suffix(".lock")
    deadline = time.monotonic() + _LOCK_WAIT_S
    acquired = False
    while True:
        try:
            handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(handle)
            acquired = True
            break
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - lock.stat().st_mtime > _LOCK_STALE_S:
                    lock.unlink()
                    continue
            if time.monotonic() >= deadline:
                break
            time.sleep(0.01)
        except OSError:
            break
    try:
        yield
    finally:
        if acquired:
            with contextlib.suppress(OSError):
                lock.unlink()


def _diag_written(root: Path, phase: str) -> bool:
    return any(
        e.get("type") == "diag.hook" and (e.get("data") or {}).get("phase") == phase
        for e in read_events(root)
    )


def _role_of(cfg_roles: dict[str, dict[str, Any]], agent: str) -> str | None:
    for role, settings in cfg_roles.items():
        if settings.get("agent") == agent:
            return role
    return None


def _handle(root: Path, phase: str, payload: dict[str, Any]) -> None:
    cfg = load_config(root)
    run = runs.active_run(root)
    if run is None:
        return
    project = str(cfg.data["project"]["key"])
    agent = agent_type(payload)
    if agent is None:
        if not _diag_written(root, phase):
            keys = [str(k)[:NAME_MAX] for k in sorted(payload)][:_MAX_KEYS]
            emit(root, "diag.hook", project=project, phase=phase, keys=keys)
        return
    active = {role: cfg.role(role) for role in cfg.active_roles()}
    role = _role_of(active, agent)
    if role is None:
        return
    settings = active[role]
    store = runs.run_dir(root, run["run_id"]) / "open-stations.json"
    now = runs.utcnow()
    with _locked(store):
        opened = runs.read_json_file(store)
        if phase == "start":
            opened[agent] = now.isoformat()
            runs.write_text_atomic(store, json.dumps(opened))
            emit(
                root,
                "station.started",
                project=project,
                run=run,
                round=run["round"],
                role=role,
                agent=agent,
                model=str(settings["model"]),
                effort=str(settings["effort"]),
            )
            return
        started = opened.pop(agent, None)
        duration = 0.0
        if isinstance(started, str):
            duration = max(0.0, (now - runs.parse_ts(started)).total_seconds())
        runs.write_text_atomic(store, json.dumps(opened))
        emit(
            root,
            "station.finished",
            project=project,
            run=run,
            round=run["round"],
            role=role,
            agent=agent,
            duration_s=round(duration, 1),
        )


def cmd_hook(phase: str, stdin: TextIO, root: Path | None) -> None:
    """Verarbeitet einen Hook-Aufruf. Wirft nie eine Ausnahme."""
    try:
        if root is None or phase not in PHASES:
            return
        raw = stdin.read(_MAX_PAYLOAD)
        payload = json.loads(raw or "{}")
        if isinstance(payload, dict):
            _handle(root, phase, payload)
    except Exception:  # ein Hook darf den Lauf nie blockieren
        return
