# Observatory monitoring review UI

The monitoring review UI is a local static HTML/JS view served by the workbench Python process. It projects rebuildable ops-health counts and review-queue items from monitoring workspace records.

## Boundary

The UI displays projections only. Ops-health counts, queue items, and capture diffs are rebuilt from monitoring and review-queue state. They are not a second source of truth and do not authenticate reviewers, mutate canonical observatory records, or establish substantive scientific, regulatory, clinical, or conformance conclusions.

Local reviewer profiles use `authority_profile: LOCAL_UNAUTHENTICATED_ATTRIBUTION`. Profile identifiers and display names are claimed workflow labels, not identity-provider assertions.

## Entry point

When the local server is running, open:

`http://127.0.0.1:8765/review.html`

The assessment workbench sidebar also links to this view.

## Views

- **Ops health** — due, overdue, pending candidate, and open queue-item counts derived from `plan_monitoring_run`, `monitoring_status`, and `list_queue_items`.
- **Queue list** — projected queue items with status, source linkage, and opinion counts.
- **Capture diff** — unified text diff between linked snapshots, rendered as escaped text in a sandboxed preview region.
- **Review opinion** — lease-gated immutable opinion submission aligned with review-queue schema concepts.
- **Adjudication** — form fields aligned with `CANDIDATE_ADJUDICATION.schema.json` concepts.

## Accessibility

The review UI follows these local static UI conventions:

- **Skip link** — a visible-on-focus skip link targets the main review content.
- **Landmarks** — header, complementary sidebar navigation, and main content regions use semantic elements and `aria-label` where headings alone are insufficient.
- **Live regions** — queue state, ops-health cards, and toast notifications use `aria-live` for asynchronous updates without stealing focus.
- **Keyboard support** — all actions use native buttons, links, and form controls with visible `:focus-visible` outlines shared with the assessment workbench styles.
- **Queue selection** — queue items expose `role="listbox"` / `role="option"` with `aria-selected` state.
- **Color and status** — queue status badges pair text labels with color; meaning is never conveyed by color alone.
- **Forms** — required adjudication and profile fields use explicit labels, fieldset/legend groupings for role checkboxes, and programmatic `required` attributes.
- **Untrusted capture content** — snapshot bytes and candidate summaries are inserted with `textContent` only in the browser. Server-side HTML render helpers escape content for fixture-driven tests.

## Safe diff rendering

Monitoring captures may contain hostile markup or script-like text from external sources. The UI treats all capture bytes as untrusted:

1. API responses return raw diff text in JSON; the browser never assigns capture content to `innerHTML`.
2. Diff previews render inside a dedicated sandbox container marked `data-sandbox="text-only"`.
3. Server-side `render_capture_preview_html()` escapes all diff lines for HTML fixture tests.

This prevents script execution in the local review surface. It does not sanitize stored workspace bytes or prove capture authenticity.

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/review/health` | Rebuildable ops-health projection |
| GET | `/api/review/queue` | Queue items and verification summary |
| GET | `/api/review/queue/{item_id}` | Item detail, capture diff, opinions |
| GET | `/api/review/profiles` | Registered profiles and field spec |
| GET | `/api/review/fields` | Adjudication field specification |
| POST | `/api/review/init` | Initialize review queue |
| POST | `/api/review/profiles` | Register local named profile |
| POST | `/api/review/queue/{item_id}/lease` | Claim exclusive lease |
| POST | `/api/review/leases/{lease_id}/release` | Release lease |
| POST | `/api/review/queue/{item_id}/opinion` | Submit immutable opinion |
| POST | `/api/review/queue/{item_id}/adjudicate` | Record monitoring adjudication |

## Dependency

This UI requires the PR-08 review queue package (`neuroai_workbench.review_queue`) and initialized observatory monitoring state. When monitoring is absent, health endpoints report the condition and queue routes return an uninitialized state rather than inventing data.

## Residual limitations

- No identity-provider integration; profiles remain local claimed attribution.
- No automatic substantive adjudication; human-entered rationale is required.
- Capture diff previews truncate large binary/text captures for local responsiveness.
- Hash validity and schema validation prove record consistency only, not reviewer identity or substantive correctness.
