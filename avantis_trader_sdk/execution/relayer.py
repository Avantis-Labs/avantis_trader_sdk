"""Blitz relayer client (`POST /relays`, `GET /relays/{requestId}`,
`GET /relays/by-tx-hash/{txHash}`).

The blitz relayer (avantis-backend-monorepo src/blitz-relayer-app) is a pure
transaction broadcaster: callers submit ready-to-broadcast ``txParams`` and it
handles wallet selection, nonces, gas bumping, and receipt tracking.

- type-2 relays may only target whitelisted contracts (the TradingRouter);
- type-4 (EIP-7702) relays may target any account (delegated smart accounts);
- ``wallet`` is the originating EOA, used only for broadcast routing;
- status lifecycle: ``Inflight`` -> ``Finalised`` (mined; check
  ``receipt.status`` for revert) or ``Failed`` (timed out / rejected).
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..errors import ApiError, RelayError, RelayTimeoutError
from ..transport import HttpTransport
from ..types import RelayStatus


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

    async def create(self, tx_params: dict[str, Any], wallet: str | None = None) -> str:
        """Submit txParams for broadcast; returns the requestId to poll.

        503 means every relayer wallet is busy; retried a few times since it
        clears as soon as an in-flight relay settles.
        """
        body: dict[str, Any] = {"txParams": tx_params}
        if wallet:
            body["wallet"] = wallet

        last_error = ""
        for attempt in range(4):
            # retries=0 in the transport: a blind re-POST after an ambiguous
            # network failure could double-broadcast.
            resp = await self._t.request(
                "POST", f"{self._base}/relays", json=body, retries=0
            )
            if resp.status_code == 503:  # all wallets busy
                last_error = resp.text[:200]
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                raise RelayError(
                    f"blitz relayer rejected relay ({resp.status_code}): {resp.text[:300]}"
                )
            data = resp.json()
            request_id = data.get("requestId")
            if not request_id:
                raise RelayError(f"blitz relayer returned no requestId: {resp.text[:300]}")
            return str(request_id)
        raise RelayError(f"blitz relayer busy (503) after retries: {last_error}")

    async def status(self, request_id: str) -> RelayStatus:
        resp = await self._t.request(
            "GET", f"{self._base}/relays/{request_id}", allow_404=True
        )
        if resp.status_code == 404:
            raise RelayError(f"unknown relay {request_id}", request_id=request_id)
        return self._parse_status(resp)

    async def status_by_tx_hash(self, tx_hash: str) -> RelayStatus | None:
        """Look up a relay by its broadcast transaction hash.

        ``GET /relays/by-tx-hash/{txHash}``; returns None when the hash is not
        known to the relayer (unknown hash answers 200 with a null body).
        """
        resp = await self._t.request(
            "GET", f"{self._base}/relays/by-tx-hash/{tx_hash}", allow_404=True
        )
        if resp.status_code == 404 or not resp.content or resp.text.strip() in ("", "null"):
            return None
        return self._parse_status(resp)

    def _parse_status(self, resp) -> RelayStatus:
        try:
            body = resp.json()
        except ValueError as exc:
            raise ApiError(
                f"blitz relayer status returned non-JSON: {resp.text[:300]}",
                status=resp.status_code,
            ) from exc

        state = body.get("status")
        receipt = body.get("receipt")
        if state == "Failed":
            return RelayStatus(
                settled=True, success=False, error_message="relay failed (timed out)"
            )
        if state == "Finalised":
            tx_hash = (receipt or {}).get("transactionHash") or (receipt or {}).get("hash")
            reverted = _receipt_reverted(receipt)
            if reverted:
                return RelayStatus(
                    settled=True,
                    success=False,
                    tx_hash=tx_hash,
                    receipt=receipt,
                    error_message=f"transaction {tx_hash} reverted",
                )
            return RelayStatus(settled=True, success=True, tx_hash=tx_hash, receipt=receipt)
        # Pending / Inflight
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


def _receipt_reverted(receipt: dict[str, Any] | None) -> bool:
    if not receipt:
        return False
    status = receipt.get("status")
    if status is None:
        return False
    if isinstance(status, str):
        return int(status, 16 if status.startswith("0x") else 10) == 0
    return int(status) == 0
