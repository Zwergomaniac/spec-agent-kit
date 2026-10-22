"""Projektkonfiguration (Spec 004): Defaults, Kern-Schutz, Prüfung, Beispiele, CLI."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from spec_agent_kit import contracts
from spec_agent_kit.cli import find_root, main
from spec_agent_kit.config import (
    CORE_CLEAN_IGNORE,
    CORE_PROTECTED,
    ConfigError,
    NotInitializedError,
    build_effective,
    load_config,
    read_dashboard_key,
    schema_errors,
)
from spec_agent_kit.config.check import check, parse_frontmatter
from spec_agent_kit.config.defaults import default_agent_name

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = REPO_ROOT / "packages" / "agent-blueprint" / "templates" / "config"
ENGINE_SRC = REPO_ROOT / "packages" / "engine" / "src" / "spec_agent_kit"

MINIMAL: dict[str, Any] = {"schema": "sak.config/1", "project": {"key": "demo", "name": "Demo"}}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _agent(root: Path, name: str, model: str = "sonnet", effort: str | None = "medium") -> None:
    agents = root / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"name: {name}", f"model: {model}"]
    if effort is not None:
        lines.append(f"effort: {effort}")
    lines += ["---", "Prompt"]
    (agents / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


def _copilot_agent(root: Path, name: str, model: str = "gpt-5", effort: str | None = "medium") -> None:
    agents = root / ".github" / "copilot" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"name: {name}", f"model: {model}"]
    if effort is not None:
        lines.append(f"effort: {effort}")
    lines += ["---", "Prompt"]
    (agents / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


def _write_config(root: Path, config: dict[str, Any]) -> None:
    (root / ".spec-agent").mkdir(exist_ok=True)
    (root / ".spec-agent" / "config.yml").write_text(
        yaml.safe_dump(config, allow_unicode=True), encoding="utf-8"
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Git-Repo mit Branch main, Kit-Agents für builder und code_review."""
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "commit", "--allow-empty", "-m", "init")
    _agent(tmp_path, "sak-builder", "sonnet")
    _agent(tmp_path, "sak-code-reviewer", "opus")
    return tmp_path


def _no_ui(config: dict[str, Any]) -> dict[str, Any]:
    """Minimale Config mit abgeschaltetem ui_review (die Agents des Fixtures genügen)."""
    base = {**MINIMAL, "pipeline": {"roles": {"ui_review": {"enabled": False}}}, **config}
    return copy.deepcopy(base)


def _paths(result: dict[str, Any], key: str = "errors") -> list[str]:
    return [e["path"] for e in result[key]]


# ---------------------------------------------------------------------------
# Defaults und wirksame Config
# ---------------------------------------------------------------------------


def test_defaults_follow_spec(tmp_path: Path) -> None:
    data = build_effective(tmp_path, MINIMAL).data
    assert data["project"]["base_branch"] == "main"
    assert data["locale"] == "de"
    assert data["agent_environment"] == "claude"
    pipeline = data["pipeline"]
    assert (pipeline["max_rounds"], pipeline["idle_minutes"], pipeline["stale_hours"]) == (2, 60, 6)
    assert pipeline["branch_pattern"] == "{spec}"
    enabled = {role: cfg["enabled"] for role, cfg in pipeline["roles"].items()}
    assert enabled == {
        "builder": True,
        "code_review": True,
        "ui_review": True,
        "security_review": False,
        "docs": False,
        "integrator": False,
    }
    assert pipeline["roles"]["code_review"]["agent"] == "sak-code-reviewer"
    assert default_agent_name("ui_review") == "sak-ui-reviewer"
    assert data["stages"] == {"deployed": True, "verified": True}
    assert data["deploy"] == {"command": None, "methods": {}, "default": None}
    assert data["plugins"] == []
    dashboard = data["dashboard"]
    assert dashboard["token_env"] == "SAK_DASHBOARD_TOKEN"
    assert dashboard["share_commit_subjects"] is False
    assert dashboard["push"] == "manual"
    assert dashboard["auth"] == "key"


def test_roles_of_defaults_equal_vocabulary(tmp_path: Path) -> None:
    roles = build_effective(tmp_path, MINIMAL).data["pipeline"]["roles"]
    assert list(roles) == contracts.vocabulary()["role"]


def test_push_default_depends_on_url(tmp_path: Path) -> None:
    with_url = {**MINIMAL, "dashboard": {"url": "https://dash.example.org"}}
    assert build_effective(tmp_path, with_url).data["dashboard"]["push"] == "auto"
    explicit = {**MINIMAL, "dashboard": {"url": "https://dash.example.org", "push": "off"}}
    assert build_effective(tmp_path, explicit).data["dashboard"]["push"] == "off"


def test_dicts_merge_deeply_and_lists_replace(tmp_path: Path) -> None:
    raw = {
        **MINIMAL,
        "pipeline": {"roles": {"code_review": {"model": "sonnet"}}},
        "commands": {"test_fast": ["a", "b"]},
    }
    data = build_effective(tmp_path, raw).data
    assert data["pipeline"]["roles"]["code_review"]["model"] == "sonnet"
    assert data["pipeline"]["roles"]["code_review"]["agent"] == "sak-code-reviewer"
    assert data["commands"]["test_fast"] == ["a", "b"]
    assert data["commands"]["lint"] == []


def test_defaults_are_not_shared_between_calls(tmp_path: Path) -> None:
    first = build_effective(tmp_path, MINIMAL).data
    first["commands"]["lint"].append("x")
    assert build_effective(tmp_path, MINIMAL).data["commands"]["lint"] == []


@pytest.mark.parametrize("guard", [{}, {"protected_paths": []}, {"protected_paths": ["docs/"]}])
def test_core_protection_cannot_be_switched_off(tmp_path: Path, guard: dict[str, Any]) -> None:
    data = build_effective(tmp_path, {**MINIMAL, "guard": guard}).data
    protected = data["guard"]["protected_paths"]
    assert protected[: len(CORE_PROTECTED)] == list(CORE_PROTECTED)
    assert ".spec-agent/config.yml" in protected
    assert ".claude/agents/sak-*" in protected
    assert ".specify/memory/constitution.md" in protected
    assert data["guard"]["clean_ignore"][0] == ".spec-agent/state/"


def test_project_paths_extend_core_without_duplicates(tmp_path: Path) -> None:
    raw = {
        **MINIMAL,
        "guard": {
            "protected_paths": ["docs/", ".spec-agent/config.yml"],
            "clean_ignore": ["out/", ".spec-agent/state/"],
        },
    }
    guard = build_effective(tmp_path, raw).data["guard"]
    assert guard["protected_paths"] == [*CORE_PROTECTED, "docs/"]
    assert guard["clean_ignore"] == [*CORE_CLEAN_IGNORE, "out/"]


def test_load_config_reads_yaml_and_validates(tmp_path: Path) -> None:
    with pytest.raises(NotInitializedError):
        load_config(tmp_path)
    _write_config(tmp_path, MINIMAL)
    config = load_config(tmp_path)
    assert config.active_roles() == ["builder", "code_review", "ui_review"]
    assert config.role("builder")["model"] == "sonnet"
    _write_config(tmp_path, {**MINIMAL, "pipeline": {"max_rounds": 9}})
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_yaml_is_read_as_data_only(tmp_path: Path) -> None:
    (tmp_path / ".spec-agent").mkdir()
    path = tmp_path / ".spec-agent" / "config.yml"
    path.write_text("schema: !!python/object/apply:os.getcwd []\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML"):
        load_config(tmp_path)
    path.write_text("- eine\n- Liste\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Mapping"):
        load_config(tmp_path)


# ---------------------------------------------------------------------------
# Secrets (FR-006)
# ---------------------------------------------------------------------------


def test_dashboard_key_comes_from_env_or_key_file(tmp_path: Path) -> None:
    config = build_effective(tmp_path, {**MINIMAL, "dashboard": {"token_env": "MY_KEY"}})
    assert read_dashboard_key(tmp_path, config, env={}) is None
    (tmp_path / ".spec-agent").mkdir()
    (tmp_path / ".spec-agent" / "dashboard.key").write_text("aus-datei\n", encoding="utf-8")
    assert read_dashboard_key(tmp_path, config, env={}) == "aus-datei"
    assert read_dashboard_key(tmp_path, config, env={"MY_KEY": "aus-env"}) == "aus-env"
    assert read_dashboard_key(tmp_path, config, env={"SAK_DASHBOARD_TOKEN": "x"}) == "aus-datei"


def test_config_has_no_field_for_the_secret_itself() -> None:
    dashboard = contracts.load_schema("config")["properties"]["dashboard"]["properties"]
    assert set(dashboard) == {"url", "token_env", "push", "auth", "share_commit_subjects"}


# ---------------------------------------------------------------------------
# config check
# ---------------------------------------------------------------------------


def test_check_accepts_valid_setup(repo: Path) -> None:
    _write_config(repo, _no_ui({}))
    result = check(repo)
    assert result == {"ok": True, "errors": [], "warnings": []}


def test_check_accepts_valid_copilot_setup(repo: Path) -> None:
    _copilot_agent(repo, "sak-builder", model="sonnet")
    _copilot_agent(repo, "sak-code-reviewer", model="opus")
    config = _no_ui({"agent_environment": "copilot"})
    _write_config(repo, config)
    result = check(repo)
    assert result == {"ok": True, "errors": [], "warnings": []}


def test_check_unknown_key_suggests_correction(repo: Path) -> None:
    _write_config(
        repo, _no_ui({"pipeline": {"max_round": 2, "roles": {"ui_review": {"enabled": False}}}})
    )
    result = check(repo)
    assert result["ok"] is False
    [error] = result["errors"]
    assert error["path"] == "pipeline.max_round"
    assert error["suggestion"] == "max_rounds"
    assert "Tippfehler" in error["message"]


def test_check_unknown_role_suggests_vocabulary_role(repo: Path) -> None:
    config = _no_ui({})
    config["pipeline"]["roles"]["code_reviewer"] = {"enabled": True}
    _write_config(repo, config)
    [error] = check(repo)["errors"]
    assert error["path"] == "pipeline.roles.code_reviewer"
    assert error["suggestion"] == "code_review"


def test_check_frontmatter_mismatch_names_both_values(repo: Path) -> None:
    config = _no_ui({})
    config["pipeline"]["roles"]["code_review"] = {"model": "opus"}
    _agent(repo, "sak-code-reviewer", "sonnet")
    _write_config(repo, config)
    result = check(repo)
    assert result["ok"] is False
    [error] = result["errors"]
    assert error["path"] == "pipeline.roles.code_review.model"
    assert "'opus'" in error["message"]
    assert "'sonnet'" in error["message"]


def test_check_effort_mismatch(repo: Path) -> None:
    _agent(repo, "sak-builder", "sonnet", effort="high")
    _write_config(repo, _no_ui({}))
    assert _paths(check(repo)) == ["pipeline.roles.builder.effort"]


def test_check_missing_frontmatter_field_is_only_a_warning(repo: Path) -> None:
    _agent(repo, "sak-builder", "sonnet", effort=None)
    _write_config(repo, _no_ui({}))
    result = check(repo)
    assert result["ok"] is True
    assert _paths(result, "warnings") == ["pipeline.roles.builder.effort"]


def test_check_missing_agent_file(repo: Path) -> None:
    (repo / ".claude" / "agents" / "sak-builder.md").unlink()
    _write_config(repo, _no_ui({}))
    [error] = check(repo)["errors"]
    assert error["path"] == "pipeline.roles.builder.agent"
    assert "sak-builder.md" in error["message"]


def test_check_agent_without_frontmatter(repo: Path) -> None:
    (repo / ".claude" / "agents" / "sak-builder.md").write_text(
        "Kein Frontmatter", encoding="utf-8"
    )
    _write_config(repo, _no_ui({}))
    [error] = check(repo)["errors"]
    assert "Frontmatter" in error["message"]


def test_check_ui_review_active_without_ui_block(repo: Path) -> None:
    _agent(repo, "sak-ui-reviewer", "sonnet")
    _write_config(repo, MINIMAL)
    result = check(repo)
    assert result["ok"] is False
    assert _paths(result) == ["ui"]


def test_check_ui_review_active_with_ui_block_is_valid(repo: Path) -> None:
    _agent(repo, "sak-ui-reviewer", "sonnet")
    ui = {"command": "npx playwright test", "base_url": "http://127.0.0.1:5173"}
    _write_config(repo, {**MINIMAL, "ui": ui})
    assert check(repo)["ok"] is True


def test_check_ui_block_without_ui_review_warns(repo: Path) -> None:
    ui = {"command": "x", "base_url": "http://127.0.0.1:5173"}
    _write_config(repo, _no_ui({"ui": ui}))
    result = check(repo)
    assert result["ok"] is True
    assert _paths(result, "warnings") == ["ui"]


@pytest.mark.parametrize("role", ["builder", "code_review"])
def test_check_requires_builder_and_code_review(repo: Path, role: str) -> None:
    config = _no_ui({})
    config["pipeline"]["roles"][role] = {"enabled": False}
    _write_config(repo, config)
    assert _paths(check(repo)) == [f"pipeline.roles.{role}.enabled"]


def test_check_no_review_role_active_is_invalid(repo: Path) -> None:
    config = _no_ui({})
    config["pipeline"]["roles"]["code_review"] = {"enabled": False}
    config["pipeline"]["roles"]["security_review"] = {"enabled": False}
    _write_config(repo, config)
    result = check(repo)
    assert result["ok"] is False
    assert "pipeline.roles.code_review.enabled" in _paths(result)


def test_check_integrator_cannot_be_enabled(repo: Path) -> None:
    config = _no_ui({})
    config["pipeline"]["roles"]["integrator"] = {"enabled": True}
    _write_config(repo, config)
    result = check(repo)
    assert result["ok"] is False
    assert "pipeline.roles.integrator.enabled" in _paths(result)


def test_check_branch_pattern_needs_spec_placeholder(repo: Path) -> None:
    config = _no_ui({})
    config["pipeline"]["branch_pattern"] = "feature"
    _write_config(repo, config)
    assert _paths(check(repo)) == ["pipeline.branch_pattern"]


def test_check_base_branch_must_exist(repo: Path) -> None:
    config = _no_ui({})
    config["project"]["base_branch"] = "develop"
    _write_config(repo, config)
    [error] = check(repo)["errors"]
    assert error["path"] == "project.base_branch"
    assert "develop" in error["message"]


def test_check_reports_every_schema_error(repo: Path) -> None:
    config = {**MINIMAL, "pipeline": {"max_rounds": 9}, "dashboard": {"push": "always"}, "x": 1}
    _write_config(repo, config)
    result = check(repo)
    assert {"pipeline.max_rounds", "dashboard.push", "x"} <= set(_paths(result))
    push = next(e for e in result["errors"] if e["path"] == "dashboard.push")
    assert "auto, manual, off" in push["message"]


def test_check_without_config(tmp_path: Path) -> None:
    result = check(tmp_path)
    assert result["ok"] is False
    assert "nicht initialisiert" in result["errors"][0]["message"]


def test_check_writes_nothing(repo: Path) -> None:
    _write_config(repo, _no_ui({}))
    before = sorted(
        p.relative_to(repo).as_posix() for p in repo.rglob("*") if ".git" not in p.parts
    )
    check(repo)
    after = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*") if ".git" not in p.parts)
    assert before == after


def test_parse_frontmatter() -> None:
    assert parse_frontmatter("---\nmodel: opus\neffort: high\n---\nText") == {
        "model": "opus",
        "effort": "high",
    }
    assert parse_frontmatter("---\r\nmodel: opus\r\n---\r\nText") == {"model": "opus"}
    assert parse_frontmatter("Text ohne Frontmatter") is None
    assert parse_frontmatter("---\nmodel: [unvollständig\n---\n") is None


# ---------------------------------------------------------------------------
# Beispiel-Configs und Vorlage
# ---------------------------------------------------------------------------


def _example(name: str) -> dict[str, Any]:
    loaded = yaml.safe_load((TEMPLATES / "examples" / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


@pytest.mark.parametrize("name", ["immoagent.config.yml", "ai-forge.config.yml"])
def test_example_configs_are_valid(name: str, tmp_path: Path) -> None:
    raw = _example(name)
    assert contracts.validate_config(raw) == []
    config = build_effective(tmp_path, raw)
    assert config.active_roles()[:2] == ["builder", "code_review"]


def test_example_configs_pass_check_with_matching_agents(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "commit", "--allow-empty", "-m", "init")
    for name in ("immoagent.config.yml", "ai-forge.config.yml"):
        raw = _example(name)
        config = build_effective(tmp_path, raw)
        for role in config.active_roles():
            settings = config.role(role)
            _agent(tmp_path, settings["agent"], settings["model"], settings["effort"])
        _write_config(tmp_path, raw)
        assert check(tmp_path) == {"ok": True, "errors": [], "warnings": []}, name


def test_ai_forge_has_no_ui_review_and_review_is_code_review_only(tmp_path: Path) -> None:
    config = build_effective(tmp_path, _example("ai-forge.config.yml"))
    assert config.active_roles() == ["builder", "code_review"]
    assert config.data["commands"]["test_fast"] == ["uv run pytest -q {paths}"]
    assert config.data["deploy"]["command"] is None
    assert "ui" not in config.data


def test_immoagent_example_covers_inventory(tmp_path: Path) -> None:
    config = build_effective(tmp_path, _example("immoagent.config.yml")).data
    assert config["ui"]["viewports"]["mobile"] == [390, 844]
    assert any("owner_id" in rule for rule in config["review"]["rules"])
    assert any("migrations" in path for path in config["escalation"]["paths"])
    assert any("Drosselung" in topic for topic in config["escalation"]["topics"])
    deploy = config["deploy"]
    assert deploy["default"] == "github"
    assert deploy["methods"]["github"]["marker"] == "workflow"
    assert deploy["methods"]["local"]["local_only"] is True
    assert deploy["methods"]["local"]["marker"] == "agent"
    assert not any(".venv" in cmd for cmd in config["commands"]["test_fast"])


def test_template_is_valid_after_placeholder_substitution(tmp_path: Path) -> None:
    text = (TEMPLATES / "config.yml").read_text(encoding="utf-8")
    for placeholder, value in (
        ("__PROJECT_KEY__", "demo-app"),
        ("__PROJECT_NAME__", "Demo App"),
        ("__BASE_BRANCH__", "main"),
    ):
        assert placeholder in text
        text = text.replace(placeholder, value)
    raw = yaml.safe_load(text)
    assert contracts.validate_config(raw) == []
    data = build_effective(tmp_path, raw).data
    defaults = build_effective(tmp_path, {**MINIMAL, "project": raw["project"]}).data
    assert data["pipeline"]["roles"]["ui_review"]["enabled"] is False
    data["pipeline"]["roles"]["ui_review"]["enabled"] = True
    assert data == {**defaults, "orchestrator_only": ["deploy", "ssh"]}


def test_no_project_specific_values_in_engine_source() -> None:
    """Constitution VIII, Spec 004 SC-001: kein Projekt-Hardcode im Kern."""
    forbidden = ("immoagent", "owner_id", "playwright", "deploy-vps", "graphify", "ai-forge")
    for path in ENGINE_SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for word in forbidden:
            assert word not in text, f"{word} in {path.name}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_find_root_prefers_spec_agent_dir_then_git(repo: Path) -> None:
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    assert find_root(nested) == repo.resolve()
    inner = repo / "sub"
    (inner / ".spec-agent").mkdir(parents=True)
    assert find_root(inner) == inner.resolve()


def test_cli_without_config_is_rejected(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(repo)
    for command in ("show", "check"):
        assert main(["config", command]) == 1
        out = json.loads(capsys.readouterr().out)
        assert out["ok"] is False
        assert "nicht initialisiert" in out["errors"][0]["message"]


def test_cli_version_works_without_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["version"]) == 0
    assert "version" in json.loads(capsys.readouterr().out)


def test_cli_show_prints_effective_config(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_config(repo, {**MINIMAL, "guard": {"protected_paths": []}})
    monkeypatch.chdir(repo)
    assert main(["config", "show"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["guard"]["protected_paths"] == list(CORE_PROTECTED)
    assert out["pipeline"]["max_rounds"] == 2


def test_cli_check_exit_codes(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(repo)
    _write_config(repo, _no_ui({}))
    assert main(["config", "check"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    _write_config(repo, _no_ui({"pipeline": {"max_round": 2}}))
    assert main(["config", "check"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_config_requires_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["config"]) == 2
    capsys.readouterr()


def test_autonomy_defaults_are_strict(tmp_path: Path) -> None:
    """Spec 012 FR-001: ohne Angabe bleibt der Push manuell, Deploy nach OK, Remote origin."""
    config = build_effective(tmp_path, {"schema": "sak.config/1", "project": {}})
    assert config.data["autonomy"] == {
        "push": "manual",
        "deploy": "after_approval",
        "remote": "origin",
    }
    partial = build_effective(tmp_path, {"autonomy": {"push": "after_merge"}})
    assert partial.data["autonomy"] == {
        "push": "after_merge",
        "deploy": "after_approval",
        "remote": "origin",
    }


def test_immoagent_example_pushes_after_merge_and_template_keeps_the_default(
    tmp_path: Path,
) -> None:
    example = build_effective(tmp_path, _example("immoagent.config.yml")).data
    assert example["autonomy"]["push"] == "after_merge"
    assert build_effective(tmp_path, _example("ai-forge.config.yml")).data["autonomy"]["push"] == (
        "manual"
    )
    text = (TEMPLATES / "config.yml").read_text(encoding="utf-8")
    assert "# autonomy:" in text and "push: manual" in text


def test_invalid_autonomy_value_is_reported_with_the_allowed_values(tmp_path: Path) -> None:
    errors = schema_errors(
        {"schema": "sak.config/1", "project": {}, "autonomy": {"push": "always"}}
    )
    assert errors and errors[0]["path"] == "autonomy.push" and "after_merge" in errors[0]["message"]


# ---------------------------------------------------------------------------
# dashboard.auth (Spec 013)
# ---------------------------------------------------------------------------


def test_dashboard_auth_accepts_only_key_or_proxy() -> None:
    assert schema_errors({**MINIMAL, "dashboard": {"auth": "proxy"}}) == []
    assert schema_errors({**MINIMAL, "dashboard": {"auth": "key"}}) == []
    errors = schema_errors({**MINIMAL, "dashboard": {"auth": "token"}})
    assert [e["path"] for e in errors] == ["dashboard.auth"]


def test_resolve_auth_env_overrides_config(tmp_path: Path) -> None:
    from spec_agent_kit.config import AuthModeError, resolve_auth

    plain = build_effective(tmp_path, MINIMAL)
    assert resolve_auth(plain, {}) == ("key", "config")
    proxied = build_effective(tmp_path, {**MINIMAL, "dashboard": {"auth": "proxy"}})
    assert resolve_auth(proxied, {}) == ("proxy", "config")
    assert resolve_auth(proxied, {"SAK_DASHBOARD_AUTH": "key"}) == ("key", "env")
    assert resolve_auth(plain, {"SAK_DASHBOARD_AUTH": " proxy "}) == ("proxy", "env")
    assert resolve_auth(plain, {"SAK_DASHBOARD_AUTH": ""}) == ("key", "config")
    with pytest.raises(AuthModeError) as caught:
        resolve_auth(plain, {"SAK_DASHBOARD_AUTH": "sak_geheim"})
    assert "geheim" not in str(caught.value)
    assert "key" in str(caught.value) and "proxy" in str(caught.value)
