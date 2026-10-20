"""Git-Zugriff der Pipeline. Aufrufe laufen nur über eine Argumentliste, nie über eine Shell."""

from __future__ import annotations

import fnmatch
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
