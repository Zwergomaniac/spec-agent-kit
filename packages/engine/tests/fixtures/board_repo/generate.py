"""Erzeugt das deterministische Fixture-Repo für die Board-Tests (Spec 006, T001).

Feste Autor- und Commit-Daten (``GIT_AUTHOR_DATE``/``GIT_COMMITTER_DATE``) ergeben dieselben
Commit-SHAs auf jeder Maschine. Das Repo enthält 6 Specs in verschiedenen Stationen:

=====  ==============  =======================================================================
Nr.    Name            Besonderheit
=====  ==============  =======================================================================
001    foundation      verified (Deploy- und Verified-Marker), gemergter Lauf
002    importer        deployed, pausierter Lauf
003    search          implementing (3/5), Betreiber-Task, eskalierter Lauf
004    billing         deploy-Marker VOR dem letzten Task-Commit, daher implemented
005    notify          tasked ohne erledigte Task, kein Lauf: wartet auf Freigabe (approval)
006    export          specified, offene Klärung; in 005 steht der Marker nur in einem Code-Span
=====  ==============  =======================================================================

Die Läufe (``.spec-agent/state/``) sind gitignored und werden direkt geschrieben.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from spec_agent_kit import contracts

TZ = "+02:00"
PROJECT = "demo-board"
NOW = "2026-10-10T11:00:00Z"
"""Die feste „aktuelle“ Zeit der Golden-File-Tests (Tests ersetzen ``runs.utcnow``)."""

CONFIG = """\
schema: sak.config/1
project:
  key: demo-board
  name: Demo Board
  base_branch: main
pipeline:
  roles:
    ui_review:
      enabled: false
"""


def _run(path: Path, args: list[str], date: str | None = None) -> str:
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="Fixture",
        GIT_AUTHOR_EMAIL="fixture@example.org",
        GIT_COMMITTER_NAME="Fixture",
        GIT_COMMITTER_EMAIL="fixture@example.org",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
    )
    if date is not None:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    done = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *args],
        cwd=path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return done.stdout


class FixtureRepo:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, rel: str, text: str) -> None:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")

    def commit(
        self, message: str, day: str, files: dict[str, str] | None = None, hour: str = "10:00:00"
    ) -> None:
        for rel, text in (files or {}).items():
            self.write(rel, text)
        _run(self.path, ["add", "-A"])
        _run(
            self.path,
            ["commit", "-q", "--allow-empty", "-m", message],
            date=f"2026-{day}T{hour}{TZ}",
        )


def _spec(title: str, extra: str = "", clarified: bool = False, status: str = "Draft") -> str:
    head = f"# Feature Specification: {title}\n\n**Status**: {status}\n\n"
    body = "## Ziel\n\nText.\n\n" + extra
    if clarified:
        body += "\n## Clarifications\n\n- Q: ? A: ja\n"
    return head + body


def _tasks(done: int, open_: int, extra_open: list[str] | None = None) -> str:
    lines = [f"- [{'X' if i % 2 else 'x'}] T{i + 1:03d} erledigt" for i in range(done)]
    lines += [f"- [ ] T{done + i + 1:03d} offen" for i in range(open_)]
    lines += [f"- [ ] {text}" for text in extra_open or []]
    return "# Tasks\n\n" + "\n".join(lines) + "\n"


def _event(etype: str, ts: str, run: dict[str, Any], **data: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "schema": "sak.event/1",
        "event_id": contracts.new_ulid(),
        "type": etype,
        "ts": ts,
        "project": PROJECT,
        "run_id": run["run_id"],
        "spec": run["spec"],
        "data": data,
    }
    assert contracts.validate_event(event) == [], (etype, contracts.validate_event(event))
    return event


def _write_run(path: Path, run: dict[str, Any], events: list[dict[str, Any]]) -> None:
    state = path / ".spec-agent" / "state"
    run_dir = state / "runs" / run["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    with (state / "events.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def _run_json(run_id: str, spec: str, state: str, rnd: int, started: str, **extra: Any) -> dict[str, Any]:
    run: dict[str, Any] = {
        "run_id": run_id,
        "spec": spec,
        "kind": "pipeline",
        "state": state,
        "paused_from": None,
        "round": rnd,
        "max_rounds": 2,
        "branch": spec,
        "base_branch": "main",
        "base_commit": "a" * 40,
        "started_at": started,
        "updated_at": started,
        "escalation": None,
        "origin": {"branch": "main"},
    }
    run.update(extra)
    return run


def _station(
    run: dict[str, Any], role: str, agent: str, rnd: int, start: str, end: str, secs: float
) -> list[dict[str, Any]]:
    return [
        _event("station.started", start, run, round=rnd, role=role, agent=agent, model="sonnet"),
        _event("station.finished", end, run, round=rnd, role=role, agent=agent, duration_s=secs),
    ]


def build_fixture_repo(path: Path) -> Path:
    """Legt das Fixture-Repo in ``path`` an (muss leer sein) und gibt ``path`` zurück."""
    path.mkdir(parents=True, exist_ok=True)
    _run(path, ["init", "-q", "-b", "main"])
    repo = FixtureRepo(path)
    repo.commit(
        "chore: init",
        "10-01",
        {
            ".gitignore": ".spec-agent/state/\n",
            ".spec-agent/config.yml": CONFIG,
            "README.md": "# Demo\n",
        },
        hour="09:00:00",
    )

    # 001: durchgängig bis verified.
    repo.commit("docs(001): spec", "10-01", {"specs/001-foundation/spec.md": _spec("Foundation", clarified=True)})
    repo.commit("docs(001): plan", "10-01", {"specs/001-foundation/plan.md": "# Plan\n"}, hour="11:00:00")
    repo.commit("docs(001): tasks", "10-01", {"specs/001-foundation/tasks.md": _tasks(0, 3)}, hour="12:00:00")
    repo.commit("feat(001): alles", "10-02", {"specs/001-foundation/tasks.md": _tasks(3, 0), "src/a.py": "a = 1\n"})
    repo.commit("deploy(001): foundation live", "10-02", hour="12:00:00")
    repo.commit("verified(001): foundation geprüft", "10-03", hour="08:00:00")

    # 002: bis deployed.
    repo.commit("docs(002): spec", "10-04", {"specs/002-importer/spec.md": _spec("Importer")}, hour="08:00:00")
    repo.commit("docs(002): plan", "10-04", {"specs/002-importer/plan.md": "# Plan\n"}, hour="09:00:00")
    repo.commit("docs(002): tasks", "10-04", {"specs/002-importer/tasks.md": _tasks(0, 2)}, hour="10:00:00")
    repo.commit("feat(002): importer", "10-05", {"specs/002-importer/tasks.md": _tasks(2, 0), "src/b.py": "b = 1\n"}, hour="09:00:00")
    repo.commit("deploy(002): importer", "10-05", hour="14:00:00")

    # 004: Deploy-Marker VOR dem letzten Commit an tasks.md -> Station implemented.
    repo.commit("docs(004): spec", "10-06", {"specs/004-billing/spec.md": _spec("Billing", clarified=True)}, hour="08:00:00")
    repo.commit("docs(004): plan", "10-06", {"specs/004-billing/plan.md": "# Plan\n"}, hour="09:00:00")
    repo.commit("docs(004): tasks", "10-06", {"specs/004-billing/tasks.md": _tasks(1, 1)}, hour="10:00:00")
    repo.commit("deploy(004): erste Stufe", "10-07", hour="10:00:00")
    repo.commit("feat(004): rest", "10-08", {"specs/004-billing/tasks.md": _tasks(2, 0), "src/c.py": "c = 1\n"}, hour="10:00:00")

    # 003: implementing mit Betreiber-Task.
    repo.commit("docs(003): spec", "10-08", {"specs/003-search/spec.md": _spec("Search")}, hour="12:00:00")
    repo.commit("docs(003): plan", "10-08", {"specs/003-search/plan.md": "# Plan\n"}, hour="13:00:00")
    repo.commit("docs(003): tasks", "10-08", {"specs/003-search/tasks.md": _tasks(0, 5)}, hour="14:00:00")
    repo.commit(
        "feat(003): erste Tasks",
        "10-09",
        {
            "specs/003-search/tasks.md": _tasks(3, 1, ["T099 **[Betreiber]** DNS-Eintrag setzen"]),
            "src/d.py": "d = 1\n",
        },
    )

    # 005: tasked, kein Lauf; der Klärungsmarker steht nur im Code-Span.
    repo.commit(
        "docs(005): spec",
        "10-09",
        {
            "specs/005-notify/spec.md": _spec(
                "Notify", "Offene Fragen stehen als `[NEEDS CLARIFICATION: ...]` im Text.\n"
            )
        },
        hour="12:00:00",
    )
    repo.commit("docs(005): tasks", "10-09", {"specs/005-notify/tasks.md": _tasks(0, 4)}, hour="13:00:00")

    # 006: nur spec.md, echter Klärungsmarker.
    repo.commit(
        "docs(006): spec",
        "10-10",
        {"specs/006-export/spec.md": _spec("Export", "Format: [NEEDS CLARIFICATION: CSV oder XLSX?]\n")},
        hour="08:00:00",
    )

    # Läufe (gitignored, direkt geschrieben).
    done = _run_json("001-20261002-080000", "001-foundation", "merged", 1, "2026-10-02T08:00:00Z")
    done["updated_at"] = "2026-10-02T09:00:00Z"
    events = [
        _event("run.started", "2026-10-02T08:00:00Z", done, kind="pipeline", base_branch="main", base_commit="a" * 40, max_rounds=2),
        _event("round.started", "2026-10-02T08:00:00Z", done, round=1),
        *_station(done, "builder", "sak-builder", 1, "2026-10-02T08:01:00Z", "2026-10-02T08:21:00Z", 1200),
        *_station(done, "code_review", "sak-code-reviewer", 1, "2026-10-02T08:22:00Z", "2026-10-02T08:30:00Z", 480),
        _event("verdict.recorded", "2026-10-02T08:31:00Z", done, round=1, role="code_review", verdict="approve", must_count=0, may_count=1),
        _event("run.approved", "2026-10-02T08:31:30Z", done),
        _event("run.merged", "2026-10-02T09:00:00Z", done, merge_commit="b" * 40),
    ]
    _write_run(path, done, events)

    paused = _run_json("002-20261005-080000", "002-importer", "paused", 1, "2026-10-05T08:00:00Z", paused_from="building")
    paused["updated_at"] = "2026-10-05T08:30:00Z"
    _write_run(
        path,
        paused,
        [
            _event("run.started", "2026-10-05T08:00:00Z", paused, kind="pipeline", base_branch="main", base_commit="a" * 40, max_rounds=2),
            _event("round.started", "2026-10-05T08:00:00Z", paused, round=1),
            _event("station.started", "2026-10-05T08:05:00Z", paused, round=1, role="builder", agent="sak-builder", model="sonnet"),
            _event("run.paused", "2026-10-05T08:30:00Z", paused, reason="API-Limit"),
        ],
    )

    esc = _run_json(
        "003-20261010-090000",
        "003-search",
        "escalated",
        2,
        "2026-10-10T09:00:00Z",
        escalation={"reason": "Rundenlimit erreicht", "gate": "round_limit", "round": 2},
    )
    esc["updated_at"] = "2026-10-10T10:30:00Z"
    _write_run(
        path,
        esc,
        [
            _event("run.started", "2026-10-10T09:00:00Z", esc, kind="pipeline", base_branch="main", base_commit="a" * 40, max_rounds=2),
            _event("round.started", "2026-10-10T09:00:00Z", esc, round=1),
            *_station(esc, "builder", "sak-builder", 1, "2026-10-10T09:01:00Z", "2026-10-10T09:20:00Z", 1140),
            *_station(esc, "code_review", "sak-code-reviewer", 1, "2026-10-10T09:21:00Z", "2026-10-10T09:30:00Z", 540),
            _event("verdict.recorded", "2026-10-10T09:31:00Z", esc, round=1, role="code_review", verdict="changes_requested", must_count=2, may_count=0),
            _event("run.returned", "2026-10-10T09:32:00Z", esc, reason="Befunde beheben"),
            _event("round.started", "2026-10-10T09:32:00Z", esc, round=2),
            *_station(esc, "builder", "sak-builder", 2, "2026-10-10T09:33:00Z", "2026-10-10T09:50:00Z", 1020),
            *_station(esc, "code_review", "sak-code-reviewer", 2, "2026-10-10T09:51:00Z", "2026-10-10T10:00:00Z", 540),
            _event("verdict.recorded", "2026-10-10T10:01:00Z", esc, round=2, role="code_review", verdict="changes_requested", must_count=1, may_count=0),
            _event("run.escalated", "2026-10-10T10:30:00Z", esc, round=2, gate="round_limit", reason="Rundenlimit erreicht"),
        ],
    )
    return path
