"""Dashboard-Anbindung des Zielprojekts: ``sak dashboard connect`` und ``sak dashboard status``.

Spec 009 US4, FR-005. Der Projekt-Schlüssel wird nie ausgegeben, nie geloggt und nie in die Config
geschrieben; er liegt nur in ``.spec-agent/dashboard.key`` (Rechte 600 unter POSIX).
"""

from __future__ import annotations

import contextlib
import difflib
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

from spec_agent_kit.config import (
    CONFIG_RELATIVE_PATH,
    ConfigError,
    NotInitializedError,
    key_source,
    load_config,
    schema_errors,
)
from spec_agent_kit.config.defaults import DASHBOARD_KEY_RELATIVE_PATH
from spec_agent_kit.install.plan import validate_url
from spec_agent_kit.push import outbox

KEY_RE: Final = re.compile(r"^sak_[A-Za-z0-9_-]{43}$")
KEY_FORMAT_HINT: Final[str] = "Format: sak_ gefolgt von 43 Zeichen aus A-Z, a-z, 0-9, - und _"
_BLOCK_RE: Final = re.compile(r"^dashboard:[ \t]*(#.*)?$")
_URL_RE: Final = re.compile(
    r"^(?P<head>[ \t]+url:[ \t]*)(?P<value>[^\s#][^#]*?)?(?P<tail>[ \t]*#.*)?$"
)

Poster = Callable[..., tuple[int, dict[str, Any]]]


class ConnectError(Exception):
    """Fachliche Ablehnung (Exit 1). Die Meldung enthält nie den Schlüssel."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(message)
        self.path = path
        self.message = message


def validate_key_format(key: str) -> str | None:
    """Prüft das Format, ohne den Schlüssel zu nennen. ``None`` heißt gültig."""
    if KEY_RE.fullmatch(key) is None:
        return f"ungültiger Schlüssel: {KEY_FORMAT_HINT}"
    return None


# ---------------------------------------------------------------------------
# Config-Änderung (zeilenbasiert, Kommentare bleiben)
# ---------------------------------------------------------------------------


@dataclass
class ConfigEdit:
    """Ergebnis von ``set_dashboard_url``: neuer Text, bisheriger Wert und Art der Änderung."""

    text: str
    old_url: str | None
    action: str  # "change" | "insert" | "append" | "unchanged"
    diff: list[str] = field(default_factory=list)


def _newline_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _unquote(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return None if value in {"", "null", "~"} else value


def set_dashboard_url(text: str, url: str) -> ConfigEdit:
    """Setzt ``dashboard.url`` zeilenbasiert. Wirft ``ConnectError``, wenn die Form nicht passt.

    Nur die erste ``url:``-Zeile im Block ``dashboard:`` ändert sich; fehlt sie, wird sie direkt
    nach ``dashboard:`` eingefügt, fehlt der Block, wird er angehängt. Kommentare und
    Zeilenenden bleiben erhalten.
    """
    nl = _newline_of(text)
    lines = text.splitlines(keepends=True)
    block = next((i for i, line in enumerate(lines) if _BLOCK_RE.match(line.rstrip("\r\n"))), None)
    if block is None:
        if re.search(r"^dashboard:\s*\S", text, re.MULTILINE):
            raise ConnectError(
                CONFIG_RELATIVE_PATH,
                "dashboard ist nicht als Block geschrieben; bitte url von Hand eintragen",
            )
        lead = "" if not text or text.endswith(("\n", "\r")) else nl
        new_lines = [*lines, f"{lead}{nl}dashboard:{nl}", f"  url: {url}{nl}"]
        return _finish(text, new_lines, None, "append")
    found: int | None = None
    child_indent = "  "
    for i in range(block + 1, len(lines)):
        raw = lines[i].rstrip("\r\n")
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw[0].isspace():
            break  # nächster Block der obersten Ebene
        if found is None:
            child_indent = raw[: len(raw) - len(raw.lstrip())]
        if re.match(r"^[ \t]+url:", raw):
            found = i
            break
    if found is None:
        new_lines = [*lines]
        new_lines.insert(block + 1, f"{child_indent}url: {url}{nl}")
        return _finish(text, new_lines, None, "insert")
    raw = lines[found].rstrip("\r\n")
    match = _URL_RE.match(raw)
    if match is None:
        raise ConnectError(CONFIG_RELATIVE_PATH, "die url-Zeile hat eine unerwartete Form")
    value = match.group("value")
    old = _unquote(value)
    if value is not None and value.strip()[:1] in {"|", ">", "&", "*", "[", "{"}:
        raise ConnectError(CONFIG_RELATIVE_PATH, "die url-Zeile hat eine unerwartete Form")
    ending = lines[found][len(raw) :]
    tail = match.group("tail") or ""
    new_lines = [*lines]
    new_lines[found] = f"{match.group('head')}{url}{tail}{ending}"
    return _finish(text, new_lines, old, "unchanged" if old == url else "change")


def _finish(old_text: str, new_lines: list[str], old_url: str | None, action: str) -> ConfigEdit:
    new_text = "".join(new_lines)
    diff = list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=CONFIG_RELATIVE_PATH,
            tofile=CONFIG_RELATIVE_PATH,
            lineterm="",
            n=1,
        )
    )
    return ConfigEdit(text=new_text, old_url=old_url, action=action, diff=diff)


def _config_errors_of(text: str) -> list[dict[str, str]]:
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [{"path": "<root>", "message": f"kein gültiges YAML: {exc}"}]
    if not isinstance(loaded, dict):
        return [{"path": "<root>", "message": "die Config muss ein Mapping sein"}]
    return schema_errors(loaded)


# ---------------------------------------------------------------------------
# Schlüsseldatei
# ---------------------------------------------------------------------------


def key_file(root: Path) -> Path:
    return root / DASHBOARD_KEY_RELATIVE_PATH


def write_key_file(root: Path, key: str) -> None:
    """Schreibt die Schlüsseldatei atomar; unter POSIX mit Rechten 600 vom ersten Byte an."""
    path = key_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".sak-tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(key + "\n")
        if os.name != "nt":
            temp.chmod(0o600)
        os.replace(temp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            temp.unlink()
        raise


def key_file_ignored(root: Path) -> bool | None:
    """``True``/``False`` laut ``git check-ignore``; ``None``, wenn git nicht antworten kann."""
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", DASHBOARD_KEY_RELATIVE_PATH],
            cwd=root,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode == 0:
        return True
    return False if proc.returncode == 1 else None


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------


def _plan_document(root: Path, edit: ConfigEdit, url: str, exists: bool, checked: bool) -> dict:
    return {
        "ok": True,
        "mode": "plan",
        "command": "dashboard connect",
        "config": {
            "path": CONFIG_RELATIVE_PATH,
            "action": edit.action,
            "url_from": edit.old_url,
            "url_to": url,
            "diff": edit.diff,
        },
        "key_file": {
            "path": DASHBOARD_KEY_RELATIVE_PATH,
            "action": "replace" if exists else "create",
            "format_checked": checked,
        },
        "next": "mit --yes anwenden (Schlüssel per --key-stdin oder verdeckter Eingabe)",
    }


def connect(
    root: Path,
    url: str,
    *,
    yes: bool,
    force: bool,
    read_key: Callable[[], str] | None,
    key_from_stdin: bool,
    test_push: bool = True,
    push_fn: Poster | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Plan oder Umsetzung von ``sak dashboard connect``. Gibt ``(Exit-Code, Antwort)`` zurück.

    ``read_key`` liefert den Schlüssel (``getpass`` oder stdin). Ohne ``yes`` wird er nur gelesen,
    wenn ``key_from_stdin`` gesetzt ist, und nur auf sein Format geprüft; geschrieben wird nichts.
    """
    try:
        return _connect(
            root,
            url,
            yes=yes,
            force=force,
            read_key=read_key,
            key_from_stdin=key_from_stdin,
            test_push=test_push,
            push_fn=push_fn,
            env=env,
        )
    except ConnectError as exc:
        return 1, {"ok": False, "errors": [{"path": exc.path, "message": exc.message}]}


def _connect(
    root: Path,
    url: str,
    *,
    yes: bool,
    force: bool,
    read_key: Callable[[], str] | None,
    key_from_stdin: bool,
    test_push: bool,
    push_fn: Poster | None,
    env: Mapping[str, str] | None,
) -> tuple[int, dict[str, Any]]:
    config_path = root / CONFIG_RELATIVE_PATH
    try:
        load_config(root)
    except NotInitializedError as exc:
        raise ConnectError("<root>", "nicht initialisiert: .spec-agent/config.yml fehlt") from exc
    except ConfigError as exc:
        first = exc.errors[0]
        raise ConnectError(
            first["path"], f"die Config ist ungültig, zuerst `sak config check`: {first['message']}"
        ) from exc
    url = url.strip().rstrip("/")
    problem = validate_url(url)
    if problem:
        raise ConnectError("--url", problem)

    exists = key_file(root).exists()
    if exists and not force:
        raise ConnectError(
            DASHBOARD_KEY_RELATIVE_PATH,
            "existiert bereits: mit --force ersetzen (der bisherige Schlüssel geht verloren)",
        )
    ignored = key_file_ignored(root)
    if ignored is False:
        raise ConnectError(
            DASHBOARD_KEY_RELATIVE_PATH,
            "ist nicht gitignored: `sak upgrade` ausführen oder dashboard.key in "
            ".spec-agent/.gitignore eintragen",
        )

    original = config_path.read_bytes()
    original_text = original.decode("utf-8")
    edit = set_dashboard_url(original_text, url)

    key: str | None = None
    if (yes or key_from_stdin) and read_key is not None:
        key = read_key().strip()
        message = validate_key_format(key)
        if message:
            raise ConnectError(DASHBOARD_KEY_RELATIVE_PATH, message)

    if not yes:
        errors = _config_errors_of(edit.text)
        if errors:
            raise ConnectError(
                errors[0]["path"], "die Config wäre danach ungültig: " + errors[0]["message"]
            )
        plan = _plan_document(root, edit, url, exists, key is not None)
        if ignored is None:
            plan["warnings"] = ["gitignore-Status von dashboard.key nicht prüfbar (git fehlt?)"]
        return 0, plan

    if key is None:
        raise ConnectError(DASHBOARD_KEY_RELATIVE_PATH, "kein Schlüssel angegeben")
    return _apply(root, url, edit, original, key, exists, test_push, push_fn, env, ignored)


def _apply(
    root: Path,
    url: str,
    edit: ConfigEdit,
    original: bytes,
    key: str,
    replaced: bool,
    test_push: bool,
    push_fn: Poster | None,
    env: Mapping[str, str] | None,
    ignored: bool | None,
) -> tuple[int, dict[str, Any]]:
    config_path = root / CONFIG_RELATIVE_PATH
    config_path.write_bytes(edit.text.encode("utf-8"))  # Bytes: Zeilenenden bleiben erhalten
    try:
        errors = _config_errors_of(config_path.read_text(encoding="utf-8"))
        if errors:
            raise ConnectError(
                errors[0]["path"], "die Config wäre danach ungültig: " + errors[0]["message"]
            )
        try:
            write_key_file(root, key)
        except OSError as exc:
            raise ConnectError(
                DASHBOARD_KEY_RELATIVE_PATH, f"nicht schreibbar: {exc.strerror}"
            ) from exc
    except BaseException:
        config_path.write_bytes(original)  # Rollback: die Config bleibt, wie sie war
        raise

    result: dict[str, Any] = {
        "ok": True,
        "mode": "applied",
        "command": "dashboard connect",
        "config": {
            "path": CONFIG_RELATIVE_PATH,
            "action": edit.action,
            "url_from": edit.old_url,
            "url_to": url,
        },
        "key_file": {
            "path": DASHBOARD_KEY_RELATIVE_PATH,
            "action": "replaced" if replaced else "created",
        },
    }
    warnings: list[str] = []
    if ignored is None:
        warnings.append("gitignore-Status von dashboard.key nicht prüfbar (git fehlt?)")
    from spec_agent_kit.config.check import check as check_config

    check = check_config(root)
    result["config_check"] = {"ok": bool(check["ok"]), "errors": check["errors"]}
    token_env = load_config(root).data["dashboard"]["token_env"]
    if (os.environ if env is None else env).get(token_env, "").strip():
        warnings.append(
            f"die Umgebungsvariable {token_env} ist gesetzt und hat beim Push Vorrang vor der Datei"
        )
    ok = bool(check["ok"])
    if test_push:
        from spec_agent_kit.push.run import push

        sender = push_fn or push
        # Leere Umgebung: der Test-Push nutzt sicher den eben geschriebenen Schlüssel.
        code, outcome = sender(root, env={})
        result["test_push"] = _scrub(outcome, key)
        ok = ok and code == 0
    else:
        result["test_push"] = {"status": "skipped", "message": "übersprungen (--no-test-push)"}
    if warnings:
        result["warnings"] = warnings
    result["ok"] = ok
    return (0 if ok else 1), result


def _scrub(value: Any, key: str) -> Any:
    """Entfernt den Schlüssel aus einer Antwort (Absicherung; die Push-Fehler nennen ihn nie)."""
    if isinstance(value, str):
        return value.replace(key, "***")
    if isinstance(value, list):
        return [_scrub(v, key) for v in value]
    if isinstance(value, dict):
        return {k: _scrub(v, key) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def status(root: Path, env: Mapping[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    """``sak dashboard status``: URL, Schlüssel vorhanden (nie der Schlüssel), Modus, Cursor."""
    try:
        cfg = load_config(root)
    except NotInitializedError:
        return 1, {
            "ok": False,
            "errors": [
                {"path": "<root>", "message": "nicht initialisiert: .spec-agent/config.yml fehlt"}
            ],
        }
    except ConfigError as exc:
        return 1, {"ok": False, "errors": exc.errors}
    dashboard = cfg.data["dashboard"]
    environment = os.environ if env is None else env
    source = key_source(root, cfg, environment)
    cursor = outbox.read_cursor(root)
    return 0, {
        "ok": True,
        "url": dashboard["url"],
        "key": {
            "present": source is not None,
            "source": source,
            "env_var": dashboard["token_env"],
            "file": DASHBOARD_KEY_RELATIVE_PATH,
        },
        "push": dashboard["push"],
        "cursor": {
            "offset": cursor.offset,
            "last_push_at": cursor.last_push_at,
            "last_error": cursor.last_error,
        },
    }
