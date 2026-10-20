"""Kit, Lockfile, spec-kit-Erkennung (Spec 005, T002 und T003)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from install_support import REAL_KIT_ROOT, make_target

from spec_agent_kit import __version__
from spec_agent_kit.install import InstallError
from spec_agent_kit.install.kit import Kit, kit_root, locate_kit, sha256_of, version_tuple
from spec_agent_kit.install.lock import Lock, read_lock
from spec_agent_kit.install.speckit import INIT_COMMAND, detect_version


def test_kit_root_is_the_checkout() -> None:
    assert kit_root() == REAL_KIT_ROOT
    assert locate_kit().version == __version__


def test_locate_kit_is_disabled_without_a_kit_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    # In der vendorten Kopie im Ziel gibt es kein Kit-Repo: kit_root() liefert None.
    monkeypatch.setattr("spec_agent_kit.install.kit.kit_root", lambda: None)
    with pytest.raises(InstallError, match="aus dem Kit-Repo aufrufen"):
        locate_kit()


def test_kit_at_rejects_a_non_kit_directory(tmp_path: Path) -> None:
    with pytest.raises(InstallError):
        Kit.at(tmp_path)


def test_managed_files_cover_agents_skills_engine_and_gitignore() -> None:
    managed = Kit.at(REAL_KIT_ROOT).managed_files()
    assert ".claude/agents/sak-builder.md" in managed
    assert ".claude/agents/sak-code-reviewer.md" in managed
    assert ".claude/skills/sak-pipeline/SKILL.md" in managed
    assert ".spec-agent/.gitignore" in managed
    assert ".spec-agent/engine/pyproject.toml" in managed
    assert ".spec-agent/engine/uv.lock" in managed
    assert ".spec-agent/engine/src/spec_agent_kit/cli.py" in managed
    assert ".spec-agent/engine/src/spec_agent_kit/install/plan.py" in managed
    assert ".spec-agent/engine/src/spec_agent_kit/schemas/lock.schema.json" in managed


def test_managed_files_exclude_tests_venv_caches_config_and_lock() -> None:
    managed = Kit.at(REAL_KIT_ROOT).managed_files()
    for path in managed:
        parts = path.split("/")
        assert "tests" not in parts, path
        assert ".venv" not in parts, path
        assert "__pycache__" not in parts, path
        assert ".ruff_cache" not in parts, path
        assert ".pytest_cache" not in parts, path
        assert not path.endswith(".pyc"), path
    assert ".spec-agent/config.yml" not in managed
    assert ".spec-agent/lock.json" not in managed
    assert ".claude/settings.json" not in managed
    assert list(managed) == sorted(managed)


def test_managed_files_ignore_a_local_venv_and_caches(tmp_path: Path) -> None:
    from install_support import make_kit

    kit = make_kit(tmp_path)
    engine = kit.root / "packages" / "engine"
    (engine / ".venv" / "Lib").mkdir(parents=True)
    (engine / ".venv" / "Lib" / "x.py").write_text("x", encoding="utf-8")
    (engine / "src" / "spec_agent_kit" / "__pycache__").mkdir(parents=True, exist_ok=True)
    (engine / "src" / "spec_agent_kit" / "__pycache__" / "a.pyc").write_bytes(b"\0")
    (engine / ".ruff_cache").mkdir()
    (engine / ".ruff_cache" / "c").write_text("c", encoding="utf-8")
    (engine / "tests").mkdir(exist_ok=True)
    (engine / "tests" / "test_x.py").write_text("x", encoding="utf-8")
    assert not [p for p in kit.managed_files() if "venv" in p or "cache" in p or "tests" in p]


def test_the_gitignore_template_covers_state_and_key() -> None:
    text = (REAL_KIT_ROOT / "packages/agent-blueprint/templates/spec-agent/gitignore").read_text(
        encoding="utf-8"
    )
    lines = text.splitlines()
    assert "state/" in lines
    assert "dashboard.key" in lines


def test_hash_ignores_line_endings_of_text_but_not_of_binary() -> None:
    assert sha256_of(b"a\r\nb\r\n") == sha256_of(b"a\nb\n")
    assert sha256_of(b"a\r\n\0") != sha256_of(b"a\n\0")


def test_version_tuple() -> None:
    assert version_tuple("1.2.3") == (1, 2, 3)
    assert version_tuple("0.10.0-rc.1") == (0, 10, 0)
    assert version_tuple("0.9.0") < version_tuple("0.10.0")
    with pytest.raises(ValueError, match="keine Version"):
        version_tuple("latest")


def _lock(**changes: object) -> Lock:
    base = Lock("0.1.0", "2026-10-20T10:20:00Z", None, {"a/b.md": "a" * 64}, "c" * 64)
    for key, value in changes.items():
        setattr(base, key, value)
    return base


def test_lock_round_trip(tmp_path: Path) -> None:
    lock = _lock()
    path = tmp_path / ".spec-agent" / "lock.json"
    path.parent.mkdir()
    path.write_bytes(lock.dumps())
    assert read_lock(tmp_path) == lock
    assert json.loads(path.read_text(encoding="utf-8"))["schema"] == "sak.lock/1"


def test_lock_missing_is_none(tmp_path: Path) -> None:
    assert read_lock(tmp_path) is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(files={"x": "kein-hash"}),
        lambda d: d.update(extra=1),
        lambda d: d.pop("settings_fragment_hash"),
        lambda d: d.update(schema="sak.lock/2"),
    ],
)
def test_invalid_lock_is_rejected(tmp_path: Path, mutate: object) -> None:
    data = json.loads(_lock().dumps())
    mutate(data)  # type: ignore[operator]
    path = tmp_path / ".spec-agent" / "lock.json"
    path.parent.mkdir()
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(InstallError, match="ungültig"):
        read_lock(tmp_path)


def test_unreadable_lock_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / ".spec-agent" / "lock.json"
    path.parent.mkdir()
    path.write_text("{kaputt", encoding="utf-8")
    with pytest.raises(InstallError, match="nicht lesbar"):
        read_lock(tmp_path)


def test_speckit_version_is_detected(tmp_path: Path) -> None:
    assert detect_version(make_target(tmp_path)) == "0.12.16"


@pytest.mark.parametrize("version", ["0.12.0", "0.13.1", "1.0.13", "v0.12.2"])
def test_supported_speckit_versions(tmp_path: Path, version: str) -> None:
    root = make_target(tmp_path, speckit={"speckit_version": version})
    assert detect_version(root) == version


def test_old_speckit_is_rejected_with_the_command(tmp_path: Path) -> None:
    root = make_target(tmp_path, speckit={"speckit_version": "0.11.9"})
    with pytest.raises(InstallError, match="zu alt") as caught:
        detect_version(root)
    assert INIT_COMMAND in caught.value.errors[0]["message"]


def test_missing_speckit_is_rejected_with_the_command(tmp_path: Path) -> None:
    root = make_target(tmp_path, speckit=None)
    with pytest.raises(InstallError, match="spec-kit fehlt") as caught:
        detect_version(root)
    assert INIT_COMMAND in caught.value.errors[0]["message"]


def test_unreadable_speckit_options_are_rejected(tmp_path: Path) -> None:
    root = make_target(tmp_path, speckit={"keine_version": 1})
    with pytest.raises(InstallError, match="keine spec-kit-Version"):
        detect_version(root)
