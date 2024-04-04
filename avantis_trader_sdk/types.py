from pydantic import BaseModel, Field, conint, validator, ValidationError
from typing import Dict, Optional
import time
import re


class PairInfoFeed(BaseModel):
    maxDeviationP: int
    feedId: str

    @validator("maxDeviationP", pre=True, allow_reuse=True)
    def convert_max_deviation(cls, v):
        return v / 10**10


class PairInfo(BaseModel):
    from_: str = Field(..., alias="from")
    to: str
    feed: PairInfoFeed
    backupFeed: PairInfoFeed
    constant_spread_bps: float = Field(..., alias="spreadP")
    price_impact_parameter: float = Field(..., alias="priceImpactMultiplier")
    skew_impact_parameter: float = Field(..., alias="skewImpactMultiplier")
    group_index: int = Field(..., alias="groupIndex")
    fee_index: int = Field(..., alias="feeIndex")
    group_open_interest_percentage: float = Field(
        ..., alias="groupOpenInterestPecentage"
    )
    max_wallet_oi: float = Field(..., alias="maxWalletOI")

    @validator(
        "price_impact_parameter", "skew_impact_parameter", pre=True, allow_reuse=True
    )
    def convert_to_float_10(cls, v):
        return v / 10**10

    @validator("constant_spread_bps", pre=True, allow_reuse=True)
    def convert_to_float_10_bps(cls, v):
        return v / 10**10 * 100

    class Config:
        allow_population_by_field_name = True


class OpenInterest(BaseModel):
    long: Dict[str, float]
    short: Dict[str, float]


class OpenInterestLimits(BaseModel):
    limits: Dict[str, float]


class Utilization(BaseModel):
    utilization: Dict[str, float]


class Skew(BaseModel):
    skew: Dict[str, float]


class MarginFee(BaseModel):
    hourly_base_fee_parameter: Dict[str, float]
    hourly_margin_fee_long_bps: Dict[str, float]
    hourly_margin_fee_short_bps: Dict[str, float]


class MarginFeeSingle(BaseModel):
    hourly_base_fee_parameter: float
    hourly_margin_fee_long_bps: float
    hourly_margin_fee_short_bps: float


class DepthSingle(BaseModel):
    above: float
    below: float


class PairInfoExtended(PairInfo):
    asset_open_interest_limit: float
    asset_open_interest: Dict[str, float]
    asset_utilization: float
    asset_skew: float
    blended_utilization: float
    blended_skew: float
    margin_fee: MarginFeeSingle
    one_percent_depth: DepthSingle
    new_1k_long_opening_fee_bps: float  # Opening fee for new $1,000 long position
    new_1k_short_opening_fee_bps: float  # Opening fee for new $1,000 short position
    new_1k_long_opening_spread_bps: float  # Opening spread for new $1,000 long position
    new_1k_short_opening_spread_bps: (
        float  # Opening spread for new $1,000 short position
    )
    price_impact_spread_long_bps: float
    price_impact_spread_short_bps: float
    skew_impact_spread_long_bps: float
    skew_impact_spread_short_bps: float

    class Config:
        allow_population_by_field_name = True


class PairSpread(BaseModel):
    spread: Dict[str, float]


class PriceFeedResponse(BaseModel):
    id: str
    price: Dict[str, str]
    ema_price: Dict[str, str]
    pair: str
    converted_price: float = 0.0
    converted_ema_price: float = 0.0

    @validator("converted_price", always=True, pre=True)
    def convert_price(cls, v, values):
        price_info = values.get("price")
        if price_info:
            return float(price_info["price"]) / 10 ** -int(price_info["expo"])
        return v

    @validator("converted_ema_price", always=True, pre=True)
    def convert_ema_price(cls, v, values):
        ema_price_info = values.get("ema_price")
        if ema_price_info:
            return float(ema_price_info["price"]) / 10 ** -int(ema_price_info["expo"])
        return v


class Spread(BaseModel):
    long: Optional[Dict[str, float]] = None
    short: Optional[Dict[str, float]] = None

    @validator("long", "short", always=True)
    def check_at_least_one(cls, v, values, field, config, **kwargs):
        if "long" not in field.name and "short" not in field.name:
            raise ValueError('At least one of "long" or "short" must be present.')
        return v


class Depth(BaseModel):
    above: Optional[Dict[str, float]] = None
    below: Optional[Dict[str, float]] = None

    @validator("above", "below", always=True)
    def check_at_least_one(cls, v, values, field, config, **kwargs):
        if "above" not in field.name and "below" not in field.name:
            raise ValueError('At least one of "above" or "below" must be present.')
        return v


class Fee(BaseModel):
    long: Optional[Dict[str, float]] = None
    short: Optional[Dict[str, float]] = None

    @validator("long", "short", always=True)
    def check_at_least_one(cls, v, values, field, config, **kwargs):
        if "long" not in field.name and "short" not in field.name:
            raise ValueError('At least one of "long" or "short" must be present.')
        return v


# struct Trade {
#         address trader;
#         uint pairIndex;
#         uint index;
#         uint initialPosToken; // 1e6
#         uint positionSizeUSDC; // 1e6
#         uint openPrice; // 1e10 PRECISION
#         bool buy;
#         uint leverage;
#         uint tp; // 1e10 PRECISION
#         uint sl; // 1e10 PRECISION
#         uint timestamp;
#     }


class TradeInput(BaseModel):
    trader: str = "0x1234567890123456789012345678901234567890"
    pairIndex: int = Field(..., alias="pair_index")
    index: int = Field(0, alias="trade_index")
    initialPosToken: int = Field(..., alias="collateral")
    positionSizeUSDC: int = Field(0, alias="position_size_usdc")
    openPrice: int = Field(0, alias="open_price")
    buy: bool = Field(..., alias="is_long")
    leverage: int
    tp: Optional[int] = 0
    sl: Optional[int] = 0
    timestamp: Optional[int] = None

    @validator("trader")
    def validate_eth_address(cls, v):
        if not re.match(r"^0x[a-fA-F0-9]{40}$", v):
            raise ValueError("Invalid Ethereum address")
        return v

    @validator("tp", always=True)
    def validate_tp(cls, v, values, **kwargs):
        if values.get("openPrice") not in [0, None] and v in [0, None]:
            raise ValueError("tp is required when openPrice is provided and is not 0")
        return v

    @validator("openPrice", "tp", "sl", "leverage", pre=True)
    def convert_to_float_10(cls, v):
        return int(v * 10**10)

    @validator("initialPosToken", "positionSizeUSDC", pre=True, allow_reuse=True)
    def convert_to_float_6(cls, v):
        return int(v * 10**6)

    @validator("timestamp", pre=True, always=True)
    def set_default_timestamp(cls, v):
        return v or int(time.time())

    class Config:
        allow_population_by_field_name = True


class TradeResponse(BaseModel):
    trader: str
    pairIndex: int
    index: int
    initialPosToken: int
    positionSizeUSDC: int
    openPrice: int
    buy: bool
    leverage: int
    tp: int
    sl: int
    timestamp: int

    @validator("trader")
    def validate_eth_address(cls, v):
        if not re.match(r"^0x[a-fA-F0-9]{40}$", v):
            raise ValueError("Invalid Ethereum address")
        return v

    @validator("openPrice", "tp", "sl", "leverage", pre=True)
    def convert_to_float_10(cls, v):
        return v / 10**10

    @validator("initialPosToken", "positionSizeUSDC", pre=True, allow_reuse=True)
    def convert_to_float_6(cls, v):
        return v / 10**6


class SnapshotOpenInterest(BaseModel):
    long: float
    short: float


class SnapshotGroup(BaseModel):
    group_open_interest_limit: float
    group_open_interest: SnapshotOpenInterest
    group_utilization: float
    group_skew: float
    pairs: Dict[str, PairInfoExtended]


class Snapshot(BaseModel):
    groups: Dict[conint(ge=0), SnapshotGroup]
