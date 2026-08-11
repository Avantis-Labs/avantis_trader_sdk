"""User-facing trading surface.

Every method follows the same recipe:
1. Resolve the pair against the markets catalog (symbol or index; the
   tx-builder always receives the resolved ``pairIndex``).
2. Build the payload via tx-builder (intent for the relayer route, calldata
   for the direct route / passthrough).
3. Route through the ExecutionEngine.

All amounts are human units (100 = 100 USDC, 10 = 10x). ``pair`` accepts
either a symbol ("ETH/USD", "eth-usd", "BTC_UPSIDE") or a pair index.

Upside markets (separate pairs suffixed ``_UPSIDE``, formerly branded ZFP /
zero-fee) route automatically: opens/closes on an upside pair take the PnL
order type — there is no flag to pass. The pair fully determines the type
(the contract reverts ``PnlOrderNotAllowed`` on any mismatch), which also
means upside pairs are market-only: no limit/stop opens and no TWAP.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from ..account.models import Position, UserData
from ..base_api import ExecutingApi
from ..config import AvantisConfig
from ..errors import ConfigError, RelayTimeoutError, ValidationError
from ..execution import ExecutionEngine
from ..execution.batched_market import BatchedMarketEventHook
from ..execution.local_intents import LocalIntentBuilder
from ..markets.models import PairInfo
from ..signing import sign_intent
from ..transport import HttpTransport
from ..txbuilder import TxBuilderClient
from ..types import (
    AggregatorOrderType,
    ExecutionReceipt,
    IntentPayload,
    MarginAction,
    Num,
    OrderType,
    Side,
    TriggerType,
    from_1e10,
)

PairRef = str | int


class TradeApi(ExecutingApi):
    _local: LocalIntentBuilder | None = None  # lazy; for locally-built intents

    def __init__(
        self,
        config: AvantisConfig,
        engine: ExecutionEngine,
        txb: TxBuilderClient,
        transport: HttpTransport,
        get_pair: Callable[[PairRef], Awaitable[PairInfo]],
    ) -> None:
        super().__init__(config, engine, txb, transport)
        self._get_pair = get_pair

    async def _resolve_pair(self, pair: PairRef) -> PairInfo:
        """Pair ref (symbol or index) -> PairInfo from the markets snapshot
        (5s cache). Order-type routing derives from it (``is_upside``)."""
        return await self._get_pair(pair)

    @staticmethod
    def _require_not_upside(info: PairInfo, what: str) -> None:
        if info.is_upside:
            raise ValidationError(
                f"{what} is not available on Upside pairs ({info.symbol} is "
                "market-only: the contract accepts only the PnL market order "
                "type on it). Use market_open/market_close, or trade the "
                f"fixed-fee pair {info.base_symbol!r} instead.",
                code="UPSIDE_MARKET_ONLY",
            )

    async def _local_intents(self) -> LocalIntentBuilder:
        """Local builder for intents that need no chain state
        (CancelOffchainOrder, TwapCancelReq, UpdateTpSlReq): the schema comes
        from ``intents_schema`` (golden-vector proven), so building locally
        skips a tx-builder round-trip."""
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

        The batched-market endpoint takes an EIP-712 intent plus an OPTIONAL
        pre-signed EIP-7702 transaction. The high-level market flows still
        send both so the server can decide which mechanism executes; market
        makers building intents locally can skip the calldata leg entirely
        (see the MM fast path).
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
        skip_validation: bool = False,
        wait: bool = True,
        on_event: BatchedMarketEventHook | None = None,
    ) -> ExecutionReceipt:
        """Open a market position.

        Upside pairs (e.g. ``"BTC_UPSIDE"`` / index 116) route automatically
        as PnL (Upside) orders — no flag needed; fixed-fee pairs always send
        the plain market type. ``open_price`` is the reference price the fill
        is validated against (± slippage_percent); resolved from the live
        feed when omitted.

        ``on_event`` (relayer route only; the direct route has no lifecycle
        stream) observes each batched-market event live — the accepted event,
        retryable ``AttemptFailed`` diagnostics, and the terminal (also when
        it raises) — while the call still settles normally. Sync or async
        callable taking a ``BatchedMarketEvent``.
        """
        info = await self._resolve_pair(pair)
        upside = info.is_upside
        order_type = OrderType.MARKET_PNL if upside else OrderType.MARKET
        params: dict[str, Any] = {
            "pairIndex": info.index,
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
                if upside
                else AggregatorOrderType.MARKET_OPEN
            )
            return await self._engine.submit_intent_batch(
                intent, agg, calldata=calldata, wait=wait, on_event=on_event
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
        skip_validation: bool = False,
        wait: bool = True,
        on_event: BatchedMarketEventHook | None = None,
    ) -> ExecutionReceipt:
        """Open sized in coin units (fill leverage floats within [min, max] bounds).

        Upside pairs route automatically as PnL (Upside) orders, and
        ``on_event`` observes the order lifecycle, like :meth:`market_open`.
        ``leverage`` is the target/reference leverage (contract-required);
        min/max default to the pair envelope when omitted. ``open_price`` is
        the reference price the fill is validated against
        (± slippage_percent); resolved from the live feed when omitted.
        """
        info = await self._resolve_pair(pair)
        upside = info.is_upside
        params: dict[str, Any] = {
            "pairIndex": info.index,
            "trader": self.trader,
            "side": Side(side).value,
            "orderType": (OrderType.MARKET_PNL if upside else OrderType.MARKET).value,
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
                if upside
                else AggregatorOrderType.MARKET_OPEN_WITH_COIN_EXPOSURE
            )
            return await self._engine.submit_intent_batch(
                intent, agg, calldata=calldata, wait=wait, on_event=on_event
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

        Not available on Upside pairs (market-only; there is no PnL limit
        order type on-chain). Note: limit opens escrow USDC on placement. On
        the relayer route this goes through the TX_RELAY passthrough
        (matching the Avantis UI).
        """
        info = await self._resolve_pair(pair)
        self._require_not_upside(info, "limit_open")
        params: dict[str, Any] = {
            "pairIndex": info.index,
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
        open_timestamp: int | None = None,
        wait: bool = True,
        on_event: BatchedMarketEventHook | None = None,
    ) -> ExecutionReceipt:
        """Close a position partially or fully (pass the full collateral for a full close).

        Positions on Upside pairs close with the PnL close type automatically;
        ``on_event`` observes the order lifecycle, like :meth:`market_open`.
        """
        info = await self._resolve_pair(pair)
        params: dict[str, Any] = {
            "pairIndex": info.index,
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
                if info.is_upside
                else AggregatorOrderType.MARKET_CLOSE
            )
            return await self._engine.submit_intent_batch(
                intent, agg, calldata=calldata, wait=wait, on_event=on_event
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
        open_timestamp: int | None = None,
        wait: bool = True,
        on_event: BatchedMarketEventHook | None = None,
    ) -> ExecutionReceipt:
        """Close sized in coin units. Upside pairs route as PnL automatically;
        ``on_event`` observes the order lifecycle, like :meth:`market_open`."""
        info = await self._resolve_pair(pair)
        params: dict[str, Any] = {
            "pairIndex": info.index,
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
                if info.is_upside
                else AggregatorOrderType.MARKET_CLOSE_WITH_COIN_EXPOSURE
            )
            return await self._engine.submit_intent_batch(
                intent, agg, calldata=calldata, wait=wait, on_event=on_event
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
            "pairIndex": (await self._resolve_pair(pair)).index,
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
            "pairIndex": (await self._resolve_pair(pair)).index,
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
            "pairIndex": (await self._resolve_pair(pair)).index,
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
        on_event: BatchedMarketEventHook | None = None,
    ) -> ExecutionReceipt:
        params: dict[str, Any] = {
            "pairIndex": (await self._resolve_pair(pair)).index,
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
                intent,
                AggregatorOrderType.INCREASE_SIZE,
                calldata=calldata,
                wait=wait,
                on_event=on_event,
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
        on_event: BatchedMarketEventHook | None = None,
    ) -> ExecutionReceipt:
        """Increase sized in coin units (``leverage`` = reference leverage for
        the added collateral; fill floats within [min, max])."""
        params: dict[str, Any] = {
            "pairIndex": (await self._resolve_pair(pair)).index,
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
                on_event=on_event,
            )
        return await self._engine.submit_direct(
            await self._calldata("/v2/position/increase-coin", params), wait=wait
        )

    async def _fetch_position(self, pair_index: int, trade_index: int) -> Position:
        """The open position at (trader, pairIndex, index) from the core API,
        or a 404-flavored ValidationError (mirrors the backend's global
        price-trigger path, which rejects mutations on unknown positions)."""
        assert self._t is not None
        data = await self._t.json(
            "GET",
            f"{self._cfg.core_api_url}/user-data",
            params={"trader": self.trader},
        )
        position = UserData.model_validate(data).position(pair_index, trade_index)
        if position is None:
            raise ValidationError(
                f"no open position for {self.trader} at pairIndex={pair_index} "
                f"index={trade_index}",
                code="NO_POSITION",
                status=404,
            )
        return position

    async def update_tp_sl(
        self,
        pair: PairRef,
        trade_index: int,
        *,
        take_profit: Num | None = None,
        stop_loss: Num | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Update the GLOBAL (on-chain) TP/SL on an open position.

        ``None`` keeps a leg unchanged (its current value is copied from the
        position — the signed intent always carries both legs); ``0`` clears
        a leg. ``stop_loss=0`` truly removes the SL. A position always has a
        TP on-chain, so ``take_profit=0`` RESETS it to the pair's max-gain
        cap (``maxGainP``, typically +2500%) rather than removing it.

        v2 has no public updateTpAndSl entry point — this signs an EIP-712
        ``UpdateTpSlReq`` and submits it to the core API price-triggers
        endpoint (``PUT /price-triggers/global-...``), which verifies it and
        executes ``executePositionUpdateBatched(UPDATE_SL, ...)`` through the
        Avantis operator. Same path in relayer and direct mode. A 2xx means
        ACCEPTED for execution, not mined: with ``wait=True`` the SDK polls
        the position until the new levels are visible on ``/user-data``.

        These levels surface on positions as the ``priceTriggers`` entries
        flagged ``isGlobal`` (deterministic ``global-tp-*`` / ``global-sl-*``
        entity ids). For partial/off-chain triggers use
        :meth:`partial_tp_sl`.
        """
        if take_profit is None and stop_loss is None:
            raise ValidationError(
                "update_tp_sl needs take_profit and/or stop_loss",
                code="NOTHING_TO_UPDATE",
            )
        signer = self._engine.signer
        if signer is None:
            raise ConfigError("update_tp_sl requires a signing key")
        info = await self._resolve_pair(pair)
        position = await self._fetch_position(info.index, trade_index)

        builder = await self._local_intents()
        intent = builder.update_tp_sl(
            trader=self.trader,
            pair_index=info.index,
            index=trade_index,
            tp=take_profit if take_profit is not None else from_1e10(position.tp_raw),
            sl=stop_loss if stop_loss is not None else from_1e10(position.sl_raw),
        )
        signed = sign_intent(intent, signer)

        # Either leg's synthetic id addresses the same position; the backend
        # routes on the id shape and validates trader/pair/index against the
        # signed intent. Use the leg being changed for readability.
        kind = "tp" if take_profit is not None else "sl"
        entity_id = f"global-{kind}-{position.trader}-{info.index}-{trade_index}"
        assert self._t is not None
        response = await self._t.json(
            "PUT",
            f"{self._cfg.core_api_url}/price-triggers/{entity_id}",
            json={
                "userIntent": intent.encoded_intent,
                "signedMessage": signed.signature,
            },
        )
        receipt = ExecutionReceipt(
            route="price-triggers",
            description=intent.intent,
            raw=response if isinstance(response, dict) else None,
        )
        if wait:
            await self._wait_for_tp_sl_change(
                info.index,
                trade_index,
                before=(position.tp_raw, position.sl_raw),
                expected=(str(intent.message["_newTp"]), str(intent.message["_newSl"])),
            )
        return receipt

    async def _wait_for_tp_sl_change(
        self,
        pair_index: int,
        trade_index: int,
        *,
        before: tuple[str, str],
        expected: tuple[str, str],
    ) -> None:
        """Poll /user-data until the position's (tp, sl) match the accepted
        update. ``take_profit=0`` is contract-corrected to the max-gain price
        (PairStorage.correctTp), so an exact match cannot be required for a
        zero TP leg — any change from the pre-update snapshot settles it too.

        One reset case is unobservable: signing ``_newTp = 0`` when the TP
        already sits at the corrected default re-stores the same value, so
        nothing on /user-data changes. If the timeout expires with every
        OTHER leg confirmed and only a zero-TP leg pending, the update is
        treated as settled instead of raising."""
        sl_ok = False
        deadline = asyncio.get_event_loop().time() + self._cfg.relay_poll_timeout_s
        while asyncio.get_event_loop().time() < deadline:
            position = await self._fetch_position(pair_index, trade_index)
            now = (position.tp_raw, position.sl_raw)
            tp_ok = now[0] == expected[0] or (expected[0] == "0" and now[0] != before[0])
            sl_ok = now[1] == expected[1]
            if tp_ok and sl_ok:
                return
            await asyncio.sleep(self._cfg.relay_poll_interval_s)
        if sl_ok and expected[0] == "0":
            return  # zero-TP reset with no observable change (see docstring)
        raise RelayTimeoutError(
            f"TP/SL update accepted but not visible on the position after "
            f"{self._cfg.relay_poll_timeout_s:.0f}s (pairIndex={pair_index} "
            f"index={trade_index}). It may still execute — re-check "
            "account.positions()."
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
            "pairIndex": (await self._resolve_pair(pair)).index,
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
        ``POST {core}/price-triggers``. The operator executes it on-chain
        when the trigger price hits. Returns the stored order — keep its
        ``entityId`` to update or cancel later.
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
            "POST", f"{self._cfg.core_api_url}/price-triggers", json=submission
        )
        # The response is the persisted order (carries entityId); merge it
        # over the submission so callers keep the signed fields too.
        return {**submission, **(stored if isinstance(stored, dict) else {})}

    @staticmethod
    def _require_partial_entity_id(entity_id: str, what: str) -> None:
        """Positions' ``priceTriggers`` mix off-chain orders with synthetic
        global entries (``global-tp-*`` / ``global-sl-*``, ``isGlobal`` true).
        The global ones live on-chain — manage them with
        :meth:`update_tp_sl` (``take_profit=0`` resets the TP,
        ``stop_loss=0`` removes the SL), not the partial-order CRUD."""
        if str(entity_id).startswith("global-"):
            raise ValidationError(
                f"{what}: {entity_id!r} is the synthetic id of the position's "
                "global on-chain TP/SL (priceTriggers entry with isGlobal). "
                "Change or remove it with update_tp_sl() — e.g. stop_loss=0 "
                "removes the SL; the partial-order CRUD only accepts stored "
                "order entityIds.",
                code="GLOBAL_TRIGGER_ID",
            )

    async def update_partial_tp_sl(
        self,
        entity_id: str,
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

        ``entity_id`` comes from the create response / a position's
        ``price_triggers`` (entries with ``is_global`` False). The
        replacement is a freshly signed TpSlReq — pass the FULL new order,
        not a diff. Ownership is enforced from the signature; per-position
        caps are not re-checked (1:1 replace).

        The backend deletes the old order and stores the replacement
        atomically, minting a NEW id: the returned dict's ``entityId`` is the
        replacement's id — adopt it, the old one is gone.
        """
        self._require_partial_entity_id(entity_id, "update_partial_tp_sl")
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
        response = await self._t.json(
            "PUT",
            f"{self._cfg.core_api_url}/price-triggers/{entity_id}",
            json=submission,
        )
        # Mutation response: {success, result: {oldEntityId, newEntityId}}.
        result = response.get("result") if isinstance(response, dict) else None
        new_id = (result or {}).get("newEntityId") or entity_id
        return {**submission, "entityId": new_id, "oldEntityId": entity_id}

    async def cancel_partial_tp_sl(self, order: dict[str, Any] | str) -> None:
        """Cancel a stored partial TP/SL trigger order.

        ``order`` is the dict returned by :meth:`partial_tp_sl` / an entry
        from a position's ``price_triggers`` with ``is_global`` False (must
        carry ``entityId``), or the ``entityId`` string itself. Global
        (on-chain) triggers cannot be cancelled here — use
        :meth:`update_tp_sl` with 0. Ownership proof is an EIP-712
        ``CancelOffchainOrder`` signature over the entityId; the trader or
        an active delegate may sign.
        """
        if isinstance(order, str):
            entity_id: Any = order
        else:
            entity_id = order.get("entityId") or order.get("documentId")
        if not entity_id:
            raise ConfigError(
                "cancel_partial_tp_sl needs the order's entityId (returned by "
                "partial_tp_sl and on positions' priceTriggers entries)."
            )
        self._require_partial_entity_id(str(entity_id), "cancel_partial_tp_sl")
        signer = self._engine.signer
        if signer is None:
            raise ConfigError("cancel_partial_tp_sl requires a signing key")
        builder = await self._local_intents()
        intent = builder.cancel_offchain_order(entity_id=str(entity_id))
        signed = sign_intent(intent, signer)
        assert self._t is not None
        await self._t.json(
            "DELETE",
            f"{self._cfg.core_api_url}/price-triggers",
            json={"entityId": str(entity_id), "signedMessage": signed.signature},
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

        Not available on Upside pairs (their TWAP params are zeroed
        on-chain). ``coin_exposure`` switches to fixed exposure targeting.
        Leverage bounds are required by the contract struct. The receipt's
        ``order_id`` is the on-chain twapId (use it to cancel).
        """
        info = await self._resolve_pair(pair)
        self._require_not_upside(info, "twap_open")
        params: dict[str, Any] = {
            "pairIndex": info.index,
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
        """Close exposure via TWAP slices spread over ``run_time_seconds``.

        Not available on Upside pairs (market-only).
        """
        info = await self._resolve_pair(pair)
        self._require_not_upside(info, "twap_close")
        params: dict[str, Any] = {
            "pairIndex": info.index,
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
            "pairIndex": (await self._resolve_pair(pair)).index,
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
            "pairIndex": (await self._resolve_pair(pair)).index,
            "trader": self.trader,
            "tradeIndex": trade_index,
            "coinExposureToClose": coin_exposure_to_close,
            "expectedPrice": expected_price,
            "maxSlippagePercent": max_slippage_percent,
        }
        return await self._passthrough_or_direct("/v2/rfq/close", params, wait)

