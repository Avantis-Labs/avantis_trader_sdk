from pydantic import BaseModel, Field, validator

class PairInfoFeed(BaseModel):
    maxDeviationP: int
    feedId: str
    
    @validator('maxDeviationP', pre=True, allow_reuse=True)
    def convert_max_deviation(cls, v):
        return v / 10 ** 10

class PairInfo(BaseModel):
    from_: str = Field(..., alias='from')
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
    @validator('spreadP', pre=True, allow_reuse=True)
    def convert_spreadP(cls, v):
        return v / 10 ** 10