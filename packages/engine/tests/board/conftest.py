"""Fixtures für die Board-Tests: das deterministische Fixture-Repo (T001) und eine feste Uhr."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pytest
from board_support import NOW, load_generator

from spec_agent_kit.config import EffectiveConfig, load_config
from spec_agent_kit.pipeline import runs

generator = load_generator()


@pytest.fixture(scope="session")
def board_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return generator.build_fixture_repo(tmp_path_factory.mktemp("board") / "repo")


@pytest.fixture
def board_repo(board_template: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "work"
    shutil.copytree(board_template, target)
    monkeypatch.chdir(target)
    return target


@pytest.fixture
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Feste „aktuelle“ Zeit; Tests dürfen ``runs.utcnow`` weiter überschreiben."""
    monkeypatch.setattr(runs, "utcnow", lambda: NOW)
    return NOW


@pytest.fixture
def cfg(board_repo: Path) -> EffectiveConfig:
    return load_config(board_repo)


@pytest.fixture
def web_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Eine kleine „gebaute UI“ (Strang B liefert die echte nach ``board/web/``)."""
    target = tmp_path / "web"
    (target / "assets").mkdir(parents=True)
    (target / "index.html").write_text(
        '<!doctype html><title>Board</title><script type="module" src="./assets/app.js"></script>',
        encoding="utf-8",
    )
    (target / "assets" / "app.js").write_text("console.log('board')\n", encoding="utf-8")
    (target / "assets" / "app.css").write_text("body{margin:0}\n", encoding="utf-8")
    monkeypatch.setattr("spec_agent_kit.board.serve.WEB_DIR", target)
    return target
