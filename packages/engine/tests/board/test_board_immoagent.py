"""Optionaler Test gegen die Specs eines echten Projekts (Spec 006 SC-001, T014).

Läuft nur mit ``SAK_IMMOAGENT_SPECS=<Pfad zum Projekt-Repo>``. Das Repo wird nur gelesen: das Board
entsteht über eine In-Memory-Config, nichts wird geschrieben (der Test prüft ``git status``).
"""

from __future__ import annotations

import os
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from spec_agent_kit import contracts
from spec_agent_kit.board.build import build_board
from spec_agent_kit.config import build_effective

ENV = "SAK_IMMOAGENT_SPECS"
pytestmark = pytest.mark.skipif(not os.environ.get(ENV), reason=f"{ENV} nicht gesetzt")


def _status(root: Path) -> str:
    done = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False
    )
    return done.stdout


def test_real_project_specs_give_a_valid_board_without_exception() -> None:
    root = Path(os.environ[ENV])
    if not (root / "specs").is_dir() and root.name == "specs":
        root = root.parent
    assert (root / "specs").is_dir(), f"{root}/specs fehlt"
    cfg = build_effective(
        root,
        {"schema": "sak.config/1", "project": {"key": "immo-agent", "name": "ImmoAgent"}},
    )
    before = _status(root)
    doc = build_board(root, cfg)
    assert contracts.validate_board(doc) == []
    assert doc["specs"], "keine Specs gefunden"
    assert _status(root) == before  # nur gelesen
    stages = Counter(s["stage"] for s in doc["specs"])
    print("\nSpecs:", len(doc["specs"]), "Stationen:", dict(stages))
    print("Hinweise:", doc["notes"])
