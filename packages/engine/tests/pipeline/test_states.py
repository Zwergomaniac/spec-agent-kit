"""Übergangstabelle (Spec 001 FR-011) und Events je Übergang (Spec 003 FR-004)."""

from __future__ import annotations

from typing import Any

import pytest

from spec_agent_kit import contracts
from spec_agent_kit.pipeline import RefusedError
from spec_agent_kit.pipeline.states import TRANSITIONS, plan_transition


def make_run(state: str, *, rnd: int = 1, kind: str = "pipeline") -> dict[str, Any]:
    return {
        "run_id": "001-20261020-100000",
        "spec": "001-demo",
        "kind": kind,
        "state": state,
        "round": rnd,
        "max_rounds": 2,
        "paused_from": None,
        "escalation": None,
    }


def test_table_uses_only_vocabulary_states() -> None:
    states = set(contracts.vocabulary()["run_state"])
    assert set(TRANSITIONS) == states
    for targets in TRANSITIONS.values():
        assert targets <= states


@pytest.mark.parametrize("terminal", ["merged", "reviewed", "aborted"])
def test_terminal_states_have_no_transitions(terminal: str) -> None:
    assert TRANSITIONS[terminal] == frozenset()


def test_spec_001_transitions_are_present() -> None:
    assert {"reviewing", "escalated", "paused", "aborted"} == TRANSITIONS["building"]
    assert {"building", "approved", "escalated", "reviewed", "paused", "aborted"} == (
        TRANSITIONS["reviewing"]
    )
    assert {"merged", "escalated", "aborted"} == TRANSITIONS["approved"]
    assert {"approved", "building", "paused", "aborted"} == TRANSITIONS["escalated"]
    assert {"building", "reviewing", "aborted"} <= TRANSITIONS["paused"]


def test_approved_cannot_pause() -> None:
    with pytest.raises(RefusedError, match="nicht erlaubt"):
        plan_transition(make_run("approved"), "paused")


@pytest.mark.parametrize(
    ("old", "new", "kwargs", "expected"),
    [
        ("building", "reviewing", {}, []),
        ("reviewing", "approved", {}, ["run.approved"]),
        ("escalated", "approved", {}, ["run.released"]),
        ("reviewing", "building", {}, ["round.started"]),
        ("escalated", "building", {"reason": "weiter"}, ["run.returned", "round.started"]),
        ("building", "escalated", {"reason": "x", "gate": "round_limit"}, ["run.escalated"]),
        ("building", "paused", {"reason": "Limit"}, ["run.paused"]),
        ("paused", "building", {}, ["run.resumed"]),
        ("paused", "aborted", {}, ["run.aborted"]),
        ("building", "aborted", {}, ["run.aborted"]),
        ("approved", "merged", {}, ["run.merged"]),
    ],
)
def test_events_per_transition(
    old: str, new: str, kwargs: dict[str, str], expected: list[str]
) -> None:
    run = make_run(old)
    if old == "paused":
        run["paused_from"] = "building"
    events = plan_transition(run, new, **kwargs)
    assert [e[0] for e in events] == expected
    assert run["state"] == new


def test_pause_remembers_state_and_resume_clears_it() -> None:
    run = make_run("reviewing")
    plan_transition(run, "paused")
    assert run["paused_from"] == "reviewing"
    plan_transition(run, "reviewing")
    assert run["paused_from"] is None


def test_escalated_run_keeps_escalation_over_pause() -> None:
    run = make_run("building")
    plan_transition(run, "escalated", reason="Grund", gate="protected_paths")
    assert run["escalation"] == {"reason": "Grund", "gate": "protected_paths", "round": 1}
    plan_transition(run, "paused")
    assert run["escalation"] is not None
    plan_transition(run, "escalated")
    assert run["escalation"] is not None
    plan_transition(run, "aborted")
    assert run["escalation"] is None


def test_failed_transition_leaves_run_unchanged() -> None:
    run = make_run("building", rnd=2)
    with pytest.raises(RefusedError, match="nicht erlaubt"):
        plan_transition(run, "merged")
    assert run["state"] == "building" and run["round"] == 2


def test_round_limit_blocks_next_round() -> None:
    run = make_run("reviewing", rnd=2)
    with pytest.raises(RefusedError, match="max_rounds"):
        plan_transition(run, "building")


def test_takeover_writes_taken_over_event() -> None:
    run = make_run("reviewing")
    events = plan_transition(run, "aborted", reason="Sitzung tot", takeover=True)
    assert events == [("run.taken_over", {"reason": "Sitzung tot", "previous_state": "reviewing"})]


def test_review_only_rules() -> None:
    run = make_run("reviewing", kind="review_only")
    with pytest.raises(RefusedError, match="keinen Builder"):
        plan_transition(run, "building")
    with pytest.raises(RefusedError, match="keinen Builder"):
        plan_transition(run, "approved")
    assert plan_transition(run, "reviewed") == [("run.reviewed", {})]
    with pytest.raises(RefusedError, match="nur für Nur-Prüfung"):
        plan_transition(make_run("reviewing"), "reviewed")
