"""Urteilsformat (Spec 003 FR-009) in en und de, Regeln aus Spec 001 FR-018."""

from __future__ import annotations

import os
import subprocess
import sys

from conftest import APPROVE, CHANGES, Repo

from spec_agent_kit.pipeline.verdict import parse_verdict, strongest


def test_english_forms_work_in_every_locale() -> None:
    for locale in ("de", "en"):
        assert parse_verdict(APPROVE, locale)["effective"] == "approve"
        assert parse_verdict(CHANGES, locale)["effective"] == "changes_requested"


def test_german_forms_need_locale_de() -> None:
    text = "Urteil: OK\n"
    assert parse_verdict(text, "de")["valid"] is True
    assert parse_verdict(text, "en")["valid"] is False


def test_german_verdict_lines() -> None:
    assert parse_verdict("Urteil: OK\n", "de")["effective"] == "approve"
    changed = parse_verdict("Urteil: Änderung\nGrund: x\n- [Muss] a — b\n", "de")
    assert changed["effective"] == "changes_requested"
    human = parse_verdict("Urteil: Mensch prüft\nGrund: x\n", "de")
    assert human["effective"] == "needs_human"


def test_german_severity_tags_count() -> None:
    text = "Urteil: Änderung\nGrund: x\n- [Muss] a — b\n- [Kann] c — d\n- [may] e — f\n"
    parsed = parse_verdict(text, "de")
    assert len(parsed["must"]) == 1 and len(parsed["may"]) == 2


def test_german_severity_tags_are_not_english_locale() -> None:
    text = "Verdict: changes_requested\nReason: x\n- [Muss] a — b\n"
    assert parse_verdict(text, "en")["valid"] is False  # kein [must]-Befund erkannt


def test_reason_is_found_in_lines_two_to_four_only() -> None:
    inside = "Verdict: needs_human\n\n\nReason: spät\n"
    assert parse_verdict(inside)["valid"] is True
    outside = "Verdict: needs_human\n\n\n\nReason: zu spät\n"
    assert parse_verdict(outside)["valid"] is False


def test_german_reason_label_is_accepted() -> None:
    assert parse_verdict("Verdict: needs_human\nGrund: weil\n")["reason"] == "weil"


def test_bom_and_crlf_are_tolerated() -> None:
    text = "\ufeffVerdict: approve\r\n\r\n- [may] a — b\r\n"
    assert parse_verdict(text)["valid"] is True


def test_findings_with_leading_text_do_not_count() -> None:
    parsed = parse_verdict("Verdict: approve\nSiehe - [must] x\n")
    assert parsed["effective"] == "approve" and parsed["must"] == []


def test_strongest_ranks_verdicts() -> None:
    assert strongest(["approve", "changes_requested"]) == "changes_requested"
    assert strongest(["needs_human", "changes_requested", "approve"]) == "needs_human"


def test_verdict_for_inactive_role_is_rejected(repo: Repo) -> None:
    repo.set_config(pipeline={"roles": {"ui_review": {"enabled": False}}}, ui=None)
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    code, out = repo.verdict(run_id, "ui_review", APPROVE)
    assert code == 1 and "keine aktive Prüfrolle" in out["error"]
    code, out = repo.verdict(run_id, "builder", APPROVE)
    assert code == 1


def test_verdict_outside_reviewing_is_rejected(repo: Repo) -> None:
    run_id = repo.start()
    code, out = repo.verdict(run_id, "code_review", APPROVE)
    assert code == 1 and "reviewing" in out["error"]


def test_approve_with_must_is_recorded_as_changes_requested(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    code, out = repo.verdict(run_id, "code_review", "Verdict: approve\n- [must] a.py:1 — kaputt\n")
    assert code == 0 and out["declared"] == "approve" and out["verdict"] == "changes_requested"
    event = repo.events(run_id)[-1]
    assert event["data"]["verdict"] == "changes_requested" and event["data"]["must_count"] == 1


def test_event_carries_counts_but_no_finding_text(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    repo.verdict(run_id, "code_review", APPROVE)
    event = repo.events(run_id)[-1]
    assert event["data"] == {
        "round": 1,
        "role": "code_review",
        "verdict": "approve",
        "must_count": 0,
        "may_count": 1,
    }
    assert "Hinweis" not in str(event)


def test_second_verdict_of_a_round_replaces_the_file(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    repo.verdict(run_id, "code_review", CHANGES, "a.md")
    repo.verdict(run_id, "code_review", APPROVE, "b.md")
    stored = repo.path / f".spec-agent/state/runs/{run_id}/verdict-code_review-r1.md"
    assert stored.read_text(encoding="utf-8") == APPROVE


def test_console_with_cp1252_prints_umlauts_and_arrows(repo: Repo) -> None:
    """Spec 003, Edge Case: Umlaute und Pfeil funktionieren auch in einer cp1252-Konsole."""
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    file = repo.write("tool-out/v.md", CHANGES)
    code_snippet = "import sys; from spec_agent_kit.cli import main; sys.exit(main(sys.argv[1:]))"
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run(
        [sys.executable, "-c", code_snippet, "run", "verdict", run_id, "ui_review", str(file)],
        cwd=repo.path,
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Überlauf → min-width entfernen".encode() in proc.stdout
