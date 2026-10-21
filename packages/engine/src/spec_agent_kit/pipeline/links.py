"""Links und Junctions unter einem Lauf-Ordner entfernen, ohne ihnen zu folgen (Spec 011 B14).

Ein UI-Prüfer kann unter ``.spec-agent/state/runs/<id>/`` eine Junction oder einen Symlink anlegen
(zum Beispiel auf ``node_modules``). Löscht man den Ordner rekursiv oder entfernt man den
Worktree, würde ein Link zum Ziel führen oder die Aktion blockieren. Dieses Modul entfernt nur
den Link selbst; das Ziel bleibt unberührt.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

_LINK_TAGS = frozenset(
    {
        getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C),
        getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003),
    }
)


def is_link(path: Path | str) -> bool:
    """``True`` für einen Symlink oder (unter Windows) eine Junction. Folgt dem Link nie."""
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return getattr(info, "st_reparse_tag", 0) in _LINK_TAGS
    return False


def _remove_link(path: Path) -> None:
    """Entfernt nur den Link. Ein Verzeichnis-Link braucht unter Windows ``rmdir``."""
    try:
        os.unlink(path)
    except OSError:
        os.rmdir(path)


def remove_links(directory: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Entfernt alle Links unter ``directory``. Gibt ``(entfernt, fehlgeschlagen)`` zurück.

    Das Verzeichnis selbst darf kein Link sein (dann wird nichts getan und der Aufrufer meldet es).
    Reguläre Verzeichnisse werden durchsucht, Links werden nie betreten.
    """
    removed: list[Path] = []
    failed: list[tuple[Path, str]] = []
    if is_link(directory) or not directory.is_dir():
        return removed, failed
    pending = [directory]
    while pending:
        current = pending.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name)
        except OSError as exc:
            failed.append((current, exc.strerror or str(exc)))
            continue
        for entry in entries:
            path = Path(entry.path)
            if is_link(path):
                try:
                    _remove_link(path)
                    removed.append(path)
                except OSError as exc:
                    failed.append((path, exc.strerror or str(exc)))
            elif entry.is_dir(follow_symlinks=False):
                pending.append(path)
    return removed, failed
