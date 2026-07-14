"""Operator relayer client (`POST /v2/relay/queue`, `GET /v2/relay/{id}`).

Semantics reverse-engineered from avantis-ui-v2 ``lib/relayer.ts``:
- queue returns the requestId as a plain string or ``{requestId|id}``
- status 404 means "not settled yet" (NOT an error)
- ``{errorMessage}`` -> failed; ``{success: true, receipt.transactionHash}`` -> done
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..errors import ApiError, RelayError, RelayTimeoutError
from ..transport import HttpTransport
from ..types import RelayAction, RelayStatus


class RelayerClient:
    def __init__(
        self,
        transport: HttpTransport,
        base_url: str,
        *,
        poll_interval_s: float = 1.0,
        poll_timeout_s: float = 60.0,
    ) -> None:
        self._t = transport
        self._base = base_url.rstrip("/")
        self.poll_interval_s = poll_interval_s
        self.poll_timeout_s = poll_timeout_s

    async def queue(self, wallet: str, action: RelayAction, payload: dict[str, Any]) -> str:
        # retries=0: a retried POST could enqueue the same signed action twice.
        # (Nonces make double-execution impossible, but the duplicate would
        # surface as a confusing InvalidNonce failure on the second run.)
        resp = await self._t.request(
            "POST",
            f"{self._base}/v2/relay/queue",
            json={"wallet": wallet, "action": action.value, "payload": payload},
            retries=0,
        )
        text = resp.text
        if resp.status_code >= 400:
            raise RelayError(f"relayer queue HTTP {resp.status_code}: {text[:300]}")
        try:
            body = resp.json()
        except ValueError:
            body = text
        request_id = (
            body if isinstance(body, str) else (body.get("requestId") or body.get("id"))
        )
        if not request_id:
            raise RelayError(f"relayer queue returned no requestId: {text[:300]}")
        return str(request_id)

    async def status(self, request_id: str) -> RelayStatus:
        resp = await self._t.request(
            "GET", f"{self._base}/v2/relay/{request_id}", allow_404=True
        )
        if resp.status_code == 404:
            return RelayStatus(settled=False)
        try:
            body = resp.json()
        except ValueError as exc:
            raise ApiError(
                f"relayer status returned non-JSON: {resp.text[:300]}",
                status=resp.status_code,
            ) from exc
        if body.get("errorMessage"):
            return RelayStatus(
                settled=True, success=False, error_message=str(body["errorMessage"])
            )
        receipt = body.get("receipt") or {}
        tx_hash = receipt.get("transactionHash")
        if body.get("success") is True and tx_hash:
            return RelayStatus(settled=True, success=True, tx_hash=tx_hash, receipt=receipt)
        return RelayStatus(settled=False)

    async def wait(self, request_id: str, timeout_s: float | None = None) -> RelayStatus:
        timeout = timeout_s if timeout_s is not None else self.poll_timeout_s
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            st = await self.status(request_id)
            if st.settled:
                if not st.success:
                    raise RelayError(
                        st.error_message or "relay failed", request_id=request_id
                    )
                return st
            await asyncio.sleep(self.poll_interval_s)
        raise RelayTimeoutError(
            f"relay {request_id} not settled after {timeout:.0f}s", request_id=request_id
        )
