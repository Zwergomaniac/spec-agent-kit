"""Git-Zugriff der Pipeline. Aufrufe laufen nur über eine Argumentliste, nie über eine Shell."""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

from spec_agent_kit.pipeline import RefusedError

_GIT = ["git", "-c", "core.quotepath=false"]


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Führt ``git <args>`` in ``root`` aus. Wirft nie wegen eines Exit-Codes."""
    try:
        return subprocess.run(
            [*_GIT, *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except OSError as exc:
        raise RefusedError(f"git ist nicht aufrufbar: {exc}") from exc


PUSH_TIMEOUT_S = 60
"""Zeitlimit für ``push_branch`` (Spec 012 FR-003)."""

_CREDENTIALS = re.compile(r"(://)[^/@\s]+@")


def redact(text: str) -> str:
    """Entfernt Zugangsdaten aus URLs (``https://user:token@host`` wird ``https://***@host``)."""
    return _CREDENTIALS.sub(r"\1***@", text)


def remotes(root: Path) -> list[str]:
    return git(root, "remote").split()


def push_branch(root: Path, remote: str, branch: str) -> subprocess.CompletedProcess[str]:
    """``git push <remote> <branch>:<branch>``: nie mit Force, nie mit Tags, nie mit Rückfrage.

    ``push.followTags`` wird ausgeschaltet, damit auch eine Nutzerkonfiguration keine Tags mitnimmt.
    Bei Zeitüberschreitung ist ``returncode`` 124 und ``stderr`` enthält den Grund.
    """
    refspec = f"{branch}:{branch}"
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        return subprocess.run(
            [*_GIT, "-c", "push.followTags=false", "push", remote, refspec],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            env=env,
            timeout=PUSH_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        message = f"Zeitüberschreitung nach {PUSH_TIMEOUT_S} s"
        return subprocess.CompletedProcess([], 124, "", message)
    except OSError as exc:
        raise RefusedError(f"git ist nicht aufrufbar: {exc}") from exc


def git(root: Path, *args: str) -> str:
    """Stdout von ``git <args>``; bei Exit ≠ 0 folgt eine Ablehnung mit der Git-Meldung."""
    proc = run_git(root, *args)
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout).strip()
        raise RefusedError(f"git {' '.join(args)} ist fehlgeschlagen: {message}")
    return proc.stdout


def current_branch(root: Path) -> str:
    """Name des ausgecheckten Branches, leer bei losgelöstem HEAD."""
    return git(root, "branch", "--show-current").strip()


def head(root: Path) -> str:
    return git(root, "rev-parse", "HEAD").strip()


def resolve_commit(root: Path, ref: str) -> str | None:
    """Vollständiger SHA eines Commits oder ``None``."""
    proc = run_git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    sha = proc.stdout.strip()
    return sha if proc.returncode == 0 and sha else None


def branch_exists(root: Path, branch: str) -> bool:
    return run_git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0


def is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return run_git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def matches(path: str, pattern: str) -> bool:
    """Pfad gegen ein Muster: Verzeichnis-Präfix (``a/``), Glob (``a/sak-*``) oder exakter Pfad."""
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if any(ch in pattern for ch in "*?["):
        return fnmatch.fnmatchcase(path, pattern)
    return path == pattern or path.startswith(pattern + "/")


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(matches(path, p) for p in patterns)


def dirty_files(root: Path, clean_ignore: Iterable[str]) -> list[str]:
    """Geänderte und unversionierte Dateien, ohne ``clean_ignore``. Sortiert, mit ``/``."""
    out = git(root, "status", "--porcelain", "-z", "-uall")
    records = out.split("\0")
    ignore = list(clean_ignore)
    files: set[str] = set()
    i = 0
    while i < len(records):
        record = records[i]
        i += 1
        if len(record) < 4:
            continue
        status, path = record[:2], record[3:]
        if "R" in status or "C" in status:
            i += 1  # Der Ursprungspfad folgt als eigener Eintrag.
        path = path.replace("\\", "/")
        if not matches_any(path, ignore):
            files.add(path)
    return sorted(files)


def changed_since(root: Path, base_commit: str, clean_ignore: Iterable[str]) -> list[str]:
    """Pfade aus ``base_commit..HEAD`` und dem Arbeitsstand, ohne ``clean_ignore``."""
    ignore = list(clean_ignore)
    committed = git(root, "diff", "--name-only", "-z", f"{base_commit}..HEAD").split("\0")
    paths = {p.replace("\\", "/") for p in committed if p}
    paths.update(dirty_files(root, ignore))
    return sorted(p for p in paths if not matches_any(p, ignore))


def exclude_specs(patterns: Iterable[str]) -> list[str]:
    """Git-Pathspecs, die ``patterns`` aus einem ``git diff`` ausnehmen."""
    specs: list[str] = []
    for pattern in patterns:
        if any(ch in pattern for ch in "*?["):
            specs.append(f":(exclude,glob){pattern}")
        else:
            specs.append(f":(exclude){pattern.rstrip('/')}")
    return specs


def _self_ignoring(directory: Path) -> bool:
    """Werkzeug-Caches (``.pytest_cache`` u. a.) haben eine eigene ``.gitignore`` mit ``*``."""
    try:
        lines = (directory / ".gitignore").read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    return any(line.strip() == "*" for line in lines)


def new_top_level_dirs(root: Path, clean_ignore: Iterable[str]) -> list[str]:
    """Top-Level-Ordner, die ``git status`` nicht sicher sieht (zum Beispiel leere Ordner).

    Nicht gezählt werden ``.git``, Ordner aus ``clean_ignore``, von Git ignorierte Ordner und
    sich selbst ignorierende Werkzeug-Caches. Der Prüfer-Snapshot hält die Liste fest, damit ein
    Prüfer, der versehentlich Ordner anlegt (etwa durch einen Pfad mit Leerzeichen ohne
    Anführungszeichen), auffällt (Spec 011 B14).
    """
    ignore = list(clean_ignore)
    try:
        names = sorted(
            e.name for e in os.scandir(root) if e.name != ".git" and e.is_dir(follow_symlinks=True)
        )
    except OSError:
        return []
    names = [n for n in names if not matches_any(f"{n}/", ignore)]
    names = [n for n in names if not _self_ignoring(root / n)]
    if not names:
        return []
    try:
        proc = subprocess.run(
            [*_GIT, "check-ignore", "-z", "--stdin"],
            cwd=root,
            input="\x00".join(f"{n}/" for n in names) + "\x00",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return names
    ignored = {p.rstrip("/") for p in proc.stdout.split("\x00") if p}
    return [n for n in names if n not in ignored]
