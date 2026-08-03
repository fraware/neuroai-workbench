# Protect main ruleset verification

- Ruleset: `Protect main` (`20116255`)
- Status: **FAIL**
- Checks: 10/12 passed
- Required status contexts: 11
- Bypass actors recorded: 0

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
| At least one approving review is required | FAIL |
| Required-status-check rule is present | PASS |
| Hosted required checks match the repository contract | FAIL |
| Required checks have unique contexts | PASS |
| Strict required-status-check policy is enabled | PASS |

## Boundary

This report verifies the GitHub-hosted ruleset response acquired for the named repository. It does not authenticate human reviewers, establish scientific or release authority, or prove that future settings remain unchanged after the recorded acquisition.

The raw GitHub Rules API response is retained as a workflow artifact and is not committed.
