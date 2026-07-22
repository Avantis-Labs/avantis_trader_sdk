"""Execution engine: routes signed actions to the chain.

TEMPORARY (branch v2-live-relayer): relays go to the live relayer-app
(`POST /v2/relay/queue`) instead of blitz.

Routes:
- ``relayer-batch``        signed EIP-712 intent -> erc712 payload
                           (BATCH_MARKET_EXECUTION / BATCH_POSITION_UPDATE);
                           the relayer fetches the price update and encodes
                           the trading-contract call server-side
- ``relayer-passthrough``  calldata wrapped in a type4 smart-account tx
                           -> TX_RELAY with a type4 payload
- ``rpc``                  normal signed transaction via the user's RPC
- ``txbuilder-relay``      normal signed transaction via POST {tx-builder}/v2/relay
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..config import AvantisConfig
from ..eip7702 import Call, GelatoDelegationEncoder
from ..eip7702.account import fresh_nonce
from ..errors import ConfigError, RelayError
from ..signing import BaseSigner, sign_intent
from ..transport import HttpTransport
from ..txbuilder import TxBuilderClient
from ..types import (
    INTENT_BATCH_ACTION,
    AggregatorOrderType,
    CallData,
    ExecutionMode,
    ExecutionReceipt,
    IntentPayload,
    RelayAction,
)
from .relayer import RelayerClient
from .rpc import JsonRpcClient


def _serialize_type4(tx_params: dict[str, Any]) -> dict[str, Any]:
    """Blitz-shaped txParams -> live relayer-app type4 payload.

    The relayer-app DTO wants string numerics, ``gas`` (not ``gasLimit``),
    and no value/transactionType (the server forces value=0, type=4).
    """
    return {
        "chainId": str(tx_params["chainId"]),
        "to": tx_params["to"],
        "data": tx_params["data"],
        "gas": str(tx_params["gasLimit"]),
        "authorizationList": [
            {
                "address": a["address"],
                "chainId": str(a["chainId"]),
                "nonce": str(a["nonce"]),
                "r": a["r"],
                "s": a["s"],
                "yParity": a["yParity"],
                "v": str(a["v"]),
            }
            for a in tx_params.get("authorizationList", [])
        ],
    }


class ExecutionEngine:
    def __init__(
        self,
        config: AvantisConfig,
        signer: BaseSigner | None,
        transport: HttpTransport,
        txbuilder: TxBuilderClient,
    ) -> None:
        self.config = config
        self.signer = signer
        self.txb = txbuilder
        self._transport = transport
        self.relayer = RelayerClient(
            transport,
            config.relayer_url,
            poll_interval_s=config.relay_poll_interval_s,
            poll_timeout_s=config.relay_poll_timeout_s,
        )
        self.rpc: JsonRpcClient | None = (
            JsonRpcClient(config.rpc_url, config.timeout_s) if config.rpc_url else None
        )
        self._chain_id: int | None = None
        self._trading_router: str | None = None
        self._encoder: GelatoDelegationEncoder | None = None

    # ------------------------------------------------------------------ utils

    def _require_signer(self) -> BaseSigner:
        if self.signer is None:
            raise ConfigError("This operation requires a signing key (AVANTIS_PRIVATE_KEY).")
        return self.signer

    async def chain_id(self) -> int:
        """Chain id from /v2/meta (cached; never hard-coded)."""
        if self._chain_id is None:
            meta = await self.txb.meta()
            self._chain_id = int(meta["chainId"])
            self._trading_router = meta["addresses"]["tradingRouter"]
        return self._chain_id

    async def trading_router(self) -> str:
        if self._trading_router is None:
            await self.chain_id()
        assert self._trading_router is not None
        return self._trading_router

    async def encoder(self) -> GelatoDelegationEncoder:
        if self._encoder is None:
            self._encoder = GelatoDelegationEncoder(
                signer=self._require_signer(),
                chain_id=await self.chain_id(),
                delegation_address=self.config.delegation_address,
                builder_code=self.config.builder_code,
            )
        return self._encoder

    async def _account_nonce(self, address: str) -> int:
        """EOA protocol nonce for the EIP-7702 authorization (0 if unknown).

        A stale nonce only matters for the very first delegation application;
        once the code is set, the authorization is redundant and ignored.
        """
        if self.rpc is None:
            return 0
        try:
            return await self.rpc.get_transaction_count(address)
        except Exception:
            return 0

    async def _estimate_gas_or_default(self, to: str, data: str, value: int = 0) -> int:
        if self.rpc is not None:
            try:
                estimated = await self.rpc.estimate_gas(
                    {"to": to, "data": data, "value": hex(value)}
                )
                return max(self.config.default_gas_limit, estimated)
            except Exception:
                pass
        return self.config.default_gas_limit

    async def _build_type4(self, calls: list[Call]) -> dict[str, Any]:
        signer = self._require_signer()
        encoder = await self.encoder()
        account_nonce = await self._account_nonce(signer.address)
        # Encode once with a pinned exec nonce, estimate gas on those exact
        # bytes, and reuse the same nonce in the final payload.
        exec_nonce = fresh_nonce()
        data = encoder.encode_call_data(calls, exec_nonce)
        gas = await self._estimate_gas_or_default(signer.address, "0x" + data.hex())
        # The UI attaches the authorization on every tx (idempotent once the
        # delegation code is set); mirror that for maximum compatibility.
        return encoder.build_type4(
            calls, gas=gas, account_nonce=account_nonce, exec_nonce=exec_nonce
        )

    # -------------------------------------------------------------- relayer

    async def submit_intent_batch(
        self,
        payload: IntentPayload,
        order_type: AggregatorOrderType,
        *,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Sign an intent and queue the batched execution via the live relayer.

        The relayer-app encodes the trading-contract call itself
        (executeMarketOrderBatched / executePositionUpdateBatched) from the
        erc712 payload: it fetches a fresh price update, appends the builder
        code, and sets the Pyth fee value server-side.
        """
        signer = self._require_signer()
        action = INTENT_BATCH_ACTION.get(payload.primary_type)
        if action is None:
            raise ConfigError(
                f"{payload.primary_type} is not a relayer-batch intent. TWAP/RFQ go "
                "through the trade API (type-4 passthrough); partial TP/SL through "
                "trade.partial_tp_sl (off-chain storage)."
            )
        signed = sign_intent(payload, signer)

        wallet = self.config.trader_address or signer.address
        request_id = await self.relayer.queue(
            action,
            {
                "erc712": {
                    "userIntent": payload.encoded_intent,
                    "userSignature": signed.signature,
                    "pairIndex": payload.pair_index,
                    "orderType": int(order_type),
                }
            },
            wallet,
        )
        receipt = ExecutionReceipt(
            route="relayer-batch", request_id=request_id, description=payload.intent
        )
        if wait:
            status = await self.relayer.wait(request_id)
            receipt.tx_hash = status.tx_hash
            receipt.raw = status.receipt
        return receipt

    async def submit_passthrough(
        self, calldata: CallData, *, wait: bool = True
    ) -> ExecutionReceipt:
        """Relay arbitrary calldata gaslessly via a type-4 smart-account tx."""
        signer = self._require_signer()
        calls = [Call.from_hex(calldata.to, calldata.data, calldata.value_wei)]
        tx_params = await self._build_type4(calls)
        wallet = self.config.trader_address or signer.address
        request_id = await self.relayer.queue(
            RelayAction.TX_RELAY, {"type4": _serialize_type4(tx_params)}, wallet
        )
        receipt = ExecutionReceipt(
            route="relayer-passthrough",
            request_id=request_id,
            description=calldata.description,
        )
        if wait:
            status = await self.relayer.wait(request_id)
            receipt.tx_hash = status.tx_hash
            receipt.raw = status.receipt
        return receipt

    # -------------------------------------------------------------- direct

    async def submit_direct(self, calldata: CallData, *, wait: bool = True) -> ExecutionReceipt:
        """Sign the calldata as a normal type-2 tx; broadcast via RPC or tx-builder relay."""
        signer = self._require_signer()
        if self.rpc is not None:
            nonce = await self.rpc.get_transaction_count(signer.address)
            gas = await self._estimate_gas_or_default(
                calldata.to, calldata.data, calldata.value_wei
            )
            max_fee, priority = await self.rpc.gas_fees()
            tx = {
                "chainId": await self.chain_id(),
                "to": calldata.to,
                "data": calldata.data,
                "value": calldata.value_wei,
                "nonce": nonce,
                "gas": gas,
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": priority,
            }
            raw, tx_hash = signer.sign_transaction(tx)
            await self.rpc.send_raw_transaction(raw)
            receipt = ExecutionReceipt(
                route="rpc", tx_hash=tx_hash, description=calldata.description
            )
            if wait:
                receipt.raw = await self.rpc.wait_for_receipt(tx_hash)
            return receipt

        # No RPC: sign with static params and use the tx-builder raw relay.
        # Nonce must come from somewhere — the tx-builder relay simulates from
        # the recovered signer, so a wrong nonce fails fast with a clear error.
        raise ConfigError(
            "Direct execution needs AVANTIS_RPC_URL for nonce/gas discovery. "
            "Alternatively use execution='relayer' (gasless, no RPC required)."
        )

    async def submit_via_txbuilder_relay(
        self, raw_transaction: str, *, wait: bool = True
    ) -> ExecutionReceipt:
        """Broadcast a pre-signed raw tx through POST {tx-builder}/v2/relay."""
        data = await self.txb.relay_raw(raw_transaction)
        tx_hash = data.get("hash")
        receipt = ExecutionReceipt(route="txbuilder-relay", tx_hash=tx_hash, raw=data)
        if wait and tx_hash:
            for _ in range(120):
                status = await self.txb.relay_status(tx_hash)
                if status.get("status") == "confirmed":
                    receipt.raw = status
                    return receipt
                if status.get("status") == "reverted":
                    raise RelayError(f"transaction {tx_hash} reverted", request_id=tx_hash)
                await asyncio.sleep(1.0)
        return receipt

    # -------------------------------------------------------------- routing

    @property
    def is_relayer_mode(self) -> bool:
        return self.config.execution is ExecutionMode.RELAYER

    async def aclose(self) -> None:
        if self.rpc is not None:
            await self.rpc.aclose()
