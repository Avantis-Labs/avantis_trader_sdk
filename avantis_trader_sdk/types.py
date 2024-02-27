from pydantic import BaseModel, Field, validator
from typing import Dict, List


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
