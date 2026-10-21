"""Erkennung von Projekt-Eigenschaften für Vorschläge im ``sak init`` (Spec 011 US2, US4).

Alles hier liest nur und schlägt vor. Die Engine schreibt aus dem Ergebnis nichts ohne Zutun des
Betreibers (Constitution III). Projektspezifische Pfade stehen nie im Kern: erkannt werden nur
Werkzeug-Konventionen (Testwerkzeuge aus den Kit-Vorlagen, pyproject.toml).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

_SKIP_DIRS: Final[frozenset[str]] = frozenset({"node_modules", ".git", ".venv", "venv", "dist"})
_MAX_DEPTH: Final[int] = 3


# ---------------------------------------------------------------------------
# Test-Artefakte bekannter Werkzeuge (US2)
# ---------------------------------------------------------------------------
#
# Welche Werkzeuge es gibt und welche Ordner sie anlegen, steht nicht im Kern, sondern in den
# Vorlagen des Kits (``templates/config/detectors.json``, Constitution VIII). Hier steht nur die
# Suche.


def _package_matches(path: Path, packages: Sequence[str]) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    for section in ("dependencies", "devDependencies"):
        deps = data.get(section)
        if isinstance(deps, dict) and any(name in deps for name in packages):
            return True
    return False


def detect_artifact_tools(root: Path, rules: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Findet Werkzeuge mit eigenen Ausgabeordnern.

    Jede Regel nennt ``id``, ``label``, ``config_files`` (Glob-Muster), ``packages`` (Einträge in
    ``package.json``) und ``artifacts`` (Ordner relativ zum Fundort). Ergebnis je Fundort:
    ``{"id", "label", "directory", "evidence", "entries"}``; die Wurzel ist ``""``.
    """
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for current, dirs, files in os.walk(root):
        here = Path(current)
        relative = here.relative_to(root)
        depth = len(relative.parts)
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not d.startswith("."))
        if depth >= _MAX_DEPTH:
            dirs[:] = []
        directory = relative.as_posix() if depth else ""
        prefix = f"{directory}/" if directory else ""
        for rule in rules:
            key = (str(rule["id"]), directory)
            if key in found:
                continue
            evidence = next(
                (
                    name
                    for name in sorted(files)
                    if any(fnmatch.fnmatchcase(name, p) for p in rule.get("config_files", []))
                ),
                None,
            )
            if (
                evidence is None
                and "package.json" in files
                and _package_matches(here / "package.json", rule.get("packages", []))
            ):
                evidence = "package.json"
            if evidence is not None:
                found[key] = {
                    "id": str(rule["id"]),
                    "label": str(rule.get("label", rule["id"])),
                    "directory": directory,
                    "evidence": evidence,
                    "entries": [f"{prefix}{a}" for a in rule.get("artifacts", [])],
                }
    return sorted(found.values(), key=lambda f: (f["id"], f["directory"]))


# ---------------------------------------------------------------------------
# pyproject.toml (US4)
# ---------------------------------------------------------------------------

_TOOLS: Final[tuple[str, ...]] = ("pytest", "ruff")
_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_UV_VALUE_OPTIONS: Final[frozenset[str]] = frozenset(
    {
        "--project",
        "--directory",
        "--extra",
        "--group",
        "--only-group",
        "--no-group",
        "--with",
        "--with-requirements",
        "--python",
        "-p",
        "--package",
        "--env-file",
        "--index",
        "--index-url",
        "--find-links",
    }
)
_ENV_SELECTORS: Final[tuple[str, ...]] = (
    "--extra",
    "--all-extras",
    "--group",
    "--only-group",
    "--all-groups",
    "--with",
    "--no-project",
    "--isolated",
    "--script",
)


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_names(requirements: Any) -> set[str]:
    names: set[str] = set()
    for item in requirements if isinstance(requirements, list) else []:
        if isinstance(item, str) and (match := _REQ_NAME.match(item)):
            names.add(_normalize(match.group(1)))
    return names


def analyze_pyproject(directory: Path) -> dict[str, dict[str, str]]:
    """Wo stehen pytest und ruff? ``{"pytest": {"where": "extra", "name": "dev"}, ...}``.

    ``where`` ist ``dependencies``, ``group`` oder ``extra``. Steht ein Werkzeug an mehreren
    Stellen, gewinnt die Stelle, die ``uv run`` ohne Zusatz erreicht (Abhängigkeiten, dann die
    Standard-Gruppen, dann Extras).
    """
    path = directory / "pyproject.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    uv = data.get("tool", {}).get("uv", {}) if isinstance(data.get("tool"), dict) else {}
    default_groups = uv.get("default-groups", ["dev"]) if isinstance(uv, dict) else ["dev"]
    if not isinstance(default_groups, list):
        default_groups = ["dev"]
    found: dict[str, dict[str, str]] = {}
    for tool in _TOOLS:
        direct = tool in _requirement_names(project.get("dependencies"))
        groups = data.get("dependency-groups")
        group_hits = [
            str(name)
            for name, requirements in (groups.items() if isinstance(groups, dict) else [])
            if tool in _requirement_names(requirements)
        ]
        extras = project.get("optional-dependencies")
        extra_hits = [
            str(name)
            for name, requirements in (extras.items() if isinstance(extras, dict) else [])
            if tool in _requirement_names(requirements)
        ]
        if direct:
            found[tool] = {"where": "dependencies", "name": ""}
        elif any(g in default_groups for g in group_hits):
            found[tool] = {
                "where": "group",
                "name": next(g for g in group_hits if g in default_groups),
            }
        elif extra_hits:
            found[tool] = {"where": "extra", "name": extra_hits[0]}
        elif group_hits:
            found[tool] = {"where": "group", "name": group_hits[0]}
    return found


def split_command(command: str) -> list[str]:
    """Zerlegt einen Befehl in Wörter (ohne Shell); ``[]`` bei unbalancierten Anführungszeichen."""
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return []


def uv_run_parts(tokens: Sequence[str]) -> tuple[list[str], int] | None:
    """Für ``uv run [Optionen] Werkzeug …``: ``(Optionen, Index des Werkzeugs)``, sonst ``None``."""
    if len(tokens) < 3 or Path(tokens[0]).stem.lower() != "uv" or tokens[1] != "run":
        return None
    index = 2
    while index < len(tokens) and tokens[index].startswith("-"):
        option = tokens[index]
        if "=" not in option and option in _UV_VALUE_OPTIONS:
            index += 1
        index += 1
    if index >= len(tokens):
        return None
    return list(tokens[2:index]), index


def tool_of(command: str) -> str | None:
    """Das Werkzeug eines Befehls: bei ``uv run …`` das Programm danach, sonst das erste Wort.

    ``python -m pytest`` ergibt ``pytest``.
    """
    tokens = split_command(command)
    if not tokens:
        return None
    parts = uv_run_parts(tokens)
    start = parts[1] if parts else 0
    word = Path(tokens[start]).stem.lower()
    if word in {"python", "python3", "py"}:
        if len(tokens) > start + 2 and tokens[start + 1] == "-m":
            return tokens[start + 2].lower()
        return word
    return word


_UV_RUN = re.compile(r"^(\s*\S*uv(?:[.]exe)?\s+run)(?=\s|$)", re.IGNORECASE)


def suggest_command(command: str, root: Path) -> dict[str, str] | None:
    """Ein Vorschlag, wenn ``uv run <pytest|ruff>`` das Werkzeug nicht erreicht (Spec 011 US4).

    Gibt ``None`` zurück, wenn der Befehl passt oder nicht beurteilbar ist.
    """
    tokens = split_command(command)
    parts = uv_run_parts(tokens)
    if parts is None:
        return None
    options = parts[0]
    tool = tool_of(command)
    if tool not in _TOOLS:
        return None
    if any(o.split("=", 1)[0] in _ENV_SELECTORS for o in options):
        return None
    directory = root
    for position, option in enumerate(options):
        if option.split("=", 1)[0] in {"--project", "--directory"}:
            if "=" in option:
                value = option.split("=", 1)[1]
            else:
                value = options[position + 1] if position + 1 < len(options) else ""
            if value:
                directory = (root / value).resolve()
    where = analyze_pyproject(directory).get(tool)
    if where is None or where["where"] == "dependencies":
        return None
    if where["where"] == "group":
        if where["name"] in _uv_default_groups(directory):
            return None
        flag = f"--group {where['name']}"
        reason = f"{tool} steht in der Gruppe '{where['name']}', die uv run nicht automatisch lädt"
    else:
        flag = f"--extra {where['name']}"
        reason = f"{tool} steht in optional-dependencies.{where['name']}, nicht in einer Gruppe"
    suggested, count = _UV_RUN.subn(lambda m: f"{m.group(1)} {flag}", command, count=1)
    if count == 0:
        return None
    return {"command": command, "suggested": suggested, "reason": reason}


def _uv_default_groups(directory: Path) -> list[str]:
    try:
        data = tomllib.loads((directory / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["dev"]
    groups = data.get("tool", {}).get("uv", {}).get("default-groups", ["dev"])
    return [g for g in groups if isinstance(g, str)] if isinstance(groups, list) else ["dev"]
