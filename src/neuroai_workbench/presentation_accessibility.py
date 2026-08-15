from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

_IDREF_ATTRIBUTES = ("aria-labelledby", "aria-describedby", "aria-controls")
_CONTROL_TAGS = frozenset({"input", "select", "textarea"})
_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
)


@dataclass(frozen=True)
class AccessibilityIssue:
    code: str
    document: str
    element: str | None
    message: str


@dataclass(frozen=True)
class AccessibilityReport:
    valid: bool
    issues: tuple[AccessibilityIssue, ...]


@dataclass
class _Element:
    index: int
    tag: str
    attrs: dict[str, str | None]
    parent: int | None


class _DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[_Element] = []
        self.stack: list[int] = []
        self.errors: list[str] = []

    def _add(self, tag: str, attrs: list[tuple[str, str | None]], *, push: bool) -> None:
        element = _Element(
            index=len(self.elements),
            tag=tag,
            attrs={name: value for name, value in attrs},
            parent=self.stack[-1] if self.stack else None,
        )
        self.elements.append(element)
        if push and tag not in _VOID_TAGS:
            self.stack.append(element.index)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._add(tag, attrs, push=True)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._add(tag, attrs, push=False)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"unexpected closing tag </{tag}>")
            return
        current = self.elements[self.stack[-1]]
        if current.tag == tag:
            self.stack.pop()
            return
        matching_position = next(
            (
                position
                for position in range(len(self.stack) - 1, -1, -1)
                if self.elements[self.stack[position]].tag == tag
            ),
            None,
        )
        if matching_position is None:
            self.errors.append(f"unexpected closing tag </{tag}>")
            return
        self.errors.append(f"mismatched closing tag </{tag}>")
        del self.stack[matching_position:]

    def close(self) -> None:
        super().close()
        for index in self.stack:
            self.errors.append(f"unclosed <{self.elements[index].tag}>")
        self.stack.clear()


def _element_ref(element: _Element) -> str:
    identifier = (element.attrs.get("id") or "").strip()
    return f"#{identifier}" if identifier else f"<{element.tag}>@{element.index}"


def _classes(element: _Element) -> set[str]:
    return set((element.attrs.get("class") or "").split())


def _is_hidden_control(element: _Element) -> bool:
    input_hidden = element.tag == "input" and (element.attrs.get("type") or "").lower() == "hidden"
    return "hidden" in element.attrs or input_hidden


def _ancestor_has_tag(elements: list[_Element], element: _Element, tag: str) -> bool:
    parent = element.parent
    while parent is not None:
        ancestor = elements[parent]
        if ancestor.tag == tag:
            return True
        parent = ancestor.parent
    return False


def _nearest_ancestor_role(elements: list[_Element], element: _Element, role: str) -> int | None:
    parent = element.parent
    while parent is not None:
        ancestor = elements[parent]
        if (ancestor.attrs.get("role") or "").lower() == role:
            return ancestor.index
        parent = ancestor.parent
    return None


def _is_focusable(element: _Element) -> bool:
    if "hidden" in element.attrs or "disabled" in element.attrs:
        return False
    if element.tag == "input" and (element.attrs.get("type") or "").lower() == "hidden":
        return False
    if element.tag in {"button", "select", "textarea", "input"}:
        return True
    if element.tag == "a" and bool((element.attrs.get("href") or "").strip()):
        return True
    tabindex = element.attrs.get("tabindex")
    if tabindex is None:
        return False
    try:
        return int(tabindex) >= 0
    except ValueError:
        return False


def validate_document(html: str, *, document_name: str) -> AccessibilityReport:
    issues: list[AccessibilityIssue] = []
    if not isinstance(html, str):
        issue = AccessibilityIssue("A11Y000", document_name, None, "document source must be text")
        return AccessibilityReport(False, (issue,))

    parser = _DocumentParser()
    try:
        parser.feed(html)
        parser.close()
    except (TypeError, ValueError) as exc:
        issue = AccessibilityIssue("A11Y000", document_name, None, f"HTML parsing failed: {exc}")
        return AccessibilityReport(False, (issue,))

    elements = parser.elements

    def add(code: str, element: _Element | None, message: str) -> None:
        issues.append(AccessibilityIssue(code, document_name, _element_ref(element) if element else None, message))

    for message in parser.errors:
        add("A11Y000", None, message)

    ids: dict[str, list[_Element]] = {}
    for element in elements:
        identifier = (element.attrs.get("id") or "").strip()
        if identifier:
            ids.setdefault(identifier, []).append(element)
    for identifier, matches in ids.items():
        if len(matches) > 1:
            add("A11Y001", matches[0], f"id {identifier!r} occurs {len(matches)} times")

    for element in elements:
        for attribute in _IDREF_ATTRIBUTES:
            value = (element.attrs.get(attribute) or "").strip()
            for target in value.split():
                if len(ids.get(target, [])) != 1:
                    add("A11Y002", element, f"{attribute} references non-unique or missing id {target!r}")

    labels_for = {
        (element.attrs.get("for") or "").strip()
        for element in elements
        if element.tag == "label" and (element.attrs.get("for") or "").strip()
    }
    for element in elements:
        if element.tag not in _CONTROL_TAGS or _is_hidden_control(element):
            continue
        identifier = (element.attrs.get("id") or "").strip()
        aria_label = (element.attrs.get("aria-label") or "").strip()
        labelledby = (element.attrs.get("aria-labelledby") or "").split()
        has_aria_labelledby = bool(labelledby) and all(len(ids.get(target, [])) == 1 for target in labelledby)
        if not (
            aria_label
            or (identifier and identifier in labels_for)
            or _ancestor_has_tag(elements, element, "label")
            or has_aria_labelledby
        ):
            add("A11Y003", element, "form control has no explicit accessible name")

    for element in elements:
        tabindex = element.attrs.get("tabindex")
        if tabindex is not None:
            try:
                if int(tabindex) > 0:
                    add("A11Y004", element, "positive tabindex is forbidden")
            except ValueError:
                add("A11Y004", element, "tabindex must be an integer")
        if (element.attrs.get("aria-hidden") or "").lower() == "true" and _is_focusable(element):
            add("A11Y007", element, "focusable element must not be aria-hidden")

    skip_links = [element for element in elements if "skip-link" in _classes(element)]
    for link in skip_links:
        href = (link.attrs.get("href") or "").strip()
        if not href.startswith("#") or len(href) == 1:
            add("A11Y005", link, "skip link must reference a local fragment target")
            continue
        target_id = href[1:]
        targets = ids.get(target_id, [])
        if len(targets) != 1:
            add("A11Y005", link, f"skip link target {target_id!r} is missing or non-unique")
            continue
        target = targets[0]
        if target.tag != "main":
            add("A11Y005", link, "skip link must target the main landmark")
        if target.attrs.get("tabindex") != "-1":
            add("A11Y005", link, "skip target must use tabindex=-1 for deterministic focus transfer")

    tablists = [element for element in elements if (element.attrs.get("role") or "").lower() == "tablist"]
    tabs = [element for element in elements if (element.attrs.get("role") or "").lower() == "tab"]
    panels = [element for element in elements if (element.attrs.get("role") or "").lower() == "tabpanel"]
    controlled_panel_ids: set[str] = set()

    for tab in tabs:
        if _nearest_ancestor_role(elements, tab, "tablist") is None:
            add("A11Y006", tab, "tab is not contained by a tablist")

    for tablist in tablists:
        owned_tabs = [tab for tab in tabs if _nearest_ancestor_role(elements, tab, "tablist") == tablist.index]
        if not owned_tabs:
            add("A11Y006", tablist, "tablist contains no tabs")
            continue
        if sum((tab.attrs.get("aria-selected") or "").lower() == "true" for tab in owned_tabs) != 1:
            add("A11Y006", tablist, "tablist must have exactly one selected tab")
        if sum(tab.attrs.get("tabindex") == "0" for tab in owned_tabs) != 1:
            add("A11Y006", tablist, "tablist must have exactly one tab with tabindex=0")
        for tab in owned_tabs:
            selected = (tab.attrs.get("aria-selected") or "").lower()
            if selected not in {"true", "false"}:
                add("A11Y006", tab, "tab aria-selected must be true or false")
            if tab.attrs.get("tabindex") not in {"0", "-1"}:
                add("A11Y006", tab, "tab tabindex must be 0 or -1")
            tab_id = (tab.attrs.get("id") or "").strip()
            controls = (tab.attrs.get("aria-controls") or "").split()
            if not tab_id or len(controls) != 1:
                add("A11Y006", tab, "tab requires a unique id and exactly one aria-controls target")
                continue
            target_id = controls[0]
            targets = ids.get(target_id, [])
            if len(targets) != 1:
                add("A11Y006", tab, f"tab panel {target_id!r} is missing or non-unique")
                continue
            panel = targets[0]
            controlled_panel_ids.add(target_id)
            if (panel.attrs.get("role") or "").lower() != "tabpanel":
                add("A11Y006", tab, "aria-controls target must have role=tabpanel")
            if tab_id not in (panel.attrs.get("aria-labelledby") or "").split():
                add("A11Y006", panel, "tabpanel aria-labelledby must reference its controlling tab")
            hidden = "hidden" in panel.attrs
            if selected == "true" and hidden:
                add("A11Y006", panel, "selected tabpanel must be exposed")
            if selected == "false" and not hidden:
                add("A11Y006", panel, "unselected tabpanel must be hidden")

    for panel in panels:
        panel_id = (panel.attrs.get("id") or "").strip()
        if not panel_id or panel_id not in controlled_panel_ids:
            add("A11Y006", panel, "tabpanel must be controlled by exactly one tab relationship")

    has_status = any(
        (element.attrs.get("role") or "").lower() == "status"
        and (element.attrs.get("aria-live") or "").lower() == "polite"
        for element in elements
    )
    has_alert = any(
        (element.attrs.get("role") or "").lower() == "alert"
        and (element.attrs.get("aria-live") or "").lower() == "assertive"
        for element in elements
    )
    if not has_status:
        add("A11Y008", None, "document requires a persistent polite status announcement region")
    if not has_alert:
        add("A11Y008", None, "document requires a persistent assertive alert region")

    ordered = tuple(sorted(issues, key=lambda item: (item.document, item.code, item.element or "", item.message)))
    return AccessibilityReport(not ordered, ordered)


def validate_static_surfaces(static_root: Path) -> AccessibilityReport:
    issues: list[AccessibilityIssue] = []
    for name in ("index.html", "review.html"):
        path = static_root / name
        if not path.is_file():
            issues.append(AccessibilityIssue("A11Y000", name, None, "required static surface is missing"))
            continue
        report = validate_document(path.read_text(encoding="utf-8"), document_name=name)
        issues.extend(report.issues)
    ordered = tuple(sorted(issues, key=lambda item: (item.document, item.code, item.element or "", item.message)))
    return AccessibilityReport(not ordered, ordered)
