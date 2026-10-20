"""``sak board [--json|--text]`` und ``render_text`` (Spec 006 US1/US2, T006)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_agent_kit import contracts
from spec_agent_kit.board.build import build_board
from spec_agent_kit.board.text import TEXT_LINE_LIMIT, render_text
from spec_agent_kit.cli import main
from spec_agent_kit.config import EffectiveConfig, load_config


@pytest.mark.usefixtures("fixed_now", "board_repo")
def test_board_json_is_valid_and_includes_commit_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["board"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert contracts.validate_board(doc) == []
    assert any("text" in t for t in doc["ticker"])  # lokal wird der Betreff immer gezeigt
    assert main(["board", "--json"]) == 0


@pytest.mark.usefixtures("fixed_now", "board_repo")
def test_board_text_has_at_most_40_lines(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["board", "--text"]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert 5 < len(lines) <= TEXT_LINE_LIMIT
    assert "Wartet auf dich (4):" in out
    assert "[Eskaliert] 003-search" in out
    assert "003-search · Umsetzung · 3/5" in out


@pytest.mark.usefixtures("fixed_now")
def test_text_is_shortened_to_40_lines_for_big_projects(
    board_repo: Path, cfg: EffectiveConfig
) -> None:
    for number in range(10, 70):
        folder = board_repo / "specs" / f"{number:03d}-extra-{number}"
        folder.mkdir()
        (folder / "spec.md").write_text(f"# Spec {number}\n", encoding="utf-8")
        (folder / "tasks.md").write_text("- [x] a\n- [ ] b\n- [ ] c [operator]\n", encoding="utf-8")
    doc = build_board(board_repo, cfg)
    text = render_text(doc)
    assert len(text.splitlines()) <= TEXT_LINE_LIMIT
    assert "weitere" in text


def test_json_and_text_are_mutually_exclusive(board_repo: Path) -> None:
    assert main(["board", "--json", "--text"]) == 2


def test_board_without_init_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["board"]) == 1
    assert "nicht initialisiert" in capsys.readouterr().out


@pytest.mark.usefixtures("fixed_now", "board_repo")
def test_invalid_board_is_an_error_with_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("spec_agent_kit.board.build.__version__", "")
    assert main(["board"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and out["errors"][0]["path"] == "kit_version"


@pytest.mark.usefixtures("fixed_now")
def test_board_does_not_write_into_the_repo(board_repo: Path) -> None:
    before = sorted(
        p.relative_to(board_repo).as_posix() for p in board_repo.rglob("*") if ".git" not in p.parts
    )
    cfg = load_config(board_repo)
    build_board(board_repo, cfg)
    after = sorted(
        p.relative_to(board_repo).as_posix() for p in board_repo.rglob("*") if ".git" not in p.parts
    )
    assert before == after
