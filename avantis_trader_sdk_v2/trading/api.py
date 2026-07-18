"""User-facing trading surface.

Every method follows the same recipe:
1. Build the payload via tx-builder (intent for the relayer route, calldata
   for the direct route / passthrough).
2. Route through the ExecutionEngine.

All amounts are human units (100 = 100 USDC, 10 = 10x). ``pair`` accepts
either a symbol ("ETH/USD", "eth-usd") or a pair index.
"""

from __future__ import annotations

from typing import Any

from ..base_api import ExecutingApi
from ..errors import ConfigError
from ..signing import sign_intent, to_int_message
from ..types import (
    AggregatorOrderType,
    ExecutionReceipt,
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

    # ------------------------------------------------------------------ opens

    async def market_open(
        self,
        pair: PairRef,
        side: Side | str,
        collateral: Num,
        leverage: Num,
        *,
        take_profit: Num | None = None,
        stop_loss: Num | None = None,
        slippage_percent: Num = 1,
        zero_fee: bool = False,
        skip_validation: bool = False,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Open a market position (or a zero-fee/PnL position with zero_fee=True)."""
        order_type = OrderType.MARKET_PNL if zero_fee else OrderType.MARKET
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "side": Side(side).value,
            "orderType": order_type.value,
            "collateralUsdc": collateral,
            "leverage": leverage,
            "slippagePercent": slippage_percent,
            "takeProfit": take_profit,
            "stopLoss": stop_loss,
            "skipValidation": skip_validation or None,
        }
        if self._engine.is_relayer_mode:
            intent = await self._txb.intent("/v2/intents/open", **params)
            agg = (
                AggregatorOrderType.MARKET_OPEN_PNL
                if zero_fee
                else AggregatorOrderType.MARKET_OPEN
            )
            return await self._engine.submit_intent_batch(intent, agg, wait=wait)
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
        slippage_percent: Num = 1,
        take_profit: Num | None = None,
        stop_loss: Num | None = None,
        zero_fee: bool = False,
        skip_validation: bool = False,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Open sized in coin units (fill leverage floats within [min, max] bounds).

        ``leverage`` is the target/reference leverage (contract-required);
        min/max default to the pair envelope when omitted.
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
            "slippagePercent": slippage_percent,
            "takeProfit": take_profit,
            "stopLoss": stop_loss,
            "skipValidation": skip_validation or None,
        }
        if self._engine.is_relayer_mode:
            intent = await self._txb.intent("/v2/intents/open-coin", **params)
            agg = (
                AggregatorOrderType.MARKET_OPEN_PNL_WITH_COIN_EXPOSURE
                if zero_fee
                else AggregatorOrderType.MARKET_OPEN_WITH_COIN_EXPOSURE
            )
            return await self._engine.submit_intent_batch(intent, agg, wait=wait)
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
            intent = await self._txb.intent(
                "/v2/intents/close", **params, openTimestamp=open_timestamp
            )
            agg = (
                AggregatorOrderType.MARKET_CLOSE_PNL
                if is_pnl
                else AggregatorOrderType.MARKET_CLOSE
            )
            return await self._engine.submit_intent_batch(intent, agg, wait=wait)
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
            intent = await self._txb.intent(
                "/v2/intents/close-coin", **params, openTimestamp=open_timestamp
            )
            agg = (
                AggregatorOrderType.MARKET_CLOSE_PNL_WITH_COIN_EXPOSURE
                if is_pnl
                else AggregatorOrderType.MARKET_CLOSE_WITH_COIN_EXPOSURE
            )
            return await self._engine.submit_intent_batch(intent, agg, wait=wait)
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
            intent = await self._txb.intent("/v2/intents/increase", **params)
            return await self._engine.submit_intent_batch(
                intent, AggregatorOrderType.INCREASE_SIZE, wait=wait
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
            intent = await self._txb.intent("/v2/intents/increase-coin", **params)
            return await self._engine.submit_intent_batch(
                intent,
                AggregatorOrderType.INCREASE_SIZE_WITH_COIN_EXPOSURE,
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
        signTimestamp) and stores it with the Avantis operator via the core
        API. The operator executes it on-chain when the trigger price hits.
        Returns the stored order fields (keep them to cancel later).
        """
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
        assert self._t is not None
        await self._t.json(
            "PUT", f"{self._cfg.core_api_url}/offchain-orders", json=submission
        )
        return submission

    async def cancel_partial_tp_sl(self, order: dict[str, Any]) -> None:
        """Cancel a stored partial TP/SL trigger order.

        ``order`` is the dict returned by partial_tp_sl() or an entry from a
        position's ``offchain_orders``. The cancel re-signs the exact order
        fields as proof of ownership.
        """
        from ..intents_schema import INTENT_TYPES, trading_domain

        signer = self._engine.signer
        if signer is None:
            raise ConfigError("cancel_partial_tp_sl requires a signing key")

        meta = await self._txb.meta()
        types = INTENT_TYPES["TpSlReq"]
        message = {
            "trader": order["trader"],
            "pairIndex": str(order["pairIndex"]),
            "index": str(order["index"]),
            "triggerType": str(order["triggerType"]),
            "coinSize": str(order["coinSize"]),
            "buy": order["buy"],
            "price": str(order["price"]),
            "percentage": str(order["percentage"]),
            "timestamp": str(order["timestamp"]),
            "signTimestamp": str(order["signTimestamp"]),
            "orderType": str(order["orderType"]),
            "nonce": str(order.get("nonce", 0)),
        }
        full_message = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                **types,
            },
            "primaryType": "TpSlReq",
            "domain": trading_domain(
                int(meta["chainId"]), meta["addresses"]["tradingRouter"]
            ),
            "message": to_int_message(types, "TpSlReq", message),
        }
        signature, _ = signer.sign_typed_data(full_message)
        assert self._t is not None
        await self._t.json(
            "DELETE",
            f"{self._cfg.core_api_url}/offchain-orders",
            params={
                "trader": order["trader"],
                "pairIndex": order["pairIndex"],
                "index": order["index"],
                "signedMessage": "0x" + signature.hex(),
            },
        )

    # ------------------------------------------------------------------ TWAP / RFQ

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
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Open a TWAP order (collateral spread over run_time_seconds slices).

        ``coin_exposure`` switches to fixed exposure targeting. Leverage
        bounds are required by the contract struct.
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
        return await self._passthrough_or_direct("/v2/twap/open", params, wait)

    async def twap_close(
        self,
        pair: PairRef,
        trade_index: int,
        coin_exposure_to_close: Num,
        run_time_seconds: int,
        *,
        wait: bool = True,
    ) -> ExecutionReceipt:
        params: dict[str, Any] = {
            **_pair_params(pair),
            "trader": self.trader,
            "tradeIndex": trade_index,
            "coinExposureToClose": coin_exposure_to_close,
            "runTimeSeconds": run_time_seconds,
        }
        return await self._passthrough_or_direct("/v2/twap/close", params, wait)

    async def twap_cancel(self, twap_id: int, *, wait: bool = True) -> ExecutionReceipt:
        params: dict[str, Any] = {"trader": self.trader, "twapId": twap_id}
        return await self._passthrough_or_direct("/v2/twap/cancel", params, wait)

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

