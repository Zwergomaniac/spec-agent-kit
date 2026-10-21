"""Erkennung für ``sak init``: Playwright und pyproject.toml (Spec 011 US2, US4; T001, T003)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from install_support import REAL_KIT_ROOT, Sak, git, write

from spec_agent_kit.install import detect
from spec_agent_kit.install.kit import TEMPLATES_RELATIVE, Kit

DEV_EXTRA = (
    '[project]\nname = "x"\nversion = "0.0.1"\n'
    '[project.optional-dependencies]\ndev = ["pytest>=8", "ruff>=0.8"]\n'
)
DEV_GROUP = (
    '[project]\nname = "x"\nversion = "0.0.1"\n[dependency-groups]\ndev = ["pytest>=8", "ruff"]\n'
)


# --- Test-Artefakte (Playwright als Regel aus den Kit-Vorlagen) ---------------

RULES = json.loads(
    (REAL_KIT_ROOT / TEMPLATES_RELATIVE / "config" / "detectors.json").read_text(encoding="utf-8")
)["artifact_tools"]


def test_the_kit_ships_a_rule_for_playwright() -> None:
    (rule,) = RULES
    assert rule["id"] == "playwright" and "test-results/" in rule["artifacts"]


def test_artifact_tools_are_found_by_config_file_and_by_package_json(tmp_path: Path) -> None:
    write(tmp_path, "web/playwright.config.ts", "export default {}\n")
    write(
        tmp_path,
        "tools/package.json",
        json.dumps({"devDependencies": {"@playwright/test": "^1.50.0"}}),
    )
    write(tmp_path, "node_modules/x/playwright.config.js", "ignoriert\n")
    found = detect.detect_artifact_tools(tmp_path, RULES)
    assert [(f["directory"], f["evidence"]) for f in found] == [
        ("tools", "package.json"),
        ("web", "playwright.config.ts"),
    ]
    assert [e for f in found for e in f["entries"]] == [
        "tools/test-results/",
        "tools/playwright-report/",
        "web/test-results/",
        "web/playwright-report/",
    ]


def test_no_matching_tool_means_no_result(tmp_path: Path) -> None:
    write(tmp_path, "package.json", json.dumps({"dependencies": {"react": "^19"}}))
    assert detect.detect_artifact_tools(tmp_path, RULES) == []
    assert detect.detect_artifact_tools(tmp_path, []) == []


def test_init_suggests_clean_ignore_when_playwright_is_present(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    write(target, "playwright.config.ts", "export default {}\n")
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "playwright")
    code, plan = sak(*init_args)
    assert code == 0
    (suggestion,) = [s for s in plan["suggestions"] if s["kind"] == "clean_ignore"]
    assert suggestion["entries"] == ["test-results/", "playwright-report/"]
    assert "--clean-ignore test-results/" in suggestion["text"]
    assert any("VORSCHLAG" in line for line in plan["text"])
    # Ein Vorschlag schreibt nichts in die Config.
    assert not (target / ".spec-agent").exists()


def test_clean_ignore_option_is_written_to_the_config(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    write(target, "playwright.config.ts", "export default {}\n")
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "playwright")
    args = [*init_args, "--clean-ignore", "test-results/", "--clean-ignore", "playwright-report/"]
    code, plan = sak(*args)
    assert code == 0 and [s for s in plan["suggestions"] if s["kind"] == "clean_ignore"] == []
    code, _ = sak(*args, "--apply")
    assert code == 0
    config = yaml.safe_load((target / ".spec-agent" / "config.yml").read_text(encoding="utf-8"))
    assert config["guard"]["clean_ignore"] == ["test-results/", "playwright-report/"]


def test_init_without_playwright_has_no_clean_ignore_suggestion(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    code, plan = sak(*init_args)
    assert code == 0 and plan["suggestions"] == []


# --- pyproject.toml ----------------------------------------------------------


@pytest.mark.parametrize(
    ("content", "tool", "expected"),
    [
        (DEV_EXTRA, "pytest", {"where": "extra", "name": "dev"}),
        (DEV_GROUP, "pytest", {"where": "group", "name": "dev"}),
        (
            '[project]\nname = "x"\nversion = "1"\ndependencies = ["Pytest>=8"]\n',
            "pytest",
            {"where": "dependencies", "name": ""},
        ),
        (
            '[project]\nname = "x"\nversion = "1"\n[dependency-groups]\ntest = ["pytest"]\n',
            "pytest",
            {"where": "group", "name": "test"},
        ),
        (
            '[project]\nname = "x"\nversion = "1"\n'
            '[project.optional-dependencies]\ndev = ["pytest"]\n'
            '[dependency-groups]\ndev = ["pytest"]\n',
            "pytest",
            {"where": "group", "name": "dev"},  # die Gruppe gewinnt: uv run lädt sie ohne Zusatz
        ),
    ],
)
def test_analyze_pyproject(
    tmp_path: Path, content: str, tool: str, expected: dict[str, str]
) -> None:
    write(tmp_path, "pyproject.toml", content)
    assert detect.analyze_pyproject(tmp_path)[tool] == expected


def test_analyze_pyproject_tolerates_missing_or_broken_files(tmp_path: Path) -> None:
    assert detect.analyze_pyproject(tmp_path) == {}
    write(tmp_path, "pyproject.toml", "[project\nkaputt")
    assert detect.analyze_pyproject(tmp_path) == {}


def test_extra_suggestion_for_optional_dependencies(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", DEV_EXTRA)
    suggestion = detect.suggest_command("uv run pytest -q {paths}", tmp_path)
    assert suggestion is not None
    assert suggestion["suggested"] == "uv run --extra dev pytest -q {paths}"
    assert "optional-dependencies.dev" in suggestion["reason"]
    ruff = detect.suggest_command("uv run ruff check .", tmp_path)
    assert ruff is not None and ruff["suggested"] == "uv run --extra dev ruff check ."


def test_dev_group_needs_no_addition(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", DEV_GROUP)
    assert detect.suggest_command("uv run pytest -q", tmp_path) is None


def test_non_default_group_gets_a_group_flag(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname = "x"\nversion = "1"\n[dependency-groups]\ntest = ["pytest"]\n',
    )
    suggestion = detect.suggest_command("uv run pytest", tmp_path)
    assert suggestion is not None and suggestion["suggested"] == "uv run --group test pytest"


def test_commands_with_their_own_environment_choice_are_left_alone(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", DEV_EXTRA)
    for command in (
        "uv run --extra dev pytest",
        "uv run --with pytest pytest",
        "uv run --all-extras pytest",
        "pytest -q",
        "npm test",
        "uv run python -m build",
        "uv run mytool",
    ):
        assert detect.suggest_command(command, tmp_path) is None, command


def test_project_option_points_at_the_other_pyproject(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", DEV_GROUP)  # Wurzel: Gruppe
    write(tmp_path, "packages/engine/pyproject.toml", DEV_EXTRA)
    suggestion = detect.suggest_command("uv run --project packages/engine pytest -q", tmp_path)
    assert suggestion is not None
    assert suggestion["suggested"] == "uv run --extra dev --project packages/engine pytest -q"


def test_tool_of_understands_uv_options_and_python_modules() -> None:
    assert detect.tool_of("uv run --project packages/engine pytest -q") == "pytest"
    assert detect.tool_of("uv run python -m pytest -q") == "pytest"
    assert detect.tool_of("python -m ruff check .") == "ruff"
    assert detect.tool_of("pnpm -r test") == "pnpm"
    assert detect.tool_of("") is None


def test_init_plan_suggests_extra_for_a_dev_extra_project(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    write(target, "pyproject.toml", DEV_EXTRA)
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "extra")
    code, plan = sak(*init_args)
    assert code == 0
    commands = {s["command"]: s["suggested"] for s in plan["suggestions"] if s["kind"] == "command"}
    assert commands == {
        "uv run pytest -q {paths}": "uv run --extra dev pytest -q {paths}",
        "uv run pytest -q": "uv run --extra dev pytest -q",
        "uv run ruff check .": "uv run --extra dev ruff check .",
    }
    # Die übergebenen Befehle bleiben unverändert in der Config.
    code, _ = sak(*init_args, "--apply")
    assert code == 0
    config = yaml.safe_load((target / ".spec-agent" / "config.yml").read_text(encoding="utf-8"))
    assert config["commands"]["test_full"] == ["uv run pytest -q"]


def test_init_plan_is_quiet_for_the_dev_group_layout(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    write(target, "pyproject.toml", DEV_GROUP)
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "group")
    code, plan = sak(*init_args)
    assert code == 0 and plan["suggestions"] == []
