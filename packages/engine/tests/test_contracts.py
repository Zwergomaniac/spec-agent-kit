"""Verträge v1: Beispiele, Byte-Gleichheit der Schema-Kopie, ULID, Limits, Labels."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from spec_agent_kit import contracts
from spec_agent_kit.cli import main

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_SOURCE = REPO_ROOT / "packages" / "contracts" / "schema"
EXAMPLES = REPO_ROOT / "packages" / "contracts" / "examples"

VALIDATORS: dict[str, Callable[[Any], list[str]]] = {
    "event": contracts.validate_event,
    "board": contracts.validate_board,
    "ingest": contracts.validate_ingest,
    "config": contracts.validate_config,
    "lock": contracts.validate_lock,
}


def _example_files() -> list[tuple[str, Path]]:
    files = []
    for kind in ("valid", "invalid"):
        files.extend((kind, p) for p in sorted((EXAMPLES / kind).glob("*.json")))
    return files


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_event() -> dict[str, Any]:
    event: dict[str, Any] = _load(EXAMPLES / "valid" / "event-round-started.json")
    return event


@pytest.mark.parametrize(
    ("kind", "path"), _example_files(), ids=lambda v: v.name if isinstance(v, Path) else v
)
def test_examples_are_judged_like_typescript(kind: str, path: Path) -> None:
    validator = VALIDATORS[path.name.split("-")[0]]
    errors = validator(_load(path))
    if kind == "valid":
        assert errors == []
    else:
        assert len(errors) == 1


def test_every_event_type_has_a_valid_example() -> None:
    types = {_load(p)["type"] for p in (EXAMPLES / "valid").glob("event-*.json")}
    vocab = contracts.vocabulary()
    assert types == set(vocab["event_type"]) | set(vocab["diag_event_type"])


def _files(base: Path) -> dict[str, bytes]:
    return {
        p.relative_to(base).as_posix(): p.read_bytes()
        for p in sorted(base.rglob("*"))
        if p.is_file()
    }


def test_schema_copy_is_byte_identical_to_contracts_source() -> None:
    copy_files = {k: v for k, v in _files(contracts.SCHEMA_DIR).items() if not k.endswith(".pyc")}
    source_files = _files(SCHEMA_SOURCE)
    assert set(copy_files) == set(source_files)
    for name, data in source_files.items():
        assert copy_files[name] == data, f"{name} weicht von packages/contracts/schema ab"


def test_vocabulary_and_labels_are_complete() -> None:
    vocab = contracts.vocabulary()
    labels = json.loads((contracts.SCHEMA_DIR / "labels" / "de.json").read_text(encoding="utf-8"))
    assert set(labels) == set(vocab)
    for level, values in vocab.items():
        assert set(labels[level]) == set(values), level
        for value in values:
            assert contracts.label(level, value).strip()


def test_label_examples_and_unknown_values() -> None:
    assert contracts.label("run_state", "escalated") == "Eskaliert"
    assert contracts.label("verdict", "changes_requested", "de") == "Änderung"
    assert contracts.label("stage", "gibt_es_nicht") == "gibt_es_nicht"


def test_enums_in_schemas_match_vocabulary() -> None:
    vocab = contracts.vocabulary()

    def walk(node: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(node, dict):
            if "enum" in node:
                found.append(node)
            for value in node.values():
                found.extend(walk(value))
        elif isinstance(node, list):
            for value in node:
                found.extend(walk(value))
        return found

    seen = 0
    for name in ("common", "event", "board", "ingest", "config", "lock"):
        for node in walk(contracts.load_schema(name)):
            seen += 1
            values = vocab[node["x-vocab"]]
            if node.get("x-vocab-subset"):
                assert set(node["enum"]) <= set(values)
            else:
                assert sorted(node["enum"]) == sorted(values)
    assert seen > 10


def test_ulid_format_and_monotonicity() -> None:
    pattern = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
    ids = [contracts.new_ulid() for _ in range(2000)]
    assert all(pattern.match(i) for i in ids)
    assert len(set(ids)) == len(ids)
    assert ids == sorted(ids)
    assert contracts.validate_event({**_valid_event(), "event_id": ids[0]}) == []


def test_ulid_encodes_timestamp_in_first_ten_characters() -> None:
    first = contracts.new_ulid(1_900_000_000_000)
    assert first[:10] == contracts.new_ulid(1_900_000_000_000)[:10]
    assert contracts.new_ulid(1_900_000_000_000 + 10_000)[:10] > first[:10]


def test_now_rfc3339_is_valid_timestamp() -> None:
    stamp = contracts.now_rfc3339()
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", stamp)
    assert contracts.validate_event({**_valid_event(), "ts": stamp}) == []


def test_limits_match_spec_and_schemas() -> None:
    limits = contracts.LIMITS
    assert limits["EVENT_MAX_BYTES"] == 8 * 1024
    assert limits["BOARD_MAX_BYTES"] == 512 * 1024
    assert limits["INGEST_MAX_BYTES"] == 2 * 1024 * 1024
    assert limits["INGEST_MAX_EVENTS"] == 500
    assert contracts.load_schema("board")["properties"]["runs"]["maxItems"] == limits["RUNS_MAX"]
    assert (
        contracts.load_schema("board")["properties"]["ticker"]["maxItems"] == limits["TICKER_MAX"]
    )
    assert contracts.load_schema("board")["properties"]["notes"]["maxItems"] == limits["NOTES_MAX"]
    request = contracts.load_schema("ingest")["$defs"]["request"]
    assert request["properties"]["events"]["maxItems"] == limits["INGEST_MAX_EVENTS"]
    assert (
        contracts.load_schema("common")["$defs"]["reason"]["maxLength"]
        == limits["REASON_MAX_CHARS"]
    )


def test_event_larger_than_8_kb_is_rejected_by_size() -> None:
    event = _valid_event()
    event["origin"] = {"machine": "m"}
    event["data"] = {"round": 1}
    assert contracts.validate_event(event) == []
    big = copy.deepcopy(_load(EXAMPLES / "valid" / "event-diag-hook.json"))
    big["data"]["keys"] = ["k" * 100] * 50  # 50 * 100 Zeichen = 5 KB, noch erlaubt
    assert contracts.validate_event(big) == []
    big["event_id"] = contracts.new_ulid()
    big["data"]["keys"] = ["ä" * 100] * 50  # 2 Bytes je Zeichen: > 8 KB
    errors = contracts.validate_event(big)
    assert len(errors) == 1
    assert "Limit" in errors[0]


def test_trailing_newline_does_not_pass_patterns() -> None:
    event = _valid_event()
    assert contracts.validate_event({**event, "project": "immo-agent\n"}) != []
    assert contracts.validate_event({**event, "event_id": event["event_id"] + "\n"}) != []


def test_invalid_calendar_date_is_rejected() -> None:
    assert contracts.validate_event({**_valid_event(), "ts": "2026-13-45T10:00:00Z"}) != []


def test_unknown_schema_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unbekanntes Schema"):
        contracts.load_schema("nope")


def test_cli_version_prints_json_in_utf8(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0
    assert json.loads(capsys.readouterr().out) == {"version": "0.1.1"}


def test_cli_usage_error_returns_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["gibt-es-nicht"]) == 2
    capsys.readouterr()
