# Presentation internationalization boundary

## Scope

The internationalization layer controls human-facing presentation strings in the local reference UI. It is deliberately outside the normative assessment kernel and outside persisted assessment, observatory, evidence, review, governance, and release records.

The shipped locale is English (`en`). Region variants such as `en-US` resolve to the supported base language. Unsupported or malformed locale requests resolve deterministically to English and the API reports that fallback. User-supplied locale text never selects a filesystem path; only repository-declared locale identifiers map to packaged catalogs.

## Non-translatable semantics

Translation catalogs must not define or rewrite requirement identifiers, finding states, priority codes, evidence types, source identifiers, governance states, release states, schema literals, hashes, or other machine-readable contract values. Values such as `PASS`, `PARTIAL`, `FAIL`, `P0`, `P1`, `P2`, `SUPPORT`, `DEFER`, `AUTHORIZED`, and `PUBLISHED` remain governed tokens wherever they appear in machine-readable records or controls.

Catalog keys are restricted to presentation namespaces and validated before use. Browser application uses `textContent` or attribute assignment for catalog output; catalog messages are never interpreted as HTML. Existing English HTML remains the fail-safe fallback if catalog retrieval fails.

## Locale resolution

The explicit `?lang=` presentation request has precedence. The server endpoint additionally supports deterministic `Accept-Language` negotiation for clients that call it directly. A requested region may fall back to a supported base language. Unsupported, malformed, wildcard-only, or unavailable languages fall back to the default English catalog. The response exposes selected locale, resolution source, fallback state, supported locales, catalog digest, and the presentation-only boundary.

## Adding a locale

A future locale is a repository-controlled catalog plus an explicit entry in the supported-locale map. Addition requires key parity with the default catalog, deterministic tests, review of terminology that intersects evidence and governance concepts, and confirmation that no governed semantic token was moved into the translation contract. Automated translation may assist drafting, but publication of a locale requires human linguistic review appropriate to the language and subject matter.

## External review plan

A non-English locale should receive independent linguistic review for terminology, boundary statements, ambiguity, and equivalence of safety-relevant instructions. Accessibility review should exercise keyboard navigation, screen-reader announcements, zoom/reflow, language metadata, long-string expansion, and any future right-to-left layout. Representative-user testing remains a human activity and is not established by this architecture or its automated tests.

## Withheld claims

This layer does not establish translation quality, linguistic equivalence, accessibility conformance, representative-user validation, regulatory compliance, institutional identity, release authority, canonical publication authority, or UNESCO endorsement.
