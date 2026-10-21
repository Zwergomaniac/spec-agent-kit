"""Spec-Scan: Titel, Station, Tasks, descoped, Klärung, Betreiber-Tasks (Spec 006 FR-001..003).

Gelesen werden nur die Artefakte unter ``specs/NNN-slug/`` und das Ergebnis von ``GitHistory``.
Eine unlesbare Datei führt zu einem Hinweis, nie zu einer Ausnahme.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, NamedTuple

from spec_agent_kit.board.git_history import GitHistory, parse_ts
from spec_agent_kit.pipeline.events import clip

SPEC_DIR_RE: Final = re.compile(r"^[0-9]{3}-[a-z0-9][a-z0-9-]{0,80}$")
TITLE_MAX: Final[int] = 200
_TITLE_PREFIX = re.compile(
    r"^(?:Feature Specification|Spec(?:ification)?)\s*(?:\d+)?\s*[:—-]\s*", re.I
)
_TASK_LINE = re.compile(r"^\s*(?:[-*+]|[0-9]{1,9}[.)])\s+\[( |x|X|~)\]\s*(.*)$")
_BULLET = re.compile(r"^\s*(?:[-*+]|[0-9]{1,9}[.)])\s")
_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})")
_CODE_BLOCK = re.compile(r"(```|~~~).*?(\1|\Z)", re.S)
_CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)
_NEEDS_CLARIFICATION = re.compile(r"\[NEEDS CLARIFICATION:")
_CLARIFICATIONS = re.compile(r"^##\s+(?:Clarifications?|Klärung(?:en)?)\b", re.I | re.M)
_DESCOPED = re.compile(r"^\s*\*\*Status\*\*\s*:\s*descoped\b", re.I | re.M)
_OPERATOR = re.compile(r"\[operator\]|\*\*\[Betreiber\]\*\*", re.I)
DONE_STAGES: Final[frozenset[str]] = frozenset({"implemented", "deployed", "verified"})


class TaskCounts(NamedTuple):
    """Ergebnis von ``count_tasks``: Zähler und Texte offener Betreiber-Tasks."""

    done: int
    partial: int
    open: int
    operator: list[str]


def is_finished(stage: str | None, open_: int, partial: int) -> bool:
    """„Fertig“ für die Kennzahlen: Station ab ``implemented`` UND keine offene/teilweise Task.

    Die Station bleibt ein Fakt (zum Beispiel ``deployed``); mit Resttasks gilt die Spec als in
    Arbeit (Spec 010, Clarifications).
    """
    return stage in DONE_STAGES and open_ == 0 and partial == 0


def is_in_progress(stage: str | None, open_: int, partial: int) -> bool:
    """„In Arbeit“: Station ``implementing``, oder fertige Station mit Resttasks."""
    return stage == "implementing" or (stage in DONE_STAGES and (open_ > 0 or partial > 0))


@dataclass
class SpecInfo:
    dir: str
    number: int
    title: str
    stage: str | None
    descoped: bool
    waiting: str | None
    done: int
    open: int
    started_at: str | None
    finished_at: str | None
    updated_at: str | None
    lead_time_days: float | None
    attention: list[dict[str, str]] = field(default_factory=list)
    partial: int = 0
    blocked: bool = False

    @property
    def finished(self) -> bool:
        return is_finished(self.stage, self.open, self.partial)

    @property
    def in_progress(self) -> bool:
        return is_in_progress(self.stage, self.open, self.partial)

    def to_board(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "number": self.number,
            "dir": self.dir,
            "title": self.title,
            "stage": self.stage,
            "descoped": self.descoped,
            "blocked": self.blocked,
            "waiting": self.waiting,
            "tasks": {"done": self.done, "open": self.open},
        }
        if self.partial:
            item["tasks"]["partial"] = self.partial
        for key in ("started_at", "finished_at", "updated_at", "lead_time_days"):
            value = getattr(self, key)
            if value is not None:
                item[key] = value
        return item


def strip_code(text: str) -> str:
    """Entfernt Codeblöcke und Code-Spans, damit darin genannte Marker nicht zählen."""
    return _CODE_SPAN.sub("", _CODE_BLOCK.sub("", text))


def has_open_clarification(spec_text: str) -> bool:
    return _NEEDS_CLARIFICATION.search(strip_code(spec_text)) is not None


def is_descoped(spec_text: str) -> bool:
    """``**Status**: Descoped`` im Kopf (vor der ersten ``## ``-Überschrift), ohne Groß/Klein."""
    head = re.split(r"^##\s", spec_text, maxsplit=1, flags=re.M)[0]
    return _DESCOPED.search(head) is not None


def _split_code_spans(text: str) -> list[tuple[str, bool]]:
    """Zerlegt ``text`` in ``(Teil, ist_code_span)``; die Teile ergeben zusammen wieder ``text``."""
    parts: list[tuple[str, bool]] = []
    position = 0
    for match in _CODE_SPAN.finditer(text):
        if match.start() > position:
            parts.append((text[position : match.start()], False))
        parts.append((match.group(0), True))
        position = match.end()
    if position < len(text):
        parts.append((text[position:], False))
    return parts


def has_operator_marker(text: str) -> bool:
    """Betreiber-Marker außerhalb von Code-Spans."""
    return any(_OPERATOR.search(part) for part, code in _split_code_spans(text) if not code)


def remove_operator_marker(text: str) -> str:
    """Entfernt den Marker außerhalb von Code-Spans; Code-Spans bleiben im Text erhalten."""
    joined = "".join(
        part if code else _OPERATOR.sub("", part) for part, code in _split_code_spans(text)
    )
    return " ".join(joined.split())


def count_tasks(tasks_text: str) -> TaskCounts:
    """Zählt Tasks in ``tasks.md`` nach den Board-Ableitungsregeln (Spec 010 FR-007).

    Task-Zeile: Aufzählung (``-``, ``*``, ``+``, nummeriert; auch eingerückt) mit Checkbox
    ``[ ]``, ``[x]``, ``[X]`` oder ``[~]``. Ein Codeblock beginnt nur mit einem Fence am
    Zeilenanfang (höchstens 3 Leerzeichen Einrückung), der nicht zu einer Aufzählung gehört; Zeilen
    in Codeblöcken zählen nicht.
    """
    done = partial = open_ = 0
    operator: list[str] = []
    fence: str | None = None  # Zeichen und Länge des öffnenden Fence
    in_list = False
    for line in tasks_text.splitlines():
        fence_match = _FENCE.match(line)
        if fence is not None:
            closes = (
                fence_match is not None
                and fence_match.group(2)[0] == fence[0]
                and len(fence_match.group(2)) >= len(fence)
                and not line[fence_match.end() :].strip()
            )
            if closes:
                fence = None
            continue
        if fence_match and not (in_list and fence_match.group(1)):
            fence = fence_match.group(2)
            in_list = False
            continue
        stripped = line.strip()
        if _BULLET.match(line):
            in_list = True
        elif stripped and line == line.lstrip():
            in_list = False  # unabgesetzte Zeile ohne Aufzählung beendet die Aufzählung
        match = _TASK_LINE.match(line)
        if not match:
            continue
        mark, text = match.group(1), match.group(2)
        if mark == " ":
            open_ += 1
            if has_operator_marker(text):
                shown = remove_operator_marker(text)
                operator.append(shown or text.strip())
        elif mark == "~":
            partial += 1
        else:
            done += 1
    return TaskCounts(done, partial, open_, operator)


def title_of(spec_text: str, directory: str) -> str:
    for line in spec_text.splitlines():
        if line.startswith("# "):
            title = _TITLE_PREFIX.sub("", line[2:].strip()).strip()
            if title:
                return clip(title, TITLE_MAX)
    return clip(directory.split("-", 1)[1].replace("-", " "), TITLE_MAX)


def _read(path: Path, notes: list[str]) -> str | None:
    """Text einer Datei; ``None`` ohne Datei, ``None`` plus Hinweis bei Lesefehlern."""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        notes.append(
            clip(f"{path.parent.name}/{path.name} nicht lesbar ({type(exc).__name__})", 280)
        )
        return None


def station(
    *,
    has_spec: bool,
    clarified: bool,
    has_plan: bool,
    has_tasks: bool,
    done: int,
    open_: int,
    descoped: bool,
    partial: int = 0,
    deploy: tuple[str, int] | None,
    verified: tuple[str, int] | None,
    last_tasks: tuple[str, int] | None,
    stages: dict[str, bool],
) -> str | None:
    """Spec-Station nach Spec 001 FR-006: die höchste zutreffende Bedingung gewinnt.

    ``[~]``-Tasks (``partial``) zählen als begonnen, aber nicht als erledigt: Mit ihnen ist die
    Umsetzung nicht fertig. Ein Deploy-Marker zählt nur, wenn er nach (oder mit) dem letzten Commit
    an ``tasks.md`` liegt. Abgeschaltete Stationen (``stages``) werden nie vergeben.
    """
    if descoped or not has_spec:
        return None
    if stages.get("verified", True) and verified is not None:
        return "verified"
    deploy_counts = deploy is not None and (last_tasks is None or deploy[1] >= last_tasks[1])
    if stages.get("deployed", True) and deploy_counts:
        return "deployed"
    if has_tasks and done > 0 and open_ == 0 and partial == 0:
        return "implemented"
    if has_tasks and done + partial > 0:
        return "implementing"
    if has_tasks:
        return "tasked"
    if has_plan:
        return "planned"
    if clarified:
        return "clarified"
    return "specified"


def _days(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    try:
        return round(max(0.0, (parse_ts(end) - parse_ts(start)).total_seconds() / 86400), 1)
    except ValueError:
        return None


def recency_key(info: SpecInfo) -> tuple[float, str]:
    """Sortierung „neueste zuerst“ (mit ``reverse=True``): letzter Commit, dann höhere Nummer."""
    stamp = info.updated_at or info.finished_at or info.started_at
    try:
        seconds = parse_ts(stamp).timestamp() if stamp else 0.0
    except ValueError:
        seconds = 0.0
    return (seconds, info.dir)


def scan_specs(
    root: Path,
    history: GitHistory,
    stages: dict[str, bool],
    started_specs: set[str],
    notes: list[str],
    extra_descoped: frozenset[str] = frozenset(),
) -> list[SpecInfo]:
    """Alle Specs, neueste zuerst. ``started_specs``: Specs, für die je ein Lauf existierte.

    ``extra_descoped``: Spec-Verzeichnisse, die ein Plugin als zurückgestellt meldet (zusätzlich zu
    ``**Status**: Descoped`` in der spec.md).
    """
    base = root / "specs"
    if not base.is_dir():
        return []
    infos: list[SpecInfo] = []
    for directory in sorted(p for p in base.iterdir() if p.is_dir() and SPEC_DIR_RE.match(p.name)):
        name = directory.name
        spec_text = _read(directory / "spec.md", notes)
        tasks_text = _read(directory / "tasks.md", notes)
        has_spec = (directory / "spec.md").is_file()
        has_plan = (directory / "plan.md").is_file()
        has_tasks = (directory / "tasks.md").is_file()
        if not (has_spec or has_plan or has_tasks):
            continue
        number = int(name[:3])
        done, partial, open_, operator_tasks = count_tasks(tasks_text or "")
        descoped = is_descoped(spec_text or "") or name in extra_descoped
        clarification_open = has_open_clarification(spec_text or "") and not descoped
        marks = history.markers.get(number, {})
        stage = station(
            has_spec=has_spec,
            clarified=bool(_CLARIFICATIONS.search(spec_text or "")),
            has_plan=has_plan,
            has_tasks=has_tasks,
            done=done,
            open_=open_,
            partial=partial,
            descoped=descoped,
            deploy=marks.get("deploy"),
            verified=marks.get("verified"),
            last_tasks=history.last_tasks.get(name),
            stages=stages,
        )
        attention: list[dict[str, str]] = []
        waiting: str | None = None
        if clarification_open:
            waiting = "clarification"
            attention.append(
                {
                    "kind": "clarification",
                    "spec": name,
                    "reason": "Klärung offen: spec.md enthält unbeantwortete Fragen",
                    "source": "spec.md",
                }
            )
        elif (
            not descoped
            and has_tasks
            and done == 0
            and partial == 0
            and open_ > 0
            and name not in started_specs
        ):
            # Spec 006 FR-003: Tasks vorhanden, 0 erledigt, nie ein Lauf gestartet. Eine Taskliste
            # ohne Tasks (0/0) hat nichts, das freigegeben werden könnte (Spec 001, Randfälle).
            waiting = "approval"
            attention.append(
                {
                    "kind": "approval",
                    "spec": name,
                    "reason": "Tasks fertig, wartet auf Freigabe zur Umsetzung",
                    "source": "tasks.md",
                }
            )
        if not descoped:
            for text in operator_tasks:
                attention.append(
                    {
                        "kind": "operator_task",
                        "spec": name,
                        "reason": clip(text, 300),
                        "source": "tasks.md",
                    }
                )
        started = history.first_seen.get(name)
        finished: str | None = None
        lead: float | None = None
        if is_finished(stage, open_, partial):
            verified_mark = marks.get("verified") if stages.get("verified", True) else None
            last_tasks = history.last_tasks.get(name)
            finished = (
                verified_mark[0] if verified_mark else (last_tasks[0] if last_tasks else None)
            )
            lead = _days(started, finished)
        infos.append(
            SpecInfo(
                dir=name,
                number=number,
                title=title_of(spec_text or "", name),
                stage=stage,
                descoped=descoped,
                waiting=waiting,
                done=done,
                open=open_,
                partial=partial,
                started_at=started,
                finished_at=finished,
                updated_at=history.last_touched.get(name),
                lead_time_days=lead,
                attention=attention,
            )
        )
    infos.sort(key=recency_key, reverse=True)
    return infos
