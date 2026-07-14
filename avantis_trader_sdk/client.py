"""Avantis v2 client.

Default experience (HyperLiquid-style):

    from avantis_trader_sdk import AsyncAvantis

    client = AsyncAvantis()          # reads AVANTIS_* env vars
    await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)

A synchronous facade is available as ``Avantis`` for scripts.
"""

from __future__ import annotations

import asyncio
import threading
from functools import cached_property
from typing import Any

from .config import AvantisConfig
from .execution import ExecutionEngine
from .signing import BaseSigner, LocalSigner
from .transport import HttpTransport
from .txbuilder import TxBuilderClient
from .types import ExecutionMode


class AsyncAvantis:
    """Async-first Avantis v2 client."""

    def __init__(self, signer: BaseSigner | None = None, **config_overrides: Any) -> None:
        self.config = AvantisConfig.load(**config_overrides)
        if signer is None and self.config.private_key:
            signer = LocalSigner(self.config.private_key)
        self.signer = signer

        self.transport = HttpTransport(timeout_s=self.config.timeout_s)
        self.txb = TxBuilderClient(self.transport, self.config.tx_builder_url)
        self.engine = ExecutionEngine(self.config, self.signer, self.transport, self.txb)

        self._meta: dict[str, Any] | None = None
        self._meta_lock = asyncio.Lock()

    # ------------------------------------------------------------------ bootstrap

    async def meta(self) -> dict[str, Any]:
        """Cached /v2/meta bootstrap (addresses, domains, enums, units, defaults)."""
        if self._meta is None:
            async with self._meta_lock:
                if self._meta is None:
                    self._meta = await self.txb.meta()
        return self._meta

    async def chain_id(self) -> int:
        return int((await self.meta())["chainId"])

    # ------------------------------------------------------------------ namespaces

    @cached_property
    def trade(self):
        from .trading import TradeApi

        return TradeApi(self.config, self.engine, self.txb, self.transport)

    @cached_property
    def account(self):
        from .account import AccountApi

        return AccountApi(self.config, self.engine, self.txb, self.transport, self.meta)

    @cached_property
    def markets(self):
        from .markets import MarketsApi

        return MarketsApi(self.config, self.transport)

    @cached_property
    def info(self):
        from .info import InfoApi

        return InfoApi(self.config, self.transport)

    @cached_property
    def referral(self):
        from .info.referral import ReferralApi

        return ReferralApi(self.config, self.engine, self.txb, self.transport)

    @cached_property
    def lp(self):
        from .info.lp import LpApi

        return LpApi(self.config, self.engine, self.txb, self.transport)

    # ------------------------------------------------------------------ streams

    def lazer_price_stream(self, lazer_feed_ids: list[int]):
        """SSE price stream (feed-v3 / Pyth Lazer). Feed ids from pair snapshot
        ``lazer_feed.feed_id``."""
        from .streams import LazerPriceStream

        return LazerPriceStream(self.config.feed_url, lazer_feed_ids)

    def hermes_price_stream(self, pyth_feed_ids: list[str]):
        """Pyth Hermes WebSocket stream (0x-hex feed ids from ``feed.feed_id``)."""
        from .streams import HermesPriceStream

        return HermesPriceStream(self.config.hermes_ws_url, pyth_feed_ids)

    def pair_data_stream(self):
        """Socket.IO RES:DATA pair/OI/funding snapshot stream."""
        from .streams import PairDataStream

        return PairDataStream(self.config.data_api_url)

    def order_event_stream(self, trader: str | None = None):
        """Pusher order-execution events for a trader (needs pusher_key config)."""
        from .errors import ConfigError
        from .streams import OrderEventStream

        if not self.config.pusher_key:
            raise ConfigError("order_event_stream requires pusher_key in config")
        addr = trader or self.config.trader_address
        if addr is None and self.signer is not None:
            addr = self.signer.address
        if addr is None:
            raise ConfigError("order_event_stream requires a trader address")
        return OrderEventStream(
            self.config.pusher_key, addr, cluster=self.config.pusher_cluster
        )

    # ------------------------------------------------------------------ MM fast path

    async def local_intents(self):
        """Local intent builder (no per-order HTTP round-trips). See
        execution/local_intents.py; combine with sign_intent + the relayer."""
        from .execution.local_intents import LocalIntentBuilder

        return LocalIntentBuilder.from_meta(await self.meta())

    # ------------------------------------------------------------------ lifecycle

    async def aclose(self) -> None:
        await self.engine.aclose()
        await self.transport.aclose()

    async def __aenter__(self) -> AsyncAvantis:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()


class Avantis:
    """Synchronous facade over AsyncAvantis (runs a private event loop thread)."""

    def __init__(self, signer: BaseSigner | None = None, **config_overrides: Any) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._async = self._run(self._create(signer, config_overrides))

    @staticmethod
    async def _create(signer: BaseSigner | None, overrides: dict[str, Any]) -> AsyncAvantis:
        return AsyncAvantis(signer=signer, **overrides)

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    # namespace proxies -------------------------------------------------------

    @property
    def config(self) -> AvantisConfig:
        return self._async.config

    @property
    def trade(self):
        return _SyncProxy(self, self._async.trade)

    @property
    def account(self):
        return _SyncProxy(self, self._async.account)

    @property
    def markets(self):
        return _SyncProxy(self, self._async.markets)

    @property
    def info(self):
        return _SyncProxy(self, self._async.info)

    @property
    def referral(self):
        return _SyncProxy(self, self._async.referral)

    @property
    def lp(self):
        return _SyncProxy(self, self._async.lp)

    def meta(self) -> dict[str, Any]:
        return self._run(self._async.meta())

    def close(self) -> None:
        self._run(self._async.aclose())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)


class _SyncProxy:
    def __init__(self, sync_client: Avantis, target: Any) -> None:
        self._sync = sync_client
        self._target = target

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._target, name)
        if callable(attr):

            def call(*args: Any, **kwargs: Any) -> Any:
                result = attr(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return self._sync._run(result)
                return result

            return call
        return attr


# re-export for convenience
__all__ = ["AsyncAvantis", "Avantis", "ExecutionMode"]
