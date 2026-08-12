"""SDK configuration: constructor args > environment variables > network profile.

Environment variables:

- ``AVANTIS_PRIVATE_KEY``    the signing key (delegate/agent key or trader key)
- ``AVANTIS_TRADER_ADDRESS`` if set and != key's address -> delegate mode
- ``AVANTIS_EXECUTION``      "relayer" (default) | "direct"
- ``AVANTIS_RPC_URL``        Base RPC. Required for execution=direct
                             (broadcast) and for relayer mode when signing
                             with the trader EOA directly (reads the EIP-7702
                             authorization nonce). Not needed with a
                             delegate/API key — the normal setup.
- ``AVANTIS_NETWORK``        "mainnet" (default) | "testnet"
- ``AVANTIS_API_BASE_URL``   central-routing host (prod-api / staging-api);
                             /core, /twap, /batched-market, /blitz, /data and
                             /risk/v2 are derived from it unless individually
                             overridden
- ``AVANTIS_TX_BUILDER_URL`` / ``AVANTIS_RELAYER_URL`` / ``AVANTIS_DATA_API_URL``
  / ``AVANTIS_CORE_API_URL`` / ``AVANTIS_TWAP_API_URL``
  / ``AVANTIS_BATCHED_MARKET_URL`` / ``AVANTIS_HISTORY_API_URL``
  / ``AVANTIS_RISK_API_URL`` / ``AVANTIS_RISK_V2_API_URL``
  / ``AVANTIS_FEED_URL``   per-service overrides
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields

from .errors import ConfigError
from .types import ExecutionMode

# Gelato EIP-7702 delegation template (same on Base mainnet and the internal
# testnet fork; from @gelatocloud/gasless constants).
DEFAULT_DELEGATION_ADDRESS = "0x5aF42746a8Af42d8a4708dF238C53F1F71abF0E0"


@dataclass(frozen=True)
class NetworkProfile:
    name: str
    api_base_url: str
    tx_builder_url: str
    history_api_url: str
    # LEGACY risk-engine (dynamic_spread) — standalone host. Testnet-only
    # since the 2026-08-12 cutover; empty = not deployed on that network.
    risk_api_url: str
    feed_url: str
    # Centrally-routed services (avantis-cd services/infra-http-routes):
    # derived from api_base_url when left empty.
    relayer_url: str = ""  # blitz relayer      -> {api_base_url}/blitz
    core_api_url: str = ""  # core backend      -> {api_base_url}/core
    twap_api_url: str = ""  # twap-app          -> {api_base_url}/twap
    batched_market_url: str = ""  # batched-market-api -> {api_base_url}/batched-market
    data_api_url: str = ""  # data-service-api  -> {api_base_url}/data
    # risk-engine v2 (spread-module): POST /spread + GET /orderbook/snapshots.
    risk_v2_api_url: str = ""  # risk-engine-v2-api -> {api_base_url}/risk/v2
    hermes_ws_url: str = "wss://hermes.pyth.network/ws"
    pusher_key: str | None = None
    pusher_cluster: str = "us2"


# Central-routing path prefixes (HTTPRoute `central-routes` on the public
# envoy gateway; rules rewrite the prefix to "/" before the backend). The
# gateway also routes /ws (iris websocket app), which the SDK does not
# consume.
_CENTRAL_ROUTES = {
    "core_api_url": "/core",
    "twap_api_url": "/twap",
    "batched_market_url": "/batched-market",
    "relayer_url": "/blitz",
    "data_api_url": "/data",
    "risk_v2_api_url": "/risk/v2",
}

TESTNET = NetworkProfile(
    name="testnet",
    # tenderly-testnet namespace (the v2 stack); testnet-public uses
    # staging-public-api.avantisfi.com instead.
    api_base_url="https://staging-api.avantisfi.com",
    tx_builder_url="https://tx-builder-testnet.avantisfi.com",
    history_api_url="https://testnet-api.avantisfi.com",
    # risk-api-testnet.avantisfi.com is cluster-internal; -public is the
    # reachable ingress (avantis-cd/services/risk-engine/testnet-public).
    risk_api_url="https://risk-api-testnet-public.avantisfi.com",
    # Testnet feed app (feed-v3, tenderly-testnet namespace). Its signed price
    # updates are the ones the fork's price aggregator verifies — messages
    # from the mainnet feed (feed-v3.avantisfi.com) revert on-chain there.
    feed_url="https://feed-v3-testnet.avantisfi.com",
    pusher_key="f86bc7e9919fc938694a",
    pusher_cluster="mt1",
)

MAINNET = NetworkProfile(
    name="mainnet",
    api_base_url="https://prod-api.avantisfi.com",
    tx_builder_url="https://tx-builder.avantisfi.com",
    history_api_url="https://api.avantisfi.com",
    # Production spreads come from the v2 engine at {api_base_url}/risk/v2
    # (markets.spread()). The legacy engine was decommissioned at the
    # 2026-08-12 cutover — risk-api.avantisfi.com is scaled to zero (503) —
    # so markets.dynamic_spread() raises on mainnet.
    risk_api_url="",
    feed_url="https://feed-v3.avantisfi.com",
)

PROFILES = {"testnet": TESTNET, "mainnet": MAINNET}

_ENV_URL_OVERRIDES = {
    "api_base_url": "AVANTIS_API_BASE_URL",
    "tx_builder_url": "AVANTIS_TX_BUILDER_URL",
    "relayer_url": "AVANTIS_RELAYER_URL",
    "data_api_url": "AVANTIS_DATA_API_URL",
    "core_api_url": "AVANTIS_CORE_API_URL",
    "twap_api_url": "AVANTIS_TWAP_API_URL",
    "batched_market_url": "AVANTIS_BATCHED_MARKET_URL",
    "history_api_url": "AVANTIS_HISTORY_API_URL",
    "risk_api_url": "AVANTIS_RISK_API_URL",
    "risk_v2_api_url": "AVANTIS_RISK_V2_API_URL",
    "feed_url": "AVANTIS_FEED_URL",
}


@dataclass
class AvantisConfig:
    """Resolved SDK configuration."""

    # identity / execution
    private_key: str | None = None
    trader_address: str | None = None
    execution: ExecutionMode = ExecutionMode.RELAYER
    # Base RPC. Broadcast path in direct mode; in relayer mode used only to
    # read the EIP-7702 authorization nonce, which is required when signing
    # with the trader EOA directly (delegate/API keys are fresh EOAs and
    # need no RPC at all).
    rpc_url: str | None = None

    # service endpoints
    network: str = "mainnet"
    api_base_url: str = ""
    tx_builder_url: str = ""
    relayer_url: str = ""
    data_api_url: str = ""
    core_api_url: str = ""
    twap_api_url: str = ""
    batched_market_url: str = ""
    history_api_url: str = ""
    risk_api_url: str = ""
    risk_v2_api_url: str = ""
    feed_url: str = ""
    hermes_ws_url: str = ""
    pusher_key: str | None = None
    pusher_cluster: str = "us2"

    # EIP-7702 / relayer plumbing
    delegation_address: str = DEFAULT_DELEGATION_ADDRESS
    builder_code: str | None = None  # optional 0x-hex 32-byte calldata suffix
    # Fallback when no RPC is available to estimate (the normal relayer setup).
    # updateMargin burns >1M gas (oracle fulfill + full position accounting;
    # the backend budgets 2M for the same call class), and the blitz relayer
    # caps relays at 3M.
    default_gas_limit: int = 2_000_000

    # behavior
    timeout_s: float = 30.0
    relay_poll_interval_s: float = 1.0
    relay_poll_timeout_s: float = 60.0

    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls, **overrides) -> AvantisConfig:
        """Build config from env + network profile, applying explicit overrides last."""
        network = str(overrides.get("network") or os.getenv("AVANTIS_NETWORK", "mainnet"))
        profile = PROFILES.get(network)
        if profile is None:
            raise ConfigError(f"Unknown AVANTIS_NETWORK {network!r}; use one of {list(PROFILES)}")

        cfg = cls(network=network)
        # profile defaults
        for f in fields(NetworkProfile):
            if f.name == "name":
                continue
            setattr(cfg, f.name, getattr(profile, f.name))
        # env URL overrides
        for attr, env in _ENV_URL_OVERRIDES.items():
            if os.getenv(env):
                setattr(cfg, attr, os.environ[env])
        # env identity/execution
        cfg.private_key = os.getenv("AVANTIS_PRIVATE_KEY") or None
        cfg.trader_address = os.getenv("AVANTIS_TRADER_ADDRESS") or None
        cfg.rpc_url = os.getenv("AVANTIS_RPC_URL") or None
        exec_env = os.getenv("AVANTIS_EXECUTION")
        if exec_env:
            cfg.execution = ExecutionMode(exec_env.lower())

        # explicit overrides win
        valid = {f.name for f in fields(cls)}
        for key, value in overrides.items():
            if value is None:
                continue
            if key not in valid:
                raise ConfigError(f"Unknown config option {key!r}")
            if key == "execution" and not isinstance(value, ExecutionMode):
                value = ExecutionMode(str(value).lower())
            setattr(cfg, key, value)

        # Central-routing derivation: any routed service left unset resolves
        # to {api_base_url}{prefix}. Explicit env/constructor values win.
        base = cfg.api_base_url.rstrip("/")
        for attr, prefix in _CENTRAL_ROUTES.items():
            if not getattr(cfg, attr) and base:
                setattr(cfg, attr, f"{base}{prefix}")
        return cfg

    def validate_for_signing(self) -> None:
        if not self.private_key:
            raise ConfigError(
                "No signing key configured. Set AVANTIS_PRIVATE_KEY or pass private_key=..."
            )
