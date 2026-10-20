"""Kommandozeile `sak`.

Konventionen (docs/architecture.md): JSON auf stdout; Exit 0 bei Erfolg,
1 bei fachlicher Ablehnung, 2 bei Bedienfehlern.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from spec_agent_kit import __version__

EXIT_OK = 0
EXIT_REJECTED = 1
EXIT_USAGE = 2


def _force_utf8() -> None:
    """Stellt stdout und stderr unabhängig von der Konsolen-Codepage auf UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sak", description="Spec Agent Kit")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="Gibt die Kit-Version als JSON aus")
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
    return EXIT_USAGE  # pragma: no cover - argparse verlangt einen Unterbefehl


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
