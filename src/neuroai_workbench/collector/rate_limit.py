from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class RateLimiter:
    requests_per_minute: int
    _events: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def _host_key(self, url: str) -> str:
        hostname = urlparse(url).hostname
        if hostname is None:
            return "unknown"
        return hostname.lower().rstrip(".")

    def check(self, url: str, *, now: float | None = None) -> None:
        if self.requests_per_minute <= 0:
            return
        current = time.monotonic() if now is None else now
        host = self._host_key(url)
        window = self._events[host]
        cutoff = current - 60.0
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= self.requests_per_minute:
            raise ValueError(f"Rate limit exceeded for host {host!r}")
        window.append(current)
