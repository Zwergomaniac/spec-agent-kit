"""Kein Projekt-Hardcode in Engine und Vorlagen (Spec 003 SC-004, Task T019, Constitution VIII)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
ENGINE_SRC = REPO_ROOT / "packages" / "engine" / "src" / "spec_agent_kit"
TEMPLATES = REPO_ROOT / "packages" / "agent-blueprint" / "templates"

FORBIDDEN = (
    "immoagent",
    "owner_id",
    "graphify",
    ".venv/scripts",
    "pythonioencoding",
    "bypasspermissions",
)
SUFFIXES = {".py", ".md", ".json", ".yml", ".yaml", ".toml", ".txt"}


def scanned_files() -> list[Path]:
    """Engine-Quellen, Vorlagen für Agents, Skill und Settings sowie die kommentierte config.yml.

    Die Beispiel-Configs unter ``templates/config/examples/`` gehören einem Projekt und sind
    ausgenommen.
    """
    files = [p for p in ENGINE_SRC.rglob("*") if p.suffix in SUFFIXES and p.is_file()]
    claude = TEMPLATES / "claude"
    if claude.is_dir():
        files += [p for p in claude.rglob("*") if p.is_file()]
    launchers = TEMPLATES / "spec-agent"
    if launchers.is_dir():  # Starter und gitignore (Spec 009)
        files += [p for p in launchers.rglob("*") if p.is_file()]
    files.append(TEMPLATES / "config" / "config.yml")
    return [f for f in files if "__pycache__" not in f.parts]


def test_scan_covers_engine_and_templates() -> None:
    files = scanned_files()
    assert any(p.name == "commands.py" for p in files)
    assert any(p.name == "config.yml" for p in files)
    assert {"sak", "sak.cmd"} <= {p.name for p in files}


@pytest.mark.parametrize("word", FORBIDDEN)
def test_forbidden_word_is_absent(word: str) -> None:
    hits = [
        str(p.relative_to(REPO_ROOT))
        for p in scanned_files()
        if word in p.read_text(encoding="utf-8").lower().replace("\\", "/")
    ]
    assert hits == []


def test_engine_has_no_interpreter_paths_or_shell_calls() -> None:
    for path in ENGINE_SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "shell=True" not in text, path.name
        assert "os.system" not in text, path.name
        assert "Scripts/python" not in text.replace("\\", "/"), path.name
