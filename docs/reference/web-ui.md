# Local web interface

The browser application is served by the Python process and uses no CDN, remote analytics, web fonts or third-party scripts.

## Views

- Summary and mechanical blocker dashboard.
- Filterable 78-requirement matrix.
- Local evidence registration and digest verification.
- Typed decision records.
- Full JSON editor with optional valid-save gate.
- Hash-chain verification and event history.
- Link to the observatory monitoring review UI at `/review.html` (see [review-ui.md](review-ui.md)).

## Network boundary

The default URL is `http://127.0.0.1:8765`. The server has no built-in authentication or TLS. Do not bind it to a shared interface unless a separate secured architecture supplies those controls.
