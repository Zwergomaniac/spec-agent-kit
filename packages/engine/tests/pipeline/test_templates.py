"""Vorlagen unter ``templates/claude/`` (Spec 003 FR-013 bis FR-015, Tasks T020 bis T023)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import Repo

from spec_agent_kit.cli import _build_parser
from spec_agent_kit.config.check import parse_frontmatter
from spec_agent_kit.config.defaults import DEFAULT_AGENTS, role_defaults

REPO_ROOT = Path(__file__).resolve().parents[4]
CLAUDE = REPO_ROOT / "packages" / "agent-blueprint" / "templates" / "claude"
AGENTS = CLAUDE / "agents"
SKILL = CLAUDE / "skills" / "sak-pipeline" / "SKILL.md"
FRAGMENT = CLAUDE / "settings.fragment.json"

AGENT_ROLES = {
    "sak-builder": "builder",
    "sak-code-reviewer": "code_review",
    "sak-ui-reviewer": "ui_review",
    "sak-security-reviewer": "security_review",
    "sak-docs": "docs",
}
REVIEWERS = ("sak-code-reviewer", "sak-ui-reviewer", "sak-security-reviewer")


def frontmatter(name: str) -> dict[str, Any]:
    parsed = parse_frontmatter((AGENTS / f"{name}.md").read_text(encoding="utf-8"))
    assert parsed is not None, name
    return parsed


def test_all_templates_exist() -> None:
    for name in AGENT_ROLES:
        assert (AGENTS / f"{name}.md").is_file(), name
    assert SKILL.is_file() and FRAGMENT.is_file()


def test_file_names_follow_the_role_table() -> None:
    for name, role in AGENT_ROLES.items():
        assert DEFAULT_AGENTS[role] == name


@pytest.mark.parametrize(("name", "role"), AGENT_ROLES.items())
def test_frontmatter_matches_the_config_defaults(name: str, role: str) -> None:
    fm = frontmatter(name)
    defaults = role_defaults()[role]
    assert fm["name"] == name
    assert fm["model"] == defaults["model"] and fm["effort"] == defaults["effort"]
    assert isinstance(fm["description"], str) and len(fm["description"]) > 40


@pytest.mark.parametrize("name", REVIEWERS)
def test_reviewers_may_only_read_and_run_bash(name: str) -> None:
    assert frontmatter(name)["tools"] == "Read, Grep, Glob, Bash"


@pytest.mark.parametrize("name", ["sak-builder", "sak-docs"])
def test_builders_have_no_tools_line(name: str) -> None:
    assert "tools" not in frontmatter(name)


@pytest.mark.parametrize("name", REVIEWERS)
def test_reviewers_use_the_verdict_format_and_the_config(name: str) -> None:
    text = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
    assert "Verdict: approve | changes_requested | needs_human" in text
    assert "[must]" in text and "[may]" in text
    assert "Urteil:" in text and "[Muss]" in text  # Hinweis auf die deutsche Form
    assert "SAK config show" in text
    assert "ändert nichts" in text or "änderst nichts" in text


def test_ui_reviewer_works_in_the_run_folder_only() -> None:
    text = (AGENTS / "sak-ui-reviewer.md").read_text(encoding="utf-8")
    assert ".spec-agent/state/runs/<run_id>/ui/" in text
    for key in ("ui.command", "ui.base_url", "ui.viewports", "ui.checks", "ui.regression_tests"):
        assert key in text


def test_builder_reads_commands_from_the_config() -> None:
    text = (AGENTS / "sak-builder.md").read_text(encoding="utf-8")
    for key in ("commands.test_fast", "commands.test_full", "commands.environment_failures"):
        assert key in text
    assert "{paths}" in text and "orchestrator_only" in text and "Co-Authored-By" in text


def test_docs_agent_only_touches_documentation() -> None:
    text = (AGENTS / "sak-docs.md").read_text(encoding="utf-8")
    assert "nur Doku-Dateien" in text


def test_templates_are_written_in_german() -> None:
    for name in AGENT_ROLES:
        text = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
        assert "Du bist die Station" in text, name
    assert "Du bist der **Orchestrator**" in SKILL.read_text(encoding="utf-8")


def test_unmodified_templates_pass_config_check(repo: Repo) -> None:
    for name in ("sak-builder", "sak-code-reviewer", "sak-ui-reviewer"):
        repo.write(f".claude/agents/{name}.md", (AGENTS / f"{name}.md").read_text("utf-8"))
    repo.commit("template agents")
    code, out = repo.sak("config", "check")
    assert code == 0, out


def test_optional_roles_pass_config_check_when_enabled(repo: Repo) -> None:
    for name in AGENT_ROLES:
        repo.write(f".claude/agents/{name}.md", (AGENTS / f"{name}.md").read_text("utf-8"))
    repo.set_config(
        pipeline={"roles": {"security_review": {"enabled": True}, "docs": {"enabled": True}}}
    )
    code, out = repo.sak("config", "check")
    assert code == 0, out


# --- Skill -----------------------------------------------------------------


def run_subcommands() -> set[str]:
    parser = _build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            run = action.choices["run"]
            for inner in run._actions:
                if isinstance(inner, argparse._SubParsersAction):
                    return set(inner.choices)
    raise AssertionError("keine run-Unterbefehle")


def test_skill_frontmatter() -> None:
    fm = parse_frontmatter(SKILL.read_text(encoding="utf-8"))
    assert fm is not None
    assert fm["name"] == "sak-pipeline" and fm["user-invocable"] is True


def test_skill_names_only_existing_commands() -> None:
    text = SKILL.read_text(encoding="utf-8")
    used = set(re.findall(r"SAK run ([a-z-]+)", text))
    assert used, "keine Befehle im Skill"
    assert used <= run_subcommands(), used - run_subcommands()
    # Jeder Schritt des Ablaufs kommt vor.
    for command in (
        "preflight",
        "state",
        "guard",
        "snapshot",
        "reviewer-check",
        "verdict",
        "combine",
        "merge",
        "pause",
        "resume",
        "release",
        "return",
        "abort",
    ):
        assert command in used, command
    assert set(re.findall(r"SAK config ([a-z]+)", text)) <= {"check", "show"}


def test_skill_covers_fr_014() -> None:
    text = SKILL.read_text(encoding="utf-8")
    for needle in (
        "ausdrückliche Freigabe",
        "genau diese",
        "Code schreibst du in diesem Ablauf **nicht** selbst",
        "in einer einzigen Nachricht",
        "SAK run pause",
        "stoppen und warten",
        "noch nicht deployt",
        "deploy.command",
        "deploy(NNN):",
        "--takeover",
        "--review-only",
        "kein Push",
    ):
        assert needle.lower() in text.lower(), needle


def test_skill_uses_the_engine_runner_and_not_a_fixed_interpreter() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "uv run --project .spec-agent/engine sak" in text
    assert "python" not in text.lower().replace("pythonic", "")


# --- settings.fragment.json -----------------------------------------------


def fragment() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(FRAGMENT.read_text(encoding="utf-8"))
    return loaded


def test_fragment_hooks() -> None:
    hooks = fragment()["hooks"]
    for event, phase in (("SubagentStart", "start"), ("SubagentStop", "stop")):
        (entry,) = hooks[event]
        assert entry["matcher"] == "sak-.*"
        (hook,) = entry["hooks"]
        assert hook["type"] == "command" and hook["timeout"] == 5
        assert hook["command"] == (
            'uv run --project "$CLAUDE_PROJECT_DIR/.spec-agent/engine" '
            f"sak hook subagent-{phase} || true"
        )


def test_fragment_permissions() -> None:
    permissions = fragment()["permissions"]
    allow, deny = permissions["allow"], permissions["deny"]
    assert "Bash(uv run --project .spec-agent/engine sak *)" in allow
    for verb in ("status", "diff", "log"):
        assert any(rule.startswith(f"Bash(git {verb}") for rule in allow), verb
    # Constitution IV: Merge und Branch-Wechsel nur über `sak run ...`; Subagents müssen nachfragen.
    for verb in ("switch", "merge"):
        assert not any(rule.startswith(f"Bash(git {verb}") for rule in allow), verb
    assert not any("push" in rule for rule in allow)
    assert "Bash(git push)" in deny and "Bash(git push *)" in deny
    assert any(".env" in rule and rule.startswith("Read(") for rule in deny)
    assert any(".env" in rule and rule.startswith("Edit(") for rule in deny)
    assert any("dashboard.key" in rule and rule.startswith("Read(") for rule in deny)
    assert any("dashboard.key" in rule and rule.startswith("Edit(") for rule in deny)


def test_fragment_sets_no_default_mode() -> None:
    data = fragment()
    assert "defaultMode" not in data.get("permissions", {})
    assert "defaultMode" not in data
    assert "bypassPermissions" not in FRAGMENT.read_text(encoding="utf-8")
