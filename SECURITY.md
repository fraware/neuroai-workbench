# Security policy

## Supported version

Security fixes are applied to the current `0.1.x` line during the pilot period.

## Reporting

Do not disclose vulnerabilities involving private neural data, participant records, credentials, or unreleased assessment evidence in a public issue. Contact the maintainers through the repository’s private security-advisory channel after publication.

## Trust boundary

The reference server is intended for local trusted use. It has no built-in authentication, authorization, multi-tenant isolation, TLS termination, secrets manager, malware scanner, content disarm, or encrypted evidence store.

Default binding is `127.0.0.1`. Binding to another interface requires a separately secured reverse proxy, identity layer, encrypted storage, host hardening, audit controls, backup policy, and an independent security review.

## Security claims explicitly withheld

A passing test suite, valid event chain, valid file digest, or clean dependency scan does not establish that a deployment is secure. Vulnerability testing and red-team evidence remain separate assessment objects under v4.2.
