"""Starter ``sak.cmd`` und ``sak`` laufen wirklich (Spec 009 US1, A03).

Gegen Wegwerf-Ordner in ``tmp_path``; die Engine wird nur gelesen. Die Windows-Tests brauchen ein
echtes ``uv`` (SAK_UV, PATH oder WinGet) und eine NTFS-Junction auf die Engine; sonst Skip.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from spec_agent_kit import __version__

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "packages" / "agent-blueprint" / "templates" / "spec-agent"
ENGINE = REPO / "packages" / "engine"
IS_WINDOWS = os.name == "nt"


def _real_uv() -> str | None:
    found = os.environ.get("SAK_UV") or shutil.which("uv")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    if local:
        winget = Path(local) / "Microsoft" / "WinGet"
        if (winget / "Links" / "uv.exe").is_file():
            return str(winget / "Links" / "uv.exe")
        for package in sorted((winget / "Packages").glob("astral-sh.uv_*")):
            if (package / "uv.exe").is_file():
                return str(package / "uv.exe")
    return None


def _crlf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


_JUNCTIONS: list[Path] = []


@pytest.fixture(autouse=True)
def _remove_junctions() -> Iterator[None]:
    """Junctions werden vor dem Aufräumen von ``tmp_path`` entfernt (nie dem Link folgen)."""
    yield
    while _JUNCTIONS:
        with contextlib.suppress(OSError):
            os.rmdir(_JUNCTIONS.pop())


def _make_cmd_home(base: Path, *, link_engine: bool) -> Path:
    """``<base>/proj/.spec-agent/sak.cmd`` (CRLF wie nach der Installation), optional Junction."""
    folder = base / "proj" / ".spec-agent"
    folder.mkdir(parents=True)
    (folder / "sak.cmd").write_bytes(_crlf((TEMPLATES / "sak.cmd").read_bytes()))
    if link_engine:
        made = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(folder / "engine"), str(ENGINE)],
            capture_output=True,
            check=False,
        )
        if made.returncode != 0:
            pytest.skip("Junction nicht anlegbar")
        _JUNCTIONS.append(folder / "engine")
    return folder


def _cmd_env(tmp_path: Path, **extra: str) -> dict[str, str]:
    """Leerer PATH (nur System32), leere Benutzerordner: nichts Bekanntes wird gefunden."""
    system = os.environ.get("SYSTEMROOT", r"C:\Windows")
    home = tmp_path / "home"
    (home / "local").mkdir(parents=True, exist_ok=True)
    env = {
        "SystemRoot": system,
        "PATH": str(Path(system) / "System32"),
        "LOCALAPPDATA": str(home / "local"),
        "USERPROFILE": str(home),
        "TEMP": str(tmp_path),
        "TMP": str(tmp_path),
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR", str(Path.home() / "AppData/Local/uv/cache")),
    }
    for name in ("APPDATA", "HOMEDRIVE", "HOMEPATH"):
        if name in os.environ:
            env[name] = os.environ[name]
    env.update(extra)
    return env


def _run_cmd(folder: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["cmd", "/c", str(folder / "sak.cmd"), *args],
        cwd=folder.parent,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )


# ---------------------------------------------------------------------------------- Windows

windows_only = pytest.mark.skipif(not IS_WINDOWS, reason="sak.cmd läuft nur unter Windows")


@windows_only
def test_cmd_runs_version_via_sak_uv_with_an_empty_path(tmp_path: Path) -> None:
    uv = _real_uv()
    if uv is None:
        pytest.skip("kein uv gefunden")
    folder = _make_cmd_home(tmp_path, link_engine=True)
    result = _run_cmd(folder, _cmd_env(tmp_path, SAK_UV=uv), "version")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"version": __version__}


@windows_only
def test_cmd_finds_uv_in_the_winget_packages_folder(tmp_path: Path) -> None:
    uv = _real_uv()
    if uv is None:
        pytest.skip("kein uv gefunden")
    folder = _make_cmd_home(tmp_path, link_engine=True)
    env = _cmd_env(tmp_path)
    package = Path(env["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Packages" / "astral-sh.uv_x"
    package.mkdir(parents=True)
    shutil.copy2(uv, package / "uv.exe")
    result = _run_cmd(folder, env, "version")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"version": __version__}


@windows_only
def test_cmd_passes_the_exit_code_through(tmp_path: Path) -> None:
    uv = _real_uv()
    if uv is None:
        pytest.skip("kein uv gefunden")
    folder = _make_cmd_home(tmp_path, link_engine=True)
    env = _cmd_env(tmp_path, SAK_UV=uv)
    assert _run_cmd(folder, env, "version").returncode == 0
    assert _run_cmd(folder, env, "config", "check").returncode == 1  # nicht initialisiert
    assert _run_cmd(folder, env, "gibt-es-nicht").returncode == 2  # Bedienfehler


@windows_only
def test_cmd_without_uv_exits_127_with_the_winget_hint(tmp_path: Path) -> None:
    folder = _make_cmd_home(tmp_path, link_engine=False)
    result = _run_cmd(folder, _cmd_env(tmp_path), "version")
    assert result.returncode == 127
    assert "winget install --id astral-sh.uv -e" in result.stderr
    assert result.stdout == ""


@windows_only
def test_cmd_with_a_broken_sak_uv_exits_127(tmp_path: Path) -> None:
    folder = _make_cmd_home(tmp_path, link_engine=False)
    result = _run_cmd(folder, _cmd_env(tmp_path, SAK_UV=str(tmp_path / "nichts.exe")), "version")
    assert result.returncode == 127 and "SAK_UV" in result.stderr


@windows_only
def test_cmd_handles_a_folder_with_spaces_and_parentheses(tmp_path: Path) -> None:
    uv = _real_uv()
    if uv is None:
        pytest.skip("kein uv gefunden")
    spaced = tmp_path / "Mein Projekt (neu)"
    spaced.mkdir()
    folder = _make_cmd_home(spaced, link_engine=True)
    result = _run_cmd(folder, _cmd_env(tmp_path, SAK_UV=uv), "version")
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------------- POSIX


def _sh() -> str | None:
    return shutil.which("sh")


posix_sh = pytest.mark.skipif(_sh() is None, reason="kein sh vorhanden")


def _make_sh_home(tmp_path: Path) -> Path:
    folder = tmp_path / "proj" / ".spec-agent"
    folder.mkdir(parents=True)
    (folder / "sak").write_bytes((TEMPLATES / "sak").read_bytes().replace(b"\r\n", b"\n"))
    return folder


def _fake_uv(path: Path, code: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = '#!/bin/sh\necho "uv: $*"\nexit ' + str(code) + "\n"
    path.write_bytes(body.encode())
    path.chmod(0o755)


def _sh_env(tmp_path: Path, **extra: str) -> dict[str, str]:
    sh = _sh()
    assert sh is not None
    env = {"HOME": (tmp_path / "home").as_posix(), "PATH": str(Path(sh).parent)}
    if IS_WINDOWS:
        env["SystemRoot"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    env.update(extra)
    return env


def _run_sh(folder: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_sh()), (folder / "sak").as_posix(), *args],
        cwd=folder.parent,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )


@posix_sh
def test_sh_uses_sak_uv_first_and_passes_args_and_exit_code(tmp_path: Path) -> None:
    folder = _make_sh_home(tmp_path)
    fake = tmp_path / "bin" / "meinuv"
    _fake_uv(fake, 7)
    result = _run_sh(folder, _sh_env(tmp_path, SAK_UV=fake.as_posix()), "board", "serve", "a b")
    assert result.returncode == 7, result.stderr
    assert "uv: run --project" in result.stdout
    assert "/engine sak board serve a b" in result.stdout


@posix_sh
def test_sh_finds_uv_in_a_known_place(tmp_path: Path) -> None:
    folder = _make_sh_home(tmp_path)
    _fake_uv(tmp_path / "home" / ".local" / "bin" / "uv", 3)
    result = _run_sh(folder, _sh_env(tmp_path), "version")
    assert result.returncode == 3, result.stderr
    assert "uv: run --project" in result.stdout


@posix_sh
def test_sh_prefers_path_over_known_places(tmp_path: Path) -> None:
    folder = _make_sh_home(tmp_path)
    _fake_uv(tmp_path / "home" / ".local" / "bin" / "uv", 3)
    _fake_uv(tmp_path / "pathbin" / "uv", 4)
    env = _sh_env(tmp_path)
    env["PATH"] = (tmp_path / "pathbin").as_posix() + os.pathsep + env["PATH"]
    assert _run_sh(folder, env, "version").returncode == 4


@posix_sh
def test_sh_without_uv_exits_127_with_the_install_hint(tmp_path: Path) -> None:
    folder = _make_sh_home(tmp_path)
    result = _run_sh(folder, _sh_env(tmp_path), "version")
    if "uv: " in result.stdout:
        pytest.skip("uv liegt an einem festen Ort dieses Rechners")
    assert result.returncode == 127
    assert "curl -LsSf https://astral.sh/uv/install.sh | sh" in result.stderr


@posix_sh
def test_sh_with_a_broken_sak_uv_exits_127(tmp_path: Path) -> None:
    folder = _make_sh_home(tmp_path)
    result = _run_sh(folder, _sh_env(tmp_path, SAK_UV=str(tmp_path / "nichts")), "version")
    assert result.returncode == 127 and "SAK_UV" in result.stderr


# ---------------------------------------------------------------------------------- Vorlagen


def test_launcher_templates_name_all_lookup_places() -> None:
    cmd = (TEMPLATES / "sak.cmd").read_text(encoding="utf-8")
    for fragment in (
        "SAK_UV",
        r"WinGet\Links\uv.exe",
        r"WinGet\Packages\astral-sh.uv_*",
        r"\.local\bin\uv.exe",
        r"\.cargo\bin\uv.exe",
        "exit /b 127",
        "winget install --id astral-sh.uv -e",
    ):
        assert fragment in cmd
    sh = (TEMPLATES / "sak").read_text(encoding="utf-8")
    for fragment in (
        "SAK_UV",
        "$HOME/.local/bin/uv",
        "$HOME/.cargo/bin/uv",
        "/opt/homebrew/bin/uv",
        "/usr/local/bin/uv",
        "exit 127",
        "curl -LsSf https://astral.sh/uv/install.sh | sh",
    ):
        assert fragment in sh
    assert sh.startswith("#!/bin/sh\n") and "\r" not in sh
