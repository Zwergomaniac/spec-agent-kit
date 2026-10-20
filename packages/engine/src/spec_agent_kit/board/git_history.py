"""Ein einziger ``git log``-Durchlauf (Port der Referenzklasse ``GitHistory``, Spec 006 T002).

Liefert je Spec den ersten und letzten Commit, den letzten Commit an ``tasks.md``, die Deploy- und
Verified-Marker sowie den Ticker. Fehler führen nie zu einer Ausnahme: ``available`` ist dann
``False`` und ``error`` nennt den Grund.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final

from spec_agent_kit.pipeline import RefusedError
from spec_agent_kit.pipeline.git import run_git

TICKER_LIMIT: Final[int] = 30
RS: Final[str] = "\x1e"
US: Final[str] = "\x1f"

MARKER_RE: Final = re.compile(r"^(deploy|verified)\(([0-9][0-9,\s\-]*)\)")
"""Marker am Anfang des Commit-Betreffs: ``deploy(084,085): …``, ``verified(079-082): …``."""
SPEC_NUMBER_RE: Final = re.compile(r"\((\d{3})\b")
_SPEC_DIR_PART: Final = re.compile(r"^\d+-")
_MAX_RANGE: Final[int] = 200


def parse_marker(subject: str) -> tuple[str, list[int]] | None:
    """``verified(079-082): …`` -> ``("verified", [79, 80, 81, 82])``; sonst ``None``."""
    match = MARKER_RE.match(subject)
    if not match:
        return None
    numbers: list[int] = []
    for part in match.group(2).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            low, _, high = (p.strip() for p in part.partition("-"))
            if not (low.isdigit() and high.isdigit()):
                return None
            first, last = int(low), int(high)
            if last < first or last - first > _MAX_RANGE:
                return None
            numbers.extend(range(first, last + 1))
        elif part.isdigit():
            numbers.append(int(part))
        else:
            return None
    numbers = [n for n in dict.fromkeys(numbers) if 0 <= n <= 999]
    return (match.group(1), numbers) if numbers else None


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class MarkerCommit:
    """Ein Marker-Commit. ``seq`` ist die Position im Log (älteste zuerst)."""

    kind: str
    specs: tuple[int, ...]
    ts: str
    commit: str
    seq: int


@dataclass
class GitHistory:
    available: bool = False
    error: str = ""
    first_seen: dict[str, str] = field(default_factory=dict)
    last_touched: dict[str, str] = field(default_factory=dict)
    last_tasks: dict[str, tuple[str, int]] = field(default_factory=dict)
    """Spec-Verzeichnis -> (Zeitpunkt, Position) des letzten Commits an ``tasks.md``."""
    markers: dict[int, dict[str, tuple[str, int]]] = field(default_factory=dict)
    """Spec-Nummer -> Marker-Art -> (Zeitpunkt, Position) des jüngsten Markers."""
    marker_commits: list[MarkerCommit] = field(default_factory=list)
    """Alle Marker-Commits, neueste zuerst."""
    ticker: list[dict[str, object]] = field(default_factory=list)
    """Neueste zuerst: ``{ts, number, kind, text}``."""

    @classmethod
    def read(cls, root: Path) -> GitHistory:
        history = cls()
        try:
            proc = run_git(root, "log", "--reverse", f"--format={RS}%H{US}%cI{US}%s", "--name-only")
        except RefusedError as exc:
            history.error = exc.message
            return history
        if proc.returncode != 0:
            first = next((ln for ln in (proc.stderr or "").splitlines() if ln.strip()), "")
            history.error = f"git beendete mit Code {proc.returncode}: {first[:160]}".rstrip(": ")
            return history
        history.available = True
        entries: list[dict[str, object]] = []
        for seq, record in enumerate(r for r in proc.stdout.split(RS) if r.strip()):
            header, _, files_text = record.partition("\n")
            sha, _, rest = header.partition(US)
            ts, _, subject = rest.partition(US)
            sha, ts = sha.strip(), ts.strip()
            for path in (f for f in files_text.splitlines() if f.strip()):
                parts = path.split("/")
                if len(parts) >= 3 and parts[0] == "specs" and _SPEC_DIR_PART.match(parts[1]):
                    history.first_seen.setdefault(parts[1], ts)
                    history.last_touched[parts[1]] = ts
                    if parts[2] == "tasks.md":
                        history.last_tasks[parts[1]] = (ts, seq)
            marker = parse_marker(subject)
            if marker:
                kind, numbers = marker
                for number in numbers:
                    history.markers.setdefault(number, {})[kind] = (ts, seq)
                history.marker_commits.append(MarkerCommit(kind, tuple(numbers), ts, sha, seq))
            spec_match = SPEC_NUMBER_RE.search(subject)
            entries.append(
                {
                    "ts": ts,
                    "number": int(spec_match.group(1)) if spec_match else None,
                    "kind": marker[0] if marker else "commit",
                    "text": subject,
                }
            )
        history.ticker = list(reversed(entries))[:TICKER_LIMIT]
        history.marker_commits.reverse()
        return history
