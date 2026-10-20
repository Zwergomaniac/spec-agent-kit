"""``sak config check``: prüft die Projektkonfiguration, bevor ein Lauf startet (Spec 004 FR-004).

Die Prüfung schreibt nichts. Ergebnis: ``{ok, errors[], warnings[]}``, je Eintrag ``path`` und
``message`` (bei Tippfehlern zusätzlich ``suggestion``).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from spec_agent_kit.config import (
    ConfigError,
    EffectiveConfig,
    NotInitializedError,
    build_effective,
    read_raw,
    schema_errors,
)

Issue = dict[str, str]

_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_CHECKED_FIELDS = ("model", "effort")


def parse_frontmatter(text: str) -> dict[str, Any] | None:
    """YAML zwischen den ersten beiden ``---``-Zeilen. ``None``, wenn keines vorhanden ist."""
    match = _FRONTMATTER.match(text.lstrip("﻿"))
    if match is None:
        return None
    try:
        loaded = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _branch_exists(root: Path, branch: str) -> bool | None:
    """``None``, wenn Git nicht verfügbar ist oder ``root`` kein Repository ist."""
    for ref in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"):
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", ref],
                cwd=root,
                capture_output=True,
                check=False,
            )
        except OSError:
            return None
        if result.returncode == 0:
            return True
    inside = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return False if inside.returncode == 0 else None


def _check_roles(
    root: Path, config: EffectiveConfig, errors: list[Issue], warnings: list[Issue]
) -> None:
    for role in config.active_roles():
        settings = config.role(role)
        where = f"pipeline.roles.{role}"
        agent_file = root / ".claude" / "agents" / f"{settings['agent']}.md"
        if not agent_file.is_file():
            errors.append(
                {
                    "path": f"{where}.agent",
                    "message": f"Agent-Datei fehlt: .claude/agents/{settings['agent']}.md",
                }
            )
            continue
        frontmatter = parse_frontmatter(agent_file.read_text(encoding="utf-8"))
        if frontmatter is None:
            errors.append(
                {
                    "path": f"{where}.agent",
                    "message": f"{agent_file.name} hat kein lesbares Frontmatter",
                }
            )
            continue
        for field in _CHECKED_FIELDS:
            wanted = str(settings[field])
            if field not in frontmatter:
                warnings.append(
                    {
                        "path": f"{where}.{field}",
                        "message": f"{agent_file.name} nennt kein {field} im Frontmatter",
                    }
                )
            elif str(frontmatter[field]) != wanted:
                errors.append(
                    {
                        "path": f"{where}.{field}",
                        "message": (
                            f"Abweichung: Config sagt '{wanted}', das Frontmatter von "
                            f"{agent_file.name} sagt '{frontmatter[field]}'"
                        ),
                    }
                )


def check(root: Path) -> dict[str, Any]:
    """Prüft ``<root>/.spec-agent/config.yml``. Schreibt nichts."""
    errors: list[Issue] = []
    warnings: list[Issue] = []
    try:
        raw = read_raw(root)
    except NotInitializedError as exc:
        return {"ok": False, "errors": exc.errors, "warnings": warnings}
    except ConfigError as exc:
        return {"ok": False, "errors": exc.errors, "warnings": warnings}

    errors.extend(schema_errors(raw))
    if errors:  # Weitere Prüfungen setzen eine gültige Form voraus.
        return {"ok": False, "errors": errors, "warnings": warnings}

    config = build_effective(root, raw)
    data = config.data

    active = config.active_roles()
    for required in ("builder", "code_review"):
        if required not in active:
            errors.append(
                {
                    "path": f"pipeline.roles.{required}.enabled",
                    "message": f"die Rolle {required} muss aktiv sein (mindestens builder und "
                    "code_review)",
                }
            )
    if "ui_review" in active and not isinstance(raw.get("ui"), dict):
        errors.append(
            {
                "path": "ui",
                "message": "ui_review ist aktiv, aber der Block ui fehlt "
                "(command und base_url sind nötig)",
            }
        )
    if "ui_review" not in active and "ui" in raw:
        warnings.append(
            {"path": "ui", "message": "der Block ui wird ignoriert, solange ui_review inaktiv ist"}
        )
    if "{spec}" not in data["pipeline"]["branch_pattern"]:
        errors.append(
            {
                "path": "pipeline.branch_pattern",
                "message": "das Muster muss den Platzhalter {spec} enthalten",
            }
        )

    _check_roles(root, config, errors, warnings)

    base_branch = data["project"]["base_branch"]
    exists = _branch_exists(root, base_branch)
    if exists is None:
        errors.append({"path": "project.base_branch", "message": "kein Git-Repository gefunden"})
    elif not exists:
        errors.append(
            {
                "path": "project.base_branch",
                "message": f"der Branch '{base_branch}' existiert nicht",
            }
        )

    return {"ok": not errors, "errors": errors, "warnings": warnings}
