"""Push im Proxy-Modus und hinter einem Proxy (Spec 013 FR-001 bis FR-004, SC-001).

Nur lokale Test-Server auf 127.0.0.1. Der Test-Server zeichnet den ``Authorization``-Header jeder
Anfrage auf; ``proxy_injects`` spielt den Proxy mit Network Secret nach.
"""

from __future__ import annotations

import json
import shutil
import ssl
import subprocess
from pathlib import Path

import pytest
import yaml
from push_support import KEY, FakeDashboard, write_config, write_events

from spec_agent_kit.config import load_config, resolve_auth
from spec_agent_kit.push import client, cloud, outbox
from spec_agent_kit.push.run import push

PROXY = {"SAK_DASHBOARD_AUTH": "proxy"}
LOCAL_KEY = "lokaler-schluessel-nur-im-test"


def set_auth(root: Path, auth: str) -> None:
    path = root / ".spec-agent" / "config.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["dashboard"]["auth"] = auth
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def put_key_file(root: Path) -> None:
    (root / ".spec-agent" / "dashboard.key").write_text(LOCAL_KEY + "\n", encoding="utf-8")


def test_proxy_mode_sends_no_authorization_header(project: Path, dashboard: FakeDashboard) -> None:
    dashboard.proxy_injects = True
    write_events(project, 2)
    code, result = push(project, env=PROXY)
    assert code == 0 and result["status"] == "pushed" and result["accepted"] == 2
    assert dashboard.auth_headers == [None]
    assert "warnings" not in result


def test_proxy_mode_from_config_without_env(project: Path, dashboard: FakeDashboard) -> None:
    dashboard.proxy_injects = True
    set_auth(project, "proxy")
    write_events(project, 1)
    code, result = push(project, env={})
    assert code == 0 and result["status"] == "pushed"
    assert dashboard.auth_headers == [None]


def test_env_overrides_the_config_in_both_directions(
    project: Path, dashboard: FakeDashboard
) -> None:
    set_auth(project, "proxy")
    write_events(project, 1)
    code, result = push(project, env={"SAK_DASHBOARD_AUTH": "key", "SAK_DASHBOARD_TOKEN": KEY})
    assert code == 0 and result["status"] == "pushed"
    assert dashboard.auth_headers == [f"Bearer {KEY}"]


def test_a_local_key_is_not_sent_in_proxy_mode_and_is_warned_about(
    project: Path, dashboard: FakeDashboard
) -> None:
    dashboard.proxy_injects = True
    put_key_file(project)
    write_events(project, 1)
    code, result = push(project, env={**PROXY, "SAK_DASHBOARD_TOKEN": LOCAL_KEY})
    assert code == 0 and result["status"] == "pushed"
    assert dashboard.auth_headers == [None]
    assert result["warnings"] and "nicht gesendet" in result["warnings"][0]
    assert LOCAL_KEY not in json.dumps(result)


def test_a_local_key_file_is_not_sent_either(project: Path, dashboard: FakeDashboard) -> None:
    dashboard.proxy_injects = True
    put_key_file(project)
    write_events(project, 1)
    code, result = push(project, env=PROXY)
    assert code == 0 and dashboard.auth_headers == [None]
    assert "warnings" in result and LOCAL_KEY not in json.dumps(result)


def test_401_in_proxy_mode_names_the_network_secret(
    project: Path, dashboard: FakeDashboard
) -> None:
    write_events(project, 1)  # kein proxy_injects: der Server sieht keinen Bearer und sagt 401
    code, result = push(project, env=PROXY)
    assert code == 1 and result["status"] == "unauthorized"
    assert (
        "Kein Network Secret für 127.0.0.1 in der Cloud-Umgebung hinterlegt (Typ Bearer)"
        in result["error"]
    )
    assert dashboard.auth_headers == [None]
    assert outbox.read_cursor(project).offset == 0  # der Cursor rückt nie vor


def test_401_in_key_mode_keeps_the_old_message(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 1)
    code, result = push(project, env={"SAK_DASHBOARD_TOKEN": "falsch"})
    assert code == 1 and result["status"] == "unauthorized"
    assert "Network Secret" not in result["error"]


def test_key_mode_without_key_keeps_the_rejection(project: Path) -> None:
    code, result = push(project, env={})
    assert code == 1 and result["status"] == "no_key"
    assert "proxy" not in result["error"].lower()


def test_key_mode_without_key_hints_at_proxy_mode_behind_a_proxy(project: Path) -> None:
    code, result = push(project, env={"HTTPS_PROXY": "http://user:pass@proxy.invalid:3128"})
    assert code == 1 and result["status"] == "no_key"
    assert "SAK_DASHBOARD_AUTH=proxy" in result["error"] and "Network Secret" in result["error"]
    assert "user:pass" not in json.dumps(result) and "proxy.invalid" not in json.dumps(result)


@pytest.mark.parametrize("value", ["token", "PROXY", "sak_geheimer_wert"])
def test_invalid_auth_env_is_an_error_without_the_value(project: Path, value: str) -> None:
    code, result = push(project, env={"SAK_DASHBOARD_AUTH": value})
    assert code == 1 and result["status"] == "invalid_auth"
    assert "key" in result["error"] and "proxy" in result["error"]
    assert value not in json.dumps(result)


def test_protection_rules_stay_in_proxy_mode(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 1)
    dashboard.redirect_to = "http://127.0.0.1:9/elsewhere"
    code, result = push(project, env=PROXY)
    assert code == 1 and result["status"] == "rejected"
    assert dashboard.auth_headers == [None]  # genau eine Anfrage, keine Weiterleitung
    write_config(project, "http://dashboard.example.org")
    code, result = push(project, env=PROXY)
    assert code == 1 and result["status"] == "insecure_url"


def test_post_ingest_without_key_has_no_authorization_header(dashboard: FakeDashboard) -> None:
    dashboard.proxy_injects = True
    payload = {
        "schema": "sak.ingest/1",
        "project": "demo",
        "sent_at": "2026-10-22T09:00:00Z",
        "events": [],
    }
    client.post_ingest(client.check_url(dashboard.url), None, payload)
    assert dashboard.auth_headers == [None]


def test_resolve_auth_reads_the_effective_config(project: Path) -> None:
    set_auth(project, "proxy")
    assert resolve_auth(load_config(project), {}) == ("proxy", "config")


# ---------------------------------------------------------------------------
# FR-004: CA-Bundle aus der Umgebung
# ---------------------------------------------------------------------------


def test_ssl_context_only_with_an_existing_bundle(tmp_path: Path) -> None:
    assert cloud.ssl_context({}) is None
    assert cloud.ssl_context({"SSL_CERT_FILE": str(tmp_path / "fehlt.pem")}) is None
    junk = tmp_path / "kaputt.pem"
    junk.write_text("kein zertifikat", encoding="utf-8")
    assert cloud.ssl_context({"REQUESTS_CA_BUNDLE": str(junk)}) is None


@pytest.fixture
def selfsigned(tmp_path: Path) -> tuple[Path, Path]:
    if shutil.which("openssl") is None:
        pytest.skip("openssl nicht verfügbar")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
            "-keyout", str(key), "-out", str(cert), "-subj", "/CN=localhost",
            "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost",
        ],
        check=True,
        capture_output=True,
    )  # fmt: skip
    return cert, key


@pytest.mark.parametrize("variable", ["SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"])
def test_ca_bundle_from_the_environment_is_used(
    selfsigned: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
) -> None:
    server = FakeDashboard()
    server.enable_tls(*selfsigned)
    server.start()
    try:
        root = tmp_path / "proj"
        root.mkdir()
        write_config(root, server.tls_url)
        write_events(root, 1)
        env = {"SAK_DASHBOARD_TOKEN": KEY}
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

        code, result = push(root, env=env)  # ohne Bundle: Zertifikat unbekannt
        assert code == 1 and result["status"] == "unreachable"
        assert "SSL_CERT_FILE" in result["error"] and "REQUESTS_CA_BUNDLE" in result["error"]

        monkeypatch.setenv(variable, str(selfsigned[0]))
        code, result = push(root, env=env)  # mit Bundle: gleiche Verbindung gelingt
        assert code == 0 and result["status"] == "pushed", result
    finally:
        server.stop()


def test_default_tls_behavior_is_unchanged_without_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    assert cloud.ssl_context() is None
    assert isinstance(ssl.create_default_context(), ssl.SSLContext)
