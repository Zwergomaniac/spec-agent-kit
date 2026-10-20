"""Outbox: Cursor, Lesen ab Offset, defekte Zeilen (Spec 006 FR-009).

Die Outbox ist ``events.jsonl`` selbst. Der Cursor (``push-cursor.json``) merkt sich den
Byte-Offset hinter der letzten verarbeiteten Zeile und die Identität der Datei (Hash ihrer
ersten vollständigen Zeile). Eine Zeile gilt erst als gelesen, wenn sie mit einem Zeilenumbruch
endet; eine halbe Zeile am Dateiende wartet. So wird keine Zeile doppelt gesendet.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

from spec_agent_kit import contracts
from spec_agent_kit.pipeline import runs
from spec_agent_kit.pipeline.events import events_path

CURSOR_FILE: Final[str] = "push-cursor.json"
REJECTED_FILE: Final[str] = "push-rejected.jsonl"
BATCH_MAX_EVENTS: Final[int] = contracts.LIMITS["INGEST_MAX_EVENTS"]
BATCH_MAX_BYTES: Final[int] = 1_200_000
"""Anfrage ≤ 2 MB: 1,2 MB Events plus höchstens 512 KB Board bleiben darunter."""
_IDENTITY_PEEK: Final[int] = 4096


@dataclass
class Cursor:
    offset: int = 0
    identity: str | None = None
    skipped: int = 0
    """Insgesamt übersprungene defekte oder ungültige Zeilen (für den Hinweis im Board)."""
    board_hash: str | None = None
    last_error: str | None = None
    last_push_at: str | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_json(self) -> str:
        data = asdict(self)
        data.pop("extra", None)
        return json.dumps(data, indent=2) + "\n"


@dataclass
class Batch:
    events: list[dict[str, Any]]
    end_offset: int
    skipped: int
    reset: bool
    has_more: bool


def cursor_path(root: Path) -> Path:
    return runs.state_dir(root) / CURSOR_FILE


def rejected_path(root: Path) -> Path:
    return runs.state_dir(root) / REJECTED_FILE


def read_cursor(root: Path) -> Cursor:
    """Liest den Cursor. Fehlt er oder ist er defekt, beginnt er bei 0 (Dashboard dedupliziert)."""
    loaded = runs.read_json_file(cursor_path(root))
    cursor = Cursor()
    offset = loaded.get("offset")
    if isinstance(offset, int) and offset >= 0:
        cursor.offset = offset
    for key in ("identity", "board_hash", "last_error", "last_push_at"):
        value = loaded.get(key)
        if isinstance(value, str) and value:
            setattr(cursor, key, value)
    skipped = loaded.get("skipped")
    if isinstance(skipped, int) and skipped >= 0:
        cursor.skipped = skipped
    return cursor


def write_cursor(root: Path, cursor: Cursor) -> None:
    runs.write_text_atomic(cursor_path(root), cursor.to_json())


def file_identity(path: Path) -> str | None:
    """Hash der ersten vollständigen Zeile; ``None``, solange es keine gibt."""
    try:
        with path.open("rb") as handle:
            head = handle.read(_IDENTITY_PEEK)
    except OSError:
        return None
    newline = head.find(b"\n")
    if newline < 0:
        return None
    return hashlib.sha256(head[:newline]).hexdigest()[:16]


def read_batch(root: Path, cursor: Cursor) -> Batch:
    """Die nächsten gültigen Events ab dem Cursor (höchstens 500 und höchstens ``BATCH_MAX_BYTES``).

    Setzt den Cursor zurück, wenn die Datei kleiner als der Offset ist oder eine andere Identität
    hat (sie wurde ersetzt). Defekte oder vertragswidrige Zeilen werden übersprungen und gezählt.
    """
    path = events_path(root)
    try:
        size = path.stat().st_size
    except OSError:
        return Batch([], cursor.offset, 0, False, False)
    reset = False
    offset = cursor.offset
    if offset > size or (offset > 0 and cursor.identity and file_identity(path) != cursor.identity):
        offset, reset = 0, True
    events: list[dict[str, Any]] = []
    skipped = 0
    total = 0
    position = offset
    has_more = False
    with path.open("rb") as handle:
        handle.seek(offset)
        while True:
            raw = handle.readline()
            if not raw or not raw.endswith(b"\n"):
                break  # Dateiende oder eine halbe Zeile, die noch geschrieben wird
            line = raw.strip()
            event: dict[str, Any] | None = None
            if line:
                try:
                    loaded = json.loads(line.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    loaded = None
                if isinstance(loaded, dict) and not contracts.validate_event(loaded):
                    event = loaded
                else:
                    skipped += 1
            size_of = contracts.serialized_size(event) if event is not None else 0
            if (
                event is not None
                and events
                and (len(events) >= BATCH_MAX_EVENTS or total + size_of > BATCH_MAX_BYTES)
            ):
                has_more = True
                break
            position += len(raw)
            if event is not None:
                events.append(event)
                total += size_of
    return Batch(
        events=events,
        end_offset=position,
        skipped=skipped,
        reset=reset,
        has_more=has_more,
    )


def append_rejected(root: Path, entries: list[dict[str, str]]) -> None:
    """Hängt abgelehnte Events (nur ID und Grund, nie der Inhalt) an ``push-rejected.jsonl``."""
    if not entries:
        return
    path = rejected_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = runs.format_ts(runs.utcnow())
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for entry in entries:
            record = {"ts": stamp, **entry}
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()


def count_rejected(root: Path) -> int:
    path = rejected_path(root)
    try:
        with path.open("rb") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0
