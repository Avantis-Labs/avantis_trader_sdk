from pydantic import BaseModel, Field, validator, ValidationError
from typing import Dict, Optional


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
    spreadP: int
    priceImpactMultiplier: int
    skewImpactMultiplier: int
    groupIndex: int
    feeIndex: int
    groupOpenInterestPecentage: int
    maxWalletOI: int

    @validator("spreadP", pre=True, allow_reuse=True)
    def convert_spreadP(cls, v):
        return v / 10**10


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
    base: Dict[str, float]
    margin_long: Dict[str, float]
    margin_short: Dict[str, float]


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


class PriceImpactSpread(BaseModel):
    long: Optional[Dict[str, float]] = None
    short: Optional[Dict[str, float]] = None

    @validator("long", "short", always=True)
    def check_at_least_one(cls, v, values, field, config, **kwargs):
        if "long" not in field.name and "short" not in field.name:
            raise ValueError('At least one of "long" or "short" must be present.')
        return v
