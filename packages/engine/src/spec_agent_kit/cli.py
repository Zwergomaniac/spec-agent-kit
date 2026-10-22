"""Kommandozeile `sak`.

Konventionen (docs/architecture.md): JSON auf stdout; Exit 0 bei Erfolg,
1 bei fachlicher Ablehnung, 2 bei Bedienfehlern.
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import json
import subprocess
import sys
import webbrowser
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from spec_agent_kit import __version__
from spec_agent_kit import deploy as deploy_module
from spec_agent_kit.board import BoardError
from spec_agent_kit.board.build import build_board
from spec_agent_kit.board.serve import (
    DEFAULT_PORT,
    FALLBACK_LAST_PORT,
    WEB_MISSING_MESSAGE,
    bind_server,
    web_available,
)
from spec_agent_kit.board.text import render_text
from spec_agent_kit.config import ConfigError, NotInitializedError, load_config
from spec_agent_kit.config.check import check as check_config
from spec_agent_kit.dashboard import connect as dashboard_connect
from spec_agent_kit.dashboard import status as dashboard_status
from spec_agent_kit.install import InstallError
from spec_agent_kit.install.apply import apply_plan
from spec_agent_kit.install.doctor import run_doctor
from spec_agent_kit.install.kit import locate_kit
from spec_agent_kit.install.plan import build_init_plan, build_upgrade_plan
from spec_agent_kit.migrate import MigrateError, legacy_pipeline
from spec_agent_kit.pipeline import RefusedError, UsageError
from spec_agent_kit.pipeline.cli_bridge import add_parsers, run_command
from spec_agent_kit.pipeline.commands import Ctx
from spec_agent_kit.pipeline.hooks import cmd_hook
from spec_agent_kit.pipeline.session import cmd_session_start
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


def _reject(errors: list[dict[str, str]], fmt: str = "json") -> int:
    if fmt == "text":
        sys.stdout.write(_NL.join(f"FEHLER {e['path']}: {e['message']}" for e in errors) + _NL)
    else:
        _emit({"ok": False, "errors": errors, "warnings": []})
    return EXIT_REJECTED


def _emit_text(lines: Sequence[str]) -> None:
    sys.stdout.write(_NL.join(lines) + _NL)


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


def _deploy(args: argparse.Namespace) -> int:
    """``sak deploy plan [--method NAME] <run|spec>...``: führt nichts aus (Spec 014)."""
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
        result = deploy_module.plan(effective, args.target, args.method)
    except RefusedError as exc:
        _emit({"ok": False, "error": exc.message, **exc.extra})
        return EXIT_REJECTED
    except UsageError as exc:
        _emit({"ok": False, "error": str(exc)})
        return EXIT_USAGE
    _emit(result)
    return EXIT_OK if result["allowed"] else EXIT_REJECTED


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
    if not web_available():
        server.server_close()
        return _reject([{"path": "board/web", "message": WEB_MISSING_MESSAGE}])
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


def _migrate(args: argparse.Namespace) -> int:
    """``sak migrate legacy-pipeline [--source DIR] [--apply]`` (Spec 010 FR-005)."""
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
        plan = legacy_pipeline.build_plan(root, effective, Path(args.source))
        if args.apply:
            legacy_pipeline.apply_plan(root, plan)
    except MigrateError as exc:
        return _reject([{"path": "--source", "message": str(exc)}])
    except OSError as exc:
        return _reject([{"path": "<root>", "message": f"Import fehlgeschlagen: {exc}"}])
    _emit(plan.to_dict(applied=args.apply))
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


def _dashboard(args: argparse.Namespace) -> int:
    """``sak dashboard connect|status`` (Spec 009 US4). Der Schlüssel erscheint nie in Ausgaben."""
    root = find_root()
    if root is None:
        return _not_initialized()
    if args.dashboard_command == "status":
        code, result = dashboard_status(root)
        _emit(result)
        return code

    def read_key() -> str:
        if args.key_stdin:
            return sys.stdin.readline(256)
        if not sys.stdin.isatty():
            raise UsageError("kein Terminal: den Schlüssel per --key-stdin übergeben")
        return getpass.getpass("Projekt-Schlüssel (Eingabe bleibt verdeckt): ")

    try:
        code, result = dashboard_connect(
            root,
            args.url,
            yes=args.yes,
            force=args.force,
            read_key=read_key,
            key_from_stdin=args.key_stdin,
            test_push=not args.no_test_push,
            auth=args.auth,
        )
    except UsageError as exc:
        _emit({"ok": False, "error": str(exc)})
        return EXIT_USAGE
    _emit(result)
    if result.get("mode") == "plan":
        sys.stderr.write(_plan_text(result) + _NL)
    return code


def _plan_text(plan: dict[str, Any]) -> str:
    config = plan["config"]
    action = plan["key_file"]["action"]
    key_action = {"replace": "ersetzt", "none": "wird nicht angelegt (Proxy-Modus)"}.get(
        action, "neu angelegt"
    )
    return _NL.join(
        [
            "sak dashboard connect (Plan, nichts geschrieben)",
            f"  Config: dashboard.url {config['url_from']} -> {config['url_to']}",
            f"  Schlüsseldatei {plan['key_file']['path']}: {key_action}",
            f"  {plan['next']}",
        ]
    )


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
                clean_ignore=args.clean_ignore,
                allow_dirty=args.allow_dirty,
                agent_environment=args.agent_environment,
            )
        else:
            plan = build_upgrade_plan(kit, target, allow_dirty=args.allow_dirty)
        if not args.apply:
            # Entweder JSON oder Text auf stdout, nie beides (Spec 011 US6).
            if args.format == "text":
                _emit_text(plan.text())
            else:
                _emit(plan.to_dict())
            return EXIT_OK
        report = apply_plan(plan, sync=not args.no_sync)
    except InstallError as exc:
        return _reject(exc.errors, args.format)
    if args.format == "text":
        _emit_text(_report_text(report))
    else:
        _emit(report)
    return EXIT_OK if report["ok"] else EXIT_REJECTED


def _report_text(report: dict[str, Any]) -> list[str]:
    """Lesbare Fassung des Berichts nach ``--apply``."""
    lines = list(report["text"])
    applied = report["applied"]
    lines.append(f"Geschrieben: {applied['written']}, gelöscht: {applied['deleted']}.")
    lines.extend(f"Konflikt, Kit-Fassung daneben: {path}" for path in applied["conflicts"])
    lines.append(f"uv sync: {report['uv_sync']['detail']}")
    if "config_check" in report:
        check = report["config_check"]
        lines.append(f"config check: {'ok' if check['ok'] else 'FEHLER'}")
        lines.extend(f"  {e['path']}: {e['message']}" for e in check.get("errors", []))
    lines.append(f"Ergebnis: {'ok' if report['ok'] else 'mit Fehlern'}")
    lines.extend(f"Nächster Schritt: {step}" for step in report["next_steps"])
    lines.append(f"Vorschlag: {report['suggested_commit']}")
    return lines


def _doctor(args: argparse.Namespace) -> int:
    """``sak doctor [ziel]`` (Spec 005 FR-008)."""
    root = Path(args.target).resolve() if args.target else find_root()
    if root is None:
        return _not_initialized()
    here = Path(__file__).resolve().parents[2]  # .../engine, wenn der Aufruf aus einer Engine kommt
    result = run_doctor(root, engine_running_from=here, probe_commands=args.probe_commands)
    if args.format == "text":
        _emit_text(_doctor_text(result))
    else:
        _emit(result)
    return EXIT_OK if result["ok"] else EXIT_REJECTED


def _doctor_text(result: dict[str, Any]) -> list[str]:
    lines = []
    for check in result["checks"]:
        if not check["ok"]:
            mark = "FEHLER" if check["required"] else "WARNUNG"
        else:
            mark = "WARNUNG" if check.get("warning") else "ok"
        lines.append(f"[{mark}] {check['check']}: {check['detail']}")
        lines.extend(
            f"    {'ok' if item['ok'] else 'FEHLER'} {item['kind']}: {item['command']} "
            f"({item['detail']})"
            for item in check.get("items", [])
            if not item["ok"] or (check["check"] == "commands" and len(check["items"]) <= 8)
        )
    lines.append("Ergebnis: " + ("ok" if result["ok"] else "Pflichtprüfung fehlgeschlagen"))
    return lines


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sak", description="Spec Agent Kit")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="Gibt die Kit-Version als JSON aus")
    config = sub.add_parser("config", help="Projektkonfiguration (.spec-agent/config.yml)")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("check", help="Prüft die Konfiguration (Schema, Agents, Frontmatter)")
    config_sub.add_parser("show", help="Gibt die wirksame Konfiguration als JSON aus")
    deploy = sub.add_parser("deploy", help="Deploy-Wege (Spec 014)")
    deploy_sub = deploy.add_subparsers(dest="deploy_command", required=True)
    deploy_plan = deploy_sub.add_parser(
        "plan", help="Löst Weg und Befehl auf, ohne etwas auszuführen (JSON)"
    )
    deploy_plan.add_argument(
        "--method", default=None, help="Name des Wegs (Default: deploy.default)"
    )
    deploy_plan.add_argument(
        "target", nargs="+", help="Lauf-ID, Spec-Verzeichnis oder Nummer (mehrere: 084,085)"
    )
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
    migrate = sub.add_parser("migrate", help="Alte Daten übernehmen (Spec 010)")
    migrate_sub = migrate.add_subparsers(dest="migrate_command", required=True)
    legacy = migrate_sub.add_parser(
        "legacy-pipeline",
        help="Lauf-Historie der alten Pipeline importieren (ohne --apply nur der Plan)",
    )
    legacy.add_argument(
        "--source",
        default=legacy_pipeline.DEFAULT_SOURCE,
        help=f"Quellverzeichnis (Default {legacy_pipeline.DEFAULT_SOURCE})",
    )
    legacy.add_argument("--apply", action="store_true", help="Import schreiben")
    pushp = sub.add_parser("push", help="Events und Board ans Dashboard senden (Spec 006)")
    pushp.add_argument("--quiet", action="store_true", help="Keine Ausgabe")
    pushp.add_argument(
        "--background", action="store_true", help="Losgelöst starten und sofort zurückkehren"
    )
    dash = sub.add_parser("dashboard", help="Projekt ans Dashboard anbinden (Spec 009)")
    dash_sub = dash.add_subparsers(dest="dashboard_command", required=True)
    connect = dash_sub.add_parser(
        "connect", help="URL eintragen und Schlüssel ablegen (ohne --yes nur der Plan)"
    )
    connect.add_argument("--url", required=True, help="https://… (http nur für localhost)")
    connect.add_argument("--key-stdin", action="store_true", help="Schlüssel von stdin lesen")
    connect.add_argument("--yes", action="store_true", help="Plan umsetzen")
    connect.add_argument("--force", action="store_true", help="vorhandene dashboard.key ersetzen")
    connect.add_argument("--no-test-push", action="store_true", help="Test-Push überspringen")
    connect.add_argument(
        "--auth",
        choices=["key", "proxy"],
        default=None,
        help="proxy: nur URL und Modus eintragen, kein Schlüssel (Network Secret, Spec 013)",
    )
    dash_sub.add_parser("status", help="URL, Schlüssel vorhanden, Push-Modus, Cursor")
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
    init.add_argument(
        "--agent-environment",
        choices=["claude", "copilot"],
        default="claude",
        help="vom Kit aktiv verwaltete Agent-Umgebung",
    )
    init.add_argument("--no-ui", action="store_true", help="ui_review nicht aktivieren")
    init.add_argument("--test-fast", action="append", default=[], help="Befehl, wiederholbar")
    init.add_argument("--test-full", action="append", default=[], help="Befehl, wiederholbar")
    init.add_argument("--lint", action="append", default=[], help="Befehl, wiederholbar")
    init.add_argument(
        "--clean-ignore",
        action="append",
        default=[],
        help="guard.clean_ignore-Eintrag (zum Beispiel test-results/), wiederholbar",
    )
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
    doctor.add_argument(
        "--probe-commands",
        action="store_true",
        help="Testbefehle probeweise ausführen (pytest --collect-only -q, sonst --version)",
    )
    for command in (init, upgrade, doctor):
        command.add_argument(
            "--format",
            choices=["json", "text"],
            default="json",
            help="Ausgabe auf stdout: json (Standard) oder text, nie beides",
        )


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
        root = find_root()
        if args.hook_command == "session-start":
            cmd_session_start(sys.stdin, root, sys.stdout)  # nur JSON, nur bei Kompaktierung
            return EXIT_OK
        phase = "start" if args.hook_command == "subagent-start" else "stop"
        cmd_hook(phase, sys.stdin, root)
        trigger_if_auto(root)  # FR-011: Hintergrund-Push, Fehler werden ignoriert
        return EXIT_OK
    if args.command in {"init", "upgrade"}:
        return _install(args)
    if args.command == "doctor":
        return _doctor(args)
    if args.command == "dashboard":
        return _dashboard(args)
    if args.command == "deploy":
        return _deploy(args)
    if args.command == "push":
        return _push(args)
    if args.command == "migrate":
        return _migrate(args)
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
