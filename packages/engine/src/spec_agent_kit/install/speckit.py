"""spec-kit im Zielprojekt erkennen (Spec 005 FR-002)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

from spec_agent_kit.install import InstallError

INIT_OPTIONS: Final[str] = ".specify/init-options.json"
MIN_VERSION: Final[tuple[int, int, int]] = (0, 12, 0)
INIT_COMMAND: Final[str] = "specify init --here --integration claude"
_VERSION = re.compile(r"^v?([0-9]+)[.]([0-9]+)(?:[.]([0-9]+))?")


def parse_version(text: str) -> tuple[int, int, int] | None:
    match = _VERSION.match(text.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)


def detect_version(root: Path) -> str:
    """Liest ``speckit_version`` aus ``.specify/init-options.json`` und prüft die Mindestversion."""
    path = root / INIT_OPTIONS
    hint = f"spec-kit zuerst einrichten: {INIT_COMMAND}"
    if not path.is_file():
        raise InstallError.single(INIT_OPTIONS, f"spec-kit fehlt ({INIT_OPTIONS}). {hint}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallError.single(INIT_OPTIONS, f"nicht lesbar: {exc}. {hint}") from exc
    raw = data.get("speckit_version") if isinstance(data, dict) else None
    parsed = parse_version(raw) if isinstance(raw, str) else None
    minimum = ".".join(map(str, MIN_VERSION))
    if parsed is None:
        raise InstallError.single(INIT_OPTIONS, f"keine spec-kit-Version erkennbar. {hint}")
    if parsed < MIN_VERSION:
        raise InstallError.single(
            INIT_OPTIONS, f"spec-kit {raw} ist zu alt (mindestens {minimum}). {hint}"
        )
    return str(raw)
