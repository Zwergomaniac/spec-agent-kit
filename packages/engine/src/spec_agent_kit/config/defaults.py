"""Defaults und Kern-Schutz der Projektkonfiguration (Spec 004 FR-002, FR-003).

Hier stehen nur projektneutrale Werte. Alles Projektspezifische gehört in
``.spec-agent/config.yml``.
"""

from __future__ import annotations

from typing import Any, Final

SCHEMA_ID: Final[str] = "sak.config/1"
CONFIG_RELATIVE_PATH: Final[str] = ".spec-agent/config.yml"
DASHBOARD_KEY_RELATIVE_PATH: Final[str] = ".spec-agent/dashboard.key"

CORE_PROTECTED: Final[tuple[str, ...]] = (
    ".spec-agent/config.yml",
    ".spec-agent/engine/",
    ".spec-agent/lock.json",
    ".claude/agents/sak-*",
    ".claude/skills/sak-*",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".specify/memory/constitution.md",
)
"""Kern-Schutz: gilt immer, auch bei ``guard.protected_paths: []``."""

CORE_CLEAN_IGNORE: Final[tuple[str, ...]] = (".spec-agent/state/",)
"""Zählt nie für den sauberen Stand."""

ROLE_ORDER: Final[tuple[str, ...]] = (
    "builder",
    "code_review",
    "ui_review",
    "security_review",
    "docs",
    "integrator",
)
"""Reihenfolge der Rollen (entspricht der Ebene ``role`` im Vokabular)."""

_ROLE_DEFAULTS: Final[dict[str, tuple[bool, str]]] = {
    # Rolle: (aktiv, Modell)
    "builder": (True, "sonnet"),
    "code_review": (True, "opus"),
    "ui_review": (True, "sonnet"),
    "security_review": (False, "opus"),
    "docs": (False, "sonnet"),
    "integrator": (False, "sonnet"),
}

DEFAULT_EFFORT: Final[str] = "medium"


DEFAULT_AGENTS: Final[dict[str, str]] = {
    "builder": "sak-builder",
    "code_review": "sak-code-reviewer",
    "ui_review": "sak-ui-reviewer",
    "security_review": "sak-security-reviewer",
    "docs": "sak-docs",
    "integrator": "sak-integrator",
}
"""Dateinamen der Kit-Agents je Rolle (Spec 003 FR-013), ohne ``.md``."""


def default_agent_name(role: str) -> str:
    """Dateiname des Kit-Agents einer Rolle, zum Beispiel ``sak-code-reviewer``."""
    return DEFAULT_AGENTS[role]


def role_defaults() -> dict[str, dict[str, Any]]:
    """Defaults je Rolle: ``enabled``, ``agent``, ``model``, ``effort``."""
    return {
        role: {
            "enabled": enabled,
            "agent": default_agent_name(role),
            "model": model,
            "effort": DEFAULT_EFFORT,
        }
        for role, (enabled, model) in _ROLE_DEFAULTS.items()
    }


def defaults() -> dict[str, Any]:
    """Der vollständige Default-Baum (frische Kopie bei jedem Aufruf).

    ``dashboard.push`` fehlt bewusst: der Default hängt von ``dashboard.url`` ab.
    ``ui`` fehlt, solange es nicht konfiguriert ist.
    """
    return {
        "schema": SCHEMA_ID,
        "project": {"base_branch": "main"},
        "locale": "de",
        "pipeline": {
            "max_rounds": 2,
            "idle_minutes": 60,
            "stale_hours": 6,
            "branch_pattern": "{spec}",
            "roles": role_defaults(),
        },
        "stages": {"deployed": True, "verified": True},
        "commands": {
            "test_fast": [],
            "test_full": [],
            "lint": [],
            "prepare": [],
            "environment_failures": [],
        },
        "guard": {"protected_paths": [], "clean_ignore": []},
        "escalation": {"paths": [], "topics": []},
        "review": {"rules": []},
        "orchestrator_only": [],
        "deploy": {"command": None},
        "dashboard": {
            "url": None,
            "token_env": "SAK_DASHBOARD_TOKEN",
            "auth": "key",
            "share_commit_subjects": False,
        },
        "autonomy": {"push": "manual", "deploy": "after_approval", "remote": "origin"},
        "plugins": [],
    }
