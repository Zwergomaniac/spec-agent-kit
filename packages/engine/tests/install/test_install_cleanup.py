"""Altes Gerüst entfernt, Init-Skill und Blueprint-AGENTS vorhanden (Spec 005 FR-010, T012/T013)."""

from __future__ import annotations

import re

from install_support import REAL_KIT_ROOT

from spec_agent_kit.install.kit import Kit


def test_legacy_scaffold_is_gone() -> None:
    assert not (REAL_KIT_ROOT / "scripts" / "init-project.mjs").exists()
    assert not (REAL_KIT_ROOT / "packages/agent-blueprint/templates/root").exists()
    package = (REAL_KIT_ROOT / "package.json").read_text(encoding="utf-8")
    assert "init-project" not in package


def test_init_skill_lives_in_the_kit_repo_and_is_not_a_template() -> None:
    skill = REAL_KIT_ROOT / ".claude/skills/sak-init/SKILL.md"
    text = skill.read_text(encoding="utf-8")
    frontmatter = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    assert frontmatter is not None
    assert 'name: "sak-init"' in frontmatter.group(1)
    for needle in ("sak init", "--apply", "doctor", "suggested_commit", "SAK_DASHBOARD_TOKEN"):
        assert needle in text.replace("SAK init", "sak init"), needle
    managed = Kit.at(REAL_KIT_ROOT).managed_files()
    assert not [p for p in managed if "sak-init" in p]  # kein Zielprojekt bekommt ihn


def test_blueprint_agents_file_describes_the_templates() -> None:
    text = (REAL_KIT_ROOT / "packages/agent-blueprint/AGENTS.md").read_text(encoding="utf-8")
    for needle in ("templates/claude/agents", "settings.fragment.json", "config.yml", ".sak-new"):
        assert needle in text, needle
    assert "Init-Skript" not in text
