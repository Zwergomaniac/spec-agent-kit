"""combine: Gesamturteil, Rundenlimit, Muss-Befunde (Spec 003 FR-010, US1)."""

from __future__ import annotations

from conftest import APPROVE, CHANGES, HUMAN, Repo


def reviewing(repo: Repo) -> str:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    return run_id


def test_two_approvals_approve_the_run(repo: Repo) -> None:
    run_id = reviewing(repo)
    repo.verdict(run_id, "code_review", APPROVE, "a.md")
    repo.verdict(run_id, "ui_review", APPROVE, "b.md")
    code, out = repo.sak("run", "combine", run_id)
    assert code == 0 and out["verdict"] == "approve" and out["state"] == "approved"
    assert repo.types(run_id)[-1] == "run.approved"


def test_changes_requested_starts_round_two_with_verbatim_findings(repo: Repo) -> None:
    run_id = reviewing(repo)
    repo.verdict(run_id, "code_review", APPROVE, "a.md")
    repo.verdict(run_id, "ui_review", CHANGES, "b.md")
    _, out = repo.sak("run", "combine", run_id)
    assert out["state"] == "building" and out["round"] == 2 and out["judged_round"] == 1
    assert out["must"] == ["[ui_review] web/style.css:880 — Überlauf → min-width entfernen"]
    assert repo.types(run_id)[-1] == "round.started"
    assert repo.events(run_id)[-1]["data"] == {"round": 2}


def test_changes_requested_in_the_last_round_escalates_with_round_limit(repo: Repo) -> None:
    run_id = reviewing(repo)
    repo.verdict(run_id, "code_review", CHANGES, "a.md")
    repo.verdict(run_id, "ui_review", APPROVE, "b.md")
    repo.sak("run", "combine", run_id)
    repo.sak("run", "state", run_id, "reviewing")
    repo.verdict(run_id, "code_review", CHANGES, "c.md")
    repo.verdict(run_id, "ui_review", CHANGES, "d.md")
    _, out = repo.sak("run", "combine", run_id)
    assert out["state"] == "escalated"
    escalated = repo.events(run_id)[-1]
    assert escalated["type"] == "run.escalated" and escalated["data"]["gate"] == "round_limit"
    assert escalated["data"]["round"] == 2
    assert repo.run_json(run_id)["escalation"]["gate"] == "round_limit"


def test_needs_human_escalates_with_the_reasons(repo: Repo) -> None:
    run_id = reviewing(repo)
    repo.verdict(run_id, "code_review", HUMAN, "a.md")
    repo.verdict(run_id, "ui_review", APPROVE, "b.md")
    _, out = repo.sak("run", "combine", run_id)
    assert out["verdict"] == "needs_human" and out["state"] == "escalated"
    assert out["reasons"] == ["[code_review] Migration auf Bestandsdaten"]
    escalated = repo.events(run_id)[-1]
    assert "Migration auf Bestandsdaten" in escalated["data"]["reason"]
    assert "gate" not in escalated["data"]


def test_missing_verdict_of_an_active_role_is_rejected(repo: Repo) -> None:
    run_id = reviewing(repo)
    repo.verdict(run_id, "ui_review", APPROVE, "b.md")
    code, out = repo.sak("run", "combine", run_id)
    assert code == 1 and out["missing"] == ["code_review"]
    assert repo.run_json(run_id)["state"] == "reviewing"


def test_only_active_roles_count(repo: Repo) -> None:
    repo.set_config(pipeline={"roles": {"ui_review": {"enabled": False}}}, ui=None)
    run_id = reviewing(repo)
    repo.verdict(run_id, "code_review", APPROVE)
    code, out = repo.sak("run", "combine", run_id)
    assert code == 0 and out["state"] == "approved"


def test_extra_review_role_counts_when_active(repo: Repo) -> None:
    repo.write(
        ".claude/agents/sak-security-reviewer.md",
        "---\nname: sak-security-reviewer\nmodel: opus\neffort: medium\n---\nx\n",
    )
    repo.set_config(pipeline={"roles": {"security_review": {"enabled": True}}})
    run_id = reviewing(repo)
    repo.verdict(run_id, "code_review", APPROVE, "a.md")
    repo.verdict(run_id, "ui_review", APPROVE, "b.md")
    code, out = repo.sak("run", "combine", run_id)
    assert code == 1 and out["missing"] == ["security_review"]
    repo.verdict(run_id, "security_review", HUMAN, "c.md")
    _, out = repo.sak("run", "combine", run_id)
    assert out["verdict"] == "needs_human"


def test_combine_outside_reviewing_is_rejected(repo: Repo) -> None:
    run_id = repo.start()
    code, out = repo.sak("run", "combine", run_id)
    assert code == 1 and "reviewing" in out["error"]


def test_max_rounds_one_escalates_immediately(repo: Repo) -> None:
    repo.set_config(pipeline={"max_rounds": 1})
    run_id = reviewing(repo)
    repo.verdict(run_id, "code_review", CHANGES, "a.md")
    repo.verdict(run_id, "ui_review", APPROVE, "b.md")
    _, out = repo.sak("run", "combine", run_id)
    assert out["state"] == "escalated"


def test_return_and_release_after_escalation(repo: Repo) -> None:
    run_id = reviewing(repo)
    repo.verdict(run_id, "code_review", HUMAN, "a.md")
    repo.verdict(run_id, "ui_review", APPROVE, "b.md")
    repo.sak("run", "combine", run_id)
    code, out = repo.sak("run", "return", run_id, "--reason", "Bitte Migration entfernen")
    assert code == 0 and out["state"] == "building" and out["round"] == 2
    assert repo.types(run_id)[-2:] == ["run.returned", "round.started"]
    assert repo.events(run_id)[-2]["data"] == {"reason": "Bitte Migration entfernen"}
    assert repo.run_json(run_id)["escalation"] is None


def test_return_is_refused_at_the_round_limit(repo: Repo) -> None:
    run_id = reviewing(repo)
    repo.sak("run", "state", run_id, "building")
    repo.sak("run", "state", run_id, "reviewing")
    repo.sak("run", "state", run_id, "escalated", "--reason", "x")
    code, out = repo.sak("run", "return", run_id, "--reason", "nochmal")
    assert code == 1 and "max_rounds" in out["error"]


def test_return_needs_a_reason_and_an_escalated_run(repo: Repo) -> None:
    run_id = repo.start()
    code, _ = repo.sak("run", "return", run_id)
    assert code == 2
    code, out = repo.sak("run", "return", run_id, "--reason", "x")
    assert code == 1 and "eskalierte" in out["error"]
    code, out = repo.sak("run", "release", run_id)
    assert code == 1 and "eskalierte" in out["error"]
