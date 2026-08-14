from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..credentials import CredentialProvider, refuse_embedded_secrets_in_request, refuse_secrets_in_value
from ..errors import CollectionFailureError
from ..http_client import HttpRequest, HttpTransport
from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter


@dataclass(frozen=True)
class AuthHeaderTransport:
    inner: HttpTransport
    credential_provider: CredentialProvider
    source_id: str

    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        header = self.credential_provider.authorization_header(self.source_id)
        if not header:
            raise CollectionFailureError(
                "AUTHENTICATION_REQUIRED",
                "Controlled authenticated download requires runtime credentials outside collection records",
            )
        headers = dict(request.headers)
        headers["Authorization"] = header
        return self.inner.send(
            HttpRequest(request.method, request.url, headers),
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )


class AuthenticatedDownloadStub(HttpCollectorAdapter):
    adapter_id = "auth_download"

    _SOURCE_CLASS = "CONTROLLED_AUTHENTICATED_DOWNLOAD"

    def __init__(
        self,
        collector: HttpCollector,
        *,
        credential_provider: CredentialProvider,
    ) -> None:
        super().__init__(collector)
        self.credential_provider = credential_provider

    def supports_source_class(self, source_class: str) -> bool:
        return source_class == self._SOURCE_CLASS

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
    ) -> CollectionOutcome:
        """Collect with request-local credential transport.

        The shared collector transport is never mutated. A transient collector
        shares only the synchronized host-rate limiter and the DNS resolver
        configuration, so concurrent authenticated and public requests cannot
        inherit each other's transport or credentials.
        """
        refuse_embedded_secrets_in_request(request)
        source_id = str(request["source_id"])
        local = HttpCollector(
            config=self.collector.config,
            transport=AuthHeaderTransport(
                self.collector.http_client.transport,
                self.credential_provider,
                source_id,
            ),
            quarantine_root=self.collector.quarantine_root,
            pace_rate_limits=self.collector.pace_rate_limits,
            sleeper=self.collector.sleeper,
            monotonic_clock=self.collector.monotonic_clock,
        )
        local.rate_limiter = self.collector.rate_limiter
        local.http_client.dns_guard = self.collector.http_client.dns_guard
        outcome = local.collect(
            request,
            prior_capture=prior_capture,
            attempt_count=attempt_count,
        )
        if outcome.kind == "result":
            refuse_secrets_in_value(outcome.record, label="collection result")
        elif outcome.kind == "failure":
            refuse_secrets_in_value(outcome.record, label="collection failure")
        return outcome
