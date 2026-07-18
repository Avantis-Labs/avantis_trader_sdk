"""Client for the avantis-tx-builder API (`/v2/*`).

This is the SDK's payload factory: calldata for the direct route, EIP-712
intents for the relayer route, plus meta/reads. All build endpoints accept
POST JSON with human units; numeric values are sent as strings.
"""

from __future__ import annotations

from typing import Any

from .transport import HttpTransport
from .types import CallData, IntentPayload, to_api_num


class TxBuilderClient:
    def __init__(self, transport: HttpTransport, base_url: str) -> None:
        self._t = transport
        self._base = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    @staticmethod
    def _clean(params: dict[str, Any]) -> dict[str, Any]:
        """Drop Nones and stringify numbers (exact decimal semantics)."""
        out: dict[str, Any] = {}
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, bool):
                out[k] = v
            elif isinstance(v, (int, float)):
                out[k] = to_api_num(v)
            else:
                out[k] = v
        return out

    # -- meta / reads ---------------------------------------------------------

    async def meta(self) -> dict[str, Any]:
        return await self._t.txb("GET", self._url("/v2/meta"))

    async def pairs(self) -> Any:
        return await self._t.txb("GET", self._url("/v2/pairs"))

    async def nonce(self, trader: str, check: int | None = None) -> dict[str, Any]:
        params = self._clean({"trader": trader, "check": check})
        return await self._t.txb("GET", self._url("/v2/nonce"), params=params)

    async def positions(self, trader: str) -> dict[str, Any]:
        return await self._t.txb("GET", self._url("/v2/positions"), params={"trader": trader})

    async def delegation(self, trader: str, delegate: str) -> dict[str, Any]:
        return await self._t.txb(
            "GET", self._url("/v2/delegation"), params={"trader": trader, "delegate": delegate}
        )

    async def allowance(self, trader: str, spender: str | None = None) -> dict[str, Any]:
        params = self._clean({"trader": trader, "spender": spender})
        return await self._t.txb("GET", self._url("/v2/allowance"), params=params)

    async def lp_state(self, owner: str | None = None) -> dict[str, Any]:
        params = self._clean({"owner": owner})
        return await self._t.txb("GET", self._url("/v2/lp/state"), params=params)

    # -- builders --------------------------------------------------------------

    async def calldata(self, path: str, **params: Any) -> CallData:
        """POST a calldata builder endpoint, e.g. ``calldata("/v2/trade/open", ...)``."""
        data = await self._t.txb("POST", self._url(path), json=self._clean(params))
        return CallData.model_validate(data)

    async def intent(self, path: str, **params: Any) -> IntentPayload:
        """POST an intent builder endpoint, e.g. ``intent("/v2/intents/open", ...)``."""
        data = await self._t.txb("POST", self._url(path), json=self._clean(params))
        return IntentPayload.model_validate(data)

    # -- raw-tx relay (direct route without user RPC) ---------------------------

    async def relay_raw(self, raw_transaction: str, skip_simulation: bool = False) -> dict[str, Any]:
        return await self._t.txb(
            "POST",
            self._url("/v2/relay"),
            json={"rawTransaction": raw_transaction, "skipSimulation": skip_simulation},
        )

    async def relay_status(self, tx_hash: str) -> dict[str, Any]:
        return await self._t.txb("GET", self._url(f"/v2/relay/{tx_hash}"))
