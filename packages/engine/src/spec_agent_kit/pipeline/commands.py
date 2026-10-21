"""Befehle von ``sak run`` und ``sak event`` (Spec 003 FR-001 bis FR-011).

Jede ``cmd_*``-Funktion gibt ein JSON-fähiges Dict zurück oder wirft ``RefusedError`` (Exit 1) bzw.
``UsageError`` (Exit 2). Git läuft nur über Argumentlisten (``pipeline.git``).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from spec_agent_kit import contracts, worktree
from spec_agent_kit.config import EffectiveConfig
from spec_agent_kit.config.check import check as check_config
from spec_agent_kit.pipeline import RefusedError, UsageError, git, links, runs
from spec_agent_kit.pipeline.events import EventError, clip, emit, last_event_at, read_events
from spec_agent_kit.pipeline.states import plan_transition
from spec_agent_kit.pipeline.verdict import parse_verdict, strongest

REVIEW_ROLES: Final[tuple[str, ...]] = ("code_review", "ui_review", "security_review")
"""Rollen, die ein Urteil liefern (Vokabular: Art „prüft“)."""

# Ereignisse ohne eigenen Befehl, die `sak event emit` schreiben darf: Typ -> Daten aus dem Lauf.
_EMITTABLE: Final[frozenset[str]] = frozenset(
    {
        "run.escalated",
        "run.released",
        "run.returned",
        "run.paused",
        "run.aborted",
        "run.resumed",
        "run.approved",
        "run.reviewed",
        "run.merged",
        "run.taken_over",
        "round.started",
    }
)


@dataclass
class Ctx:
    """Projektwurzel, wirksame Config und gesammelte Hinweise (Events, die nicht gültig waren)."""

    root: Path
    cfg: EffectiveConfig
    warnings: list[str] = field(default_factory=list)

    @property
    def project(self) -> str:
        return str(self.cfg.data["project"]["key"])

    @property
    def clean_ignore(self) -> list[str]:
        return list(self.cfg.data["guard"]["clean_ignore"])

    @property
    def locale(self) -> str:
        return str(self.cfg.data["locale"])

    def review_roles(self) -> list[str]:
        return [r for r in self.cfg.active_roles() if r in REVIEW_ROLES]


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------


def _event(ctx: Ctx, etype: str, run: dict[str, Any] | None, **data: Any) -> None:
    """Schreibt ein Event. Ein ungültiges Event wird verworfen und als Hinweis gemeldet."""
    try:
        emit(ctx.root, etype, project=ctx.project, run=run, **data)
    except EventError as exc:
        ctx.warnings.append(f"Event verworfen: {exc}")


def _apply(ctx: Ctx, run: dict[str, Any], new: str, **options: Any) -> None:
    """Zustandswechsel mit Speichern und Events."""
    planned = plan_transition(run, new, **options)
    runs.write_run(ctx.root, run)
    for etype, data in planned:
        _event(ctx, etype, run, **data)


def _result(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    result = {"ok": True, **payload}
    if ctx.warnings:
        result["warnings"] = list(ctx.warnings)
    return result


def _idle(ctx: Ctx, run: dict[str, Any]) -> dict[str, Any]:
    pipeline = ctx.cfg.data["pipeline"]
    return runs.idle_info(
        run,
        last_event_at(ctx.root, run["run_id"]),
        idle_minutes=int(pipeline["idle_minutes"]),
        stale_hours=int(pipeline["stale_hours"]),
        now=runs.utcnow(),
    )


def _stale_note(ctx: Ctx, run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run["run_id"],
        "spec": run["spec"],
        "state": run["state"],
        "last_event_at": _idle(ctx, run)["last_event_at"],
    }


def _stale_runs(ctx: Ctx) -> list[dict[str, Any]]:
    notes = []
    for run in runs.all_runs(ctx.root):
        if run.get("state") in runs.ACTIVE_STATES and _idle(ctx, run)["stale"]:
            notes.append(_stale_note(ctx, run))
    return notes


def _roles_info(ctx: Ctx, only_review: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for role in ctx.cfg.active_roles():
        if only_review and role not in REVIEW_ROLES:
            continue
        settings = ctx.cfg.role(role)
        result[role] = {
            "agent": settings["agent"],
            "model": settings["model"],
            "effort": settings["effort"],
        }
    return result


def _require_gate(gate: str | None) -> None:
    if gate is not None and gate not in contracts.vocabulary()["gate"]:
        raise UsageError(f"unbekanntes Gate: {gate}")


def _dirty(ctx: Ctx) -> list[str]:
    return git.dirty_files(ctx.root, ctx.clean_ignore)


def _require_clean(ctx: Ctx) -> None:
    dirty = _dirty(ctx)
    if dirty:
        raise RefusedError("Arbeitsstand nicht sauber: " + ", ".join(dirty[:10]), files=dirty)


def _resolve(ctx: Ctx, token: str, **kwargs: Any) -> dict[str, Any]:
    return runs.resolve_run(ctx.root, token, **kwargs)


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------


def _branch_name(ctx: Ctx, spec: str) -> str:
    pattern = str(ctx.cfg.data["pipeline"]["branch_pattern"])
    try:
        return pattern.format(spec=spec)
    except (KeyError, IndexError, ValueError) as exc:
        raise RefusedError(f"branch_pattern '{pattern}' ist nicht auflösbar") from exc


def _switch_to_run_branch(ctx: Ctx, spec: str, base_branch: str) -> str:
    """Legt den Spec-Branch an oder wechselt auf ihn. Kein automatisches Rebase."""
    root = ctx.root
    branch = _branch_name(ctx, spec)
    current = git.current_branch(root)
    if not git.branch_exists(root, base_branch):
        raise RefusedError(f"Basis-Branch '{base_branch}' existiert nicht")
    if current not in {branch, base_branch}:
        raise RefusedError(
            f"ausgecheckt ist '{current or 'losgelöster HEAD'}', erwartet wird der Basis-Branch "
            f"'{base_branch}' (oder --base angeben)"
        )
    if git.branch_exists(root, branch):
        if current != branch:
            if not git.is_ancestor(root, "HEAD", branch):
                raise RefusedError(
                    f"Branch '{branch}' existiert schon und enthält den Stand von '{current}' "
                    "nicht — umbenennen oder löschen und neu starten (kein automatisches Rebase)"
                )
            git.git(root, "switch", branch)
    else:
        git.git(root, "switch", "-c", branch)
    return branch


def _worktree_note(ctx: Ctx) -> dict[str, Any] | None:
    """Hinweise zu Worktrees (Spec 011 US3).

    Die Hooks schreiben nach ``CLAUDE_PROJECT_DIR``, also dorthin, wo die Sitzung gestartet wurde.
    Läuft die Sitzung nicht im Checkout des Laufs, entstehen dort keine Stations-Events.
    """
    session = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if session and not worktree.same_directory(session, ctx.root):
        ctx.warnings.append(
            f"CLAUDE_PROJECT_DIR ({session}) ist nicht der Checkout des Laufs ({ctx.root}): die "
            "Hooks schreiben Stations-Events dorthin, nicht in den Lauf. Die Sitzung im Checkout "
            "des Laufs starten."
        )
    main = worktree.main_checkout(ctx.root)
    if main is None:
        return None
    inherited = ctx.cfg.inherited_from is not None
    return {"main_checkout": str(main), "dashboard_inherited": inherited}


def cmd_preflight(
    ctx: Ctx,
    spec_token: str,
    *,
    base: str | None = None,
    review_only: bool = False,
    base_commit: str | None = None,
    takeover: str | None = None,
) -> dict[str, Any]:
    """Prüft die Voraussetzungen, legt Branch und Lauf an und schreibt ``run.started``."""
    root = ctx.root
    if takeover is not None and not takeover.strip():
        raise UsageError("--takeover braucht einen Grund")
    if review_only and not base_commit:
        raise UsageError("--review-only braucht --base-commit <sha>")
    if base_commit and not review_only:
        raise UsageError("--base-commit gilt nur zusammen mit --review-only")

    checked = check_config(root)
    if not checked["ok"]:
        raise RefusedError("Config ungültig (sak config check)", errors=checked["errors"])
    spec = runs.resolve_spec(root, spec_token)
    if not (root / "specs" / spec / "tasks.md").is_file():
        raise RefusedError(f"specs/{spec}/tasks.md fehlt")
    _require_clean(ctx)

    other = runs.active_run(root)
    stale_before = _stale_runs(ctx)
    taken: dict[str, Any] | None = None
    if other is not None:
        if _idle(ctx, other)["stale"]:
            if takeover is None:
                raise RefusedError(
                    f"verwaister Lauf {other['run_id']} ({other['spec']}, {other['state']}): "
                    'mit --takeover "<Grund>" übernehmen',
                    stale_runs=stale_before,
                )
            taken = other
        else:
            hint = " (nicht verwaist, keine Übernahme möglich)" if takeover is not None else ""
            raise RefusedError(
                f"es läuft bereits ein Lauf: {other['run_id']} ({other['spec']}, "
                f"{other['state']}){hint}",
                stale_runs=stale_before,
            )

    base_branch = base or str(ctx.cfg.data["project"]["base_branch"])
    kind = "review_only" if review_only else "pipeline"
    if review_only:
        assert base_commit is not None
        sha = git.resolve_commit(root, base_commit)
        if sha is None:
            raise RefusedError(f"Commit '{base_commit}' nicht gefunden")
        branch = git.current_branch(root)
        if not branch:
            raise RefusedError("losgelöster HEAD: für --review-only auf einen Branch wechseln")
        state = "reviewing"
    else:
        branch = _switch_to_run_branch(ctx, spec, base_branch)
        sha = git.head(root)
        state = "building"

    if taken is not None:
        assert takeover is not None
        _apply(ctx, taken, "aborted", reason=takeover, takeover=True)

    worktree_note = _worktree_note(ctx)
    now = runs.utcnow()
    run_id = runs.new_run_id(root, spec, now)
    run: dict[str, Any] = {
        "run_id": run_id,
        "spec": spec,
        "kind": kind,
        "state": state,
        "paused_from": None,
        "round": 1,
        "max_rounds": int(ctx.cfg.data["pipeline"]["max_rounds"]),
        "branch": branch,
        "base_branch": base_branch,
        "base_commit": sha,
        "started_at": runs.format_ts(now),
        "updated_at": runs.format_ts(now),
        "escalation": None,
        "origin": {"branch": base_branch},
    }
    runs.write_run(root, run)
    _event(
        ctx,
        "run.started",
        run,
        kind=kind,
        base_branch=base_branch,
        base_commit=sha,
        max_rounds=run["max_rounds"],
    )
    _event(ctx, "round.started", run, round=1)
    return _result(
        ctx,
        {
            "run_id": run_id,
            "spec": spec,
            "kind": kind,
            "state": state,
            "round": 1,
            "max_rounds": run["max_rounds"],
            "branch": branch,
            "base_branch": base_branch,
            "base_commit": sha,
            "roles": _roles_info(ctx, only_review=review_only),
            "commands": ctx.cfg.data["commands"],
            "taken_over": taken["run_id"] if taken else None,
            "stale_runs": _stale_runs(ctx),
            "worktree": worktree_note,
        },
    )


# ---------------------------------------------------------------------------
# Zustandsbefehle
# ---------------------------------------------------------------------------


def _state_payload(run: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": run["run_id"], "state": run["state"], "round": run["round"]}


def cmd_state(
    ctx: Ctx, token: str, new: str, *, reason: str | None = None, gate: str | None = None
) -> dict[str, Any]:
    """Allgemeiner Zustandswechsel nach der Übergangstabelle."""
    _require_gate(gate)
    if new == "paused":
        return cmd_pause(ctx, token, reason=reason)
    if new == "merged":
        raise RefusedError("merged setzt `sak run merge`")
    run = _resolve(ctx, token)
    if run["state"] == "paused" and new != "aborted":
        if new != run.get("paused_from"):
            raise RefusedError(
                f"Übergang paused → {new} nicht erlaubt (fortsetzen nach {run.get('paused_from')})"
            )
        return cmd_resume(ctx, run["run_id"])
    _apply(ctx, run, new, reason=reason, gate=gate)
    return _result(ctx, _state_payload(run))


def cmd_pause(ctx: Ctx, token: str, *, reason: str | None = None) -> dict[str, Any]:
    """Pausiert einen Lauf und gibt die Sperre frei."""
    run = _resolve(ctx, token)
    _apply(ctx, run, "paused", reason=reason)
    return _result(ctx, {**_state_payload(run), "paused_from": run["paused_from"]})


def cmd_resume(ctx: Ctx, token: str) -> dict[str, Any]:
    """Setzt einen pausierten Lauf fort (freie Sperre; Branch-Wechsel nur bei sauberem Stand)."""
    run = _resolve(ctx, token, only_states=frozenset({"paused"}))
    if run["state"] != "paused":
        raise RefusedError(f"Lauf {run['run_id']} ist nicht pausiert ({run['state']})")
    other = runs.active_run(ctx.root)
    if other is not None:
        raise RefusedError(
            f"es läuft bereits ein Lauf: {other['run_id']} ({other['spec']}, {other['state']})"
        )
    target = run.get("paused_from")
    if target not in {"building", "reviewing", "escalated"}:
        raise RefusedError(f"Lauf {run['run_id']} hat keinen gültigen Zustand vor der Pause")
    if run["kind"] == "pipeline" and git.current_branch(ctx.root) != run["branch"]:
        _require_clean(ctx)
        if not git.branch_exists(ctx.root, run["branch"]):
            raise RefusedError(f"Run-Branch '{run['branch']}' existiert nicht mehr")
        git.git(ctx.root, "switch", run["branch"])
    _apply(ctx, run, str(target))
    return _result(ctx, {**_state_payload(run), "branch": run["branch"]})


def cmd_release(ctx: Ctx, token: str, *, reason: str | None = None) -> dict[str, Any]:
    """Gibt einen eskalierten Lauf frei (``escalated`` → ``approved``)."""
    run = _resolve(ctx, token)
    if run["state"] != "escalated":
        raise RefusedError(f"release gilt nur für eskalierte Läufe ({run['state']})")
    _apply(ctx, run, "approved", reason=reason)
    return _result(ctx, _state_payload(run))


def cmd_return(ctx: Ctx, token: str, *, reason: str) -> dict[str, Any]:
    """Gibt einen eskalierten Lauf mit Auftrag an den Builder zurück (nächste Runde)."""
    if not reason or not reason.strip():
        raise UsageError("return braucht --reason")
    run = _resolve(ctx, token)
    if run["state"] != "escalated":
        raise RefusedError(f"return gilt nur für eskalierte Läufe ({run['state']})")
    _apply(ctx, run, "building", reason=reason)
    return _result(ctx, _state_payload(run))


def cmd_abort(ctx: Ctx, token: str, *, reason: str | None = None) -> dict[str, Any]:
    """Bricht einen Lauf ab. Der Branch bleibt bestehen. Links im Lauf-Ordner werden entfernt."""
    run = _resolve(ctx, token)
    _apply(ctx, run, "aborted", reason=reason)
    run["paused_from"] = None
    runs.write_run(ctx.root, run)
    return _result(ctx, {**_state_payload(run), **_cleanup_links(ctx, run)})


# ---------------------------------------------------------------------------
# cleanup (Spec 011 B14)
# ---------------------------------------------------------------------------


def _cleanup_links(ctx: Ctx, run: dict[str, Any]) -> dict[str, Any]:
    """Entfernt Links und Junctions unter ``runs/<id>/`` (ohne ihnen zu folgen).

    Gibt ``{"cleaned_links": [...]}`` zurück, leer, wenn nichts zu tun war. Fehler werden als
    Hinweis gemeldet und brechen den aufrufenden Befehl nicht ab.
    """
    directory = runs.run_dir(ctx.root, run["run_id"])
    removed, failed = links.remove_links(directory)
    for path, reason in failed:
        ctx.warnings.append(f"Link nicht entfernt: {_relative(directory, path)} ({reason})")
    if not removed:
        return {}
    return {"cleaned_links": [_relative(directory, p) for p in removed]}


def _relative(base: Path, path: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def cmd_cleanup(ctx: Ctx, token: str) -> dict[str, Any]:
    """Entfernt Links und Junctions unter ``runs/<id>/``. Das Ziel eines Links bleibt unberührt."""
    run = _resolve(ctx, token, include_finished=True)
    directory = runs.run_dir(ctx.root, run["run_id"])
    if links.is_link(directory):
        raise RefusedError(f"Lauf-Ordner von {run['run_id']} ist selbst ein Link; nichts getan")
    removed, failed = links.remove_links(directory)
    payload = {
        "run_id": run["run_id"],
        "removed": [_relative(directory, p) for p in removed],
        "failed": [{"path": _relative(directory, p), "reason": r} for p, r in failed],
    }
    if failed:
        raise RefusedError("nicht alle Links entfernt", **payload)
    return _result(ctx, payload)


# ---------------------------------------------------------------------------
# guard, snapshot, reviewer-check
# ---------------------------------------------------------------------------


def cmd_guard(ctx: Ctx, token: str) -> dict[str, Any]:
    """Prüft die geänderten Pfade gegen Kern-Schutz und ``guard.protected_paths``."""
    run = _resolve(ctx, token)
    data = ctx.cfg.data
    changed = git.changed_since(ctx.root, run["base_commit"], ctx.clean_ignore)
    protected = [p for p in changed if git.matches_any(p, data["guard"]["protected_paths"])]
    hints = [p for p in changed if git.matches_any(p, data["escalation"]["paths"])]
    return _result(
        ctx,
        {
            "run_id": run["run_id"],
            "escalate": bool(protected),
            "gate": "protected_paths" if protected else None,
            "reason": "Pipeline-Datei geändert" if protected else None,
            "protected_hits": protected,
            "hints": hints,
            "changed_count": len(changed),
        },
    )


def snapshot_hash(root: Path, clean_ignore: list[str]) -> str:
    """SHA-256 über HEAD, geänderte Dateien (Pfad, Inhalt), ``git diff`` (ohne clean_ignore) und
    die Top-Level-Ordner, die Git nicht sieht (leere Ordner, Spec 011 B14)."""
    parts = [git.head(root)]
    for rel in git.dirty_files(root, clean_ignore):
        path = root / rel
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "-"
        except OSError:
            digest = "?"
        parts.append(f"{rel}\0{digest}")
    parts.append(git.git(root, "diff", "HEAD", "--", ".", *git.exclude_specs(clean_ignore)))
    parts.append("dirs\x00" + "\x00".join(git.new_top_level_dirs(root, clean_ignore)))
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


_SNAPSHOT_DIRS = "snapshot-dirs.json"


def cmd_snapshot(ctx: Ctx) -> dict[str, Any]:
    # Die Liste der Top-Level-Ordner bleibt liegen, damit reviewer-check neue Ordner benennen kann.
    with contextlib.suppress(OSError):
        runs.write_text_atomic(
            runs.state_dir(ctx.root) / _SNAPSHOT_DIRS,
            json.dumps(git.new_top_level_dirs(ctx.root, ctx.clean_ignore)),
        )
    return _result(ctx, {"snapshot": snapshot_hash(ctx.root, ctx.clean_ignore)})


def _new_dirs_since_snapshot(ctx: Ctx) -> list[str]:
    try:
        before = json.loads((runs.state_dir(ctx.root) / _SNAPSHOT_DIRS).read_text("utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(before, list):
        return []
    now = git.new_top_level_dirs(ctx.root, ctx.clean_ignore)
    return [d for d in now if d not in before]


def cmd_reviewer_check(ctx: Ctx, before: str) -> dict[str, Any]:
    """Vergleicht mit dem Snapshot. Eine Änderung eskaliert den Lauf (``review_integrity``)."""
    after = snapshot_hash(ctx.root, ctx.clean_ignore)
    if after == before:
        return _result(ctx, {"changed": False})
    extra: dict[str, Any] = {}
    new_dirs = _new_dirs_since_snapshot(ctx)
    if new_dirs:
        extra["new_top_level_dirs"] = new_dirs
    run = runs.active_run(ctx.root)
    if run is not None and run["state"] != "escalated":
        _apply(
            ctx,
            run,
            "escalated",
            reason="Prüfer hat das Repo verändert",
            gate="review_integrity",
        )
        extra = {
            **extra,
            "run_id": run["run_id"],
            "state": run["state"],
            "gate": "review_integrity",
        }
    message = "Prüfer hat das Repo verändert"
    if new_dirs:
        message += " (neue Top-Level-Ordner: " + ", ".join(new_dirs) + ")"
    raise RefusedError(message, **extra)


# ---------------------------------------------------------------------------
# verdict, combine
# ---------------------------------------------------------------------------


def _verdict_path(root: Path, run: dict[str, Any], role: str, rnd: int | None = None) -> Path:
    return runs.run_dir(root, run["run_id"]) / f"verdict-{role}-r{rnd or run['round']}.md"


def cmd_verdict(ctx: Ctx, token: str, role: str, file: Path) -> dict[str, Any]:
    """Prüft das Urteilsformat, legt das Urteil ab und schreibt ``verdict.recorded``."""
    run = _resolve(ctx, token)
    allowed = ctx.review_roles()
    if role not in allowed:
        raise RefusedError(f"Rolle '{role}' ist keine aktive Prüfrolle (aktiv: {allowed})")
    if run["state"] != "reviewing":
        raise RefusedError(f"Urteile gelten nur im Zustand reviewing ({run['state']})")
    try:
        text = file.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise RefusedError(f"Urteilsdatei nicht lesbar: {file}") from exc
    parsed = parse_verdict(text, ctx.locale)
    if not parsed["valid"]:
        raise RefusedError(parsed["error"])
    target = _verdict_path(ctx.root, run, role)
    runs.write_text_atomic(target, text)
    _event(
        ctx,
        "verdict.recorded",
        run,
        round=run["round"],
        role=role,
        verdict=parsed["effective"],
        must_count=len(parsed["must"]),
        may_count=len(parsed["may"]),
    )
    return _result(
        ctx,
        {
            "run_id": run["run_id"],
            "role": role,
            "round": run["round"],
            "path": str(target),
            "verdict": parsed["effective"],
            "declared": parsed["declared"],
            "reason": parsed["reason"],
            "must": parsed["must"],
            "may": parsed["may"],
            "must_count": len(parsed["must"]),
            "may_count": len(parsed["may"]),
        },
    )


def cmd_combine(ctx: Ctx, token: str) -> dict[str, Any]:
    """Bildet das Gesamturteil der Runde und führt den Zustandswechsel aus (Spec 001 FR-019)."""
    run = _resolve(ctx, token)
    if run["state"] != "reviewing":
        raise RefusedError(f"combine gilt nur im Zustand reviewing ({run['state']})")
    found: dict[str, dict[str, Any]] = {}
    for role in ctx.review_roles():
        path = _verdict_path(ctx.root, run, role)
        if path.is_file():
            parsed = parse_verdict(path.read_text(encoding="utf-8"), ctx.locale)
            if parsed["valid"]:
                found[role] = parsed
    missing = [r for r in ctx.review_roles() if r not in found]
    if missing:
        raise RefusedError(
            "Urteil fehlt für: " + ", ".join(missing), missing=missing, round=run["round"]
        )
    overall = strongest([v["effective"] for v in found.values()])
    must = [f"[{role}] {item}" for role, v in found.items() for item in v["must"]]
    reasons = [f"[{role}] {v['reason']}" for role, v in found.items() if v["reason"]]
    judged_round = run["round"]
    review_only = run["kind"] == "review_only"

    if overall == "approve":
        _apply(ctx, run, "reviewed" if review_only else "approved")
    elif overall == "changes_requested":
        if not review_only and run["round"] < run["max_rounds"]:
            _apply(ctx, run, "building")
        else:
            reason = (
                f"weiterhin Änderung nach Runde {judged_round}"
                if not review_only
                else "Prüfung ergab Änderungsbedarf"
            )
            gate = None if review_only else "round_limit"
            _apply(ctx, run, "escalated", reason=reason, gate=gate)
    else:
        reason = "; ".join(reasons) or "Mensch prüft"
        _apply(ctx, run, "escalated", reason=reason)
    return _result(
        ctx,
        {
            "run_id": run["run_id"],
            "verdict": overall,
            "judged_round": judged_round,
            "state": run["state"],
            "round": run["round"],
            "must": must,
            "reasons": reasons,
            **_cleanup_links(ctx, run),
        },
    )


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


def cmd_merge(ctx: Ctx, token: str) -> dict[str, Any]:
    """Merged einen freigegebenen Lauf mit ``--no-ff`` in den Basis-Branch. Pusht nie."""
    root = ctx.root
    run = _resolve(ctx, token)
    if run["kind"] != "pipeline":
        raise RefusedError("ein Nur-Prüfung-Lauf wird nicht gemergt")
    if run["state"] != "approved":
        raise RefusedError(f"merge gilt nur für freigegebene Läufe ({run['state']})")
    _require_clean(ctx)
    base, branch = run["base_branch"], run["branch"]
    if git.current_branch(root) != base:
        git.git(root, "switch", base)
    message = f"merge: {run['spec']} via sak pipeline ({run['run_id']})"
    proc = git.run_git(root, "merge", "--no-ff", branch, "-m", message)
    if proc.returncode != 0:
        detail = (proc.stdout + proc.stderr).strip()
        git.run_git(root, "merge", "--abort")
        git.run_git(root, "switch", branch)
        if "CONFLICT" in detail or "conflict" in detail:
            reason = f"Merge-Konflikt: {branch} in {base}"
            _apply(ctx, run, "escalated", reason=reason)
            raise RefusedError(reason, run_id=run["run_id"], state=run["state"])
        raise RefusedError(f"git merge ist fehlgeschlagen: {clip(detail, 300)}")
    commit = git.head(root)
    _apply(ctx, run, "merged", merge_commit=commit)
    return _result(ctx, {**_state_payload(run), "merge_commit": commit, "base_branch": base})


# ---------------------------------------------------------------------------
# list, show, event emit
# ---------------------------------------------------------------------------


def _row(ctx: Ctx, run: dict[str, Any]) -> dict[str, Any]:
    keys = ("run_id", "spec", "kind", "state", "round", "max_rounds", "branch")
    return {
        **{k: run.get(k) for k in keys},
        "started_at": run.get("started_at"),
        "updated_at": run.get("updated_at"),
        **_idle(ctx, run),
    }


def cmd_list(ctx: Ctx, *, include_all: bool = False) -> dict[str, Any]:
    """Offene Läufe (mit ``--all`` auch beendete), neueste zuerst."""
    selected = [
        r
        for r in runs.all_runs(ctx.root)
        if include_all or r.get("state") not in runs.TERMINAL_STATES
    ]
    rows = [_row(ctx, r) for r in reversed(selected)]
    return _result(ctx, {"runs": rows, "stale_runs": _stale_runs(ctx)})


def cmd_show(ctx: Ctx, token: str) -> dict[str, Any]:
    """Ein Lauf mit Verdict-Dateien, offenen Stationen und letzten Events."""
    run = _resolve(ctx, token, include_finished=True)
    directory = runs.run_dir(ctx.root, run["run_id"])
    events = read_events(ctx.root, run["run_id"])
    return _result(
        ctx,
        {
            "run": run,
            **_idle(ctx, run),
            "verdicts": sorted(p.name for p in directory.glob("verdict-*.md")),
            "open_stations": runs.read_json_file(directory / "open-stations.json"),
            "event_count": len(events),
            "last_events": [{"type": e.get("type"), "ts": e.get("ts")} for e in events[-10:]],
        },
    )


def cmd_event_emit(
    ctx: Ctx, etype: str, *, run_token: str | None = None, reason: str | None = None
) -> dict[str, Any]:
    """Schreibt ein Ereignis ohne Zustandswechsel (für Ereignisse ohne eigenen Befehl)."""
    if etype not in _EMITTABLE:
        raise RefusedError(
            f"'{etype}' schreibt die Engine selbst (preflight, verdict, hook); "
            f"erlaubt: {sorted(_EMITTABLE)}"
        )
    if run_token:
        run = _resolve(ctx, run_token)
    else:
        found = runs.active_run(ctx.root)
        if found is None:
            raise RefusedError("kein aktiver Lauf (--run angeben)")
        run = found
    shown = clip(reason) if reason else None
    data: dict[str, Any]
    if etype == "run.escalated":
        data = {"round": run["round"], "reason": shown}
    elif etype == "run.taken_over":
        data = {"reason": shown, "previous_state": run["state"]}
    elif etype == "round.started":
        data = {"round": run["round"]}
    elif etype in {"run.released", "run.returned", "run.paused", "run.aborted"}:
        data = {"reason": shown}
    else:
        data = {}
    try:
        event = emit(ctx.root, etype, project=ctx.project, run=run, **data)
    except EventError as exc:
        raise RefusedError(f"Event ungültig: {exc}") from exc
    return _result(ctx, {"run_id": run["run_id"], "event_id": event["event_id"], "type": etype})
