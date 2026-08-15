from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from importlib.resources import files
from typing import Any

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en",)
PRESENTATION_BOUNDARY = (
    "Locale catalogs control human-facing presentation text only. They do not translate or alter requirement IDs, "
    "finding states, evidence types, governance states, source IDs, schema literals, hashes, stored records, or "
    "other machine-readable contract values."
)
_CATALOG_FILES = {"en": "messages.en.json"}
_ALLOWED_KEY_PREFIXES = ("assessment.", "review.", "shell.")
_FORBIDDEN_KEY_SEGMENTS = frozenset(
    {
        "PASS",
        "PARTIAL",
        "FAIL",
        "P0",
        "P1",
        "P2",
        "SUPPORT",
        "OPPOSE",
        "DEFER",
        "ABSTAIN",
        "NEEDS_EVIDENCE",
        "AUTHORIZED",
        "PUBLISHED",
    }
)
_LOCALE_RE = re.compile(r"^[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{1,8})*$")
_MESSAGE_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_MAX_LOCALE_LENGTH = 64
_MAX_ACCEPT_LANGUAGE_LENGTH = 2048
_MAX_LANGUAGE_RANGES = 32
_MAX_MESSAGES = 512
_MAX_MESSAGE_LENGTH = 4000


@dataclass(frozen=True)
class LocaleResolution:
    requested_locale: str | None
    selected_locale: str
    source: str
    fallback_used: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_locale(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value or len(value) > _MAX_LOCALE_LENGTH or _LOCALE_RE.fullmatch(value) is None:
        return None
    parts = re.split(r"[-_]", value)
    normalized = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            normalized.append(part.title())
        elif (len(part) == 2 and part.isalpha()) or (len(part) == 3 and part.isdigit()):
            normalized.append(part.upper())
        else:
            normalized.append(part.lower())
    return "-".join(normalized)


def _match_supported(locale: str | None) -> str | None:
    if locale is None:
        return None
    if locale in SUPPORTED_LOCALES:
        return locale
    base = locale.split("-", 1)[0]
    return base if base in SUPPORTED_LOCALES else None


def _accept_language_candidates(header: str | None) -> list[str]:
    if not header or len(header) > _MAX_ACCEPT_LANGUAGE_LENGTH:
        return []
    weighted: list[tuple[float, int, str]] = []
    for index, raw_range in enumerate(header.split(",")[:_MAX_LANGUAGE_RANGES]):
        parts = [part.strip() for part in raw_range.split(";")]
        token = parts[0]
        if not token:
            continue
        quality = 1.0
        valid = True
        for parameter in parts[1:]:
            if not parameter.lower().startswith("q="):
                continue
            try:
                quality = float(parameter[2:])
            except ValueError:
                valid = False
                break
            if quality < 0.0 or quality > 1.0:
                valid = False
                break
        if valid and quality > 0.0:
            weighted.append((quality, index, token))
    weighted.sort(key=lambda item: (-item[0], item[1]))
    return [token for _, _, token in weighted]


def resolve_locale(
    requested_locale: str | None = None,
    *,
    accept_language: str | None = None,
) -> LocaleResolution:
    if requested_locale is not None:
        normalized = normalize_locale(requested_locale)
        selected = _match_supported(normalized) or DEFAULT_LOCALE
        return LocaleResolution(
            requested_locale=normalized,
            selected_locale=selected,
            source="query",
            fallback_used=normalized != selected,
        )

    saw_language_range = False
    for candidate in _accept_language_candidates(accept_language):
        saw_language_range = True
        if candidate == "*":
            return LocaleResolution(None, DEFAULT_LOCALE, "accept-language", True)
        normalized = normalize_locale(candidate)
        matched_locale = _match_supported(normalized)
        if matched_locale is not None:
            return LocaleResolution(
                requested_locale=normalized,
                selected_locale=matched_locale,
                source="accept-language",
                fallback_used=normalized != matched_locale,
            )
    return LocaleResolution(None, DEFAULT_LOCALE, "default", saw_language_range or bool(accept_language))


def _reject_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate catalog key: {key}")
        result[key] = value
    return result


def validate_catalog(payload: Any, *, expected_locale: str) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("Presentation catalog root must be an object")
    if payload.get("schema_version") != "1":
        raise ValueError("Presentation catalog schema_version must be '1'")
    locale = payload.get("locale")
    if not isinstance(locale, str) or locale != expected_locale or normalize_locale(locale) != expected_locale:
        raise ValueError("Presentation catalog locale does not match the selected locale")
    raw_messages = payload.get("messages")
    if not isinstance(raw_messages, dict) or not raw_messages:
        raise ValueError("Presentation catalog messages must be a non-empty object")
    if len(raw_messages) > _MAX_MESSAGES:
        raise ValueError("Presentation catalog contains too many messages")

    messages: dict[str, str] = {}
    for raw_key, raw_value in raw_messages.items():
        if not isinstance(raw_key, str) or _MESSAGE_KEY_RE.fullmatch(raw_key) is None:
            raise ValueError("Presentation catalog keys must be lowercase presentation identifiers")
        if not raw_key.startswith(_ALLOWED_KEY_PREFIXES):
            raise ValueError(f"Presentation catalog key is outside the presentation namespace: {raw_key}")
        if any(segment.upper() in _FORBIDDEN_KEY_SEGMENTS for segment in raw_key.split(".")):
            raise ValueError(f"Governed semantic token is not translatable: {raw_key}")
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValueError(f"Presentation catalog value must be non-empty text: {raw_key}")
        if len(raw_value) > _MAX_MESSAGE_LENGTH or "\x00" in raw_value:
            raise ValueError(f"Presentation catalog value is unsafe or too long: {raw_key}")
        messages[raw_key] = raw_value
    return dict(sorted(messages.items()))


def load_catalog(locale: str) -> dict[str, str]:
    filename = _CATALOG_FILES.get(locale)
    if filename is None:
        raise ValueError(f"Unsupported presentation locale: {locale}")
    text = files("neuroai_workbench.static").joinpath(filename).read_text(encoding="utf-8")
    payload = json.loads(text, object_pairs_hook=_reject_duplicate_object)
    return validate_catalog(payload, expected_locale=locale)


def catalog_message(messages: dict[str, str], key: str) -> str:
    try:
        return messages[key]
    except KeyError as exc:
        raise KeyError(f"Missing presentation message: {key}") from exc


def build_presentation_catalog(
    *,
    requested_locale: str | None = None,
    accept_language: str | None = None,
) -> dict[str, object]:
    resolution = resolve_locale(requested_locale, accept_language=accept_language)
    messages = load_catalog(resolution.selected_locale)
    digest_payload = json.dumps(
        {"locale": resolution.selected_locale, "messages": messages},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "schema_version": "1",
        "translation_scope": "PRESENTATION_ONLY",
        "locale": resolution.selected_locale,
        "default_locale": DEFAULT_LOCALE,
        "supported_locales": list(SUPPORTED_LOCALES),
        "resolution": resolution.to_dict(),
        "messages": messages,
        "catalog_sha256": hashlib.sha256(digest_payload).hexdigest(),
        "boundary": PRESENTATION_BOUNDARY,
    }
