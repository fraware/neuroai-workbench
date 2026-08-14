from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock
from urllib.parse import urlparse


@dataclass
class RateLimiter:
    requests_per_minute: int
    _events: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))
    _lock: Lock = field(default_factory=Lock, repr=False)

    def _host_key(self, url: str) -> str:
        hostname = urlparse(url).hostname
        if hostname is None:
            return "unknown"
        return hostname.lower().rstrip(".")

    def _prune(self, window: deque[float], current: float) -> None:
        cutoff = current - 60.0
        while window and window[0] <= cutoff:
            window.popleft()

    def check(self, url: str, *, now: float | None = None) -> None:
        """Reserve one immediate host request or fail without sleeping.

        This method remains useful for callers that explicitly want fail-fast
        rate limiting. The mutation is serialized so concurrent callers cannot
        over-admit a host by racing on the same deque.
        """
        if self.requests_per_minute <= 0:
            return
        current = time.monotonic() if now is None else now
        host = self._host_key(url)
        with self._lock:
            window = self._events[host]
            self._prune(window, current)
            if len(window) >= self.requests_per_minute:
                raise ValueError(f"Rate limit exceeded for host {host!r}")
            window.append(current)

    def acquire(
        self,
        url: str,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> float:
        """Wait until one host request can be reserved and return total wait seconds.

        Admission and reservation happen under one lock. Sleeping happens
        outside the lock so unrelated hosts and other workers continue. This
        prevents a concurrent due-cycle executor from turning a configured
        host rate limit into synthetic collection failures.
        """
        if self.requests_per_minute <= 0:
            return 0.0
        host = self._host_key(url)
        waited = 0.0
        while True:
            current = clock()
            with self._lock:
                window = self._events[host]
                self._prune(window, current)
                if len(window) < self.requests_per_minute:
                    window.append(current)
                    return waited
                delay = max(0.0, window[0] + 60.0 - current)
            # Avoid a zero-delay busy loop around floating-point boundaries.
            if delay <= 0.0:
                delay = 1e-6
            sleeper(delay)
            waited += delay
