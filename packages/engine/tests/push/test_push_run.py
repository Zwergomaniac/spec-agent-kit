"""Push gegen den lokalen Test-Server (Spec 006 US3, SC-002, T009 bis T013)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from push_support import KEY, FakeDashboard, make_event, write_config, write_events

from spec_agent_kit import contracts
from spec_agent_kit.board.build import build_board
from spec_agent_kit.config import load_config
from spec_agent_kit.push import client, outbox
from spec_agent_kit.push.run import acquire_lock, lock_path, push

ENV = {"SAK_DASHBOARD_TOKEN": KEY}


def do_push(root: Path) -> tuple[int, dict[str, object]]:
    return push(root, env=ENV)


def events_size(root: Path) -> int:
    return (root / ".spec-agent" / "state" / "events.jsonl").stat().st_size


def test_success_sends_events_and_a_valid_board(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 3)
    code, result = do_push(project)
    assert code == 0 and result["status"] == "pushed"
    assert result["accepted"] == 3 and result["board_sent"] is True and result["pending"] is False
    (request,) = dashboard.requests
    assert request["schema"] == "sak.ingest/1" and request["project"] == "demo"
    assert contracts.validate_ingest(request) == []
    assert len(request["events"]) == 3 and request["board"]["schema"] == "sak.board/1"
    assert outbox.read_cursor(project).offset == events_size(project)
    assert not (project / ".spec-agent" / "state" / "push.lock").exists()


def test_second_push_without_news_sends_nothing(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 2)
    do_push(project)
    code, result = do_push(project)
    assert code == 0 and result["status"] == "up_to_date"
    assert len(dashboard.requests) == 1  # weder Events noch ein unverändertes Board


def test_unreachable_keeps_50_events_then_delivers_all(
    project: Path, dashboard: FakeDashboard
) -> None:
    write_events(project, 50)
    write_config(project, "http://127.0.0.1:1")  # nichts hört dort zu
    code, result = do_push(project)
    assert code == 1 and result["status"] == "unreachable"
    assert outbox.read_cursor(project).offset == 0
    assert "nicht erreichbar" in (outbox.read_cursor(project).last_error or "")
    write_config(project, dashboard.url)
    code, result = do_push(project)
    assert code == 0 and result["accepted"] == 50
    assert len(dashboard.seen) == 50
    cursor = outbox.read_cursor(project)
    assert cursor.offset == events_size(project) and cursor.last_error is None


def test_timeout_is_a_network_error(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    with socket.socket() as silent:  # nimmt Verbindungen an, antwortet aber nie
        silent.bind(("127.0.0.1", 0))
        silent.listen(1)
        write_config(project, f"http://127.0.0.1:{silent.getsockname()[1]}")
        write_events(project, 1)
        monkeypatch.setattr(client, "TIMEOUT_S", 0.3)
        started = time.monotonic()
        code, result = do_push(project)
        assert code == 1 and result["status"] == "unreachable"
        assert time.monotonic() - started < 3


def test_per_event_rejections_advance_the_cursor_and_are_logged(
    project: Path, dashboard: FakeDashboard
) -> None:
    events = write_events(project, 4)
    bad = {events[1]["event_id"], events[3]["event_id"]}
    dashboard.reject = lambda e: (
        "ungültiges event: data.round: zu klein" if e["event_id"] in bad else None
    )
    code, result = do_push(project)
    assert code == 0 and result["accepted"] == 2 and result["rejected"] == 2
    assert outbox.read_cursor(project).offset == events_size(project)
    lines = (project / ".spec-agent/state/push-rejected.jsonl").read_text("utf-8").splitlines()
    logged = [json.loads(line) for line in lines]
    assert {r["event_id"] for r in logged} == bad
    assert all("zu klein" in r["error"] and "data" not in r for r in logged)
    # Kein erneutes Senden: der nächste Push findet nichts Neues.
    assert do_push(project)[1]["sent"] == 0  # höchstens das Board (neuer Hinweis) geht raus
    assert len(dashboard.seen) == 2
    # Das Board nennt die Ablehnung als Hinweis.
    doc = build_board(project, load_config(project))
    assert any("2 Event(s) vom Dashboard abgelehnt" in n for n in doc["notes"])


def test_401_keeps_the_cursor_and_says_why(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 2)
    dashboard.auth_status = 401
    code, result = do_push(project)
    assert code == 1 and result["status"] == "unauthorized" and "401" in str(result["error"])
    assert outbox.read_cursor(project).offset == 0
    assert KEY not in json.dumps(result)


def test_wrong_key_is_unauthorized(project: Path) -> None:
    write_events(project, 1)
    code, result = push(project, env={"SAK_DASHBOARD_TOKEN": "falsch"})
    assert code == 1 and result["status"] == "unauthorized"


def test_whole_request_version_error_keeps_the_cursor(
    project: Path, dashboard: FakeDashboard
) -> None:
    write_events(project, 2)
    dashboard.raw_status = (400, {"error": "unsupported schema version (erwartet sak.ingest/2)"})
    code, result = do_push(project)
    assert code == 1 and result["status"] == "version_mismatch"
    assert outbox.read_cursor(project).offset == 0


@pytest.mark.parametrize(
    "message", ["unsupported schema version (erwartet sak.event/2)", "unknown event type"]
)
def test_per_event_version_errors_keep_the_cursor(
    project: Path, dashboard: FakeDashboard, message: str
) -> None:
    write_events(project, 2)
    dashboard.reject = lambda e: message
    code, result = do_push(project)
    assert code == 1 and result["status"] == "version_mismatch"
    assert outbox.read_cursor(project).offset == 0
    assert not (project / ".spec-agent/state/push-rejected.jsonl").exists()


def test_other_whole_request_400_keeps_the_cursor(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 2)
    dashboard.raw_status = (400, {"error": "invalid_request", "detail": "events: Required"})
    code, result = do_push(project)
    assert (
        code == 1 and result["status"] == "rejected" and "invalid_request" in str(result["error"])
    )
    assert outbox.read_cursor(project).offset == 0


def test_board_rejection_does_not_block_events(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 2)
    dashboard.board_error = "board: unsupported schema version (erwartet sak.board/2)"
    code, result = do_push(project)
    assert code == 0 and result["accepted"] == 2 and "board_error" in result
    assert outbox.read_cursor(project).offset == events_size(project)
    assert outbox.read_cursor(project).board_hash is None  # wird erneut versucht


def test_redirects_are_not_followed(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 1)
    dashboard.redirect_to = "http://127.0.0.1:1/steal"
    code, result = do_push(project)
    assert code == 1 and result["status"] == "rejected" and "Weiterleitung" in str(result["error"])


def test_cursor_reset_when_the_file_was_replaced(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 5)
    do_push(project)
    first_seen = set(dashboard.seen)
    # Ersetzt durch eine kleinere Datei mit anderen Events.
    write_events(project, 2, append=False)
    code, result = do_push(project)
    assert code == 0 and result["accepted"] == 2
    assert any("zurückgesetzt" in n for n in result["notes"])  # type: ignore[attr-defined]
    assert len(dashboard.seen) == len(first_seen) + 2
    assert outbox.read_cursor(project).offset == events_size(project)


def test_cursor_reset_when_a_larger_replacement_has_another_identity(
    project: Path, dashboard: FakeDashboard
) -> None:
    write_events(project, 2)
    do_push(project)
    write_events(project, 6, append=False)  # größer als zuvor, andere erste Zeile
    code, result = do_push(project)
    assert code == 0 and result["accepted"] == 6


def test_reset_resends_old_events_and_the_dashboard_deduplicates(
    project: Path, dashboard: FakeDashboard
) -> None:
    write_events(project, 3)
    do_push(project)
    outbox.write_cursor(project, outbox.Cursor(offset=0))  # Cursor verloren
    code, result = do_push(project)
    assert code == 0 and result["accepted"] == 0 and result["duplicates"] == 3


def test_batches_of_500_and_three_batches_per_call(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 1200)
    code, result = do_push(project)
    assert code == 0 and result["sent"] == 1200 and result["pending"] is False
    assert [len(r["events"]) for r in dashboard.requests] == [500, 500, 200]
    assert "board" not in dashboard.requests[0] and "board" in dashboard.requests[-1]
    write_events(project, 1700)
    dashboard.requests.clear()
    code, result = do_push(project)
    assert result["sent"] == 1500 and result["pending"] is True
    assert len(dashboard.requests) == 3 and all("board" not in r for r in dashboard.requests)
    code, result = do_push(project)
    assert result["sent"] == 200 and result["pending"] is False
    assert len(dashboard.seen) == 2900


def test_broken_lines_are_skipped_counted_and_never_sent_twice(
    project: Path, dashboard: FakeDashboard
) -> None:
    write_events(project, 2)
    path = project / ".spec-agent" / "state" / "events.jsonl"
    invalid = make_event()
    invalid["type"] = "run.unbekannt"
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{abgeschnitten\n\n[1]\n" + json.dumps(invalid) + "\n")
    write_events(project, 1)
    code, result = do_push(project)
    assert code == 0 and result["accepted"] == 3 and result["skipped_lines"] == 3
    do_push(project)
    assert len(dashboard.seen) == 3 and outbox.read_cursor(project).skipped == 3
    doc = build_board(project, load_config(project))
    assert any("3 defekte Zeile(n)" in n for n in doc["notes"])


def test_half_written_last_line_waits(project: Path, dashboard: FakeDashboard) -> None:
    (event,) = write_events(project, 1)
    path = project / ".spec-agent" / "state" / "events.jsonl"
    text = json.dumps(make_event(), separators=(",", ":"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text[:40])  # ohne Zeilenumbruch
    code, result = do_push(project)
    assert code == 0 and result["accepted"] == 1
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text[40:] + "\n")
    code, result = do_push(project)
    assert result["accepted"] == 1 and len(dashboard.seen) == 2
    assert event["event_id"] in dashboard.seen


def test_only_validated_events_and_board_are_sent(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 2)
    do_push(project)
    for request in dashboard.requests:
        assert contracts.validate_ingest(request) == []
        for event in request["events"]:
            assert contracts.validate_event(event) == []
        assert contracts.validate_board(request["board"]) == []
        assert all("text" not in t for t in request["board"]["ticker"])  # opt-in


# --- Sperre -----------------------------------------------------------------------------------


def test_parallel_push_is_prevented_by_the_lock(project: Path, dashboard: FakeDashboard) -> None:
    write_events(project, 2)
    assert acquire_lock(project)
    code, result = do_push(project)
    assert code == 0 and result["status"] == "locked"
    assert dashboard.requests == [] and outbox.read_cursor(project).offset == 0
    assert not acquire_lock(project)  # zweiter gleichzeitiger Zugriff scheitert


def test_expired_lock_is_taken_over_after_60_seconds(
    project: Path, dashboard: FakeDashboard
) -> None:
    write_events(project, 2)
    assert acquire_lock(project)
    old = time.time() - 61
    os.utime(lock_path(project), (old, old))
    code, result = do_push(project)
    assert code == 0 and result["status"] == "pushed"
    assert not lock_path(project).exists()


def test_lock_is_released_after_a_failure(project: Path) -> None:
    write_events(project, 1)
    write_config(project, "http://127.0.0.1:1")
    do_push(project)
    assert not lock_path(project).exists()


# --- Randfälle --------------------------------------------------------------------------------


@pytest.mark.parametrize(("url", "mode"), [(None, "manual"), ("http://127.0.0.1:1", "off")])
def test_disabled_is_exit_0(project: Path, url: str | None, mode: str) -> None:
    write_config(project, url, mode)
    code, result = do_push(project)
    assert code == 0 and result["status"] == "disabled" and "deaktiviert" in str(result["message"])


def test_missing_key_is_exit_1_with_a_hint(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, result = push(project, env={})
    assert code == 1 and result["status"] == "no_key"
    assert "SAK_DASHBOARD_TOKEN" in str(result["error"]) and "dashboard.key" in str(result["error"])
    (project / ".spec-agent" / "dashboard.key").write_text(KEY + "\n", encoding="utf-8")
    write_events(project, 1)
    code, result = push(project, env={})
    assert code == 0 and result["accepted"] == 1  # Schlüsseldatei genügt


@pytest.mark.parametrize(
    "url",
    [
        "http://dashboard.example.com",
        "ftp://x",
        "https://user:pw@example.com",
        "kein-url",
        "http://127.0.0.1.evil.com",
    ],
)
def test_https_is_mandatory_except_for_loopback(project: Path, url: str) -> None:
    write_config(project, url)
    write_events(project, 1)
    code, result = do_push(project)
    # Das Config-Schema fängt ftp:// und Nicht-URLs schon vorher ab (invalid_config).
    assert code == 1 and result["status"] in {"insecure_url", "invalid_config"}
    assert outbox.read_cursor(project).offset == 0


def test_check_url_accepts_https_and_local_http() -> None:
    assert client.check_url("https://dash.example.com") == "https://dash.example.com/api/ingest"
    assert (
        client.check_url("https://dash.example.com/sub/")
        == "https://dash.example.com/sub/api/ingest"
    )
    assert client.check_url("http://localhost:3000") == "http://localhost:3000/api/ingest"
    assert client.check_url("http://127.0.0.1:3000/") == "http://127.0.0.1:3000/api/ingest"


@pytest.mark.parametrize("url", ["ftp://x", "kein-url", "http://example.com"])
def test_check_url_refuses_unsafe_urls(url: str) -> None:
    with pytest.raises(client.InsecureUrlError):
        client.check_url(url)


def test_not_initialized_is_exit_1(tmp_path: Path) -> None:
    code, result = push(tmp_path, env=ENV)
    assert code == 1 and result["status"] == "not_initialized"


def test_cli_quiet_prints_nothing_and_manual_prints_json(
    project: Path,
    dashboard: FakeDashboard,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from spec_agent_kit.cli import main

    monkeypatch.setenv("SAK_DASHBOARD_TOKEN", KEY)
    write_events(project, 1)
    assert main(["push", "--quiet"]) == 0
    assert capsys.readouterr().out == ""
    write_events(project, 1)
    assert main(["push"]) == 0
    assert json.loads(capsys.readouterr().out)["accepted"] == 1
