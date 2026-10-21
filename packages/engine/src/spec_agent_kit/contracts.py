"""Verträge v1: Schemas, Vokabular, Labels, Limits, ULID.

Die JSON-Schemas unter ``schemas/`` sind eine byte-gleiche Kopie von
``packages/contracts/schema/`` (Sync-Skript, Test prüft die Gleichheit). Diese Datei ändert sie nie.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from jsonschema import Draft202012Validator, FormatChecker, validators
from jsonschema.exceptions import ValidationError, relevance
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SCHEMA_DIR: Final[Path] = Path(__file__).resolve().parent / "schemas"
SCHEMA_NAMES: Final[tuple[str, ...]] = ("common", "event", "board", "ingest", "config", "lock")
CONFIG_MAX_BYTES: Final[int] = 256 * 1024
DEFAULT_LOCALE: Final[str] = "de"

# ---------------------------------------------------------------------------
# Laden
# ---------------------------------------------------------------------------


@cache
def _load_json(relative: str) -> Any:
    return json.loads((SCHEMA_DIR / relative).read_text(encoding="utf-8"))


def load_schema(name: str) -> dict[str, Any]:
    """Lädt ``<name>.schema.json`` (eines aus ``SCHEMA_NAMES``)."""
    if name not in SCHEMA_NAMES:
        raise ValueError(f"Unbekanntes Schema: {name}")
    schema: dict[str, Any] = _load_json(f"{name}.schema.json")
    return schema


def vocabulary() -> dict[str, list[str]]:
    """Die Ebenen des Vokabulars (Ebene -> erlaubte Maschinenwerte)."""
    levels: dict[str, list[str]] = _load_json("vocabulary.json")["levels"]
    return levels


def vocabulary_version() -> int:
    """Versionsnummer des Vokabulars (``vocabulary.json``)."""
    version: int = _load_json("vocabulary.json")["version"]
    return version


def label(level: str, value: str, locale: str = DEFAULT_LOCALE) -> str:
    """Anzeigebezeichnung eines Werts. Unbekannte Werte kommen unverändert zurück."""
    table: dict[str, dict[str, str]] = _load_json(f"labels/{locale}.json")
    return table.get(level, {}).get(value, value)


def labels(locale: str = DEFAULT_LOCALE) -> dict[str, dict[str, str]]:
    """Alle Anzeigebezeichnungen einer Locale (Ebene -> Maschinenwert -> Bezeichnung)."""
    table: dict[str, dict[str, str]] = _load_json(f"labels/{locale}.json")
    return table


def _load_limits() -> Any:
    raw: dict[str, int] = _load_json("limits.json")
    return MappingProxyType({k.upper(): v for k, v in raw.items() if k != "version"})


LIMITS: Final = _load_limits()
"""Größen- und Mengenlimits (gleich wie ``LIMITS`` in ``@sak/contracts``)."""

# ---------------------------------------------------------------------------
# Validierung
# ---------------------------------------------------------------------------


def _pattern(validator: Any, pattern: str, instance: Any, schema: dict[str, Any]) -> Any:
    """``pattern`` als vollständiger Treffer.

    Das Standardverhalten (``re.search``) lässt bei ``$`` ein abschließendes Newline zu; JavaScript
    tut das nicht. ``fullmatch`` stellt gleiches Verhalten in beiden Sprachen her.
    """
    if validator.is_type(instance, "string") and re.fullmatch(pattern, instance) is None:
        yield ValidationError(f"{instance!r} does not match {pattern!r}")


_Validator = validators.extend(Draft202012Validator, {"pattern": _pattern})


def _is_rfc3339(value: object) -> bool:
    if not isinstance(value, str):
        return True
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


_FORMATS = FormatChecker(formats=())
_FORMATS.checks("date-time")(_is_rfc3339)


@cache
def _registry() -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name in SCHEMA_NAMES:
        schema = load_schema(name)
        registry = registry.with_resource(
            schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012)
        )
    return registry


@cache
def _validator(name: str) -> Any:
    return _Validator(load_schema(name), registry=_registry(), format_checker=_FORMATS)


def serialized_size(value: Any) -> int:
    """Größe der kompakten UTF-8-JSON-Serialisierung in Bytes."""
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


_DISCRIMINATORS: Final[frozenset[str]] = frozenset({"type", "schema", "descoped", "verdict"})


def _is_discriminator_failure(error: ValidationError) -> bool:
    return (
        error.validator in ("const", "enum")
        and len(error.relative_path) == 1
        and error.relative_path[0] in _DISCRIMINATORS
    )


def _explain(error: ValidationError) -> ValidationError:
    """Steigt in ``anyOf`` zum passenden Zweig ab.

    Die Zweige unterscheiden sich über eine Konstante (``type``, ``schema``, ``descoped`` ...).
    Fehler des Zweigs, dessen Unterscheidungsmerkmal passt, sind aussagekräftiger als die
    Sammelmeldung "not valid under any of the given schemas".
    """
    if error.validator not in ("anyOf", "oneOf") or not error.context:
        return error
    branches: dict[Any, list[ValidationError]] = {}
    for inner in error.context:
        branches.setdefault(inner.schema_path[0], []).append(inner)
    matching = [
        errors
        for errors in branches.values()
        if not any(_is_discriminator_failure(e) for e in errors)
    ]
    if not matching:
        return error
    chosen = min(matching, key=len)
    return _explain(max(chosen, key=relevance))


def _describe(error: ValidationError) -> str:
    where = "/".join(str(p) for p in error.absolute_path) or "<root>"
    message = error.message if len(error.message) <= 300 else error.message[:297] + "..."
    return f"{where}: {message}"


def _validate(name: str, obj: Any, max_bytes: int) -> list[str]:
    """Leere Liste = gültig. Sonst genau die aussagekräftigste Fehlermeldung."""
    errors = list(_validator(name).iter_errors(obj))
    if errors:
        return [_describe(_explain(max(errors, key=relevance)))]
    size = serialized_size(obj)
    if size > max_bytes:
        return [f"<root>: {size} Bytes überschreiten das Limit von {max_bytes} Bytes"]
    return []


def validate_event(obj: Any) -> list[str]:
    """Prüft ein Event gegen ``sak.event/1`` (inklusive 8-KB-Limit)."""
    return _validate("event", obj, LIMITS["EVENT_MAX_BYTES"])


def validate_board(obj: Any) -> list[str]:
    """Prüft ein Board-Dokument gegen ``sak.board/1`` (inklusive 512-KB-Limit)."""
    return _validate("board", obj, LIMITS["BOARD_MAX_BYTES"])


def validate_ingest(obj: Any) -> list[str]:
    """Prüft Ingest-Anfrage oder -Antwort (``sak.ingest/1`` bzw. ``sak.ingest_result/1``)."""
    return _validate("ingest", obj, LIMITS["INGEST_MAX_BYTES"])


def validate_config(obj: Any) -> list[str]:
    """Prüft eine Projektkonfiguration gegen ``sak.config/1`` (höchstens 256 KB)."""
    return _validate("config", obj, CONFIG_MAX_BYTES)


def validate_lock(obj: Any) -> list[str]:
    """Prüft ein Lockfile gegen ``sak.lock/1`` (höchstens 256 KB)."""
    return _validate("lock", obj, CONFIG_MAX_BYTES)


def config_schema_errors(obj: Any) -> list[ValidationError]:
    """Alle Schemaverstöße einer Projektkonfiguration (für ``sak config check``)."""
    return sorted(_validator("config").iter_errors(obj), key=lambda e: list(map(str, e.path)))


# ---------------------------------------------------------------------------
# Zeit und ULID
# ---------------------------------------------------------------------------

_CROCKFORD: Final[str] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LOCK = threading.Lock()
_ulid_state: tuple[int, int] = (-1, 0)  # (letzte Millisekunde, letzter Zufallsteil)


def now_rfc3339() -> str:
    """Aktuelle UTC-Zeit als RFC 3339 mit Sekundengenauigkeit, z. B. ``2026-10-20T10:20:00Z``."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _encode(value: int) -> str:
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def new_ulid(timestamp_ms: int | None = None) -> str:
    """Erzeugt eine ULID (48 Bit Zeit, 80 Bit Zufall; Crockford Base32, 26 Zeichen).

    Innerhalb derselben Millisekunde wächst der Zufallsteil um 1, sodass die Reihenfolge im
    Prozess monoton bleibt. ``timestamp_ms`` ist für Tests gedacht.
    """
    global _ulid_state
    now = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    with _ULID_LOCK:
        last_ms, last_rand = _ulid_state
        if now <= last_ms:
            now = last_ms
            rand = last_rand + 1
            if rand >= 1 << 80:  # Überlauf: nächste Millisekunde verwenden
                now += 1
                rand = secrets.randbits(80)
        else:
            rand = secrets.randbits(80)
        _ulid_state = (now, rand)
    return _encode((now << 80) | rand)


def deterministic_ulid(timestamp_ms: int, seed: str) -> str:
    """ULID mit festem Zeitteil und einem aus ``seed`` abgeleiteten Zufallsteil (80 Bit).

    Gleiche Eingabe ergibt immer dieselbe ID. Das braucht der Import alter Historie
    (``sak migrate legacy-pipeline``), damit ein zweiter Lauf keine Duplikate erzeugt.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return _encode((timestamp_ms << 80) | int.from_bytes(digest[:10], "big"))
