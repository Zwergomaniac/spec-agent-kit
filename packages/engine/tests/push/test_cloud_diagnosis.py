"""Diagnose typischer Cloud-Fehler (Spec 013 US2, FR-005, FR-006, SC-002).

Der Test-Proxy lauscht auf 127.0.0.1 und beantwortet CONNECT mit 403. Das Ziel ist ein Host unter
``example.org``; er wird nie aufgelöst, weil der Proxy die Verbindung ablehnt.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from push_support import RefusingProxy, write_config, write_events

from spec_agent_kit import dashboard
from spec_agent_kit.install import doctor as doctor_module
from spec_agent_kit.push import cloud
from spec_agent_kit.push.run import push

TARGET = "https://dashboard.example.org"
SECRET_PART = "geheimes-passwort"


@pytest.fixture
def proxy(monkeypatch: pytest.MonkeyPatch) -> Iterator[RefusingProxy]:
    server = RefusingProxy().start()
    for name in ("NO_PROXY", "no_proxy", "ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    # Zugangsdaten in der Proxy-URL: sie dürfen in keiner Ausgabe auftauchen.
    host = server.url.removeprefix("http://")
    monkeypatch.setenv("HTTPS_PROXY", f"http://nutzer:{SECRET_PART}@{host}")
    yield server
    server.stop()


@pytest.fixture
def cloud_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    write_config(root, TARGET)
    write_events(root, 1)
    return root


def test_push_explains_a_refused_tunnel(proxy: RefusingProxy, cloud_project: Path) -> None:
    code, result = push(cloud_project, env={"SAK_DASHBOARD_TOKEN": "schluessel"})
    assert code == 1 and result["status"] == "unreachable"
    message = result["error"]
    assert "Netzzugriff der Cloud-Umgebung erlaubt dashboard.example.org nicht" in message
    assert "Network access auf Custom" in message and "Network Secret" in message
    assert "umgeht die Allowlist" in message
    assert "HTTPS_PROXY gesetzt" in message
    assert proxy.connects == ["dashboard.example.org:443"]
    assert SECRET_PART not in json.dumps(result) and "nutzer" not in json.dumps(result)


def test_proxy_mode_gets_the_same_diagnosis(proxy: RefusingProxy, cloud_project: Path) -> None:
    code, result = push(cloud_project, env={"SAK_DASHBOARD_AUTH": "proxy"})
    assert code == 1 and "Netzzugriff der Cloud-Umgebung erlaubt" in result["error"]


def test_status_shows_the_diagnosis_auth_and_which_proxy_vars_are_set(
    proxy: RefusingProxy, cloud_project: Path
) -> None:
    push(cloud_project, env={"SAK_DASHBOARD_AUTH": "proxy"})
    code, out = dashboard.status(cloud_project, env={"SAK_DASHBOARD_AUTH": "proxy", **_proxy_env()})
    assert code == 1 and out["auth"] == "proxy" and out["auth_source"] == "env"
    assert any("Netzzugriff der Cloud-Umgebung erlaubt" in p for p in out["problems"])
    assert out["proxy_env"] == {"HTTPS_PROXY": True, "https_proxy": False}
    text = json.dumps(out)
    assert SECRET_PART not in text and "127.0.0.1" not in text.replace(TARGET, "")


def test_doctor_explains_a_refused_tunnel(proxy: RefusingProxy, cloud_project: Path) -> None:
    check = doctor_module._check_dashboard(cloud_project, TARGET)
    assert check["check"] == "dashboard" and check["ok"] is False and check["required"] is False
    assert "Netzzugriff der Cloud-Umgebung erlaubt dashboard.example.org nicht" in check["detail"]
    assert "Network Secret" in check["detail"] and "HTTPS_PROXY gesetzt" in check["detail"]
    assert SECRET_PART not in check["detail"]


def test_without_proxy_variables_the_error_is_not_called_a_cloud_problem() -> None:
    error = OSError("Tunnel connection failed: 403 Forbidden")
    assert cloud.explain(error, "dashboard.example.org", {}) is None
    assert cloud.explain(error, "dashboard.example.org", {"HTTPS_PROXY": "http://p:1"})


def test_other_errors_are_not_mistaken_for_a_proxy_rejection() -> None:
    env = {"HTTPS_PROXY": "http://p:1"}
    assert cloud.explain(OSError("Tunnel connection failed: 502 Bad Gateway"), "h", env) is None
    assert cloud.explain(ConnectionRefusedError("Verbindung abgelehnt"), "h", env) is None


def test_proxy_context_names_variables_never_values() -> None:
    env = {"HTTPS_PROXY": f"http://u:{SECRET_PART}@p:1", "https_proxy": ""}
    assert cloud.proxy_vars_set(env) == ["HTTPS_PROXY"]
    assert cloud.proxy_context(env) == " (HTTPS_PROXY gesetzt)"
    assert SECRET_PART not in cloud.proxy_context(env)
    assert cloud.proxy_context({}) == ""


def _proxy_env() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if k in cloud.PROXY_VARS}
