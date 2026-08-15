from __future__ import annotations

from pathlib import Path

import pytest

import neuroai_workbench.presentation_accessibility as accessibility
from neuroai_workbench.presentation_accessibility import validate_document, validate_static_surfaces


def valid_document() -> str:
    return """<!doctype html>
<html><body>
<a class="skip-link" href="#main">Skip</a>
<main id="main" tabindex="-1">
<label for="query">Search</label><input id="query">
<div id="views-label">Views</div>
<div role="tablist" aria-labelledby="views-label">
  <button id="tab-one" role="tab" aria-controls="panel-one" aria-selected="true" tabindex="0">One</button>
  <button id="tab-two" role="tab" aria-controls="panel-two" aria-selected="false" tabindex="-1">Two</button>
</div>
<section id="panel-one" role="tabpanel" aria-labelledby="tab-one"></section>
<section id="panel-two" role="tabpanel" aria-labelledby="tab-two" hidden></section>
<div id="status" role="status" aria-live="polite" aria-atomic="true" data-announcer="status"></div>
<div id="alert" role="alert" aria-live="assertive" aria-atomic="true" data-announcer="alert"></div>
<div id="toast" aria-hidden="true" data-toast-announcer hidden></div>
</main>
</body></html>"""


def codes(html: str) -> list[str]:
    return [issue.code for issue in validate_document(html, document_name="fixture.html").issues]


def messages(html: str, code: str) -> list[str]:
    return [
        issue.message for issue in validate_document(html, document_name="fixture.html").issues if issue.code == code
    ]


def test_valid_contract_passes() -> None:
    report = validate_document(valid_document(), document_name="fixture.html")
    assert report.valid is True
    assert report.issues == ()


def test_duplicate_ids_and_broken_idrefs_are_reported() -> None:
    html = valid_document().replace(
        '<div id="status" role="status"',
        '<div id="query"></div><div id="status" role="status"',
    )
    html = html.replace('<input id="query">', '<input id="query" aria-describedby="missing">')
    result = codes(html)
    assert "A11Y001" in result
    assert "A11Y002" in result


@pytest.mark.parametrize(
    "control",
    [
        '<input id="query" placeholder="Search">',
        '<select id="query"><option>Any</option></select>',
        '<textarea id="query"></textarea>',
    ],
)
def test_placeholder_or_default_option_is_not_an_accessible_name(control: str) -> None:
    html = valid_document().replace('<label for="query">Search</label><input id="query">', control)
    assert "A11Y003" in codes(html)


@pytest.mark.parametrize(
    "replacement",
    [
        '<label>Search<input id="query"></label>',
        '<input id="query" aria-label="Search">',
        '<span id="query-label">Search</span><input id="query" aria-labelledby="query-label">',
        '<input id="query" type="hidden">',
    ],
)
def test_supported_control_naming_patterns_pass(replacement: str) -> None:
    html = valid_document().replace('<label for="query">Search</label><input id="query">', replacement)
    assert "A11Y003" not in codes(html)


def test_positive_malformed_tabindex_and_hidden_focusable_are_rejected() -> None:
    positive = valid_document().replace('id="query">', 'id="query" tabindex="2">')
    malformed = valid_document().replace('id="query">', 'id="query" tabindex="first">')
    hidden = valid_document().replace('id="query">', 'id="query" aria-hidden="true">')
    assert any("positive tabindex" in message for message in messages(positive, "A11Y004"))
    assert any("must be an integer" in message for message in messages(malformed, "A11Y004"))
    assert "A11Y007" in codes(hidden)


def test_disabled_or_hidden_controls_do_not_trigger_focusable_hidden_rule() -> None:
    disabled = valid_document().replace('id="query">', 'id="query" disabled aria-hidden="true">')
    hidden = valid_document().replace(
        '<label for="query">Search</label><input id="query">',
        '<input id="query" type="hidden" aria-hidden="true">',
    )
    assert "A11Y007" not in codes(disabled)
    assert "A11Y007" not in codes(hidden)


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ('href="#main"', 'href="/main"', "local fragment"),
        ('href="#main"', 'href="#missing"', "missing or non-unique"),
        ('<main id="main" tabindex="-1">', '<div id="main" tabindex="-1">', "main landmark"),
        ('<main id="main" tabindex="-1">', '<main id="main">', "tabindex=-1"),
    ],
)
def test_skip_link_contract_fails_closed(old: str, new: str, expected: str) -> None:
    assert any(expected in message for message in messages(valid_document().replace(old, new), "A11Y005"))


def test_skip_and_main_landmark_presence_are_required() -> None:
    missing_skip = valid_document().replace('<a class="skip-link" href="#main">Skip</a>\n', "")
    assert "document must contain exactly one skip link; found 0" in messages(missing_skip, "A11Y005")

    duplicate_skip = valid_document().replace(
        '<a class="skip-link" href="#main">Skip</a>',
        '<a class="skip-link" href="#main">Skip</a><a class="skip-link" href="#main">Skip again</a>',
    )
    assert "document must contain exactly one skip link; found 2" in messages(duplicate_skip, "A11Y005")

    two_mains = valid_document().replace("</body>", '<main id="extra" tabindex="-1"></main></body>')
    assert "document must contain exactly one main landmark; found 2" in messages(two_mains, "A11Y005")


def test_tab_outside_tablist_and_empty_tablist_are_rejected() -> None:
    outside = valid_document().replace('<div role="tablist" aria-labelledby="views-label">', "<div>")
    assert any("not contained by a tablist" in message for message in messages(outside, "A11Y006"))

    empty = valid_document().replace(
        """<div role="tablist" aria-labelledby="views-label">
  <button id="tab-one" role="tab" aria-controls="panel-one" aria-selected="true" tabindex="0">One</button>
  <button id="tab-two" role="tab" aria-controls="panel-two" aria-selected="false" tabindex="-1">Two</button>
</div>""",
        '<div role="tablist" aria-labelledby="views-label"></div>',
    )
    assert "tablist contains no tabs" in messages(empty, "A11Y006")


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ('aria-selected="false"', 'aria-selected="true"', "exactly one selected"),
        (
            'id="tab-two" role="tab" aria-controls="panel-two" aria-selected="false" tabindex="-1"',
            'id="tab-two" role="tab" aria-controls="panel-two" aria-selected="false" tabindex="0"',
            "exactly one tab with tabindex=0",
        ),
        ('aria-selected="false"', 'aria-selected="maybe"', "aria-selected must be"),
        (
            'id="tab-two" role="tab" aria-controls="panel-two" aria-selected="false" tabindex="-1"',
            'id="tab-two" role="tab" aria-controls="panel-two" aria-selected="false" tabindex="-2"',
            "tab tabindex must be",
        ),
        ('id="tab-two"', 'id=""', "unique id"),
        ('aria-controls="panel-two"', 'aria-controls=""', "exactly one aria-controls"),
        ('aria-controls="panel-two"', 'aria-controls="missing"', "missing or non-unique"),
        ('id="panel-two" role="tabpanel"', 'id="panel-two" role="region"', "role=tabpanel"),
        ('aria-labelledby="tab-two" hidden', 'aria-labelledby="tab-one" hidden', "must reference its controlling tab"),
        ('aria-labelledby="tab-two" hidden', 'aria-labelledby="tab-two"', "unselected tabpanel must be hidden"),
    ],
)
def test_tab_relationship_defects_are_detected(old: str, new: str, expected: str) -> None:
    html = valid_document().replace(old, new, 1)
    assert any(expected in message for message in messages(html, "A11Y006"))


def test_selected_panel_must_not_be_hidden() -> None:
    html = valid_document().replace(
        'id="panel-one" role="tabpanel" aria-labelledby="tab-one">',
        'id="panel-one" role="tabpanel" aria-labelledby="tab-one" hidden>',
    )
    assert "selected tabpanel must be exposed" in messages(html, "A11Y006")


def test_orphan_and_multiply_controlled_tabpanels_are_rejected() -> None:
    orphan = valid_document().replace(
        '<div id="status" role="status"',
        '<section id="orphan" role="tabpanel" aria-labelledby="tab-one"></section><div id="status" role="status"',
    )
    assert "tabpanel must be controlled by exactly one tab; found 0" in messages(orphan, "A11Y006")

    multiply_controlled = valid_document().replace('aria-controls="panel-two"', 'aria-controls="panel-one"', 1)
    assert "tabpanel must be controlled by exactly one tab; found 2" in messages(multiply_controlled, "A11Y006")


def test_live_announcement_contract_fails_closed() -> None:
    status_role = valid_document().replace('role="status" aria-live="polite"', 'role="region" aria-live="polite"', 1)
    status_atomic = valid_document().replace(
        'aria-atomic="true" data-announcer="status"', 'aria-atomic="false" data-announcer="status"'
    )
    status_hidden = valid_document().replace('data-announcer="status"></div>', 'data-announcer="status" hidden></div>')
    alert_live = valid_document().replace('role="alert" aria-live="assertive"', 'role="alert" aria-live="polite"', 1)
    duplicate_status = valid_document().replace(
        '<div id="alert" role="alert"',
        '<div data-announcer="status"></div><div id="alert" role="alert"',
    )
    missing_toast = valid_document().replace(
        '<div id="toast" aria-hidden="true" data-toast-announcer hidden></div>\n', ""
    )
    exposed_toast = valid_document().replace('id="toast" aria-hidden="true"', 'id="toast" aria-hidden="false"')

    assert "status announcer must use role=status" in messages(status_role, "A11Y008")
    assert "status announcer must use aria-atomic=true" in messages(status_atomic, "A11Y008")
    assert any("remain exposed" in message for message in messages(status_hidden, "A11Y008"))
    assert "alert announcer must use aria-live=assertive" in messages(alert_live, "A11Y008")
    assert "document requires exactly one status announcer; found 2" in messages(duplicate_status, "A11Y008")
    assert "document requires exactly one visual toast announcement source; found 0" in messages(
        missing_toast, "A11Y008"
    )
    assert "visual toast announcement source must use aria-hidden=true" in messages(exposed_toast, "A11Y008")


def test_malformed_markup_and_non_text_source_fail_closed() -> None:
    malformed = valid_document().replace("</main>", "</section></main>", 1)
    assert "A11Y000" in codes(malformed)
    report = validate_document(None, document_name="fixture.html")  # type: ignore[arg-type]
    assert report.valid is False
    assert report.issues[0].code == "A11Y000"


def test_static_surface_aggregation_and_missing_surface(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(valid_document(), encoding="utf-8")
    missing = validate_static_surfaces(tmp_path)
    assert missing.valid is False
    assert any(issue.document == "review.html" and "missing" in issue.message for issue in missing.issues)

    (tmp_path / "review.html").write_text(valid_document(), encoding="utf-8")
    complete = validate_static_surfaces(tmp_path)
    assert complete.valid is True


def test_packaged_primary_surfaces_pass_and_load_shared_interaction_layer() -> None:
    root = Path(__file__).resolve().parents[2]
    static_root = root / "src" / "neuroai_workbench" / "static"
    report = validate_static_surfaces(static_root)
    assert report.valid, report.issues

    index = (static_root / "index.html").read_text(encoding="utf-8")
    review = (static_root / "review.html").read_text(encoding="utf-8")
    interaction = (static_root / "accessibility.js").read_text(encoding="utf-8")
    styles = (static_root / "styles.css").read_text(encoding="utf-8")

    assert '<script src="accessibility.js" defer></script>' in index
    assert '<script src="accessibility.js" defer></script>' in review
    assert 'data-announcer="status"' in index and 'data-announcer="alert"' in index
    assert 'data-announcer="status"' in review and 'data-announcer="alert"' in review
    assert "data-toast-announcer" in index and "data-toast-announcer" in review
    assert "MutationObserver" in interaction
    assert "ArrowRight" in interaction and "ArrowLeft" in interaction
    assert "a:focus-visible" in styles
    assert ".sr-only" in styles
    assert ".innerHTML" not in interaction


def test_assessment_tab_state_is_owned_by_shared_interaction_layer() -> None:
    root = Path(__file__).resolve().parents[2]
    app = (root / "src" / "neuroai_workbench" / "static" / "app.js").read_text(encoding="utf-8")
    assert "function activateTab" not in app
    assert ".tabs button" not in app


def test_parser_boundary_branches_and_generic_focusability() -> None:
    self_closing = valid_document().replace('<div id="status"', '<br/><div id="status"', 1)
    assert validate_document(self_closing, document_name="fixture.html").valid

    unexpected = valid_document().replace("<html><body>", "<html><body></aside>")
    assert "A11Y000" in codes(unexpected)

    void_close = valid_document().replace("</body>", "</input></body>")
    assert "A11Y000" not in codes(void_close)

    unclosed = valid_document().replace("</main>", "", 1)
    assert "A11Y000" in codes(unclosed)

    anchor = valid_document().replace(
        '<div id="status" role="status"',
        '<a href="/" aria-hidden="true">Hidden link</a><div id="status" role="status"',
    )
    assert "A11Y007" in codes(anchor)

    tabindex_focusable = valid_document().replace(
        '<div id="status" role="status"',
        '<div tabindex="0" aria-hidden="true">Hidden focus target</div><div id="status" role="status"',
    )
    assert "A11Y007" in codes(tabindex_focusable)

    malformed_tabindex = valid_document().replace(
        '<div id="status" role="status"',
        '<div tabindex="bad" aria-hidden="true">Not focusable</div><div id="status" role="status"',
    )
    assert "A11Y007" not in codes(malformed_tabindex)


def test_parser_exception_is_converted_to_deterministic_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_feed(self: object, html: str) -> None:
        raise ValueError("synthetic parser failure")

    monkeypatch.setattr(accessibility._DocumentParser, "feed", fail_feed)
    report = validate_document(valid_document(), document_name="fixture.html")
    assert report.valid is False
    assert report.issues[0].code == "A11Y000"
    assert "synthetic parser failure" in report.issues[0].message
