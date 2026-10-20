"""Gemeinsame Hilfen der Board-Tests (eigenes Modul, kein Namenskonflikt mit anderen conftest)."""

from __future__ import annotations

import importlib.util
import shutil
import stat
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "board_repo"
GOLDEN = FIXTURE_DIR / "expected_board.json"
NOW = datetime(2026, 10, 10, 11, 0, tzinfo=UTC)


def load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "board_repo_generate", FIXTURE_DIR / "generate.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def force_rmtree(path: Path) -> None:
    def _writable(func: Callable[..., Any], target: str, _exc: object) -> None:
        Path(target).chmod(stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onerror=_writable)
