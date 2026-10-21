"""Verwaltete Starter ``.spec-agent/sak.cmd`` und ``.spec-agent/sak`` (Spec 009 FR-001, A02)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from install_support import Sak, git, read_json, write

from spec_agent_kit.install.apply import ensure_launcher_mode
from spec_agent_kit.install.kit import Kit, sha256_of

CMD = ".spec-agent/sak.cmd"
SH = ".spec-agent/sak"


def _template(kit: Kit, name: str) -> Path:
    return kit.templates / "spec-agent" / name


def _installed(sak: Sak, init_args: list[str], target: Path) -> None:
    code, out = sak(*init_args, "--apply")
    assert code == 0, out
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "sak init")


def test_kit_manages_both_launchers() -> None:
    from install_support import REAL_KIT_ROOT

    managed = Kit.at(REAL_KIT_ROOT).managed_files()
    assert managed[CMD].name == "sak.cmd" and managed[SH].name == "sak"


def test_init_installs_both_launchers_and_locks_them(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    code, plan = sak(*init_args)
    assert code == 0
    created = {a["path"] for a in plan["actions"] if a["action"] == "create"}
    assert {CMD, SH} <= created
    code, _ = sak(*init_args, "--apply")
    assert code == 0
    lock = read_json(target / ".spec-agent/lock.json")["files"]
    for path, name in ((CMD, "sak.cmd"), (SH, "sak")):
        assert (target / path).is_file()
        assert lock[path] == sha256_of(_template(kit, name).read_bytes())


def test_cmd_is_written_with_crlf_and_sh_with_lf(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    assert sak(*init_args, "--apply")[0] == 0
    cmd = (target / CMD).read_bytes()
    sh = (target / SH).read_bytes()
    assert cmd.count(b"\r\n") == cmd.count(b"\n") > 0
    assert b"\r" not in sh and sh.startswith(b"#!/bin/sh\n")


def test_init_does_not_list_launchers_as_conflicts_on_a_second_plan(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    code, plan = sak("upgrade", str(target), "--no-sync")
    assert code == 0 and plan["empty"] is True


def test_upgrade_replaces_an_unchanged_launcher(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    from install_support import bump_version

    _installed(sak, init_args, target)
    template = _template(kit, "sak")
    template.write_text(
        template.read_text(encoding="utf-8") + "# neu\n", encoding="utf-8", newline="\n"
    )
    bump_version(kit, "0.4.0")
    code, plan = sak("upgrade", str(target), "--no-sync", "--apply")
    assert code == 0
    assert {a["path"]: a["action"] for a in plan["actions"]}[SH] == "replace"
    assert (target / SH).read_text(encoding="utf-8").endswith("# neu\n")


def test_upgrade_keeps_a_locally_changed_launcher_and_writes_sak_new(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    from install_support import bump_version

    _installed(sak, init_args, target)
    write(target, SH, "#!/bin/sh\necho eigene Fassung\n")
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "eigener Starter")
    template = _template(kit, "sak")
    template.write_text(
        template.read_text(encoding="utf-8") + "# neu\n", encoding="utf-8", newline="\n"
    )
    bump_version(kit, "0.4.0")
    code, plan = sak("upgrade", str(target), "--no-sync", "--apply")
    assert code == 0
    assert {a["path"]: a["action"] for a in plan["actions"]}[SH] == "conflict"
    assert "eigene Fassung" in (target / SH).read_text(encoding="utf-8")
    assert (target / (SH + ".sak-new")).is_file()


def test_deleted_launcher_is_restored_by_upgrade(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    (target / CMD).unlink()
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "ohne cmd")
    code, plan = sak("upgrade", str(target), "--no-sync", "--apply")
    assert code == 0 and (target / CMD).is_file()
    assert {a["path"]: a["action"] for a in plan["actions"]}[CMD] == "create"


@pytest.mark.skipif(os.name == "nt", reason="Ausführbar-Bit gibt es unter Windows nicht")
def test_sh_launcher_is_executable_after_init_and_after_upgrade(
    kit: Kit, target: Path, sak: Sak, init_args: list[str]
) -> None:
    _installed(sak, init_args, target)
    assert (target / SH).stat().st_mode & stat.S_IXUSR
    (target / SH).chmod(0o644)
    sak("upgrade", str(target), "--no-sync", "--apply", "--allow-dirty")
    assert (target / SH).stat().st_mode & stat.S_IXUSR


@pytest.mark.skipif(os.name == "nt", reason="Ausführbar-Bit gibt es unter Windows nicht")
def test_ensure_launcher_mode_sets_the_bit(tmp_path: Path) -> None:
    write(tmp_path, SH, "#!/bin/sh\n")
    (tmp_path / SH).chmod(0o600)
    ensure_launcher_mode(tmp_path)
    assert (tmp_path / SH).stat().st_mode & 0o111 == 0o111


def test_ensure_launcher_mode_tolerates_a_missing_launcher(tmp_path: Path) -> None:
    ensure_launcher_mode(tmp_path)
