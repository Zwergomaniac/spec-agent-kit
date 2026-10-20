"""Pilotfälle aus ImmoAgent als End-to-End-Tests mit Fixture-Repo (Spec 003 SC-003, T018).

- 066: zwei Runden, am Ende gemergt.
- 084/085: Eskalation (Mensch prüft; geschützter Pfad ohne Prüfer), Betreiber pausiert.
- 088: Unterbrechung durch ein API-Limit, Pause, Fortsetzen, Abschluss.

Ein Skript spielt die Befehle des Orchestrators mit vorgefertigten Prüfer-Antworten durch.
"""

from __future__ import annotations

import json

from conftest import APPROVE, CHANGES, HUMAN, Repo


def station(repo: Repo, phase: str, agent: str) -> None:
    code, _ = repo.sak("hook", f"subagent-{phase}", stdin=json.dumps({"agent_type": agent}))
    assert code == 0


def build(repo: Repo, rel: str, content: str) -> None:
    station(repo, "start", "sak-builder")
    repo.write(rel, content)
    repo.commit(f"feat: {rel}")
    station(repo, "stop", "sak-builder")


def review_round(repo: Repo, run_id: str, code_text: str, ui_text: str) -> dict[str, object]:
    """Wächter, Snapshot, beide Prüfer parallel gestartet, Integritätsprüfung, Urteile, combine."""
    code, out = repo.sak("run", "state", run_id, "reviewing")
    assert code == 0, out
    _, guard = repo.sak("run", "guard", run_id)
    assert guard["escalate"] is False
    _, snap = repo.sak("run", "snapshot")
    for agent in ("sak-code-reviewer", "sak-ui-reviewer"):
        station(repo, "start", agent)
    for agent in ("sak-code-reviewer", "sak-ui-reviewer"):
        station(repo, "stop", agent)
    code, out = repo.sak("run", "reviewer-check", snap["snapshot"])
    assert code == 0, out
    repo.verdict(run_id, "code_review", code_text, "code.md")
    repo.verdict(run_id, "ui_review", ui_text, "ui.md")
    code, combined = repo.sak("run", "combine", run_id)
    assert code == 0, combined
    return combined


def test_066_two_rounds_then_merged(repo: Repo) -> None:
    repo.add_spec("066-chat")
    run_id = repo.start("066")
    build(repo, "src/chat.py", "v = 1\n")

    first = review_round(repo, run_id, APPROVE, CHANGES)
    assert first["state"] == "building" and first["round"] == 2
    assert first["must"] == ["[ui_review] web/style.css:880 — Überlauf → min-width entfernen"]

    build(repo, "web/style.css", ".a { min-width: 0 }\n")
    second = review_round(repo, run_id, APPROVE, APPROVE)
    assert second["state"] == "approved"

    code, merged = repo.sak("run", "merge", run_id)
    assert code == 0, merged
    assert merged["state"] == "merged"
    assert repo.types(run_id) == [
        "run.started",
        "round.started",
        "station.started",
        "station.finished",
        "station.started",
        "station.started",
        "station.finished",
        "station.finished",
        "verdict.recorded",
        "verdict.recorded",
        "round.started",
        "station.started",
        "station.finished",
        "station.started",
        "station.started",
        "station.finished",
        "station.finished",
        "verdict.recorded",
        "verdict.recorded",
        "run.approved",
        "run.merged",
    ]
    events = repo.events(run_id)
    assert len({e["event_id"] for e in events}) == len(events)
    assert {e["project"] for e in events} == {"demo"}
    assert repo.branch() == "main"
    assert (repo.path / "web/style.css").is_file()


def test_084_needs_human_escalates_and_the_operator_pauses(repo: Repo) -> None:
    repo.add_spec("084-migration")
    run_id = repo.start("084")
    build(repo, "src/migrate.py", "m = 1\n")
    result = review_round(repo, run_id, HUMAN, APPROVE)
    assert result["state"] == "escalated" and result["verdict"] == "needs_human"

    code, out = repo.sak("run", "pause", run_id, "--reason", "Betreiber prüft morgen")
    assert code == 0 and out["paused_from"] == "escalated"
    _, listed = repo.sak("run", "list")
    assert [r["state"] for r in listed["runs"]] == ["paused"]

    repo.git("switch", "-q", "main")
    repo.add_spec("085-other")
    other = repo.start("085")  # die Sperre ist frei
    repo.sak("run", "abort", other)

    code, out = repo.sak("run", "resume", run_id)
    assert code == 0 and out["state"] == "escalated" and repo.branch() == "084-migration"
    code, out = repo.sak("run", "release", run_id, "--reason", "Migration geprüft")
    assert code == 0 and out["state"] == "approved"
    assert repo.types(run_id)[-4:] == [
        "run.escalated",
        "run.paused",
        "run.resumed",
        "run.released",
    ]


def test_085_protected_path_escalates_before_any_reviewer(repo: Repo) -> None:
    repo.add_spec("085-guard")
    run_id = repo.start("085")
    build(repo, ".claude/settings.json", "{}\n")
    repo.sak("run", "state", run_id, "reviewing")
    _, guard = repo.sak("run", "guard", run_id)
    assert guard["escalate"] is True and guard["gate"] == "protected_paths"
    code, out = repo.sak(
        "run",
        "state",
        run_id,
        "escalated",
        "--gate",
        guard["gate"],
        "--reason",
        f"{guard['reason']}: {', '.join(guard['protected_hits'])}",
    )
    assert code == 0 and out["state"] == "escalated"
    assert "verdict.recorded" not in repo.types(run_id)
    escalated = repo.events(run_id)[-1]
    assert escalated["data"]["gate"] == "protected_paths"
    assert ".claude/settings.json" in escalated["data"]["reason"]


def test_088_api_limit_pause_resume_and_finish(repo: Repo) -> None:
    repo.add_spec("088-limit")
    run_id = repo.start("088")
    station(repo, "start", "sak-builder")
    repo.write("src/part1.py", "p = 1\n")
    repo.commit("feat: part 1")

    code, out = repo.sak("run", "pause", run_id, "--reason", "API-Limit erreicht")
    assert code == 0 and out["state"] == "paused"
    repo.git("switch", "-q", "main")

    code, out = repo.sak("run", "resume", "088")
    assert code == 0 and out["state"] == "building" and repo.branch() == "088-limit"
    build(repo, "src/part2.py", "p = 2\n")

    result = review_round(repo, run_id, APPROVE, APPROVE)
    assert result["state"] == "approved"
    code, merged = repo.sak("run", "merge", run_id)
    assert code == 0 and merged["state"] == "merged"
    types = repo.types(run_id)
    assert types[:2] == ["run.started", "round.started"]
    assert "run.paused" in types and "run.resumed" in types and types[-1] == "run.merged"
    assert types.index("run.paused") < types.index("run.resumed")
    paused = next(e for e in repo.events(run_id) if e["type"] == "run.paused")
    assert paused["data"] == {"reason": "API-Limit erreicht"}
