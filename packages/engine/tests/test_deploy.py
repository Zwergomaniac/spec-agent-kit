"""Deploy-Wege (Spec 014): Config-Normalisierung, ``config check`` und ``sak deploy plan``."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from spec_agent_kit.cli import main
from spec_agent_kit.config import ConfigError, build_effective, load_config
from spec_agent_kit.config.check import check
from spec_agent_kit.push.cloud import detect_environment

MINIMAL: dict[str, Any] = {
    "schema": "sak.config/1",
    "project": {"key": "demo", "name": "Demo"},
    "pipeline": {"roles": {"ui_review": {"enabled": False}}},
}
TWO_WAYS: dict[str, Any] = {
    "methods": {
        "github": {"command": "gh run --spec {spec}", "marker": "workflow"},
        "local": {"command": "bash deploy.sh {spec}", "marker": "agent", "local_only": True},
    },
    "default": "github",
}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _agent(root: Path, name: str, model: str) -> None:
    agents = root / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    text = f"---\nname: {name}\nmodel: {model}\neffort: medium\n---\nPrompt"
    (agents / f"{name}.md").write_text(text, encoding="utf-8")


def _write(root: Path, deploy: dict[str, Any] | None, **extra: Any) -> None:
    config = {**MINIMAL, **extra}
    if deploy is not None:
        config["deploy"] = deploy
    (root / ".spec-agent").mkdir(exist_ok=True)
    (root / ".spec-agent" / "config.yml").write_text(
        yaml.safe_dump(config, allow_unicode=True), encoding="utf-8"
    )


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HTTPS_PROXY", "https_proxy", "SAK_ENVIRONMENT"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "commit", "--allow-empty", "-m", "init")
    _agent(tmp_path, "sak-builder", "sonnet")
    _agent(tmp_path, "sak-code-reviewer", "opus")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _plan(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, Any]]:
    capsys.readouterr()
    code = main(["deploy", "plan", *argv])
    return code, json.loads(capsys.readouterr().out)


# ---------------------------------------------------------------------------
# Normalisierung
# ---------------------------------------------------------------------------


def test_old_form_becomes_default_method_with_agent_marker(tmp_path: Path) -> None:
    config = build_effective(tmp_path, {**MINIMAL, "deploy": {"command": "make deploy {spec}"}})
    deploy = config.data["deploy"]
    assert deploy["default"] == "default"
    assert deploy["methods"] == {
        "default": {"command": "make deploy {spec}", "marker": "agent", "local_only": False}
    }
    assert deploy["command"] == "make deploy {spec}"


def test_no_deploy_means_no_methods(tmp_path: Path) -> None:
    deploy = build_effective(tmp_path, MINIMAL).data["deploy"]
    assert deploy == {"command": None, "methods": {}, "default": None}


def test_methods_get_defaults(tmp_path: Path) -> None:
    raw = {**MINIMAL, "deploy": {"methods": {"only": {"command": "x"}}}}
    deploy = build_effective(tmp_path, raw).data["deploy"]
    assert deploy["methods"]["only"] == {"command": "x", "marker": "agent", "local_only": False}
    assert deploy["default"] == "only"
    assert deploy["command"] is None


# ---------------------------------------------------------------------------
# config check (SC-002)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("deploy", "path"),
    [
        ({"command": "x", "methods": {"a": {"command": "y"}}, "default": "a"}, "deploy.command"),
        ({"methods": {"a": {"command": "y"}}, "default": "b"}, "deploy.default"),
        ({"methods": {"a": {"command": "y"}, "b": {"command": "z"}}}, "deploy.default"),
        ({"command": "x", "default": "default"}, "deploy.default"),
        ({"methods": {"A b": {"command": "y"}}}, "deploy.methods.A b"),
        ({"methods": {"a": {"command": "y", "marker": "both"}}}, "deploy.methods.a.marker"),
        ({"methods": {"a": {"marker": "agent"}}}, "deploy.methods.a"),
        ({"methods": {"a": {"command": "y", "local": True}}}, "deploy.methods.a.local"),
    ],
)
def test_check_rejects_invalid_deploy(repo: Path, deploy: dict[str, Any], path: str) -> None:
    _write(repo, deploy)
    result = check(repo)
    assert result["ok"] is False
    assert path in [e["path"] for e in result["errors"]]
    with pytest.raises(ConfigError):
        load_config(repo)


@pytest.mark.parametrize(
    "deploy",
    [None, {"command": None}, {"command": "x"}, TWO_WAYS, {"methods": {"a": {"command": "y"}}}],
)
def test_check_accepts_valid_deploy(repo: Path, deploy: dict[str, Any] | None) -> None:
    _write(repo, deploy)
    assert check(repo) == {"ok": True, "errors": [], "warnings": []}


# ---------------------------------------------------------------------------
# Umgebung
# ---------------------------------------------------------------------------


def test_environment_heuristic_and_override() -> None:
    assert detect_environment({}) == ("local", "heuristic")
    assert detect_environment({"HTTPS_PROXY": "http://p"}) == ("cloud", "heuristic")
    assert detect_environment({"HTTPS_PROXY": "http://p", "SAK_ENVIRONMENT": "local"}) == (
        "local",
        "env",
    )
    assert detect_environment({"SAK_ENVIRONMENT": "cloud"}) == ("cloud", "env")
    with pytest.raises(ValueError, match="SAK_ENVIRONMENT"):
        detect_environment({"SAK_ENVIRONMENT": "mars"})


# ---------------------------------------------------------------------------
# sak deploy plan (SC-001)
# ---------------------------------------------------------------------------


def test_plan_uses_default_method(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, TWO_WAYS)
    code, out = _plan(capsys, "84")
    assert code == 0
    assert out["method"] == "github"
    assert out["command"] == "gh run --spec 084"
    assert out["marker"] == "workflow"
    assert out["allowed"] is True
    assert out["reason"] is None


def test_plan_named_method_local(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, TWO_WAYS)
    code, out = _plan(capsys, "--method", "local", "084-some-slug")
    assert code == 0
    assert (out["method"], out["marker"], out["allowed"]) == ("local", "agent", True)
    assert out["command"] == "bash deploy.sh 084"


def test_plan_unknown_method(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, TWO_WAYS)
    code, out = _plan(capsys, "--method", "ftp", "084")
    assert code == 1
    assert out["ok"] is False
    assert out["known"] == ["github", "local"]


def test_plan_local_only_refused_in_cloud(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, TWO_WAYS)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")
    code, out = _plan(capsys, "--method", "local", "084")
    assert code == 1
    assert out["allowed"] is False
    assert "local_only" in out["reason"]
    assert out["alternatives"] == ["github"]
    assert out["environment"] == "cloud"
    assert "proxy.invalid" not in json.dumps(out)
    code, out = _plan(capsys, "084")  # der Default bleibt in der Cloud erlaubt
    assert (code, out["allowed"]) == (0, True)


def test_plan_local_only_allowed_locally_and_override(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, TWO_WAYS)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")
    monkeypatch.setenv("SAK_ENVIRONMENT", "local")
    code, out = _plan(capsys, "--method", "local", "084")
    assert (code, out["allowed"], out["environment_source"]) == (0, True, "env")
    monkeypatch.delenv("HTTPS_PROXY")
    monkeypatch.setenv("SAK_ENVIRONMENT", "cloud")
    code, out = _plan(capsys, "--method", "local", "084")
    assert (code, out["allowed"]) == (1, False)


def test_plan_invalid_environment_value_is_usage_error(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, TWO_WAYS)
    monkeypatch.setenv("SAK_ENVIRONMENT", "mars")
    code, out = _plan(capsys, "084")
    assert code == 2
    assert "mars" not in out["error"]


def test_plan_replaces_spec_for_one_and_several_specs(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, {"command": "deploy {spec} --all {spec}"})
    _, one = _plan(capsys, "084")
    assert one["command"] == "deploy 084 --all 084"
    _, many = _plan(capsys, "84,085")
    assert many["command"] == "deploy 084,085 --all 084,085"
    _, listed = _plan(capsys, "084", "085-x", "084-20261022-101500")
    assert listed["specs"] == "084,085"


def test_plan_accepts_run_id(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, {"command": "d {spec}"})
    _, out = _plan(capsys, "084-20261022-101500-b")
    assert out["command"] == "d 084"


def test_plan_old_form(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, {"command": "make deploy {spec}"})
    code, out = _plan(capsys, "7")
    assert code == 0
    assert (out["method"], out["marker"], out["command"]) == ("default", "agent", "make deploy 007")


def test_plan_without_deploy_is_refused(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, None)
    code, out = _plan(capsys, "084")
    assert code == 1
    assert "kein Deploy-Weg" in out["error"]


def test_plan_refused_when_autonomy_never(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, TWO_WAYS, autonomy={"deploy": "never"})
    code, out = _plan(capsys, "084")
    assert (code, out["allowed"]) == (1, False)
    assert "never" in out["reason"]


def test_plan_bad_spec_token_is_usage_error(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, TWO_WAYS)
    code, _ = _plan(capsys, "abc")
    assert code == 2


def test_plan_executes_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    marker = repo / "ran.txt"
    _write(repo, {"command": f"python -c open('{marker.as_posix()}','w') {{spec}}"})
    calls: list[Any] = []
    real_run = subprocess.run

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(args[0] if args else kwargs.get("args"))
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    code, _ = _plan(capsys, "084")
    assert code == 0
    assert not marker.exists()
    assert all(isinstance(c, list) and c[0] == "git" for c in calls)
