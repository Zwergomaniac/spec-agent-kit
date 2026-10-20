"""Kommandozeile `sak`.

Konventionen (docs/architecture.md): JSON auf stdout; Exit 0 bei Erfolg,
1 bei fachlicher Ablehnung, 2 bei Bedienfehlern.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
import webbrowser
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from spec_agent_kit import __version__
from spec_agent_kit.board import BoardError
from spec_agent_kit.board.build import build_board
from spec_agent_kit.board.serve import DEFAULT_PORT, FALLBACK_LAST_PORT, bind_server
from spec_agent_kit.board.text import render_text
from spec_agent_kit.config import ConfigError, NotInitializedError, load_config
from spec_agent_kit.config.check import check as check_config
from spec_agent_kit.install import InstallError
from spec_agent_kit.install.apply import apply_plan
from spec_agent_kit.install.doctor import run_doctor
from spec_agent_kit.install.kit import locate_kit
from spec_agent_kit.install.plan import build_init_plan, build_upgrade_plan
from spec_agent_kit.pipeline import RefusedError, UsageError
from spec_agent_kit.pipeline.cli_bridge import add_parsers, run_command
from spec_agent_kit.pipeline.commands import Ctx
from spec_agent_kit.pipeline.hooks import cmd_hook
from spec_agent_kit.push.run import push, push_background, trigger_if_auto

EXIT_OK = 0
EXIT_REJECTED = 1
EXIT_USAGE = 2
_NL = chr(10)


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
    if args.port is not None and not 0 <= args.port <= 65535:
        _emit({"ok": False, "error": f"ungültiger Port: {args.port}"})
        return EXIT_USAGE
    try:
        server, moved_from = bind_server(root, args.port)
    except OSError as exc:
        if args.port is None:
            message = (
                f"kein freier Port zwischen {DEFAULT_PORT} und {FALLBACK_LAST_PORT}: {exc}. "
                "Mit --port einen anderen Port wählen."
            )
        else:
            message = (
                f"Port {args.port} nicht nutzbar: {exc}. Bei ausdrücklichem --port wird nicht "
                "ausgewichen; ohne --port wählt sak einen freien Port."
            )
        _emit({"ok": False, "error": message})
        return EXIT_USAGE
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}"
    result: dict[str, Any] = {"ok": True, "url": url, "hint": "Strg+C beendet"}
    if moved_from is not None:
        result["port_busy"] = moved_from
        result["note"] = f"Port {moved_from} ist belegt; ausgewichen auf {port}"
    _emit(result)
    sys.stdout.flush()
    if args.open:
        with contextlib.suppress(Exception):
            webbrowser.open(url)
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


def _install(args: argparse.Namespace) -> int:
    """``sak init`` und ``sak upgrade`` (Spec 005): ohne ``--apply`` nur der Plan."""
    target = Path(args.target)
    try:
        kit = locate_kit()
        if args.command == "init":
            plan = build_init_plan(
                kit,
                target,
                key=args.key,
                name=args.name,
                base_branch=args.base_branch,
                dashboard_url=args.dashboard_url,
                ui=not args.no_ui,
                test_fast=args.test_fast,
                test_full=args.test_full,
                lint=args.lint,
                allow_dirty=args.allow_dirty,
            )
        else:
            plan = build_upgrade_plan(kit, target, allow_dirty=args.allow_dirty)
        if not args.apply:
            _emit(plan.to_dict())
            sys.stderr.write(_NL.join(plan.text()) + _NL)
            return EXIT_OK
        report = apply_plan(plan, sync=not args.no_sync)
    except InstallError as exc:
        return _reject(exc.errors)
    _emit(report)
    sys.stderr.write(_NL.join(report["text"]) + _NL)
    return EXIT_OK if report["ok"] else EXIT_REJECTED


def _doctor(args: argparse.Namespace) -> int:
    """``sak doctor [ziel]`` (Spec 005 FR-008)."""
    root = Path(args.target).resolve() if args.target else find_root()
    if root is None:
        return _not_initialized()
    here = Path(__file__).resolve().parents[2]  # .../engine, wenn der Aufruf aus einer Engine kommt
    result = run_doctor(root, engine_running_from=here)
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
    board = sub.add_parser("board", help="Board-Dokument sak.board/1 (Spec 006)")
    shape = board.add_mutually_exclusive_group()
    shape.add_argument("--json", action="store_true", help="Board als JSON (Standard)")
    shape.add_argument("--text", action="store_true", help="Kurzfassung, höchstens 40 Zeilen")
    board_sub = board.add_subparsers(dest="board_command")
    serve = board_sub.add_parser("serve", help="Lokale Ansicht auf 127.0.0.1 (ohne Netz)")
    serve.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Port; ohne Angabe {DEFAULT_PORT} und bei Belegung der nächste freie bis "
        f"{FALLBACK_LAST_PORT}",
    )
    serve.add_argument("--open", action="store_true", help="Browser mit der URL öffnen")
    pushp = sub.add_parser("push", help="Events und Board ans Dashboard senden (Spec 006)")
    pushp.add_argument("--quiet", action="store_true", help="Keine Ausgabe")
    pushp.add_argument(
        "--background", action="store_true", help="Losgelöst starten und sofort zurückkehren"
    )
    _add_install_parsers(sub)
    add_parsers(sub)
    return parser


def _add_install_parsers(sub: Any) -> None:
    init = sub.add_parser("init", help="Kit in ein Zielprojekt installieren (Plan, dann --apply)")
    init.add_argument("target", help="Zielprojekt (Git-Wurzel mit spec-kit)")
    init.add_argument("--key", required=True, help="Projektschlüssel (a-z, 0-9, Bindestrich)")
    init.add_argument("--name", required=True, help="Anzeigename (1 bis 80 Zeichen)")
    init.add_argument("--base-branch", default="main", help="Basis-Branch (Default main)")
    init.add_argument("--dashboard-url", default=None, help="https://… (http nur für localhost)")
    init.add_argument("--no-ui", action="store_true", help="ui_review nicht aktivieren")
    init.add_argument("--test-fast", action="append", default=[], help="Befehl, wiederholbar")
    init.add_argument("--test-full", action="append", default=[], help="Befehl, wiederholbar")
    init.add_argument("--lint", action="append", default=[], help="Befehl, wiederholbar")
    upgrade = sub.add_parser("upgrade", help="Kit-Dateien im Zielprojekt nachrüsten")
    upgrade.add_argument("target", help="Zielprojekt")
    for command in (init, upgrade):
        command.add_argument("--apply", action="store_true", help="Plan umsetzen")
        command.add_argument("--allow-dirty", action="store_true", help="Unsauberen Stand zulassen")
        command.add_argument(
            "--no-sync", action="store_true", help="uv sync im Engine-Ordner überspringen"
        )
    doctor = sub.add_parser("doctor", help="Gesundheitscheck des Projekts")
    doctor.add_argument("target", nargs="?", default=None, help="Zielprojekt (Default: aktuelles)")


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
    if args.command in {"init", "upgrade"}:
        return _install(args)
    if args.command == "doctor":
        return _doctor(args)
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
