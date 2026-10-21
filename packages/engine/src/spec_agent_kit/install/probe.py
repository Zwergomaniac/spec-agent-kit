"""Probe der Befehle aus ``commands.*`` für ``sak doctor`` (Spec 011 US4, US7).

Ohne ``--probe-commands`` prüft ``doctor`` nur, ob das Programm eines Befehls auffindbar ist. Mit
der Option laufen pytest-Befehle mit ``--collect-only -q`` (Timeout 60 s) und andere bekannte
Werkzeuge mit ``--version``. ``commands.prepare`` wird nie ausgeführt, weil Vorbereitungsbefehle
Dateien erzeugen. Es gibt keine Shell; zusammengesetzte Befehle (``&&``, ``|``) werden nicht
geprüft.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Final

from spec_agent_kit.install import detect
from spec_agent_kit.install.tools import find_uv

PROBE_TIMEOUT_SECONDS: Final[int] = 60
COMMAND_KINDS: Final[tuple[str, ...]] = ("test_fast", "test_full", "lint", "prepare")
VERSION_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "ruff",
        "mypy",
        "pyright",
        "black",
        "isort",
        "flake8",
        "eslint",
        "tsc",
        "prettier",
        "biome",
        "vitest",
        "jest",
        "uv",
        "pnpm",
        "npm",
        "npx",
        "yarn",
        "node",
        "python",
        "python3",
        "cargo",
        "go",
    }
)
_SHELL_WORDS: Final[frozenset[str]] = frozenset({"&&", "||", "|", ";", "&", ">", ">>", "<"})
_PLACEHOLDER = re.compile(r"\{paths\}")
_COLLECTED = re.compile(r"([0-9]+) tests? collected|([0-9]+)/[0-9]+ tests collected", re.IGNORECASE)
_PER_FILE = re.compile(r"^\S+: ([0-9]+)$", re.MULTILINE)

Item = dict[str, Any]


def _tokens(command: str) -> list[str]:
    """Befehl ohne ``{paths}``-Platzhalter in Wörtern."""
    return detect.split_command(_PLACEHOLDER.sub("", command))


def _resolve(program: str) -> str | None:
    """Pfad eines Programms; uv wird an den Orten des Starters gesucht."""
    if Path(program).stem.lower() == "uv" and not Path(program).parent.parts:
        return find_uv()
    return shutil.which(program)


def _environment() -> dict[str, str]:
    return {
        k: v for k, v in os.environ.items() if k not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"}
    }


def _run(argv: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=root,
        env=_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        timeout=PROBE_TIMEOUT_SECONDS,
        check=False,
    )


def _tail(proc: subprocess.CompletedProcess[str]) -> str:
    lines = [
        line.strip() for line in (proc.stderr or proc.stdout or "").splitlines() if line.strip()
    ]
    return " | ".join(lines[-3:])[:300]


def probe_command(root: Path, kind: str, command: str, *, run: bool) -> Item:
    """Prüft einen Befehl. ``run=False``: nur Auffindbarkeit des Programms."""
    item: Item = {"kind": kind, "command": command, "ok": True, "detail": ""}
    tokens = _tokens(command)
    if not tokens:
        return {**item, "ok": False, "detail": "leerer oder nicht lesbarer Befehl"}
    if any(t in _SHELL_WORDS for t in tokens):
        return {**item, "detail": "zusammengesetzter Befehl, nicht geprüft"}
    program = _resolve(tokens[0])
    if program is None:
        return {
            **item,
            "ok": False,
            "detail": f"Programm '{tokens[0]}' nicht gefunden (PATH der Sitzung prüfen)",
        }
    if not run:
        return {**item, "detail": f"Programm gefunden ({tokens[0]})"}
    if kind == "prepare":
        return {**item, "detail": "Programm gefunden; Vorbereitungsbefehle werden nicht ausgeführt"}
    parts = detect.uv_run_parts(tokens)
    tool_at = parts[1] if parts is not None else 0
    tool = detect.tool_of(command)
    argv = [program, *tokens[1:]]
    if tool == "pytest":
        return _probe_pytest(root, item, [*argv, "--collect-only", "-q"])
    if tool in VERSION_TOOLS:
        # Nur bis zum Werkzeug: `uv run ruff check .` -> `uv run ruff --version`.
        return _probe_version(root, item, [program, *tokens[1 : tool_at + 1], "--version"])
    return {**item, "detail": f"Programm gefunden; '{tool}' hat keine sichere Probe"}


def _probe_pytest(root: Path, item: Item, argv: list[str]) -> Item:
    try:
        proc = _run(argv, root)
    except subprocess.TimeoutExpired:
        return {
            **item,
            "ok": False,
            "detail": f"pytest --collect-only: länger als {PROBE_TIMEOUT_SECONDS} s",
        }
    except OSError as exc:
        return {**item, "ok": False, "detail": f"nicht ausführbar: {exc}"}
    if proc.returncode == 0:
        match = _COLLECTED.search(proc.stdout or "")
        count = next((g for g in (match.groups() if match else ()) if g), None)
        if count is None:  # doppeltes -q: nur Zahlen je Datei
            per_file = _PER_FILE.findall(proc.stdout or "")
            count = str(sum(int(n) for n in per_file)) if per_file else None
        detail = (
            f"pytest --collect-only: {count} Tests gesammelt"
            if count
            else "pytest --collect-only: ok"
        )
        return {**item, "detail": detail}
    if proc.returncode == 5:
        return {**item, "detail": "pytest --collect-only: keine Tests gesammelt (Exit 5)"}
    return {
        **item,
        "ok": False,
        "detail": f"pytest --collect-only endete mit Exit {proc.returncode}: {_tail(proc)}",
    }


def _probe_version(root: Path, item: Item, argv: list[str]) -> Item:
    try:
        proc = _run(argv, root)
    except subprocess.TimeoutExpired:
        return {**item, "ok": False, "detail": f"--version: länger als {PROBE_TIMEOUT_SECONDS} s"}
    except OSError as exc:
        return {**item, "ok": False, "detail": f"nicht ausführbar: {exc}"}
    if proc.returncode != 0:
        return {
            **item,
            "ok": False,
            "detail": f"--version endete mit Exit {proc.returncode}: {_tail(proc)}",
        }
    first = (proc.stdout or proc.stderr or "").strip().splitlines()
    return {**item, "detail": "--version: " + (first[0][:80] if first else "ok")}


def probe_commands(root: Path, commands: dict[str, Any], *, run: bool) -> list[Item]:
    """Alle konfigurierten Befehle (``test_fast``, ``test_full``, ``lint``, ``prepare``)."""
    items: list[Item] = []
    for kind in COMMAND_KINDS:
        values = commands.get(kind)
        for command in values if isinstance(values, list) else []:
            if isinstance(command, str) and command.strip():
                items.append(probe_command(root, kind, command, run=run))
    return items
