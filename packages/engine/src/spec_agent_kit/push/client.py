"""HTTP-Client für ``POST <dashboard.url>/api/ingest`` (Spec 006 FR-009, FR-012).

Nur Standardbibliothek (``urllib``). Fehler werden in Klassen übersetzt, aus denen ``push.run``
entscheidet, ob der Cursor vorrückt (nie bei Netz-, Auth- und Versionsfehlern). Der Schlüssel steht
nur im ``Authorization``-Header und nie in einer Fehlermeldung. Weiterleitungen folgt der Client
nicht, damit der Schlüssel keinen anderen Host erreicht.
"""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from typing import Any, Final
from urllib.parse import urlsplit

from spec_agent_kit import contracts

TIMEOUT_S: Final[float] = 3.0
INGEST_PATH: Final[str] = "/api/ingest"
_LOCAL_HTTP_HOSTS: Final[frozenset[str]] = frozenset({"localhost", "127.0.0.1"})
_MAX_ERROR_BODY: Final[int] = 65536
_MAX_RESPONSE: Final[int] = 1_000_000
VERSION_MARKERS: Final[tuple[str, ...]] = ("unsupported schema version", "unknown event type")
"""Antworttexte des Dashboards, die auf einen Versionsunterschied hinweisen (Spec 002 US4)."""


class PushError(Exception):
    """Basis der Push-Fehler. ``status`` ist ein stabiler Kurzname für die JSON-Ausgabe."""

    status = "error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InsecureUrlError(PushError):
    """``dashboard.url`` verletzt FR-012 (kein HTTPS, kein lokaler Host) oder ist ungültig."""

    status = "insecure_url"


class NetworkError(PushError):
    """Dashboard nicht erreichbar, Zeitüberschreitung, 429 oder 5xx. Später erneut versuchen."""

    status = "unreachable"


class AuthError(PushError):
    """401 oder 403: der Schlüssel passt nicht zum Projekt."""

    status = "unauthorized"


class VersionError(PushError):
    """Dashboard und Projekt sprechen verschiedene Vertragsversionen (Dashboard zuerst updaten)."""

    status = "version_mismatch"


class RequestRejected(PushError):
    """Das Dashboard lehnt die ganze Anfrage ab (400, 404, 413 ...). Cursor bleibt stehen."""

    status = "rejected"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def check_url(base: str) -> str:
    """Prüft ``dashboard.url`` und gibt die Ingest-URL zurück.

    HTTPS ist Pflicht, außer bei ``http://localhost`` und ``http://127.0.0.1``.
    """
    parts = urlsplit(base)
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or not host:
        raise InsecureUrlError(f"dashboard.url ist keine gültige URL: {base!r}")
    if parts.username or parts.password:
        raise InsecureUrlError("dashboard.url darf keine Zugangsdaten enthalten")
    if parts.scheme == "http" and host not in _LOCAL_HTTP_HOSTS:
        raise InsecureUrlError(
            "dashboard.url muss HTTPS nutzen (HTTP nur für localhost und 127.0.0.1)"
        )
    path = parts.path.rstrip("/")
    return f"{parts.scheme}://{parts.netloc}{path}{INGEST_PATH}"


def _opener(url: str) -> urllib.request.OpenerDirector:
    handlers: list[urllib.request.BaseHandler] = [_NoRedirect()]
    if (urlsplit(url).hostname or "").lower() in _LOCAL_HTTP_HOSTS:
        handlers.append(urllib.request.ProxyHandler({}))  # lokal nie über einen Proxy
    return urllib.request.build_opener(*handlers)


def _error_text(body: bytes) -> str:
    try:
        loaded = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return ""
    if isinstance(loaded, dict):
        error = str(loaded.get("error") or "")
        detail = loaded.get("detail")
        return f"{error}: {detail}" if detail else error
    return ""


def post_ingest(
    url: str, key: str, payload: dict[str, Any], timeout: float = TIMEOUT_S
) -> dict[str, Any]:
    """Sendet ``payload`` und gibt die Antwort ``sak.ingest_result/1`` zurück.

    ``url`` ist die fertige Ingest-URL (``check_url``). Wirft eine ``PushError``-Unterklasse.
    """
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    limit = contracts.LIMITS["INGEST_MAX_BYTES"]
    if len(body) > limit:
        raise RequestRejected(f"Anfrage mit {len(body)} Bytes überschreitet {limit} Bytes")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "spec-agent-kit",
        },
    )
    try:
        with _opener(url).open(request, timeout=timeout) as response:
            raw = response.read(_MAX_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        _raise_for_status(exc, sent_project=payload.get("project"))
        raise  # pragma: no cover - _raise_for_status wirft immer
    except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise NetworkError(f"Dashboard nicht erreichbar: {type(reason).__name__}") from exc
    try:
        result = json.loads(raw[:_MAX_RESPONSE].decode("utf-8"))
    except ValueError as exc:
        raise NetworkError("Antwort des Dashboards ist kein JSON") from exc
    if (
        len(raw) > _MAX_RESPONSE
        or not isinstance(result, dict)
        or result.get("schema") != "sak.ingest_result/1"
        or contracts.validate_ingest(result)
    ):
        raise RequestRejected("Antwort des Dashboards ist kein gültiges sak.ingest_result/1")
    return result


def _expected_project(body: bytes) -> str | None:
    """Das Projekt, das die Antwort als erwartet nennt (Feld ``expected``, nie ein Schlüssel)."""
    try:
        loaded = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return None
    value = loaded.get("expected") if isinstance(loaded, dict) else None
    return value if isinstance(value, str) and 0 < len(value) <= 80 else None


def _raise_for_status(exc: urllib.error.HTTPError, sent_project: Any = None) -> None:
    try:
        body = exc.read(_MAX_ERROR_BODY)
    except OSError:
        body = b""
    text = _error_text(body)
    code = exc.code
    if code == 403 and "project mismatch" in text:
        expected = _expected_project(body)
        sent = (
            f"'{sent_project}'" if isinstance(sent_project, str) else "dem konfigurierten Projekt"
        )
        wanted = (
            f"das Dashboard erwartet das Projekt '{expected}'"
            if expected
            else "der Schlüssel gehört zu einem anderen Projekt"
        )
        raise AuthError(
            f"HTTP 403: project mismatch (gesendet als {sent}, {wanted}); project.key in der "
            "Config bzw. den Schlüssel prüfen"
        ) from exc
    if code in {401, 403}:
        raise AuthError(f"HTTP {code}: {text or 'Schlüssel abgelehnt'}") from exc
    if any(marker in text.lower() for marker in VERSION_MARKERS):
        raise VersionError(f"HTTP {code}: {text}") from exc
    if code == 429 or code >= 500:
        raise NetworkError(f"Dashboard meldet HTTP {code}") from exc
    if 300 <= code < 400:
        raise RequestRejected(f"HTTP {code}: Weiterleitungen werden nicht verfolgt") from exc
    if code == 404:
        raise RequestRejected(
            "HTTP 404: Endpunkt /api/ingest nicht gefunden (dashboard.url?)"
        ) from exc
    raise RequestRejected(f"HTTP {code}: {text or 'Anfrage abgelehnt'}") from exc
