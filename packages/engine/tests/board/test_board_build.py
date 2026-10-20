"""Board-Ableitung: Golden File und Einzelfälle (Spec 006 US1, FR-001 bis FR-007)."""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from board_support import GOLDEN, NOW, force_rmtree

from spec_agent_kit import contracts
from spec_agent_kit.board import BoardError
from spec_agent_kit.board.build import build_board
from spec_agent_kit.board.git_history import parse_marker
from spec_agent_kit.board.specs import count_tasks, has_open_clarification, is_descoped
from spec_agent_kit.config import EffectiveConfig, load_config
from spec_agent_kit.pipeline import runs


def stage_of(doc: dict[str, Any], directory: str) -> str | None:
    (spec,) = [s for s in doc["specs"] if s["dir"] == directory]
    stage: str | None = spec["stage"]
    return stage


def edit_config(root: Path, **sections: Any) -> EffectiveConfig:
    path = root / ".spec-agent" / "config.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key, value in sections.items():
        data.setdefault(key, {}).update(value)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return load_config(root)


# --- Golden File ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fixed_now")
def test_golden_file(board_repo: Path, cfg: EffectiveConfig) -> None:
    doc = build_board(board_repo, cfg, share_text=True)
    assert contracts.validate_board(doc) == []
    rendered = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if os.environ.get("SAK_UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(rendered, encoding="utf-8", newline="\n")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert doc == expected
    assert doc["notes"] == []


@pytest.mark.usefixtures("fixed_now")
def test_fixture_covers_the_independent_test(board_repo: Path, cfg: EffectiveConfig) -> None:
    doc = build_board(board_repo, cfg, share_text=True)
    assert len(doc["specs"]) == 6
    assert {s["stage"] for s in doc["specs"]} == {
        "specified",
        "tasked",
        "implementing",
        "implemented",
        "deployed",
        "verified",
    }
    assert {a["kind"] for a in doc["attention"]} == {
        "escalation",
        "approval",
        "clarification",
        "operator_task",
    }
    assert {r["state"] for r in doc["runs"]} == {"merged", "escalated", "paused"}
    assert {m["kind"] for m in doc["markers"]} == {"deploy", "verified"}
    assert doc["metrics"] == {
        "in_progress": 1,
        "done": 3,
        "blocked": 0,
        "waiting": 4,
        "mean_lead_time_days": 1.7,
    }


# --- Stationen -----------------------------------------------------------------------------


@pytest.mark.usefixtures("fixed_now")
def test_deploy_marker_before_last_task_commit_is_implemented(
    board_repo: Path, cfg: EffectiveConfig
) -> None:
    doc = build_board(board_repo, cfg)
    assert stage_of(doc, "004-billing") == "implemented"
    assert any(m["kind"] == "deploy" and m["specs"] == [4] for m in doc["markers"])


@pytest.mark.usefixtures("fixed_now")
def test_disabled_stages_are_never_assigned(board_repo: Path) -> None:
    cfg = edit_config(board_repo, stages={"deployed": False, "verified": False})
    doc = build_board(board_repo, cfg)
    assert stage_of(doc, "001-foundation") == "implemented"
    assert stage_of(doc, "002-importer") == "implemented"
    assert not {s["stage"] for s in doc["specs"]} & {"deployed", "verified"}


@pytest.mark.usefixtures("fixed_now")
def test_only_verified_disabled_keeps_deployed(board_repo: Path) -> None:
    cfg = edit_config(board_repo, stages={"verified": False})
    doc = build_board(board_repo, cfg)
    assert stage_of(doc, "001-foundation") == "deployed"


@pytest.mark.usefixtures("fixed_now")
@pytest.mark.parametrize("header", ["**Status**: Descoped", "**Status**: DESCOPED (später)"])
def test_descoped_has_no_stage_and_no_attention(
    board_repo: Path, cfg: EffectiveConfig, header: str
) -> None:
    spec = board_repo / "specs" / "006-export" / "spec.md"
    spec.write_text(
        f"# Feature Specification: Export\n\n{header}\n\n## Ziel\n\n[NEEDS CLARIFICATION: x]\n",
        encoding="utf-8",
    )
    tasks = board_repo / "specs" / "006-export" / "tasks.md"
    tasks.write_text("- [ ] T001 [operator] etwas\n", encoding="utf-8")
    doc = build_board(board_repo, cfg)
    (item,) = [s for s in doc["specs"] if s["dir"] == "006-export"]
    assert item["descoped"] is True and item["stage"] is None and item["waiting"] is None
    assert not [a for a in doc["attention"] if a.get("spec") == "006-export"]
    assert doc["metrics"]["in_progress"] == 1


def test_descoped_detection_is_header_only() -> None:
    assert is_descoped("# T\n\n**Status**: descoped\n\n## A\n")
    assert not is_descoped("# T\n\n**Status**: Draft\n\n## A\n\n**Status**: Descoped\n")


# --- Aufmerksamkeit ------------------------------------------------------------------------


@pytest.mark.usefixtures("fixed_now")
def test_clarification_only_outside_code_spans(board_repo: Path, cfg: EffectiveConfig) -> None:
    doc = build_board(board_repo, cfg)
    clarif = [a for a in doc["attention"] if a["kind"] == "clarification"]
    assert [a["spec"] for a in clarif] == ["006-export"]  # 005 nennt den Marker nur im Code-Span


def test_clarification_detection() -> None:
    assert has_open_clarification("Text [NEEDS CLARIFICATION: Frage?]")
    assert not has_open_clarification("Text `[NEEDS CLARIFICATION: Frage?]` Ende")
    assert not has_open_clarification("```\n[NEEDS CLARIFICATION: x]\n```\n")
    assert not has_open_clarification("kein Marker [NEEDS CLARIFICATION] ohne Doppelpunkt")


@pytest.mark.usefixtures("fixed_now")
def test_operator_tasks_one_entry_per_open_task(board_repo: Path, cfg: EffectiveConfig) -> None:
    path = board_repo / "specs" / "003-search" / "tasks.md"
    path.write_text(
        "- [x] T001 fertig [operator] erledigt\n"
        "- [ ] T002 [operator] Konto anlegen\n"
        "- [ ] T003 **[Betreiber]** Domain kaufen\n"
        "- [ ] T004 normal\n",
        encoding="utf-8",
    )
    doc = build_board(board_repo, cfg)
    reasons = sorted(a["reason"] for a in doc["attention"] if a["kind"] == "operator_task")
    assert reasons == ["T002 Konto anlegen", "T003 Domain kaufen"]


def test_task_counting() -> None:
    text = "- [ ] a\n- [x] b\n- [X] c\n* [ ] d [operator]\n```\n- [ ] im Code\n```\n- nichts\n"
    assert count_tasks(text) == (2, 2, ["d"])


@pytest.mark.usefixtures("fixed_now")
def test_approval_needs_tasks_and_no_run(board_repo: Path, cfg: EffectiveConfig) -> None:
    doc = build_board(board_repo, cfg)
    assert [a["spec"] for a in doc["attention"] if a["kind"] == "approval"] == ["005-notify"]
    # Eine leere Taskliste (0/0) hat nichts, das freigegeben werden könnte.
    (board_repo / "specs" / "005-notify" / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    doc = build_board(board_repo, cfg)
    assert not [a for a in doc["attention"] if a["kind"] == "approval"]
    # Sobald je ein Lauf gestartet wurde, entfällt die Freigabe ebenfalls.
    (board_repo / "specs" / "005-notify" / "tasks.md").write_text("- [ ] T1 x\n", encoding="utf-8")
    run = {
        "run_id": "005-20261009-150000",
        "spec": "005-notify",
        "kind": "pipeline",
        "state": "aborted",
        "paused_from": None,
        "round": 1,
        "max_rounds": 2,
        "branch": "005-notify",
        "base_branch": "main",
        "base_commit": "a" * 40,
        "started_at": "2026-10-09T15:00:00Z",
        "updated_at": "2026-10-09T15:10:00Z",
        "escalation": None,
        "origin": {"branch": "main"},
    }
    folder = runs.run_dir(board_repo, run["run_id"])
    folder.mkdir(parents=True)
    (folder / "run.json").write_text(json.dumps(run), encoding="utf-8")
    doc = build_board(board_repo, cfg)
    assert not [a for a in doc["attention"] if a["kind"] == "approval"]


@pytest.mark.usefixtures("fixed_now")
def test_stale_run_gets_attention_entry(
    board_repo: Path, cfg: EffectiveConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    later = NOW + timedelta(hours=8)
    monkeypatch.setattr(runs, "utcnow", lambda: later)
    doc = build_board(board_repo, cfg)
    (run,) = [r for r in doc["runs"] if r["state"] == "escalated"]
    assert run["idle"] is True and run["stale"] is True
    kinds = [a["kind"] for a in doc["attention"] if a.get("spec") == "003-search"]
    assert kinds[:2] == ["escalation", "stale_run"]
    assert contracts.validate_board(doc) == []


@pytest.mark.usefixtures("fixed_now")
def test_idle_but_not_stale(
    board_repo: Path, cfg: EffectiveConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runs, "utcnow", lambda: NOW + timedelta(hours=2))
    doc = build_board(board_repo, cfg)
    (run,) = [r for r in doc["runs"] if r["state"] == "escalated"]
    assert run["idle"] is True and run["stale"] is False
    assert not [a for a in doc["attention"] if a["kind"] == "stale_run"]


# --- Läufe ---------------------------------------------------------------------------------


@pytest.mark.usefixtures("fixed_now")
def test_runs_newest_first_and_limited_to_20(board_repo: Path, cfg: EffectiveConfig) -> None:
    for day in range(1, 26):
        run_id = f"002-202609{day:02d}-120000"
        run = {
            "run_id": run_id,
            "spec": "002-importer",
            "kind": "pipeline",
            "state": "aborted",
            "paused_from": None,
            "round": 1,
            "max_rounds": 2,
            "branch": "002-importer",
            "base_branch": "main",
            "base_commit": "a" * 40,
            "started_at": f"2026-09-{day:02d}T12:00:00Z",
            "updated_at": f"2026-09-{day:02d}T13:00:00Z",
            "escalation": None,
            "origin": {},
        }
        folder = runs.run_dir(board_repo, run_id)
        folder.mkdir(parents=True)
        (folder / "run.json").write_text(json.dumps(run), encoding="utf-8")
    doc = build_board(board_repo, cfg)
    assert len(doc["runs"]) == 20
    starts = [r["started_at"] for r in doc["runs"]]
    assert starts == sorted(starts, reverse=True)
    assert starts[0] == "2026-10-10T09:00:00Z"
    assert contracts.validate_board(doc) == []


@pytest.mark.usefixtures("fixed_now")
def test_run_with_unknown_state_is_dropped_with_a_note(
    board_repo: Path, cfg: EffectiveConfig
) -> None:
    path = runs.run_dir(board_repo, "001-20261002-080000") / "run.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["state"] = "geparkt"  # Wert eines anderen Kit-Stands
    path.write_text(json.dumps(data), encoding="utf-8")
    doc = build_board(board_repo, cfg)
    assert "001-20261002-080000" not in {r["run_id"] for r in doc["runs"]}
    assert any("runs[" in n for n in doc["notes"])
    assert contracts.validate_board(doc) == []


@pytest.mark.usefixtures("fixed_now")
def test_broken_run_json_and_event_lines_become_notes(
    board_repo: Path, cfg: EffectiveConfig
) -> None:
    (runs.run_dir(board_repo, "001-20261002-080000") / "run.json").write_text(
        "{kaputt", encoding="utf-8"
    )
    events = board_repo / ".spec-agent" / "state" / "events.jsonl"
    with events.open("a", encoding="utf-8") as handle:
        handle.write("das ist kein json\n[1,2]\n")
    doc = build_board(board_repo, cfg)
    assert any("unlesbare Zeile" in n for n in doc["notes"])
    assert "001-20261002-080000" not in {r["run_id"] for r in doc["runs"]}
    assert contracts.validate_board(doc) == []


# --- Robustheit ----------------------------------------------------------------------------


@pytest.mark.usefixtures("fixed_now")
def test_unreadable_tasks_file_is_a_note_and_the_rest_stays(
    board_repo: Path, cfg: EffectiveConfig
) -> None:
    (board_repo / "specs" / "003-search" / "tasks.md").write_bytes(b"\xff\xfe\x00 kein utf-8 \x80")
    doc = build_board(board_repo, cfg)
    assert any("003-search/tasks.md nicht lesbar" in n for n in doc["notes"])
    assert len(doc["specs"]) == 6 and len(doc["runs"]) == 3
    assert stage_of(doc, "001-foundation") == "verified"
    assert contracts.validate_board(doc) == []


@pytest.mark.usefixtures("fixed_now")
def test_without_git_the_board_still_builds(board_repo: Path, cfg: EffectiveConfig) -> None:
    force_rmtree(board_repo / ".git")
    doc = build_board(board_repo, cfg)
    assert any(n.startswith("Git nicht verfügbar") for n in doc["notes"])
    assert doc["markers"] == [] and doc["ticker"] == []
    assert len(doc["specs"]) == 6
    assert contracts.validate_board(doc) == []


@pytest.mark.usefixtures("fixed_now")
def test_empty_project_is_a_valid_board(tmp_path: Path) -> None:
    root = tmp_path / "leer"
    (root / ".spec-agent").mkdir(parents=True)
    (root / ".spec-agent" / "config.yml").write_text(
        "schema: sak.config/1\nproject:\n  key: leer\n  name: Leer\n", encoding="utf-8"
    )
    doc = build_board(root, load_config(root))
    assert (
        doc["specs"] == [] and doc["runs"] == [] and doc["metrics"]["mean_lead_time_days"] is None
    )
    assert contracts.validate_board(doc) == []


@pytest.mark.usefixtures("fixed_now")
def test_ticker_text_is_opt_in(board_repo: Path, cfg: EffectiveConfig) -> None:
    hidden = build_board(board_repo, cfg)  # share_commit_subjects ist false
    assert hidden["ticker"] and all("text" not in t for t in hidden["ticker"])
    shown = build_board(board_repo, cfg, share_text=True)
    assert all("text" in t for t in shown["ticker"])
    shared = build_board(
        board_repo, edit_config(board_repo, dashboard={"share_commit_subjects": True})
    )
    assert all("text" in t for t in shared["ticker"])


@pytest.mark.usefixtures("fixed_now")
def test_snapshot_source_drops_runs_escalations_and_texts(
    board_repo: Path, cfg: EffectiveConfig
) -> None:
    doc = build_board(board_repo, cfg, source="snapshot", share_text=True)
    assert doc["source"] == "snapshot" and doc["runs"] == []
    assert not [a for a in doc["attention"] if a["kind"] in {"escalation", "stale_run"}]
    assert all("text" not in t for t in doc["ticker"])
    assert contracts.validate_board(doc) == []


@pytest.mark.usefixtures("fixed_now")
def test_invalid_document_raises_with_path(
    board_repo: Path, cfg: EffectiveConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spec_agent_kit.board.build.__version__", "")
    with pytest.raises(BoardError) as info:
        build_board(board_repo, cfg)
    assert info.value.path == "kit_version"


@pytest.mark.usefixtures("fixed_now")
def test_notes_are_capped_at_20(board_repo: Path, cfg: EffectiveConfig) -> None:
    for i in range(30):
        folder = runs.run_dir(board_repo, f"009-20261001-0000{i:02d}")
        folder.mkdir(parents=True)
        (folder / "run.json").write_text('{"run_id": "x"}', encoding="utf-8")
    doc = build_board(board_repo, cfg)
    assert len(doc["notes"]) <= 20
    assert contracts.validate_board(doc) == []


# --- Marker-Regex ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("deploy(084): x", ("deploy", [84])),
        ("deploy(084,085): x", ("deploy", [84, 85])),
        ("verified(079-082): x", ("verified", [79, 80, 81, 82])),
        ("verified(001, 003-004)", ("verified", [1, 3, 4])),
        ("feat(084): x", None),
        ("deploy(a): x", None),
        ("verified(5-3): x", None),
        ("see deploy(084)", None),
    ],
)
def test_parse_marker(subject: str, expected: tuple[str, list[int]] | None) -> None:
    assert parse_marker(subject) == expected
