
# Security review checklist

- Confirm localhost is the default binding.
- Confirm no remote assets, telemetry, analytics, or model calls.
- Verify path traversal and identifier rejection.
- Verify malformed and oversized request handling.
- Verify evidence replacement detection.
- Verify event alteration, deletion, and truncation detection.
- Verify bundles exclude credentials and keys.
- Verify container runs as a non-root user with a localhost-only published port.
- Verify dependency and CodeQL results are reviewed as bounded evidence.
- Confirm deployment claims remain limited to the reviewed profile.
