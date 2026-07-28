"""User-facing trading surface.

Every method follows the same recipe:
1. Build the payload via tx-builder (intent for the relayer route, calldata
   for the direct route / passthrough).
2. Route through the ExecutionEngine.

All amounts are human units (100 = 100 USDC, 10 = 10x). ``pair`` accepts
either a symbol ("ETH/USD", "eth-usd") or a pair index.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..base_api import ExecutingApi
from ..errors import ConfigError
from ..execution.local_intents import LocalIntentBuilder
from ..signing import sign_intent
from ..types import (
    AggregatorOrderType,
    ExecutionReceipt,
    IntentPayload,
    MarginAction,
    Num,
    OrderType,
    Side,
    TriggerType,
)

PairRef = str | int


def _pair_params(pair: PairRef) -> dict[str, Any]:
    if isinstance(pair, int):
        return {"pairIndex": pair}
    return {"pair": pair}


class TradeApi(ExecutingApi):
    _local: LocalIntentBuilder | None = None  # lazy; for locally-built intents

    async def _local_intents(self) -> LocalIntentBuilder:
        """Local builder for the off-chain-verified intents (TwapCancelReq,
        CancelOffchainOrder). The tx-builder also serves these
        (/v2/intents/twap-cancel, /v2/intents/offchain-cancel — digest-equal
        by golden vectors); building locally just skips the round-trip since
        neither needs any chain state."""
        if self._local is None:
            self._local = LocalIntentBuilder(
                await self._engine.chain_id(), await self._engine.trading_router()
            )
        return self._local

    async def _intent_and_calldata(
        self,
        intent_path: str,
        calldata_path: str,
        params: dict[str, Any],
        **intent_extra: Any,
    ) -> tuple[IntentPayload, Any]:
        """Both encodings of the same order, fetched concurrently.

        The batched-market endpoint requires an EIP-712 intent AND a
        pre-signed EIP-7702 transaction on every request (the server decides
        which mechanism executes), so market flows always build both.
        """
        return await asyncio.gather(
            self._txb.intent(intent_path, **params, **intent_extra),
            self._calldata(calldata_path, params),
        )

    # ------------------------------------------------------------------ opens

    async def market_open(
        self,
        pair: PairRef,
        side: Side | str,
        collateral: Num,
        leverage: Num,
        *,
        open_price: Num | None = None,
        take_profit: Num | None = None,
        stop_loss: Num | None = None,
        slippage_percent: Num = 1,
        zero_fee: bool = False,
        skip_validation: bool = False,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Open a market position (or a zero-fee/PnL position with zero_fee=True).

        ``open_price`` is the reference price the fill is validated against
        (± slippage_percent); resolved from the live feed when omitted.
        """
        order_type = OrderType.MARKET_PNL if zero_fee else OrderType.MARKET
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "side": Side(side).value,
            "orderType": order_type.value,
            "collateralUsdc": collateral,
            "leverage": leverage,
            "openPrice": open_price,
            "slippagePercent": slippage_percent,
            "takeProfit": take_profit,
            "stopLoss": stop_loss,
            "skipValidation": skip_validation or None,
        }
        if self._engine.is_relayer_mode:
            intent, calldata = await self._intent_and_calldata(
                "/v2/intents/open", "/v2/trade/open", params
            )
            agg = (
                AggregatorOrderType.MARKET_OPEN_PNL
                if zero_fee
                else AggregatorOrderType.MARKET_OPEN
            )
            return await self._engine.submit_intent_batch(
                intent, agg, calldata=calldata, wait=wait
            )
        return await self._engine.submit_direct(
            await self._calldata("/v2/trade/open", params), wait=wait
        )

    async def market_open_coin(
        self,
        pair: PairRef,
        side: Side | str,
        collateral: Num,
        coin_exposure: Num,
        *,
        leverage: Num,
        min_leverage: Num | None = None,
        max_leverage: Num | None = None,
        open_price: Num | None = None,
        slippage_percent: Num = 1,
        take_profit: Num | None = None,
        stop_loss: Num | None = None,
        zero_fee: bool = False,
        skip_validation: bool = False,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Open sized in coin units (fill leverage floats within [min, max] bounds).

        ``leverage`` is the target/reference leverage (contract-required);
        min/max default to the pair envelope when omitted. ``open_price`` is
        the reference price the fill is validated against (± slippage_percent);
        resolved from the live feed when omitted.
        """
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "side": Side(side).value,
            "orderType": (OrderType.MARKET_PNL if zero_fee else OrderType.MARKET).value,
            "collateralUsdc": collateral,
            "coinExposure": coin_exposure,
            "leverage": leverage,
            "minLeverage": min_leverage,
            "maxLeverage": max_leverage,
            "openPrice": open_price,
            "slippagePercent": slippage_percent,
            "takeProfit": take_profit,
            "stopLoss": stop_loss,
            "skipValidation": skip_validation or None,
        }
        if self._engine.is_relayer_mode:
            intent, calldata = await self._intent_and_calldata(
                "/v2/intents/open-coin", "/v2/trade/open-coin", params
            )
            agg = (
                AggregatorOrderType.MARKET_OPEN_PNL_WITH_COIN_EXPOSURE
                if zero_fee
                else AggregatorOrderType.MARKET_OPEN_WITH_COIN_EXPOSURE
            )
            return await self._engine.submit_intent_batch(
                intent, agg, calldata=calldata, wait=wait
            )
        return await self._engine.submit_direct(
            await self._calldata("/v2/trade/open-coin", params), wait=wait
        )

    async def limit_open(
        self,
        pair: PairRef,
        side: Side | str,
        collateral: Num,
        leverage: Num,
        price: Num,
        *,
        stop: bool = False,
        take_profit: Num | None = None,
        stop_loss: Num | None = None,
        slippage_percent: Num = 1,
        skip_validation: bool = False,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Place a limit (or stop-limit) open order.

        Note: limit opens escrow USDC on placement. On the relayer route this
        goes through the TX_RELAY passthrough (matching the Avantis UI).
        """
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "side": Side(side).value,
            "orderType": (OrderType.STOP_LIMIT if stop else OrderType.LIMIT).value,
            "collateralUsdc": collateral,
            "leverage": leverage,
            "openPrice": price,
            "slippagePercent": slippage_percent,
            "takeProfit": take_profit,
            "stopLoss": stop_loss,
            "skipValidation": skip_validation or None,
        }
        calldata = await self._calldata("/v2/trade/open", params)
        if self._engine.is_relayer_mode:
            return await self._engine.submit_passthrough(calldata, wait=wait)
        return await self._engine.submit_direct(calldata, wait=wait)

    # ------------------------------------------------------------------ closes

    async def market_close(
        self,
        pair: PairRef,
        trade_index: int,
        collateral_to_close: Num,
        *,
        expected_price: Num | None = None,
        is_pnl: bool = False,
        open_timestamp: int | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Close a position partially or fully (pass the full collateral for a full close)."""
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "tradeIndex": trade_index,
            "collateralToCloseUsdc": collateral_to_close,
            "expectedPrice": expected_price,
        }
        if self._engine.is_relayer_mode:
            intent, calldata = await self._intent_and_calldata(
                "/v2/intents/close", "/v2/trade/close", params,
                openTimestamp=open_timestamp,
            )
            agg = (
                AggregatorOrderType.MARKET_CLOSE_PNL
                if is_pnl
                else AggregatorOrderType.MARKET_CLOSE
            )
            return await self._engine.submit_intent_batch(
                intent, agg, calldata=calldata, wait=wait
            )
        return await self._engine.submit_direct(
            await self._calldata("/v2/trade/close", params), wait=wait
        )

    async def market_close_coin(
        self,
        pair: PairRef,
        trade_index: int,
        coin_exposure: Num,
        *,
        expected_price: Num | None = None,
        is_pnl: bool = False,
        open_timestamp: int | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "tradeIndex": trade_index,
            "coinExposure": coin_exposure,
            "expectedPrice": expected_price,
        }
        if self._engine.is_relayer_mode:
            intent, calldata = await self._intent_and_calldata(
                "/v2/intents/close-coin", "/v2/trade/close-coin", params,
                openTimestamp=open_timestamp,
            )
            agg = (
                AggregatorOrderType.MARKET_CLOSE_PNL_WITH_COIN_EXPOSURE
                if is_pnl
                else AggregatorOrderType.MARKET_CLOSE_WITH_COIN_EXPOSURE
            )
            return await self._engine.submit_intent_batch(
                intent, agg, calldata=calldata, wait=wait
            )
        return await self._engine.submit_direct(
            await self._calldata("/v2/trade/close-coin", params), wait=wait
        )

    # ------------------------------------------------------------------ limit order mgmt

    async def update_limit_order(
        self,
        pair: PairRef,
        order_index: int,
        *,
        price: Num,
        slippage_percent: Num = 1,
        take_profit: Num | None = None,
        stop_loss: Num | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "orderIndex": order_index,
            "price": price,
            "slippagePercent": slippage_percent,
            "takeProfit": take_profit,
            "stopLoss": stop_loss,
        }
        return await self._passthrough_or_direct("/v2/limit/update", params, wait)

    async def cancel_limit_order(
        self, pair: PairRef, order_index: int, *, wait: bool = True
    ) -> ExecutionReceipt:
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "orderIndex": order_index,
        }
        return await self._passthrough_or_direct("/v2/limit/cancel", params, wait)

    # ------------------------------------------------------------------ position updates

    async def update_margin(
        self,
        pair: PairRef,
        trade_index: int,
        action: MarginAction | str,
        amount: Num,
        *,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Deposit or withdraw collateral on an open position."""
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "tradeIndex": trade_index,
            "action": MarginAction(action).value,
            "collateralUsdc": amount,
        }
        return await self._passthrough_or_direct("/v2/margin/update", params, wait)

    async def increase_position(
        self,
        pair: PairRef,
        trade_index: int,
        collateral: Num,
        leverage: Num,
        *,
        open_price: Num | None = None,
        slippage_percent: Num = 1,
        wait: bool = True,
    ) -> ExecutionReceipt:
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "tradeIndex": trade_index,
            "additionalCollateralUsdc": collateral,
            "leverage": leverage,
            "openPrice": open_price,
            "slippagePercent": slippage_percent,
        }
        if self._engine.is_relayer_mode:
            intent, calldata = await self._intent_and_calldata(
                "/v2/intents/increase", "/v2/position/increase", params
            )
            return await self._engine.submit_intent_batch(
                intent, AggregatorOrderType.INCREASE_SIZE, calldata=calldata, wait=wait
            )
        return await self._engine.submit_direct(
            await self._calldata("/v2/position/increase", params), wait=wait
        )

    async def increase_position_coin(
        self,
        pair: PairRef,
        trade_index: int,
        collateral: Num,
        coin_exposure: Num,
        *,
        leverage: Num,
        min_leverage: Num,
        max_leverage: Num,
        open_price: Num | None = None,
        slippage_percent: Num = 1,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Increase sized in coin units (``leverage`` = reference leverage for
        the added collateral; fill floats within [min, max])."""
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "tradeIndex": trade_index,
            "additionalCollateralUsdc": collateral,
            "coinExposure": coin_exposure,
            "leverage": leverage,
            "minLeverage": min_leverage,
            "maxLeverage": max_leverage,
            "openPrice": open_price,
            "slippagePercent": slippage_percent,
        }
        if self._engine.is_relayer_mode:
            intent, calldata = await self._intent_and_calldata(
                "/v2/intents/increase-coin", "/v2/position/increase-coin", params
            )
            return await self._engine.submit_intent_batch(
                intent,
                AggregatorOrderType.INCREASE_SIZE_WITH_COIN_EXPOSURE,
                calldata=calldata,
                wait=wait,
            )
        return await self._engine.submit_direct(
            await self._calldata("/v2/position/increase-coin", params), wait=wait
        )

    async def update_tp_sl(
        self,
        pair: PairRef,
        trade_index: int,
        *,
        take_profit: Num | None = None,
        stop_loss: Num | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Update TP/SL on an open position. 0 removes the level.

        v2 removed the public updateTpAndSl entry point — this is intent-only
        and therefore always goes through the relayer, even in direct mode.
        """
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "tradeIndex": trade_index,
            "takeProfit": take_profit,
            "stopLoss": stop_loss,
        }
        intent = await self._txb.intent("/v2/intents/tpsl-update", **params)
        return await self._engine.submit_intent_batch(
            intent, AggregatorOrderType.UPDATE_SL, wait=wait
        )

    async def _partial_tp_sl_submission(
        self,
        pair: PairRef,
        trade_index: int,
        *,
        side: Side | str,
        kind: str,
        coin_exposure: Num,
        trigger: TriggerType | str,
        price: Num | None,
        percentage: Num | None,
        open_timestamp: int | None,
    ) -> dict[str, Any]:
        """Build + sign a TpSlReq and shape the core-API submission body."""
        trigger = TriggerType(trigger)
        kind_full = {"tp": "take_profit", "sl": "stop_loss"}.get(kind, kind)
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "tradeIndex": trade_index,
            "side": Side(side).value,
            "kind": kind_full,
            "coinExposure": coin_exposure,
            "triggerType": trigger.value,
            "price": price,
            "percentage": percentage,
            "openTimestamp": open_timestamp,
        }
        intent = await self._txb.intent("/v2/intents/tpsl-partial", **params)
        signer = self._engine.signer
        if signer is None:
            raise ConfigError("partial_tp_sl requires a signing key")
        signed = sign_intent(intent, signer)
        msg = intent.message
        submission = {
            "trader": msg["trader"],
            "pairIndex": int(msg["pairIndex"]),
            "index": int(msg["index"]),
            "triggerType": int(msg["triggerType"]),
            "coinSize": str(msg["coinSize"]),
            "buy": bool(msg["buy"]),
            "price": str(msg["price"]),
            "percentage": str(msg["percentage"]),
            "timestamp": int(msg["timestamp"]),
            "signTimestamp": int(msg["signTimestamp"]),
            "orderType": int(msg["orderType"]),
            "signedMessage": signed.signature,
        }
        if "nonce" in msg:
            submission["nonce"] = str(msg["nonce"])
        return submission

    async def partial_tp_sl(
        self,
        pair: PairRef,
        trade_index: int,
        *,
        side: Side | str,  # side of the POSITION being trimmed
        kind: str,  # "tp"/"take_profit" | "sl"/"stop_loss"
        coin_exposure: Num,
        trigger: TriggerType | str = TriggerType.FIXED,
        price: Num | None = None,
        percentage: Num | None = None,
        open_timestamp: int | None = None,
    ) -> dict[str, Any]:
        """Create a partial TP/SL trigger order.

        Signs a TpSlReq intent (no deadline by design; freshness comes from
        signTimestamp) and stores it with the Avantis operator via
        ``POST {core}/offchain-orders``. The operator executes it on-chain
        when the trigger price hits. Returns the stored order — keep its
        ``documentId`` to update or cancel later.
        """
        submission = await self._partial_tp_sl_submission(
            pair,
            trade_index,
            side=side,
            kind=kind,
            coin_exposure=coin_exposure,
            trigger=trigger,
            price=price,
            percentage=percentage,
            open_timestamp=open_timestamp,
        )
        assert self._t is not None
        stored = await self._t.json(
            "POST", f"{self._cfg.core_api_url}/offchain-orders", json=submission
        )
        # The response is the persisted order (carries documentId); merge it
        # over the submission so callers keep the signed fields too.
        return {**submission, **(stored if isinstance(stored, dict) else {})}

    async def update_partial_tp_sl(
        self,
        document_id: str,
        pair: PairRef,
        trade_index: int,
        *,
        side: Side | str,
        kind: str,
        coin_exposure: Num,
        trigger: TriggerType | str = TriggerType.FIXED,
        price: Num | None = None,
        percentage: Num | None = None,
        open_timestamp: int | None = None,
    ) -> dict[str, Any]:
        """Replace a stored partial TP/SL order in place (atomic edit).

        ``document_id`` comes from the create response / a position's
        ``offchainOrders``. The replacement is a freshly signed TpSlReq —
        pass the FULL new order, not a diff. Ownership is enforced from the
        signature; per-position caps are not re-checked (1:1 replace).
        """
        submission = await self._partial_tp_sl_submission(
            pair,
            trade_index,
            side=side,
            kind=kind,
            coin_exposure=coin_exposure,
            trigger=trigger,
            price=price,
            percentage=percentage,
            open_timestamp=open_timestamp,
        )
        assert self._t is not None
        stored = await self._t.json(
            "PUT",
            f"{self._cfg.core_api_url}/offchain-orders/{document_id}",
            json=submission,
        )
        return {**submission, **(stored if isinstance(stored, dict) else {})}

    async def cancel_partial_tp_sl(self, order: dict[str, Any] | str) -> None:
        """Cancel a stored partial TP/SL trigger order.

        ``order`` is the dict returned by :meth:`partial_tp_sl` / an entry
        from a position's ``offchainOrders`` (must carry ``documentId``), or
        the ``documentId`` string itself. Ownership proof is an EIP-712
        ``CancelOffchainOrder`` signature over the documentId; the trader or
        an active delegate may sign.
        """
        document_id = order if isinstance(order, str) else order.get("documentId")
        if not document_id:
            raise ConfigError(
                "cancel_partial_tp_sl needs the order's documentId (returned by "
                "partial_tp_sl and on /user-data offchainOrders entries)."
            )
        signer = self._engine.signer
        if signer is None:
            raise ConfigError("cancel_partial_tp_sl requires a signing key")
        builder = await self._local_intents()
        intent = builder.cancel_offchain_order(document_id=str(document_id))
        signed = sign_intent(intent, signer)
        assert self._t is not None
        await self._t.json(
            "DELETE",
            f"{self._cfg.core_api_url}/offchain-orders",
            json={"documentId": str(document_id), "signedMessage": signed.signature},
        )

    # ------------------------------------------------------------------ TWAP / RFQ

    async def _submit_twap(self, path: str, intent: IntentPayload) -> ExecutionReceipt:
        """Sign a TWAP intent and submit it to the twap-app API.

        The twap-app verifies the signature, sends executeTwapBatched itself
        (operator wallet) and responds synchronously with
        {twapId, transactionHash, blockNumber} — no relayer involved. Body
        shape follows the twap-app DTOs: pairIndex/index as numbers, other
        numerics as decimal strings, ``__reserved1`` renamed ``reserved1``.
        """
        signer = self._engine.signer
        if signer is None:
            raise ConfigError("TWAP orders require a signing key")
        signed = sign_intent(intent, signer)
        body: dict[str, Any] = {}
        for key, value in intent.message.items():
            if key == "__reserved1":
                body["reserved1"] = str(value)
            elif key in ("pairIndex", "index"):
                body[key] = int(value)
            elif isinstance(value, bool):
                body[key] = value
            else:
                body[key] = str(value)
        body["signature"] = signed.signature
        assert self._t is not None
        data = await self._t.json(
            "POST", f"{self._cfg.twap_api_url}{path}", json=body
        )
        data = data if isinstance(data, dict) else {}
        return ExecutionReceipt(
            route="twap-api",
            tx_hash=data.get("transactionHash"),
            order_id=int(data["twapId"]) if data.get("twapId") is not None else None,
            description=intent.intent,
            raw=data,
        )

    async def twap_open(
        self,
        pair: PairRef,
        side: Side | str,
        collateral: Num,
        run_time_seconds: int,
        *,
        leverage: Num,
        max_leverage: Num,
        coin_exposure: Num | None = None,
    ) -> ExecutionReceipt:
        """Open a TWAP order (collateral spread over run_time_seconds slices).

        ``coin_exposure`` switches to fixed exposure targeting. Leverage
        bounds are required by the contract struct. The receipt's
        ``order_id`` is the on-chain twapId (use it to cancel).
        """
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "side": Side(side).value,
            "collateralUsdc": collateral,
            "coinExposure": coin_exposure,
            "leverage": leverage,
            "maxLeverage": max_leverage,
            "runTimeSeconds": run_time_seconds,
        }
        intent = await self._txb.intent("/v2/intents/twap-open", **params)
        return await self._submit_twap("/twaps/open", intent)

    async def twap_close(
        self,
        pair: PairRef,
        trade_index: int,
        coin_exposure_to_close: Num,
        run_time_seconds: int,
    ) -> ExecutionReceipt:
        """Close exposure via TWAP slices spread over ``run_time_seconds``."""
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "tradeIndex": trade_index,
            "coinExposureToClose": coin_exposure_to_close,
            "runTimeSeconds": run_time_seconds,
        }
        intent = await self._txb.intent("/v2/intents/twap-close", **params)
        return await self._submit_twap("/twaps/close", intent)

    async def twap_cancel(self, twap_id: int) -> ExecutionReceipt:
        """Cancel a TWAP by its on-chain ``twapId`` (receipt.order_id from
        twap_open, or ``account.twaps()``). Signs a TwapCancelReq built
        locally (needs no chain state; digest-equal to the tx-builder's
        /v2/intents/twap-cancel)."""
        builder = await self._local_intents()
        intent = builder.twap_cancel(trader=self.trader, twap_id=twap_id)
        return await self._submit_twap("/twaps/cancel", intent)

    async def rfq_open(
        self,
        pair: PairRef,
        side: Side | str,
        collateral: Num,
        *,
        leverage: Num,
        max_leverage: Num,
        max_slippage_percent: Num,
        expected_price: Num | None = None,
        coin_exposure: Num | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Open an RFQ order (fill at expected_price ± max_slippage_percent).

        NOTE: RFQ is not live on Avantis yet — kept for when it ships.

        ``expected_price`` is resolved from the live feed when omitted. There
        is no trader-side RFQ cancel on-chain (operator-only).
        """
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "side": Side(side).value,
            "collateralUsdc": collateral,
            "coinExposure": coin_exposure,
            "leverage": leverage,
            "maxLeverage": max_leverage,
            "expectedPrice": expected_price,
            "maxSlippagePercent": max_slippage_percent,
        }
        return await self._passthrough_or_direct("/v2/rfq/open", params, wait)

    async def rfq_close(
        self,
        pair: PairRef,
        trade_index: int,
        coin_exposure_to_close: Num,
        *,
        max_slippage_percent: Num,
        expected_price: Num | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """NOTE: RFQ is not live on Avantis yet — kept for when it ships."""
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "tradeIndex": trade_index,
            "coinExposureToClose": coin_exposure_to_close,
            "expectedPrice": expected_price,
            "maxSlippagePercent": max_slippage_percent,
        }
        return await self._passthrough_or_direct("/v2/rfq/close", params, wait)

