"""Worktrees: Erkennung, geerbte Dashboard-Einstellungen, Preflight-Warnung (Spec 011 US3, T002).

Die Worktrees entstehen mit einem echten ``git worktree add`` in ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from conftest import Repo

from spec_agent_kit import worktree
from spec_agent_kit.config import load_config, read_dashboard_key
from spec_agent_kit.dashboard import status

KEY = "sak_" + "A" * 43
URL = "https://dash.example.org"


def add_worktree(repo: Repo, tmp_path: Path, branch: str = "001-demo") -> Path:
    path = tmp_path / "wt"
    repo.git("worktree", "add", "-q", str(path), "-b", branch)
    return path


def set_main_dashboard(repo: Repo, *, url: str | None, key: str | None) -> None:
    """Uncommittete Dashboard-Einstellungen im Haupt-Checkout (wie nach `dashboard connect`)."""
    if url is not None:
        path = repo.path / ".spec-agent" / "config.yml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        config["dashboard"] = {"url": url}
        path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    if key is not None:
        (repo.path / ".spec-agent" / "dashboard.key").write_text(key + "\n", encoding="utf-8")


def test_main_checkout_of_a_real_worktree(repo: Repo, tmp_path: Path) -> None:
    wt = add_worktree(repo, tmp_path)
    found = worktree.main_checkout(wt)
    assert found is not None and found.samefile(repo.path)
    assert worktree.main_checkout(repo.path) is None


def test_a_submodule_style_git_file_is_not_a_worktree(tmp_path: Path) -> None:
    gitdir = tmp_path / "super" / ".git" / "modules" / "lib"
    gitdir.mkdir(parents=True)
    module = tmp_path / "lib"
    module.mkdir()
    (module / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    assert worktree.main_checkout(module) is None


def test_garbage_git_files_are_ignored(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("kein gitdir\n", encoding="utf-8")
    assert worktree.main_checkout(tmp_path) is None
    (tmp_path / ".git").write_text("gitdir: " + str(tmp_path / "gibt-es-nicht") + "\n")
    assert worktree.main_checkout(tmp_path) is None


def test_worktree_inherits_url_and_key_from_the_main_checkout(repo: Repo, tmp_path: Path) -> None:
    set_main_dashboard(repo, url=URL, key=KEY)
    wt = add_worktree(repo, tmp_path)
    assert not (wt / ".spec-agent" / "dashboard.key").exists()  # gitignoriert, fehlt im Worktree
    cfg = load_config(wt)
    assert cfg.data["dashboard"]["url"] == URL
    assert cfg.data["dashboard"]["push"] == "auto"
    assert read_dashboard_key(wt, cfg, {}) == KEY


def test_inheritance_does_not_override_the_worktrees_own_values(repo: Repo, tmp_path: Path) -> None:
    set_main_dashboard(repo, url=URL, key=KEY)
    wt = add_worktree(repo, tmp_path)
    own = wt / ".spec-agent" / "config.yml"
    config = yaml.safe_load(own.read_text(encoding="utf-8"))
    config["dashboard"] = {"url": "https://other.example.org", "push": "manual"}
    own.write_text(yaml.safe_dump(config), encoding="utf-8")
    (wt / ".spec-agent" / "dashboard.key").write_text("sak_" + "B" * 43 + "\n", encoding="utf-8")
    cfg = load_config(wt)
    assert cfg.data["dashboard"]["url"] == "https://other.example.org"
    assert cfg.data["dashboard"]["push"] == "manual"
    assert read_dashboard_key(wt, cfg, {}) == "sak_" + "B" * 43


def test_environment_variable_beats_the_inherited_key(repo: Repo, tmp_path: Path) -> None:
    set_main_dashboard(repo, url=URL, key=KEY)
    wt = add_worktree(repo, tmp_path)
    cfg = load_config(wt)
    env = {cfg.data["dashboard"]["token_env"]: "sak_" + "C" * 43}
    assert read_dashboard_key(wt, cfg, env) == "sak_" + "C" * 43


def test_the_main_checkout_does_not_inherit_from_anywhere(repo: Repo) -> None:
    cfg = load_config(repo.path)
    assert cfg.data["dashboard"]["url"] is None
    assert read_dashboard_key(repo.path, cfg, {}) is None


def test_dashboard_status_names_the_inherited_source(repo: Repo, tmp_path: Path) -> None:
    set_main_dashboard(repo, url=URL, key=KEY)
    wt = add_worktree(repo, tmp_path)
    code, out = status(wt, env={})
    assert code == 0 and out["url"] == URL
    assert out["key"]["present"] is True and out["key"]["source"] == "main_checkout"
    assert KEY not in str(out)


def test_preflight_warns_when_the_session_directory_is_not_the_run_checkout(
    repo: Repo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wt = add_worktree(repo, tmp_path)
    main = repo.path
    monkeypatch.chdir(wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main))
    repo.path = wt  # Repo.sak() arbeitet über das aktuelle Verzeichnis
    code, out = repo.sak("run", "preflight", "001")
    assert code == 0, out
    warning = next(w for w in out["warnings"] if "CLAUDE_PROJECT_DIR" in w)
    assert "Stations-Events" in warning
    assert Path(out["worktree"]["main_checkout"]).samefile(main)


def test_preflight_is_quiet_when_the_session_runs_in_the_run_checkout(
    repo: Repo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wt = add_worktree(repo, tmp_path)
    monkeypatch.chdir(wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))
    repo.path = wt
    code, out = repo.sak("run", "preflight", "001")
    assert code == 0, out
    assert not [w for w in out.get("warnings", []) if "CLAUDE_PROJECT_DIR" in w]
    assert out["worktree"] is not None


def test_preflight_in_a_plain_checkout_has_no_worktree_note(
    repo: Repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    code, out = repo.sak("run", "preflight", "001")
    assert code == 0 and out["worktree"] is None
    assert "warnings" not in out
