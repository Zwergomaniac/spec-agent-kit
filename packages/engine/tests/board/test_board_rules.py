"""Board-Ableitungsregeln (Spec 010 US6, FR-007): je ein Regressionstest pro Punkt 1 bis 7."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from spec_agent_kit import contracts
from spec_agent_kit.board.build import build_board
from spec_agent_kit.board.specs import count_tasks, is_finished, is_in_progress
from spec_agent_kit.board.text import local_stamp, render_text
from spec_agent_kit.config import EffectiveConfig, load_config

DESCOPED_YML = "\n".join(
    [
        "feature_status_report:",
        "  specs:",
        "    - spec_dir: 005-notify",
        "      status: descoped",
        "",
    ]
)


def with_plugins(root: Path, plugins: list[dict[str, Any]]) -> EffectiveConfig:
    path = root / ".spec-agent" / "config.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["plugins"] = plugins
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return load_config(root)


def spec_item(doc: dict[str, Any], directory: str) -> dict[str, Any]:
    (item,) = [s for s in doc["specs"] if s["dir"] == directory]
    return item


# --- Punkt 1: [~] ----------------------------------------------------------------------------


def test_rule1_partial_tasks_are_counted_separately() -> None:
    result = count_tasks("- [x] a\n- [~] b\n- [~] c\n- [ ] d\n")
    assert (result.done, result.partial, result.open) == (1, 2, 1)


@pytest.mark.usefixtures("fixed_now")
def test_rule1_partial_blocks_finished_and_fills_tasks_partial(
    board_repo: Path, cfg: EffectiveConfig
) -> None:
    # 004-billing ist „implemented“ (2/2). Eine teilweise Task macht daraus „in Arbeit“.
    (board_repo / "specs" / "004-billing" / "tasks.md").write_text(
        "- [x] T001 a\n- [x] T002 b\n- [~] T003 c\n", encoding="utf-8"
    )
    doc = build_board(board_repo, cfg)
    item = spec_item(doc, "004-billing")
    assert item["tasks"] == {"done": 2, "open": 0, "partial": 1}
    assert item["stage"] == "implementing"
    assert contracts.validate_board(doc) == []


@pytest.mark.usefixtures("fixed_now")
def test_rule1_tasks_partial_is_absent_without_partial_tasks(
    board_repo: Path, cfg: EffectiveConfig
) -> None:
    doc = build_board(board_repo, cfg)
    assert all("partial" not in s["tasks"] for s in doc["specs"])


# --- Punkt 2: descoped aus anderer Quelle (Plugin) ---------------------------------------------


@pytest.mark.usefixtures("fixed_now")
def test_rule2_descoped_from_a_plugin_source(board_repo: Path) -> None:
    (board_repo / ".specify").mkdir()
    (board_repo / ".specify" / "feature-status.yml").write_text(
        DESCOPED_YML,
        encoding="utf-8",
    )
    cfg = with_plugins(board_repo, [{"name": "legacy-status"}])
    doc = build_board(board_repo, cfg)
    item = spec_item(doc, "005-notify")
    assert item["descoped"] is True and item["stage"] is None and item["waiting"] is None
    assert not [a for a in doc["attention"] if a.get("spec") == "005-notify"]


@pytest.mark.usefixtures("fixed_now")
def test_rule2_without_the_plugin_the_spec_is_not_descoped(
    board_repo: Path, cfg: EffectiveConfig
) -> None:
    (board_repo / ".specify").mkdir()
    (board_repo / ".specify" / "feature-status.yml").write_text(
        DESCOPED_YML,
        encoding="utf-8",
    )
    assert spec_item(build_board(board_repo, cfg), "005-notify")["descoped"] is False


# --- Punkt 3: Code-Spans -----------------------------------------------------------------------


def test_rule3_operator_marker_in_code_span_is_ignored() -> None:
    text = "- [ ] T038 Test für `**[Betreiber]**`-Task\n- [ ] T039 `[operator]` erkennen\n"
    assert count_tasks(text).operator == []


def test_rule3_code_spans_survive_in_the_shown_reason() -> None:
    text = "- [ ] T001 **[Betreiber]** Ändere `AGENT.MD` und `--flag` ab\n"
    assert count_tasks(text).operator == ["T001 Ändere `AGENT.MD` und `--flag` ab"]


def test_rule3_marker_outside_and_inside_in_one_line() -> None:
    text = "- [ ] T001 [operator] zeige `**[Betreiber]**` an\n"
    assert count_tasks(text).operator == ["T001 zeige `**[Betreiber]**` an"]


# --- Punkt 4: Fence als Folgezeile einer Aufzählung --------------------------------------------


def test_rule4_fence_like_continuation_of_a_bullet_does_not_swallow_tasks() -> None:
    text = (
        "- [ ] T001 Regel\n"
        "      ```mermaid-Block beginnt mit einem Diagrammtyp\n"
        "- [ ] T002 zwei\n"
        "- [ ] T003 drei\n"
    )
    assert count_tasks(text)[:3] == (0, 0, 3)


def test_rule4_fence_with_up_to_3_spaces_after_a_bullet_is_a_continuation() -> None:
    text = "- [ ] T001 Regel\n  ```bash\n- [ ] T002 zwei\n"
    assert count_tasks(text)[:3] == (0, 0, 2)


def test_rule4_real_code_blocks_still_hide_their_lines() -> None:
    text = "- [ ] a\n```\n- [ ] im Code\n```\n- [x] b\n~~~\n- [ ] auch\n~~~\n"
    assert count_tasks(text)[:3] == (1, 0, 1)


def test_rule4_fence_after_a_paragraph_opens_a_block() -> None:
    text = "- [ ] a\n\nText\n\n  ```\n- [ ] im Code\n  ```\n- [ ] b\n"
    assert count_tasks(text)[:3] == (0, 0, 2)


def test_rule4_longer_fence_needs_an_equally_long_closing_fence() -> None:
    text = "````\n```\n- [ ] im Code\n````\n- [ ] draussen\n"
    assert count_tasks(text)[:3] == (0, 0, 1)


# --- Punkt 5: Task-Zeilen ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("- [ ] a", (0, 0, 1)),
        ("* [x] a", (1, 0, 0)),
        ("+ [X] a", (1, 0, 0)),
        ("1. [ ] a", (0, 0, 1)),
        ("12) [~] a", (0, 1, 0)),
        ("    - [ ] eingerückte Unteraufgabe", (0, 0, 1)),
        ("\t* [x] mit Tab", (1, 0, 0)),
        ("- [ ]ohne Leerzeichen", (0, 0, 1)),
        ("- T001 ohne Checkbox", (0, 0, 0)),
        ("- [] leer", (0, 0, 0)),
        ("- [y] anders", (0, 0, 0)),
        ("-[ ] ohne Aufzählungsabstand", (0, 0, 0)),
        ("Text [ ] kein Bullet", (0, 0, 0)),
    ],
)
def test_rule5_task_line_forms(line: str, expected: tuple[int, int, int]) -> None:
    assert count_tasks(line + "\n")[:3] == expected


def test_rule5_tasks_need_no_task_id() -> None:
    assert count_tasks("- [x] ohne ID\n- [ ] T001 mit ID\n")[:3] == (1, 0, 1)


# --- Punkt 6: „fertig“ an Station und Tasks -----------------------------------------------------


def test_rule6_finished_needs_stage_and_no_remaining_tasks() -> None:
    assert is_finished("deployed", 0, 0)
    assert not is_finished("deployed", 2, 0)
    assert not is_finished("verified", 0, 1)
    assert not is_finished("implementing", 0, 0)
    assert is_in_progress("deployed", 2, 0)
    assert is_in_progress("implementing", 0, 0)
    assert not is_in_progress("verified", 0, 0)
    assert not is_in_progress("tasked", 3, 0)


@pytest.mark.usefixtures("fixed_now")
def test_rule6_deployed_with_open_tasks_keeps_the_stage_but_counts_as_in_progress(
    board_repo: Path, cfg: EffectiveConfig
) -> None:
    before = build_board(board_repo, cfg)
    (board_repo / "specs" / "002-importer" / "tasks.md").write_text(
        "- [x] T001 a\n- [x] T002 b\n- [ ] T003 Rest\n", encoding="utf-8"
    )
    after = build_board(board_repo, cfg)
    item = spec_item(after, "002-importer")
    assert item["stage"] == "deployed"
    assert "finished_at" not in item and "lead_time_days" not in item
    assert after["metrics"]["done"] == before["metrics"]["done"] - 1
    assert after["metrics"]["in_progress"] == before["metrics"]["in_progress"] + 1


# --- Punkt 7: lokale Zeit mit Zone in --text ------------------------------------------------------


def test_rule7_local_stamp_shows_zone_offset() -> None:
    plus2 = timezone(timedelta(hours=2))
    assert local_stamp("2026-10-21T12:03:44Z", plus2) == "2026-10-21 14:03 UTC+02:00"
    minus330 = timezone(timedelta(hours=-3, minutes=-30))
    assert local_stamp("2026-10-21T12:00:00Z", minus330) == "2026-10-21 08:30 UTC-03:30"
    assert local_stamp("2026-10-21T12:00:00Z", UTC) == "2026-10-21 12:00 UTC"
    assert local_stamp("kaputt") == "kaputt"


@pytest.mark.usefixtures("fixed_now")
def test_rule7_text_header_uses_local_time(board_repo: Path, cfg: EffectiveConfig) -> None:
    doc = build_board(board_repo, cfg)
    assert doc["generated_at"] == "2026-10-10T11:00:00Z"
    text = render_text(doc, tz=timezone(timedelta(hours=2)))
    assert "Stand 2026-10-10 13:00 UTC+02:00" in text.splitlines()[0]
    assert datetime(2026, 10, 10, 11, tzinfo=UTC)  # Konsistenz der Annahme
