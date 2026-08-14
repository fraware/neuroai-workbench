# Destination-host concurrency invariant

The operational collector enforces `max_workers_per_host` at the **actual HTTP transport-send boundary**, not only around the logical source or the first requested URL.

This placement is required because multiple independent entry URLs can redirect or adapt into the same destination host. A scheduler-level permit keyed only by the initial URL would allow redirect convergence to exceed the intended destination-host concurrency ceiling.

`HostLimitedTransport` therefore wraps the shared transport supplied to all collector adapters. Every actual send acquires a permit keyed by the canonical hostname of that request URL and releases it after the transport call returns or raises. Redirect hops pass through the same wrapper, and request-local authenticated transports delegate to the same bounded transport, so they inherit the identical host limit without sharing credentials.

The invariant is tested with distinct entry hosts redirecting concurrently into one shared destination host: aggregate cross-host concurrency must remain greater than the destination limit, while simultaneous sends to the shared host never exceed `max_workers_per_host`.

This is an operational resource and source-safety guarantee. It does not establish source truth, assessment validity, governance approval, or release authority.
