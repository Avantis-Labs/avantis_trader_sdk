"""Central-routing config: /core, /twap, /batched-market, /blitz, /data and
/risk/v2 derive from api_base_url unless individually overridden."""

from veranta_sdk.config import VerantaConfig


def test_testnet_derives_centrally_routed_urls(monkeypatch):
    for var in (
        "VERANTA_API_BASE_URL",
        "VERANTA_CORE_API_URL",
        "VERANTA_TWAP_API_URL",
        "VERANTA_BATCHED_MARKET_URL",
        "VERANTA_RELAYER_URL",
        "VERANTA_DATA_API_URL",
        "VERANTA_RISK_V2_API_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    cfg = VerantaConfig.load(network="testnet")
    assert cfg.api_base_url == "https://staging-api.veranta.xyz"
    assert cfg.core_api_url == "https://staging-api.veranta.xyz/core"
    assert cfg.twap_api_url == "https://staging-api.veranta.xyz/twap"
    assert cfg.batched_market_url == "https://staging-api.veranta.xyz/batched-market"
    assert cfg.relayer_url == "https://staging-api.veranta.xyz/blitz"
    assert cfg.data_api_url == "https://staging-api.veranta.xyz/data"
    assert cfg.risk_v2_api_url == "https://staging-api.veranta.xyz/risk/v2"


def test_default_network_is_mainnet(monkeypatch):
    """Public releases default to mainnet; testnet (the staging stack) is
    an explicit opt-in via VERANTA_NETWORK=testnet."""
    monkeypatch.delenv("VERANTA_NETWORK", raising=False)
    monkeypatch.delenv("VERANTA_API_BASE_URL", raising=False)
    cfg = VerantaConfig.load()
    assert cfg.network == "mainnet"
    assert cfg.api_base_url == "https://prod-api.veranta.xyz"
    monkeypatch.setenv("VERANTA_NETWORK", "testnet")
    assert VerantaConfig.load().network == "testnet"


def test_mainnet_uses_prod_api(monkeypatch):
    monkeypatch.delenv("VERANTA_API_BASE_URL", raising=False)
    cfg = VerantaConfig.load(network="mainnet")
    assert cfg.api_base_url == "https://prod-api.veranta.xyz"
    assert cfg.core_api_url == "https://prod-api.veranta.xyz/core"
    assert cfg.batched_market_url == "https://prod-api.veranta.xyz/batched-market"
    assert cfg.data_api_url == "https://prod-api.veranta.xyz/data"
    assert cfg.risk_v2_api_url == "https://prod-api.veranta.xyz/risk/v2"


def test_base_url_override_propagates():
    cfg = VerantaConfig.load(network="testnet", api_base_url="https://my-proxy.test/")
    assert cfg.core_api_url == "https://my-proxy.test/core"
    assert cfg.twap_api_url == "https://my-proxy.test/twap"
    assert cfg.batched_market_url == "https://my-proxy.test/batched-market"
    assert cfg.relayer_url == "https://my-proxy.test/blitz"
    assert cfg.data_api_url == "https://my-proxy.test/data"
    assert cfg.risk_v2_api_url == "https://my-proxy.test/risk/v2"


def test_individual_override_beats_derivation():
    cfg = VerantaConfig.load(
        network="testnet",
        core_api_url="https://core.local",
        relayer_url="https://blitz.local",
    )
    assert cfg.core_api_url == "https://core.local"
    assert cfg.relayer_url == "https://blitz.local"
    # untouched services still derive
    assert cfg.twap_api_url == "https://staging-api.veranta.xyz/twap"


def test_env_overrides_respected(monkeypatch):
    monkeypatch.setenv("VERANTA_API_BASE_URL", "https://env-base.test")
    monkeypatch.setenv("VERANTA_TWAP_API_URL", "https://env-twap.test")
    cfg = VerantaConfig.load(network="testnet")
    assert cfg.twap_api_url == "https://env-twap.test"
    assert cfg.core_api_url == "https://env-base.test/core"
    assert cfg.batched_market_url == "https://env-base.test/batched-market"


def test_no_rpc_by_default(monkeypatch):
    """No RPC in the default mix: delegate/API keys are fresh EOAs (nonce-0
    authorizations), so relayer mode is fully API-driven. rpc_url is an
    explicit opt-in for direct mode or trader-EOA signing."""
    monkeypatch.delenv("VERANTA_RPC_URL", raising=False)
    assert VerantaConfig.load(network="testnet").rpc_url is None
    assert VerantaConfig.load(network="mainnet").rpc_url is None
    monkeypatch.setenv("VERANTA_RPC_URL", "https://my-node.test")
    assert VerantaConfig.load(network="testnet").rpc_url == "https://my-node.test"
