"""Setzt einen Installationsplan um (Spec 005 FR-006, FR-009).

Geschrieben wird atomar je Datei (Temp-Datei + ``os.replace``). Das Lockfile kommt zuletzt.
Danach laufen ``uv sync`` und ``config check``. Es wird nie committet.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Final

from spec_agent_kit.config.check import check as check_config
from spec_agent_kit.install import InstallError
from spec_agent_kit.install.kit import (
    ENGINE_TARGET,
    LAUNCHER_CMD_TARGET,
    LAUNCHER_SH_TARGET,
    LOCK_TARGET,
    sha256_of,
)
from spec_agent_kit.install.plan import (
    CONFLICT,
    CREATE,
    DELETE,
    MERGE,
    REPLACE,
    SAK_NEW_SUFFIX,
    Action,
    Plan,
)

SYNC_TIMEOUT_SECONDS: Final[int] = 600
_KEEP_DIRS: Final[frozenset[str]] = frozenset(
    {"", ".claude", ".claude/agents", ".claude/skills", ".spec-agent"}
)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".sak-tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def _prune_empty_parents(target: Path, relative: str) -> None:
    parent = Path(relative).parent
    while parent.as_posix() not in _KEEP_DIRS:
        directory = target / parent
        try:
            directory.rmdir()
        except OSError:
            return
        parent = parent.parent


def _current_hash(path: Path) -> str | None:
    return sha256_of(path.read_bytes()) if path.is_file() else None


def _precheck(plan: Plan) -> None:
    """Das Ziel muss noch so aussehen wie bei der Planung."""
    for action in plan.actions:
        if action.kind in {CREATE, MERGE, REPLACE, DELETE, CONFLICT}:
            current = _current_hash(plan.target / action.path)
            if current != action.expect:
                raise InstallError.single(
                    action.path, "hat sich seit der Planung geändert; bitte neu planen"
                )


def _launcher_bytes(path: str, data: bytes) -> bytes:
    """Starter: ``sak.cmd`` mit CRLF (Labels in Batch), ``sak`` mit LF. Der Hash bleibt gleich."""
    text = data.replace(b"\r\n", b"\n")
    if path == LAUNCHER_CMD_TARGET:
        return text.replace(b"\n", b"\r\n")
    return text


def ensure_launcher_mode(target: Path) -> None:
    """Setzt das Ausführbar-Bit des POSIX-Starters (unter Windows ohne Wirkung, nicht im Lock)."""
    launcher = target / LAUNCHER_SH_TARGET
    if os.name != "nt" and launcher.is_file():
        launcher.chmod(launcher.stat().st_mode | 0o111)


def _write_action(plan: Plan, action: Action) -> None:
    destination = plan.target / action.path
    if action.kind == DELETE:
        destination.unlink(missing_ok=True)
        _prune_empty_parents(plan.target, action.path)
    elif action.kind == CONFLICT:
        assert action.content is not None
        _atomic_write(
            destination.with_name(destination.name + SAK_NEW_SUFFIX),
            _launcher_bytes(action.path, action.content),
        )
    elif action.kind in {CREATE, MERGE, REPLACE}:
        assert action.content is not None
        _atomic_write(destination, _launcher_bytes(action.path, action.content))


def _uv_executable() -> str | None:
    return os.environ.get("UV") or shutil.which("uv")


def uv_sync(target: Path) -> dict[str, Any]:
    """``uv sync --project .spec-agent/engine --locked`` (Netz nur, wenn der Cache nicht reicht)."""
    uv = _uv_executable()
    if uv is None:
        return {"ok": False, "detail": "uv wurde nicht gefunden (PATH prüfen)"}
    env = {
        k: v for k, v in os.environ.items() if k not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"}
    }
    try:
        proc = subprocess.run(
            [uv, "sync", "--project", str(target / ENGINE_TARGET), "--locked"],
            cwd=target,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=SYNC_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "detail": f"uv sync nicht ausgeführt: {exc}"}
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
        return {"ok": False, "detail": "uv sync fehlgeschlagen: " + " | ".join(tail)}
    return {"ok": True, "detail": "uv sync ausgeführt"}


def suggested_commit(plan: Plan) -> str:
    paths = ".spec-agent .claude/agents .claude/skills .claude/settings.json"
    verb = "installieren" if plan.command == "init" else "auf"
    suffix = "" if plan.command == "init" else " aktualisieren"
    return (
        f"git add {paths} && git commit -m "
        f'"chore(sak): Spec Agent Kit {verb} {plan.kit_version}{suffix}"'
    )


def apply_plan(plan: Plan, *, sync: bool = True) -> dict[str, Any]:
    """Setzt ``plan`` um und gibt den Bericht zurück; ``InstallError`` kommt vor dem Schreiben."""
    _precheck(plan)
    ordinary = [a for a in plan.actions if a.path != LOCK_TARGET]
    for action in ordinary:
        _write_action(plan, action)
    for action in plan.actions:
        if action.path == LOCK_TARGET:
            _write_action(plan, action)  # Lockfile zuletzt
    ensure_launcher_mode(plan.target)

    report: dict[str, Any] = plan.to_dict()
    report["mode"] = "applied"
    changes = plan.changes()
    report["applied"] = {
        "written": sum(1 for a in changes if a.kind in {CREATE, MERGE, REPLACE}),
        "deleted": sum(1 for a in changes if a.kind == DELETE),
        "conflicts": [a.path + SAK_NEW_SUFFIX for a in plan.conflicts],
    }
    ok = True
    if sync and (plan.target / ENGINE_TARGET / "pyproject.toml").is_file():
        report["uv_sync"] = uv_sync(plan.target)
        ok = ok and bool(report["uv_sync"]["ok"])
    else:
        report["uv_sync"] = {"ok": True, "skipped": True, "detail": "übersprungen"}
    if (plan.target / ".spec-agent" / "config.yml").is_file():
        check = check_config(plan.target)
        report["config_check"] = check
        ok = ok and bool(check["ok"])
    report["ok"] = ok
    report["suggested_commit"] = suggested_commit(plan)
    next_steps = []
    if plan.conflicts:
        next_steps.append(
            "Konflikte klären: je Datei die .sak-new-Fassung prüfen, übernehmen oder verwerfen."
        )
    next_steps.append(
        "Ergebnis prüfen (git status, git diff) und committen. Das Kit committet nie."
    )
    report["next_steps"] = next_steps
    report["text"] = [
        line.replace("(Plan)", "(angewendet)", 1) for line in plan.text()[:2]
    ] + plan.text()[2:-1]
    return report
