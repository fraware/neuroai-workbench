from __future__ import annotations

import json
import re
from importlib.resources import files

import pytest

from neuroai_workbench.presentation_i18n import validate_catalog


def test_catalog_rejects_non_string_locale_metadata_fail_closed() -> None:
    payload = {
        "schema_version": "1",
        "locale": 7,
        "messages": {"assessment.shell_title": "Workbench"},
    }
    with pytest.raises(ValueError, match="locale does not match"):
        validate_catalog(payload, expected_locale="en")


def test_every_annotated_presentation_key_has_exact_catalog_parity() -> None:
    static = files("neuroai_workbench.static")
    index = static.joinpath("index.html").read_text(encoding="utf-8")
    review = static.joinpath("review.html").read_text(encoding="utf-8")
    catalog = json.loads(static.joinpath("messages.en.json").read_text(encoding="utf-8"))

    annotated_keys = set(re.findall(r'data-i18n="([a-z0-9_.-]+)"', index + review))
    catalog_keys = set(catalog["messages"])

    assert annotated_keys
    assert annotated_keys == catalog_keys
