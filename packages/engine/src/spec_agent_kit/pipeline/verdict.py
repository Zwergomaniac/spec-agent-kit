"""Urteilsformat der Prüfer (Spec 003 FR-009, Spec 001 FR-017 bis FR-019).

Erste Zeile ``Verdict: approve|changes_requested|needs_human``. Bei Locale ``de`` ist zusätzlich
``Urteil: OK|Änderung|Mensch prüft`` erlaubt. Grund in den Zeilen 2 bis 4, Befunde als
``- [must|may] datei:zeile — … → …`` (bei ``de`` auch ``[Muss]`` und ``[Kann]``).
"""

from __future__ import annotations

import re
from typing import Any, Final

RANK: Final[dict[str, int]] = {"approve": 0, "changes_requested": 1, "needs_human": 2}

_VERDICT_EN = re.compile(r"^Verdict:\s*(approve|changes_requested|needs_human)\s*$")
_VERDICT_DE = re.compile(r"^Urteil:\s*(OK|Änderung|Mensch prüft)\s*$")
_DE_VALUES: Final[dict[str, str]] = {
    "OK": "approve",
    "Änderung": "changes_requested",
    "Mensch prüft": "needs_human",
}
_REASON = re.compile(r"^(?:Reason|Grund):\s*(\S.*?)\s*$")
_FINDING_EN = re.compile(r"^\s*-\s*\[(must|may)\]\s*(\S.*?)\s*$")
_FINDING_DE = re.compile(r"^\s*-\s*\[(must|may|Muss|Kann)\]\s*(\S.*?)\s*$")
_DE_SEVERITY: Final[dict[str, str]] = {"Muss": "must", "Kann": "may"}


def strongest(verdicts: list[str]) -> str:
    """Stärkstes Einzelurteil (``approve < changes_requested < needs_human``)."""
    return max(verdicts, key=lambda v: RANK[v])


def parse_verdict(text: str, locale: str = "de") -> dict[str, Any]:
    """Prüft und zerlegt eine Prüfer-Antwort.

    Gültig: ``{valid: True, declared, effective, reason, must[], may[]}``.
    Ungültig: ``{valid: False, error}``. ``effective`` ist ``changes_requested``, wenn ein
    ``approve`` einen Muss-Befund enthält.
    """
    lines = text.lstrip("﻿").splitlines()
    first = lines[0] if lines else ""
    declared: str | None = None
    match = _VERDICT_EN.match(first)
    if match:
        declared = match.group(1)
    elif locale == "de":
        match_de = _VERDICT_DE.match(first)
        if match_de:
            declared = _DE_VALUES[match_de.group(1)]
    if declared is None:
        return {"valid": False, "error": "erste Zeile ist kein gültiges Urteil"}

    reason = ""
    for line in lines[1:4]:
        found = _REASON.match(line)
        if found:
            reason = found.group(1)
            break

    finding = _FINDING_DE if locale == "de" else _FINDING_EN
    must: list[str] = []
    may: list[str] = []
    for line in lines[1:]:
        found = finding.match(line)
        if found:
            severity = _DE_SEVERITY.get(found.group(1), found.group(1))
            (must if severity == "must" else may).append(found.group(2))

    if declared in {"changes_requested", "needs_human"} and not reason:
        return {"valid": False, "error": f"'{declared}' braucht eine Grund-Zeile (Reason:/Grund:)"}
    if declared == "changes_requested" and not must:
        return {
            "valid": False,
            "error": "'changes_requested' braucht mindestens einen [must]-Befund",
        }
    effective = "changes_requested" if declared == "approve" and must else declared
    return {
        "valid": True,
        "declared": declared,
        "effective": effective,
        "reason": reason,
        "must": must,
        "may": may,
    }
