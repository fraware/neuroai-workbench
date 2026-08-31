# DNS-pinned production HTTP transport

Status: draft implementation contract. This document does not authorize network execution.

## Purpose

The collector resolves and validates public DNS targets before transport. A production transport must contact only an IP literal from that validated set; otherwise DNS validation and socket connection are separated by a time-of-check/time-of-use gap.

## Security boundary

`HttpClient` performs URL-policy validation and request-scoped DNS validation for every redirect hop. It passes the exact approved address set on `HttpRequest.validated_addresses`.

`PinnedSocketHttpTransport` then:

- requires a non-empty validated address set;
- independently confirms every supplied address is a globally routable IP literal;
- opens a socket directly to the numeric IP, without a second hostname-resolution path;
- preserves the normalized original hostname in the HTTP `Host` header;
- for HTTPS, uses the normalized original hostname as TLS `server_hostname`, so the default SSL context performs SNI and certificate hostname validation against the URL identity;
- follows no redirects; redirect acceptance and fresh DNS validation remain `HttpClient` responsibilities;
- permits GET only;
- rejects caller overrides of `Host` and `Connection`;
- rejects CR/LF injection in method, target and headers;
- bounds the raw body returned to the existing decompression/content-type layer;
- retries connection failures only across the supplied approved IP set and never falls back to hostname resolution or proxy configuration.

The transport does not itself create evidence, Sources, monitors, assessments or releases.

## Provenance boundary

Collection results retain the request-scoped DNS-approved address set, rebinding check, and the actual connected IP from `TransportResponse.connected_address`. The transport does not keep mutable `last_connected_address` state.

## Quarantine boundary

A successful collector operation writes retrieved bytes to quarantine and marks them `RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED`. The returned `CollectionOutcome` exposes the persisted quarantine record to controlled callers, but this does not approve the record for monitoring handoff. Quarantine approval remains a separate explicit operation.

## Authority boundary

This capability is reusable S1 transport infrastructure only. Callers remain responsible for explicit network authorization, source/monitor scope, collection-request construction, quarantine review, monitoring handoff and any later registry/release decision.
