"""Models for the data API /v2/trading snapshot (human units).

The snapshot is rich; models type the load-bearing fields and keep the rest
accessible via ``extra`` so nothing is lost.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..errors import ApiError

# Upside pairs (formerly "ZFP"/zero-fee) are listed as separate markets whose
# base or quote symbol carries this suffix (BTC_UPSIDE/USD, USD/JPY_UPSIDE).
UPSIDE_SUFFIX = "_UPSIDE"


def strip_upside_suffix(symbol: str) -> str:
    """"BTC_UPSIDE" -> "BTC"; non-upside symbols pass through unchanged."""
    if symbol.upper().endswith(UPSIDE_SUFFIX):
        return symbol[: -len(UPSIDE_SUFFIX)]
    return symbol


class Leverages(BaseModel):
    model_config = ConfigDict(extra="allow")

    min_leverage: float = Field(alias="minLeverage", default=1)
    max_leverage: float = Field(alias="maxLeverage", default=1)
    pnl_min_leverage: float = Field(alias="pnlMinLeverage", default=0)
    pnl_max_leverage: float = Field(alias="pnlMaxLeverage", default=0)


class OpenInterest(BaseModel):
    model_config = ConfigDict(extra="allow")

    long: float = 0
    short: float = 0


class FundingRate(BaseModel):
    model_config = ConfigDict(extra="allow")

    long: float = 0
    short: float = 0


class FeedAttributes(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str | None = None
    asset_type: str | None = Field(alias="assetType", default=None)
    is_open: bool = Field(alias="isOpen", default=True)
    next_open: int = Field(alias="nextOpen", default=0)
    next_close: int = Field(alias="nextClose", default=0)
    schedule: str | None = None


class Feed(BaseModel):
    model_config = ConfigDict(extra="allow")

    feed_id: str | None = Field(alias="feedId", default=None)
    attributes: FeedAttributes = Field(default_factory=FeedAttributes)


class PairValues(BaseModel):
    model_config = ConfigDict(extra="allow")

    max_gain_p: float = Field(alias="maxGainP", default=2500)
    max_sl_p: float = Field(alias="maxSlP", default=80)
    max_long_oi_p: float = Field(alias="maxLongOiP", default=100)
    max_short_oi_p: float = Field(alias="maxShortOiP", default=100)
    max_wallet_oi: float = Field(alias="maxWalletOI", default=0)
    group_open_interest_percentage_p: float = Field(
        alias="groupOpenInterestPercentageP", default=100
    )


class PnlFees(BaseModel):
    model_config = ConfigDict(extra="allow")

    num_tiers: int = Field(alias="numTiers", default=0)
    tier_p: list[float] = Field(alias="tierP", default_factory=list)
    fees_p: list[float] = Field(alias="feesP", default_factory=list)


class TwapParams(BaseModel):
    model_config = ConfigDict(extra="allow")

    min_run_time: int = Field(alias="minRunTime", default=0)
    max_run_time: int = Field(alias="maxRunTime", default=0)
    frequency: int = Field(alias="frequency", default=0)
    twap_fee: float = Field(alias="twapFee", default=0)


class AdditionalPairParams2(BaseModel):
    model_config = ConfigDict(extra="allow")

    open_maker_fee_p: float = Field(alias="openMakerFeeP", default=0)
    close_maker_fee_p: float = Field(alias="closeMakerFeeP", default=0)
    open_taker_fee_p: float = Field(alias="openTakerFeeP", default=0)
    close_taker_fee_p: float = Field(alias="closeTakerFeeP", default=0)
    close_only_mode: bool = Field(alias="closeOnlyMode", default=False)


class LazerFeed(BaseModel):
    model_config = ConfigDict(extra="allow")

    feed_id: int | None = Field(alias="feedId", default=None)
    exponent: int | None = None
    state: str | None = None


class StoragePairParams(BaseModel):
    """On-chain pair params (TradingStorage). ``is_pnl_type_allowed`` gates the
    Upside (PnL) order type: the contract reverts ``PnlOrderNotAllowed`` unless
    it matches the order's ``_type``, so it must be 1 on upside pairs and the
    order type plain market everywhere else."""

    model_config = ConfigDict(extra="allow")

    is_pnl_type_allowed: int = Field(alias="isPnlTypeAllowed", default=0)
    pos_spread_cap: float = Field(alias="posSpreadCap", default=0)
    neg_spread_cap: float = Field(alias="negSpreadCap", default=0)
    pnl_pos_spread_cap: float = Field(alias="pnlPosSpreadCap", default=0)
    pnl_neg_spread_cap: float = Field(alias="pnlNegSpreadCap", default=0)


class PairInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int
    from_symbol: str = Field(alias="from")
    to_symbol: str = Field(alias="to")
    group_index: int = Field(alias="groupIndex", default=0)
    is_pair_listed: bool = Field(alias="isPairListed", default=True)
    leverages: Leverages = Field(default_factory=Leverages)
    spread_p: float = Field(alias="spreadP", default=0)
    pnl_spread_p: float = Field(alias="pnlSpreadP", default=0)
    open_fee_p: float = Field(alias="openFeeP", default=0)
    close_fee_p: float = Field(alias="closeFeeP", default=0)
    min_lev_pos_usdc: float = Field(alias="minLevPosUSDC", default=0)
    open_interest: OpenInterest = Field(alias="openInterest", default_factory=OpenInterest)
    coin_oi: OpenInterest = Field(alias="coinOI", default_factory=OpenInterest)
    pair_oi: float = Field(alias="pairOI", default=0)
    pair_max_oi: float = Field(alias="pairMaxOI", default=0)
    max_wallet_oi: float = Field(alias="maxWalletOI", default=0)
    margin_fee: FundingRate = Field(alias="marginFee", default_factory=FundingRate)
    funding_rate: FundingRate = Field(alias="fundingRate", default_factory=FundingRate)
    funding_fee_per_hour_p: float = Field(alias="fundingFeePerHourP", default=0)
    feed: Feed = Field(default_factory=Feed)
    lazer_feed: LazerFeed | None = Field(alias="lazerFeed", default=None)
    values: PairValues = Field(default_factory=PairValues)
    pnl_fees: PnlFees = Field(alias="pnlFees", default_factory=PnlFees)
    loss_protection_multiplier: dict[str, float] = Field(
        alias="lossProtectionMultiplier", default_factory=dict
    )
    long_skew_config: dict[str, float] = Field(alias="longSkewConfig", default_factory=dict)
    short_skew_config: dict[str, float] = Field(alias="shortSkewConfig", default_factory=dict)
    skew_eq_params: list[list[float]] = Field(alias="skewEqParams", default_factory=list)
    twap_params: TwapParams = Field(alias="pairTwapParams", default_factory=TwapParams)
    additional_params: AdditionalPairParams2 = Field(
        alias="additionalPairParams2", default_factory=AdditionalPairParams2
    )
    storage_pair_params: StoragePairParams = Field(
        alias="storagePairParams", default_factory=StoragePairParams
    )
    liquidity: dict[str, float] = Field(default_factory=dict)

    @property
    def symbol(self) -> str:
        return f"{self.from_symbol}/{self.to_symbol}"

    @property
    def is_upside(self) -> bool:
        """True for Upside markets (BTC_UPSIDE/USD, USD/JPY_UPSIDE, ...).

        Same convention as the Avantis UI: the ``_UPSIDE`` suffix on either
        symbol. Upside pairs take ONLY the PnL order type (market_pnl) and are
        market-only — no limit/stop opens, no TWAP.
        """
        upper_from = self.from_symbol.upper()
        upper_to = self.to_symbol.upper()
        return upper_from.endswith(UPSIDE_SUFFIX) or upper_to.endswith(UPSIDE_SUFFIX)

    @property
    def base_symbol(self) -> str:
        """The pair symbol with any ``_UPSIDE`` suffix stripped
        ("BTC_UPSIDE/USD" -> "BTC/USD")."""
        return f"{strip_upside_suffix(self.from_symbol)}/{strip_upside_suffix(self.to_symbol)}"

    @property
    def is_market_open(self) -> bool:
        """Market-hours check (forex/commodity groups use the feed schedule)."""
        import time

        attrs = self.feed.attributes
        if self.group_index not in (2, 3, 6):
            return True
        now = time.time()
        is_open = attrs.is_open or (attrs.next_open > 0 and now > attrs.next_open)
        before_close = attrs.next_close == 0 or now < attrs.next_close
        return is_open and before_close


class GroupInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    group_max_oi: float = Field(alias="groupMaxOI", default=0)
    group_oi: float = Field(alias="groupOI", default=0)


def _normalize_symbol(ref: str) -> tuple[str, str]:
    """Legacy separator rewrite ("eth-usd"/"eth_usd" -> ETH, USD).

    Only used as the LAST resolution step: upside symbols carry a real
    underscore (BTC_UPSIDE) that this rewrite would destroy, so exact
    matching runs first in :meth:`TradingSnapshot.pair_by_symbol`.
    """
    cleaned = ref.upper().replace("-", "/").replace("_", "/")
    if "/" not in cleaned:
        return cleaned, "USD"
    base, quote = cleaned.split("/", 1)
    return base, quote


class TradingSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    data_version: int | None = Field(alias="dataVersion", default=None)
    pair_count: int = Field(alias="pairCount", default=0)
    max_trades_per_pair: int = Field(alias="maxTradesPerPair", default=0)
    total_oi: float = Field(alias="totalOi", default=0)
    max_open_interest: float = Field(alias="maxOpenInterest", default=0)
    pair_infos: dict[str, PairInfo] = Field(alias="pairInfos", default_factory=dict)
    group_info: dict[str, GroupInfo] = Field(alias="groupInfo", default_factory=dict)

    @property
    def pairs(self) -> dict[int, PairInfo]:
        return {info.index: info for info in self.pair_infos.values()}

    def pair_by_symbol(self, ref: str) -> PairInfo:
        """Resolve "ETH/USD", "eth-usd", "ETH", "BTC_UPSIDE", "USD/JPY_UPSIDE".

        Exact from/to matching runs first with underscores preserved (upside
        symbols contain them), then a bare-base match (quote defaults to USD),
        and finally the legacy ``-``/``_`` -> ``/`` rewrite.
        """
        cleaned = ref.strip().upper()
        pairs = list(self.pair_infos.values())
        for info in pairs:
            if info.symbol.upper() == cleaned:
                return info
        base_matches = [p for p in pairs if p.from_symbol.upper() == cleaned]
        for info in base_matches:
            if info.to_symbol.upper() == "USD":
                return info
        if len(base_matches) == 1:
            return base_matches[0]
        base, quote = _normalize_symbol(ref)
        for info in pairs:
            if info.from_symbol.upper() == base and info.to_symbol.upper() == quote:
                return info
        raise ApiError(f"unknown pair {ref!r}")
