"""Das Kit-Repo als Quelle: Wurzel, Version und verwaltete Dateien (Spec 005 FR-003)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from spec_agent_kit.agent_env import get_agent_environment
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

    def settings_fragment(self, environment: str = "claude") -> bytes:
        spec = get_agent_environment(environment)
        if spec.name == "claude":
            return (self.templates / "claude" / "settings.fragment.json").read_bytes()
        return (self.templates / "copilot" / "settings.json").read_bytes()

    def detectors(self) -> list[dict[str, Any]]:
        """Regeln zur Erkennung von Testwerkzeugen mit Ausgabeordnern (``detectors.json``)."""
        path = self.templates / "config" / "detectors.json"
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        rules = loaded.get("artifact_tools") if isinstance(loaded, dict) else None
        return (
            [r for r in rules if isinstance(r, dict) and "id" in r]
            if isinstance(rules, list)
            else []
        )

    def config_template(self) -> str:
        return (self.templates / "config" / "config.yml").read_text(encoding="utf-8")

    def managed_files(self, environment: str = "claude") -> dict[str, Path]:
        """Zielpfad (POSIX, relativ zum Zielprojekt) -> Quelldatei, sortiert nach Zielpfad.

        ``config.yml`` und ``settings.json`` gehören nicht dazu (Seed bzw. Merge).
        """
        files: dict[str, Path] = {}
        spec = get_agent_environment(environment)
        template_root = self.templates / spec.name
        for sub in ("agents", "skills"):
            base = template_root / sub
            if base.is_dir():
                for path in sorted(p for p in base.rglob("*") if p.is_file()):
                    target_base = spec.agent_dir if sub == "agents" else spec.skills_dir
                    files[f"{target_base}/{path.relative_to(base).as_posix()}"] = path
        if spec.instructions_path is not None:
            instructions = template_root / "instructions.md"
            if instructions.is_file():
                files[spec.instructions_path] = instructions
        if spec.name == "copilot":
            settings = template_root / "settings.json"
            tasks = template_root / "tasks.json"
            if settings.is_file():
                files[spec.settings_path] = settings
            if tasks.is_file():
                files[spec.hook_target_path] = tasks
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
