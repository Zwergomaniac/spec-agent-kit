"""Additiver Settings-Merge (Spec 005 FR-005, T005)."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from install_support import OWN_SETTINGS, REAL_KIT_ROOT

from spec_agent_kit.install.doctor import REQUIRED_DENY
from spec_agent_kit.install.settings import (
    allow_entries,
    dumps_settings,
    merge_settings,
    parse_settings,
)

FRAGMENT: dict[str, Any] = json.loads(
    (REAL_KIT_ROOT / "packages/agent-blueprint/templates/claude/settings.fragment.json").read_text(
        encoding="utf-8"
    )
)
UNSAFE = "bypass" + "Permissions"


def test_missing_file_is_created_from_the_fragment() -> None:
    merged, warnings = merge_settings(None, FRAGMENT)
    assert merged == FRAGMENT
    assert warnings == []


def test_existing_hooks_and_settings_stay_untouched() -> None:
    original = copy.deepcopy(OWN_SETTINGS)
    merged, warnings = merge_settings(original, FRAGMENT)
    assert original == OWN_SETTINGS  # die Eingabe wird nicht verändert
    assert warnings == []
    assert merged["hooks"]["SessionStart"] == OWN_SETTINGS["hooks"]["SessionStart"]
    assert merged["env"] == OWN_SETTINGS["env"]
    assert merged["permissions"]["defaultMode"] == "acceptEdits"
    assert set(merged["hooks"]) == {"SessionStart", "SubagentStart", "SubagentStop"}


def test_allow_and_deny_are_united_without_duplicates_and_in_order() -> None:
    merged, _ = merge_settings(OWN_SETTINGS, FRAGMENT)
    allow = merged["permissions"]["allow"]
    assert allow[:2] == OWN_SETTINGS["permissions"]["allow"]  # eigene Einträge zuerst
    assert "Bash(git status)" in allow
    assert allow.count("Bash(git status)") == 1  # steht in beiden, kommt einmal vor
    assert "Bash(uv run --project .spec-agent/engine sak *)" in allow
    assert merged["permissions"]["deny"] == FRAGMENT["permissions"]["deny"]


def test_existing_deny_entries_are_kept_and_extended() -> None:
    existing = {"permissions": {"deny": ["Read(./secrets/**)", "Bash(git push)"]}}
    merged, _ = merge_settings(existing, FRAGMENT)
    deny = merged["permissions"]["deny"]
    assert deny[:2] == ["Read(./secrets/**)", "Bash(git push)"]
    assert deny.count("Bash(git push)") == 1
    assert set(FRAGMENT["permissions"]["deny"]) <= set(deny)


def test_extra_allow_entries_are_added() -> None:
    merged, _ = merge_settings(None, FRAGMENT, ["Bash(uv run pytest -q *)"])
    assert "Bash(uv run pytest -q *)" in merged["permissions"]["allow"]


def test_hook_is_not_added_when_the_event_already_calls_the_engine() -> None:
    own = {
        "hooks": {
            "SubagentStart": [
                {
                    "matcher": "x-.*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "uv run --project .spec-agent/engine sak hook",
                        }
                    ],
                }
            ]
        }
    }
    merged, _ = merge_settings(own, FRAGMENT)
    assert merged["hooks"]["SubagentStart"] == own["hooks"]["SubagentStart"]
    assert len(merged["hooks"]["SubagentStop"]) == 1  # für Stop fehlte der Eintrag


def test_hook_of_the_target_for_the_same_event_is_kept_and_ours_is_appended() -> None:
    own = {
        "hooks": {"SubagentStart": [{"hooks": [{"type": "command", "command": "echo eigener"}]}]}
    }
    merged, _ = merge_settings(own, FRAGMENT)
    entries = merged["hooks"]["SubagentStart"]
    assert entries[0] == own["hooks"]["SubagentStart"][0]
    assert entries[1] == FRAGMENT["hooks"]["SubagentStart"][0]


def test_unsafe_default_mode_is_kept_and_warned_about() -> None:
    existing = {"permissions": {"defaultMode": UNSAFE}}
    merged, warnings = merge_settings(existing, FRAGMENT)
    assert merged["permissions"]["defaultMode"] == UNSAFE
    assert len(warnings) == 1
    assert "defaultMode" in warnings[0]
    assert "unverändert" in warnings[0]


def test_fragment_never_sets_a_default_mode() -> None:
    merged, warnings = merge_settings(None, FRAGMENT)
    assert "defaultMode" not in merged.get("permissions", {})
    assert warnings == []


@pytest.mark.parametrize("start", [None, OWN_SETTINGS, {"permissions": {"allow": ["x"]}}, {}])
def test_merge_is_idempotent(start: dict[str, Any] | None) -> None:
    once, _ = merge_settings(start, FRAGMENT, ["Bash(a *)"])
    twice, _ = merge_settings(once, FRAGMENT, ["Bash(a *)"])
    assert once == twice
    assert dumps_settings(once) == dumps_settings(twice)


def test_key_order_of_the_existing_file_is_kept() -> None:
    existing = {"zzz": 1, "permissions": {"defaultMode": "plan", "allow": []}, "aaa": 2}
    merged, _ = merge_settings(existing, FRAGMENT)
    assert list(merged)[:3] == ["zzz", "permissions", "aaa"]
    assert list(merged["permissions"])[:2] == ["defaultMode", "allow"]
    assert list(merged)[-1] == "hooks"  # neue Schlüssel kommen ans Ende


def test_output_uses_two_spaces_and_a_final_newline() -> None:
    text = dumps_settings({"a": {"b": 1}, "text": "Größe"})
    assert text == '{\n  "a": {\n    "b": 1\n  },\n  "text": "Größe"\n}\n'


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(ValueError, match="kein gültiges JSON"):
        parse_settings("{kaputt")
    with pytest.raises(ValueError, match="JSON-Objekt"):
        parse_settings("[1, 2]")
    assert parse_settings('{"a": 1}') == {"a": 1}


def test_allow_entries_turn_paths_into_wildcards() -> None:
    assert allow_entries(["uv run pytest -q {paths}", "uv run ruff check .", "  "]) == [
        "Bash(uv run pytest -q *)",
        "Bash(uv run ruff check .)",
    ]
    assert allow_entries(["a", "a"]) == ["Bash(a)"]


def test_required_deny_rules_match_the_fragment() -> None:
    assert set(REQUIRED_DENY) == set(FRAGMENT["permissions"]["deny"])
