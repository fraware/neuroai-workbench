from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import BoundedSemaphore, Lock
from urllib.parse import urlparse

from .http_client import HttpRequest, HttpTransport, TransportResult


def host_from_url(url: str) -> str:
    """Return the canonical hostname used for transport concurrency accounting."""
    hostname = urlparse(url).hostname
    return hostname.lower().rstrip(".") if hostname else "unknown"


class HostPermitPool:
    """Thread-safe per-host permit registry shared by all HTTP sends in one scheduler run."""

    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("per-host transport limit must be >= 1")
        self.limit = limit
        self._lock = Lock()
        self._permits: dict[str, BoundedSemaphore] = {}

    def _permit(self, host: str) -> BoundedSemaphore:
        with self._lock:
            permit = self._permits.get(host)
            if permit is None:
                permit = BoundedSemaphore(self.limit)
                self._permits[host] = permit
            return permit

    @contextmanager
    def acquire(self, url: str) -> Iterator[str]:
        host = host_from_url(url)
        permit = self._permit(host)
        permit.acquire()
        try:
            yield host
        finally:
            permit.release()


@dataclass(frozen=True)
class HostLimitedTransport:
    """Limit every actual transport send, including redirect hops, by destination host."""

    inner: HttpTransport
    max_workers_per_host: int
    _permits: HostPermitPool = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_permits", HostPermitPool(self.max_workers_per_host))

    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> TransportResult:
        with self._permits.acquire(request.url):
            return self.inner.send(
                request,
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
            )
