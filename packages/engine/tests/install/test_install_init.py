"""``sak init`` gegen ein Fixture-Repo (Spec 005 US1, SC-001, SC-002; T006 bis T008)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from install_support import (
    OWN_AGENT,
    OWN_SETTINGS,
    Sak,
    git,
    make_target,
    read_json,
    snapshot,
    write,
)

from spec_agent_kit import contracts
from spec_agent_kit.config.check import check as check_config
from spec_agent_kit.install.kit import Kit, sha256_of
from spec_agent_kit.install.speckit import INIT_COMMAND

UNSAFE = "bypass" + "Permissions"
OWN_BUILDER = "---\nname: sak-builder\nmodel: sonnet\neffort: medium\n---\nEigene Fassung\n"


def _apply(sak: Sak, init_args: list[str], *extra: str) -> dict[str, Any]:
    code, out = sak(*init_args, "--apply", *extra)
    assert code == 0, (out.get("config_check"), out.get("uv_sync"))
    return out


def _fake_venv(target: Path) -> None:
    write(target, ".spec-agent/engine/.venv/pyvenv.cfg", "home = x\n")


# --------------------------------------------------------------------------- Plan vor Apply


def test_without_apply_only_a_plan_is_printed(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    before = snapshot(target)
    code, plan = sak(*init_args)
    assert code == 0
    assert snapshot(target) == before
    assert not (target / ".spec-agent").exists()
    assert plan["mode"] == "plan"
    assert plan["command"] == "init"
    assert plan["empty"] is False
    kinds = {a["action"] for a in plan["actions"]}
    assert kinds <= {"create", "merge", "conflict", "skip", "replace", "delete"}
    created = {a["path"] for a in plan["actions"] if a["action"] == "create"}
    assert ".spec-agent/config.yml" in created
    assert ".spec-agent/lock.json" in created
    assert ".claude/agents/sak-builder.md" in created
    assert ".claude/skills/sak-pipeline/SKILL.md" in created
    assert ".spec-agent/.gitignore" in created
    assert any(p.startswith(".spec-agent/engine/") for p in created)
    assert [a["path"] for a in plan["actions"] if a["action"] == "merge"] == [
        ".claude/settings.json"
    ]
    assert plan["text"][0].startswith("sak init (Plan)")


def test_plan_lists_the_lock_last(kit: Kit, target: Path, sak: Sak, init_args: list[str]) -> None:
    _, plan = sak(*init_args)
    assert plan["actions"][-1]["path"] == ".spec-agent/lock.json"


# --------------------------------------------------------------------------- Validierung


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--key", "../x y"),
        ("--key", "A"),
        ("--key", "a"),
        ("--key", "1ab"),
        ("--key", "ab-"),
        ("--key", "x" * 41),
        ("--name", ""),
        ("--name", "n" * 81),
        ("--name", "Zeile\neins"),
        ("--name", "Tab\there"),
        ("--dashboard-url", "http://example.com"),
        ("--dashboard-url", "ftp://localhost"),
        ("--dashboard-url", "https://"),
        ("--dashboard-url", "https://mit leerzeichen.example"),
        ("--base-branch", "gibt-es-nicht"),
    ],
)
def test_invalid_input_is_rejected_without_any_write(
    kit: Kit, target: Path, sak: Sak, init_args: list[str], option: str, value: str
) -> None:
    before = snapshot(target)
    args = [*init_args, "--apply"]
    if option in args:
        args[args.index(option) + 1] = value
    else:
        args += [option, value]
    code, out = sak(*args)
    assert code == 1
    assert out["ok"] is False
    assert out["errors"]
    assert snapshot(target) == before
    assert git(target, "status", "--porcelain") == ""


def test_invalid_key_message_names_the_problem(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    args = list(init_args)
    args[args.index("--key") + 1] = "../x y"
    code, out = sak(*args, "--apply")
    assert code == 1
    assert out["errors"][0]["path"] == "--key"
    assert "ungültiger Projektschlüssel" in out["errors"][0]["message"]


@pytest.mark.parametrize("url", ["https://board.example.org", "http://localhost:5190"])
def test_valid_dashboard_urls_are_accepted(
    kit: Kit, target: Path, sak: Sak, init_args: list[str], url: str
) -> None:
    _apply(sak, init_args, "--dashboard-url", url)
    config = yaml.safe_load((target / ".spec-agent/config.yml").read_text(encoding="utf-8"))
    assert config["dashboard"]["url"] == url


def test_name_with_special_characters_survives_in_the_config(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    args = list(init_args)
    args[args.index("--name") + 1] = 'Größe: "A" # B'
    _apply(sak, args)
    config = yaml.safe_load((target / ".spec-agent/config.yml").read_text(encoding="utf-8"))
    assert config["project"]["name"] == 'Größe: "A" # B'


def test_target_without_git_is_rejected(
    kit: Kit, tmp_path: Path, sak: Sak, init_args: list[str]
) -> None:
    plain = tmp_path / "kein-git"
    write(plain, ".specify/init-options.json", '{"speckit_version": "0.12.16"}\n')
    args = list(init_args)
    args[1] = str(plain)
    before = snapshot(plain)
    code, out = sak(*args, "--apply")
    assert code == 1
    assert "Git-Repository" in out["errors"][0]["message"]
    assert snapshot(plain) == before


def test_target_must_be_the_git_root(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    sub = target / "src"
    args = list(init_args)
    args[1] = str(sub)
    code, out = sak(*args, "--apply")
    assert code == 1
    assert "Git-Repository" in out["errors"][0]["message"]


def test_missing_speckit_is_rejected_with_the_exact_command(
    kit: Kit, tmp_path: Path, sak: Sak, init_args: list[str]
) -> None:
    bare = make_target(tmp_path, name="ohne-speckit", speckit=None)
    args = list(init_args)
    args[1] = str(bare)
    before = snapshot(bare)
    code, out = sak(*args, "--apply")
    assert code == 1
    assert INIT_COMMAND in out["errors"][0]["message"]
    assert snapshot(bare) == before


def test_too_old_speckit_is_rejected(
    kit: Kit, tmp_path: Path, sak: Sak, init_args: list[str]
) -> None:
    old = make_target(tmp_path, name="alt", speckit={"speckit_version": "0.11.0"})
    args = list(init_args)
    args[1] = str(old)
    code, out = sak(*args)
    assert code == 1
    assert "zu alt" in out["errors"][0]["message"]


def test_invalid_settings_json_is_rejected_without_change(
    kit: Kit, tmp_path: Path, sak: Sak, init_args: list[str]
) -> None:
    bad = make_target(tmp_path, name="kaputt", settings=None, commit=False)
    write(bad, ".claude/settings.json", "{ das ist kein json")
    git(bad, "add", "-A")
    git(bad, "commit", "-q", "-m", "Ausgangsstand")
    args = list(init_args)
    args[1] = str(bad)
    before = snapshot(bad)
    code, out = sak(*args, "--apply")
    assert code == 1
    assert out["errors"][0]["path"] == ".claude/settings.json"
    assert snapshot(bad) == before


def test_init_is_disabled_without_a_kit_repo(
    monkeypatch: pytest.MonkeyPatch, target: Path, sak: Sak, init_args: list[str]
) -> None:
    monkeypatch.setattr("spec_agent_kit.install.kit.kit_root", lambda: None)
    before = snapshot(target)
    code, out = sak(*init_args, "--apply")
    assert code == 1
    assert "aus dem Kit-Repo aufrufen" in out["errors"][0]["message"]
    assert snapshot(target) == before


# --------------------------------------------------------------------------- Arbeitsstand


def test_dirty_tree_is_rejected(kit: Kit, target: Path, sak: Sak, init_args: list[str]) -> None:
    write(target, "README.md", "geändert\n")
    code, out = sak(*init_args, "--apply")
    assert code == 1
    assert "nicht sauber" in out["errors"][0]["message"]
    assert not (target / ".spec-agent").exists()


def test_untracked_file_counts_as_dirty(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    write(target, "notizen.txt", "x\n")
    code, _ = sak(*init_args)
    assert code == 1


def test_allow_dirty_works_when_no_action_touches_the_changed_file(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    write(target, "README.md", "geändert\n")
    _apply(sak, init_args, "--allow-dirty")
    assert (target / "README.md").read_text(encoding="utf-8") == "geändert\n"
    assert (target / ".spec-agent/lock.json").is_file()


def test_allow_dirty_is_rejected_when_an_action_touches_a_changed_file(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    settings = target / ".claude/settings.json"
    settings.write_text(settings.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    before = snapshot(target)
    code, out = sak(*init_args, "--apply", "--allow-dirty")
    assert code == 1
    assert ".claude/settings.json" in out["errors"][0]["message"]
    assert snapshot(target) == before


# --------------------------------------------------------------------------- Acceptance Scenarios


def test_conflict_keeps_the_file_and_writes_sak_new(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    write(target, ".claude/agents/sak-builder.md", OWN_BUILDER)
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "eigener sak-builder")
    out = _apply(sak, init_args)
    assert (target / ".claude/agents/sak-builder.md").read_text(encoding="utf-8") == (OWN_BUILDER)
    sak_new = target / ".claude/agents/sak-builder.md.sak-new"
    source = kit.root / "packages/agent-blueprint/templates/claude/agents/sak-builder.md"
    assert sak_new.read_bytes() == source.read_bytes()
    assert out["conflicts"] == [".claude/agents/sak-builder.md"]
    assert out["applied"]["conflicts"] == [".claude/agents/sak-builder.md.sak-new"]
    assert any("sak-builder.md" in line for line in out["text"])
    lock = read_json(target / ".spec-agent/lock.json")
    assert ".claude/agents/sak-builder.md" not in lock["files"]  # nicht unser Eigentum


def test_bypass_mode_of_the_target_is_kept_with_a_warning(
    kit: Kit, tmp_path: Path, sak: Sak, init_args: list[str]
) -> None:
    unsafe = {**OWN_SETTINGS, "permissions": {"defaultMode": UNSAFE}}
    root = make_target(tmp_path, name="bypass", settings=unsafe)
    args = list(init_args)
    args[1] = str(root)
    _, plan = sak(*args)
    assert any("defaultMode" in w for w in plan["warnings"])
    out = _apply(sak, args)
    assert any("defaultMode" in w for w in out["warnings"])
    settings = read_json(root / ".claude/settings.json")
    assert settings["permissions"]["defaultMode"] == UNSAFE


def test_ui_is_on_by_default_with_a_warning_about_placeholders(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    args = [a for a in init_args if a != "--no-ui"]
    _, plan = sak(*args)
    assert any("ui.base_url" in w for w in plan["warnings"])
    _apply(sak, args)
    config = yaml.safe_load((target / ".spec-agent/config.yml").read_text(encoding="utf-8"))
    assert config["pipeline"]["roles"]["ui_review"]["enabled"] is True
    assert config["ui"]["base_url"].startswith("http://127.0.0.1")
    assert check_config(target)["ok"] is True


# --------------------------------------------------------------------------- SC-002 und Ergebnis


def test_existing_files_stay_identical_except_for_the_additive_settings_merge(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    tracked_before = {
        f: (target / f).read_bytes() for f in git(target, "ls-files").splitlines() if f
    }
    _apply(sak, init_args)
    changed = git(target, "diff", "--name-only").splitlines()
    assert changed == [".claude/settings.json"]
    for name, data in tracked_before.items():
        if name != ".claude/settings.json":
            assert (target / name).read_bytes() == data, name
    # Alles andere ist neu und liegt in den Kit-Pfaden.
    untracked = [
        line[3:]
        for line in git(target, "status", "--porcelain", "-uall").splitlines()
        if line[:2] == "??"
    ]
    assert untracked
    for path in untracked:
        assert path.startswith((".spec-agent/", ".claude/agents/sak-", ".claude/skills/sak-")), path
    # Der eigene Agent und der eigene Hook sind unverändert da.
    assert (target / ".claude/agents/code-executor.md").read_text(encoding="utf-8") == OWN_AGENT
    settings = read_json(target / ".claude/settings.json")
    own_session = OWN_SETTINGS["hooks"]["SessionStart"]
    assert settings["hooks"]["SessionStart"][: len(own_session)] == own_session
    assert [e.get("matcher") for e in settings["hooks"]["SessionStart"][len(own_session) :]] == [
        "compact"
    ]  # der Kit-Hook (Spec 011 US8) kommt dazu
    assert settings["env"] == OWN_SETTINGS["env"]
    assert settings["permissions"]["defaultMode"] == "acceptEdits"
    assert settings["permissions"]["allow"][:2] == OWN_SETTINGS["permissions"]["allow"]
    # Die Testbefehle stehen in der Allowlist (Spec 003 FR-015).
    allow = settings["permissions"]["allow"]
    assert "Bash(uv run pytest -q *)" in allow
    assert "Bash(uv run ruff check .)" in allow
    assert "Bash(git push)" in settings["permissions"]["deny"]


def test_config_check_and_doctor_report_ok_after_init(
    kit: Kit,
    target: Path,
    sak: Sak,
    init_args: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply(sak, init_args)
    _fake_venv(target)
    monkeypatch.chdir(target)
    code, check = sak("config", "check")
    assert code == 0, check
    assert check["ok"] is True
    code, doctor = sak("doctor")
    assert code == 0, doctor
    assert all(c["ok"] for c in doctor["checks"]), doctor
    assert git(target, "status", "--porcelain", "-uall").count("\n") > 0  # neue Dateien da


def test_config_is_rendered_from_the_template_with_options(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _apply(sak, init_args, "--base-branch", "main")
    text = (target / ".spec-agent/config.yml").read_text(encoding="utf-8")
    assert "__PROJECT_" not in text and "__BASE_BRANCH__" not in text
    assert "# Projektkonfiguration des Spec Agent Kit" in text  # Kommentare bleiben
    config = yaml.safe_load(text)
    assert contracts.validate_config(config) == []
    assert config["project"] == {"key": "ai-forge", "name": "AI-Forge", "base_branch": "main"}
    assert config["commands"]["test_fast"] == ["uv run pytest -q {paths}"]
    assert config["commands"]["test_full"] == ["uv run pytest -q"]
    assert config["commands"]["lint"] == ["uv run ruff check ."]
    assert config["pipeline"]["roles"]["ui_review"]["enabled"] is False
    assert "ui" not in config
    assert config["dashboard"]["url"] is None


def test_engine_copy_is_complete_and_without_tests_and_caches(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _apply(sak, init_args)
    engine = target / ".spec-agent" / "engine"
    assert (engine / "uv.lock").is_file()
    assert (engine / "pyproject.toml").is_file()
    assert (engine / "src/spec_agent_kit/cli.py").is_file()
    assert not (engine / "tests").exists()
    assert not (engine / ".venv").exists()
    assert not list(engine.rglob("__pycache__"))
    for path in engine.rglob("*"):
        if path.is_file():
            relative = path.relative_to(engine).as_posix()
            assert path.read_bytes() == (kit.engine / relative).read_bytes(), relative


def test_lock_lists_all_managed_files_but_not_config_or_itself(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    out = _apply(sak, init_args)
    lock = read_json(target / ".spec-agent/lock.json")
    assert contracts.validate_lock(lock) == []
    assert lock["kit_version"] == kit.version == out["kit_version"]
    assert lock["upgraded_at"] is None
    assert set(lock["files"]) == set(kit.managed_files())
    assert ".spec-agent/config.yml" not in lock["files"]
    assert ".spec-agent/lock.json" not in lock["files"]
    assert ".claude/settings.json" not in lock["files"]
    for path, digest in lock["files"].items():
        assert digest == sha256_of((target / path).read_bytes()), path
    assert lock["settings_fragment_hash"] == sha256_of(kit.settings_fragment())


def test_init_never_commits_and_suggests_a_commit(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    head = git(target, "rev-parse", "HEAD")
    out = _apply(sak, init_args)
    assert git(target, "rev-parse", "HEAD") == head
    assert out["suggested_commit"].startswith("git add .spec-agent")
    assert "git commit" in out["suggested_commit"]
    assert out["uv_sync"]["skipped"] is True
    assert out["config_check"]["ok"] is True


def test_no_temp_files_are_left_behind(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _apply(sak, init_args)
    assert not list(target.rglob("*.sak-tmp"))


# --------------------------------------------------------------------------- Idempotenz


def test_second_init_is_rejected_and_changes_nothing(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _apply(sak, init_args)
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "sak init")
    before = snapshot(target)
    code, out = sak(*init_args, "--apply")
    assert code == 1
    assert "sak upgrade" in out["errors"][0]["message"]
    assert snapshot(target) == before


def test_existing_config_is_never_overwritten(
    kit: Kit, tmp_path: Path, sak: Sak, init_args: list[str]
) -> None:
    root = make_target(tmp_path, name="mit-config", commit=False)
    own = (
        "schema: sak.config/1\n"
        "project:\n  key: eigenes\n  name: Eigene Config\n"
        "pipeline:\n  roles:\n    ui_review: { enabled: false }\n"
    )
    write(root, ".spec-agent/config.yml", own)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "Ausgangsstand")
    args = list(init_args)
    args[1] = str(root)
    out = _apply(sak, args)
    assert (root / ".spec-agent/config.yml").read_text(encoding="utf-8") == own
    skipped = [a for a in out["actions"] if a["path"] == ".spec-agent/config.yml"]
    assert skipped[0]["action"] == "skip"
    assert not (root / ".spec-agent/config.yml.sak-new").exists()


def test_files_identical_to_the_kit_are_adopted_without_conflict(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    source = kit.root / "packages/agent-blueprint/templates/claude/agents/sak-docs.md"
    write(target, ".claude/agents/sak-docs.md", source.read_text(encoding="utf-8"))
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "gleiche Datei")
    out = _apply(sak, init_args)
    assert out["conflicts"] == []
    lock = read_json(target / ".spec-agent/lock.json")
    assert ".claude/agents/sak-docs.md" in lock["files"]


def test_apply_refuses_when_the_target_changed_after_planning(
    kit: Kit, target: Path, tmp_path: Path
) -> None:
    from spec_agent_kit.install import InstallError
    from spec_agent_kit.install.apply import apply_plan
    from spec_agent_kit.install.plan import build_init_plan

    plan = build_init_plan(kit, target, key="ai-forge", name="AI-Forge", ui=False)
    write(target, ".claude/agents/sak-builder.md", "inzwischen angelegt\n")
    with pytest.raises(InstallError, match="seit der Planung"):
        apply_plan(plan, sync=False)
    assert not (target / ".spec-agent").exists()  # nichts geschrieben
    assert json.dumps(plan.summary())
