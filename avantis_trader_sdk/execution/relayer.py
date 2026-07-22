"""Live relayer client (`POST /v2/relay/queue`, `GET /v2/relay/{requestId}`).

TEMPORARY (branch v2-live-relayer): targets the live relayer-app
(avantis-backend-monorepo src/relayer-app) instead of blitz. Callers queue a
relay by action:

- ``BATCH_MARKET_EXECUTION`` / ``BATCH_POSITION_UPDATE`` carry an ``erc712``
  payload (userIntent, userSignature, pairIndex, orderType); the server
  fetches the price update and encodes the trading-contract call itself;
- ``TX_RELAY`` carries a ``type4`` payload (EIP-7702 smart-account tx);
- ``wallet`` is the originating EOA, used for logging/auth only;
- status: pending = ``success=false, errorMessage=null``; failed =
  ``errorMessage`` set; mined = ``success=true`` + ``receipt.transactionHash``.
  404 is treated as still-pending (mirrors the UI).
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

    async def queue(
        self, action: RelayAction, payload: dict[str, Any], wallet: str
    ) -> str:
        """Queue a relay; returns the requestId to poll."""
        body: dict[str, Any] = {
            "wallet": wallet,
            "action": action.value,
            "payload": payload,
        }
        # retries=0 in the transport: a blind re-POST after an ambiguous
        # network failure could double-broadcast.
        resp = await self._t.request(
            "POST", f"{self._base}/v2/relay/queue", json=body, retries=0
        )
        if resp.status_code >= 400:
            raise RelayError(
                f"relayer rejected queue ({resp.status_code}): {resp.text[:300]}"
            )
        data = resp.json()
        request_id = data.get("requestId") if isinstance(data, dict) else data
        if not request_id:
            raise RelayError(f"relayer returned no requestId: {resp.text[:300]}")
        return str(request_id)

    async def status(self, request_id: str) -> RelayStatus:
        resp = await self._t.request(
            "GET", f"{self._base}/v2/relay/{request_id}", allow_404=True
        )
        if resp.status_code == 404:
            # The doc is created synchronously on queue; a 404 is treated as
            # still-pending (replication lag), matching the UI behavior.
            return RelayStatus(settled=False)
        try:
            body = resp.json()
        except ValueError as exc:
            raise ApiError(
                f"relayer status returned non-JSON: {resp.text[:300]}",
                status=resp.status_code,
            ) from exc

        error_message = body.get("errorMessage")
        if error_message:
            return RelayStatus(
                settled=True, success=False, error_message=str(error_message)
            )
        receipt = body.get("receipt")
        tx_hash = (receipt or {}).get("transactionHash")
        if body.get("success") is True and tx_hash:
            return RelayStatus(settled=True, success=True, tx_hash=tx_hash, receipt=receipt)
        # Pending: success=false with no errorMessage yet.
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
