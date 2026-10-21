"""Suche nach ``uv`` und ``sh`` an bekannten Orten (Spec 011 B12).

Der Starter ``.spec-agent/sak`` sucht uv selbst. ``doctor`` braucht dieselbe Suche, und die
Hook-Probe braucht eine POSIX-Shell, auch wenn ``sak.cmd`` aus PowerShell oder cmd läuft und
Git-Bash nicht im PATH liegt.
"""

from __future__ import annotations

import glob
import os
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

Which = Callable[[str], str | None]


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _git_roots(env: Mapping[str, str], which: Which) -> list[Path]:
    """Mögliche Git-for-Windows-Installationen: bekannte Orte und das Umfeld von ``git.exe``."""
    roots: list[Path] = []
    for name in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        if env.get(name):
            roots.append(Path(env[name]) / "Git")
    if env.get("LOCALAPPDATA"):
        roots.append(Path(env["LOCALAPPDATA"]) / "Programs" / "Git")
    git = which("git")
    if git:
        for parent in Path(git).resolve().parents[:3]:  # …/Git/cmd/git.exe -> …/Git
            roots.append(parent)
    return list(dict.fromkeys(roots))


def find_sh(
    env: Mapping[str, str] | None = None,
    which: Which = shutil.which,
    windows: bool | None = None,
) -> str | None:
    """Pfad einer POSIX-Shell: PATH zuerst, unter Windows danach die Orte von Git for Windows."""
    found = which("sh")
    if found:
        return found
    if windows is None:
        windows = os.name == "nt"
    if not windows:
        return None
    environment = os.environ if env is None else env
    for root in _git_roots(environment, which):
        for relative in ("usr/bin/sh.exe", "bin/sh.exe"):
            candidate = root / relative
            if _is_file(candidate):
                return str(candidate)
    return None


def find_uv(
    env: Mapping[str, str] | None = None,
    which: Which = shutil.which,
    windows: bool | None = None,
) -> str | None:
    """Pfad von uv wie im Starter: ``SAK_UV``, ``UV``, PATH, dann bekannte Orte."""
    environment = os.environ if env is None else env
    for name in ("SAK_UV", "UV"):
        value = environment.get(name, "").strip()
        if value and _is_file(Path(value)):
            return value
    found = which("uv")
    if found:
        return found
    if windows is None:
        windows = os.name == "nt"
    candidates: list[Path] = []
    local = environment.get("LOCALAPPDATA", "")
    if windows and local:
        winget = Path(local) / "Microsoft" / "WinGet"
        candidates.append(winget / "Links" / "uv.exe")
        candidates.extend(
            Path(p)
            for p in sorted(glob.glob(str(winget / "Packages" / "astral-sh.uv_*" / "uv.exe")))
        )
    home = environment.get("USERPROFILE") or environment.get("HOME") or ""
    if home:
        suffix = ".exe" if windows else ""
        candidates.append(Path(home) / ".local" / "bin" / f"uv{suffix}")
        candidates.append(Path(home) / ".cargo" / "bin" / f"uv{suffix}")
    if not windows:
        candidates.extend(Path(p) for p in ("/opt/homebrew/bin/uv", "/usr/local/bin/uv"))
    for candidate in candidates:
        if _is_file(candidate):
            return str(candidate)
    return None
