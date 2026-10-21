"""Hook ``SessionStart`` (Matcher ``compact``): Lauf-Kontext nach dem Kompaktieren (Spec 011 US8).

Claude Code kompaktiert den Kontext automatisch oder auf Wunsch des Betreibers. Hooks und Skills
können das nicht selbst auslösen, und das Kit empfiehlt es nie. Es sorgt nur dafür, dass der
Orchestrator danach weiß, wo er steht: Der Hook gibt bei ``source == "compact"`` und aktivem Lauf
eine Kurzfassung als ``additionalContext`` aus, sonst nichts.

Der Hook endet immer mit Exit 0, schreibt höchstens ein JSON-Dokument auf stdout und gibt nach
``DEADLINE_S`` Sekunden still auf.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Final, TextIO

from spec_agent_kit.config import EffectiveConfig, load_config
from spec_agent_kit.pipeline import runs
from spec_agent_kit.pipeline.events import clip
from spec_agent_kit.pipeline.verdict import parse_verdict

DEADLINE_S: float = 1.8
"""Höchstdauer; Tests setzen sie herab. Das Limit des Hooks in Claude Code ist 5 s."""
_MAX_PAYLOAD: Final[int] = 1_000_000
_MAX_MUST: Final[int] = 10
_MUST_CLIP: Final[int] = 300
_VERDICT_FILE = re.compile(r"^verdict-(?P<role>[a-z_]+)-r(?P<round>[0-9]+)[.]md$")
SAK: Final[str] = "uv run --project .spec-agent/engine sak"


def _verdicts(root: Path, run: dict[str, Any], cfg: EffectiveConfig) -> dict[int, dict[str, Any]]:
    """Gültige Urteile je Runde: ``{runde: {rolle: geparstes Urteil}}``."""
    found: dict[int, dict[str, Any]] = {}
    directory = runs.run_dir(root, run["run_id"])
    try:
        files = sorted(directory.glob("verdict-*-r*.md"))
    except OSError:
        return found
    for path in files:
        match = _VERDICT_FILE.match(path.name)
        if match is None:
            continue
        try:
            parsed = parse_verdict(path.read_text(encoding="utf-8"), str(cfg.data["locale"]))
        except (OSError, UnicodeDecodeError):
            continue
        if parsed["valid"]:
            found.setdefault(int(match["round"]), {})[match["role"]] = parsed
    return found


def _next_step(run: dict[str, Any], roles: dict[str, str], missing: list[str]) -> str:
    run_id = run["run_id"]
    state = run["state"]
    builder = roles.get("builder", "sak-builder")
    if state == "building":
        scope = (
            "Behebe nur die Muss-Befunde der letzten Prüfung (siehe oben)."
            if run["round"] > 1
            else "Arbeite die Tasks der Spec ab."
        )
        return (
            f"Builder-Agent '{builder}' starten (oder dessen laufenden Bericht abwarten). {scope} "
            f"Danach `{SAK} run state {run_id} reviewing` und `{SAK} run guard {run_id}`."
        )
    if state == "reviewing":
        pending = (
            f" Es fehlen noch Urteile von: {', '.join(missing)}."
            if missing
            else " Alle Urteile liegen vor."
        )
        return (
            f"Prüfer parallel in einer Nachricht starten (vorher `{SAK} run snapshot`), danach "
            f"`{SAK} run reviewer-check <snapshot>`, die Urteile mit `{SAK} run verdict {run_id} "
            f"<rolle> <datei>` ablegen und `{SAK} run combine {run_id}` aufrufen.{pending}"
        )
    if state == "approved":
        return (
            f"Abschluss: Diff sichten, `{SAK} run cleanup {run_id}`, `{SAK} run merge {run_id}` "
            "(kein Push), dann Kurzbericht an den Betreiber."
        )
    return (
        "Der Lauf ist eskaliert und wartet auf den Betreiber. Berichte kurz (Gate, Grund, offene "
        "Muss-Befunde) und warte. Setze die Eskalation nie selbst zurück; die Entscheidungen sind "
        "release, return, abort oder pause."
    )


def build_context(root: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Das Hook-Dokument, oder ``None``, wenn der Hook schweigen soll."""
    if payload.get("source") != "compact":
        return None
    run = runs.active_run(root)
    if run is None:
        return None
    cfg = load_config(root)
    roles = {r: str(cfg.role(r)["agent"]) for r in cfg.active_roles()}
    review_roles = [r for r in roles if r in ("code_review", "ui_review", "security_review")]
    verdicts = _verdicts(root, run, cfg)
    current = verdicts.get(int(run["round"]), {})
    missing = [r for r in review_roles if r not in current]

    last_round = max(verdicts) if verdicts else None
    must: list[str] = []
    if last_round is not None:
        for role in review_roles:
            parsed = verdicts[last_round].get(role)
            if parsed is not None:
                must.extend(f"[{role}] {clip(item, _MUST_CLIP)}" for item in parsed["must"])
    shown = must[:_MAX_MUST]

    lines = [
        "Spec Agent Kit: Der Kontext wurde kompaktiert, ein Lauf ist aktiv. Arbeite ohne "
        "Rückfrage an der Stelle weiter, an der der Lauf steht.",
        f"Lauf: {run['run_id']} ({run['kind']})",
        f"Spec: {run['spec']}",
        f"Zustand: {run['state']}, Runde {run['round']} von {run['max_rounds']}",
        f"Branch: {run['branch']}, Basis-Commit: {str(run['base_commit'])[:12]}",
        "Aktive Rollen: " + ", ".join(f"{r}={a}" for r, a in roles.items()),
    ]
    escalation = run.get("escalation")
    if run["state"] == "escalated" and isinstance(escalation, dict):
        lines.append(
            f"Eskalation: Gate {escalation.get('gate') or '-'}, Grund: "
            f"{clip(str(escalation.get('reason') or '-'), _MUST_CLIP)}"
        )
    if shown:
        lines.append(f"Muss-Befunde der letzten Prüfung (Runde {last_round}):")
        lines.extend(f"- {item}" for item in shown)
        if len(must) > len(shown):
            lines.append(
                f"- … {len(must) - len(shown)} weitere (Urteile unter runs/{run['run_id']}/)"
            )
    else:
        lines.append("Muss-Befunde der letzten Prüfung: keine.")
    lines.append("Nächster Schritt: " + _next_step(run, roles, missing))
    lines.append(
        f"Stand prüfen: `{SAK} run show {run['run_id']}`. Der Ablauf steht im Skill sak-pipeline."
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }


def cmd_session_start(stdin: TextIO, root: Path | None, out: TextIO) -> None:
    """``sak hook session-start``: schreibt höchstens ein JSON-Dokument. Wirft nie."""
    result: dict[str, Any] = {}

    def work() -> None:
        try:
            if root is None:
                return
            payload = json.loads(stdin.read(_MAX_PAYLOAD) or "{}")
            if isinstance(payload, dict):
                document = build_context(root, payload)
                if document is not None:
                    result["document"] = document
        except Exception:  # ein Hook darf die Sitzung nie stören
            return

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(DEADLINE_S)
    if worker.is_alive():
        return
    document = result.get("document")
    if document is not None:
        try:
            out.write(json.dumps(document, ensure_ascii=True) + "\n")
            out.flush()
        except Exception:
            return
