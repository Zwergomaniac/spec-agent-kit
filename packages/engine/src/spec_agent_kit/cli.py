"""Kommandozeile `sak`.

Konventionen (docs/architecture.md): JSON auf stdout; Exit 0 bei Erfolg,
1 bei fachlicher Ablehnung, 2 bei Bedienfehlern.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from spec_agent_kit import __version__
from spec_agent_kit.config import ConfigError, NotInitializedError, load_config
from spec_agent_kit.config.check import check as check_config

EXIT_OK = 0
EXIT_REJECTED = 1
EXIT_USAGE = 2


def _force_utf8() -> None:
    """Stellt stdout und stderr unabhängig von der Konsolen-Codepage auf UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def find_root(start: Path | None = None) -> Path | None:
    """Projektwurzel: das nächste Verzeichnis aufwärts mit ``.spec-agent/``, sonst das Git-Toplevel.

    Gibt ``None`` zurück, wenn beides fehlt.
    """
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".spec-agent").is_dir():
            return candidate
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=here,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    top = result.stdout.strip()
    return Path(top) if result.returncode == 0 and top else None


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _reject(errors: list[dict[str, str]]) -> int:
    _emit({"ok": False, "errors": errors, "warnings": []})
    return EXIT_REJECTED


def _not_initialized() -> int:
    return _reject(
        [{"path": "<root>", "message": "nicht initialisiert: .spec-agent/config.yml fehlt"}]
    )


def _config_show() -> int:
    root = find_root()
    if root is None:
        return _not_initialized()
    try:
        effective = load_config(root)
    except NotInitializedError:
        return _not_initialized()
    except ConfigError as exc:
        return _reject(exc.errors)
    _emit(effective.to_dict())
    return EXIT_OK


def _config_check() -> int:
    root = find_root()
    if root is None:
        return _not_initialized()
    result = check_config(root)
    _emit(result)
    return EXIT_OK if result["ok"] else EXIT_REJECTED


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sak", description="Spec Agent Kit")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="Gibt die Kit-Version als JSON aus")
    config = sub.add_parser("config", help="Projektkonfiguration (.spec-agent/config.yml)")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("check", help="Prüft die Konfiguration (Schema, Agents, Frontmatter)")
    config_sub.add_parser("show", help="Gibt die wirksame Konfiguration als JSON aus")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Einstiegspunkt. Gibt den Exit-Code zurück."""
    _force_utf8()
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    if args.command == "version":
        sys.stdout.write(json.dumps({"version": __version__}, ensure_ascii=False) + "\n")
        return EXIT_OK
    if args.command == "config" and args.config_command == "check":
        return _config_check()
    if args.command == "config" and args.config_command == "show":
        return _config_show()
    return EXIT_USAGE  # pragma: no cover - argparse verlangt einen Unterbefehl


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
