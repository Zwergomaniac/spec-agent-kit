"""Projektkonfiguration ``.spec-agent/config.yml`` (Spec 004).

``load_config`` liest die Datei als Daten (``safe_load``), prüft sie gegen ``sak.config/1`` und
liefert die wirksame Konfiguration mit Defaults und Kern-Schutz. Secrets liest dieses Modul nie aus
der Config (FR-006); der Dashboard-Schlüssel kommt aus der Umgebung oder aus einer eigenen Datei.
"""

from __future__ import annotations

import copy
import difflib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema.exceptions import ValidationError

from spec_agent_kit import contracts, worktree
from spec_agent_kit.config.defaults import (
    CONFIG_RELATIVE_PATH,
    CORE_CLEAN_IGNORE,
    CORE_PROTECTED,
    DASHBOARD_KEY_RELATIVE_PATH,
    ROLE_ORDER,
    defaults,
)

__all__ = [
    "CONFIG_RELATIVE_PATH",
    "CORE_CLEAN_IGNORE",
    "CORE_PROTECTED",
    "LEGACY_METHOD",
    "AuthModeError",
    "ConfigError",
    "EffectiveConfig",
    "NotInitializedError",
    "build_effective",
    "config_path",
    "deploy_errors",
    "key_source",
    "load_config",
    "read_dashboard_key",
    "read_raw",
    "resolve_auth",
    "schema_errors",
]


class ConfigError(Exception):
    """Die Konfiguration ist ungültig. ``errors`` sind ``{path, message[, suggestion]}``."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        super().__init__("; ".join(f"{e['path']}: {e['message']}" for e in errors))
        self.errors = errors


class AuthModeError(ValueError):
    """``SAK_DASHBOARD_AUTH`` hat einen ungültigen Wert. Die Meldung nennt den Wert nie."""


class NotInitializedError(ConfigError):
    """``.spec-agent/config.yml`` fehlt: das Projekt ist nicht initialisiert."""

    def __init__(self, root: Path) -> None:
        super().__init__(
            [{"path": "<root>", "message": f"nicht initialisiert: {CONFIG_RELATIVE_PATH} fehlt"}]
        )
        self.root = root


@dataclass(frozen=True)
class EffectiveConfig:
    """Wirksame Konfiguration: Projektwerte über Defaults, plus Kern-Schutz."""

    root: Path
    data: dict[str, Any]
    inherited_from: Path | None = None
    """Haupt-Checkout, aus dem Dashboard-Einstellungen eines Worktrees stammen (Spec 011 US3)."""

    def to_dict(self) -> dict[str, Any]:
        """Tiefe Kopie der wirksamen Konfiguration (JSON-fähig)."""
        return copy.deepcopy(self.data)

    def role(self, name: str) -> dict[str, Any]:
        """Wirksame Einstellungen einer Rolle."""
        roles: dict[str, dict[str, Any]] = self.data["pipeline"]["roles"]
        return roles[name]

    def active_roles(self) -> list[str]:
        """Aktive Rollen in Vokabular-Reihenfolge."""
        return [r for r in ROLE_ORDER if self.role(r)["enabled"]]


def config_path(root: Path) -> Path:
    return root / CONFIG_RELATIVE_PATH


def read_raw(root: Path) -> dict[str, Any]:
    """Liest die Config als Daten. Wirft ``NotInitializedError`` oder ``ConfigError``."""
    path = config_path(root)
    if not path.is_file():
        raise NotInitializedError(root)
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ConfigError([{"path": "<root>", "message": f"kein gültiges YAML: {exc}"}]) from exc
    if not isinstance(loaded, dict):
        raise ConfigError([{"path": "<root>", "message": "die Config muss ein Mapping sein"}])
    return loaded


def _dotted(parts: Any) -> str:
    return ".".join(str(p) for p in parts) or "<root>"


def _suggest(word: str, candidates: Any) -> str | None:
    matches = difflib.get_close_matches(word, [str(c) for c in candidates], n=1, cutoff=0.6)
    return matches[0] if matches else None


def _describe(error: ValidationError) -> list[dict[str, str]]:
    base = _dotted(error.absolute_path)
    if error.validator == "additionalProperties" and isinstance(error.instance, dict):
        props = error.schema.get("properties", {})
        entries: list[dict[str, str]] = []
        for key in error.instance:
            if key in props:
                continue
            path = f"{base}.{key}" if base != "<root>" else str(key)
            entry = {"path": path, "message": f"unbekannter Schlüssel '{key}'"}
            hint = _suggest(str(key), props)
            if hint is not None:
                entry["suggestion"] = hint
                entry["message"] += f" (Tippfehler? Meinten Sie '{hint}'?)"
            entries.append(entry)
        return entries
    if error.validator == "anyOf" and all("const" in b for b in error.schema["anyOf"]):
        allowed = ", ".join(str(b["const"]) for b in error.schema["anyOf"])
        message = f"ungültiger Wert {error.instance!r} (erlaubt: {allowed})"
        return [{"path": base, "message": message}]
    if error.validator == "required":
        return [{"path": base, "message": error.message}]
    message = error.message if len(error.message) <= 300 else error.message[:297] + "..."
    return [{"path": base, "message": message}]


_METHOD_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
LEGACY_METHOD = "default"
"""Name des Wegs, zu dem das alte ``deploy.command`` wird (Spec 014 FR-001)."""


def deploy_errors(raw: Any) -> list[dict[str, str]]:
    """Regeln zu ``deploy``, die das Schema nicht ausdrückt (Spec 014 FR-001, SC-002)."""
    deploy = raw.get("deploy") if isinstance(raw, dict) else None
    if not isinstance(deploy, dict) or "methods" not in deploy:
        if isinstance(deploy, dict) and deploy.get("default") is not None:
            return [{"path": "deploy.default", "message": "deploy.default braucht deploy.methods"}]
        return []
    errors: list[dict[str, str]] = []
    methods = deploy["methods"]
    if deploy.get("command") is not None:
        errors.append(
            {
                "path": "deploy.command",
                "message": "deploy.command und deploy.methods gleichzeitig sind ungültig "
                "(entweder die alte Form oder benannte Wege)",
            }
        )
    for name in methods:
        if not _METHOD_NAME.match(str(name)):
            errors.append(
                {
                    "path": f"deploy.methods.{name}",
                    "message": "ungültiger Name (erlaubt: a-z, 0-9, _ und -, Buchstabe zuerst)",
                }
            )
    default = deploy.get("default")
    if default is not None and default not in methods:
        known = ", ".join(sorted(str(n) for n in methods)) or "keine"
        errors.append(
            {
                "path": "deploy.default",
                "message": f"unbekannter Weg '{default}' (bekannt: {known})",
            }
        )
    elif default is None and len(methods) > 1:
        errors.append(
            {
                "path": "deploy.default",
                "message": "bei mehreren Wegen muss deploy.default einen davon nennen",
            }
        )
    return errors


def schema_errors(raw: Any) -> list[dict[str, str]]:
    """Alle Schemaverstöße als ``{path, message[, suggestion]}``."""
    if isinstance(raw, dict) and "agent_environment" not in raw:
        raw = {**raw, "agent_environment": "claude"}
    result: list[dict[str, str]] = []
    for error in contracts.config_schema_errors(raw):
        result.extend(_describe(error))
    if not result:
        result.extend(deploy_errors(raw))
    return result


def _normalize_deploy(deploy: dict[str, Any]) -> dict[str, Any]:
    """Bringt ``deploy`` auf die eine wirksame Form: ``command`` (alt), ``methods``, ``default``.

    Die Altform ``deploy.command`` wird zum Weg ``default`` mit ``marker: agent``.
    """
    methods_raw = deploy.get("methods")
    if methods_raw:
        methods = {
            str(name): {
                "command": spec["command"],
                "marker": spec.get("marker", "agent"),
                "local_only": bool(spec.get("local_only", False)),
            }
            for name, spec in methods_raw.items()
        }
        default = deploy.get("default") or next(iter(methods))
        return {"command": None, "methods": methods, "default": default}
    command = deploy.get("command")
    if command:
        legacy = {"command": command, "marker": "agent", "local_only": False}
        return {"command": command, "methods": {LEGACY_METHOD: legacy}, "default": LEGACY_METHOD}
    return {"command": None, "methods": {}, "default": None}


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _prepend_unique(core: tuple[str, ...], extra: list[str]) -> list[str]:
    result = list(core)
    result.extend(item for item in extra if item not in core)
    return list(dict.fromkeys(result))


def build_effective(root: Path, raw: Mapping[str, Any]) -> EffectiveConfig:
    """Mischt ``raw`` über die Defaults. Setzt Kern-Schutz und ``dashboard.push``."""
    data = _deep_merge(defaults(), raw)
    guard = data["guard"]
    guard["protected_paths"] = _prepend_unique(CORE_PROTECTED, list(guard["protected_paths"]))
    guard["clean_ignore"] = _prepend_unique(CORE_CLEAN_IGNORE, list(guard["clean_ignore"]))
    data["deploy"] = _normalize_deploy(data["deploy"])
    dashboard = data["dashboard"]
    if "push" not in dashboard:
        dashboard["push"] = "auto" if dashboard["url"] else "manual"
    data["pipeline"]["roles"] = {r: data["pipeline"]["roles"][r] for r in ROLE_ORDER}
    return EffectiveConfig(root=root, data=data)


def _inherit_dashboard(root: Path, raw: dict[str, Any]) -> tuple[dict[str, Any], Path | None]:
    """Ergänzt ``dashboard.url`` und ``dashboard.push`` aus dem Haupt-Checkout (nur in Worktrees).

    Eigene Werte des Worktrees haben Vorrang; es wird nur gefüllt, was dort fehlt oder ``null`` ist.
    Fehler beim Lesen der Haupt-Config führen nie zu einem Abbruch (dann bleibt es beim Eigenen).
    """
    main = worktree.main_checkout(root)
    if main is None:
        return raw, None
    section = raw.get("dashboard")
    own = section if isinstance(section, dict) else {}
    if own.get("url"):
        return raw, None
    try:
        main_raw = read_raw(main)
    except ConfigError:
        return raw, None
    main_section = main_raw.get("dashboard")
    if not isinstance(main_section, dict) or not main_section.get("url"):
        return raw, None
    merged = {**own, "url": main_section["url"]}
    if "push" not in merged and "push" in main_section:
        merged["push"] = main_section["push"]
    if "auth" not in merged and "auth" in main_section:
        merged["auth"] = main_section["auth"]
    return {**raw, "dashboard": merged}, main


def load_config(root: Path) -> EffectiveConfig:
    """Lädt und prüft die Config. Wirft ``NotInitializedError`` oder ``ConfigError``.

    In einem Git-Worktree werden fehlende Dashboard-Einstellungen aus dem Haupt-Checkout geerbt.
    """
    raw = read_raw(root)
    errors = schema_errors(raw)
    if errors:
        raise ConfigError(errors)
    raw, inherited = _inherit_dashboard(root, raw)
    effective = build_effective(root, raw)
    if inherited is None:
        return effective
    return EffectiveConfig(root=effective.root, data=effective.data, inherited_from=inherited)


def key_source(
    root: Path, config: EffectiveConfig, env: Mapping[str, str] | None = None
) -> str | None:
    """Woher der Schlüssel käme: ``env``, ``file``, ``main_checkout`` (Worktree) oder ``None``."""
    environment = os.environ if env is None else env
    if environment.get(config.data["dashboard"]["token_env"], "").strip():
        return "env"
    if _read_key_file(root / DASHBOARD_KEY_RELATIVE_PATH):
        return "file"
    main = worktree.main_checkout(root)
    if main is not None and _read_key_file(main / DASHBOARD_KEY_RELATIVE_PATH):
        return "main_checkout"
    return None


def _read_key_file(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip() or None if path.is_file() else None
    except (OSError, UnicodeDecodeError):
        return None


def read_dashboard_key(
    root: Path, config: EffectiveConfig, env: Mapping[str, str] | None = None
) -> str | None:
    """Dashboard-Schlüssel aus ``token_env``, ``.spec-agent/dashboard.key`` oder dem Haupt-Checkout.

    Die Config enthält nur den Namen der Variablen, nie den Schlüssel selbst. In einem
    Git-Worktree fehlt die gitignorierte Schlüsseldatei; dort gilt die des Haupt-Checkouts
    (Spec 011 US3). Der Schlüssel des Worktrees hat immer Vorrang.
    """
    environment = os.environ if env is None else env
    value = environment.get(config.data["dashboard"]["token_env"], "").strip()
    if value:
        return value
    own = _read_key_file(root / DASHBOARD_KEY_RELATIVE_PATH)
    if own:
        return own
    main = worktree.main_checkout(root)
    return _read_key_file(main / DASHBOARD_KEY_RELATIVE_PATH) if main is not None else None


def resolve_auth(config: EffectiveConfig, env: Mapping[str, str] | None = None) -> tuple[str, str]:
    """Der Auth-Modus ``key`` oder ``proxy`` und seine Quelle (``env`` oder ``config``).

    ``SAK_DASHBOARD_AUTH`` hat Vorrang vor ``dashboard.auth`` (Spec 013 FR-002). Ein ungültiger
    Wert wirft ``AuthModeError``, ohne den Wert zu nennen.
    """
    environment = os.environ if env is None else env
    value = environment.get("SAK_DASHBOARD_AUTH", "").strip()
    if value:
        if value not in {"key", "proxy"}:
            raise AuthModeError("SAK_DASHBOARD_AUTH ist ungültig: erlaubt sind key und proxy")
        return value, "env"
    return str(config.data["dashboard"].get("auth", "key")), "config"
