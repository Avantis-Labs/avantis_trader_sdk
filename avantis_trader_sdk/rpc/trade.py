from ..feed.feed_client import FeedClient
from ..config import AVANTIS_CORE_API_BASE_URL
from ..types import (
    TradeInput,
    TradeInputOrderType,
    TradeExtendedResponse,
    TradeResponse,
    TradeInfo,
    PendingLimitOrderExtendedResponse,
    MarginUpdateType,
)
from typing import Optional, List, Tuple
import math
import asyncio
import requests


class TradeRPC:
    """
    The TradeRPC class contains methods for retrieving trading parameters from the Avantis Protocol.
    """

    def __init__(
        self,
        client,
        feed_client: FeedClient,
        core_api_base_url: Optional[str] = None,
    ):
        """
        Constructor for the TradeRPC class.

        Args:
            client: The TraderClient object.
            feed_client: The FeedClient object.
            core_api_base_url: Optional override for the API base URL.
        """
        self.client = client
        self.feed_client = feed_client
        self.core_api_base_url = core_api_base_url or AVANTIS_CORE_API_BASE_URL

    async def build_trade_open_tx(
        self,
        trade_input: TradeInput,
        trade_input_order_type: TradeInputOrderType,
        slippage_percentage: int,
        execution_fee: Optional[float] = None,
    ):
        """
        Builds a transaction to open a trade.

        Args:
            trade: The trade input object.
            trade_input_order_type: The trade input order type.
            slippage_percentage: The slippage percentage.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if (
            trade_input.trader == "0x1234567890123456789012345678901234567890"
            and self.client.get_signer() is not None
        ):
            trade_input.trader = await self.client.get_signer().get_ethereum_address()

        if execution_fee is not None:
            execution_fee_wei = int(execution_fee * 10**18)
        else:
            execution_fee_wei = await self.get_trade_execution_fee()

        if (
            trade_input_order_type == TradeInputOrderType.MARKET
            or trade_input_order_type == TradeInputOrderType.MARKET_ZERO_FEE
        ) and not trade_input.openPrice:
            pair_name = await self.client.pairs_cache.get_pair_name_from_index(
                trade_input.pairIndex
            )
            price_data = await self.feed_client.get_latest_price_updates([pair_name])
            price = int(price_data.parsed[0].converted_price * 10**10)
            trade_input.openPrice = price

        if (
            trade_input_order_type == TradeInputOrderType.LIMIT
            or trade_input_order_type == TradeInputOrderType.STOP_LIMIT
        ) and not trade_input.openPrice:
            raise Exception("Open price is required for LIMIT/STOP LIMIT order type")

        transaction = await Trading.functions.openTrade(
            trade_input.model_dump(),
            trade_input_order_type.value,
            slippage_percentage * 10**10,
        ).build_transaction(
            {
                "from": trade_input.trader,
                "value": execution_fee_wei,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(trade_input.trader),
            }
        )

        return transaction

    async def build_trade_open_tx_delegate(
        self,
        trade_input: TradeInput,
        trade_input_order_type: TradeInputOrderType,
        slippage_percentage: int,
        execution_fee: Optional[float] = None,
    ):
        """
        Builds a transaction to open a trade.

        Args:
            trade: The trade input object.
            trade_input_order_type: The trade input order type.
            slippage_percentage: The slippage percentage.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if (
            trade_input.trader == "0x1234567890123456789012345678901234567890"
            and self.client.get_signer() is not None
        ):
            trade_input.trader = await self.client.get_signer().get_ethereum_address()

        if execution_fee is not None:
            execution_fee_wei = int(execution_fee * 10**18)
        else:
            execution_fee_wei = await self.get_trade_execution_fee()

        if (
            trade_input_order_type == TradeInputOrderType.MARKET
            or trade_input_order_type == TradeInputOrderType.MARKET_ZERO_FEE
        ) and not trade_input.openPrice:
            pair_name = await self.client.pairs_cache.get_pair_name_from_index(
                trade_input.pairIndex
            )
            price_data = await self.feed_client.get_latest_price_updates([pair_name])
            price = int(price_data.parsed[0].converted_price * 10**10)
            trade_input.openPrice = price

        if (
            trade_input_order_type == TradeInputOrderType.LIMIT
            or trade_input_order_type == TradeInputOrderType.STOP_LIMIT
        ) and not trade_input.openPrice:
            raise Exception("Open price is required for LIMIT/STOP LIMIT order type")

        transaction = await Trading.functions.openTrade(
            trade_input.model_dump(),
            trade_input_order_type.value,
            slippage_percentage * 10**10,
        ).build_transaction(
            {
                "from": trade_input.trader,
                "value": 0,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(trade_input.trader),
            }
        )

        print("transaction: ", trade_input.trader)

        delegate_transaction = await Trading.functions.delegatedAction(
            trade_input.trader, transaction["data"]
        ).build_transaction(
            {
                "from": self.client.get_signer().get_ethereum_address(),
                "value": execution_fee_wei,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(
                    self.client.get_signer().get_ethereum_address()
                ),
            }
        )

        return delegate_transaction

    async def get_trade_execution_fee(self):
        """
        Gets the correct trade execution fee.

        Returns:
            The trade execution fee
        """
        execution_fee = round(0.00035, 18)  # default value
        execution_fee_wei = int(execution_fee * 10**18)

        try:
            estimatedL2Gas = math.floor(850000 * 1.1)

            l2GasPrice = await self.client.async_web3.eth.gas_price
            estimatedL2GasEth = l2GasPrice * estimatedL2Gas
            estimatedL1GasEth = 5000000000

            feeEstimate = estimatedL1GasEth + estimatedL2GasEth
            feeEstimate = round(feeEstimate, 18)
            return feeEstimate
        except Exception as e:
            print("Error getting correct trade execution fee. Using fallback: ", e)
            return execution_fee_wei

    async def get_trades(
        self,
        trader: Optional[str] = None,
        use_api: bool = True,
    ) -> Tuple[List[TradeExtendedResponse], List[PendingLimitOrderExtendedResponse]]:
        """
        Gets the trades and pending limit orders for a trader.

        Attempts to fetch from API first for better performance. Falls back to
        paginated smart contract calls if API is unavailable or disabled.

        Args:
            trader: The trader's wallet address.
            use_api: Whether to attempt API fetch first. Defaults to True.

        Returns:
            A tuple of (trades, pending_limit_orders).
        """
        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        if use_api:
            api_enabled = await self._check_api_enabled(trader)
            if api_enabled:
                try:
                    return await self._fetch_trades_from_api(trader)
                except Exception:
                    pass

        return await self._fetch_trades_from_contracts(trader)

    async def _check_api_enabled(self, trader: str) -> bool:
        """Checks if the API is enabled for the given trader."""
        try:
            response = requests.get(
                f"{self.core_api_base_url}/user-data/config",
                params={"wallet": trader},
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("globallyEnabled", False) or data.get(
                "enabledForWallet", False
            )
        except Exception:
            return False

    async def _fetch_trades_from_api(
        self, trader: str
    ) -> Tuple[List[TradeExtendedResponse], List[PendingLimitOrderExtendedResponse]]:
        """Fetches trades from the API."""
        response = requests.get(
            f"{self.core_api_base_url}/user-data",
            params={"trader": trader},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        trades = []
        for position in data.get("positions", []):
            loss_protection_tier = int(position.get("lossProtection", 0))
            pair_index = int(position.get("pairIndex", 0))
            loss_protection_pct = await self.client.trading_parameters.get_loss_protection_percentage_by_tier(
                loss_protection_tier, pair_index
            )
            position["lossProtectionPercentage"] = loss_protection_pct
            trades.append(TradeExtendedResponse(**position))

        limit_orders = [
            PendingLimitOrderExtendedResponse(**order)
            for order in data.get("limitOrders", [])
        ]

        return trades, limit_orders

    async def _fetch_trades_from_contracts(
        self,
        trader: str,
        max_pairs_per_call: int = 12,
    ) -> Tuple[List[TradeExtendedResponse], List[PendingLimitOrderExtendedResponse]]:
        """Fetches trades from smart contracts with paginated calls."""
        socket_info = await self.client.pairs_cache.get_info_from_socket()
        max_trades_per_pair = socket_info.get("maxTradesPerPair", 40)

        pairs_count = await self.client.pairs_cache.get_pairs_count()
        pair_ranges = self._build_pair_ranges(pairs_count, max_pairs_per_call)

        tasks = [
            self._fetch_positions_for_range(trader, start, end, max_trades_per_pair)
            for start, end in pair_ranges
        ]
        results = await asyncio.gather(*tasks)

        raw_trades = []
        raw_orders = []
        for trades_batch, orders_batch in results:
            raw_trades.extend(trades_batch)
            raw_orders.extend(orders_batch)

        trades = await self._parse_raw_trades(raw_trades)
        limit_orders = self._parse_raw_limit_orders(raw_orders)

        return trades, limit_orders

    def _build_pair_ranges(
        self, pairs_count: int, max_pairs_per_call: int
    ) -> List[Tuple[int, int]]:
        """Builds pair index ranges for paginated fetching."""
        ranges = []
        for i in range(0, pairs_count, max_pairs_per_call):
            start = i
            end = min(i + max_pairs_per_call, pairs_count)
            ranges.append((start, end))
        return ranges

    async def _fetch_positions_for_range(
        self,
        trader: str,
        start_pair: int,
        end_pair: int,
        max_trades_per_pair: int,
    ) -> Tuple[list, list]:
        """Fetches positions for a range of pair indexes."""
        result = (
            await self.client.contracts.get("Multicall")
            .functions.getPositionsForPairIndexes(
                trader, start_pair, end_pair, max_trades_per_pair
            )
            .call()
        )
        return result[0], result[1]

    async def _parse_raw_trades(self, raw_trades: list) -> List[TradeExtendedResponse]:
        """Parses raw contract trade data into TradeExtendedResponse objects."""
        trades = []
        for aggregated_trade in raw_trades:
            (trade, trade_info, margin_fee, liquidation_price, is_zfp) = (
                aggregated_trade
            )

            if trade[7] <= 0:
                continue

            loss_protection = await self.client.trading_parameters.get_loss_protection_percentage_by_tier(
                trade_info[4], trade[1]
            )

            trades.append(
                TradeExtendedResponse(
                    trade=TradeResponse(
                        trader=trade[0],
                        pairIndex=trade[1],
                        index=trade[2],
                        initialPosToken=trade[3],
                        positionSizeUSDC=trade[3],
                        openPrice=trade[5],
                        buy=trade[6],
                        leverage=trade[7],
                        tp=trade[8],
                        sl=trade[9],
                        timestamp=trade[10],
                    ),
                    additional_info=TradeInfo(
                        lossProtectionPercentage=loss_protection,
                    ),
                    margin_fee=margin_fee,
                    liquidation_price=liquidation_price,
                    is_zfp=is_zfp,
                )
            )
        return trades

    def _parse_raw_limit_orders(
        self, raw_orders: list
    ) -> List[PendingLimitOrderExtendedResponse]:
        """Parses raw contract order data into PendingLimitOrderExtendedResponse objects."""
        orders = []
        for aggregated_order in raw_orders:
            (order, liquidation_price) = aggregated_order

            if order[5] <= 0:
                continue

            orders.append(
                PendingLimitOrderExtendedResponse(
                    trader=order[0],
                    pairIndex=order[1],
                    index=order[2],
                    positionSize=order[3],
                    buy=order[4],
                    leverage=order[5],
                    tp=order[6],
                    sl=order[7],
                    price=order[8],
                    slippageP=order[9],
                    block=order[10],
                    executionFee=order[11],
                    liquidation_price=liquidation_price,
                )
            )
        return orders

    async def build_trade_close_tx(
        self,
        pair_index: int,
        trade_index: int,
        collateral_to_close: float,
        trader: Optional[str] = None,
        execution_fee: Optional[float] = None,
    ):
        """
        Builds a transaction to close a trade.

        Args:
            pair_index: The pair index.
            trade_index: The trade index.
            collateral_to_close: The collateral to close.
            trader (optional): The trader's wallet address.
            execution_fee (optional): The execution fee.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        collateral_to_close = int(collateral_to_close * 10**6)

        if execution_fee is not None:
            execution_fee_wei = int(execution_fee * 10**18)
        else:
            execution_fee_wei = await self.get_trade_execution_fee()

        transaction = await Trading.functions.closeTradeMarket(
            pair_index,
            trade_index,
            collateral_to_close,
        ).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(trader),
                "value": execution_fee_wei,
            }
        )

        return transaction

    async def build_trade_close_tx_delegate(
        self,
        pair_index: int,
        trade_index: int,
        collateral_to_close: float,
        trader: Optional[str] = None,
        execution_fee: Optional[float] = None,
    ):
        """
        Builds a transaction to close a trade.

        Args:
            pair_index: The pair index.
            trade_index: The trade index.
            collateral_to_close: The collateral to close.
            trader (optional): The trader's wallet address.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        collateral_to_close = int(collateral_to_close * 10**6)

        if execution_fee is not None:
            execution_fee_wei = int(execution_fee * 10**18)
        else:
            execution_fee_wei = await self.get_trade_execution_fee()

        transaction = await Trading.functions.closeTradeMarket(
            pair_index,
            trade_index,
            collateral_to_close,
        ).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(trader),
                "value": 0,
            }
        )

        delegate_transaction = await Trading.functions.delegatedAction(
            trader, transaction["data"]
        ).build_transaction(
            {
                "from": self.client.get_signer().get_ethereum_address(),
                "value": execution_fee_wei,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(
                    self.client.get_signer().get_ethereum_address()
                ),
            }
        )

        return delegate_transaction

    async def build_order_cancel_tx(
        self, pair_index: int, trade_index: int, trader: Optional[str] = None
    ):
        """
        Builds a transaction to cancel an order.

        Args:
            pair_index: The pair index.
            trade_index: The trade/order index.
            trader (optional): The trader's wallet address.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        transaction = await Trading.functions.cancelOpenLimitOrder(
            pair_index, trade_index
        ).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(trader),
            }
        )

        return transaction

    async def build_order_cancel_tx_delegate(
        self, pair_index: int, trade_index: int, trader: Optional[str] = None
    ):
        """
        Builds a transaction to cancel an order.

        Args:
            pair_index: The pair index.
            trade_index: The trade/order index.
            trader (optional): The trader's wallet address.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        transaction = await Trading.functions.cancelOpenLimitOrder(
            pair_index, trade_index
        ).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(trader),
            }
        )

        delegate_transaction = await Trading.functions.delegatedAction(
            trader, transaction["data"]
        ).build_transaction(
            {
                "from": self.client.get_signer().get_ethereum_address(),
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(
                    self.client.get_signer().get_ethereum_address()
                ),
            }
        )

        return delegate_transaction

    async def build_trade_margin_update_tx(
        self,
        pair_index: int,
        trade_index: int,
        margin_update_type: MarginUpdateType,
        collateral_change: float,
        trader: Optional[str] = None,
    ):
        """
        Builds a transaction to update the margin of a trade.

        Args:
            pair_index: The pair index.
            trade_index: The trade index.
            margin_update_type: The margin update type.
            collateral_change: The collateral change.
            trader (optional): The trader's wallet address.
        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        collateral_change = int(collateral_change * 10**6)

        pair_name = await self.client.pairs_cache.get_pair_name_from_index(pair_index)

        price_data = await self.feed_client.get_latest_price_updates([pair_name])

        price_update_data = "0x" + price_data.binary.data[0]

        transaction = await Trading.functions.updateMargin(
            pair_index,
            trade_index,
            margin_update_type.value,
            collateral_change,
            [price_update_data],
        ).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "value": 1,
                "nonce": await self.client.get_transaction_count(trader),
            }
        )

        return transaction

    async def build_trade_margin_update_tx_delegate(
        self,
        pair_index: int,
        trade_index: int,
        margin_update_type: MarginUpdateType,
        collateral_change: float,
        trader: Optional[str] = None,
    ):
        """
        Builds a transaction to update the margin of a trade.

        Args:
            pair_index: The pair index.
            trade_index: The trade index.
            margin_update_type: The margin update type.
            collateral_change: The collateral change.
            trader (optional): The trader's wallet address.
        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        collateral_change = int(collateral_change * 10**6)

        pair_name = await self.client.pairs_cache.get_pair_name_from_index(pair_index)

        price_data = await self.feed_client.get_latest_price_updates([pair_name])

        price_update_data = "0x" + price_data.binary.data[0]

        transaction = await Trading.functions.updateMargin(
            pair_index,
            trade_index,
            margin_update_type.value,
            collateral_change,
            [price_update_data],
        ).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "value": 0,
                "nonce": await self.client.get_transaction_count(trader),
            }
        )

        delegate_transaction = await Trading.functions.delegatedAction(
            trader, transaction["data"]
        ).build_transaction(
            {
                "from": self.client.get_signer().get_ethereum_address(),
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(
                    self.client.get_signer().get_ethereum_address()
                ),
                "value": 1,
            }
        )

        return delegate_transaction

    async def build_trade_tp_sl_update_tx(
        self,
        pair_index: int,
        trade_index: int,
        take_profit_price: float,
        stop_loss_price: float,
        trader: str = None,
    ):
        """
        Builds a transaction to update the stop loss and take profit of a trade.

        Args:
            pair_index: The pair index.
            trade_index: The trade index.
            take_profit_price: The take profit price.
            stop_loss_price: The stop loss price. Pass 0 if you want to remove the stop loss.
            trader (optional): The trader's wallet address.
        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if take_profit_price == 0:
            raise ValueError("Take profit price cannot be 0")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        pair_name = await self.client.pairs_cache.get_pair_name_from_index(pair_index)

        price_data = await self.feed_client.get_latest_price_updates([pair_name])

        price_update_data = "0x" + price_data.binary.data[0]

        take_profit_price = int(take_profit_price * 10**10)
        stop_loss_price = int(stop_loss_price * 10**10)

        transaction = await Trading.functions.updateTpAndSl(
            pair_index,
            trade_index,
            stop_loss_price,
            take_profit_price,
            [price_update_data],
        ).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "value": 1,
                "nonce": await self.client.get_transaction_count(trader),
                "gas": 1_000_000,
            }
        )

        return transaction

    async def build_trade_tp_sl_update_tx_delegate(
        self,
        pair_index: int,
        trade_index: int,
        take_profit_price: float,
        stop_loss_price: float,
        trader: str = None,
    ):
        """
        Builds a transaction to update the stop loss and take profit of a trade.

        Args:
            pair_index: The pair index.
            trade_index: The trade index.
            take_profit_price: The take profit price.
            stop_loss_price: The stop loss price. Pass 0 if you want to remove the stop loss.
            trader (optional): The trader's wallet address.
        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if take_profit_price == 0:
            raise ValueError("Take profit price cannot be 0")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        pair_name = await self.client.pairs_cache.get_pair_name_from_index(pair_index)

        price_data = await self.feed_client.get_latest_price_updates([pair_name])

        price_update_data = "0x" + price_data.binary.data[0]

        take_profit_price = int(take_profit_price * 10**10)
        stop_loss_price = int(stop_loss_price * 10**10)

        transaction = await Trading.functions.updateTpAndSl(
            pair_index,
            trade_index,
            stop_loss_price,
            take_profit_price,
            [price_update_data],
        ).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "value": 0,
                "nonce": await self.client.get_transaction_count(trader),
                "gas": 1_000_000,
            }
        )

        delegate_transaction = await Trading.functions.delegatedAction(
            trader, transaction["data"]
        ).build_transaction(
            {
                "from": self.client.get_signer().get_ethereum_address(),
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(
                    self.client.get_signer().get_ethereum_address()
                ),
                "value": 1,
                "gas": 1_000_000,
            }
        )
        return delegate_transaction

    async def get_delegate(self, trader: Optional[str] = None) -> str:
        """
        Gets the delegate address for a trader.

        Args:
            trader: The trader's wallet address. Defaults to signer's address.

        Returns:
            The delegate address, or zero address if no delegate is set.
        """
        Trading = self.client.contracts.get("Trading")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        delegate = await Trading.functions.delegations(trader).call()
        return delegate

    async def build_set_delegate_tx(
        self,
        delegate: str,
        trader: Optional[str] = None,
    ):
        """
        Builds a transaction to set a delegate for trading.

        The delegate can perform all trade-related actions on behalf of the trader.
        Each wallet can have at most one delegate.

        Args:
            delegate: The delegate's wallet address.
            trader: The trader's wallet address. Defaults to signer's address.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        transaction = await Trading.functions.setDelegate(delegate).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(trader),
            }
        )

        return transaction

    async def build_remove_delegate_tx(self, trader: Optional[str] = None):
        """
        Builds a transaction to remove the current delegate.

        Args:
            trader: The trader's wallet address. Defaults to signer's address.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        transaction = await Trading.functions.removeDelegate().build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(trader),
            }
        )

        return transaction
