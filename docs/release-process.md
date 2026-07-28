# Release process

1. Freeze the v4.2 resource inputs and record checksums.
2. Run compilation, unit, CLI, API, migration and reference-case validation tests.
3. Generate the software bill of materials and dependency record.
4. Create the example workspace and controlled release report.
5. Initialize Git history and tag the release candidate.
6. Build wheel and source distribution.
7. Generate checksum manifests and archive integrity records.
8. Preserve all failed checks and remediation history in the release verification record.

Release integrity confirms artifact identity. It does not establish production security or institutional adoption.
