"""Cloud- und Proxy-Hilfen für den Push-Client (Spec 013).

Alles hier ändert nur Meldungen und die TLS-Vertrauenskette, nie die Schutzregeln des Clients.
Von den Proxy-Variablen wird nur genannt, ob sie gesetzt sind; ihre Werte können Zugangsdaten
enthalten und erscheinen nirgends.
"""

from __future__ import annotations

import os
import ssl
from collections.abc import Mapping
from pathlib import Path
from typing import Final

PROXY_VARS: Final[tuple[str, ...]] = ("HTTPS_PROXY", "https_proxy")
CA_VARS: Final[tuple[str, ...]] = ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE")
AUTH_ENV: Final[str] = "SAK_DASHBOARD_AUTH"
AUTH_MODES: Final[tuple[str, ...]] = ("key", "proxy")

_TUNNEL_MARKER: Final[str] = "tunnel connection failed"


def proxy_vars_set(env: Mapping[str, str] | None = None) -> list[str]:
    """Namen der gesetzten Proxy-Variablen (nie ihre Werte)."""
    environment = os.environ if env is None else env
    return [name for name in PROXY_VARS if environment.get(name, "").strip()]


def proxy_context(env: Mapping[str, str] | None = None) -> str:
    """Kontextzeile für Meldungen, z. B. ``(HTTPS_PROXY gesetzt)``; leer ohne Proxy."""
    names = proxy_vars_set(env)
    return (" (" + ", ".join(f"{n} gesetzt" for n in names) + ")") if names else ""


def ca_bundle(env: Mapping[str, str] | None = None) -> Path | None:
    """CA-Bundle aus ``SSL_CERT_FILE`` bzw. ``REQUESTS_CA_BUNDLE`` (nur als vorhandene Datei)."""
    environment = os.environ if env is None else env
    for name in CA_VARS:
        value = environment.get(name, "").strip()
        if value and Path(value).is_file():
            return Path(value)
    return None


def ssl_context(env: Mapping[str, str] | None = None) -> ssl.SSLContext | None:
    """System-Store plus Bundle aus der Umgebung; ``None``, wenn keine Variable greift (FR-004)."""
    bundle = ca_bundle(env)
    if bundle is None:
        return None
    context = ssl.create_default_context()
    try:
        context.load_verify_locations(cafile=str(bundle))
    except (OSError, ssl.SSLError):
        return None  # unbrauchbares Bundle: Verhalten wie ohne Variable
    return context


def is_proxy_rejection(exc: BaseException) -> bool:
    """Der Proxy hat den Tunnel (CONNECT) abgelehnt: ``Tunnel connection failed: 403 ...``."""
    text = str(getattr(exc, "reason", exc)).lower()
    return _TUNNEL_MARKER in text and "403" in text


def is_cert_error(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, ssl.SSLCertVerificationError) or (
        isinstance(reason, ssl.SSLError) and "certificate" in str(reason).lower()
    )


def explain(exc: BaseException, host: str, env: Mapping[str, str] | None = None) -> str | None:
    """Erklärt typische Cloud-Fehler; ``None``, wenn der Fehler nicht dazu passt (FR-006)."""
    if is_proxy_rejection(exc) and proxy_vars_set(env):
        return (
            f"Netzzugriff der Cloud-Umgebung erlaubt {host} nicht: Network access auf Custom "
            f"stellen und {host} eintragen, oder ein Network Secret für {host} anlegen "
            f"(umgeht die Allowlist){proxy_context(env)}"
        )
    if is_cert_error(exc):
        return (
            f"TLS-Zertifikat von {host} nicht vertrauenswürdig: hinter einem Proxy das "
            "CA-Bundle über SSL_CERT_FILE oder REQUESTS_CA_BUNDLE angeben"
            f"{proxy_context(env)}"
        )
    return None


def no_network_secret_message(host: str) -> str:
    return f"Kein Network Secret für {host} in der Cloud-Umgebung hinterlegt (Typ Bearer)"


def proxy_mode_hint(env: Mapping[str, str] | None = None) -> str:
    """Zusatzhinweis für Modus ``key`` ohne Schlüssel, falls ein Proxy gesetzt ist."""
    if not proxy_vars_set(env):
        return ""
    return (
        "; in einer Cloud-Umgebung hinter Proxy: Network Secret anlegen und "
        f"{AUTH_ENV}=proxy setzen (docs/cloud.md)"
    )


ENVIRONMENT_ENV: Final[str] = "SAK_ENVIRONMENT"
ENVIRONMENTS: Final[tuple[str, ...]] = ("cloud", "local")


def detect_environment(env: Mapping[str, str] | None = None) -> tuple[str, str]:
    """``(cloud|local, Quelle)``. ``SAK_ENVIRONMENT`` übersteuert die Proxy-Heuristik (Spec 014).

    Quelle ist ``env`` (ausdrückliche Übersteuerung) oder ``heuristic``. Ein ungültiger Wert
    wirft ``ValueError``, ohne den Wert zu nennen.
    """
    environment = os.environ if env is None else env
    value = environment.get(ENVIRONMENT_ENV, "").strip()
    if value:
        if value not in ENVIRONMENTS:
            raise ValueError(f"{ENVIRONMENT_ENV} ist ungültig: erlaubt sind cloud und local")
        return value, "env"
    return ("cloud" if proxy_vars_set(environment) else "local"), "heuristic"
