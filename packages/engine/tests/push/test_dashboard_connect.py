"""``sak dashboard connect`` und ``status`` (Spec 009 US4, FR-005, A05).

Nur Wegwerf-Projekte in ``tmp_path`` und der lokale Test-Server; der Schlüssel ist ein frisch
erzeugter Testwert. Kernaussage: Er erscheint nie in stdout, stderr, Config, Cursor oder Log.
"""

from __future__ import annotations

import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import push_support
import pytest
from push_support import FakeDashboard

from spec_agent_kit import dashboard
from spec_agent_kit.cli import main
from spec_agent_kit.dashboard import ConnectError, set_dashboard_url
from spec_agent_kit.install.plan import render_config

REPO = Path(__file__).resolve().parents[4]
TEMPLATES = REPO / "packages" / "agent-blueprint" / "templates"
KEY_PATH = ".spec-agent/dashboard.key"
CONFIG_PATH = ".spec-agent/config.yml"

Run = Callable[..., tuple[int, dict[str, Any], str, str]]


def new_key() -> str:
    return "sak_" + secrets.token_urlsafe(32)


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch) -> str:
    value = new_key()
    assert dashboard.KEY_RE.fullmatch(value)
    monkeypatch.setattr(push_support, "KEY", value)  # der Test-Server erwartet genau diesen
    return value


@pytest.fixture
def dashboard_server(request: pytest.FixtureRequest) -> FakeDashboard:
    server: FakeDashboard = request.getfixturevalue("dashboard")
    return server


@pytest.fixture
def proj(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Initialisiertes Projekt: kommentierte Config aus der Vorlage, Agents, gitignore, Git."""
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(
        [
            *("git", "-c", "user.name=t", "-c", "user.email=t@example.org"),
            *("commit", "-q", "--allow-empty", "-m", "start"),
        ],
        cwd=root,
        check=True,
    )
    template = (TEMPLATES / "config" / "config.yml").read_text(encoding="utf-8")
    text = render_config(
        template,
        key="demo",
        name="Demo",
        base_branch="main",
        dashboard_url=None,
        ui=False,
        test_fast=[],
        test_full=[],
        lint=[],
    )
    (root / ".spec-agent").mkdir()
    (root / CONFIG_PATH).write_text(text, encoding="utf-8", newline="\n")
    shutil.copy(TEMPLATES / "spec-agent" / "gitignore", root / ".spec-agent" / ".gitignore")
    shutil.copytree(TEMPLATES / "claude" / "agents", root / ".claude" / "agents")
    monkeypatch.chdir(root)
    monkeypatch.delenv("SAK_DASHBOARD_TOKEN", raising=False)
    return root


@pytest.fixture
def run(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> Run:
    """Ruft ``sak`` auf: ``(exit, json, stdout, stderr)``; ``stdin`` ersetzt den Standardeingang."""

    def call(*argv: str, stdin: str | None = None) -> tuple[int, dict[str, Any], str, str]:
        capsys.readouterr()
        if stdin is not None:
            monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
        code = main(list(argv))
        captured = capsys.readouterr()
        out = captured.out.strip()
        return code, json.loads(out) if out else {}, captured.out, captured.err

    return call


def all_text(root: Path) -> str:
    """Alles, was unter ``.spec-agent`` außer der Schlüsseldatei selbst liegt (Config, State)."""
    parts = []
    for path in sorted((root / ".spec-agent").rglob("*")):
        if path.is_file() and path.name != "dashboard.key" and "engine" not in path.parts:
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


# --------------------------------------------------------------------------- Plan (Szenario 2)


def test_without_yes_only_the_plan_is_shown_and_nothing_is_written(
    proj: Path, run: Run, key: str
) -> None:
    before = snapshot(proj)
    code, out, _, stderr = run("dashboard", "connect", "--url", "https://x.example")
    assert code == 0 and out["mode"] == "plan" and out["ok"] is True
    assert out["config"]["action"] == "change"
    assert out["config"]["url_from"] is None and out["config"]["url_to"] == "https://x.example"
    assert any(line.startswith("+  url: https://x.example") for line in out["config"]["diff"])
    assert out["key_file"] == {"path": KEY_PATH, "action": "create", "format_checked": False}
    assert "Plan" in stderr
    assert snapshot(proj) == before


def test_plan_with_key_stdin_checks_the_format_but_still_writes_nothing(
    proj: Path, run: Run, key: str
) -> None:
    before = snapshot(proj)
    code, out, stdout, stderr = run(
        "dashboard", "connect", "--url", "https://x.example", "--key-stdin", stdin=key + "\n"
    )
    assert code == 0 and out["key_file"]["format_checked"] is True
    assert key not in stdout and key not in stderr
    assert snapshot(proj) == before


def test_plan_does_not_read_stdin_without_key_stdin(
    proj: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Forbidden(io.StringIO):
        def readline(self, *args: Any) -> str:
            raise AssertionError("stdin darf im Plan nicht gelesen werden")

    monkeypatch.setattr(sys, "stdin", Forbidden())
    assert main(["dashboard", "connect", "--url", "https://x.example"]) == 0


def test_plan_with_a_bad_key_is_rejected_without_naming_it(proj: Path, run: Run) -> None:
    code, out, stdout, stderr = run(
        "dashboard", "connect", "--url", "https://x.example", "--key-stdin", stdin="geheim\n"
    )
    assert code == 1 and out["ok"] is False
    assert "geheim" not in stdout + stderr


def test_plan_for_an_existing_key_file_says_replace_only_with_force(
    proj: Path, run: Run, key: str
) -> None:
    (proj / KEY_PATH).write_text("alt\n", encoding="utf-8")
    code, out, *_ = run("dashboard", "connect", "--url", "https://x.example")
    assert code == 1 and "--force" in out["errors"][0]["message"]
    code, out, *_ = run("dashboard", "connect", "--url", "https://x.example", "--force")
    assert code == 0 and out["key_file"]["action"] == "replace"


# --------------------------------------------------------------------------- Anwenden (Szenario 1)


def test_connect_writes_key_and_url_keeps_comments_and_pushes(
    proj: Path, run: Run, key: str, dashboard_server: FakeDashboard
) -> None:
    original = (proj / CONFIG_PATH).read_text(encoding="utf-8")
    code, out, _, _ = run(
        "dashboard", "connect", "--url", dashboard_server.url, "--key-stdin", "--yes", stdin=key
    )
    assert code == 0, json.dumps(out)
    assert out["mode"] == "applied" and out["ok"] is True
    assert out["key_file"] == {"path": KEY_PATH, "action": "created"}
    assert out["config_check"]["ok"] is True, out["config_check"]
    assert out["test_push"]["ok"] is True and out["test_push"]["status"] == "pushed"
    assert dashboard_server.boards and dashboard_server.requests

    assert (proj / KEY_PATH).read_text(encoding="utf-8").strip() == key
    new = (proj / CONFIG_PATH).read_text(encoding="utf-8")
    assert f"url: {dashboard_server.url}" in new
    # Genau eine Zeile ändert sich; alle Kommentare und der Rest bleiben.
    old_lines, new_lines = original.splitlines(), new.splitlines()
    assert len(old_lines) == len(new_lines)
    changed = [(a, b) for a, b in zip(old_lines, new_lines, strict=True) if a != b]
    assert len(changed) == 1 and changed[0][0].strip().startswith("url: null")
    assert [ln for ln in old_lines if ln.lstrip().startswith("#")] == [
        ln for ln in new_lines if ln.lstrip().startswith("#")
    ]


def test_the_key_never_appears_in_any_output_or_file(
    proj: Path, run: Run, key: str, dashboard_server: FakeDashboard
) -> None:
    code, _, stdout, stderr = run(
        "dashboard", "connect", "--url", dashboard_server.url, "--key-stdin", "--yes", stdin=key
    )
    assert code == 0
    assert key not in stdout and key not in stderr
    assert key not in all_text(proj)  # Config, Cursor, Log, Outbox
    code, _, stdout, stderr = run("dashboard", "status")
    assert code == 0 and key not in stdout and key not in stderr
    code, _, stdout, stderr = run("push")
    assert key not in stdout and key not in stderr
    # auch nicht im Verlauf der Anfragen an den Test-Server (nur im Header, nie im Body)
    assert key not in json.dumps(dashboard_server.requests)


def test_the_key_is_not_printed_on_failures_either(
    proj: Path, run: Run, key: str, dashboard_server: FakeDashboard
) -> None:
    dashboard_server.auth_status = 401
    code, _, stdout, stderr = run(
        "dashboard", "connect", "--url", dashboard_server.url, "--key-stdin", "--yes", stdin=key
    )
    assert code == 1
    assert key not in stdout and key not in stderr and key not in all_text(proj)


def test_failed_test_push_exits_1_but_keeps_the_connection(
    proj: Path, run: Run, key: str, dashboard_server: FakeDashboard
) -> None:
    dashboard_server.auth_status = 401
    code, out, *_ = run(
        "dashboard", "connect", "--url", dashboard_server.url, "--key-stdin", "--yes", stdin=key
    )
    assert code == 1 and out["ok"] is False
    assert out["config_check"]["ok"] is True
    assert out["test_push"]["status"] == "unauthorized"
    assert (proj / KEY_PATH).is_file() and dashboard_server.url in (proj / CONFIG_PATH).read_text(
        encoding="utf-8"
    )


def test_no_test_push_skips_the_push(proj: Path, run: Run, key: str) -> None:
    code, out, *_ = run(
        "dashboard",
        "connect",
        "--url",
        "https://x.example",
        "--key-stdin",
        "--yes",
        "--no-test-push",
        stdin=key,
    )
    assert code == 0 and out["test_push"]["status"] == "skipped"
    assert not (proj / ".spec-agent" / "state").exists()


@pytest.mark.skipif(os.name == "nt", reason="Dateirechte 600 gibt es nur unter POSIX")
def test_key_file_has_mode_600(proj: Path, run: Run, key: str) -> None:
    run(
        "dashboard", "connect", "--url", "https://x.example", "--key-stdin", "--yes",
        "--no-test-push", stdin=key,
    )  # fmt: skip
    assert (proj / KEY_PATH).stat().st_mode & 0o777 == 0o600


def test_key_comes_from_the_hidden_prompt_when_a_terminal_is_attached(
    proj: Path, run: Run, key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts: list[str] = []

    class Tty(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", Tty())
    monkeypatch.setattr(
        "spec_agent_kit.cli.getpass.getpass", lambda prompt="": prompts.append(prompt) or key
    )
    code = main(["dashboard", "connect", "--url", "https://x.example", "--yes", "--no-test-push"])
    assert code == 0 and prompts and "verdeckt" in prompts[0]
    assert (proj / KEY_PATH).read_text(encoding="utf-8").strip() == key


def test_yes_without_terminal_and_without_key_stdin_is_a_usage_error(proj: Path, run: Run) -> None:
    code, out, *_ = run("dashboard", "connect", "--url", "https://x.example", "--yes", stdin="")
    assert code == 2 and "--key-stdin" in out["error"]
    assert not (proj / KEY_PATH).exists()


def test_token_env_is_warned_about_and_does_not_hide_the_new_key(
    proj: Path,
    run: Run,
    key: str,
    dashboard_server: FakeDashboard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAK_DASHBOARD_TOKEN", "falscher-wert")
    code, out, *_ = run(
        "dashboard", "connect", "--url", dashboard_server.url, "--key-stdin", "--yes", stdin=key
    )
    assert code == 0 and out["test_push"]["status"] == "pushed"
    assert any("SAK_DASHBOARD_TOKEN" in w for w in out["warnings"])


# --------------------------------------------------------------------------- Ablehnungen


def test_existing_key_file_is_refused_without_force_and_kept(
    proj: Path, run: Run, key: str
) -> None:
    (proj / KEY_PATH).write_text("bestehender-wert\n", encoding="utf-8")
    before = snapshot(proj)
    code, out, *_ = run(
        "dashboard", "connect", "--url", "https://x.example", "--key-stdin", "--yes", stdin=key
    )
    assert code == 1 and "--force" in out["errors"][0]["message"]
    assert snapshot(proj) == before


def test_force_replaces_the_existing_key_file(proj: Path, run: Run, key: str) -> None:
    (proj / KEY_PATH).write_text("bestehender-wert\n", encoding="utf-8")
    code, out, *_ = run(
        "dashboard", "connect", "--url", "https://x.example", "--key-stdin", "--yes", "--force",
        "--no-test-push", stdin=key,
    )  # fmt: skip
    assert code == 0 and out["key_file"]["action"] == "replaced"
    assert (proj / KEY_PATH).read_text(encoding="utf-8").strip() == key


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "kein-schluessel",
        "sak_kurz",
        "sak_" + "a" * 42,
        "sak_" + "a" * 44,
        "sak_" + "a" * 42 + "!",
        "sak_" + "a" * 42 + " ",  # Leerzeichen mitten im Wert
        "key_" + "a" * 43,
        "SAK_" + "a" * 43,
        "sak_" + "ä" * 43,
    ],
)
def test_bad_key_formats_are_refused_without_writing_or_echoing(
    proj: Path, run: Run, bad: str
) -> None:
    before = snapshot(proj)
    code, out, stdout, stderr = run(
        "dashboard",
        "connect",
        "--url",
        "https://x.example",
        "--key-stdin",
        "--yes",
        stdin=bad + "\n",
    )
    assert code == 1 and out["ok"] is False and "Format" in out["errors"][0]["message"]
    if len(bad.strip()) > 8:
        assert bad.strip() not in stdout + stderr
    assert snapshot(proj) == before


@pytest.mark.parametrize(
    "url",
    ["ftp://x.example", "http://x.example", "x.example", "https://", "https://x y", "javascript:1"],
)
def test_bad_urls_are_refused(proj: Path, run: Run, key: str, url: str) -> None:
    before = snapshot(proj)
    code, out, *_ = run("dashboard", "connect", "--url", url, "--key-stdin", "--yes", stdin=key)
    assert code == 1 and out["errors"][0]["path"] == "--url"
    assert snapshot(proj) == before


def test_http_is_allowed_for_localhost(proj: Path, run: Run, key: str) -> None:
    code, out, *_ = run(
        "dashboard", "connect", "--url", "http://127.0.0.1:3000/", "--key-stdin", "--yes",
        "--no-test-push", stdin=key,
    )  # fmt: skip
    assert code == 0 and out["config"]["url_to"] == "http://127.0.0.1:3000"


def test_invalid_config_after_the_change_is_rolled_back(
    proj: Path, run: Run, key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = snapshot(proj)
    monkeypatch.setattr(
        dashboard,
        "_config_errors_of",
        lambda text: [{"path": "dashboard.url", "message": "kaputt"}],
    )
    code, out, *_ = run(
        "dashboard", "connect", "--url", "https://x.example", "--key-stdin", "--yes", stdin=key
    )
    assert code == 1 and "kaputt" in out["errors"][0]["message"]
    assert snapshot(proj) == before  # Config zurück, keine Schlüsseldatei


def test_unwritable_key_file_rolls_the_config_back(
    proj: Path, run: Run, key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = snapshot(proj)

    def boom(root: Path, value: str) -> None:
        raise PermissionError(13, "Zugriff verweigert")

    monkeypatch.setattr(dashboard, "write_key_file", boom)
    code, out, stdout, stderr = run(
        "dashboard", "connect", "--url", "https://x.example", "--key-stdin", "--yes", stdin=key
    )
    assert code == 1 and out["ok"] is False
    assert snapshot(proj) == before
    assert key not in stdout + stderr


def test_invalid_existing_config_is_refused_first(proj: Path, run: Run, key: str) -> None:
    path = proj / CONFIG_PATH
    path.write_text(path.read_text(encoding="utf-8") + "\nunbekannt: 1\n", encoding="utf-8")
    code, out, *_ = run("dashboard", "connect", "--url", "https://x.example", "--yes", stdin=key)
    assert code == 1 and "config check" in out["errors"][0]["message"]


def test_key_file_not_gitignored_is_refused(proj: Path, run: Run, key: str) -> None:
    (proj / ".spec-agent" / ".gitignore").write_text("state/\n", encoding="utf-8")
    code, out, *_ = run(
        "dashboard", "connect", "--url", "https://x.example", "--key-stdin", "--yes", stdin=key
    )
    assert code == 1 and "gitignore" in out["errors"][0]["message"]
    assert not (proj / KEY_PATH).exists()


def test_not_initialized_is_a_rejection(
    tmp_path: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "leer"
    empty.mkdir()
    monkeypatch.chdir(empty)
    monkeypatch.setattr("spec_agent_kit.cli.find_root", lambda start=None: None)
    code, out, *_ = run("dashboard", "connect", "--url", "https://x.example")
    assert code == 1 and "nicht initialisiert" in out["errors"][0]["message"]


def test_url_is_required(run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dashboard", "connect"]) == 2


# ------------------------------------------------------------------- Zeilenbasierte Änderung

BASE = (
    "# Kopfkommentar\nschema: sak.config/1\n\nother:\n  url: https://anderer.example\n\n"
    "dashboard:\n  # Ziel\n  url: null   # hier eintragen\n  token_env: SAK_DASHBOARD_TOKEN\n"
    "  share_commit_subjects: false\n\nplugins: []\n"
)


def test_edit_replaces_only_the_dashboard_url_and_keeps_the_inline_comment() -> None:
    edit = set_dashboard_url(BASE, "https://neu.example")
    assert edit.action == "change" and edit.old_url is None
    assert "  url: https://neu.example   # hier eintragen\n" in edit.text
    assert "other:\n  url: https://anderer.example\n" in edit.text
    assert edit.text.count("url:") == BASE.count("url:")
    assert [
        ln for ln in edit.diff if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))
    ] == [
        "-  url: null   # hier eintragen",
        "+  url: https://neu.example   # hier eintragen",
    ]


def test_edit_reports_the_old_value_and_unchanged() -> None:
    text = BASE.replace("url: null", 'url: "https://alt.example"')
    edit = set_dashboard_url(text, "https://alt.example")
    assert edit.old_url == "https://alt.example" and edit.action == "unchanged"
    assert set_dashboard_url(text, "https://neu.example").old_url == "https://alt.example"


def test_edit_inserts_a_missing_url_line_with_the_blocks_indent() -> None:
    text = "dashboard:\n    token_env: X_TOKEN\nplugins: []\n"
    edit = set_dashboard_url(text, "https://neu.example")
    assert edit.action == "insert"
    assert (
        edit.text
        == "dashboard:\n    url: https://neu.example\n    token_env: X_TOKEN\nplugins: []\n"
    )


def test_edit_appends_a_missing_block() -> None:
    edit = set_dashboard_url("schema: sak.config/1\n", "https://neu.example")
    assert edit.action == "append"
    assert edit.text == "schema: sak.config/1\n\ndashboard:\n  url: https://neu.example\n"
    no_newline = set_dashboard_url("schema: sak.config/1", "https://neu.example")
    assert no_newline.text.endswith("\ndashboard:\n  url: https://neu.example\n")


def test_edit_keeps_crlf_line_endings() -> None:
    crlf = BASE.replace("\n", "\r\n")
    edit = set_dashboard_url(crlf, "https://neu.example")
    assert edit.text.count("\r\n") == crlf.count("\r\n")
    assert edit.text.replace("\r\n", "").count("\n") == 0
    inserted = set_dashboard_url("dashboard:\r\n  token_env: X_T\r\n", "https://neu.example")
    assert inserted.text == "dashboard:\r\n  url: https://neu.example\r\n  token_env: X_T\r\n"


def test_edit_refuses_flow_style_blocks() -> None:
    with pytest.raises(ConnectError, match="Block"):
        set_dashboard_url("dashboard: {url: null}\n", "https://neu.example")


def test_edit_result_is_valid_yaml_with_the_new_value() -> None:
    import yaml

    loaded = yaml.safe_load(set_dashboard_url(BASE, "https://neu.example").text)
    assert loaded["dashboard"]["url"] == "https://neu.example"
    assert loaded["other"]["url"] == "https://anderer.example"


# --------------------------------------------------------------------------- status


def test_status_before_and_after_connect(
    proj: Path, run: Run, key: str, dashboard_server: FakeDashboard
) -> None:
    code, out, *_ = run("dashboard", "status")
    assert code == 0 and out["url"] is None and out["key"]["present"] is False
    assert out["key"]["source"] is None and out["push"] == "manual"
    assert out["cursor"] == {"offset": 0, "last_push_at": None, "last_error": None}

    run("dashboard", "connect", "--url", dashboard_server.url, "--key-stdin", "--yes", stdin=key)
    code, out, stdout, _ = run("dashboard", "status")
    assert out["url"] == dashboard_server.url and out["push"] == "auto"
    assert out["key"]["present"] is True and out["key"]["source"] == "file"
    assert out["cursor"]["last_push_at"] and out["cursor"]["last_error"] is None
    assert key not in stdout


def test_status_reports_the_last_push_error_and_an_env_key(
    proj: Path, run: Run, key: str, dashboard_server: FakeDashboard, monkeypatch: pytest.MonkeyPatch
) -> None:
    dashboard_server.auth_status = 401
    run("dashboard", "connect", "--url", dashboard_server.url, "--key-stdin", "--yes", stdin=key)
    code, out, *_ = run("dashboard", "status")
    assert out["cursor"]["last_error"]
    # Ein gesetzter letzter Fehler macht den Status nicht ok (Spec 011 US6).
    assert code == 1 and out["ok"] is False
    assert out["problems"] == [f"letzter Push-Fehler: {out['cursor']['last_error']}"]
    monkeypatch.setenv("SAK_DASHBOARD_TOKEN", "irgendwas")
    (proj / KEY_PATH).unlink()
    _, out, stdout, _ = run("dashboard", "status")
    assert out["key"]["present"] is True and out["key"]["source"] == "env"
    assert "irgendwas" not in stdout


def test_status_with_a_url_but_without_a_key_is_not_ok(
    proj: Path, run: Run, key: str, dashboard_server: FakeDashboard
) -> None:
    """Spec 011 B15: erreichbar genügt nicht, ein Schlüssel gehört dazu."""
    run("dashboard", "connect", "--url", dashboard_server.url, "--key-stdin", "--yes", stdin=key)
    (proj / KEY_PATH).unlink()
    outbox_cursor = proj / ".spec-agent" / "state" / "push-cursor.json"
    outbox_cursor.unlink(missing_ok=True)
    code, out, *_ = run("dashboard", "status")
    assert code == 1 and out["ok"] is False
    assert any("kein Schlüssel" in p for p in out["problems"])


def test_status_requires_an_initialized_project(
    tmp_path: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spec_agent_kit.cli.find_root", lambda start=None: tmp_path)
    code, out, *_ = run("dashboard", "status")
    assert code == 1 and out["ok"] is False


def test_no_project_values_are_hardcoded_in_the_module() -> None:
    text = Path(dashboard.__file__).read_text(encoding="utf-8").lower()
    for word in ("immoagent", "ai-forge", "prozessfit", "specboard"):
        assert word not in text
    assert re.search(r"sak_\[A-Za-z0-9_-\]\{43\}", Path(dashboard.__file__).read_text("utf-8"))


# --------------------------------------------------------------------------- Proxy-Modus (Spec 013)


def test_connect_auth_proxy_writes_url_and_mode_but_no_key(
    proj: Path, run: Run, dashboard_server: FakeDashboard
) -> None:
    dashboard_server.proxy_injects = True
    original = (proj / CONFIG_PATH).read_text(encoding="utf-8")
    code, out, _, _ = run(
        "dashboard", "connect", "--url", dashboard_server.url, "--auth", "proxy", "--yes"
    )
    assert code == 0, json.dumps(out)
    assert out["key_file"] == {"path": KEY_PATH, "action": "none"}
    assert out["config"]["auth_to"] == "proxy" and out["config_check"]["ok"] is True
    assert out["test_push"]["status"] == "pushed"
    assert dashboard_server.auth_headers and set(dashboard_server.auth_headers) == {None}
    assert not (proj / KEY_PATH).exists()
    new = (proj / CONFIG_PATH).read_text(encoding="utf-8")
    assert "auth: proxy" in new and f"url: {dashboard_server.url}" in new
    removed = [line for line in original.splitlines() if line not in new.splitlines()]
    assert len(removed) == 1 and removed[0].strip().startswith("url: null")


def test_connect_auth_proxy_plan_writes_nothing(
    proj: Path, run: Run, dashboard_server: FakeDashboard
) -> None:
    before = snapshot(proj)
    code, out, _, err = run(
        "dashboard", "connect", "--url", dashboard_server.url, "--auth", "proxy"
    )
    assert code == 0 and out["mode"] == "plan" and out["key_file"]["action"] == "none"
    assert out["config"]["auth_to"] == "proxy"
    assert any("auth: proxy" in line for line in out["config"]["diff"])
    assert "Proxy-Modus" in err
    assert snapshot(proj) == before


def test_connect_auth_proxy_needs_no_force_next_to_an_existing_key_file(
    proj: Path, run: Run, key: str, dashboard_server: FakeDashboard
) -> None:
    (proj / KEY_PATH).write_text(key + "\n", encoding="utf-8")
    argv = ["dashboard", "connect", "--url", dashboard_server.url, "--auth", "proxy"]
    code, out, stdout, _ = run(*argv, "--yes", "--no-test-push")
    assert code == 0 and out["key_file"]["action"] == "none"
    assert (proj / KEY_PATH).read_text(encoding="utf-8").strip() == key  # unangetastet
    assert key not in stdout


def test_connect_auth_proxy_refuses_a_key_on_stdin(
    proj: Path, run: Run, key: str, dashboard_server: FakeDashboard
) -> None:
    argv = ["dashboard", "connect", "--url", dashboard_server.url, "--auth", "proxy"]
    code, out, stdout, _ = run(*argv, "--key-stdin", "--yes", stdin=key)
    assert code == 1 and out["ok"] is False and key not in stdout
    assert not (proj / KEY_PATH).exists()


def test_connect_auth_key_replaces_an_existing_auth_line(
    proj: Path, run: Run, key: str, dashboard_server: FakeDashboard
) -> None:
    url = dashboard_server.url
    run("dashboard", "connect", "--url", url, "--auth", "proxy", "--yes", "--no-test-push")
    argv = ["dashboard", "connect", "--url", url, "--auth", "key", "--key-stdin", "--yes"]
    code, *_ = run(*argv, "--no-test-push", stdin=key)
    text = (proj / CONFIG_PATH).read_text(encoding="utf-8")
    assert code == 0 and "auth: key" in text and "auth: proxy" not in text
    assert text.count("auth:") == 1


def test_status_shows_the_auth_mode(proj: Path, run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    _, out, *_ = run("dashboard", "status")
    assert out["auth"] == "key" and out["auth_source"] == "config"
    monkeypatch.setenv("SAK_DASHBOARD_AUTH", "proxy")
    _, out, *_ = run("dashboard", "status")
    assert out["auth"] == "proxy" and out["auth_source"] == "env"
    assert set(out["proxy_env"]) == {"HTTPS_PROXY", "https_proxy"}


def test_status_in_proxy_mode_without_key_is_ok(
    proj: Path, run: Run, dashboard_server: FakeDashboard
) -> None:
    url = dashboard_server.url
    run("dashboard", "connect", "--url", url, "--auth", "proxy", "--yes", "--no-test-push")
    code, out, *_ = run("dashboard", "status")
    assert code == 0 and out["ok"] is True and out["auth"] == "proxy"
    assert out["key"]["present"] is False and "warnings" not in out


def test_status_in_proxy_mode_warns_about_a_local_key(
    proj: Path, run: Run, key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    (proj / KEY_PATH).write_text(key + "\n", encoding="utf-8")
    monkeypatch.setenv("SAK_DASHBOARD_AUTH", "proxy")
    _, out, stdout, _ = run("dashboard", "status")
    assert out["warnings"] and "nicht gesendet" in out["warnings"][0] and key not in stdout


def test_status_with_an_invalid_auth_env_is_an_error_without_the_value(
    proj: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAK_DASHBOARD_AUTH", "wertinfo")
    code, out, stdout, _ = run("dashboard", "status")
    assert code == 1 and out["ok"] is False and "wertinfo" not in stdout
