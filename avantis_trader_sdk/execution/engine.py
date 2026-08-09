"""Execution engine: routes signed actions to the chain.

Routes:
- ``batched-market``       market opens/closes/increases: signed EIP-712 intent
                           + optionally a pre-signed EIP-7702 type-4 tx
                           (server-side strategy switch when both are sent;
                           intent-only is the MM fast path) -> POST
                           {batched-market}/market/execute-batched, lifecycle
                           streamed back as SSE
- ``relayer-passthrough``  calldata wrapped in a type4 smart-account tx
                           -> blitz POST /relays (type 4)
- ``rpc``                  normal signed transaction via the user's RPC
- ``txbuilder-relay``      normal signed transaction via POST {tx-builder}/v2/relay

Global TP/SL updates (UpdateTpSlReq) do not pass through here anymore: they
are signed intents submitted to the core API price-triggers endpoint (see
``TradeApi.update_tp_sl``), which executes the operator entry point itself.
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
    BATCHED_MARKET_INTENT_KINDS,
    BATCHED_MARKET_ORDER_TYPES,
    AggregatorOrderType,
    CallData,
    ExecutionMode,
    ExecutionReceipt,
    IntentPayload,
)
from .batched_market import BatchedMarketClient
from .relayer import RelayerClient
from .rpc import JsonRpcClient


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
        self.batched_market = BatchedMarketClient(
            transport,
            config.batched_market_url,
            poll_interval_s=config.relay_poll_interval_s,
            timeout_s=config.relay_poll_timeout_s,
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

    async def _authorization_nonce(self, signer_address: str) -> int:
        """EOA protocol nonce the EIP-7702 authorization is signed over.

        A wrong nonce makes the authorization invalid, so the protocol skips
        it silently: fine once the Gelato delegation code is already set (the
        authorization is redundant), but the first application — or replacing
        a foreign delegation, e.g. a MetaMask-upgraded EOA — never happens and
        every smart-account call reverts.

        Delegate/API keys (the normal setup: register the delegate in the UI,
        export its key for the SDK) are fresh EOAs, so nonce 0 is correct and
        no RPC is needed. Signing with the trader EOA directly is the power
        path: its nonce is almost never 0, so an RPC (any Base endpoint) is
        required to read it.
        """
        if self.rpc is not None:
            return await self.rpc.get_transaction_count(signer_address)
        trader = self.config.trader_address
        if trader and trader.lower() != signer_address.lower():
            return 0  # delegate/API key: fresh EOA, nothing to read
        raise ConfigError(
            "Relayer mode with the trader EOA needs an RPC to read the EIP-7702 "
            "authorization nonce (a stale nonce is skipped on-chain and the "
            "transaction reverts). Set rpc_url / AVANTIS_RPC_URL to any Base RPC "
            "(e.g. https://mainnet.base.org), or sign with a delegate/API key."
        )

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
        account_nonce = await self._authorization_nonce(signer.address)
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
        calldata: CallData | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Sign a market intent and execute it through the batched-market API.

        Market opens/closes/increases (the batched-market allow-list) go to
        ``POST {batched-market}/market/execute-batched``, which injects a
        fresh price/spread per attempt server-side and streams the lifecycle
        back. The EIP-7702 leg is optional: pass the direct-route
        ``calldata`` to also send a pre-signed EIP-7702 transaction (the
        server then picks the execution mechanism); omit it to execute the
        signed intent directly — the market-maker fast path, with no
        tx-builder round-trip.
        """
        signer = self._require_signer()
        if (
            payload.primary_type not in BATCHED_MARKET_INTENT_KINDS
            or order_type not in BATCHED_MARKET_ORDER_TYPES
        ):
            raise ConfigError(
                f"{payload.primary_type} (order type {int(order_type)}) is not a "
                "batched-market intent. TWAP goes through trade.twap_* (twap-app "
                "intents); TP/SL through trade.update_tp_sl / trade.partial_tp_sl "
                "(core-API price-triggers)."
            )
        signed = sign_intent(payload, signer)

        eip7702: dict[str, Any] | None = None
        if calldata is not None:
            calls = [Call.from_hex(calldata.to, calldata.data, calldata.value_wei)]
            tx_params = await self._build_type4(calls)
            eip7702 = _relay_request_params(tx_params)
        outcome = await self.batched_market.execute(
            int(order_type),
            {
                "userIntent": payload.encoded_intent,
                "userSignature": signed.signature,
            },
            eip7702,
            wait=wait,
        )
        return ExecutionReceipt(
            route="batched-market",
            tracking_id=outcome.tracking_id or None,
            tx_hash=outcome.tx_hash,
            order_id=outcome.order_id,
            description=payload.intent,
            raw=outcome.terminal.data if outcome.terminal else None,
        )

    async def submit_passthrough(
        self, calldata: CallData, *, wait: bool = True
    ) -> ExecutionReceipt:
        """Relay arbitrary calldata gaslessly via a type-4 smart-account tx."""
        signer = self._require_signer()
        calls = [Call.from_hex(calldata.to, calldata.data, calldata.value_wei)]
        tx_params = await self._build_type4(calls)
        wallet = self.config.trader_address or signer.address
        request_id = await self.relayer.create(tx_params, wallet)
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


def _relay_request_params(tx_params: dict[str, Any]) -> dict[str, Any]:
    """Blitz ``txParams`` -> batched-market ``RelayRequestParamsDto``.

    The DTO wants chainId/gas/nonce as strings, ``gas`` instead of
    ``gasLimit``, and has no ``value``/``transactionType`` fields (type-4 is
    implied; smart-account relays carry no ETH).
    """
    return {
        "chainId": str(tx_params["chainId"]),
        "to": tx_params["to"],
        "data": tx_params["data"],
        "gas": str(tx_params["gasLimit"]),
        "authorizationList": [
            {
                "address": auth["address"],
                "chainId": str(auth["chainId"]),
                "nonce": str(auth["nonce"]),
                "r": auth["r"],
                "s": auth["s"],
                "yParity": auth["yParity"],
                "v": str(auth["v"]),
            }
            for auth in tx_params.get("authorizationList", [])
        ],
    }
