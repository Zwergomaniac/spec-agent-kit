"""Das Kit-Repo als Quelle: Wurzel, Version und verwaltete Dateien (Spec 005 FR-003)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from spec_agent_kit.install import InstallError

TEMPLATES_RELATIVE: Final[str] = "packages/agent-blueprint/templates"
ENGINE_RELATIVE: Final[str] = "packages/engine"
ENGINE_TARGET: Final[str] = ".spec-agent/engine"
GITIGNORE_TARGET: Final[str] = ".spec-agent/.gitignore"
LAUNCHER_CMD_TARGET: Final[str] = ".spec-agent/sak.cmd"
LAUNCHER_SH_TARGET: Final[str] = ".spec-agent/sak"
LOCK_TARGET: Final[str] = ".spec-agent/lock.json"
CONFIG_TARGET: Final[str] = ".spec-agent/config.yml"
SETTINGS_TARGET: Final[str] = ".claude/settings.json"

_IGNORED_DIRS: Final[frozenset[str]] = frozenset(
    {".venv", "__pycache__", ".ruff_cache", ".pytest_cache", ".mypy_cache", "node_modules"}
)
_IGNORED_SUFFIXES: Final[tuple[str, ...]] = (".pyc", ".pyo")
_VERSION_RE = re.compile(r"""^__version__\s*=\s*["']([^"']+)["']""", re.MULTILINE)
_NUMERIC_VERSION = re.compile(r"^([0-9]+)[.]([0-9]+)[.]([0-9]+)")


def kit_root() -> Path | None:
    """Wurzel des Kit-Repos, abgeleitet vom Pfad dieses Pakets; ``None``, wenn es keins gibt.

    ``packages/engine/src/spec_agent_kit/install/kit.py`` liegt fünf Ebenen unter der Wurzel. In der
    vendorten Kopie im Zielprojekt fehlt ``packages/agent-blueprint/templates``: dann ``None``.
    """
    candidate = Path(__file__).resolve().parents[5]
    if (candidate / TEMPLATES_RELATIVE).is_dir() and (candidate / ENGINE_RELATIVE).is_dir():
        return candidate
    return None


def sha256_of(data: bytes) -> str:
    """SHA-256; Zeilenenden werden bei Textdateien auf LF normalisiert (autocrlf-fest)."""
    if b"\0" not in data:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def version_tuple(version: str) -> tuple[int, int, int]:
    """``1.2.3`` oder ``1.2.3-rc.1`` -> ``(1, 2, 3)``."""
    match = _NUMERIC_VERSION.match(version)
    if match is None:
        raise ValueError(f"keine Version: {version}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _skipped(relative: Path) -> bool:
    if any(part in _IGNORED_DIRS or part.endswith(".egg-info") for part in relative.parts):
        return True
    return relative.suffix in _IGNORED_SUFFIXES


@dataclass(frozen=True)
class Kit:
    """Ein Kit-Checkout. ``version`` steht in ``packages/engine/src/spec_agent_kit/__init__.py``."""

    root: Path
    version: str

    @classmethod
    def at(cls, root: Path) -> Kit:
        init = root / ENGINE_RELATIVE / "src" / "spec_agent_kit" / "__init__.py"
        if not (root / TEMPLATES_RELATIVE).is_dir() or not init.is_file():
            raise InstallError.single(
                "<kit>", f"{root} ist kein Kit-Repo (Vorlagen oder Engine fehlen)"
            )
        match = _VERSION_RE.search(init.read_text(encoding="utf-8"))
        if match is None:
            raise InstallError.single("<kit>", f"keine __version__ in {init}")
        return cls(root=root, version=match.group(1))

    @property
    def templates(self) -> Path:
        return self.root / TEMPLATES_RELATIVE

    @property
    def engine(self) -> Path:
        return self.root / ENGINE_RELATIVE

    def settings_fragment(self) -> bytes:
        return (self.templates / "claude" / "settings.fragment.json").read_bytes()

    def config_template(self) -> str:
        return (self.templates / "config" / "config.yml").read_text(encoding="utf-8")

    def managed_files(self) -> dict[str, Path]:
        """Zielpfad (POSIX, relativ zum Zielprojekt) -> Quelldatei, sortiert nach Zielpfad.

        ``config.yml`` und ``settings.json`` gehören nicht dazu (Seed bzw. Merge).
        """
        files: dict[str, Path] = {}
        claude = self.templates / "claude"
        for sub in ("agents", "skills"):
            base = claude / sub
            if base.is_dir():
                for path in sorted(p for p in base.rglob("*") if p.is_file()):
                    files[f".claude/{sub}/{path.relative_to(base).as_posix()}"] = path
        for path in sorted(p for p in self.engine.rglob("*") if p.is_file()):
            relative = path.relative_to(self.engine)
            if relative.parts[0] == "tests" or _skipped(relative):
                continue
            files[f"{ENGINE_TARGET}/{relative.as_posix()}"] = path
        gitignore = self.templates / "spec-agent" / "gitignore"
        if gitignore.is_file():
            files[GITIGNORE_TARGET] = gitignore
        for name, target in (("sak.cmd", LAUNCHER_CMD_TARGET), ("sak", LAUNCHER_SH_TARGET)):
            launcher = self.templates / "spec-agent" / name
            if launcher.is_file():
                files[target] = launcher
        return dict(sorted(files.items()))


def locate_kit() -> Kit:
    """Das Kit des laufenden Prozesses; lehnt in der vendorten Kopie ab."""
    root = kit_root()
    if root is None:
        raise InstallError.single(
            "<kit>",
            "init und upgrade sind hier deaktiviert: aus dem Kit-Repo aufrufen "
            "(uv run --project packages/engine sak …)",
        )
    return Kit.at(root)
