"""``sak upgrade`` (Spec 005 US2, SC-001, SC-003; T009 und T010)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from install_support import (
    Sak,
    bump_version,
    git,
    read_json,
    snapshot,
    write,
)

from spec_agent_kit.install import doctor as doctor_module
from spec_agent_kit.install.kit import Kit, sha256_of

REVIEWER = ".claude/agents/sak-code-reviewer.md"
DOCS = ".claude/agents/sak-docs.md"


def _installed(sak: Sak, init_args: list[str], target: Path) -> None:
    code, out = sak(*init_args, "--apply")
    assert code == 0, out
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "sak init")


def _template(kit: Kit, name: str) -> Path:
    return kit.templates / "claude" / "agents" / name


def _upgrade(sak: Sak, target: Path, *extra: str) -> dict[str, Any]:
    code, out = sak("upgrade", str(target), "--no-sync", *extra)
    assert code == 0, out
    return out


def _actions(plan: dict[str, Any]) -> dict[str, str]:
    return {a["path"]: a["action"] for a in plan["actions"]}


def _change_reviewer(kit: Kit) -> None:
    path = _template(kit, "sak-code-reviewer.md")
    path.write_text(
        path.read_text(encoding="utf-8") + "\nNeue Regel.\n", encoding="utf-8", newline="\n"
    )


# --------------------------------------------------------------------------- US2


def test_unmodified_file_is_replaced_and_the_lock_hash_is_updated(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    old_lock = read_json(target / ".spec-agent/lock.json")
    _change_reviewer(kit)
    bump_version(kit, "0.4.0")
    plan_code, plan = sak("upgrade", str(target), "--no-sync")
    assert plan_code == 0
    assert plan["mode"] == "plan"
    assert _actions(plan)[REVIEWER] == "replace"
    assert (target / REVIEWER).read_text(encoding="utf-8") != _template(
        kit, "sak-code-reviewer.md"
    ).read_text(encoding="utf-8")  # der Plan schreibt nichts
    out = _upgrade(sak, target, "--apply")
    new_text = _template(kit, "sak-code-reviewer.md").read_bytes()
    assert (target / REVIEWER).read_bytes() == new_text
    lock = read_json(target / ".spec-agent/lock.json")
    assert lock["files"][REVIEWER] == sha256_of(new_text)
    assert lock["files"][REVIEWER] != old_lock["files"][REVIEWER]
    assert lock["kit_version"] == "0.4.0"
    assert lock["installed_at"] == old_lock["installed_at"]
    assert lock["upgraded_at"] is not None
    assert out["conflicts"] == []
    assert not list(target.rglob("*.sak-new"))


def test_locally_modified_file_stays_and_sak_new_is_created(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    local = (target / REVIEWER).read_text(encoding="utf-8") + "\nLokale Anpassung.\n"
    write(target, REVIEWER, local)
    git(target, "commit", "-q", "-am", "lokal angepasst")
    _change_reviewer(kit)
    bump_version(kit, "0.4.0")
    out = _upgrade(sak, target, "--apply")
    assert (target / REVIEWER).read_text(encoding="utf-8") == local
    assert (target / (REVIEWER + ".sak-new")).read_bytes() == _template(
        kit, "sak-code-reviewer.md"
    ).read_bytes()
    assert out["conflicts"] == [REVIEWER]
    entry = next(a for a in out["actions"] if a["path"] == REVIEWER)
    assert entry["action"] == "conflict"
    assert "git diff --no-index" in entry["hint"]
    # Der Lock behält den alten Hash: der Konflikt bleibt sichtbar, bis er gelöst ist.
    lock = read_json(target / ".spec-agent/lock.json")
    assert lock["files"][REVIEWER] != sha256_of(_template(kit, "sak-code-reviewer.md").read_bytes())


def test_locally_modified_file_with_unchanged_kit_is_left_alone(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    write(target, REVIEWER, (target / REVIEWER).read_text(encoding="utf-8") + "\nLokal.\n")
    git(target, "commit", "-q", "-am", "lokal")
    bump_version(kit, "0.4.0")
    plan = _upgrade(sak, target)
    assert REVIEWER not in _actions(plan)
    assert plan["conflicts"] == []


def test_removed_kit_file_is_deleted_when_unchanged(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    _template(kit, "sak-docs.md").unlink()
    bump_version(kit, "0.4.0")
    out = _upgrade(sak, target, "--apply")
    assert _actions(out)[DOCS] == "delete"
    assert not (target / DOCS).exists()
    assert DOCS not in read_json(target / ".spec-agent/lock.json")["files"]
    assert (target / ".claude/agents").is_dir()  # das Verzeichnis bleibt


def test_removed_kit_file_stays_when_modified_and_is_reported(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    write(target, DOCS, (target / DOCS).read_text(encoding="utf-8") + "\nEigener Zusatz.\n")
    git(target, "commit", "-q", "-am", "lokal")
    _template(kit, "sak-docs.md").unlink()
    bump_version(kit, "0.4.0")
    out = _upgrade(sak, target, "--apply")
    assert (target / DOCS).is_file()
    assert any(DOCS in w and "bleibt" in w for w in out["warnings"])
    assert DOCS not in _actions(out) or _actions(out)[DOCS] == "skip"


def test_removed_kit_file_that_is_already_gone_leaves_the_lock(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    (target / DOCS).unlink()
    git(target, "commit", "-q", "-am", "gelöscht")
    _template(kit, "sak-docs.md").unlink()
    bump_version(kit, "0.4.0")
    _upgrade(sak, target, "--apply")
    assert DOCS not in read_json(target / ".spec-agent/lock.json")["files"]


def test_new_kit_file_is_created(kit: Kit, target: Path, sak: Sak, init_args: list[str]) -> None:
    _installed(sak, init_args, target)
    write(
        kit.root,
        "packages/agent-blueprint/templates/claude/agents/sak-neu.md",
        "---\nname: x\n---\n",
    )
    bump_version(kit, "0.4.0")
    out = _upgrade(sak, target, "--apply")
    assert _actions(out)[".claude/agents/sak-neu.md"] == "create"
    assert ".claude/agents/sak-neu.md" in read_json(target / ".spec-agent/lock.json")["files"]


def test_new_kit_file_colliding_with_a_local_file_is_a_conflict(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    write(target, ".claude/agents/sak-neu.md", "lokal\n")
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "lokal")
    write(kit.root, "packages/agent-blueprint/templates/claude/agents/sak-neu.md", "kit\n")
    bump_version(kit, "0.4.0")
    out = _upgrade(sak, target, "--apply")
    assert out["conflicts"] == [".claude/agents/sak-neu.md"]
    assert (target / ".claude/agents/sak-neu.md").read_text(encoding="utf-8") == "lokal\n"


def test_deleted_managed_file_is_restored(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    (target / DOCS).unlink()
    git(target, "commit", "-q", "-am", "gelöscht")
    out = _upgrade(sak, target, "--apply")
    assert _actions(out)[DOCS] == "create"
    assert (target / DOCS).is_file()


def test_engine_files_are_replaced_by_the_new_kit(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    cli = kit.engine / "src/spec_agent_kit/cli.py"
    cli.write_text(cli.read_text(encoding="utf-8") + "\n# neu\n", encoding="utf-8", newline="\n")
    bump_version(kit, "0.4.0")
    out = _upgrade(sak, target, "--apply")
    assert _actions(out)[".spec-agent/engine/src/spec_agent_kit/cli.py"] == "replace"
    assert (
        target / ".spec-agent/engine/src/spec_agent_kit/cli.py"
    ).read_bytes() == cli.read_bytes()
    assert (target / ".spec-agent/engine/src/spec_agent_kit/__init__.py").read_text(
        encoding="utf-8"
    ).count("0.4.0") == 1


def test_resolved_conflict_is_adopted_into_the_lock(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    write(target, REVIEWER, (target / REVIEWER).read_text(encoding="utf-8") + "\nLokal.\n")
    git(target, "commit", "-q", "-am", "lokal")
    _change_reviewer(kit)
    bump_version(kit, "0.4.0")
    _upgrade(sak, target, "--apply")
    # Der Betreiber übernimmt die Kit-Fassung und räumt die .sak-new-Datei weg.
    sak_new = target / (REVIEWER + ".sak-new")
    (target / REVIEWER).write_bytes(sak_new.read_bytes())
    sak_new.unlink()
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "Konflikt gelöst")
    adopt = _upgrade(sak, target, "--apply")
    assert adopt["conflicts"] == []
    assert read_json(target / ".spec-agent/lock.json")["files"][REVIEWER] == sha256_of(
        (target / REVIEWER).read_bytes()
    )
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "Lock")
    assert _upgrade(sak, target)["empty"] is True


# --------------------------------------------------------------------------- Config (US2.4)


def test_config_is_never_touched_and_missing_keys_are_reported(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    minimal = (
        "schema: sak.config/1\nproject:\n  key: ai-forge\n  name: AI-Forge\n"
        "pipeline:\n  roles:\n    ui_review: { enabled: false }\n"
        'commands:\n  test_fast: ["uv run pytest -q {paths}"]\n'
    )
    write(target, ".spec-agent/config.yml", minimal)
    git(target, "commit", "-q", "-am", "minimale Config")
    bump_version(kit, "0.4.0")
    plan = _upgrade(sak, target)
    assert ".spec-agent/config.yml" not in _actions(plan)
    keys = {k["path"]: k["default"] for k in plan["config_keys"]}
    assert keys["stages"] == {"deployed": True, "verified": True}
    assert keys["pipeline.max_rounds"] == 2
    assert keys["locale"] == "de"
    assert "commands.test_fast" not in keys
    assert "commands.lint" in keys
    assert "project.base_branch" in keys
    out = _upgrade(sak, target, "--apply")
    assert (target / ".spec-agent/config.yml").read_text(encoding="utf-8") == minimal
    assert out["config_keys"]
    assert yaml.safe_load(minimal)["project"]["key"] == "ai-forge"


def test_commands_from_the_config_are_added_to_the_allowlist(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    config = (target / ".spec-agent/config.yml").read_text(encoding="utf-8")
    write(
        target,
        ".spec-agent/config.yml",
        config.replace("uv run ruff check .", "uv run ruff check src"),
    )
    git(target, "commit", "-q", "-am", "anderer Lint-Befehl")
    out = _upgrade(sak, target, "--apply")
    assert _actions(out)[".claude/settings.json"] == "merge"
    allow = read_json(target / ".claude/settings.json")["permissions"]["allow"]
    assert "Bash(uv run ruff check src)" in allow
    assert "Bash(uv run ruff check .)" not in allow  # Kit-Eintrag, ersetzt (Spec 011 B13)


def test_settings_fragment_changes_are_merged_additively(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    fragment = kit.templates / "claude" / "settings.fragment.json"
    data = read_json(fragment)
    data["permissions"]["deny"].append("Bash(git reset --hard *)")
    import json

    fragment.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    bump_version(kit, "0.4.0")
    _upgrade(sak, target, "--apply")
    settings = read_json(target / ".claude/settings.json")
    assert "Bash(git reset --hard *)" in settings["permissions"]["deny"]
    assert (
        settings["hooks"]["SessionStart"][0]["hooks"][0]["command"] == "echo Willkommen im Projekt"
    )
    lock = read_json(target / ".spec-agent/lock.json")
    assert lock["settings_fragment_hash"] == sha256_of(fragment.read_bytes())


# --------------------------------------------------------------------------- Idempotenz (SC-001)


def test_upgrade_without_kit_change_has_an_empty_plan(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    before = snapshot(target)
    plan = _upgrade(sak, target)
    assert plan["empty"] is True
    assert [a for a in plan["actions"] if a["action"] != "skip"] == []
    out = _upgrade(sak, target, "--apply")
    assert out["empty"] is True
    assert snapshot(target) == before


def test_second_apply_after_a_real_upgrade_is_empty(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    _change_reviewer(kit)
    bump_version(kit, "0.4.0")
    _upgrade(sak, target, "--apply")
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "sak upgrade")
    before = snapshot(target)
    again = _upgrade(sak, target, "--apply")
    assert again["empty"] is True
    assert snapshot(target) == before


def test_pending_conflict_is_reported_again_but_never_written_twice_differently(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    write(target, REVIEWER, (target / REVIEWER).read_text(encoding="utf-8") + "\nLokal.\n")
    git(target, "commit", "-q", "-am", "lokal")
    _change_reviewer(kit)
    bump_version(kit, "0.4.0")
    _upgrade(sak, target, "--apply")
    first = snapshot(target)
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "upgrade mit Konflikt")
    again = _upgrade(sak, target, "--apply")
    assert again["conflicts"] == [REVIEWER]
    assert snapshot(target) == first


# --------------------------------------------------------------------------- Ablehnungen


def test_upgrade_requires_an_initialized_project(kit: Kit, target: Path, sak: Sak) -> None:
    code, out = sak("upgrade", str(target), "--no-sync")
    assert code == 1
    assert "sak init" in out["errors"][0]["message"]


def test_downgrade_is_rejected(kit: Kit, target: Path, sak: Sak, init_args: list[str]) -> None:
    bump_version(kit, "0.4.0")
    _installed(sak, init_args, target)
    bump_version(kit, "0.3.0")
    before = snapshot(target)
    code, out = sak("upgrade", str(target), "--no-sync", "--apply")
    assert code == 1
    assert "Downgrade" in out["errors"][0]["message"]
    assert snapshot(target) == before


def test_dirty_tree_is_rejected_and_allow_dirty_needs_untouched_files(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    _change_reviewer(kit)
    bump_version(kit, "0.4.0")
    write(target, "README.md", "geändert\n")
    code, out = sak("upgrade", str(target), "--no-sync")
    assert code == 1
    assert "nicht sauber" in out["errors"][0]["message"]
    out = _upgrade(sak, target, "--allow-dirty", "--apply")  # README wird nicht berührt
    assert (target / "README.md").read_text(encoding="utf-8") == "geändert\n"
    assert _actions(out)[REVIEWER] == "replace"


def test_allow_dirty_is_rejected_when_a_replace_touches_a_changed_file(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    settings = read_json(target / ".claude/settings.json")
    settings["env"]["NEU"] = "1"
    import json

    write(target, ".claude/settings.json", json.dumps(settings, indent=2) + "\n")
    config = (target / ".spec-agent/config.yml").read_text(encoding="utf-8")
    write(
        target,
        ".spec-agent/config.yml",
        config.replace("uv run ruff check .", "uv run ruff check src"),
    )
    code, out = sak("upgrade", str(target), "--no-sync", "--allow-dirty")
    assert code == 1
    assert ".claude/settings.json" in out["errors"][0]["message"]


# --------------------------------------------------------------------------- uv sync


def test_uv_sync_runs_in_the_engine_folder_after_apply(
    kit: Kit, target: Path, sak: Sak, init_args: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _installed(sak, init_args, target)
    _change_reviewer(kit)
    bump_version(kit, "0.4.0")
    calls: list[Path] = []

    def fake_sync(root: Path) -> dict[str, Any]:
        calls.append(root)
        return {"ok": True, "detail": "uv sync ausgeführt"}

    monkeypatch.setattr("spec_agent_kit.install.apply.uv_sync", fake_sync)
    code, out = sak("upgrade", str(target), "--apply")
    assert code == 0, out
    assert calls == [target.resolve()]
    assert out["uv_sync"]["ok"] is True
    assert out["config_check"]["ok"] is True


def test_failed_uv_sync_is_reported_with_exit_1(
    kit: Kit, target: Path, sak: Sak, init_args: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "spec_agent_kit.install.apply.uv_sync",
        lambda root: {"ok": False, "detail": "uv sync fehlgeschlagen: kein Netz"},
    )
    args = [a for a in init_args if a != "--no-sync"]
    code, out = sak(*args, "--apply")
    assert code == 1
    assert out["uv_sync"]["ok"] is False
    assert (target / ".spec-agent/lock.json").is_file()  # die Dateien liegen trotzdem da


# --------------------------------------------------------------------------- SC-003


def test_smoke_init_doctor_local_change_version_bump_upgrade(
    kit: Kit,
    target: Path,
    sak: Sak,
    init_args: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _installed(sak, init_args, target)
    write(target, ".spec-agent/engine/.venv/pyvenv.cfg", "home = x\n")
    monkeypatch.setattr(  # die echte Hook-Probe braucht ein echtes uv (siehe test_install_doctor)
        doctor_module,
        "_check_hook_probe",
        lambda root: {"check": "hook_probe", "ok": True, "detail": "ersetzt", "required": True},
    )
    monkeypatch.chdir(target)
    code, doctor = sak("doctor")
    assert code == 0, doctor
    # Eine Kit-Datei lokal ändern, Kit-Version erhöhen und die Datei im Kit ebenfalls ändern.
    write(target, DOCS, (target / DOCS).read_text(encoding="utf-8") + "\nLokal.\n")
    git(target, "commit", "-q", "-am", "lokale Änderung")
    path = _template(kit, "sak-docs.md")
    path.write_text(
        path.read_text(encoding="utf-8") + "\nKit neu.\n", encoding="utf-8", newline="\n"
    )
    bump_version(kit, "0.4.0")
    code, out = sak("upgrade", str(target), "--no-sync", "--apply")
    assert code == 0, out
    assert out["conflicts"] == [DOCS]
    assert (target / (DOCS + ".sak-new")).is_file()
    code, doctor = sak("doctor")
    assert code == 0, doctor  # lokal geänderte Dateien sind erlaubt


def test_upgrade_replaces_old_direct_uv_hooks_and_keeps_foreign_ones(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    import json

    _installed(sak, init_args, target)
    path = target / ".claude/settings.json"
    settings = read_json(path)
    old = (
        'uv run --project "$CLAUDE_PROJECT_DIR/.spec-agent/engine" sak hook subagent-start || true'
    )
    settings["hooks"]["SubagentStart"] = [
        {"hooks": [{"type": "command", "command": "echo fremd"}]},
        {"matcher": "sak-.*", "hooks": [{"type": "command", "command": old, "timeout": 5}]},
    ]
    text = json.dumps(settings, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    git(target, "commit", "-q", "-am", "alte Hooks")
    bump_version(kit, "0.4.0")
    _upgrade(sak, target, "--apply")
    entries = read_json(path)["hooks"]["SubagentStart"]
    commands = [h["command"] for e in entries for h in e["hooks"]]
    assert commands[0] == "echo fremd"
    assert commands[1:] == ['sh "$CLAUDE_PROJECT_DIR/.spec-agent/sak" hook subagent-start || true']
    assert len(entries) == 2
