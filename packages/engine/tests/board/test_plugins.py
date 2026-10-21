"""Plugin-Mechanismus und ``legacy-status`` (Spec 010 US5, FR-006, A04)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from spec_agent_kit import contracts
from spec_agent_kit.board.build import build_board
from spec_agent_kit.config import ConfigError, load_config
from spec_agent_kit.plugins import PluginContext, PluginResult, list_spec_dirs, run_plugins

BLOCKERS = """\
# Spec-Blocker, manuell gepflegt
blockers:
  003-search:
    type: account
    ref: ""
    detail: "echtes Konto + manuelle 2FA"
    actionable: blocked
  004-billing:
    type: other
    detail: "Backfill bewusst nicht ungefragt gebaut"
    actionable: partial
  002-importer:
    type: fixture
    detail: "wird nur vermerkt"
    actionable: ready
  099-gibt-es-nicht:
    type: other
    detail: "unbekannte Spec"
    actionable: blocked
"""

DECISIONS = """\
# Deferred Decisions

## Offen

| # | Frage | Betrifft | Lösung |
|---|-------|----------|--------|
| DQ-11 | Soll der Export CSV oder JSON liefern? —— lange Begründung | Spec 006 | |
| DQ-12 | Allgemeine Frage ohne Spec | Alle | |

## Gelöst

| # | Frage | Betrifft | Lösung |
|---|-------|----------|--------|
| DQ-01 | Cookie läuft ab? | Spec 003 | ✅ **beantwortet** (2026-09-15): ja |
"""

STATUS = """\
feature_status_report:
  specs:
    - spec_dir: 005-notify
      status: descoped
    - spec_dir: 004-billing
      status: partial
    - spec_dir: 077-unbekannt
      status: descoped
"""


def write_legacy_files(root: Path, *, blockers: bool = True, decisions: bool = True) -> None:
    folder = root / ".specify"
    folder.mkdir(exist_ok=True)
    if blockers:
        (folder / "blockers.yml").write_text(BLOCKERS, encoding="utf-8")
    if decisions:
        (folder / "deferred-decisions.md").write_text(DECISIONS, encoding="utf-8")
    (folder / "feature-status.yml").write_text(STATUS, encoding="utf-8")


def enable(root: Path, plugins: list[dict[str, Any]]) -> None:
    path = root / ".spec-agent" / "config.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["plugins"] = plugins
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def board_with_plugin(root: Path) -> dict[str, Any]:
    enable(root, [{"name": "legacy-status"}])
    return build_board(root, load_config(root))


@pytest.mark.usefixtures("fixed_now")
def test_without_plugins_there_are_no_blockers_or_decisions(board_repo: Path) -> None:
    write_legacy_files(board_repo)
    doc = build_board(board_repo, load_config(board_repo))
    assert doc["metrics"]["blocked"] == 0
    assert not {a["kind"] for a in doc["attention"]} & {"blocker", "decision"}


@pytest.mark.usefixtures("fixed_now")
def test_blockers_set_blocked_and_attention_like_the_old_board(board_repo: Path) -> None:
    write_legacy_files(board_repo)
    doc = board_with_plugin(board_repo)
    blocked = sorted(s["dir"] for s in doc["specs"] if s["blocked"])
    assert blocked == ["002-importer", "003-search", "004-billing"]  # jeder Eintrag, auch „ready“
    assert doc["metrics"]["blocked"] == 3
    entries = {a["spec"]: a for a in doc["attention"] if a["kind"] == "blocker"}
    assert sorted(entries) == ["003-search", "004-billing"]  # nur blocked und partial
    assert entries["003-search"]["reason"] == "echtes Konto + manuelle 2FA"
    assert entries["003-search"]["source"] == "blockers.yml"
    assert contracts.validate_board(doc) == []


@pytest.mark.usefixtures("fixed_now")
def test_open_decisions_become_attention_and_resolved_ones_do_not(board_repo: Path) -> None:
    write_legacy_files(board_repo)
    doc = board_with_plugin(board_repo)
    decisions = [a for a in doc["attention"] if a["kind"] == "decision"]
    by_reason = {a["reason"]: a for a in decisions}
    assert sorted(by_reason) == [
        "Allgemeine Frage ohne Spec (DQ-12)",
        "Soll der Export CSV oder JSON liefern? (DQ-11)",
    ]
    assert by_reason["Soll der Export CSV oder JSON liefern? (DQ-11)"]["spec"] == "006-export"
    assert "spec" not in by_reason["Allgemeine Frage ohne Spec (DQ-12)"]
    assert all(a["source"] == "deferred-decisions.md" for a in decisions)


@pytest.mark.usefixtures("fixed_now")
def test_feature_status_descoped_is_applied_and_unknown_specs_are_ignored(
    board_repo: Path,
) -> None:
    write_legacy_files(board_repo)
    doc = board_with_plugin(board_repo)
    (item,) = [s for s in doc["specs"] if s["dir"] == "005-notify"]
    assert item["descoped"] is True and item["stage"] is None
    assert all(s["dir"] != "077-unbekannt" for s in doc["specs"])


@pytest.mark.usefixtures("fixed_now")
def test_missing_files_are_notes_not_errors(board_repo: Path) -> None:
    write_legacy_files(board_repo, blockers=False, decisions=False)
    doc = board_with_plugin(board_repo)
    assert any("blockers.yml fehlt" in n for n in doc["notes"])
    assert any("deferred-decisions.md fehlt" in n for n in doc["notes"])
    assert doc["metrics"]["blocked"] == 0
    assert contracts.validate_board(doc) == []


@pytest.mark.usefixtures("fixed_now")
def test_broken_yaml_is_a_note(board_repo: Path) -> None:
    write_legacy_files(board_repo)
    (board_repo / ".specify" / "blockers.yml").write_text("blockers: [unvollständig\n", "utf-8")
    doc = board_with_plugin(board_repo)
    assert any("blockers.yml ist kein gültiges YAML" in n for n in doc["notes"])
    assert doc["metrics"]["blocked"] == 0


@pytest.mark.usefixtures("fixed_now")
def test_options_can_point_to_other_files_but_not_out_of_the_project(
    board_repo: Path, tmp_path: Path
) -> None:
    write_legacy_files(board_repo)
    (board_repo / "docs").mkdir()
    (board_repo / "docs" / "stops.yml").write_text(BLOCKERS, encoding="utf-8")
    (board_repo / ".specify" / "blockers.yml").unlink()
    enable(
        board_repo,
        [
            {
                "name": "legacy-status",
                "options": {"blockers_file": "docs/stops.yml", "decisions_file": "../draussen.md"},
            }
        ],
    )
    doc = build_board(board_repo, load_config(board_repo))
    assert doc["metrics"]["blocked"] == 3
    assert any("decisions_file" in n and "hinaus" in n for n in doc["notes"])


@pytest.mark.usefixtures("fixed_now")
def test_a_failing_plugin_never_breaks_the_board(
    board_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(ctx: PluginContext) -> PluginResult:
        raise RuntimeError("kaputt")

    monkeypatch.setattr("spec_agent_kit.plugins.registry", lambda: {"legacy-status": boom})
    write_legacy_files(board_repo)
    doc = board_with_plugin(board_repo)
    assert any(
        "Plugin 'legacy-status' fehlgeschlagen (RuntimeError: kaputt)" in n for n in doc["notes"]
    )
    assert len(doc["specs"]) == 6 and contracts.validate_board(doc) == []


@pytest.mark.usefixtures("fixed_now")
def test_a_plugin_with_invalid_entries_is_repaired_by_dropping_them(
    board_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def messy(ctx: PluginContext) -> PluginResult:
        result = PluginResult()
        result.attention.append({"kind": "gibt-es-nicht", "reason": "x", "source": "p"})
        return result

    monkeypatch.setattr("spec_agent_kit.plugins.registry", lambda: {"legacy-status": messy})
    doc = board_with_plugin(board_repo)
    assert contracts.validate_board(doc) == []
    assert any("attention" in n and "verworfen" in n for n in doc["notes"])


def test_run_plugins_isolates_each_plugin(tmp_path: Path) -> None:
    def good(ctx: PluginContext) -> PluginResult:
        return PluginResult(blocked={"001-a"})

    def bad(ctx: PluginContext) -> PluginResult:
        raise ValueError("nein")

    result = run_plugins(
        tmp_path,
        [{"name": "bad"}, {"name": "good"}, {"name": "weg"}],
        ["001-a"],
        plugins={"good": good, "bad": bad},
    )
    assert result.blocked == {"001-a"}
    assert len(result.notes) == 2
    assert "bad" in result.notes[0] and "weg" in result.notes[1]


def test_list_spec_dirs(tmp_path: Path) -> None:
    assert list_spec_dirs(tmp_path) == []
    (tmp_path / "specs" / "002-b").mkdir(parents=True)
    (tmp_path / "specs" / "001-a").mkdir()
    (tmp_path / "specs" / "datei.md").write_text("x", encoding="utf-8")
    assert list_spec_dirs(tmp_path) == ["001-a", "002-b"]


def test_config_accepts_plugins_and_rejects_unknown_names(board_repo: Path) -> None:
    enable(board_repo, [{"name": "legacy-status", "options": {"blockers_file": "x.yml"}}])
    assert load_config(board_repo).data["plugins"][0]["name"] == "legacy-status"
    enable(board_repo, [{"name": "gibt-es-nicht"}])
    with pytest.raises(ConfigError):
        load_config(board_repo)
