
# Security policy

## Supported versions

The latest tagged line documented by this repository is `v0.2.1`; `main` currently identifies as `0.3.0.dev0`, a **development build, not a published `v0.3.0` release**. The previously documented controlled-pilot maintenance line is `0.2.x`. A security fix landing on `main` does **not** automatically reach a tagged `0.2.x` release: any supported-line backport needs a separately reviewed patch and published release/advisory record. Historical tags are preserved for provenance. Verify the actual published releases and repository security advisories before deciding which build to deploy; development CI success is not a support guarantee.

## Reporting

Do not disclose vulnerabilities involving private neural data, participant records, credentials, unreleased assessment evidence, or exploitable deployment details in a public issue. Use the repository's private security-advisory channel.

## Reference-server boundary

The bundled server is intended for local trusted use. It has no built-in authentication, authorization, multi-tenant isolation, TLS termination, secrets manager, malware scanner, content disarm, or encrypted evidence store.

Default binding is `127.0.0.1`. Any non-local deployment requires a separate architecture with identity, encrypted transport and storage, host hardening, audit controls, backup and recovery, retention, incident response, and independent review.

## Security claims withheld

Passing tests, valid hashes, a valid event chain, a dependency scan, or a clean CodeQL run does not establish that a deployment is secure. Those results are bounded technical evidence only.
