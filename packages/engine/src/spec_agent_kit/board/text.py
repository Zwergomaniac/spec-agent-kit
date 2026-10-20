"""Kurzfassung des Boards für das Terminal: höchstens 40 Zeilen (Port von ``render_text``)."""

from __future__ import annotations

from typing import Any, Final

from spec_agent_kit import contracts

TEXT_LINE_LIMIT: Final[int] = 40


def _label(level: str, value: str | None, locale: str) -> str:
    return contracts.label(level, value, locale) if value else "-"


def _fit(sections: list[tuple[str, list[str]]], budget: int) -> list[str]:
    """Kürzt die längsten Abschnitte, bis alles passt; Überhang wird zu „+N weitere“."""
    kept = [len(body) for _, body in sections]

    def total() -> int:
        extra = sum(1 for k, (_, body) in zip(kept, sections, strict=True) if k < len(body))
        return len(sections) + sum(kept) + extra

    while total() > budget and max(kept, default=0) > 0:
        kept[kept.index(max(kept))] -= 1
    lines: list[str] = []
    for count, (title, body) in zip(kept, sections, strict=True):
        lines.append(title)
        lines.extend(body[:count])
        if count < len(body):
            lines.append(f"  +{len(body) - count} weitere")
    return lines


def _run_lines(run: dict[str, Any], locale: str) -> list[str]:
    state = _label("run_state", run["state"], locale)
    lines = [f"  {run['spec']} · {state} · Runde {run['round']}/{run['max_rounds']}"]
    for station in run["stations"][-4:]:
        verdict = (
            f" → {_label('verdict', station.get('verdict'), locale)}"
            if station.get("verdict")
            else ""
        )
        lines.append(
            f"    {_label('role', station['role'], locale)} (Runde {station['round']}): "
            f"{station['state']}{verdict}"
        )
    return lines


def render_text(document: dict[str, Any], locale: str = "de") -> str:
    """Terminal-Text aus einem Board-Dokument, höchstens ``TEXT_LINE_LIMIT`` Zeilen."""
    metrics = document["metrics"]
    mean = metrics["mean_lead_time_days"]
    head = [
        f"Board {document['project']['name']} · Stand "
        f"{document['generated_at'][:16].replace('T', ' ')}",
        f"In Arbeit {metrics['in_progress']} · Fertig {metrics['done']} · "
        f"Blockiert {metrics['blocked']} · Wartet {metrics['waiting']} · "
        f"Ø Durchlauf {'-' if mean is None else f'{mean} Tage'}",
    ]
    waiting = [
        f"  [{_label('attention_kind', a['kind'], locale)}] {a.get('spec', '-')} - {a['reason']}"
        for a in document["attention"]
    ]
    working = [
        f"  {s['dir']} · {_label('stage', s['stage'], locale)} · "
        f"{s['tasks']['done']}/{s['tasks']['done'] + s['tasks']['open']}"
        for s in document["specs"]
        if s["stage"] == "implementing"
    ]
    finished = [
        f"  {s['dir']} · {_label('stage', s['stage'], locale)}"
        for s in document["specs"]
        if s["stage"] in {"implemented", "deployed", "verified"}
    ][:5]
    sections: list[tuple[str, list[str]]] = [
        (f"Wartet auf dich ({len(waiting)}):", waiting),
        (f"In Arbeit ({len(working)}):", working),
        ("Zuletzt fertig:", finished),
    ]
    active = [r for r in document["runs"] if r["active"]]
    if active:
        sections.append(("Läufe:", [line for r in active for line in _run_lines(r, locale)]))
    if document["notes"]:
        sections.append(("Hinweise:", [f"  {n}" for n in document["notes"]]))
    lines = head + _fit(sections, TEXT_LINE_LIMIT - len(head))
    return "\n".join(lines[:TEXT_LINE_LIMIT]) + "\n"
