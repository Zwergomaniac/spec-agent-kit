"""Lockfile ``.spec-agent/lock.json`` (``sak.lock/1``, Spec 005 FR-004)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from spec_agent_kit import contracts
from spec_agent_kit.install import InstallError
from spec_agent_kit.install.kit import LOCK_TARGET

SCHEMA_ID: Final[str] = "sak.lock/1"


@dataclass
class Lock:
    kit_version: str
    installed_at: str
    upgraded_at: str | None
    files: dict[str, str] = field(default_factory=dict)
    settings_fragment_hash: str = ""
    settings_allow: list[str] | None = None
    """Vom Kit eingetragene allow-Regeln (Spec 011 B13); ``None`` bei einem Lock vor 0.2.0."""

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema": SCHEMA_ID,
            "kit_version": self.kit_version,
            "installed_at": self.installed_at,
            "upgraded_at": self.upgraded_at,
            "files": dict(sorted(self.files.items())),
            "settings_fragment_hash": self.settings_fragment_hash,
        }
        if self.settings_allow is not None:
            data["settings_allow"] = list(self.settings_allow)
        return data

    def dumps(self) -> bytes:
        text = json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"
        return text.encode("utf-8")


def lock_path(root: Path) -> Path:
    return root / LOCK_TARGET


def read_lock(root: Path) -> Lock | None:
    """Liest das Lockfile. ``None``, wenn es fehlt; ``InstallError``, wenn es ungültig ist."""
    path = lock_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallError.single(LOCK_TARGET, f"Lockfile nicht lesbar: {exc}") from exc
    errors = contracts.validate_lock(data)
    if errors:
        raise InstallError.single(LOCK_TARGET, f"Lockfile ungültig: {errors[0]}")
    return Lock(
        kit_version=data["kit_version"],
        installed_at=data["installed_at"],
        upgraded_at=data["upgraded_at"],
        files=dict(data["files"]),
        settings_fragment_hash=data["settings_fragment_hash"],
        settings_allow=list(data["settings_allow"]) if "settings_allow" in data else None,
    )
