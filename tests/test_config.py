"""Central-routing config: /core, /twap, /batched-market and /blitz derive
from api_base_url unless individually overridden."""

from avantis_trader_sdk.config import AvantisConfig


def test_testnet_derives_centrally_routed_urls(monkeypatch):
    for var in (
        "AVANTIS_API_BASE_URL",
        "AVANTIS_CORE_API_URL",
        "AVANTIS_TWAP_API_URL",
        "AVANTIS_BATCHED_MARKET_URL",
        "AVANTIS_RELAYER_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    cfg = AvantisConfig.load(network="testnet")
    assert cfg.api_base_url == "https://staging-api.avantisfi.com"
    assert cfg.core_api_url == "https://staging-api.avantisfi.com/core"
    assert cfg.twap_api_url == "https://staging-api.avantisfi.com/twap"
    assert cfg.batched_market_url == "https://staging-api.avantisfi.com/batched-market"
    assert cfg.relayer_url == "https://staging-api.avantisfi.com/blitz"


def test_mainnet_uses_prod_api(monkeypatch):
    monkeypatch.delenv("AVANTIS_API_BASE_URL", raising=False)
    cfg = AvantisConfig.load(network="mainnet")
    assert cfg.api_base_url == "https://prod-api.avantisfi.com"
    assert cfg.core_api_url == "https://prod-api.avantisfi.com/core"
    assert cfg.batched_market_url == "https://prod-api.avantisfi.com/batched-market"


def test_base_url_override_propagates():
    cfg = AvantisConfig.load(network="testnet", api_base_url="https://my-proxy.test/")
    assert cfg.core_api_url == "https://my-proxy.test/core"
    assert cfg.twap_api_url == "https://my-proxy.test/twap"
    assert cfg.batched_market_url == "https://my-proxy.test/batched-market"
    assert cfg.relayer_url == "https://my-proxy.test/blitz"


def test_individual_override_beats_derivation():
    cfg = AvantisConfig.load(
        network="testnet",
        core_api_url="https://core.local",
        relayer_url="https://blitz.local",
    )
    assert cfg.core_api_url == "https://core.local"
    assert cfg.relayer_url == "https://blitz.local"
    # untouched services still derive
    assert cfg.twap_api_url == "https://staging-api.avantisfi.com/twap"


def test_env_overrides_respected(monkeypatch):
    monkeypatch.setenv("AVANTIS_API_BASE_URL", "https://env-base.test")
    monkeypatch.setenv("AVANTIS_TWAP_API_URL", "https://env-twap.test")
    cfg = AvantisConfig.load(network="testnet")
    assert cfg.twap_api_url == "https://env-twap.test"
    assert cfg.core_api_url == "https://env-base.test/core"
    assert cfg.batched_market_url == "https://env-base.test/batched-market"
