"""Fixtures der Installations-Tests: Ziel-Repo, Kit-Kopie und ``sak``-Aufruf."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from install_support import Sak, make_kit, make_target

from spec_agent_kit.cli import main
from spec_agent_kit.install import kit as kit_module
from spec_agent_kit.install.kit import Kit


@pytest.fixture
def kit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Kit:
    """Eine Kit-Kopie, die ``locate_kit()`` des CLI liefert."""
    copy = make_kit(tmp_path)
    monkeypatch.setattr(kit_module, "kit_root", lambda: copy.root)
    return copy


@pytest.fixture
def target(tmp_path: Path) -> Path:
    return make_target(tmp_path)


@pytest.fixture
def sak(capsys: pytest.CaptureFixture[str]) -> Sak:
    """Ruft ``sak`` auf und gibt ``(exit, json)`` zurück."""

    def run(*argv: str) -> tuple[int, dict[str, Any]]:
        capsys.readouterr()
        code = main(list(argv))
        out = capsys.readouterr().out.strip()
        return code, json.loads(out) if out else {}

    return run


@pytest.fixture
def init_args(target: Path) -> list[str]:
    return [
        "init",
        str(target),
        "--key",
        "ai-forge",
        "--name",
        "AI-Forge",
        "--no-ui",
        "--test-fast",
        "uv run pytest -q {paths}",
        "--test-full",
        "uv run pytest -q",
        "--lint",
        "uv run ruff check .",
        "--no-sync",
    ]
