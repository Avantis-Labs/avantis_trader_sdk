import json
from pathlib import Path

import pytest

VECTORS = json.loads((Path(__file__).parent / "vectors" / "vectors.json").read_text())

TEST_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
TEST_ADDRESS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
TRADER = "0x1111111111111111111111111111111111111111"

META = {
    "chainId": 31337,
    "addresses": {
        "tradingRouter": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
        "tradingStorage": "0x2222222222222222222222222222222222222222",
        "usdc": "0x3333333333333333333333333333333333333333",
        "referral": "0x4444444444444444444444444444444444444444",
    },
    "eip712": {
        "trading": {
            "name": "AvantisTrading",
            "version": "1",
            "chainId": 31337,
            "verifyingContract": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
        },
        "signatureFormat": "rsv-65-bytes",
    },
    "enums": {
        "openOrderType": {"market": 0, "stop_limit": 1, "limit": 2, "market_pnl": 3},
    },
    "units": {"price": "1e10", "leverage": "1e10", "usdc": "1e6"},
    "defaults": {"executionFeeWei": "0", "intentDeadlineMs": 120000, "slippagePercent": "1"},
}


@pytest.fixture
def meta() -> dict:
    return json.loads(json.dumps(META))
