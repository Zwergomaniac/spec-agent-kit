"""``sak doctor`` nach Spec 011: Befehlsprobe, B12, B15, Format, SessionStart."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from install_support import Sak, read_json, write

from spec_agent_kit.cli import main
from spec_agent_kit.install import doctor as doctor_module
from spec_agent_kit.install import probe
from spec_agent_kit.install.kit import Kit

REAL_PROBE = doctor_module._check_hook_probe
needs_sh = pytest.mark.skipif(shutil.which("sh") is None, reason="kein sh vorhanden")
PYTHON = f'"{sys.executable}"'


@pytest.fixture
def ready(
    kit: Kit, target: Path, sak: Sak, init_args: list[str], monkeypatch: pytest.MonkeyPatch
) -> Path:
    monkeypatch.setattr(
        doctor_module,
        "_check_hook_probe",
        lambda root: {"check": "hook_probe", "ok": True, "detail": "ersetzt", "required": True},
    )
    code, out = sak(*init_args, "--apply")
    assert code == 0, out
    write(target, ".spec-agent/engine/.venv/pyvenv.cfg", "home = x\n")
    return target


def by_name(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["check"]: c for c in result["checks"]}


def set_commands(root: Path, **commands: list[str]) -> None:
    path = root / ".spec-agent/config.yml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["commands"] = commands
    path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")


def test_lock_check_explains_the_number_of_entries(ready: Path, sak: Sak) -> None:
    _, result = sak("doctor", str(ready))
    detail = by_name(result)["lock"]["detail"]
    assert "Dateien im Lock" in detail and "vendorten Engine" in detail
    assert "config.yml, lock.json und settings.json sind nicht im Lock" in detail


def test_commands_check_finds_programs_without_running_them(ready: Path, sak: Sak) -> None:
    set_commands(ready, test_fast=[f"{PYTHON} -m pytest -q {{paths}}"])
    _, result = sak("doctor", str(ready))
    check = by_name(result)["commands"]
    assert check["ok"] is True and check["required"] is False
    assert "nur Auffindbarkeit" in check["detail"]


def test_commands_check_reports_a_missing_program_but_stays_optional(ready: Path, sak: Sak) -> None:
    set_commands(ready, test_fast=["gibt-es-nicht-xyz -q"])
    code, result = sak("doctor", str(ready))
    check = by_name(result)["commands"]
    assert check["ok"] is False and code == 0
    assert "gibt-es-nicht-xyz" in check["detail"]


def test_probe_commands_collects_pytest_and_makes_failures_required(ready: Path, sak: Sak) -> None:
    set_commands(ready, test_fast=[f"{PYTHON} -m pytest -q {{paths}}"])
    code, result = sak("doctor", str(ready), "--probe-commands")
    check = by_name(result)["commands"]
    assert code == 0 and check["ok"] is True and check["required"] is True
    assert "keine Tests gesammelt" in check["items"][0]["detail"]
    write(ready, "tests/test_a.py", "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n")
    _, result = sak("doctor", str(ready), "--probe-commands")
    assert "2 Tests gesammelt" in by_name(result)["commands"]["items"][0]["detail"]
    write(ready, "tests/test_bad.py", "import gibt_es_wirklich_nicht_xyz\n")
    code, result = sak("doctor", str(ready), "--probe-commands")
    assert code == 1 and by_name(result)["commands"]["ok"] is False


def test_probe_commands_times_out(ready: Path, sak: Sak, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe, "PROBE_TIMEOUT_SECONDS", 1)
    write(ready, "tests/conftest.py", "import time\n\ntime.sleep(10)\n")
    set_commands(ready, test_full=[f"{PYTHON} -m pytest -q"])
    code, result = sak("doctor", str(ready), "--probe-commands")
    check = by_name(result)["commands"]
    assert code == 1 and "länger als 1 s" in check["items"][0]["detail"]


def test_probe_runs_version_for_other_tools_and_never_runs_prepare(ready: Path, sak: Sak) -> None:
    set_commands(
        ready,
        lint=[f"{PYTHON} lint.py"],
        prepare=[f"{PYTHON} -c \"open('sentinel.txt', 'w')\""],
    )
    code, result = sak("doctor", str(ready), "--probe-commands")
    items = {i["kind"]: i for i in by_name(result)["commands"]["items"]}
    assert code == 0
    assert items["lint"]["detail"].startswith("--version: Python")
    assert "nicht ausgeführt" in items["prepare"]["detail"]
    assert not (ready / "sentinel.txt").exists()


def test_shell_commands_are_not_probed(ready: Path, sak: Sak) -> None:
    set_commands(ready, prepare=["cd web && npm ci"])
    _, result = sak("doctor", str(ready), "--probe-commands")
    item = by_name(result)["commands"]["items"][0]
    assert item["ok"] is True and "nicht geprüft" in item["detail"]


def test_missing_session_start_hook_is_only_a_warning(ready: Path, sak: Sak) -> None:
    path = ready / ".claude/settings.json"
    settings = read_json(path)
    settings["hooks"]["SessionStart"] = [
        e for e in settings["hooks"]["SessionStart"] if "matcher" not in e
    ]
    path.write_text(json.dumps(settings), encoding="utf-8")
    code, result = sak("doctor", str(ready))
    check = by_name(result)["hooks_and_deny"]
    assert code == 0 and check["ok"] is True and check["warning"] is True
    assert "SessionStart" in check["detail"]


def test_unsafe_default_mode_shows_up_as_a_warning_check(ready: Path, sak: Sak) -> None:
    unsafe = "bypass" + "Permissions"
    settings = {"permissions": {"defaultMode": unsafe}}
    write(ready, ".claude/settings.local.json", json.dumps(settings))
    code, result = sak("doctor", str(ready))
    check = by_name(result)["default_mode"]
    assert code == 0 and check["ok"] is True and check["warning"] is True
    assert "settings.local.json" in check["detail"]


def test_doctor_text_format(ready: Path, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()
    assert main(["doctor", str(ready), "--format", "text"]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines()[0].startswith("[ok] lock:")
    assert captured.out.rstrip().endswith("Ergebnis: ok") and captured.err == ""


def test_hook_probe_without_any_sh_names_git_for_windows(
    ready: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(doctor_module, "find_sh", lambda: None)
    check = REAL_PROBE(ready)
    assert check["ok"] is False and "Git for Windows" in check["detail"]


@needs_sh
def test_hook_probe_fails_when_session_start_misbehaves(
    ready: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    uv = tmp_path / "bin" / "uv"
    uv.parent.mkdir(parents=True)
    script = '#!/bin/sh\ncase "$*" in\n  *session-start) echo kaputt ;;\nesac\nexit 0\n'
    uv.write_bytes(script.encode())
    uv.chmod(0o755)
    monkeypatch.setenv("SAK_UV", uv.as_posix())
    check = REAL_PROBE(ready)
    assert check["ok"] is False and "session-start" in check["detail"]
