
# Security policy

## Supported versions

Security fixes are applied to the current `0.2.x` line during the controlled pilot period. Earlier lines are retained for provenance and are not supported for new deployments.

## Reporting

Do not disclose vulnerabilities involving private neural data, participant records, credentials, unreleased assessment evidence, or exploitable deployment details in a public issue. Use the repository's private security-advisory channel.

## Reference-server boundary

The bundled server is intended for local trusted use. It has no built-in authentication, authorization, multi-tenant isolation, TLS termination, secrets manager, malware scanner, content disarm, or encrypted evidence store.

Default binding is `127.0.0.1`. Any non-local deployment requires a separate architecture with identity, encrypted transport and storage, host hardening, audit controls, backup and recovery, retention, incident response, and independent review.

## Security claims withheld

Passing tests, valid hashes, a valid event chain, a dependency scan, or a clean CodeQL run does not establish that a deployment is secure. Those results are bounded technical evidence only.
