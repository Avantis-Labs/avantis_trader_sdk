"""SDK configuration: constructor args > environment variables > network profile.

Environment variables (HyperLiquid-style semantics):

- ``AVANTIS_PRIVATE_KEY``    the signing key (delegate/agent key or trader key)
- ``AVANTIS_TRADER_ADDRESS`` if set and != key's address -> delegate mode
- ``AVANTIS_EXECUTION``      "relayer" (default) | "direct"
- ``AVANTIS_RPC_URL``        write RPC; required broadcast path only when
                             execution=direct and you want self-broadcast
- ``AVANTIS_NETWORK``        "testnet" (default) | "mainnet"
- ``AVANTIS_TX_BUILDER_URL`` / ``AVANTIS_RELAYER_URL`` / ``AVANTIS_DATA_API_URL``
  / ``AVANTIS_CORE_API_URL`` / ``AVANTIS_HISTORY_API_URL`` / ``AVANTIS_RISK_API_URL``
  / ``AVANTIS_FEED_URL``     per-service overrides
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
    tx_builder_url: str
    relayer_url: str
    data_api_url: str
    core_api_url: str
    history_api_url: str
    risk_api_url: str
    feed_url: str
    hermes_ws_url: str = "wss://hermes.pyth.network/ws"
    pusher_key: str | None = None
    pusher_cluster: str = "us2"


TESTNET = NetworkProfile(
    name="testnet",
    tx_builder_url="https://tx-builder.avantisfi.com",
    relayer_url="https://relayer-testnet.avantisfi.com",
    data_api_url="https://testnet-data.avantisfi.com",
    core_api_url="https://core-testnet.avantisfi.com",
    history_api_url="https://testnet-api.avantisfi.com",
    risk_api_url="https://risk-api-testnet.avantisfi.com",
    feed_url="https://feed-v3.avantisfi.com",
)

MAINNET = NetworkProfile(
    name="mainnet",
    tx_builder_url="https://tx-builder.avantisfi.com",
    relayer_url="https://relayer.avantisfi.com",
    data_api_url="https://data.avantisfi.com",
    core_api_url="https://core.avantisfi.com",
    history_api_url="https://api.avantisfi.com",
    risk_api_url="https://risk-api.avantisfi.com",
    feed_url="https://feed-v3.avantisfi.com",
)

PROFILES = {"testnet": TESTNET, "mainnet": MAINNET}

_ENV_URL_OVERRIDES = {
    "tx_builder_url": "AVANTIS_TX_BUILDER_URL",
    "relayer_url": "AVANTIS_RELAYER_URL",
    "data_api_url": "AVANTIS_DATA_API_URL",
    "core_api_url": "AVANTIS_CORE_API_URL",
    "history_api_url": "AVANTIS_HISTORY_API_URL",
    "risk_api_url": "AVANTIS_RISK_API_URL",
    "feed_url": "AVANTIS_FEED_URL",
}


@dataclass
class AvantisConfig:
    """Resolved SDK configuration."""

    # identity / execution
    private_key: str | None = None
    trader_address: str | None = None
    execution: ExecutionMode = ExecutionMode.RELAYER
    rpc_url: str | None = None

    # service endpoints
    network: str = "testnet"
    tx_builder_url: str = ""
    relayer_url: str = ""
    data_api_url: str = ""
    core_api_url: str = ""
    history_api_url: str = ""
    risk_api_url: str = ""
    feed_url: str = ""
    hermes_ws_url: str = ""
    pusher_key: str | None = None
    pusher_cluster: str = "us2"

    # EIP-7702 / relayer plumbing
    delegation_address: str = DEFAULT_DELEGATION_ADDRESS
    builder_code: str | None = None  # optional 0x-hex 32-byte calldata suffix
    default_gas_limit: int = 1_000_000

    # behavior
    timeout_s: float = 30.0
    relay_poll_interval_s: float = 1.0
    relay_poll_timeout_s: float = 60.0

    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls, **overrides) -> AvantisConfig:
        """Build config from env + network profile, applying explicit overrides last."""
        network = str(overrides.get("network") or os.getenv("AVANTIS_NETWORK", "testnet"))
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
        return cfg

    def validate_for_signing(self) -> None:
        if not self.private_key:
            raise ConfigError(
                "No signing key configured. Set AVANTIS_PRIVATE_KEY or pass private_key=..."
            )
