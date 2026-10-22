"""Agent-Umgebungen und ihre verwalteten Artefakte."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class AgentEnvironmentSpec:
    name: str
    agent_dir: str
    skills_dir: str
    instructions_path: str | None
    settings_path: str
    hook_target_path: str
    hook_mechanism: str
    settings_merge: bool


CLAUDE: Final[AgentEnvironmentSpec] = AgentEnvironmentSpec(
    name="claude",
    agent_dir=".claude/agents",
    skills_dir=".claude/skills",
    instructions_path=None,
    settings_path=".claude/settings.json",
    hook_target_path=".claude/settings.json",
    hook_mechanism="native",
    settings_merge=True,
)

COPILOT: Final[AgentEnvironmentSpec] = AgentEnvironmentSpec(
    name="copilot",
    agent_dir=".github/copilot/agents",
    skills_dir=".github/copilot/skills",
    instructions_path=".github/copilot/instructions.md",
    settings_path=".vscode/settings.json",
    hook_target_path=".vscode/tasks.json",
    hook_mechanism="native_integrated_tasks",
    settings_merge=False,
)

SPECS: Final[dict[str, AgentEnvironmentSpec]] = {
    CLAUDE.name: CLAUDE,
    COPILOT.name: COPILOT,
}


def get_agent_environment(name: str | None) -> AgentEnvironmentSpec:
    return SPECS.get(name or "claude", CLAUDE)
