"""``sak deploy plan``: löst einen Deploy-Weg auf, ohne etwas auszuführen (Spec 014).

Der Befehl wird nie gestartet. Die Ausgabe sagt dem Orchestrator, welcher Befehl (mit ersetztem
``{spec}``) zu welchem Weg gehört, wer den Marker setzt und ob der Weg hier erlaubt ist.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from spec_agent_kit.config import EffectiveConfig
from spec_agent_kit.pipeline import RefusedError, UsageError
from spec_agent_kit.push.cloud import detect_environment

_SPEC_TOKEN = re.compile(r"^([0-9]{1,3})(?:-.*)?$")
_RUN_TOKEN = re.compile(r"^([0-9]{3})-[0-9]{8}-[0-9]{6}")


def spec_numbers(tokens: list[str]) -> str:
    """Spec-Nummern aus Lauf-ID, Spec-Verzeichnis oder Nummer, komma-getrennt (``084,085``)."""
    numbers: list[str] = []
    for token in (part.strip() for item in tokens for part in item.split(",")):
        match = _RUN_TOKEN.match(token) or _SPEC_TOKEN.match(token)
        if match is None:
            raise UsageError(f"keine Lauf-ID oder Spec: '{token}'")
        number = match.group(1).zfill(3)
        if number not in numbers:
            numbers.append(number)
    if not numbers:
        raise UsageError("keine Spec angegeben")
    return ",".join(numbers)


def plan(
    config: EffectiveConfig,
    tokens: list[str],
    method: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Der Plan als JSON-fähiges Dict. Wirft ``RefusedError`` bei unbekanntem oder fehlendem Weg."""
    deploy = config.data["deploy"]
    methods: dict[str, dict[str, Any]] = deploy["methods"]
    if not methods:
        raise RefusedError("kein Deploy-Weg konfiguriert (deploy.command oder deploy.methods)")
    name = method or deploy["default"]
    if name not in methods:
        raise RefusedError(
            f"unbekannter Deploy-Weg '{name}'", known=sorted(methods), default=deploy["default"]
        )
    try:
        environment, source = detect_environment(env)
    except ValueError as exc:
        raise UsageError(str(exc)) from exc
    chosen = methods[name]
    specs = spec_numbers(tokens)
    allowed, reason = True, None
    if config.data["autonomy"]["deploy"] == "never":
        allowed, reason = False, "autonomy.deploy ist never: Deploy nur durch den Betreiber"
    elif chosen["local_only"] and environment == "cloud":
        allowed = False
        reason = (
            f"Weg '{name}' ist nur lokal erlaubt (local_only): er braucht Zugriff vom Rechner "
            "des Betreibers (zum Beispiel SSH), in der Cloud-Sitzung nicht verfügbar"
        )
    alternatives = [
        n
        for n, m in methods.items()
        if n != name and not (m["local_only"] and environment == "cloud")
    ]
    result = {
        "ok": allowed,
        "method": name,
        "command": chosen["command"].replace("{spec}", specs),
        "marker": chosen["marker"],
        "allowed": allowed,
        "reason": reason,
        "specs": specs,
        "environment": environment,
        "environment_source": source,
    }
    if not allowed and alternatives and config.data["autonomy"]["deploy"] != "never":
        result["alternatives"] = alternatives
    return result
