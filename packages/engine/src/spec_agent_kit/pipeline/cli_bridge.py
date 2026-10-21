"""Argumente und Verteilung von ``sak run``, ``sak hook`` und ``sak event`` (Spec 003 FR-001)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from spec_agent_kit.pipeline import UsageError, commands
from spec_agent_kit.pipeline.commands import Ctx


def add_parsers(sub: Any) -> None:
    """Hängt die Gruppen ``run``, ``hook`` und ``event`` an den Haupt-Parser."""
    run = sub.add_parser("run", help="Pipeline-Läufe (Spec 003)")
    r = run.add_subparsers(dest="run_command", required=True)

    pre = r.add_parser("preflight", help="Prüft Voraussetzungen, legt Branch und Lauf an")
    pre.add_argument("spec", help="Spec-Verzeichnis (NNN-slug) oder Nummer")
    pre.add_argument("--base", help="Basis-Branch (Default: project.base_branch)")
    pre.add_argument("--review-only", action="store_true", help="Nur-Prüfung-Lauf, ohne Builder")
    pre.add_argument("--base-commit", help="Basis-Commit (nur mit --review-only)")
    pre.add_argument("--takeover", metavar="GRUND", help="Verwaisten Lauf übernehmen")

    st = r.add_parser("state", help="Zustandswechsel nach der Übergangstabelle")
    st.add_argument("run")
    st.add_argument("new", help="Zielzustand")
    st.add_argument("--reason")
    st.add_argument("--gate")

    for name, text in (
        ("pause", "Pausiert den Lauf und gibt die Sperre frei"),
        ("release", "Gibt einen eskalierten Lauf frei (→ approved)"),
        ("abort", "Bricht den Lauf ab"),
    ):
        p = r.add_parser(name, help=text)
        p.add_argument("run")
        p.add_argument("--reason")
    ret = r.add_parser("return", help="Gibt einen eskalierten Lauf an den Builder zurück")
    ret.add_argument("run")
    ret.add_argument("--reason", required=True)
    res = r.add_parser("resume", help="Setzt einen pausierten Lauf fort")
    res.add_argument("run")

    for name, text in (
        ("guard", "Prüft geänderte Pfade gegen den Schutz"),
        ("combine", "Bildet das Gesamturteil der Runde"),
        ("merge", "Merged einen freigegebenen Lauf (--no-ff, kein Push)"),
        ("show", "Zeigt einen Lauf"),
    ):
        p = r.add_parser(name, help=text)
        p.add_argument("run")
    cl = r.add_parser(
        "cleanup", help="Entfernt Links und Junctions unter runs/<id>/ (Ziele bleiben)"
    )
    cl.add_argument("run")
    r.add_parser("snapshot", help="Hash des Arbeitsstands")
    rc = r.add_parser("reviewer-check", help="Prüft, dass ein Prüfer nichts verändert hat")
    rc.add_argument("hash")
    vd = r.add_parser("verdict", help="Legt das Urteil eines Prüfers ab")
    vd.add_argument("run")
    vd.add_argument("role")
    vd.add_argument("file", type=Path)
    ls = r.add_parser("list", help="Läufe auflisten")
    ls.add_argument("--all", action="store_true", help="Auch beendete Läufe")

    hook = sub.add_parser("hook", help="Hook-Einstiege (enden immer mit Exit 0)")
    hook.add_argument("hook_command", choices=["subagent-start", "subagent-stop"])

    event = sub.add_parser("event", help="Ereignisse")
    e = event.add_subparsers(dest="event_command", required=True)
    em = e.add_parser("emit", help="Schreibt ein Ereignis ohne Zustandswechsel")
    em.add_argument("type")
    em.add_argument("--run")
    em.add_argument("--reason")


def run_command(args: argparse.Namespace, ctx: Ctx) -> dict[str, Any]:
    """Führt einen ``run``- oder ``event``-Befehl aus."""
    if args.command == "event":
        return commands.cmd_event_emit(ctx, args.type, run_token=args.run, reason=args.reason)
    name = args.run_command
    if name == "preflight":
        return commands.cmd_preflight(
            ctx,
            args.spec,
            base=args.base,
            review_only=args.review_only,
            base_commit=args.base_commit,
            takeover=args.takeover,
        )
    if name == "state":
        return commands.cmd_state(ctx, args.run, args.new, reason=args.reason, gate=args.gate)
    if name == "pause":
        return commands.cmd_pause(ctx, args.run, reason=args.reason)
    if name == "resume":
        return commands.cmd_resume(ctx, args.run)
    if name == "release":
        return commands.cmd_release(ctx, args.run, reason=args.reason)
    if name == "return":
        return commands.cmd_return(ctx, args.run, reason=args.reason)
    if name == "abort":
        return commands.cmd_abort(ctx, args.run, reason=args.reason)
    if name == "cleanup":
        return commands.cmd_cleanup(ctx, args.run)
    if name == "guard":
        return commands.cmd_guard(ctx, args.run)
    if name == "snapshot":
        return commands.cmd_snapshot(ctx)
    if name == "reviewer-check":
        return commands.cmd_reviewer_check(ctx, args.hash)
    if name == "verdict":
        return commands.cmd_verdict(ctx, args.run, args.role, args.file)
    if name == "combine":
        return commands.cmd_combine(ctx, args.run)
    if name == "merge":
        return commands.cmd_merge(ctx, args.run)
    if name == "list":
        return commands.cmd_list(ctx, include_all=args.all)
    if name == "show":
        return commands.cmd_show(ctx, args.run)
    raise UsageError(f"unbekannter Befehl: {name}")  # pragma: no cover
