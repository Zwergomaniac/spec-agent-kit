"""Ein echter Lauf: ``uv sync`` im vendorten Engine-Ordner und ``sak`` daraus (Spec 005 FR-009).

Braucht uv; Abhängigkeiten kommen aus dem uv-Cache (offline möglich) oder aus dem Netz.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from install_support import Sak, git

from spec_agent_kit.install.apply import _uv_executable
from spec_agent_kit.install.kit import Kit


def _run(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        k: v for k, v in os.environ.items() if k not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"}
    }
    return subprocess.run(
        [str(_uv_executable()), "run", "--project", ".spec-agent/engine", "sak", *args],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
        timeout=300,
        check=False,
    )


@pytest.mark.skipif(_uv_executable() is None, reason="uv nicht gefunden")
def test_real_sync_and_vendored_engine_runs(kit: Kit, target: Path, sak: Sak) -> None:
    code, out = sak(
        "init", str(target), "--key", "ai-forge", "--name", "AI-Forge", "--no-ui", "--apply"
    )
    assert code == 0, (out.get("uv_sync"), out.get("config_check"))
    assert out["uv_sync"]["ok"] is True
    assert (target / ".spec-agent/engine/.venv/pyvenv.cfg").is_file()

    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "sak init")
    check = _run(target, "config", "check")
    assert check.returncode == 0, check.stdout + check.stderr
    doctor = _run(target, "doctor")
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "läuft" in doctor.stdout
    # Die vendorte Engine lehnt init ab: sie hat kein Kit-Repo.
    refused = _run(target, "init", str(target), "--key", "x-y", "--name", "n")
    assert refused.returncode == 1
    assert "aus dem Kit-Repo aufrufen" in refused.stdout
    # Die Umgebung und Caches erscheinen nicht als Änderung im Arbeitsstand.
    assert git(target, "status", "--porcelain", "-uall") == ""
