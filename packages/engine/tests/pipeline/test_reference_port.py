"""Portierung der 40 Verhaltensfälle aus ImmoAgent ``tests/unit/specify/test_pipeline.py``.

Spec 003 SC-001 und Task T016. Die Fälle laufen gegen die CLI ``sak`` mit Lauf-ID, Rollenliste aus
der Config und v1-Events. Spalte „Änderung“: was sich am Modell geändert hat.

| Alter Test (ImmoAgent) | Neuer Test | Änderung |
|---|---|---|
| test_config_check_ok | test_config_check_ok | ``sak config check`` (Spec 004) statt ``config-check`` |
| test_config_check_missing_key | test_config_check_missing_key | Pflichtschlüssel ``project`` statt ``max_rounds`` |
| test_config_check_agent_without_file | test_config_check_agent_without_file | Rollen statt Agent-Liste |
| test_config_check_frontmatter_mismatch | test_config_check_frontmatter_mismatch | unverändert |
| test_config_check_reports_invalid_frontmatter_yaml | test_config_check_reports_unreadable_frontmatter | Meldung „kein lesbares Frontmatter“ |
| test_preflight_creates_branch_and_run | test_preflight_creates_branch_and_run | Lauf-ID, v1-Events, ``run.json`` je Lauf |
| test_preflight_rejects_dirty_tree | test_preflight_rejects_dirty_tree | unverändert |
| test_preflight_ignores_graphify_changes | test_preflight_ignores_clean_ignore_paths | projektneutral: ``guard.clean_ignore`` |
| test_preflight_requires_tasks | test_preflight_requires_tasks | unverändert |
| test_preflight_rejects_second_active_run | test_preflight_rejects_second_active_run | Sperre nach Spec 001 FR-013 |
| test_preflight_refuses_an_old_spec_branch_that_lacks_the_current_state | test_preflight_refuses_an_old_spec_branch_that_lacks_the_current_state | unverändert |
| test_preflight_reuses_an_existing_spec_branch_that_contains_the_current_state | test_preflight_reuses_an_existing_spec_branch_that_contains_the_current_state | unverändert |
| test_preflight_on_spec_branch_needs_base | test_preflight_on_spec_branch_uses_configured_base | Anforderung entfällt: ``--base`` ist nicht mehr Pflicht, der Default kommt aus ``project.base_branch`` |
| test_state_happy_path_to_merged | test_state_happy_path_to_merged | ``merged`` über ``run merge``; Events ``run.approved``, ``run.merged`` |
| test_state_round_two_then_no_third | test_state_round_two_then_no_third | ``round.started`` als v1-Event |
| test_state_rejects_illegal_transition | test_state_rejects_illegal_transition | unverändert |
| test_state_escalate_needs_reason_and_release | test_state_escalate_needs_reason_and_release | ``run release`` statt ``state approved`` |
| test_guard_flags_pipeline_files | test_guard_flags_pipeline_files | Kern-Schutz ``.claude/agents/sak-*``, Gate ``protected_paths`` |
| test_guard_hints_only_for_escalation_paths | test_guard_hints_only_for_escalation_paths | unverändert |
| test_guard_sees_uncommitted_changes_but_not_graphify | test_guard_sees_uncommitted_changes_but_not_clean_ignore | ``guard.clean_ignore`` |
| test_reviewer_check_detects_changes | test_reviewer_check_detects_changes | unverändert; Eskalation siehe test_guard_snapshot.py |
| test_reviewer_check_detects_edit_of_dirty_file | test_reviewer_check_detects_edit_of_dirty_file | unverändert |
| test_reviewer_check_ignores_graphify_and_run_files | test_reviewer_check_ignores_clean_ignore_and_run_files | ``guard.clean_ignore`` |
| test_parse_verdict_forms | test_parse_verdict_forms | ``Verdict:`` (en) und ``Urteil:`` (de) |
| test_parse_verdict_invalid_first_line | test_parse_verdict_invalid_first_line | englische Werte, Groß-/Kleinschreibung |
| test_parse_verdict_ok_with_muss_becomes_change | test_parse_verdict_approve_with_must_becomes_changes_requested | Maschinenwerte |
| test_parse_verdict_change_needs_reason_and_muss | test_parse_verdict_changes_requested_needs_reason_and_must | Maschinenwerte |
| test_verdict_command_stores_file_per_round | test_verdict_command_stores_file_per_round | Rolle statt Station, Zustand ``reviewing`` nötig |
| test_verdict_command_rejects_invalid | test_verdict_command_rejects_invalid | unverändert |
| test_combine_waits_for_both_and_ranks | test_combine_requires_all_active_roles_and_ranks | fehlendes Urteil wird abgelehnt (Exit 1); ``combine`` wechselt den Zustand |
| test_event_hook_writes_station_events | test_hook_writes_station_events | v1-Events mit ``role``, ``agent``, ``duration_s`` |
| test_verdict_command_writes_verdict_event | test_verdict_command_writes_verdict_event | ``verdict.recorded`` mit ``must_count``, ``may_count`` |
| test_event_hook_stop_without_message_field | test_hook_stop_without_message_field | ``diag.hook`` nur ohne Agent-Typ (Spec 003, Edge Cases) |
| test_event_hook_ignores_foreign_agent_and_no_run | test_hook_ignores_foreign_agent_and_no_run | ohne Lauf kein Event, auch kein ``diag.hook`` |
| test_event_hook_logs_debug_keys_once | test_hook_logs_diag_keys_once | ``diag.hook`` statt ``hook_debug``, nur bei fehlendem Agent-Typ |
| test_event_hook_accepts_tool_input_shape | test_hook_accepts_tool_input_shape | unverändert |
| test_event_hook_never_fails (4 Fälle) | test_hook_never_fails (4 Fälle) | unverändert |
| test_event_hook_never_fails_without_config | test_hook_never_fails_without_config | unverändert |
| test_event_kind_writes_reason | test_event_emit_writes_reason | ``sak event emit run.escalated`` |
| test_event_requires_hook_or_kind | test_event_requires_a_known_type | ``sak event`` ohne Unterbefehl: Exit 2; unbekannter Typ: Exit 1 |

Bilanz: 40 von 40 Fällen übernommen (43 Testfälle mit der Parametrisierung), 0 entfallen
ersatzlos. Eine Anforderung entfällt bewusst (``--base`` auf dem Spec-Branch, Zeile 13); an ihre
Stelle tritt der Test mit dem neuen Verhalten. Dazu kommen die neuen Tests in den Dateien
``test_states.py``, ``test_preflight.py``, ``test_guard_snapshot.py``, ``test_verdict.py``,
``test_combine.py``, ``test_hooks.py``, ``test_pause_resume_takeover.py``, ``test_review_only.py``,
``test_merge.py`` und ``test_e2e_pilot.py``.
"""

# ruff: noqa: E501  (die Zuordnungstabelle oben hat lange Zeilen)
from __future__ import annotations

import json
import re

import pytest
from conftest import APPROVE, CHANGES, HUMAN, Repo

from spec_agent_kit.pipeline.verdict import parse_verdict


def hook_payload(agent: str, **extra: object) -> str:
    return json.dumps({"agent_type": agent, "hook_event_name": "SubagentStart", **extra})


def to_reviewing(repo: Repo, run_id: str) -> None:
    code, out = repo.sak("run", "state", run_id, "reviewing")
    assert code == 0, out


# --- config check -----------------------------------------------------------


def test_config_check_ok(repo: Repo) -> None:
    code, out = repo.sak("config", "check")
    assert code == 0 and out["ok"] is True and out["errors"] == []


def test_config_check_missing_key(repo: Repo) -> None:
    repo.write(".spec-agent/config.yml", "schema: sak.config/1\n")
    code, out = repo.sak("config", "check")
    assert code == 1 and out["ok"] is False
    assert any("project" in e["message"] for e in out["errors"])


def test_config_check_agent_without_file(repo: Repo) -> None:
    (repo.path / ".claude/agents/sak-ui-reviewer.md").unlink()
    _, out = repo.sak("config", "check")
    assert any("Agent-Datei fehlt" in e["message"] for e in out["errors"])


def test_config_check_frontmatter_mismatch(repo: Repo) -> None:
    repo.write(
        ".claude/agents/sak-builder.md",
        "---\nname: sak-builder\nmodel: opus\neffort: high\n---\n",
    )
    _, out = repo.sak("config", "check")
    paths = [e["path"] for e in out["errors"]]
    assert "pipeline.roles.builder.model" in paths and "pipeline.roles.builder.effort" in paths


def test_config_check_reports_unreadable_frontmatter(repo: Repo) -> None:
    repo.write(
        ".claude/agents/sak-builder.md",
        "---\nname: sak-builder\ndescription: Station: Builder\nmodel: sonnet\n---\n",
    )
    _, out = repo.sak("config", "check")
    assert any("kein lesbares Frontmatter" in e["message"] for e in out["errors"])


# --- preflight / state ------------------------------------------------------


def test_preflight_creates_branch_and_run(repo: Repo) -> None:
    code, out = repo.sak("run", "preflight", "001")
    assert code == 0, out
    assert re.fullmatch(r"001-[0-9]{8}-[0-9]{6}", out["run_id"])
    assert out["branch"] == "001-demo" and out["base_branch"] == "main"
    assert out["state"] == "building" and out["round"] == 1 and out["max_rounds"] == 2
    assert repo.branch() == "001-demo"
    assert repo.types() == ["run.started", "round.started"]
    started = repo.events()[0]
    assert started["project"] == "demo" and started["run_id"] == out["run_id"]
    assert started["data"]["kind"] == "pipeline"
    assert started["origin"] == {"branch": "main"}
    run = repo.run_json(out["run_id"])
    assert run["spec"] == "001-demo" and run["base_commit"] == started["data"]["base_commit"]


def test_preflight_rejects_dirty_tree(repo: Repo) -> None:
    repo.write("src/new.py", "y = 2\n")
    code, out = repo.sak("run", "preflight", "001")
    assert code == 1 and "nicht sauber" in out["error"] and "src/new.py" in out["error"]


def test_preflight_ignores_clean_ignore_paths(repo: Repo) -> None:
    repo.write("tool-out/graph.json", "{}")
    code, _ = repo.sak("run", "preflight", "001")
    assert code == 0


def test_preflight_requires_tasks(repo: Repo) -> None:
    (repo.path / "specs/001-demo/tasks.md").unlink()
    repo.git("commit", "-qam", "drop tasks")
    code, out = repo.sak("run", "preflight", "001")
    assert code == 1 and "tasks.md" in out["error"]


def test_preflight_rejects_second_active_run(repo: Repo) -> None:
    repo.start()
    repo.add_spec("002-other")
    code, out = repo.sak("run", "preflight", "002", "--base", "001-demo")
    assert code == 1 and "läuft bereits" in out["error"]


def test_preflight_refuses_an_old_spec_branch_that_lacks_the_current_state(repo: Repo) -> None:
    repo.git("branch", "001-demo")  # alter Branch am aktuellen Commit ...
    repo.write("src/later.py", "z = 9\n")
    repo.commit("work on main after the branch was cut")  # ... der jetzt hinter main liegt
    code, out = repo.sak("run", "preflight", "001")
    assert code == 1 and "existiert schon" in out["error"]
    assert repo.branch() == "main"


def test_preflight_reuses_an_existing_spec_branch_that_contains_the_current_state(
    repo: Repo,
) -> None:
    repo.git("branch", "001-demo")  # gleicher Commit wie main: nichts geht verloren
    code, out = repo.sak("run", "preflight", "001")
    assert code == 0 and out["base_branch"] == "main" and repo.branch() == "001-demo"


def test_preflight_on_spec_branch_uses_configured_base(repo: Repo) -> None:
    repo.git("switch", "-q", "-c", "001-demo")
    code, out = repo.sak("run", "preflight", "001")
    assert code == 0 and out["base_branch"] == "main"
    repo.sak("run", "abort", out["run_id"])
    code, out = repo.sak("run", "preflight", "001", "--base", "missing-branch")
    assert code == 1 and "missing-branch" in out["error"]


def test_state_happy_path_to_merged(repo: Repo) -> None:
    run_id = repo.start()
    repo.write("src/feature.py", "f = 1\n")
    repo.commit("feat")
    for new in ("reviewing", "approved"):
        code, out = repo.sak("run", "state", run_id, new)
        assert code == 0 and out["state"] == new
    code, out = repo.sak("run", "merge", run_id)
    assert code == 0 and out["state"] == "merged"
    assert repo.types(run_id) == ["run.started", "round.started", "run.approved", "run.merged"]
    assert repo.branch() == "main"
    _, listed = repo.sak("run", "list")  # beendet: die Sperre ist frei
    assert listed["runs"] == []
    code, out = repo.sak("run", "preflight", "001")
    assert code == 1 and "existiert schon" in out["error"]  # der Branch kennt den Merge nicht


def test_state_round_two_then_no_third(repo: Repo) -> None:
    run_id = repo.start()
    to_reviewing(repo, run_id)
    code, out = repo.sak("run", "state", run_id, "building")
    assert code == 0 and out["round"] == 2
    to_reviewing(repo, run_id)
    code, out = repo.sak("run", "state", run_id, "building")
    assert code == 1 and "max_rounds" in out["error"]
    assert repo.types(run_id).count("round.started") == 2


def test_state_rejects_illegal_transition(repo: Repo) -> None:
    run_id = repo.start()
    code, out = repo.sak("run", "state", run_id, "approved")
    assert code == 1 and "nicht erlaubt" in out["error"]


def test_state_escalate_needs_reason_and_release(repo: Repo) -> None:
    run_id = repo.start()
    code, _ = repo.sak("run", "state", run_id, "escalated")
    assert code == 1
    code, _ = repo.sak("run", "state", run_id, "escalated", "--reason", "Migration")
    assert code == 0
    code, out = repo.sak("run", "release", run_id)
    assert code == 0 and out["state"] == "approved"
    assert repo.types(run_id)[-2:] == ["run.escalated", "run.released"]
    escalated = repo.events(run_id)[-2]
    assert escalated["data"] == {"round": 1, "reason": "Migration"}


# --- guard / snapshot / reviewer-check --------------------------------------


def test_guard_flags_pipeline_files(repo: Repo) -> None:
    run_id = repo.start()
    repo.write(".claude/agents/sak-builder.md", "---\nmodel: sonnet\neffort: medium\n---\nx\n")
    repo.git("commit", "-qam", "touch agent")
    _, out = repo.sak("run", "guard", run_id)
    assert out["escalate"] is True and out["gate"] == "protected_paths"
    assert out["reason"] == "Pipeline-Datei geändert"
    assert ".claude/agents/sak-builder.md" in out["protected_hits"]


def test_guard_hints_only_for_escalation_paths(repo: Repo) -> None:
    run_id = repo.start()
    repo.write("src/payments/pay.py", "x = 2\n")
    repo.git("commit", "-qam", "payments")
    _, out = repo.sak("run", "guard", run_id)
    assert out["escalate"] is False
    assert out["hints"] == ["src/payments/pay.py"]


def test_guard_sees_uncommitted_changes_but_not_clean_ignore(repo: Repo) -> None:
    run_id = repo.start()
    repo.write(
        ".spec-agent/config.yml",
        (repo.path / ".spec-agent/config.yml").read_text("utf-8") + "# edit\n",
    )
    repo.write("tool-out/graph.json", "{}")
    _, out = repo.sak("run", "guard", run_id)
    assert out["protected_hits"] == [".spec-agent/config.yml"]
    assert out["changed_count"] == 1


def test_reviewer_check_detects_changes(repo: Repo) -> None:
    _, snap = repo.sak("run", "snapshot")
    code, _ = repo.sak("run", "reviewer-check", snap["snapshot"])
    assert code == 0
    repo.write("src/new.py", "z = 3\n")
    code, out = repo.sak("run", "reviewer-check", snap["snapshot"])
    assert code == 1 and "verändert" in out["error"]


def test_reviewer_check_detects_edit_of_dirty_file(repo: Repo) -> None:
    repo.write("src/payments/pay.py", "x = 5\n")
    _, snap = repo.sak("run", "snapshot")
    repo.write("src/payments/pay.py", "x = 6\n")
    code, _ = repo.sak("run", "reviewer-check", snap["snapshot"])
    assert code == 1


def test_reviewer_check_ignores_clean_ignore_and_run_files(repo: Repo) -> None:
    run_id = repo.start()
    _, snap = repo.sak("run", "snapshot")
    repo.write("tool-out/graph.json", '{"a": 1}')
    repo.write(f".spec-agent/state/runs/{run_id}/ui/shot.txt", "x")
    code, _ = repo.sak("run", "reviewer-check", snap["snapshot"])
    assert code == 0


# --- verdict / combine ------------------------------------------------------

OK_DE = "Urteil: OK\n\n## Befunde\n- [Kann] a.py:1 — Hinweis\n"
CHANGE_DE = (
    "Urteil: Änderung\nGrund: Überlauf mobil\n\n## Befunde\n"
    "- [Muss] web/style.css:880 — Überlauf → min-width entfernen\n"
)
HUMAN_DE = "Urteil: Mensch prüft\nGrund: Migration auf Bestandsdaten\n"


def test_parse_verdict_forms() -> None:
    assert parse_verdict(APPROVE)["effective"] == "approve"
    parsed = parse_verdict(CHANGES)
    assert parsed["effective"] == "changes_requested" and len(parsed["must"]) == 1
    assert parse_verdict(HUMAN)["effective"] == "needs_human"
    assert parse_verdict(OK_DE, "de")["effective"] == "approve"
    assert parse_verdict(CHANGE_DE, "de")["effective"] == "changes_requested"
    assert parse_verdict(HUMAN_DE, "de")["effective"] == "needs_human"


def test_parse_verdict_invalid_first_line() -> None:
    assert parse_verdict("Alles gut\n")["valid"] is False
    assert parse_verdict("Verdict: ok\n")["valid"] is False
    assert parse_verdict("Verdict: Approve\n")["valid"] is False


def test_parse_verdict_approve_with_must_becomes_changes_requested() -> None:
    parsed = parse_verdict("Verdict: approve\n- [must] a.py:1 — kaputt\n")
    assert parsed["declared"] == "approve" and parsed["effective"] == "changes_requested"


def test_parse_verdict_changes_requested_needs_reason_and_must() -> None:
    assert parse_verdict("Verdict: changes_requested\n- [must] a — b\n")["valid"] is False
    assert parse_verdict("Verdict: changes_requested\nReason: x\n- [may] a — b\n")["valid"] is False
    assert parse_verdict("Verdict: needs_human\n")["valid"] is False


def test_verdict_command_stores_file_per_round(repo: Repo) -> None:
    run_id = repo.start()
    to_reviewing(repo, run_id)
    code, out = repo.verdict(run_id, "code_review", APPROVE)
    assert code == 0 and out["verdict"] == "approve"
    stored = repo.path / f".spec-agent/state/runs/{run_id}/verdict-code_review-r1.md"
    assert stored.read_text(encoding="utf-8") == APPROVE


def test_verdict_command_rejects_invalid(repo: Repo) -> None:
    run_id = repo.start()
    to_reviewing(repo, run_id)
    code, _ = repo.verdict(run_id, "ui_review", "nope")
    assert code == 1
    assert not (repo.path / f".spec-agent/state/runs/{run_id}/verdict-ui_review-r1.md").exists()


def test_combine_requires_all_active_roles_and_ranks(repo: Repo) -> None:
    run_id = repo.start()
    to_reviewing(repo, run_id)
    repo.verdict(run_id, "code_review", APPROVE, "a.md")
    code, out = repo.sak("run", "combine", run_id)
    assert code == 1 and out["missing"] == ["ui_review"]
    repo.verdict(run_id, "ui_review", CHANGES, "b.md")
    code, out = repo.sak("run", "combine", run_id)
    assert code == 0 and out["verdict"] == "changes_requested"
    assert out["must"][0].startswith("[ui_review]")
    assert out["state"] == "building" and out["round"] == 2
    to_reviewing(repo, run_id)
    repo.verdict(run_id, "code_review", HUMAN, "c.md")
    repo.verdict(run_id, "ui_review", CHANGES, "d.md")
    _, out = repo.sak("run", "combine", run_id)
    assert out["verdict"] == "needs_human" and out["judged_round"] == 2
    assert out["state"] == "escalated"


# --- Events und Hooks -------------------------------------------------------


def test_hook_writes_station_events(repo: Repo, clock: object) -> None:
    run_id = repo.start()
    assert repo.sak("hook", "subagent-start", stdin=hook_payload("sak-code-reviewer"))[0] == 0
    assert repo.sak("hook", "subagent-stop", stdin=hook_payload("sak-code-reviewer"))[0] == 0
    stations = [e for e in repo.events(run_id) if e["type"].startswith("station.")]
    assert [e["type"] for e in stations] == ["station.started", "station.finished"]
    started, finished = stations
    assert started["data"] == {
        "round": 1,
        "role": "code_review",
        "agent": "sak-code-reviewer",
        "model": "opus",
        "effort": "medium",
    }
    assert finished["data"]["role"] == "code_review" and finished["data"]["round"] == 1
    assert isinstance(finished["data"]["duration_s"], int | float)


def test_verdict_command_writes_verdict_event(repo: Repo) -> None:
    run_id = repo.start()
    to_reviewing(repo, run_id)
    repo.verdict(run_id, "ui_review", CHANGES)
    event = repo.events(run_id)[-1]
    assert event["type"] == "verdict.recorded"
    assert event["data"] == {
        "round": 1,
        "role": "ui_review",
        "verdict": "changes_requested",
        "must_count": 1,
        "may_count": 0,
    }


def test_hook_stop_without_message_field(repo: Repo) -> None:
    """Der SubagentStop-Payload von Claude Code trägt keinen Antworttext."""
    run_id = repo.start()
    repo.sak("hook", "subagent-start", stdin=hook_payload("sak-builder"))
    repo.sak("hook", "subagent-stop", stdin=hook_payload("sak-builder"))
    assert repo.types(run_id)[-1] == "station.finished"
    assert "diag.hook" not in repo.types()


def test_hook_ignores_foreign_agent_and_no_run(repo: Repo) -> None:
    repo.sak("hook", "subagent-start", stdin=hook_payload("sak-builder"))
    assert repo.events() == []
    run_id = repo.start()
    before = len(repo.events(run_id))
    repo.sak("hook", "subagent-start", stdin=hook_payload("Explore"))
    assert len(repo.events(run_id)) == before


def test_hook_logs_diag_keys_once(repo: Repo) -> None:
    repo.start()
    for _ in range(2):
        repo.sak("hook", "subagent-start", stdin=json.dumps({"hook_event_name": "x", "cwd": "y"}))
    diag = [e for e in repo.events() if e["type"] == "diag.hook"]
    assert len(diag) == 1
    assert diag[0]["data"] == {"phase": "start", "keys": ["cwd", "hook_event_name"]}


def test_hook_accepts_tool_input_shape(repo: Repo) -> None:
    repo.start()
    payload = json.dumps({"tool_input": {"subagent_type": "sak-builder"}})
    repo.sak("hook", "subagent-start", stdin=payload)
    assert repo.events()[-1]["type"] == "station.started"


@pytest.mark.parametrize("raw", ["", "not json", "[1, 2]", "null"])
def test_hook_never_fails(repo: Repo, raw: str) -> None:
    repo.start()
    code, _ = repo.sak("hook", "subagent-stop", stdin=raw)
    assert code == 0


def test_hook_never_fails_without_config(repo: Repo) -> None:
    (repo.path / ".spec-agent/config.yml").unlink()
    code, _ = repo.sak("hook", "subagent-start", stdin=hook_payload("sak-builder"))
    assert code == 0


def test_event_emit_writes_reason(repo: Repo) -> None:
    run_id = repo.start()
    code, _ = repo.sak("event", "emit", "run.escalated", "--reason", "Login")
    assert code == 0
    last = repo.events(run_id)[-1]
    assert last["type"] == "run.escalated" and last["data"] == {"round": 1, "reason": "Login"}


def test_event_requires_a_known_type(repo: Repo) -> None:
    repo.start()
    code, _ = repo.sak("event")
    assert code == 2
    code, out = repo.sak("event", "emit", "verdict.recorded")
    assert code == 1 and "schreibt die Engine selbst" in out["error"]
