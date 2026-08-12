"""Central-routing config: /core, /twap, /batched-market, /blitz, /data and
/risk/v2 derive from api_base_url unless individually overridden."""

from avantis_trader_sdk.config import AvantisConfig


def test_testnet_derives_centrally_routed_urls(monkeypatch):
    for var in (
        "AVANTIS_API_BASE_URL",
        "AVANTIS_CORE_API_URL",
        "AVANTIS_TWAP_API_URL",
        "AVANTIS_BATCHED_MARKET_URL",
        "AVANTIS_RELAYER_URL",
        "AVANTIS_DATA_API_URL",
        "AVANTIS_RISK_V2_API_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    cfg = AvantisConfig.load(network="testnet")
    assert cfg.api_base_url == "https://staging-api.avantisfi.com"
    assert cfg.core_api_url == "https://staging-api.avantisfi.com/core"
    assert cfg.twap_api_url == "https://staging-api.avantisfi.com/twap"
    assert cfg.batched_market_url == "https://staging-api.avantisfi.com/batched-market"
    assert cfg.relayer_url == "https://staging-api.avantisfi.com/blitz"
    assert cfg.data_api_url == "https://staging-api.avantisfi.com/data"
    assert cfg.risk_v2_api_url == "https://staging-api.avantisfi.com/risk/v2"


def test_default_network_is_mainnet(monkeypatch):
    """Public releases default to mainnet; testnet (the staging stack) is
    an explicit opt-in via AVANTIS_NETWORK=testnet."""
    monkeypatch.delenv("AVANTIS_NETWORK", raising=False)
    monkeypatch.delenv("AVANTIS_API_BASE_URL", raising=False)
    cfg = AvantisConfig.load()
    assert cfg.network == "mainnet"
    assert cfg.api_base_url == "https://prod-api.avantisfi.com"
    monkeypatch.setenv("AVANTIS_NETWORK", "testnet")
    assert AvantisConfig.load().network == "testnet"


def test_mainnet_uses_prod_api(monkeypatch):
    monkeypatch.delenv("AVANTIS_API_BASE_URL", raising=False)
    cfg = AvantisConfig.load(network="mainnet")
    assert cfg.api_base_url == "https://prod-api.avantisfi.com"
    assert cfg.core_api_url == "https://prod-api.avantisfi.com/core"
    assert cfg.batched_market_url == "https://prod-api.avantisfi.com/batched-market"
    assert cfg.data_api_url == "https://prod-api.avantisfi.com/data"
    assert cfg.risk_v2_api_url == "https://prod-api.avantisfi.com/risk/v2"


def test_base_url_override_propagates():
    cfg = AvantisConfig.load(network="testnet", api_base_url="https://my-proxy.test/")
    assert cfg.core_api_url == "https://my-proxy.test/core"
    assert cfg.twap_api_url == "https://my-proxy.test/twap"
    assert cfg.batched_market_url == "https://my-proxy.test/batched-market"
    assert cfg.relayer_url == "https://my-proxy.test/blitz"
    assert cfg.data_api_url == "https://my-proxy.test/data"
    assert cfg.risk_v2_api_url == "https://my-proxy.test/risk/v2"


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


def test_no_rpc_by_default(monkeypatch):
    """No RPC in the default mix: delegate/API keys are fresh EOAs (nonce-0
    authorizations), so relayer mode is fully API-driven. rpc_url is an
    explicit opt-in for direct mode or trader-EOA signing."""
    monkeypatch.delenv("AVANTIS_RPC_URL", raising=False)
    assert AvantisConfig.load(network="testnet").rpc_url is None
    assert AvantisConfig.load(network="mainnet").rpc_url is None
    monkeypatch.setenv("AVANTIS_RPC_URL", "https://my-node.test")
    assert AvantisConfig.load(network="testnet").rpc_url == "https://my-node.test"
