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
from spec_agent_kit.board import BoardError
from spec_agent_kit.board.build import build_board
from spec_agent_kit.board.serve import DEFAULT_PORT, make_server
from spec_agent_kit.board.text import render_text
from spec_agent_kit.config import ConfigError, NotInitializedError, load_config
from spec_agent_kit.config.check import check as check_config
from spec_agent_kit.pipeline import RefusedError, UsageError
from spec_agent_kit.pipeline.cli_bridge import add_parsers, run_command
from spec_agent_kit.pipeline.commands import Ctx
from spec_agent_kit.pipeline.hooks import cmd_hook
from spec_agent_kit.push.run import push, push_background, trigger_if_auto

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


def _pipeline(args: argparse.Namespace) -> int:
    """``sak run ...`` und ``sak event ...`` (Spec 003)."""
    root = find_root()
    if root is None:
        return _not_initialized()
    try:
        effective = load_config(root)
    except NotInitializedError:
        return _not_initialized()
    except ConfigError as exc:
        return _reject(exc.errors)
    try:
        result = run_command(args, Ctx(root=root, cfg=effective))
    except RefusedError as exc:
        _emit({"ok": False, "error": exc.message, **exc.extra})
        return EXIT_REJECTED
    except UsageError as exc:
        _emit({"ok": False, "error": str(exc)})
        return EXIT_USAGE
    _emit(result)
    return EXIT_OK


def _board(args: argparse.Namespace) -> int:
    """``sak board [--json|--text]`` (Spec 006 FR-007): validiert das Board vor der Ausgabe."""
    root = find_root()
    if root is None:
        return _not_initialized()
    try:
        effective = load_config(root)
    except NotInitializedError:
        return _not_initialized()
    except ConfigError as exc:
        return _reject(exc.errors)
    try:
        # Lokal wird der Text der Commit-Betreffe immer angezeigt (Spec 006, Annahmen).
        document = build_board(root, effective, share_text=True)
    except BoardError as exc:
        return _reject([{"path": exc.path, "message": exc.message}])
    if args.text:
        sys.stdout.write(render_text(document, str(effective.data["locale"])))
    else:
        _emit(document)
    return EXIT_OK


def _board_serve(args: argparse.Namespace) -> int:
    """``sak board serve [--port]``: lokale Ansicht auf 127.0.0.1 (Spec 006 FR-008)."""
    root = find_root()
    if root is None:
        return _not_initialized()
    try:
        load_config(root)
    except NotInitializedError:
        return _not_initialized()
    except ConfigError as exc:
        return _reject(exc.errors)
    if not 0 <= args.port <= 65535:
        _emit({"ok": False, "error": f"ungültiger Port: {args.port}"})
        return EXIT_USAGE
    try:
        server = make_server(root, args.port)
    except OSError as exc:
        _emit({"ok": False, "error": f"Port {args.port} nicht nutzbar: {exc}"})
        return EXIT_USAGE
    host, port = server.server_address[:2]
    _emit({"ok": True, "url": f"http://{host}:{port}", "hint": "Strg+C beendet"})
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return EXIT_OK


def _push(args: argparse.Namespace) -> int:
    """``sak push [--quiet] [--background]`` (Spec 006 FR-009, FR-010)."""
    root = find_root()
    if root is None:
        code, result = (
            1,
            {
                "ok": False,
                "status": "not_initialized",
                "error": "nicht initialisiert: .spec-agent/config.yml fehlt",
            },
        )
    elif args.background:
        code, result = push_background(root)
    else:
        code, result = push(root)
    if not args.quiet:
        _emit(result)
    return code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sak", description="Spec Agent Kit")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="Gibt die Kit-Version als JSON aus")
    config = sub.add_parser("config", help="Projektkonfiguration (.spec-agent/config.yml)")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("check", help="Prüft die Konfiguration (Schema, Agents, Frontmatter)")
    config_sub.add_parser("show", help="Gibt die wirksame Konfiguration als JSON aus")
    board = sub.add_parser("board", help="Board-Dokument sak.board/1 (Spec 006)")
    shape = board.add_mutually_exclusive_group()
    shape.add_argument("--json", action="store_true", help="Board als JSON (Standard)")
    shape.add_argument("--text", action="store_true", help="Kurzfassung, höchstens 40 Zeilen")
    board_sub = board.add_subparsers(dest="board_command")
    serve = board_sub.add_parser("serve", help="Lokale Ansicht auf 127.0.0.1 (ohne Netz)")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port (Default 5192)")
    pushp = sub.add_parser("push", help="Events und Board ans Dashboard senden (Spec 006)")
    pushp.add_argument("--quiet", action="store_true", help="Keine Ausgabe")
    pushp.add_argument(
        "--background", action="store_true", help="Losgelöst starten und sofort zurückkehren"
    )
    add_parsers(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Einstiegspunkt. Gibt den Exit-Code zurück."""
    _force_utf8()
    parser = _build_parser()
    given = list(sys.argv[1:] if argv is None else argv)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if given[:1] == ["hook"]:
            return EXIT_OK  # Hooks enden immer mit 0.
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    if args.command == "hook":
        phase = "start" if args.hook_command == "subagent-start" else "stop"
        root = find_root()
        cmd_hook(phase, sys.stdin, root)
        trigger_if_auto(root)  # FR-011: Hintergrund-Push, Fehler werden ignoriert
        return EXIT_OK
    if args.command == "push":
        return _push(args)
    if args.command in {"run", "event"}:
        code = _pipeline(args)
        if getattr(args, "run_command", None) not in {"list", "show", "snapshot"}:
            trigger_if_auto(find_root())
        return code
    if args.command == "board":
        return _board_serve(args) if args.board_command == "serve" else _board(args)
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
