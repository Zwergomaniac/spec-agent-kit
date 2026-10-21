"""``sak migrate legacy-pipeline`` (Spec 010 US4, FR-005, A05)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from spec_agent_kit import contracts
from spec_agent_kit.board.build import build_board
from spec_agent_kit.cli import main
from spec_agent_kit.config import load_config
from spec_agent_kit.migrate import MigrateError
from spec_agent_kit.migrate.legacy_pipeline import ZERO_SHA, apply_plan, build_plan, map_event
from spec_agent_kit.pipeline import runs as run_store
from spec_agent_kit.pipeline.events import events_path

SHA = "c8dacb795d4ec7a537dcbc03673ddfe7c65e4f9d"


def line(
    kind: str, ts: str, spec: str | None = "066-webapp-tooltips", **extra: Any
) -> dict[str, Any]:
    item: dict[str, Any] = {"ts": ts, "kind": kind}
    if spec is not None:
        item["spec"] = spec
    item.update(extra)
    return item


def legacy_events() -> list[dict[str, Any]]:
    """Lauf 066 (zwei Runden, gemergt), geparkter Lauf 084, von Hand angelegter Lauf 092."""
    return [
        line("hook_debug", "2026-10-19T16:45:53+02:00", None, phase="start", keys=["agent_id"]),
        line(
            "station_started",
            "2026-10-19T16:45:53+02:00",
            "092-dev-dashboard",
            round=1,
            station="ui",
            agent="pipeline-ui-reviewer",
            model="sonnet",
            effort="medium",
        ),
        line(
            "station_finished",
            "2026-10-19T16:47:24+02:00",
            "092-dev-dashboard",
            round=1,
            station="ui",
            agent="pipeline-ui-reviewer",
            duration_s=91,
        ),
        line(
            "verdict",
            "2026-10-19T16:49:17+02:00",
            "092-dev-dashboard",
            round=1,
            station="code",
            verdict="Änderung",
            muss_count=1,
        ),
        line(
            "aborted",
            "2026-10-19T18:35:56+02:00",
            "092-dev-dashboard",
            round=1,
            reason="Gegenprüfung abgeschlossen, Lauf von Hand angelegt",
        ),
        line("run_started", "2026-10-19T18:38:04+02:00", round=1),
        line(
            "station_started",
            "2026-10-19T18:38:14+02:00",
            round=1,
            station="builder",
            agent="pipeline-builder",
            model="sonnet",
            effort="medium",
        ),
        line(
            "station_finished",
            "2026-10-19T20:20:01+02:00",
            round=1,
            station="builder",
            agent="pipeline-builder",
            duration_s=64,
        ),
        line(
            "verdict",
            "2026-10-19T20:27:16+02:00",
            round=1,
            station="ui",
            verdict="Änderung",
            muss_count=3,
        ),
        line(
            "verdict",
            "2026-10-19T20:53:02+02:00",
            round=1,
            station="code",
            verdict="OK",
            muss_count=0,
        ),
        line("round_started", "2026-10-19T20:53:16+02:00", round=2),
        line("approved", "2026-10-19T20:57:03+02:00", round=2),
        line("merged", "2026-10-19T20:57:09+02:00", round=2),
        line("run_started", "2026-10-19T21:36:39+02:00", "084-wbs-cross-portal", round=1),
        line(
            "verdict",
            "2026-10-19T23:39:14+02:00",
            "084-wbs-cross-portal",
            round=1,
            station="code",
            verdict="Mensch prüft",
            muss_count=0,
        ),
        line(
            "escalated",
            "2026-10-19T23:39:15+02:00",
            "084-wbs-cross-portal",
            round=1,
            reason="Code-Prüfer: Mensch prüft",
        ),
        line(
            "aborted",
            "2026-10-19T23:39:51+02:00",
            "084-wbs-cross-portal",
            round=1,
            reason="geparkt nach Eskalation",
        ),
    ]


def legacy_run(spec: str, state: str, started: str, **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "spec": spec,
        "branch": spec,
        "base_branch": "pipeline-test",
        "base_commit": SHA,
        "state": state,
        "round": 1,
        "started_at": started,
        "escalation_reason": None,
        "updated_at": started,
    }
    data.update(extra)
    return data


def write_legacy(
    source: Path, events: list[dict[str, Any]] | None = None, *, runs: bool = True
) -> Path:
    source.mkdir(parents=True, exist_ok=True)
    items = legacy_events() if events is None else events
    (source / "events.jsonl").write_text(
        "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8"
    )
    if runs:
        for spec, state, started, extra in (
            ("066-webapp-tooltips", "merged", "2026-10-19T18:38:04+02:00", {"round": 2}),
            (
                "084-wbs-cross-portal",
                "aborted",
                "2026-10-19T21:36:39+02:00",
                {"escalation_reason": "Code-Prüfer: Mensch prüft"},
            ),
            (
                "092-dev-dashboard",
                "aborted",
                "2026-10-19T16:00:00+02:00",
                {"base_commit": "9b9aeff3", "branch": "claude/x", "base_branch": "claude/x"},
            ),
        ):
            folder = source / "runs" / spec
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "run.json").write_text(
                json.dumps(legacy_run(spec, state, started, **extra), ensure_ascii=False),
                encoding="utf-8",
            )
    return source


@pytest.fixture
def legacy(board_repo: Path) -> Path:
    # Das Fixture-Repo hat eigene Läufe und Events; für den Import zählt ein leerer Zustand.
    shutil.rmtree(board_repo / ".spec-agent" / "state", ignore_errors=True)
    return write_legacy(board_repo / ".specify" / "pipeline")


def state_snapshot(root: Path) -> dict[str, bytes]:
    base = root / ".spec-agent" / "state"
    if not base.is_dir():
        return {}
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}


def read_state_events(root: Path) -> list[dict[str, Any]]:
    path = events_path(root)
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


# --- Plan ohne --apply ------------------------------------------------------------------------


def test_plan_writes_nothing(board_repo: Path, legacy: Path) -> None:
    before = state_snapshot(board_repo)
    plan = build_plan(board_repo, load_config(board_repo), legacy)
    assert state_snapshot(board_repo) == before == {}
    assert len(plan.new_runs) == 3 and plan.new_events


def test_cli_without_apply_only_prints_the_plan(
    board_repo: Path, legacy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["migrate", "legacy-pipeline", "--source", str(legacy)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["mode"] == "plan"
    assert out["events"]["new"] > 0 and "--apply" in out["next"]
    assert state_snapshot(board_repo) == {}


def test_cli_apply_and_default_source(
    board_repo: Path, legacy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["migrate", "legacy-pipeline", "--apply"]) == 0  # Default .specify/pipeline
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "applied"
    assert {r["run_id"] for r in out["runs"]} == {
        "066-20261019-163804",
        "084-20261019-193639",
        "092-20261019-140000",
    }
    assert (board_repo / ".spec-agent" / "state" / "events.jsonl").is_file()


def test_cli_missing_source_is_rejected(
    board_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["migrate", "legacy-pipeline", "--source", "gibt/es/nicht"]) == 1
    assert "Quellverzeichnis nicht gefunden" in capsys.readouterr().out


def test_build_plan_raises_for_a_missing_source(board_repo: Path) -> None:
    with pytest.raises(MigrateError):
        build_plan(board_repo, load_config(board_repo), board_repo / "nope")


# --- Läufe ------------------------------------------------------------------------------------


def test_run_ids_follow_spec_and_run_started_time(board_repo: Path, legacy: Path) -> None:
    plan = build_plan(board_repo, load_config(board_repo), legacy)
    ids = {r["spec"]: r["run_id"] for r in plan.runs}
    # 18:38:04+02:00 = 16:38:04Z; ohne run_started (092) zählt started_at aus run.json.
    assert ids == {
        "066-webapp-tooltips": "066-20261019-163804",
        "084-wbs-cross-portal": "084-20261019-193639",
        "092-dev-dashboard": "092-20261019-140000",
    }
    assert all(run_store._RUN_ID.match(i) for i in ids.values())


def test_aborted_stays_aborted_and_state_is_kept(board_repo: Path, legacy: Path) -> None:
    plan = build_plan(board_repo, load_config(board_repo), legacy)
    states = {r["spec"]: r["state"] for r in plan.runs}
    assert states == {
        "066-webapp-tooltips": "merged",
        "084-wbs-cross-portal": "aborted",
        "092-dev-dashboard": "aborted",
    }
    apply_plan(board_repo, plan)
    stored = run_store.read_run(board_repo, "084-20261019-193639")
    assert stored["state"] == "aborted" and stored["paused_from"] is None
    assert stored["imported_from"] == "legacy-pipeline"
    assert stored["base_commit"] == SHA and stored["kind"] == "pipeline"
    assert stored["updated_at"] == "2026-10-19T19:36:39Z"


def test_short_base_commit_is_resolved_through_git_or_replaced(
    board_repo: Path, legacy: Path
) -> None:
    plan = build_plan(board_repo, load_config(board_repo), legacy)
    run = next(r for r, _ in plan.new_runs if r["spec"] == "092-dev-dashboard")
    assert run["base_commit"] == ZERO_SHA
    assert any("9b9aeff3" in w for w in plan.warnings)
    head = os.popen(f'git -C "{board_repo}" rev-parse HEAD').read().strip()
    (legacy / "runs" / "092-dev-dashboard" / "run.json").write_text(
        json.dumps(
            legacy_run(
                "092-dev-dashboard", "aborted", "2026-10-19T16:00:00+02:00", base_commit=head[:8]
            )
        ),
        encoding="utf-8",
    )
    plan = build_plan(board_repo, load_config(board_repo), legacy)
    run = next(r for r, _ in plan.new_runs if r["spec"] == "092-dev-dashboard")
    assert run["base_commit"] == head


def test_unusable_runs_are_skipped_with_a_warning(board_repo: Path, legacy: Path) -> None:
    folder = legacy / "runs" / "100-kaputt"
    folder.mkdir()
    (folder / "run.json").write_text("{nicht json", encoding="utf-8")
    other = legacy / "runs" / "101-zustand"
    other.mkdir()
    (other / "run.json").write_text(
        json.dumps(legacy_run("101-zustand", "geparkt", "2026-10-19T16:00:00+02:00")),
        encoding="utf-8",
    )
    plan = build_plan(board_repo, load_config(board_repo), legacy)
    assert len(plan.runs) == 3
    assert any("100-kaputt" in w for w in plan.warnings)
    assert any("'geparkt' unbekannt" in w for w in plan.warnings)


def test_active_legacy_run_gets_a_lock_warning(board_repo: Path, legacy: Path) -> None:
    (legacy / "runs" / "092-dev-dashboard" / "run.json").write_text(
        json.dumps(
            legacy_run(
                "092-dev-dashboard", "building", "2026-10-19T16:00:00+02:00", base_commit=SHA
            )
        ),
        encoding="utf-8",
    )
    plan = build_plan(board_repo, load_config(board_repo), legacy)
    assert any("Pipeline-Sperre" in w for w in plan.warnings)


# --- Events: Zuordnung aller alten Arten ------------------------------------------------------


@pytest.mark.parametrize(
    ("item", "etype", "data"),
    [
        (line("run_started", "t", round=1), "run.started", {}),
        (line("round_started", "t", round=2), "round.started", {"round": 2}),
        (
            line(
                "station_started",
                "t",
                round=1,
                station="code",
                agent="pipeline-code-reviewer",
                model="opus",
                effort="medium",
            ),
            "station.started",
            {
                "round": 1,
                "role": "code_review",
                "agent": "pipeline-code-reviewer",
                "model": "opus",
                "effort": "medium",
            },
        ),
        (
            line("station_started", "t", round=1, station="builder", agent="pipeline-builder"),
            "station.started",
            {"round": 1, "role": "builder", "agent": "pipeline-builder"},
        ),
        (
            line(
                "station_finished",
                "t",
                round=1,
                station="ui",
                agent="pipeline-ui-reviewer",
                duration_s=91,
            ),
            "station.finished",
            {"round": 1, "role": "ui_review", "agent": "pipeline-ui-reviewer", "duration_s": 91},
        ),
        (
            line("verdict", "t", round=1, station="code", verdict="OK", muss_count=0),
            "verdict.recorded",
            {
                "round": 1,
                "role": "code_review",
                "verdict": "approve",
                "must_count": 0,
                "may_count": 0,
            },
        ),
        (
            line(
                "verdict",
                "t",
                round=1,
                station="ui",
                verdict="Änderung",
                muss_count=3,
                kann_count=2,
            ),
            "verdict.recorded",
            {
                "round": 1,
                "role": "ui_review",
                "verdict": "changes_requested",
                "must_count": 3,
                "may_count": 2,
            },
        ),
        (
            line("verdict", "t", round=1, station="code", verdict="Mensch prüft", muss_count=0),
            "verdict.recorded",
            {
                "round": 1,
                "role": "code_review",
                "verdict": "needs_human",
                "must_count": 0,
                "may_count": 0,
            },
        ),
        (
            line("escalated", "t", round=1, reason="Grund"),
            "run.escalated",
            {"round": 1, "reason": "Grund"},
        ),
        (line("approved", "t", round=2), "run.approved", {}),
        (line("merged", "t", round=2), "run.merged", {}),
        (line("aborted", "t", round=1, reason="geparkt"), "run.aborted", {"reason": "geparkt"}),
        (line("aborted", "t", round=1), "run.aborted", {}),
        (line("released", "t", round=1, reason="frei"), "run.released", {"reason": "frei"}),
        (
            line("hook_debug", "t", None, phase="stop", keys=["a", "b"]),
            "diag.hook",
            {"phase": "stop", "keys": ["a", "b"]},
        ),
    ],
)
def test_every_legacy_kind_maps_to_a_v1_event(
    item: dict[str, Any], etype: str, data: dict[str, Any]
) -> None:
    mapped, reason = map_event(item)
    assert reason == "" and mapped == {"type": etype, "data": data}


@pytest.mark.parametrize(
    "item",
    [
        line("round_started", "t"),
        line("station_started", "t", round=1, station="unbekannt", agent="x"),
        line("station_finished", "t", round=1, station="code", agent="x"),
        line("verdict", "t", round=1, station="code", verdict="Vielleicht", muss_count=0),
        line("verdict", "t", round=1, station="code", verdict="Änderung", muss_count=0),
        line("escalated", "t"),
        line("hook_debug", "t", None, phase="mitte", keys=[]),
    ],
)
def test_unmappable_entries_are_rejected_with_a_reason(item: dict[str, Any]) -> None:
    mapped, reason = map_event(item)
    assert mapped is None and reason


def test_all_imported_events_are_valid_and_chronological(board_repo: Path, legacy: Path) -> None:
    plan = build_plan(board_repo, load_config(board_repo), legacy)
    apply_plan(board_repo, plan)
    events = read_state_events(board_repo)
    assert events and all(contracts.validate_event(e) == [] for e in events)
    stamps = [e["ts"] for e in events]
    assert stamps == sorted(stamps)
    types = {e["type"] for e in events}
    assert {
        "run.started",
        "round.started",
        "station.started",
        "station.finished",
        "verdict.recorded",
        "run.escalated",
        "run.aborted",
        "run.approved",
        "run.merged",
        "diag.hook",
    } <= types
    # 092 hatte kein run_started: eines wird aus run.json ergänzt.
    starts = [e for e in events if e["type"] == "run.started"]
    assert {e["run_id"] for e in starts} == {
        "066-20261019-163804",
        "084-20261019-193639",
        "092-20261019-140000",
    }
    assert plan.by_type["run.started"] == 3


def test_unknown_kinds_and_broken_lines_are_counted(board_repo: Path, legacy: Path) -> None:
    events = legacy_events()
    events += [
        line("queued", "2026-10-19T22:00:00+02:00"),
        line("queued", "2026-10-19T22:01:00+02:00"),
        line(
            "verdict",
            "2026-10-19T22:02:00+02:00",
            round=1,
            station="code",
            verdict="Änderung",
            muss_count=0,
        ),
    ]
    write_legacy(legacy, events)
    with (legacy / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            "das ist kein json\n[1, 2]\n"
            + json.dumps({"ts": "x", "kind": "merged", "spec": "066-webapp-tooltips"})
            + "\n"
        )
    plan = build_plan(board_repo, load_config(board_repo), legacy)
    assert plan.unknown_kinds == {"queued": 2}
    assert plan.skipped["Zeile ist kein JSON"] == 1
    assert plan.skipped["Eintrag ohne 'kind'"] == 1
    assert plan.skipped["Eintrag ohne gültigen Zeitpunkt"] == 1
    assert any("Änderung" in reason for reason in plan.skipped)
    report = plan.to_dict(applied=False)
    assert report["unknown_kinds"] == {"queued": 2}
    assert sum(s["count"] for s in report["skipped"]) == report["events"]["skipped"] == 4


def test_events_of_specs_without_run_json_are_reported(board_repo: Path, legacy: Path) -> None:
    shutil.rmtree(legacy / "runs" / "084-wbs-cross-portal")
    plan = build_plan(board_repo, load_config(board_repo), legacy)
    assert {r["spec"] for r in plan.runs} == {"066-webapp-tooltips", "092-dev-dashboard"}
    assert any("ohne passenden Lauf" in reason for reason in plan.skipped)


# --- Idempotenz und Determinismus -------------------------------------------------------------


def test_second_import_creates_nothing_new(board_repo: Path, legacy: Path) -> None:
    config = load_config(board_repo)
    first = build_plan(board_repo, config, legacy)
    apply_plan(board_repo, first)
    after_first = state_snapshot(board_repo)
    second = build_plan(board_repo, config, legacy)
    assert second.new_events == [] and second.new_runs == []
    assert second.events_present == first.events_mapped
    assert all(r["status"] == "exists" for r in second.runs)
    apply_plan(board_repo, second)
    assert state_snapshot(board_repo) == after_first  # byte-gleich


def test_cli_second_apply_reports_zero_new_events(
    board_repo: Path, legacy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["migrate", "legacy-pipeline", "--apply"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(["migrate", "legacy-pipeline", "--apply"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["events"]["new"] > 0
    assert second["events"]["new"] == 0 and second["events"]["already_present"] > 0


def test_event_ids_are_deterministic_across_projects_copies(
    board_repo: Path, legacy: Path, tmp_path: Path
) -> None:
    other = tmp_path / "kopie"
    shutil.copytree(board_repo, other)
    ids_a = [
        e["event_id"] for e in build_plan(board_repo, load_config(board_repo), legacy).new_events
    ]
    ids_b = [
        e["event_id"]
        for e in build_plan(other, load_config(other), other / ".specify" / "pipeline").new_events
    ]
    assert ids_a == ids_b and len(set(ids_a)) == len(ids_a)


def test_identical_legacy_lines_keep_distinct_but_stable_ids(
    board_repo: Path, legacy: Path
) -> None:
    twin = line("hook_debug", "2026-10-19T16:45:53+02:00", None, phase="start", keys=["a"])
    write_legacy(legacy, [twin, twin, line("run_started", "2026-10-19T18:38:04+02:00", round=1)])
    config = load_config(board_repo)
    plan = build_plan(board_repo, config, legacy)
    hook_ids = [e["event_id"] for e in plan.new_events if e["type"] == "diag.hook"]
    assert len(hook_ids) == 2 and len(set(hook_ids)) == 2
    apply_plan(board_repo, plan)
    assert build_plan(board_repo, config, legacy).new_events == []


def test_import_keeps_native_events_and_runs(board_repo: Path) -> None:
    # Ohne Zurücksetzen des Zustands: vorhandene Läufe und Events bleiben unberührt.
    source = write_legacy(board_repo / ".specify" / "pipeline")
    before = state_snapshot(board_repo)
    plan = build_plan(board_repo, load_config(board_repo), source)
    apply_plan(board_repo, plan)
    after = state_snapshot(board_repo)
    for name, content in before.items():
        if name == "events.jsonl":
            assert after[name].startswith(content)
        else:
            assert after[name] == content


# --- Wirkung auf das Board --------------------------------------------------------------------


@pytest.mark.usefixtures("fixed_now")
def test_board_shows_the_imported_runs(board_repo: Path, legacy: Path) -> None:
    config = load_config(board_repo)
    apply_plan(board_repo, build_plan(board_repo, config, legacy))
    doc = build_board(board_repo, config)
    assert contracts.validate_board(doc) == []
    runs = {r["run_id"]: r for r in doc["runs"]}
    assert set(runs) == {"066-20261019-163804", "084-20261019-193639", "092-20261019-140000"}
    parked = runs["084-20261019-193639"]
    assert parked["state"] == "aborted" and parked["active"] is False
    assert [e["open"] for e in parked["escalations"]] == [
        False
    ]  # Eskalation durch Abbruch erledigt
    merged = runs["066-20261019-163804"]
    assert merged["state"] == "merged" and merged["round"] == 2
    verdicts = [s.get("verdict") for s in merged["stations"] if s.get("verdict")]
    assert verdicts == ["changes_requested", "approve"]
    assert not [a for a in doc["attention"] if a["kind"] in {"escalation", "stale_run"}]


# --- Optionaler Test gegen die echte alte Pipeline (nur lesend, auf einer Kopie) --------------

ENV = "SAK_IMMOAGENT_PIPELINE"


@pytest.mark.skipif(not os.environ.get(ENV), reason=f"{ENV} nicht gesetzt")
def test_real_pipeline_copy_imports_idempotently(board_repo: Path) -> None:
    original = Path(os.environ[ENV])
    shutil.rmtree(board_repo / ".spec-agent" / "state", ignore_errors=True)
    copy = board_repo / "kopie-pipeline"
    shutil.copytree(original, copy)
    config = load_config(board_repo)
    plan = build_plan(board_repo, config, copy)
    apply_plan(board_repo, plan)
    events = read_state_events(board_repo)
    assert events and all(contracts.validate_event(e) == [] for e in events)
    print("\nLäufe:", [(r["run_id"], r["state"]) for r in plan.runs])
    print("Events:", plan.to_dict(applied=True)["events"], "unbekannt:", dict(plan.unknown_kinds))
    again = build_plan(board_repo, config, copy)
    assert again.new_events == [] and again.new_runs == []
