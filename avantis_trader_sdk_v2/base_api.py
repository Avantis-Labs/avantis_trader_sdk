"""Shared base for namespaces that execute transactions."""

from __future__ import annotations

from typing import Any

from .config import AvantisConfig
from .errors import ConfigError
from .execution import ExecutionEngine
from .transport import HttpTransport
from .txbuilder import TxBuilderClient
from .types import CallData, ExecutionReceipt


class ExecutingApi:
    def __init__(
        self,
        config: AvantisConfig,
        engine: ExecutionEngine,
        txb: TxBuilderClient,
        transport: HttpTransport | None = None,
    ) -> None:
        self._cfg = config
        self._engine = engine
        self._txb = txb
        self._t = transport

    @property
    def trader(self) -> str:
        """The trader address whose account is being operated."""
        if self._cfg.trader_address:
            return self._cfg.trader_address
        if self._engine.signer is not None:
            return self._engine.signer.address
        raise ConfigError("No trader address: set AVANTIS_TRADER_ADDRESS or a signing key.")

    @property
    def _delegate_param(self) -> str | None:
        """Delegate address for calldata wrapping, when signer != trader."""
        signer = self._engine.signer
        if (
            signer is not None
            and self._cfg.trader_address
            and signer.address.lower() != self._cfg.trader_address.lower()
        ):
            return signer.address
        return None

    async def _calldata(
        self, path: str, params: dict[str, Any], *, delegatable: bool = True
    ) -> CallData:
        """Fetch direct-route calldata, delegate-wrapped when signer != trader."""
        cd_params = dict(params)
        delegate = self._delegate_param
        if delegate and delegatable:
            cd_params["delegate"] = delegate
        return await self._txb.calldata(path, **cd_params)

    async def _route(self, calldata: CallData, wait: bool) -> ExecutionReceipt:
        if self._engine.is_relayer_mode:
            return await self._engine.submit_passthrough(calldata, wait=wait)
        return await self._engine.submit_direct(calldata, wait=wait)

    async def _passthrough_or_direct(
        self, path: str, params: dict[str, Any], wait: bool, *, delegatable: bool = True
    ) -> ExecutionReceipt:
        if not delegatable:
            self._require_caller_is_signer(path)
        calldata = await self._calldata(path, params, delegatable=delegatable)
        return await self._route(calldata, wait)

    def _require_caller_is_signer(self, what: str) -> None:
        """Guard for calls where msg.sender identity matters (referral, approve,
        claims): they cannot be executed by a delegate on the trader's behalf."""
        if self._delegate_param is not None:
            raise ConfigError(
                f"{what} executes as the caller's own address and cannot be routed "
                "through a delegate key. Run it with the trader key (or on the Avantis UI)."
            )
