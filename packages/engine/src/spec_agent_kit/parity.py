"""Paritaetsbeschreibung fuer agentbezogene Faehigkeiten je Umgebung."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final


@dataclass(frozen=True)
class CapabilityParity:
    capability: str
    parity_level: str
    mechanism: str
    verification_expectation: str
    intentional_deviation: bool
    claude_mechanism: str
    copilot_mechanism: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_PARITY: Final[dict[str, tuple[CapabilityParity, ...]]] = {
    "claude": (
        CapabilityParity(
            capability="agents",
            parity_level="full",
            mechanism="native claude agent files under .claude/agents",
            verification_expectation="managed agent markdown files exist for active roles",
            intentional_deviation=False,
            claude_mechanism=".claude/agents/*.md",
            copilot_mechanism=".github/copilot/agents/*.md",
        ),
        CapabilityParity(
            capability="skills",
            parity_level="full",
            mechanism="native claude skill files under .claude/skills",
            verification_expectation="managed skill artifacts exist in the environment-specific skill location",
            intentional_deviation=False,
            claude_mechanism=".claude/skills/**",
            copilot_mechanism=".github/copilot/skills/*.md",
        ),
        CapabilityParity(
            capability="hooks",
            parity_level="full",
            mechanism="native claude hooks in .claude/settings.json",
            verification_expectation="required hook entries are present and doctor hook probe passes",
            intentional_deviation=False,
            claude_mechanism="hooks in .claude/settings.json",
            copilot_mechanism="VS-Code tasks in .vscode/tasks.json",
        ),
        CapabilityParity(
            capability="instructions",
            parity_level="full",
            mechanism="role instructions live in agent files",
            verification_expectation="managed instruction-bearing agent artifacts exist",
            intentional_deviation=False,
            claude_mechanism="frontmatter and body in .claude/agents/*.md",
            copilot_mechanism=".github/copilot/instructions.md plus agent files",
        ),
        CapabilityParity(
            capability="settings",
            parity_level="full",
            mechanism="merged claude settings fragment",
            verification_expectation="settings target exists and contains managed protection rules",
            intentional_deviation=False,
            claude_mechanism="merge into .claude/settings.json",
            copilot_mechanism="replace .vscode/settings.json",
        ),
    ),
    "copilot": (
        CapabilityParity(
            capability="agents",
            parity_level="approximate",
            mechanism="copilot agent markdown under .github/copilot/agents",
            verification_expectation="managed copilot agent files exist for active roles",
            intentional_deviation=True,
            claude_mechanism=".claude/agents/*.md",
            copilot_mechanism=".github/copilot/agents/*.md",
        ),
        CapabilityParity(
            capability="skills",
            parity_level="approximate",
            mechanism="copilot skill markdown under .github/copilot/skills",
            verification_expectation="managed copilot skill files exist in the skill location",
            intentional_deviation=True,
            claude_mechanism=".claude/skills/**",
            copilot_mechanism=".github/copilot/skills/*.md",
        ),
        CapabilityParity(
            capability="hooks",
            parity_level="approximate",
            mechanism="native integrated VS-Code tasks replace claude hook entries",
            verification_expectation=".vscode/tasks.json contains the required sak hook tasks and doctor reports the replacement explicitly",
            intentional_deviation=True,
            claude_mechanism="hooks in .claude/settings.json",
            copilot_mechanism="sak hook tasks in .vscode/tasks.json",
        ),
        CapabilityParity(
            capability="instructions",
            parity_level="approximate",
            mechanism="shared instructions file plus copilot agent files",
            verification_expectation=".github/copilot/instructions.md exists and managed agent files remain present",
            intentional_deviation=True,
            claude_mechanism="frontmatter and body in .claude/agents/*.md",
            copilot_mechanism=".github/copilot/instructions.md plus .github/copilot/agents/*.md",
        ),
        CapabilityParity(
            capability="settings",
            parity_level="approximate",
            mechanism="managed VS-Code settings file",
            verification_expectation=".vscode/settings.json exists and points to managed copilot artifacts",
            intentional_deviation=True,
            claude_mechanism="merge into .claude/settings.json",
            copilot_mechanism="replace .vscode/settings.json",
        ),
    ),
}


def parity_for(environment: str) -> list[dict[str, object]]:
    return [entry.to_dict() for entry in _PARITY[environment]]
