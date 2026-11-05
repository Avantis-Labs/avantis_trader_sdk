"""Minimal async JSON-RPC client (no web3 dependency).

Used for: EOA nonces + code checks (EIP-7702 authorizations), gas estimation,
direct-route broadcasting, and receipt polling.
"""

from __future__ import annotations

import asyncio
import itertools
from typing import Any

import httpx

from ..errors import RpcError, TransactionRevertedError

_ids = itertools.count(1)

# Default ``wait_for_receipt`` poll interval. Base has produced a block every
# 200 ms since Denim (mainnet, 2026-11-05 18:00 UTC), so 0.25 s finds a receipt
# within about one block of it landing.
_DEFAULT_RECEIPT_POLL_S = 0.25


class JsonRpcClient:
    def __init__(self, url: str, timeout_s: float = 30.0) -> None:
        self.url = url
        self._client = httpx.AsyncClient(timeout=timeout_s)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def call(self, method: str, params: list[Any] | None = None) -> Any:
        payload = {"jsonrpc": "2.0", "id": next(_ids), "method": method, "params": params or []}
        try:
            resp = await self._client.post(self.url, json=payload)
        except httpx.TransportError as exc:
            raise RpcError(f"RPC transport error ({method}): {exc}") from exc
        body = resp.json()
        if "error" in body and body["error"]:
            err = body["error"]
            raise RpcError(
                f"RPC error on {method}: {err.get('message')}",
                code=err.get("code"),
                data=err.get("data"),
            )
        return body.get("result")

    # -- typed helpers ---------------------------------------------------------

    async def chain_id(self) -> int:
        return int(await self.call("eth_chainId"), 16)

    async def get_transaction_count(self, address: str, block: str = "pending") -> int:
        """Account nonce at ``block``. The default stays ``"pending"`` on purpose.

        Denim (Base mainnet, 2026-11-05 18:00 UTC) removes Flashblocks. The
        ``pending`` tag still works, but it no longer means "preconfirmed": do
        not read it as proof that an earlier transaction landed. Wait for that
        transaction's receipt (``wait_for_receipt``, about 200 ms) when order
        matters.
        """
        return int(await self.call("eth_getTransactionCount", [address, block]), 16)

    async def get_code(self, address: str) -> str:
        return await self.call("eth_getCode", [address, "latest"]) or "0x"

    async def get_balance(self, address: str) -> int:
        return int(await self.call("eth_getBalance", [address, "latest"]), 16)

    async def estimate_gas(self, tx: dict[str, Any]) -> int:
        return int(await self.call("eth_estimateGas", [tx]), 16)

    async def gas_fees(self) -> tuple[int, int]:
        """Returns (max_fee_per_gas, max_priority_fee_per_gas)."""
        try:
            priority = int(await self.call("eth_maxPriorityFeePerGas"), 16)
        except RpcError:
            priority = 1_000_000  # 0.001 gwei floor on Base
        block = await self.call("eth_getBlockByNumber", ["latest", False])
        base_fee = int(block.get("baseFeePerGas", "0x0"), 16)
        return base_fee * 2 + priority, priority

    async def send_raw_transaction(self, raw: bytes | str) -> str:
        raw_hex = raw if isinstance(raw, str) else "0x" + raw.hex()
        return await self.call("eth_sendRawTransaction", [raw_hex])

    async def get_receipt(self, tx_hash: str) -> dict[str, Any] | None:
        return await self.call("eth_getTransactionReceipt", [tx_hash])

    async def wait_for_receipt(
        self,
        tx_hash: str,
        timeout_s: float = 120.0,
        poll_s: float = _DEFAULT_RECEIPT_POLL_S,
    ) -> dict[str, Any]:
        """Poll ``eth_getTransactionReceipt`` until the transaction is mined.

        ``poll_s`` defaults to 0.25 s (one 200 ms Base block, rounded up). Raise
        it for a rate-limited public RPC. Raises ``TransactionRevertedError`` for
        a failed receipt and ``RpcError`` once ``timeout_s`` (default 120 s) has
        passed.
        """
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            receipt = await self.get_receipt(tx_hash)
            if receipt is not None:
                if int(receipt.get("status", "0x0"), 16) != 1:
                    raise TransactionRevertedError(
                        f"transaction {tx_hash} reverted", tx_hash=tx_hash
                    )
                return receipt
            await asyncio.sleep(poll_s)
        raise RpcError(f"timed out waiting for receipt of {tx_hash}")
