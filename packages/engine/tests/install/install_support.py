"""Fixture-Generatoren der Installations-Tests (Spec 005, T004).

Alle Tests laufen nur gegen Wegwerf-Repos in ``tmp_path``, nie gegen echte Projekte.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from spec_agent_kit.install.kit import ENGINE_RELATIVE, TEMPLATES_RELATIVE, Kit

Sak = Callable[..., tuple[int, dict[str, Any]]]
"""Aufruf von ``sak``: ``(exit, json)``."""

REAL_KIT_ROOT = Path(__file__).resolve().parents[4]

SPECKIT_OPTIONS: dict[str, Any] = {
    "ai": "claude",
    "ai_skills": True,
    "here": True,
    "integration": "claude",
    "speckit_version": "0.12.16",
}

OWN_AGENT = (
    "---\nname: code-executor\ndescription: Eigener Agent des Zielprojekts\nmodel: sonnet\n---\n"
    "Setzt Aufgaben um.\n"
)

OWN_SETTINGS: dict[str, Any] = {
    "permissions": {
        "allow": ["Bash(uv run pytest -q)", "Bash(git status)"],
        "defaultMode": "acceptEdits",
    },
    "hooks": {
        "SessionStart": [
            {"hooks": [{"type": "command", "command": "echo Willkommen im Projekt", "timeout": 5}]}
        ]
    },
    "env": {"PROJECT_MODE": "dev"},
}


def git(path: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
        cwd=path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return out.stdout


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def make_target(
    base: Path,
    *,
    name: str = "ai-forge-like",
    settings: dict[str, Any] | None = OWN_SETTINGS,
    speckit: dict[str, Any] | None = SPECKIT_OPTIONS,
    commit: bool = True,
) -> Path:
    """Ein Ziel-Repo, das AI-Forge ähnelt: spec-kit-Attrappe, eigener Agent, eigener Hook."""
    root = base / name
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    if speckit is not None:
        write(root, ".specify/init-options.json", json.dumps(speckit, indent=2) + "\n")
    write(root, ".claude/agents/code-executor.md", OWN_AGENT)
    if settings is not None:
        write(root, ".claude/settings.json", json.dumps(settings, indent=2) + "\n")
    write(root, ".gitignore", ".venv/\n__pycache__/\n")
    write(root, "README.md", "# Beispielprojekt\n")
    write(root, "pyproject.toml", '[project]\nname = "beispiel"\nversion = "0.0.1"\n')
    write(root, "src/app.py", "def main() -> None:\n    print('hallo')\n")
    if commit:
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "Ausgangsstand")
    return root


def snapshot(root: Path) -> dict[str, bytes]:
    """Alle Dateien außer ``.git`` (für 'es wurde nichts geschrieben')."""
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


def make_kit(base: Path, name: str = "kit") -> Kit:
    """Eine Kopie von Vorlagen und Engine als veränderbares Kit (Version, Vorlagen anpassbar)."""
    root = base / name
    ignore = shutil.ignore_patterns(".venv", "__pycache__", ".ruff_cache", ".pytest_cache")
    shutil.copytree(REAL_KIT_ROOT / TEMPLATES_RELATIVE, root / TEMPLATES_RELATIVE, ignore=ignore)
    shutil.copytree(
        REAL_KIT_ROOT / ENGINE_RELATIVE,
        root / ENGINE_RELATIVE,
        ignore=shutil.ignore_patterns(
            ".venv", "__pycache__", ".ruff_cache", ".pytest_cache", "tests"
        ),
    )
    return Kit.at(root)


def bump_version(kit: Kit, version: str) -> Kit:
    init = kit.root / ENGINE_RELATIVE / "src" / "spec_agent_kit" / "__init__.py"
    init.write_text(f'"""Kit."""\n\n__version__ = "{version}"\n', encoding="utf-8", newline="\n")
    return Kit.at(kit.root)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
