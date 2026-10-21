"""``sak run cleanup``, Links im Lauf-Ordner und neue Top-Level-Ordner (Spec 011 B14, T001).

Links und Ziele liegen ausschließlich in ``tmp_path``. Aufgeräumt wird, ohne Links zu folgen.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from conftest import APPROVE, Repo

from spec_agent_kit.pipeline import links


def make_dir_link(link: Path, target: Path) -> None:
    """Junction (Windows, ohne Rechte nötig) oder Symlink (POSIX)."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            pytest.skip("mklink /J nicht möglich: " + proc.stdout.decode("cp850", "replace"))
    else:
        os.symlink(target, link, target_is_directory=True)


def make_target(base: Path) -> Path:
    target = base / "outside" / "node_modules"
    (target / "pkg").mkdir(parents=True)
    (target / "pkg" / "index.js").write_text("x\n", encoding="utf-8")
    (target / "top.txt").write_text("wichtig\n", encoding="utf-8")
    return target


def assert_target_intact(target: Path) -> None:
    assert (target / "top.txt").read_text(encoding="utf-8") == "wichtig\n"
    assert (target / "pkg" / "index.js").read_text(encoding="utf-8") == "x\n"


def run_dir(repo: Repo, run_id: str) -> Path:
    return repo.path / ".spec-agent" / "state" / "runs" / run_id


def test_is_link_recognises_links_and_not_plain_directories(tmp_path: Path) -> None:
    target = make_target(tmp_path)
    link = tmp_path / "ui" / "node_modules"
    make_dir_link(link, target)
    assert links.is_link(link)
    assert not links.is_link(target)
    assert not links.is_link(tmp_path / "missing")
    assert not links.is_link(target / "top.txt")


def test_remove_links_removes_the_link_and_keeps_the_target(tmp_path: Path) -> None:
    target = make_target(tmp_path)
    root = tmp_path / "run"
    (root / "ui").mkdir(parents=True)
    (root / "ui" / "report.txt").write_text("bleibt\n", encoding="utf-8")
    link = root / "ui" / "node_modules"
    make_dir_link(link, target)
    removed, failed = links.remove_links(root)
    assert removed == [link] and failed == []
    assert not os.path.lexists(link)
    assert_target_intact(target)
    assert (root / "ui" / "report.txt").read_text(encoding="utf-8") == "bleibt\n"


def test_remove_links_never_descends_into_a_link(tmp_path: Path) -> None:
    """Ein Link im Ziel eines Links darf nicht angefasst werden."""
    inner_target = make_target(tmp_path)
    outer_target = tmp_path / "outer"
    outer_target.mkdir()
    make_dir_link(outer_target / "inner-link", inner_target)
    root = tmp_path / "run"
    root.mkdir()
    make_dir_link(root / "outer-link", outer_target)
    removed, _ = links.remove_links(root)
    assert removed == [root / "outer-link"]
    assert os.path.lexists(outer_target / "inner-link")
    assert_target_intact(inner_target)


@pytest.mark.skipif(os.name == "nt", reason="Datei-Symlinks brauchen unter Windows Rechte")
def test_remove_links_removes_file_symlinks(tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    target.write_text("geheim\n", encoding="utf-8")
    root = tmp_path / "run"
    root.mkdir()
    os.symlink(target, root / "file-link")
    removed, _ = links.remove_links(root)
    assert removed == [root / "file-link"]
    assert target.read_text(encoding="utf-8") == "geheim\n"


def test_remove_links_does_nothing_when_the_directory_is_a_link(tmp_path: Path) -> None:
    target = make_target(tmp_path)
    link = tmp_path / "run-link"
    make_dir_link(link, target)
    assert links.remove_links(link) == ([], [])
    assert os.path.lexists(link)
    assert_target_intact(target)


def test_cleanup_command_removes_links_and_keeps_the_target(repo: Repo, tmp_path: Path) -> None:
    run_id = repo.start()
    target = make_target(tmp_path)
    link = run_dir(repo, run_id) / "ui" / "node_modules"
    make_dir_link(link, target)
    code, out = repo.sak("run", "cleanup", run_id)
    assert code == 0 and out["removed"] == ["ui/node_modules"] and out["failed"] == []
    assert not os.path.lexists(link)
    assert_target_intact(target)
    # Zweiter Aufruf: nichts mehr zu tun.
    code, out = repo.sak("run", "cleanup", run_id)
    assert code == 0 and out["removed"] == []


def test_cleanup_refuses_when_the_run_folder_is_a_link(repo: Repo, tmp_path: Path) -> None:
    run_id = repo.start()
    target = make_target(tmp_path)
    folder = run_dir(repo, run_id)
    (folder / "run.json").rename(target / "run.json")
    folder.rmdir()
    make_dir_link(folder, target)
    try:
        code, out = repo.sak("run", "cleanup", run_id, strict=False)
        assert code == 1 and "Link" in out["error"]
        assert os.path.lexists(folder)
        assert_target_intact(target)
    finally:
        links.remove_links(folder.parent)


def test_abort_cleans_links_itself(repo: Repo, tmp_path: Path) -> None:
    run_id = repo.start()
    target = make_target(tmp_path)
    link = run_dir(repo, run_id) / "ui" / "node_modules"
    make_dir_link(link, target)
    code, out = repo.sak("run", "abort", run_id, "--reason", "Test")
    assert code == 0 and out["state"] == "aborted"
    assert out["cleaned_links"] == ["ui/node_modules"]
    assert not os.path.lexists(link)
    assert_target_intact(target)


def test_combine_cleans_links_itself(repo: Repo, tmp_path: Path) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    target = make_target(tmp_path)
    link = run_dir(repo, run_id) / "ui" / "node_modules"
    make_dir_link(link, target)
    repo.verdict(run_id, "code_review", APPROVE, "code.md")
    repo.verdict(run_id, "ui_review", APPROVE, "ui.md")
    code, out = repo.sak("run", "combine", run_id)
    assert code == 0 and out["cleaned_links"] == ["ui/node_modules"]
    assert not os.path.lexists(link)
    assert_target_intact(target)


# --- neue Top-Level-Ordner (reviewer-check) ---------------------------------


def test_reviewer_check_notices_a_new_empty_top_level_folder(repo: Repo) -> None:
    """Leere Ordner sieht ``git status`` nicht: Der Pfad ohne Anführungszeichen erzeugt solche."""
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    _, snap = repo.sak("run", "snapshot")
    (repo.path / "Department").mkdir()
    (repo.path / "Repos").mkdir()
    code, out = repo.sak("run", "reviewer-check", snap["snapshot"])
    assert code == 1 and out["gate"] == "review_integrity" and out["state"] == "escalated"
    assert out["new_top_level_dirs"] == ["Department", "Repos"]
    assert "Department" in out["error"]


def test_reviewer_check_tolerates_ignored_folders_and_tool_caches(repo: Repo) -> None:
    repo.write(".gitignore", ".spec-agent/state/\ntool-out/\nnode_modules/\n")
    repo.commit("ignore")
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    _, snap = repo.sak("run", "snapshot")
    (repo.path / "node_modules").mkdir()  # von .gitignore abgedeckt
    (repo.path / "tool-out" / "x").mkdir(parents=True)  # clean_ignore
    cache = repo.path / ".pytest_cache"
    cache.mkdir()
    (cache / ".gitignore").write_text("*\n", encoding="utf-8")  # Werkzeug-Cache
    code, out = repo.sak("run", "reviewer-check", snap["snapshot"])
    assert code == 0 and out["changed"] is False


def test_reviewer_check_still_catches_a_real_source_change(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    _, snap = repo.sak("run", "snapshot")
    repo.write("src/payments/pay.py", "x = 2\n")
    code, out = repo.sak("run", "reviewer-check", snap["snapshot"])
    assert code == 1 and out["gate"] == "review_integrity"
    assert "new_top_level_dirs" not in out
