"""Zustandsmaschine (Spec 001 FR-010 bis FR-013, Spec 003 FR-004).

``plan_transition`` prüft einen Übergang gegen die Tabelle, ändert den Lauf im Speicher und liefert
die Events, die dazu gehören. Das Schreiben übernimmt der Aufrufer.
"""

from __future__ import annotations

from typing import Any, Final

from spec_agent_kit.pipeline import RefusedError
from spec_agent_kit.pipeline.events import clip

TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "building": frozenset({"reviewing", "escalated", "paused", "aborted"}),
    "reviewing": frozenset({"building", "approved", "escalated", "reviewed", "paused", "aborted"}),
    "approved": frozenset({"merged", "escalated", "aborted"}),
    "escalated": frozenset({"approved", "building", "paused", "aborted"}),
    # Lesart: Ein aus `escalated` pausierter Lauf kehrt nach `escalated` zurück (Zustand vor der
    # Pause, Spec 003 US3); die Eskalation bleibt offen. Spec 001 FR-011 nennt nur building und
    # reviewing.
    "paused": frozenset({"building", "reviewing", "escalated", "aborted"}),
    "merged": frozenset(),
    "reviewed": frozenset(),
    "aborted": frozenset(),
}

Event = tuple[str, dict[str, Any]]


def plan_transition(
    run: dict[str, Any],
    new: str,
    *,
    reason: str | None = None,
    gate: str | None = None,
    merge_commit: str | None = None,
    takeover: bool = False,
) -> list[Event]:
    """Setzt ``run`` auf ``new`` und gibt die zugehörigen Events ``(type, data)`` zurück.

    Wirft ``RefusedError`` bei unerlaubten Übergängen. ``run`` bleibt dann unverändert.
    """
    old = run["state"]
    if new not in TRANSITIONS:
        raise RefusedError(f"unbekannter Zustand: {new}")
    if new not in TRANSITIONS[old]:
        raise RefusedError(f"Übergang {old} → {new} nicht erlaubt")
    kind = run.get("kind", "pipeline")
    if new == "reviewed" and kind != "review_only":
        raise RefusedError("reviewed ist nur für Nur-Prüfung-Läufe möglich")
    if kind == "review_only" and old == "reviewing" and new in {"building", "approved"}:
        raise RefusedError("ein Nur-Prüfung-Lauf hat keinen Builder und endet mit reviewed")
    if new == "escalated" and old != "paused" and not reason:
        raise RefusedError("escalated braucht --reason")
    shown = clip(reason) if reason else None
    events: list[Event] = []

    if old == "paused" and new != "aborted":
        events.append(("run.resumed", {}))
        run["paused_from"] = None
    elif new == "building":
        if run["round"] >= run["max_rounds"]:
            raise RefusedError(
                f"Runde {run['round']} war die letzte (max_rounds {run['max_rounds']})"
            )
        if old == "escalated":
            events.append(("run.returned", {"reason": shown}))
        run["round"] += 1
        events.append(("round.started", {"round": run["round"]}))
    elif new == "escalated":
        run["escalation"] = {"reason": shown, "gate": gate, "round": run["round"]}
        events.append(("run.escalated", {"round": run["round"], "gate": gate, "reason": shown}))
    elif new == "paused":
        run["paused_from"] = old
        events.append(("run.paused", {"reason": shown}))
    elif new == "approved":
        if old == "escalated":
            events.append(("run.released", {"reason": shown}))
        else:
            events.append(("run.approved", {}))
    elif new == "merged":
        events.append(("run.merged", {"merge_commit": merge_commit}))
    elif new == "reviewed":
        events.append(("run.reviewed", {}))
    elif takeover:  # new == "aborted"
        events.append(("run.taken_over", {"reason": shown, "previous_state": old}))
    else:
        events.append(("run.aborted", {"reason": shown}))

    if old == "escalated" and new in {"approved", "building", "aborted"}:
        run["escalation"] = None
    run["state"] = new
    return events
