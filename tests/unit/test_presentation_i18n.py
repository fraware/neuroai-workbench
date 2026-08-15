from __future__ import annotations

import json
from importlib.resources import files

import pytest

from neuroai_workbench.presentation_i18n import (
    DEFAULT_LOCALE,
    PRESENTATION_BOUNDARY,
    SUPPORTED_LOCALES,
    _accept_language_candidates,
    _reject_duplicate_object,
    build_presentation_catalog,
    catalog_message,
    load_catalog,
    normalize_locale,
    resolve_locale,
    validate_catalog,
)


def valid_payload(messages: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "schema_version": "1",
        "locale": "en",
        "messages": messages or {"assessment.shell_title": "Workbench"},
    }


def test_locale_normalization_is_bounded_and_canonical() -> None:
    assert normalize_locale(None) is None
    assert normalize_locale("") is None
    assert normalize_locale(" en_us ") == "en-US"
    assert normalize_locale("zh_hant_tw") == "zh-Hant-TW"
    assert normalize_locale("es-419") == "es-419"
    assert normalize_locale("../../en") is None
    assert normalize_locale("e") is None
    assert normalize_locale("a" * 65) is None


def test_query_locale_has_precedence_and_explicit_fallback() -> None:
    exact = resolve_locale("en", accept_language="fr")
    assert exact.selected_locale == "en"
    assert exact.source == "query"
    assert exact.fallback_used is False

    regional = resolve_locale("en-US")
    assert regional.requested_locale == "en-US"
    assert regional.selected_locale == "en"
    assert regional.fallback_used is True

    unsupported = resolve_locale("fr-FR", accept_language="en")
    assert unsupported.requested_locale == "fr-FR"
    assert unsupported.selected_locale == DEFAULT_LOCALE
    assert unsupported.source == "query"
    assert unsupported.fallback_used is True

    malformed = resolve_locale("../../etc/passwd")
    assert malformed.requested_locale is None
    assert malformed.selected_locale == DEFAULT_LOCALE
    assert malformed.fallback_used is True


def test_accept_language_resolution_is_deterministic() -> None:
    weighted = resolve_locale(accept_language="fr-CA;q=0.9, en-GB;q=0.8, en;q=0.7")
    assert weighted.requested_locale == "en-GB"
    assert weighted.selected_locale == "en"
    assert weighted.source == "accept-language"
    assert weighted.fallback_used is True

    wildcard = resolve_locale(accept_language="*;q=0.8")
    assert wildcard.selected_locale == "en"
    assert wildcard.source == "accept-language"
    assert wildcard.fallback_used is True

    unavailable = resolve_locale(accept_language="fr;q=1")
    assert unavailable.selected_locale == "en"
    assert unavailable.source == "default"
    assert unavailable.fallback_used is True

    absent = resolve_locale()
    assert absent.selected_locale == "en"
    assert absent.source == "default"
    assert absent.fallback_used is False


def test_accept_language_parser_rejects_invalid_or_disabled_ranges() -> None:
    assert _accept_language_candidates(None) == []
    assert _accept_language_candidates("") == []
    assert _accept_language_candidates("en;q=0") == []
    assert _accept_language_candidates("fr;q=bogus,en;q=0.5") == ["en"]
    assert _accept_language_candidates("fr;q=2,en;q=0.4") == ["en"]
    assert _accept_language_candidates("fr;foo=bar,en;q=0.8") == ["fr", "en"]
    assert _accept_language_candidates("x" * 2049) == []


def test_duplicate_catalog_members_fail_closed() -> None:
    with pytest.raises(ValueError, match="Duplicate catalog key"):
        _reject_duplicate_object([("locale", "en"), ("locale", "fr")])
    assert _reject_duplicate_object([("locale", "en")]) == {"locale": "en"}


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "root must be an object"),
        ({"schema_version": "2", "locale": "en", "messages": {"assessment.x": "x"}}, "schema_version"),
        ({"schema_version": "1", "locale": "fr", "messages": {"assessment.x": "x"}}, "locale does not match"),
        ({"schema_version": "1", "locale": "en", "messages": {}}, "non-empty object"),
        ({"schema_version": "1", "locale": "en", "messages": []}, "non-empty object"),
        (valid_payload({"Bad Key": "x"}), "lowercase presentation identifiers"),
        (valid_payload({"semantic.label": "x"}), "outside the presentation namespace"),
        (valid_payload({"review.position.pass": "Pass"}), "Governed semantic token"),
        (valid_payload({"assessment.x": 3}), "non-empty text"),
        (valid_payload({"assessment.x": "   "}), "non-empty text"),
        (valid_payload({"assessment.x": "bad\x00value"}), "unsafe or too long"),
        (valid_payload({"assessment.x": "x" * 4001}), "unsafe or too long"),
    ],
)
def test_catalog_validation_rejects_invalid_translation_contract(payload: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_catalog(payload, expected_locale="en")


def test_catalog_validation_caps_catalog_size() -> None:
    messages = {f"assessment.k{i}": "x" for i in range(513)}
    with pytest.raises(ValueError, match="too many messages"):
        validate_catalog(valid_payload(messages), expected_locale="en")


def test_packaged_english_catalog_is_valid_and_presentation_only() -> None:
    messages = load_catalog("en")
    assert messages["assessment.shell_title"] == "NeuroAI Evidence and Decision Workbench"
    assert messages["review.skip_link"] == "Skip to review content"
    assert all(key.startswith(("assessment.", "review.", "shell.")) for key in messages)
    assert "PASS" not in messages
    with pytest.raises(ValueError, match="Unsupported presentation locale"):
        load_catalog("fr")


def test_catalog_message_missing_key_is_explicit() -> None:
    messages = {"assessment.x": "X"}
    assert catalog_message(messages, "assessment.x") == "X"
    with pytest.raises(KeyError, match="Missing presentation message"):
        catalog_message(messages, "assessment.missing")


def test_catalog_response_is_deterministic_and_auditable() -> None:
    first = build_presentation_catalog(requested_locale="en-US")
    second = build_presentation_catalog(requested_locale="en-US")
    assert first == second
    assert first["translation_scope"] == "PRESENTATION_ONLY"
    assert first["locale"] == "en"
    assert first["default_locale"] == "en"
    assert first["supported_locales"] == list(SUPPORTED_LOCALES)
    assert first["resolution"]["fallback_used"] is True
    assert first["boundary"] == PRESENTATION_BOUNDARY
    assert len(first["catalog_sha256"]) == 64


def test_static_shells_use_safe_catalog_bootstrap_and_english_fallback() -> None:
    static = files("neuroai_workbench.static")
    index = static.joinpath("index.html").read_text(encoding="utf-8")
    review = static.joinpath("review.html").read_text(encoding="utf-8")
    bootstrap = static.joinpath("i18n.js").read_text(encoding="utf-8")
    catalog = json.loads(static.joinpath("messages.en.json").read_text(encoding="utf-8"))

    assert 'data-i18n="assessment.shell_title"' in index
    assert 'data-i18n="review.shell_title"' in review
    assert '<script src="i18n.js" defer></script>' in index
    assert '<script src="i18n.js" defer></script>' in review
    assert "textContent = messages[key]" in bootstrap
    assert ".innerHTML" not in bootstrap
    assert "/api/presentation/catalog?locale=" in bootstrap
    assert "NeuroAI Evidence and Decision Workbench" in index
    assert "Observatory monitoring review" in review
    assert catalog["locale"] == "en"
