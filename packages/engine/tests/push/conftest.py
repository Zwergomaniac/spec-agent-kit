"""Fixtures der Push-Tests: ein Wegwerf-Projekt und der lokale Test-Server."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from push_support import FakeDashboard, write_config


@pytest.fixture
def dashboard() -> Iterator[FakeDashboard]:
    server = FakeDashboard().start()
    yield server
    server.stop()


@pytest.fixture
def project(tmp_path: Path, dashboard: FakeDashboard, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    write_config(root, dashboard.url)
    monkeypatch.chdir(root)
    return root
