# ADR 0001 — Offline-first, localhost-only reference server

**Status:** Accepted

The reference implementation uses a local Python server and browser application with no remote assets. It binds to `127.0.0.1` by default.

This decision reduces data egress and dependency complexity. It does not provide authentication, encryption or production-grade network security.
