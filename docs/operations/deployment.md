# Deployment profiles

## Supported reference profile

- Single trusted user or assessment team.
- Local workstation or controlled virtual machine.
- Localhost-only server (loopback bind; no `NEUROAI_ALLOW_NETWORK`).
- Filesystem permissions managed by the host operating system.
- No raw evidence transfer unless authorised.

The reference container image and default `compose.yaml` follow this profile: the process listens on `127.0.0.1` inside the container and does not set `NEUROAI_ALLOW_NETWORK`. Docker port publish cannot reach a loopback-only listener; use `docker exec` health checks or run the CLI/server directly on the host for local access.

## Explicit network profile

`compose.network.yaml` is an opt-in overlay that binds `0.0.0.0`, sets `NEUROAI_ALLOW_NETWORK=1`, and publishes `127.0.0.1:8765` on the host:

```bash
docker compose -f compose.yaml -f compose.network.yaml up --build
```

This profile is not institutional deployment. It still requires reverse-proxy authentication, TLS, access controls, and a separate threat review — none of which the reference image provides. See [THREAT_MODEL.md](../../THREAT_MODEL.md).

## Unsupported without additional controls

- Internet-facing deployment.
- Multi-tenant hosting.
- Clinical or regulatory production records.
- Untrusted upload processing.
- Central storage of participant-private neural data.

Institutional deployments need identity and access management, TLS, encryption at rest, key management, backup and recovery, malware controls, audit retention, incident response, privacy review, penetration testing and operational ownership.
