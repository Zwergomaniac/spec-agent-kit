"""Erkennung verknüpfter Git-Worktrees (Spec 011 US3).

Ein Worktree hat statt eines ``.git``-Ordners eine ``.git``-Datei (``gitdir: <Pfad>``). Der Eintrag
unter ``<haupt>/.git/worktrees/<name>`` verweist über die Datei ``commondir`` auf das gemeinsame
Git-Verzeichnis. Das Lesen dieser Dateien braucht keinen Git-Aufruf; die Engine fragt sie bei jedem
Laden der Config ab, auch in den Hooks.
"""

from __future__ import annotations

import os
from pathlib import Path


def _read_first_line(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (OSError, UnicodeDecodeError, IndexError):
        return None


def main_checkout(root: Path) -> Path | None:
    """Der Haupt-Checkout, wenn ``root`` ein verknüpfter Worktree ist, sonst ``None``.

    Ein Submodul hat ebenfalls eine ``.git``-Datei, aber keine ``commondir``-Datei und gilt nicht
    als Worktree. Ein Haupt-Checkout (``.git`` ist ein Ordner) ergibt ebenfalls ``None``.
    """
    dotgit = root / ".git"
    if not dotgit.is_file():
        return None
    line = _read_first_line(dotgit)
    if line is None or not line.startswith("gitdir:"):
        return None
    gitdir = Path(line[len("gitdir:") :].strip())
    if not gitdir.is_absolute():
        gitdir = root / gitdir
    pointer = _read_first_line(gitdir / "commondir")
    if pointer is None:
        return None
    common = Path(os.path.normpath(gitdir / pointer))
    if common.name != ".git" or not common.is_dir():
        return None  # bare-Repository: es gibt keinen Haupt-Checkout
    main = common.parent
    try:
        if main.samefile(root):
            return None
    except OSError:
        return None
    return main


def same_directory(first: Path | str, second: Path | str) -> bool:
    """Gleiches Verzeichnis? Ohne vorhandenen Pfad entscheidet der normalisierte Text."""
    try:
        return os.path.samefile(first, second)
    except OSError:
        return os.path.normcase(os.path.normpath(first)) == os.path.normcase(
            os.path.normpath(second)
        )
