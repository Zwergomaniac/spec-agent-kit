"""``sak doctor`` (Spec 005 US4, FR-008; T011)."""

from __future__ import annotations

import json
import shutil
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from install_support import Sak, git, read_json, write

from spec_agent_kit import __version__
from spec_agent_kit.install import doctor as doctor_module
from spec_agent_kit.install.doctor import run_doctor
from spec_agent_kit.install.kit import Kit

CHECKS = {
    "lock",
    "config",
    "engine",
    "hooks_and_deny",
    "hook_probe",
    "gitignore",
    "speckit",
    "commands",
}
REAL_PROBE = doctor_module._check_hook_probe


@pytest.fixture
def ready(
    kit: Kit, target: Path, sak: Sak, init_args: list[str], monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Ein initialisiertes Projekt mit (angetäuschter) Engine-Umgebung.

    Die echte Hook-Probe braucht ein funktionierendes uv; hier ist sie ersetzt, die Probe-Tests
    unten rufen ``REAL_PROBE`` mit einem unechten uv auf.
    """
    monkeypatch.setattr(
        doctor_module,
        "_check_hook_probe",
        lambda root: {"check": "hook_probe", "ok": True, "detail": "ersetzt", "required": True},
    )
    code, out = sak(*init_args, "--apply")
    assert code == 0, out
    write(target, ".spec-agent/engine/.venv/pyvenv.cfg", "home = x\n")
    return target


def _by_name(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["check"]: c for c in result["checks"]}


class _Health(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self) -> None:
        self.send_response(self.status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        return


@pytest.fixture
def health_server() -> Iterator[ThreadingHTTPServer]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Health)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_a_healthy_project_passes_every_check(ready: Path, sak: Sak) -> None:
    code, result = sak("doctor", str(ready))
    assert code == 0, result
    assert result["ok"] is True
    checks = _by_name(result)
    assert set(checks) == CHECKS  # ohne Dashboard-URL keine Dashboard-Prüfung
    for check in result["checks"]:
        assert set(check) >= {"check", "ok", "detail"}
        assert check["ok"] is True, check
        assert check["detail"]


def test_doctor_uses_the_current_project_without_an_argument(
    ready: Path, sak: Sak, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(ready)
    code, result = sak("doctor")
    assert code == 0, result


def test_uninitialized_project_fails_with_exit_1(target: Path, sak: Sak) -> None:
    code, result = sak("doctor", str(target))
    assert code == 1
    checks = _by_name(result)
    assert checks["lock"]["ok"] is False
    assert "nicht initialisiert" in checks["lock"]["detail"]
    assert checks["config"]["ok"] is False
    assert checks["speckit"]["ok"] is True


def test_missing_managed_file_fails_the_lock_check(ready: Path, sak: Sak) -> None:
    (ready / ".claude/agents/sak-docs.md").unlink()
    code, result = sak("doctor", str(ready))
    assert code == 1
    assert _by_name(result)["lock"]["ok"] is False
    assert "sak-docs.md" in _by_name(result)["lock"]["detail"]


def test_locally_modified_file_is_allowed(ready: Path, sak: Sak) -> None:
    path = ready / ".claude/agents/sak-docs.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nLokal.\n", encoding="utf-8")
    code, result = sak("doctor", str(ready))
    assert code == 0, result
    assert "lokal geändert" in _by_name(result)["lock"]["detail"]


def test_invalid_lock_fails(ready: Path, sak: Sak) -> None:
    lock = read_json(ready / ".spec-agent/lock.json")
    lock["files"]["x"] = "kein-hash"
    (ready / ".spec-agent/lock.json").write_text(json.dumps(lock), encoding="utf-8")
    code, result = sak("doctor", str(ready))
    assert code == 1
    assert "ungültig" in _by_name(result)["lock"]["detail"]


def test_invalid_config_fails(ready: Path, sak: Sak) -> None:
    config = ready / ".spec-agent/config.yml"
    config.write_text(config.read_text(encoding="utf-8") + "\nunbekannt: 1\n", encoding="utf-8")
    code, result = sak("doctor", str(ready))
    assert code == 1
    assert _by_name(result)["config"]["ok"] is False
    assert "unbekannt" in _by_name(result)["config"]["detail"]


def test_missing_engine_environment_fails_with_a_hint(ready: Path, sak: Sak) -> None:
    (ready / ".spec-agent/engine/.venv/pyvenv.cfg").unlink()
    code, result = sak("doctor", str(ready))
    assert code == 1
    assert "uv sync" in _by_name(result)["engine"]["detail"]


def test_engine_check_passes_when_called_from_the_vendored_engine(ready: Path) -> None:
    (ready / ".spec-agent/engine/.venv/pyvenv.cfg").unlink()
    engine = ready / ".spec-agent" / "engine"
    result = run_doctor(ready, engine_running_from=engine)
    assert _by_name(result)["engine"]["ok"] is True


def test_missing_engine_folder_fails(ready: Path, sak: Sak) -> None:
    (ready / ".spec-agent/engine/pyproject.toml").unlink()
    code, result = sak("doctor", str(ready))
    assert code == 1
    assert _by_name(result)["engine"]["ok"] is False


def test_missing_hook_fails(ready: Path, sak: Sak) -> None:
    path = ready / ".claude/settings.json"
    settings = read_json(path)
    del settings["hooks"]["SubagentStop"]
    path.write_text(json.dumps(settings), encoding="utf-8")
    code, result = sak("doctor", str(ready))
    assert code == 1
    assert "SubagentStop" in _by_name(result)["hooks_and_deny"]["detail"]


def test_missing_deny_rule_fails(ready: Path, sak: Sak) -> None:
    path = ready / ".claude/settings.json"
    settings = read_json(path)
    settings["permissions"]["deny"].remove("Bash(git push)")
    path.write_text(json.dumps(settings), encoding="utf-8")
    code, result = sak("doctor", str(ready))
    assert code == 1
    assert "Bash(git push)" in _by_name(result)["hooks_and_deny"]["detail"]


def test_missing_settings_file_fails(ready: Path, sak: Sak) -> None:
    (ready / ".claude/settings.json").unlink()
    code, result = sak("doctor", str(ready))
    assert code == 1
    assert _by_name(result)["hooks_and_deny"]["ok"] is False


def test_state_not_gitignored_fails(ready: Path, sak: Sak) -> None:
    (ready / ".spec-agent/.gitignore").write_text("dashboard.key\n", encoding="utf-8")
    code, result = sak("doctor", str(ready))
    assert code == 1
    assert "state" in _by_name(result)["gitignore"]["detail"]


def test_unsupported_speckit_fails(ready: Path, sak: Sak) -> None:
    write(ready, ".specify/init-options.json", '{"speckit_version": "0.11.0"}\n')
    code, result = sak("doctor", str(ready))
    assert code == 1
    assert "zu alt" in _by_name(result)["speckit"]["detail"]


def _with_dashboard(root: Path, url: str) -> None:
    config = root / ".spec-agent/config.yml"
    text = config.read_text(encoding="utf-8").replace("  url: null", f'  url: "{url}"', 1)
    config.write_text(text, encoding="utf-8")


def test_reachable_dashboard_passes(
    ready: Path, sak: Sak, health_server: ThreadingHTTPServer
) -> None:
    _with_dashboard(ready, f"http://127.0.0.1:{health_server.server_address[1]}")
    write(ready, ".spec-agent/dashboard.key", "sak_" + "A" * 43 + "\n")
    code, result = sak("doctor", str(ready))
    assert code == 0, result
    check = _by_name(result)["dashboard"]
    assert check["ok"] is True
    assert "healthz" in check["detail"] and "Schlüssel vorhanden (file)" in check["detail"]


def test_reachable_dashboard_without_a_key_is_not_ok(
    ready: Path, sak: Sak, health_server: ThreadingHTTPServer
) -> None:
    """Spec 011 B15: erreichbar genügt nicht."""
    _with_dashboard(ready, f"http://127.0.0.1:{health_server.server_address[1]}")
    code, result = sak("doctor", str(ready))
    check = _by_name(result)["dashboard"]
    assert check["ok"] is False and check["required"] is False and code == 0
    assert "keinen Schlüssel" in check["detail"]


def test_unreachable_dashboard_is_reported_but_not_required(ready: Path, sak: Sak) -> None:
    _with_dashboard(ready, "http://127.0.0.1:1")
    code, result = sak("doctor", str(ready))
    check = _by_name(result)["dashboard"]
    assert check["ok"] is False
    assert check["required"] is False
    assert result["ok"] is True
    assert code == 0


def test_dashboard_server_error_counts_as_unreachable(
    ready: Path, sak: Sak, health_server: ThreadingHTTPServer
) -> None:
    _Health.status = 503
    try:
        _with_dashboard(ready, f"http://127.0.0.1:{health_server.server_address[1]}")
        _, result = sak("doctor", str(ready))
    finally:
        _Health.status = 200
    assert _by_name(result)["dashboard"]["ok"] is False


def test_doctor_writes_nothing(ready: Path, sak: Sak) -> None:
    before = git(ready, "status", "--porcelain", "-uall")
    sak("doctor", str(ready))
    assert git(ready, "status", "--porcelain", "-uall") == before


# ------------------------------------------------------------------------------- Hook-Probe


def _fake_uv(path: Path, version: str = __version__) -> str:
    """Ein unechtes uv als sh-Skript: ``sak version`` liefert JSON, alles andere endet still."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "#!/bin/sh\n"
        'case "$*" in\n'
        f"  *' sak version') echo '{{\"version\": \"{version}\"}}' ;;\n"
        "esac\n"
        "exit 0\n"
    )
    path.write_bytes(body.encode())
    path.chmod(0o755)
    return path.as_posix()


needs_sh = pytest.mark.skipif(shutil.which("sh") is None, reason="kein sh vorhanden")


@needs_sh
def test_hook_probe_passes_with_a_working_starter(
    ready: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAK_UV", _fake_uv(tmp_path / "bin" / "uv"))
    check = REAL_PROBE(ready)
    assert check["ok"] is True, check
    assert check["check"] == "hook_probe"


@needs_sh
def test_hook_probe_fails_with_exit_127_when_uv_is_missing(
    ready: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAK_UV", (tmp_path / "gibt-es-nicht").as_posix())
    check = REAL_PROBE(ready)
    assert check["ok"] is False
    assert check["required"] is True
    assert "127" in check["detail"] and "SAK_UV" in check["detail"]


@needs_sh
def test_hook_probe_fails_on_a_wrong_kit_version(
    ready: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAK_UV", _fake_uv(tmp_path / "bin" / "uv", version="9.9.9"))
    check = REAL_PROBE(ready)
    assert check["ok"] is False
    assert __version__ in check["detail"]


def test_hook_probe_fails_without_the_starter(ready: Path) -> None:
    (ready / ".spec-agent/sak").unlink()
    check = REAL_PROBE(ready)
    assert check["ok"] is False
    assert ".spec-agent/sak" in check["detail"]


@needs_sh
def test_failing_probe_makes_the_doctor_fail(
    ready: Path, sak: Sak, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(doctor_module, "_check_hook_probe", REAL_PROBE)
    monkeypatch.setenv("SAK_UV", (tmp_path / "gibt-es-nicht").as_posix())
    code, result = sak("doctor", str(ready))
    assert code == 1
    assert _by_name(result)["hook_probe"]["ok"] is False


def test_hook_entries_pointing_at_the_starter_pass_without_warning(ready: Path, sak: Sak) -> None:
    _, result = sak("doctor", str(ready))
    check = _by_name(result)["hooks_and_deny"]
    assert check["ok"] is True
    assert "warning" not in check


def test_old_direct_uv_hook_is_a_warning_pointing_to_upgrade(ready: Path, sak: Sak) -> None:
    path = ready / ".claude/settings.json"
    settings = read_json(path)
    settings["hooks"]["SubagentStart"][0]["hooks"][0]["command"] = (
        'uv run --project "$CLAUDE_PROJECT_DIR/.spec-agent/engine" sak hook subagent-start || true'
    )
    path.write_text(json.dumps(settings), encoding="utf-8")
    code, result = sak("doctor", str(ready))
    check = _by_name(result)["hooks_and_deny"]
    assert code == 0, result
    assert check["ok"] is True and check["warning"] is True
    assert "sak upgrade" in check["detail"] and "SubagentStart" in check["detail"]


def test_proxy_mode_needs_no_key_when_healthz_answers(
    ready: Path, sak: Sak, health_server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec 013: im Proxy-Modus genügt ein erreichbares /healthz."""
    _with_dashboard(ready, f"http://127.0.0.1:{health_server.server_address[1]}")
    monkeypatch.setenv("SAK_DASHBOARD_AUTH", "proxy")
    monkeypatch.delenv("SAK_DASHBOARD_TOKEN", raising=False)
    code, result = sak("doctor", str(ready))
    check = _by_name(result)["dashboard"]
    assert code == 0 and check["ok"] is True
    assert "auth: proxy" in check["detail"] and "keinen Schlüssel" not in check["detail"]


def test_proxy_mode_from_config_with_a_local_key_says_it_is_not_sent(
    ready: Path, sak: Sak, health_server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_dashboard(ready, f"http://127.0.0.1:{health_server.server_address[1]}")
    config = ready / ".spec-agent/config.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "dashboard:\n", "dashboard:\n  auth: proxy\n", 1
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("SAK_DASHBOARD_AUTH", raising=False)
    write(ready, ".spec-agent/dashboard.key", "sak_" + "B" * 43 + "\n")
    _, result = sak("doctor", str(ready))
    check = _by_name(result)["dashboard"]
    assert check["ok"] is True and "nicht gesendet" in check["detail"]
    assert "B" * 43 not in json.dumps(result)


def test_key_mode_without_a_key_hints_at_proxy_mode_when_a_proxy_is_set(
    ready: Path, sak: Sak, health_server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_dashboard(ready, f"http://127.0.0.1:{health_server.server_address[1]}")
    monkeypatch.delenv("SAK_DASHBOARD_AUTH", raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")  # der Test-Server bleibt direkt erreichbar
    monkeypatch.setenv("HTTPS_PROXY", "http://nutzer:geheim@proxy.invalid:3128")
    _, result = sak("doctor", str(ready))
    check = _by_name(result)["dashboard"]
    assert check["ok"] is False and "SAK_DASHBOARD_AUTH=proxy" in check["detail"]
    assert "geheim" not in json.dumps(result) and "proxy.invalid" not in json.dumps(result)


def test_invalid_auth_env_fails_the_dashboard_check_without_the_value(
    ready: Path, sak: Sak, health_server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_dashboard(ready, f"http://127.0.0.1:{health_server.server_address[1]}")
    monkeypatch.setenv("SAK_DASHBOARD_AUTH", "sak_wertinfo")
    _, result = sak("doctor", str(ready))
    check = _by_name(result)["dashboard"]
    assert check["ok"] is False and "SAK_DASHBOARD_AUTH" in check["detail"]
    assert "wertinfo" not in json.dumps(result)
