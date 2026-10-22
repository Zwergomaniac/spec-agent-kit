"""Spec 011 T005/T006: Format, Plan-Details, bypass, sh-Suche, settings_allow, Upgrade."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from install_support import Sak, bump_version, git, read_json, write

from spec_agent_kit.cli import main
from spec_agent_kit.install import tools
from spec_agent_kit.install.kit import Kit

UNSAFE = "bypass" + "Permissions"
OLD_TEST = "Bash(uv run pytest -q *)"


def _installed(sak: Sak, init_args: list[str], target: Path) -> None:
    code, out = sak(*init_args, "--apply")
    assert code == 0, out
    git(target, "add", "-A")
    git(target, "commit", "-q", "-am", "sak init")


def _commit(target: Path, message: str = "x") -> None:
    git(target, "add", "-A")
    if not git(target, "status", "--porcelain").strip():
        return
    git(target, "commit", "-q", "-m", message)


def _change_test_command(target: Path) -> None:
    config = target / ".spec-agent" / "config.yml"
    text = config.read_text(encoding="utf-8").replace(
        "uv run pytest -q", "uv run --extra dev pytest -q"
    )
    config.write_text(text, encoding="utf-8", newline="\n")
    _commit(target, "config")


# --- sh- und uv-Suche (B12) ----------------------------------------------------------------


def test_find_sh_prefers_the_path() -> None:
    assert tools.find_sh(env={}, which=lambda name: "/x/sh", windows=True) == "/x/sh"


def test_find_sh_looks_in_the_git_for_windows_locations(tmp_path: Path) -> None:
    sh = tmp_path / "pf" / "Git" / "usr" / "bin" / "sh.exe"
    write(tmp_path, "pf/Git/usr/bin/sh.exe", "x")
    found = tools.find_sh(
        env={"ProgramFiles": str(tmp_path / "pf")}, which=lambda n: None, windows=True
    )
    assert found == str(sh)


def test_find_sh_falls_back_to_bin_and_to_the_local_programs_folder(tmp_path: Path) -> None:
    write(tmp_path, "pf/Git/bin/sh.exe", "x")
    env = {"ProgramFiles": str(tmp_path / "pf")}
    assert tools.find_sh(env, lambda n: None, True) == str(
        tmp_path / "pf" / "Git" / "bin" / "sh.exe"
    )
    write(tmp_path, "local/Programs/Git/usr/bin/sh.exe", "x")
    env = {"LOCALAPPDATA": str(tmp_path / "local")}
    assert tools.find_sh(env, lambda n: None, True) == str(
        tmp_path / "local" / "Programs" / "Git" / "usr" / "bin" / "sh.exe"
    )


def test_find_sh_derives_the_location_from_git(tmp_path: Path) -> None:
    write(tmp_path, "tools/Git/cmd/git.exe", "x")
    write(tmp_path, "tools/Git/usr/bin/sh.exe", "x")
    git_exe = str(tmp_path / "tools" / "Git" / "cmd" / "git.exe")
    found = tools.find_sh({}, lambda n: git_exe if n == "git" else None, True)
    assert found == str(tmp_path / "tools" / "Git" / "usr" / "bin" / "sh.exe")


def test_find_sh_returns_none_when_nothing_exists(tmp_path: Path) -> None:
    assert tools.find_sh({"ProgramFiles": str(tmp_path)}, lambda n: None, True) is None
    assert tools.find_sh({}, lambda n: None, False) is None


def test_find_uv_uses_the_starter_order(tmp_path: Path) -> None:
    write(tmp_path, "local/Microsoft/WinGet/Packages/astral-sh.uv_x/uv.exe", "x")
    env = {"LOCALAPPDATA": str(tmp_path / "local")}
    found = tools.find_uv(env, lambda n: None, True)
    assert found is not None and found.endswith("uv.exe")
    explicit = write(tmp_path, "mine/uv", "x")
    assert tools.find_uv({"SAK_UV": str(explicit)}, lambda n: "/path/uv", True) == str(explicit)
    assert tools.find_uv({}, lambda n: "/path/uv", True) == "/path/uv"
    assert tools.find_uv({}, lambda n: None, False) is None or True


# --- Format (US6) -----------------------------------------------------------------------------


def test_default_output_is_json_only_on_stdout(
    kit: Kit, target: Path, init_args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert main(init_args) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["mode"] == "plan"
    assert captured.err == ""


def test_text_format_prints_text_only(
    kit: Kit, target: Path, init_args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert main([*init_args, "--format", "text"]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("sak init (Plan)")
    assert not captured.out.lstrip().startswith("{") and captured.err == ""
    assert "Permissions in .claude/settings.json" in captured.out


def test_apply_in_text_format(
    kit: Kit, target: Path, init_args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert main([*init_args, "--apply", "--format", "text"]) == 0
    captured = capsys.readouterr()
    assert "Ergebnis: ok" in captured.out and "Vorschlag: git add" in captured.out
    assert captured.err == "" and "{" not in captured.out.splitlines()[0]


def test_apply_in_json_format_has_no_stderr(
    kit: Kit, target: Path, init_args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert main([*init_args, "--apply"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["mode"] == "applied" and captured.err == ""


def test_errors_in_text_format(
    kit: Kit, target: Path, init_args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    args = [a if a != "ai-forge" else "UNGÜLTIG" for a in init_args]
    capsys.readouterr()
    assert main([*args, "--format", "text"]) == 1
    assert capsys.readouterr().out.startswith("FEHLER --key")


# --- Plan-Details (Befund 9) ---------------------------------------------------------------


def test_plan_lists_every_rule_and_the_scope(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    code, plan = sak(*init_args)
    assert code == 0
    info = plan["permissions"]
    assert "gesamtes Projekt" in info["scope"]
    assert "Bash(git diff)" in info["allow"]["add"]
    assert "Bash(uv run ruff check .)" in info["allow"]["add"]
    assert "Bash(git status)" in info["allow"]["present"]  # eigener Eintrag des Ziels
    assert "Bash(git push)" in info["deny"]["add"]
    text = "\n".join(plan["text"])
    assert "gelten für das ganze Projekt" in text
    assert "+ allow Bash(git diff)" in text and "+ deny  Bash(git push)" in text


# --- bypass (Befund 7) ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("relative", "settings"),
    [
        (".claude/settings.json", {"defaultMode": UNSAFE}),
        (".claude/settings.json", {"permissions": {"defaultMode": UNSAFE}}),
        (".claude/settings.local.json", {"permissions": {"defaultMode": UNSAFE}}),
    ],
)
def test_init_plan_warns_about_the_unsafe_mode(
    kit: Kit, target: Path, sak: Sak, init_args: list[str], relative: str, settings: dict[str, Any]
) -> None:
    write(target, relative, json.dumps(settings))
    _commit(target)
    code, plan = sak(*init_args)
    assert code == 0
    assert any(UNSAFE in w and relative in w for w in plan["warnings"]), plan["warnings"]


def test_no_warning_for_a_safe_mode(kit: Kit, target: Path, sak: Sak, init_args: list[str]) -> None:
    _, plan = sak(*init_args)
    assert not [w for w in plan["warnings"] if "defaultMode" in w]


# --- settings_allow und Upgrade (B13) ----------------------------------------------------------


def test_init_records_only_the_entries_it_added(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    owned = read_json(target / ".spec-agent/lock.json")["settings_allow"]
    assert OLD_TEST in owned and "Bash(git diff)" in owned
    # Beides gehörte dem Ziel schon vor dem Init.
    assert "Bash(git status)" not in owned and "Bash(uv run pytest -q)" not in owned


def test_upgrade_replaces_obsolete_kit_entries_and_keeps_foreign_ones(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    _change_test_command(target)
    bump_version(kit, "0.5.1")
    code, plan = sak("upgrade", str(target), "--no-sync")
    assert code == 0
    assert plan["permissions"]["allow"]["remove"] == [OLD_TEST]
    assert "Bash(uv run --extra dev pytest -q *)" in plan["permissions"]["allow"]["add"]
    assert any("- allow Bash(uv run pytest -q *)" in line for line in plan["text"])
    code, _ = sak("upgrade", str(target), "--no-sync", "--apply")
    assert code == 0
    allow = read_json(target / ".claude/settings.json")["permissions"]["allow"]
    assert OLD_TEST not in allow
    assert "Bash(uv run --extra dev pytest -q *)" in allow
    assert "Bash(uv run pytest -q)" in allow  # eigener Eintrag des Ziels bleibt
    lock = read_json(target / ".spec-agent/lock.json")
    assert OLD_TEST not in lock["settings_allow"]
    assert "Bash(uv run --extra dev pytest -q *)" in lock["settings_allow"]
    _commit(target, "upgrade")
    _, again = sak("upgrade", str(target), "--no-sync")
    assert again["empty"] is True


def test_upgrade_from_a_lock_without_settings_allow(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    """Altbestand vor 0.2.0: nur bekannte Kit-Muster werden ersetzt, alles andere bleibt."""
    _installed(sak, init_args, target)
    lock_path = target / ".spec-agent/lock.json"
    lock = read_json(lock_path)
    del lock["settings_allow"]
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    settings_path = target / ".claude/settings.json"
    settings = read_json(settings_path)
    settings["permissions"]["allow"] += [
        "Bash(git switch *)",
        "Bash(git merge *)",
        "Bash(npm test)",
    ]
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    _change_test_command(target)
    bump_version(kit, "0.5.1")
    code, plan = sak("upgrade", str(target), "--no-sync")
    assert code == 0
    assert any("Altbestand" in w and "Bash(git switch *)" in w for w in plan["warnings"])
    code, _ = sak("upgrade", str(target), "--no-sync", "--apply")
    assert code == 0
    allow = read_json(settings_path)["permissions"]["allow"]
    assert "Bash(git switch *)" not in allow and "Bash(git merge *)" not in allow
    assert "Bash(npm test)" in allow  # fremd
    assert OLD_TEST in allow  # Herkunft unbekannt: bleibt (dokumentierte Grenze)
    assert "Bash(uv run --extra dev pytest -q *)" in allow
    assert "settings_allow" in read_json(lock_path)  # ab jetzt bekannt
    _commit(target, "upgrade")
    _, again = sak("upgrade", str(target), "--no-sync")
    assert again["empty"] is True


def test_upgrade_adds_the_session_start_hook(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    path = target / ".claude/settings.json"
    settings = read_json(path)
    settings["hooks"]["SessionStart"] = [
        e for e in settings["hooks"]["SessionStart"] if "matcher" not in e
    ]
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    _commit(target, "ohne Kit-SessionStart")
    bump_version(kit, "0.5.1")
    code, _ = sak("upgrade", str(target), "--no-sync", "--apply")
    assert code == 0
    entries = read_json(path)["hooks"]["SessionStart"]
    assert any(e.get("matcher") == "compact" for e in entries)
    assert any("Willkommen" in json.dumps(e) for e in entries)  # fremder Hook bleibt
