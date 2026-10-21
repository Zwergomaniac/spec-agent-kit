"""Additiver Settings-Merge (Spec 005 FR-005, T005)."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from install_support import OWN_SETTINGS, REAL_KIT_ROOT

from spec_agent_kit.install.doctor import REQUIRED_DENY
from spec_agent_kit.install.settings import (
    LEGACY_KIT_ALLOW,
    allow_entries,
    dumps_settings,
    merge_settings,
    merge_settings_detailed,
    parse_settings,
    unsafe_mode_in,
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
    # Der eigene SessionStart-Hook bleibt an erster Stelle, der Kit-Hook (compact) kommt dazu.
    session = merged["hooks"]["SessionStart"]
    assert session[0] == OWN_SETTINGS["hooks"]["SessionStart"][0]
    assert session[1:] == FRAGMENT["hooks"]["SessionStart"]
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


OLD_START = {
    "matcher": "sak-.*",
    "hooks": [
        {
            "type": "command",
            "command": 'uv run --project "$CLAUDE_PROJECT_DIR/.spec-agent/engine" sak hook '
            "subagent-start || true",
            "timeout": 5,
        }
    ],
}
OLD_STOP = {
    "matcher": "sak-.*",
    "hooks": [
        {
            "type": "command",
            "command": 'uv run --project "$CLAUDE_PROJECT_DIR/.spec-agent/engine" sak hook '
            "subagent-stop || true",
            "timeout": 5,
        }
    ],
}
FOREIGN_HOOK = {"matcher": "x-.*", "hooks": [{"type": "command", "command": "echo fremd"}]}


def test_fragment_hooks_call_the_posix_starter_with_timeout_10() -> None:
    for event, name in (("SubagentStart", "subagent-start"), ("SubagentStop", "subagent-stop")):
        (entry,) = FRAGMENT["hooks"][event]
        (hook,) = entry["hooks"]
        assert hook["command"] == f'sh "$CLAUDE_PROJECT_DIR/.spec-agent/sak" hook {name} || true'
        assert hook["timeout"] == 10
        assert "uv run" not in hook["command"]
        assert ".spec-agent/engine" not in hook["command"]


def test_upgrade_replaces_old_direct_uv_hooks_with_the_starter_version() -> None:
    old = {
        "hooks": {
            "SessionStart": [FOREIGN_HOOK],
            "SubagentStart": [FOREIGN_HOOK, OLD_START],
            "SubagentStop": [OLD_STOP, FOREIGN_HOOK],
        }
    }
    original = copy.deepcopy(old)
    merged, _ = merge_settings(old, FRAGMENT)
    assert old == original
    assert merged["hooks"]["SessionStart"] == [FOREIGN_HOOK, *FRAGMENT["hooks"]["SessionStart"]]
    assert merged["hooks"]["SubagentStart"] == [FOREIGN_HOOK, FRAGMENT["hooks"]["SubagentStart"][0]]
    assert merged["hooks"]["SubagentStop"] == [FRAGMENT["hooks"]["SubagentStop"][0], FOREIGN_HOOK]
    assert ".spec-agent/engine" not in json.dumps(merged["hooks"])
    again, _ = merge_settings(merged, FRAGMENT)
    assert again == merged  # zweiter Lauf ändert nichts


def test_foreign_hook_sharing_an_entry_with_a_kit_hook_survives() -> None:
    mixed = {
        "matcher": "sak-.*",
        "hooks": [{"type": "command", "command": "echo fremd"}, OLD_START["hooks"][0]],
    }
    merged, _ = merge_settings({"hooks": {"SubagentStart": [mixed]}}, FRAGMENT)
    commands = [h["command"] for e in merged["hooks"]["SubagentStart"] for h in e["hooks"]]
    assert commands.count("echo fremd") == 1
    assert sum(".spec-agent/sak" in c for c in commands) == 1
    assert not any(".spec-agent/engine" in c for c in commands)


def test_duplicate_kit_entries_collapse_to_one() -> None:
    existing = {"hooks": {"SubagentStart": [OLD_START, FOREIGN_HOOK, OLD_START]}}
    merged, _ = merge_settings(existing, FRAGMENT)
    assert merged["hooks"]["SubagentStart"] == [FRAGMENT["hooks"]["SubagentStart"][0], FOREIGN_HOOK]


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


# --- Spec 011: SessionStart, Herkunft der allow-Einträge, unsicherer Modus ------------------


def test_session_start_hook_is_added_once_with_the_compact_matcher() -> None:
    once, _ = merge_settings(OWN_SETTINGS, FRAGMENT)
    twice, _ = merge_settings(once, FRAGMENT)
    kit_entries = [
        entry for entry in twice["hooks"]["SessionStart"] if ".spec-agent/sak" in json.dumps(entry)
    ]
    assert len(kit_entries) == 1 and kit_entries[0]["matcher"] == "compact"
    assert kit_entries[0]["hooks"][0]["command"].endswith("hook session-start || true")
    assert twice == once


def test_owned_allow_entries_are_replaced_and_foreign_ones_stay() -> None:
    existing = {
        "permissions": {"allow": ["Bash(npm test)", "Bash(old *)", "Bash(git status)", "Bash(x)"]}
    }
    result = merge_settings_detailed(existing, FRAGMENT, ["Bash(new *)"], ["Bash(old *)"])
    allow = result.merged["permissions"]["allow"]
    assert "Bash(old *)" not in allow
    assert allow[:3] == ["Bash(npm test)", "Bash(git status)", "Bash(x)"]  # fremd, Reihenfolge
    assert "Bash(new *)" in allow
    assert result.allow_removed == ["Bash(old *)"]
    assert "Bash(new *)" in result.allow_added
    # Eigentum: nur, was das Kit ergänzt hat (git status war schon da).
    assert "Bash(git status)" not in result.allow_owned
    assert "Bash(new *)" in result.allow_owned
    assert "Bash(git diff)" in result.allow_owned
    assert result.legacy_lock is False


def test_an_owned_entry_that_is_still_wanted_stays_owned() -> None:
    first = merge_settings_detailed(None, FRAGMENT, ["Bash(a *)"], [])
    second = merge_settings_detailed(first.merged, FRAGMENT, ["Bash(a *)"], first.allow_owned)
    assert second.allow_added == [] and second.allow_removed == []
    assert second.allow_owned == first.allow_owned
    assert second.merged == first.merged


def test_without_owned_list_only_known_kit_patterns_are_replaced() -> None:
    existing = {
        "permissions": {
            "allow": ["Bash(git switch *)", "Bash(git merge *)", "Bash(npm test)", "Bash(old *)"]
        }
    }
    result = merge_settings_detailed(existing, FRAGMENT, ["Bash(new *)"], None)
    assert result.legacy_lock is True
    assert set(result.allow_removed) == LEGACY_KIT_ALLOW
    allow = result.merged["permissions"]["allow"]
    assert "Bash(npm test)" in allow and "Bash(old *)" in allow  # Herkunft unbekannt: bleibt


def test_a_fresh_install_owns_nothing_beforehand() -> None:
    existing = {"permissions": {"allow": ["Bash(git merge *)"]}}
    result = merge_settings_detailed(existing, FRAGMENT, [], [])
    assert "Bash(git merge *)" in result.merged["permissions"]["allow"]
    assert result.allow_removed == []


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ({"permissions": {"defaultMode": UNSAFE}}, True),
        ({"defaultMode": UNSAFE}, True),
        ({"permissions": {"defaultMode": UNSAFE.lower()}}, True),
        ({"permissions": {"defaultMode": " " + UNSAFE + " "}}, True),
        ({"permissions": {"defaultMode": "acceptEdits"}}, False),
        ({"permissions": {"defaultMode": 7}}, False),
        ({"permissions": []}, False),
        ({}, False),
        (None, False),
        ([UNSAFE], False),
    ],
)
def test_unsafe_mode_detection(settings: Any, expected: bool) -> None:
    assert unsafe_mode_in(settings) is expected


def test_unsafe_mode_at_the_top_level_is_warned_about_too() -> None:
    _, warnings = merge_settings({"defaultMode": UNSAFE}, FRAGMENT)
    assert len(warnings) == 1 and "defaultMode" in warnings[0]
