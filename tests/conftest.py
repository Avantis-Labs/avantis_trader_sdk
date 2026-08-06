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

# Shared /v2/trading snapshot: fixed-fee pairs (isPnlTypeAllowed 0) plus their
# Upside twins as separate _UPSIDE pairs (isPnlTypeAllowed 1), mirroring the
# testnet catalog (BTC_UPSIDE/USD = 116, USD/JPY_UPSIDE = 119).
TRADING_SNAPSHOT = {
    "pairInfos": {
        "ETH/USD": {
            "index": 1,
            "from": "ETH",
            "to": "USD",
            "feed": {"feedId": "0xeth"},
            "storagePairParams": {"isPnlTypeAllowed": 0},
        },
        "BTC/USD": {
            "index": 2,
            "from": "BTC",
            "to": "USD",
            "feed": {"feedId": "0xbtc"},
            "storagePairParams": {"isPnlTypeAllowed": 0},
        },
        "USD/JPY": {
            "index": 20,
            "from": "USD",
            "to": "JPY",
            "feed": {"feedId": "0xjpy"},
            "storagePairParams": {"isPnlTypeAllowed": 0},
        },
        "BTC_UPSIDE/USD": {
            "index": 116,
            "from": "BTC_UPSIDE",
            "to": "USD",
            "feed": {"feedId": "0xbtc"},
            "storagePairParams": {"isPnlTypeAllowed": 1},
        },
        "USD/JPY_UPSIDE": {
            "index": 119,
            "from": "USD",
            "to": "JPY_UPSIDE",
            "feed": {"feedId": "0xjpy"},
            "storagePairParams": {"isPnlTypeAllowed": 1},
        },
    }
}


def mock_data_api(base_url: str):
    """Mount the /v2/trading respx route (trade methods resolve pairs first)."""
    import httpx
    import respx

    return respx.get(f"{base_url}/v2/trading").mock(
        return_value=httpx.Response(200, json=TRADING_SNAPSHOT)
    )


@pytest.fixture
def meta() -> dict:
    return json.loads(json.dumps(META))
