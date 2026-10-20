"""Fixture-Repo für die Pipeline-Tests: git init, Config, Kit-Agents, eine Spec mit tasks.md."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from spec_agent_kit import contracts
from spec_agent_kit.cli import main
from spec_agent_kit.pipeline import runs

CONFIG: dict[str, Any] = {
    "schema": "sak.config/1",
    "project": {"key": "demo", "name": "Demo", "base_branch": "main"},
    "pipeline": {"max_rounds": 2},
    "ui": {"command": "echo ui", "base_url": "http://127.0.0.1:5173"},
    "guard": {"protected_paths": [".claude/commands/"], "clean_ignore": ["tool-out/"]},
    "escalation": {"paths": ["src/payments/"], "topics": ["Zahlungen"]},
}
AGENTS: dict[str, tuple[str, str]] = {
    "sak-builder": ("sonnet", "medium"),
    "sak-code-reviewer": ("opus", "medium"),
    "sak-ui-reviewer": ("sonnet", "medium"),
}

APPROVE = "Verdict: approve\n\n## Befunde\n- [may] a.py:1 — Hinweis\n\n## Geprüft\n- Tests\n"
CHANGES = (
    "Verdict: changes_requested\nReason: Überlauf mobil\n\n## Befunde\n"
    "- [must] web/style.css:880 — Überlauf → min-width entfernen\n"
)
HUMAN = "Verdict: needs_human\nReason: Migration auf Bestandsdaten\n"


class Clock:
    """Steuerbare UTC-Uhr für ``runs.utcnow``."""

    def __init__(self) -> None:
        self.now = datetime.now(UTC).replace(microsecond=0)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


class Repo:
    """Ein Wegwerf-Repo mit Hilfen zum Schreiben, Committen und Aufrufen von ``sak``."""

    def __init__(self, path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
        self.path = path
        self._monkeypatch = monkeypatch
        self._capsys = capsys

    def git(self, *args: str) -> str:
        out = subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
            cwd=self.path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return out.stdout

    def write(self, rel: str, text: str) -> Path:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        return target

    def commit(self, message: str = "work") -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def branch(self) -> str:
        return self.git("branch", "--show-current").strip()

    def sak(self, *argv: str, stdin: str = "", strict: bool = True) -> tuple[int, dict[str, Any]]:
        """Ruft ``sak`` auf. Ein verworfenes Event (``warnings``) lässt den Test scheitern."""
        self._monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
        self._capsys.readouterr()
        code = main(list(argv))
        out = self._capsys.readouterr().out.strip()
        data: dict[str, Any] = json.loads(out) if out else {}
        if strict:
            bad = [w for w in data.get("warnings", []) if w.startswith("Event verworfen")]
            assert not bad, bad
        return code, data

    def events(self, run_id: str | None = None) -> list[dict[str, Any]]:
        path = self.path / ".spec-agent" / "state" / "events.jsonl"
        if not path.is_file():
            return []
        found = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        for event in found:
            assert contracts.validate_event(event) == [], event
        return [e for e in found if run_id is None or e.get("run_id") == run_id]

    def types(self, run_id: str | None = None) -> list[str]:
        return [e["type"] for e in self.events(run_id)]

    def run_json(self, run_id: str) -> dict[str, Any]:
        path = self.path / ".spec-agent" / "state" / "runs" / run_id / "run.json"
        loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return loaded

    def start(self, spec: str = "001", *extra: str) -> str:
        """Startet einen Lauf und gibt die Lauf-ID zurück."""
        code, out = self.sak("run", "preflight", spec, *extra)
        assert code == 0, out
        run_id: str = out["run_id"]
        return run_id

    def verdict(self, run: str, role: str, text: str, name: str = "answer.md") -> tuple[int, Any]:
        file = self.write(f"tool-out/{name}", text)
        return self.sak("run", "verdict", run, role, str(file))

    def set_config(self, **sections: Any) -> None:
        config = json.loads(json.dumps(CONFIG))
        config.update(sections)
        config = {k: v for k, v in config.items() if v is not None}
        self.write(".spec-agent/config.yml", yaml.safe_dump(config, allow_unicode=True))
        self.commit("config")

    def add_spec(self, name: str) -> None:
        self.write(f"specs/{name}/tasks.md", "- [ ] T001 y\n")
        self.commit(f"spec {name}")


@pytest.fixture(scope="session")
def repo_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Einmal gebautes Fixture-Repo; jeder Test arbeitet auf einer Kopie (spart Git-Aufrufe)."""
    path = tmp_path_factory.mktemp("template")
    fx = Repo(path, pytest.MonkeyPatch(), None)
    fx.git("init", "-q", "-b", "main")
    fx.git("config", "user.name", "Test")
    fx.git("config", "user.email", "test@example.org")
    fx.write(".gitignore", ".spec-agent/state/\ntool-out/\n")
    fx.write(".spec-agent/config.yml", yaml.safe_dump(CONFIG, allow_unicode=True))
    for name, (model, effort) in AGENTS.items():
        fx.write(
            f".claude/agents/{name}.md",
            f"---\nname: {name}\nmodel: {model}\neffort: {effort}\n---\nPrompt\n",
        )
    fx.write("specs/001-demo/tasks.md", "- [ ] T001 x\n")
    fx.write("src/payments/pay.py", "x = 1\n")
    fx.commit("init")
    return path


@pytest.fixture
def repo(
    repo_template: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> Repo:
    target = tmp_path / "work"
    shutil.copytree(repo_template, target)
    monkeypatch.chdir(target)
    return Repo(target, monkeypatch, capsys)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(runs, "utcnow", fake)
    return fake
