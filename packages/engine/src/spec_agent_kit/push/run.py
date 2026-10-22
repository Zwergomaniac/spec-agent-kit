"""``sak push``: Events und Board ans Dashboard, ohne Verlust und ohne Doppelungen (Spec 006).

Ablauf je Aufruf: Sperrdatei nehmen, höchstens 3 Batches mit je höchstens 500 Events ab dem Cursor
senden, das aktuelle Board an die letzte Anfrage hängen, den Cursor nur nach einer gültigen Antwort
vorrücken. Die Pipeline wartet nie auf das Netz: Hooks starten den Push über ``spawn_background``
als losgelösten Prozess (FR-010, FR-011).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any, Final

from spec_agent_kit.board import BoardError
from spec_agent_kit.board.build import build_board
from spec_agent_kit.config import (
    AuthModeError,
    ConfigError,
    EffectiveConfig,
    NotInitializedError,
    key_source,
    load_config,
    read_dashboard_key,
    resolve_auth,
)
from spec_agent_kit.pipeline import runs
from spec_agent_kit.pipeline.events import clip
from spec_agent_kit.push import client, cloud, outbox

LOCK_FILE: Final[str] = "push.lock"
LOCK_TTL_S: Final[float] = 60.0
MAX_BATCHES: Final[int] = 3
DETACHED_PROCESS: Final[int] = 0x00000008
CREATE_NEW_PROCESS_GROUP: Final[int] = 0x00000200
CREATE_NO_WINDOW: Final[int] = 0x08000000

Poster = Callable[[str, str | None, dict[str, Any], float], dict[str, Any]]
Result = tuple[int, dict[str, Any]]


# ---------------------------------------------------------------------------
# Sperrdatei
# ---------------------------------------------------------------------------


def lock_path(root: Path) -> Path:
    return runs.state_dir(root) / LOCK_FILE


def lock_is_fresh(root: Path) -> bool:
    """``True``, wenn eine Sperre existiert, die jünger als ``LOCK_TTL_S`` ist."""
    try:
        return time.time() - lock_path(root).stat().st_mtime < LOCK_TTL_S
    except OSError:
        return False


def acquire_lock(root: Path) -> bool:
    """Legt die Sperre atomar an. Eine abgelaufene Sperre (älter als 60 s) wird übernommen."""
    path = lock_path(root)
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if lock_is_fresh(root):
                return False
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            except OSError:
                return False
            continue
        except OSError:
            return False
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(f"{os.getpid()} {runs.format_ts(runs.utcnow())}\n")
        return True
    return False


def release_lock(root: Path) -> None:
    with contextlib.suppress(OSError):
        lock_path(root).unlink()


@contextlib.contextmanager
def _locked(root: Path) -> Iterator[bool]:
    got = acquire_lock(root)
    try:
        yield got
    finally:
        if got:
            release_lock(root)


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------


def _board_hash(board: Mapping[str, Any]) -> str:
    """Hash des Boards ohne ``generated_at``: gleicher Stand, gleicher Hash."""
    stable = {k: v for k, v in board.items() if k != "generated_at"}
    text = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _is_board_error(item: Mapping[str, Any]) -> bool:
    return str(item.get("error", "")).startswith("board")


def _is_version_error(item: Mapping[str, Any]) -> bool:
    text = str(item.get("error", "")).lower()
    return not _is_board_error(item) and any(m in text for m in client.VERSION_MARKERS)


def _fail(status: str, message: str, **extra: Any) -> Result:
    return 1, {"ok": False, "status": status, "error": message, **extra}


def _remember_error(root: Path, cursor: outbox.Cursor, message: str) -> None:
    cursor.last_error = clip(message, 200)
    with contextlib.suppress(OSError):
        outbox.write_cursor(root, cursor)


def push(
    root: Path,
    *,
    env: Mapping[str, str] | None = None,
    post: Poster | None = None,
    cfg: EffectiveConfig | None = None,
) -> Result:
    """Ein Push-Aufruf. Gibt ``(Exit-Code, JSON-Antwort)`` zurück und wirft nie.

    ``post`` ersetzt den HTTP-Aufruf (Tests); ``env`` die Umgebung für den Schlüssel.
    """
    try:
        return _push(root, env=env, post=post, cfg=cfg)
    except Exception as exc:  # der Push darf nie mit einer Ausnahme enden
        return _fail("error", f"{type(exc).__name__}: {exc}")


def _push(
    root: Path,
    *,
    env: Mapping[str, str] | None,
    post: Poster | None,
    cfg: EffectiveConfig | None,
) -> Result:
    try:
        cfg = cfg or load_config(root)
    except NotInitializedError:
        return _fail("not_initialized", "nicht initialisiert: .spec-agent/config.yml fehlt")
    except ConfigError as exc:
        return _fail("invalid_config", str(exc), errors=exc.errors)
    dashboard = cfg.data["dashboard"]
    if not dashboard["url"] or dashboard["push"] == "off":
        return 0, {"ok": True, "status": "disabled", "message": "Push deaktiviert"}
    try:
        mode, _source = resolve_auth(cfg, env)
    except AuthModeError as exc:
        return _fail("invalid_auth", str(exc))
    warnings: list[str] = []
    key: str | None = None
    if mode == "proxy":
        # Proxy-Modus (Spec 013): nie ein eigener Authorization-Header, auch nicht mit Schlüssel.
        if key_source(root, cfg, env) is not None:
            warnings.append(
                "auth ist proxy: der lokale Schlüssel wird nicht gesendet "
                "(Network Secret des Proxys gilt)"
            )
    else:
        key = read_dashboard_key(root, cfg, env)
        if not key:
            return _fail(
                "no_key",
                f"Schlüssel fehlt: Umgebungsvariable {dashboard['token_env']} (token_env) oder "
                "Datei .spec-agent/dashboard.key" + cloud.proxy_mode_hint(env),
            )
    try:
        url = client.check_url(str(dashboard["url"]))
    except client.PushError as exc:
        return _fail(exc.status, exc.message)
    send = post or client.post_ingest

    with _locked(root) as got:
        if not got:
            return 0, {"ok": True, "status": "locked", "message": "ein Push läuft bereits"}
        code, outcome = _drain(root, cfg, url, key, send)
    if warnings:
        outcome["warnings"] = warnings
    return code, outcome


def _drain(root: Path, cfg: EffectiveConfig, url: str, key: str | None, send: Poster) -> Result:
    cursor = outbox.read_cursor(root)
    project = str(cfg.data["project"]["key"])
    totals = {"sent": 0, "accepted": 0, "duplicates": 0, "rejected": 0}
    board_sent = False
    board_error: str | None = None
    pending = False
    notes: list[str] = []
    batches = 0
    try:
        while batches < MAX_BATCHES:
            batch = outbox.read_batch(root, cursor)
            if batch.reset:
                cursor.offset, cursor.identity = 0, None
                notes.append("events.jsonl wurde ersetzt: Cursor zurückgesetzt")
            board: dict[str, Any] | None = None
            if not batch.has_more:
                board = _board_for_push(root, cfg, notes)
                if board is not None and _board_hash(board) == cursor.board_hash:
                    board = None
            if not batch.events and board is None:
                if batch.end_offset != cursor.offset or batch.reset or batch.skipped:
                    _advance(root, cursor, batch, None)  # nur übersprungene Zeilen
                break
            batches += 1
            payload: dict[str, Any] = {
                "schema": "sak.ingest/1",
                "project": project,
                "sent_at": runs.format_ts(runs.utcnow()),
                "events": batch.events,
            }
            if board is not None:
                payload["board"] = board
            result = send(url, key, payload, client.TIMEOUT_S)
            rejected = [r for r in result["rejected"] if isinstance(r, dict)]
            if any(_is_version_error(r) for r in rejected):
                raise client.VersionError(
                    "Dashboard kennt die Vertragsversion oder Event-Typen nicht "
                    "(Dashboard zuerst aktualisieren): " + clip(str(rejected[0].get("error")), 200)
                )
            event_rejects = [r for r in rejected if not _is_board_error(r)]
            board_rejects = [r for r in rejected if _is_board_error(r)]
            outbox.append_rejected(
                root,
                [
                    {k: str(v) for k, v in r.items() if k in {"event_id", "error"}}
                    for r in event_rejects
                ],
            )
            if board_rejects:
                board_error = clip(str(board_rejects[0].get("error")), 200)
            elif board is not None:
                cursor.board_hash = _board_hash(board)
                board_sent = True
            _advance(root, cursor, batch, result)
            totals["sent"] += len(batch.events)
            totals["accepted"] += int(result["accepted"])
            totals["duplicates"] += int(result["duplicates"])
            totals["rejected"] += len(event_rejects)
            pending = batch.has_more
            if not batch.has_more:
                break
    except client.PushError as exc:
        _remember_error(root, cursor, exc.message)
        return _fail(exc.status, exc.message, **totals, cursor_offset=cursor.offset)
    cursor.last_error = None
    cursor.last_push_at = runs.format_ts(runs.utcnow())
    outbox.write_cursor(root, cursor)
    payload_out: dict[str, Any] = {
        "ok": True,
        "status": "pushed" if (totals["sent"] or board_sent) else "up_to_date",
        **totals,
        "board_sent": board_sent,
        "pending": pending,
        "cursor_offset": cursor.offset,
    }
    if board_error:
        payload_out["board_error"] = board_error
    if cursor.skipped:
        payload_out["skipped_lines"] = cursor.skipped
    if notes:
        payload_out["notes"] = notes
    return 0, payload_out


def _advance(
    root: Path, cursor: outbox.Cursor, batch: outbox.Batch, result: dict[str, Any] | None
) -> None:
    """Rückt den Cursor hinter die verarbeitete Strecke vor (nur nach gültiger Antwort)."""
    cursor.offset = batch.end_offset
    cursor.skipped += batch.skipped
    cursor.identity = outbox.file_identity(outbox.events_path(root)) if cursor.offset else None
    outbox.write_cursor(root, cursor)


def _board_for_push(root: Path, cfg: EffectiveConfig, notes: list[str]) -> dict[str, Any] | None:
    """Das validierte Board für den Push. Bei einem Fehler gehen nur die Events raus."""
    try:
        return build_board(root, cfg)
    except BoardError as exc:
        notes.append(f"Board nicht gesendet: {exc}")
    except Exception as exc:  # das Board darf den Event-Push nie verhindern
        notes.append(f"Board nicht gesendet: {type(exc).__name__}")
    return None


# ---------------------------------------------------------------------------
# Hintergrundstart (FR-010, FR-011)
# ---------------------------------------------------------------------------


def background_command() -> list[str]:
    """Der Befehl des losgelösten Prozesses: derselbe Interpreter, ``sak push --quiet``."""
    return [sys.executable, "-m", "spec_agent_kit.cli", "push", "--quiet"]


def spawn_background(root: Path) -> bool:
    """Startet ``sak push`` losgelöst und kehrt sofort zurück.

    Windows: ``DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW``; POSIX:
    ``start_new_session``. stdin, stdout und stderr gehen nach ``DEVNULL``. Gibt ``False`` zurück,
    wenn keine Pushes gestartet wurden (Sperre frisch oder Start nicht möglich). Wirft nie.
    """
    try:
        if not sys.executable or lock_is_fresh(root):
            return False
        options: dict[str, Any] = {
            "cwd": root,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if os.name == "nt":
            options["creationflags"] = (
                DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            )
        else:
            options["start_new_session"] = True
        subprocess.Popen(background_command(), **options)
    except Exception:  # ein Fehler hier darf nie die Pipeline stören
        return False
    return True


def trigger_if_auto(root: Path | None) -> bool:
    """Löst bei ``push: auto`` mit gesetzter URL den Hintergrund-Push aus (Fehler ignoriert)."""
    if root is None:
        return False
    try:
        dashboard = load_config(root).data["dashboard"]
        if dashboard["push"] != "auto" or not dashboard["url"]:
            return False
        return spawn_background(root)
    except Exception:
        return False


def push_background(root: Path) -> Result:
    """``sak push --background``: Hintergrundprozess starten und sofort zurückkehren."""
    try:
        cfg = load_config(root)
    except NotInitializedError:
        return _fail("not_initialized", "nicht initialisiert: .spec-agent/config.yml fehlt")
    except ConfigError as exc:
        return _fail("invalid_config", str(exc), errors=exc.errors)
    dashboard = cfg.data["dashboard"]
    if not dashboard["url"] or dashboard["push"] == "off":
        return 0, {"ok": True, "status": "disabled", "message": "Push deaktiviert"}
    if lock_is_fresh(root):
        return 0, {"ok": True, "status": "locked", "message": "ein Push läuft bereits"}
    if spawn_background(root):
        return 0, {"ok": True, "status": "started"}
    return _fail("spawn_failed", "Hintergrundprozess konnte nicht gestartet werden")
