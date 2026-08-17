"""Async HTTP transport shared by all API clients.

Handles the tx-builder ``{ok, data|error}`` envelope, the avantis-server
``{success, ...}`` wrapper, retries on transient failures, and mapping of
error codes to typed exceptions.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ._version import __version__
from .errors import ApiError, api_error_from_envelope

_RETRYABLE_STATUS = {502, 503, 504}
_DEFAULT_RETRIES = 2


class HttpTransport:
    """Thin wrapper over a shared httpx.AsyncClient."""

    def __init__(self, timeout_s: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout_s,
            headers={"User-Agent": f"avantis-trader-sdk/{__version__}"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def stream(
        self,
        method: str,
        url: str,
        *,
        json: Any = None,
        read_timeout_s: float | None = None,
    ):
        """Streaming request (SSE). Returns httpx's async context manager.

        ``read_timeout_s`` bounds the gap between chunks; it must exceed the
        server's keep-alive interval (batched-market heartbeats every 15s),
        not the total stream lifetime.
        """
        timeout = httpx.Timeout(10.0, read=read_timeout_s)
        return self._client.stream(method, url, json=json, timeout=timeout)

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        retries: int = _DEFAULT_RETRIES,
        allow_404: bool = False,
    ) -> httpx.Response:
        attempt = 0
        while True:
            try:
                resp = await self._client.request(method, url, params=params, json=json)
            except httpx.TransportError as exc:
                if attempt < retries:
                    attempt += 1
                    await asyncio.sleep(0.25 * 2**attempt)
                    continue
                raise ApiError(f"network error calling {url}: {exc}", url=url) from exc
            if resp.status_code in _RETRYABLE_STATUS and attempt < retries:
                attempt += 1
                await asyncio.sleep(0.25 * 2**attempt)
                continue
            if resp.status_code == 404 and allow_404:
                return resp
            return resp

    # -- tx-builder envelope -------------------------------------------------

    async def txb(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        """Call a tx-builder endpoint and unwrap ``{ok, data}`` / raise on error."""
        resp = await self.request(method, url, params=params, json=json)
        try:
            body = resp.json()
        except ValueError as exc:
            raise ApiError(
                f"non-JSON response ({resp.status_code}) from {url}",
                status=resp.status_code,
                url=url,
            ) from exc
        if isinstance(body, dict) and body.get("ok") is True:
            return body.get("data")
        if isinstance(body, dict) and body.get("ok") is False:
            raise api_error_from_envelope(
                body.get("error") or {}, status=resp.status_code, url=url
            )
        if resp.status_code >= 400:
            raise ApiError(
                f"HTTP {resp.status_code} from {url}: {resp.text[:300]}",
                status=resp.status_code,
                url=url,
            )
        return body

    # -- plain JSON APIs (data/core/history/risk/feed) -----------------------

    async def json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        allow_404: bool = False,
    ) -> Any:
        resp = await self.request(method, url, params=params, json=json, allow_404=allow_404)
        if allow_404 and resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise ApiError(
                f"HTTP {resp.status_code} from {url}: {resp.text[:300]}",
                status=resp.status_code,
                url=url,
            )
        if not resp.content:  # e.g. 200/204 with empty body (core API deletes)
            return None
        try:
            return resp.json()
        except ValueError as exc:
            raise ApiError(f"non-JSON response from {url}", url=url) from exc
