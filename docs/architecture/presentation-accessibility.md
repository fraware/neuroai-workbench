# Presentation accessibility boundary

## Engineering protections

The local reference UI has deterministic regression checks for accessibility-relevant structure and keyboard state. The Python presentation contract validates duplicate identifiers, ARIA ID references, explicit names for form controls, positive `tabindex`, skip-navigation targets, tab relationships, focusable content hidden from accessibility APIs, and persistent status/alert regions. The shared browser interaction layer implements skip-link focus transfer, synchronized tab selection and panel visibility, ArrowLeft/ArrowRight/Home/End navigation, roving `tabindex`, and visual-toast announcements through persistent live regions.

These checks operate on repository-controlled presentation assets. They do not inspect protected evidence, alter assessment records, change review authority, or invoke the public network.

## Structural contract

Each primary surface has one stable `main` target with `tabindex="-1"` for skip navigation. Form controls require a native label, `aria-label`, or a valid `aria-labelledby` relationship; placeholder and default-option text are not treated as names.

Case views use the ARIA tab pattern. Exactly one tab is selected and keyboard-focusable at a time. Each tab has a stable identifier and `aria-controls` reference, and each panel has a reciprocal `aria-labelledby` reference. Governed identifiers and machine-readable values are not derived from translated labels.

Routine confirmations are mirrored into a persistent polite status region. Errors are mirrored into a persistent assertive alert region. Visual toasts remain presentation-only and are hidden from the accessibility tree to prevent duplicate announcements. Actionable links and form controls receive an explicit `:focus-visible` treatment.

## Known limitations

Repository checks establish structural and interaction regression protection for the properties they exercise. They do not establish screen-reader usability, semantic comprehension, zoom or reflow quality across environments, forced-colors behavior, cognitive accessibility, motor accessibility across devices, translation quality, assistive-technology interoperability, representative-user validation, or WCAG conformance.

The dependency-free JavaScript tests exercise deterministic tab-state logic. Browser and assistive-technology interoperability remains an external validation activity.

## External validation protocol

A later human review should exercise the complete assessment and monitoring-review workflows with keyboard-only navigation; NVDA with a current Firefox or Chrome release on Windows; VoiceOver with a current Safari release on macOS; 200% and 400% zoom; narrow-viewport reflow; forced-colors or equivalent high-contrast modes; and representative users.

The review record should identify the exact environment and versions, workflow, finding, severity, affected users, reproduction steps, owner, remediation issue, disposition, reviewer, verification result, and timestamp. Sensitive participant information must remain outside the public repository. Unfavorable findings remain attributable after remediation.

## Withheld claims

Passing these automated checks does not establish accessibility conformance, representative-user validation, institutional readiness, regulatory compliance, substantive assessment validity, release authority, canonical publication authority, or endorsement by any external institution.
