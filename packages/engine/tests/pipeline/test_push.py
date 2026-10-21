"""push: nur Basis-Branch, fast-forward, ohne Force und Tags (Spec 012 FR-003, SC-001, SC-002)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Repo

from spec_agent_kit.pipeline import git


def _bare(repo: Repo) -> Path:
    remote = repo.path.parent / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    repo.git("remote", "add", "origin", str(remote))
    repo.git("push", "-q", "origin", "main")
    return remote


def _remote_head(remote: Path, branch: str = "main") -> str:
    out = subprocess.run(
        ["git", "--git-dir", str(remote), "rev-parse", branch],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def _merged(repo: Repo) -> str:
    run_id = repo.start()
    repo.write("src/feature.py", "f = 1\n")
    repo.commit("feat: feature")
    repo.sak("run", "state", run_id, "reviewing")
    repo.sak("run", "state", run_id, "approved")
    code, _ = repo.sak("run", "merge", run_id)
    assert code == 0
    return run_id


def _remote_moves_on(repo: Repo, remote: Path) -> None:
    """Ein zweiter Klon schreibt auf das Remote, sodass der lokale Push kein fast-forward wäre."""
    other = repo.path.parent / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    for args in (
        ("config", "user.name", "o"),
        ("config", "user.email", "o@example.org"),
        ("commit", "-q", "--allow-empty", "-m", "remote moves on"),
        ("push", "-q", "origin", "main"),
    ):
        subprocess.run(["git", *args], cwd=other, check=True)


@pytest.fixture
def pushable(repo: Repo) -> tuple[Repo, Path]:
    repo.set_config(autonomy={"push": "after_merge"})
    return repo, _bare(repo)


def test_approved_to_merged_to_pushed_without_prompt(pushable: tuple[Repo, Path]) -> None:
    repo, remote = pushable
    run_id = _merged(repo)
    assert _remote_head(remote) != repo.git("rev-parse", "HEAD").strip()
    code, out = repo.sak("run", "push", run_id)
    head = repo.git("rev-parse", "HEAD").strip()
    assert code == 0 and out["state"] == "merged"
    assert out["remote"] == "origin" and out["branch"] == "main" and out["commit"] == head
    assert _remote_head(remote) == head
    event = repo.events(run_id)[-1]
    assert event["type"] == "run.pushed"
    assert event["data"] == {"remote": "origin", "branch": "main", "commit": head}
    assert repo.run_json(run_id)["state"] == "merged"


def test_push_sends_no_tags_even_with_follow_tags(pushable: tuple[Repo, Path]) -> None:
    repo, remote = pushable
    repo.git("config", "push.followTags", "true")
    run_id = _merged(repo)
    repo.git("tag", "-a", "v1", "-m", "release")
    code, _ = repo.sak("run", "push", run_id)
    assert code == 0
    tags = subprocess.run(
        ["git", "--git-dir", str(remote), "tag"], capture_output=True, text=True, check=True
    )
    assert tags.stdout.strip() == ""


def test_marker_commit_after_the_merge_can_be_pushed(pushable: tuple[Repo, Path]) -> None:
    repo, remote = pushable
    run_id = _merged(repo)
    repo.sak("run", "push", run_id)
    repo.git("commit", "-q", "--allow-empty", "-m", "deploy(001): ausgerollt")
    code, out = repo.sak("run", "push", run_id)
    assert code == 0 and out["commit"] == _remote_head(remote)
    assert repo.types(run_id).count("run.pushed") == 2


def test_manual_is_the_default_and_refuses_with_a_config_hint(repo: Repo) -> None:
    remote = _bare(repo)
    before = _remote_head(remote)
    run_id = _merged(repo)
    code, out = repo.sak("run", "push", run_id)
    assert code == 1 and "autonomy.push" in out["error"] and "after_merge" in out["error"]
    assert _remote_head(remote) == before
    assert "run.pushed" not in repo.types(run_id)


def test_non_fast_forward_is_refused_with_an_attention_entry(pushable: tuple[Repo, Path]) -> None:
    repo, remote = pushable
    run_id = _merged(repo)
    _remote_moves_on(repo, remote)
    remote_before = _remote_head(remote)
    local_before = repo.git("rev-parse", "HEAD").strip()
    code, out = repo.sak("run", "push", run_id)
    assert code == 1 and "non-fast-forward" in out["error"] and out["state"] == "merged"
    assert _remote_head(remote) == remote_before
    assert repo.git("rev-parse", "HEAD").strip() == local_before  # kein Merge, kein Rebase
    assert repo.run_json(run_id)["state"] == "merged"
    last = repo.events(run_id)[-1]
    assert last["type"] == "run.escalated" and last["data"]["gate"] == "release"
    assert "Push abgelehnt" in last["data"]["reason"]
    assert "run.pushed" not in repo.types(run_id)


def test_run_that_is_not_merged_is_refused(pushable: tuple[Repo, Path]) -> None:
    repo, remote = pushable
    run_id = repo.start()
    repo.write("src/feature.py", "f = 1\n")
    repo.commit("feat: feature")
    repo.sak("run", "state", run_id, "reviewing")
    repo.sak("run", "state", run_id, "approved")
    before = _remote_head(remote)
    code, out = repo.sak("run", "push", run_id)
    assert code == 1 and "gemergte" in out["error"]
    assert _remote_head(remote) == before


def test_foreign_branch_is_refused(pushable: tuple[Repo, Path]) -> None:
    repo, remote = pushable
    run_id = _merged(repo)
    repo.git("switch", "-q", "-c", "side")
    before = _remote_head(remote)
    code, out = repo.sak("run", "push", run_id)
    assert code == 1 and "Basis-Branch" in out["error"] and "side" in out["error"]
    assert _remote_head(remote) == before


def test_base_without_the_merge_commit_is_refused(pushable: tuple[Repo, Path]) -> None:
    repo, _ = pushable
    run_id = _merged(repo)
    repo.git("reset", "-q", "--hard", "HEAD~1")
    code, out = repo.sak("run", "push", run_id)
    assert code == 1 and "Merge-Commit" in out["error"]
    assert "run.escalated" not in repo.types(run_id)


def test_missing_remote_is_refused(repo: Repo) -> None:
    repo.set_config(autonomy={"push": "after_merge", "remote": "upstream"})
    run_id = _merged(repo)
    code, out = repo.sak("run", "push", run_id)
    assert code == 1 and "upstream" in out["error"]


def test_remote_name_cannot_inject_an_option(repo: Repo) -> None:
    repo.set_config(autonomy={"push": "after_merge", "remote": "--force"})
    run_id = _merged(repo)
    code, out = repo.sak("run", "push", run_id)
    assert code == 1 and "nicht eingerichtet" in out["error"]


def test_push_command_is_exactly_remote_and_branch_refspec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Any] = []

    def fake(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake)
    git.push_branch(Path("."), "origin", "main")
    cmd, kwargs = seen[0]
    assert cmd[-3:] == ["push", "origin", "main:main"]
    assert not {"--force", "-f", "--force-with-lease", "--tags", "--mirror", "--delete"} & set(cmd)
    assert kwargs["timeout"] == 60 and kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_timeout_becomes_a_failed_push(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd, 60)

    monkeypatch.setattr(subprocess, "run", fake)
    proc = git.push_branch(Path("."), "origin", "main")
    assert proc.returncode == 124 and "60" in proc.stderr


def test_output_carries_no_credentials() -> None:
    text = "fatal: unable to access 'https://user:s3cret@example.org/repo.git/': failed"
    assert "s3cret" not in git.redact(text) and "user" not in git.redact(text)
    assert "example.org" in git.redact(text)


def test_board_shows_pushed_and_keeps_a_rejection_open_until_pushed(
    pushable: tuple[Repo, Path],
) -> None:
    repo, remote = pushable
    run_id = _merged(repo)
    local_merge = repo.git("rev-parse", "HEAD").strip()
    behind = repo.git("rev-parse", "HEAD~1").strip()
    _remote_moves_on(repo, remote)
    repo.sak("run", "push", run_id)
    _, board = repo.sak("board", "--json")
    run = next(r for r in board["runs"] if r["run_id"] == run_id)
    assert "pushed" not in run and run["escalations"][-1]["open"] is True
    assert [a["kind"] for a in board["attention"]].count("escalation") == 1
    # Der Betreiber klärt die Lage; hier setzen wir das Remote zurück, damit es wieder passt.
    subprocess.run(
        ["git", "--git-dir", str(remote), "update-ref", "refs/heads/main", behind], check=True
    )
    code, _ = repo.sak("run", "push", run_id)
    assert code == 0 and _remote_head(remote) == local_merge
    _, board = repo.sak("board", "--json")
    run = next(r for r in board["runs"] if r["run_id"] == run_id)
    assert run["pushed"] is True and run["escalations"][-1]["open"] is False
    assert [a["kind"] for a in board["attention"]].count("escalation") == 0
