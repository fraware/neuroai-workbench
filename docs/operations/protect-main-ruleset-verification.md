# Protect main ruleset verification

- Acquired at: `2026-08-03T16:17:10Z`
- Ruleset: `Protect main` (`20116255`)
- Status: **FAIL**
- Checks: 13/14 passed
- Required status contexts: 11
- Approval count: 0
- Review-thread resolution: True
- Merge methods: squash
- Bypass actors recorded: 0
- Rules API update succeeded: False

## Check results

| Check | Status |
|---|---|
| Ruleset ID | PASS |
| Ruleset name | PASS |
| Ruleset enforcement is active | PASS |
| Ruleset targets branches | PASS |
| Ruleset includes the default branch | PASS |
| Ruleset does not exclude the default branch | PASS |
| Pull-request rule is present | PASS |
| Approving-review count matches the core-development policy | PASS |
| Review-thread resolution policy matches | PASS |
| Allowed merge methods match | PASS |
| Required-status-check rule is present | PASS |
| Hosted required checks match the repository contract | FAIL |
| Required checks have unique contexts | PASS |
| Strict required-status-check policy is enabled | PASS |

## Boundary

This report verifies the GitHub-hosted ruleset response acquired for the named repository. It does not authenticate human reviewers, establish scientific or release authority, or prove that future settings remain unchanged after the recorded acquisition.

The raw pre-update and post-update GitHub Rules API responses are retained as workflow artifacts and are not committed.
