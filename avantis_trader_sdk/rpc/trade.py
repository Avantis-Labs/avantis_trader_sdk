from ..feed.feed_client import FeedClient
from ..types import (
    TradeInput,
    TradeInputOrderType,
    TradeExtendedResponse,
    TradeResponse,
    TradeInfo,
    PendingLimitOrderExtendedResponse,
    MarginUpdateType,
)
from typing import Optional
import math


class TradeRPC:
    """
    The TradeRPC class contains methods for retrieving trading parameters from the Avantis Protocol.
    """

    def __init__(self, client, feed_client: FeedClient):
        """
        Constructor for the TradeRPC class.

        Args:
            client: The TraderClient object.
            feed_client: The FeedClient object.
        """
        self.client = client
        self.feed_client = feed_client

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

    async def get_trades(self, trader: Optional[str] = None):
        """
        Gets the trades.

        Args:
            trader: The trader's wallet address.

        Returns:
            The trades.
        """
        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        result = (
            await self.client.contracts.get("Multicall")
            .functions.getPositions(trader)
            .call()
        )
        trades = []
        pendingOpenLimitOrders = []

        for aggregated_trade in result[0]:  # Access the list of aggregated trades
            (trade, trade_info, margin_fee, liquidation_price) = aggregated_trade

            if trade[7] <= 0:
                continue

            # Extract and format the trade data
            trade_details = {
                "trade": {
                    "trader": trade[0],
                    "pairIndex": trade[1],
                    "index": trade[2],
                    "initialPosToken": trade[3],
                    "positionSizeUSDC": trade[4],
                    "openPrice": trade[5],
                    "buy": trade[6],
                    "leverage": trade[7],
                    "tp": trade[8],
                    "sl": trade[9],
                    "timestamp": trade[10],
                },
                "additional_info": {
                    "openInterestUSDC": trade_info[0],
                    "tpLastUpdated": trade_info[1],
                    "slLastUpdated": trade_info[2],
                    "beingMarketClosed": trade_info[3],
                    "lossProtectionPercentage": await self.client.trading_parameters.get_loss_protection_percentage_by_tier(
                        trade_info[4], trade[1]
                    ),
                },
                "margin_fee": margin_fee,
                "liquidationPrice": liquidation_price,
            }
            trades.append(
                TradeExtendedResponse(
                    trade=TradeResponse(**trade_details["trade"]),
                    additional_info=TradeInfo(**trade_details["additional_info"]),
                    margin_fee=trade_details["margin_fee"],
                    liquidation_price=trade_details["liquidationPrice"],
                )
            )

        for aggregated_order in result[1]:  # Access the list of aggregated orders
            (order, liquidation_price) = aggregated_order

            if order[5] <= 0:
                continue

            # Extract and format the order data
            order_details = {
                "trader": order[0],
                "pairIndex": order[1],
                "index": order[2],
                "positionSize": order[3],
                "buy": order[4],
                "leverage": order[5],
                "tp": order[6],
                "sl": order[7],
                "price": order[8],
                "slippageP": order[9],
                "block": order[10],
                # 'executionFee': order[11],
                "liquidation_price": liquidation_price,
            }
            pendingOpenLimitOrders.append(
                PendingLimitOrderExtendedResponse(**order_details)
            )

        return trades, pendingOpenLimitOrders

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

        price_data = await feed_client.get_latest_price_updates([pair_name])

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

        feed_client = self.FeedClient()

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
