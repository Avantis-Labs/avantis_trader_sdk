"""Account state: positions, orders, balances, allowance, delegation, onboarding."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any

from eth_abi import encode as abi_encode
from eth_utils import keccak, to_bytes

from ..base_api import ExecutingApi
from ..config import AvantisConfig
from ..errors import ConfigError, DelegationError
from ..execution import ExecutionEngine
from ..markets.models import PairInfo
from ..signing import BaseSigner, sign_intent
from ..transport import HttpTransport
from ..txbuilder import TxBuilderClient
from ..types import CallData, ExecutionReceipt, Num
from .models import UserData

_SET_DELEGATE_WITH_SIG_SELECTOR = keccak(text="setDelegateWithSig(bytes,bytes)")[:4]


class AccountApi(ExecutingApi):
    def __init__(
        self,
        config: AvantisConfig,
        engine: ExecutionEngine,
        txb: TxBuilderClient,
        transport: HttpTransport,
        get_meta: Callable[[], Awaitable[dict[str, Any]]],
        get_pairs: Callable[[], Awaitable[dict[int, PairInfo]]],
    ) -> None:
        super().__init__(config, engine, txb, transport)
        self._get_meta = get_meta
        self._get_pairs = get_pairs

    # ------------------------------------------------------------------ reads

    async def positions(self, trader: str | None = None) -> UserData:
        """Open positions + standing limit orders (core API, enriched with
        liquidation price, rollover, and unrealized funding).

        Each position also gets ``base_symbol`` from the markets pair catalog
        so ``Position.size_in_asset`` handles USD-base pairs (USD/JPY, ...)
        correctly.
        """
        addr = trader or self.trader
        assert self._t is not None
        data = await self._t.json(
            "GET", f"{self._cfg.core_api_url}/user-data", params={"trader": addr}
        )
        user_data = UserData.model_validate(data)
        if user_data.positions:
            pairs = await self._get_pairs()
            for pos in user_data.positions:
                info = pairs.get(pos.pair_index)
                if info is not None:
                    pos.base_symbol = info.from_symbol
        return user_data

    async def positions_onchain(self, trader: str | None = None) -> dict[str, Any]:
        """Positions via the tx-builder RPC read (raw bigint strings)."""
        return await self._txb.positions(trader or self.trader)

    async def twaps(
        self,
        trader: str | None = None,
        *,
        include_canceled: bool = False,
        page: int = 0,
        page_size: int = 20,
    ) -> Any:
        """TWAP orders with their per-slice trades (twap-app API; ``page`` is
        0-based)."""
        assert self._t is not None
        return await self._t.json(
            "GET",
            f"{self._cfg.twap_api_url}/twaps",
            params={
                "trader": trader or self.trader,
                "includeCanceled": str(include_canceled).lower(),
                "pageNum": page,
                "pageSize": page_size,
            },
        )

    async def allowance(self, spender: str | None = None) -> dict[str, Any]:
        """USDC allowance + balance (spender defaults to TradingStorage)."""
        return await self._txb.allowance(self.trader, spender)

    async def usdc_balance(self) -> Decimal:
        """USDC wallet balance in human units.

        tx-builder /v2/allowance returns both raw strings (`balance`,
        `allowance`) and human floats (`balanceUsdc`, `allowanceUsdc`);
        prefer the exact raw value.
        """
        data = await self.allowance()
        return Decimal(str(data.get("balance", "0"))) / Decimal(10**6)

    async def delegation_status(self, delegate: str | None = None) -> dict[str, Any]:
        """{isEnabled, expiry, canDelegatedAction, canSignIntents}."""
        d = delegate or (self._engine.signer.address if self._engine.signer else None)
        if d is None:
            raise ConfigError("No delegate address to check.")
        return await self._txb.delegation(self.trader, d)

    async def verify_delegation(self) -> None:
        """Fail fast if the configured delegate cannot act for the trader."""
        signer = self._engine.signer
        if signer is None or not self._cfg.trader_address:
            return
        if signer.address.lower() == self._cfg.trader_address.lower():
            return
        status = await self.delegation_status(signer.address)
        ok = (
            status.get("canSignIntents")
            if self._engine.is_relayer_mode
            else status.get("canDelegatedAction")
        )
        if not ok:
            raise DelegationError(
                f"Delegate {signer.address} is not authorized for trader "
                f"{self._cfg.trader_address} (status: {status}). Register the delegate "
                "on the Avantis UI or via register_delegate()."
            )

    # ------------------------------------------------------------------ onboarding

    async def approve_usdc(
        self,
        amount: Num | None = None,
        *,
        spender: str | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Approve USDC for trading (TradingStorage) or LP (pass the tranche).

        The approval must come from the TRADER's own address — it cannot be
        routed through a delegate key.
        """
        self._require_caller_is_signer("USDC approve")
        calldata = await self._txb.calldata(
            "/v2/token/approve",
            trader=self.trader,
            spender=spender,
            amountUsdc=amount,
        )
        return await self._route(calldata, wait)

    async def register_delegate(
        self,
        delegate: str,
        expiry_seconds: int,
        trader_signer: BaseSigner,
        *,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Register a delegate gaslessly (trader signs a DelegateReq intent).

        ``expiry_seconds`` is an ABSOLUTE unix timestamp in seconds (e.g.
        ``int(time.time()) + 3600`` for one hour), not a duration.

        The trader key is used transiently for one signature and not stored.
        submission of setDelegateWithSig is permissionless, so the SDK's own
        key relays it (TX_RELAY passthrough in relayer mode).
        """
        intent = await self._txb.intent(
            "/v2/intents/delegate-set",
            trader=self.trader,
            delegate=delegate,
            expirySeconds=expiry_seconds,
        )
        signed = sign_intent(intent, trader_signer)  # trader-only signer rule
        meta = await self._get_meta()
        router = meta["addresses"]["tradingRouter"]
        data = _SET_DELEGATE_WITH_SIG_SELECTOR + abi_encode(
            ["bytes", "bytes"],
            [to_bytes(hexstr=signed.signature), to_bytes(hexstr=intent.encoded_intent)],
        )
        calldata = CallData.model_validate(
            {
                "to": router,
                "from": self._engine.signer.address if self._engine.signer else self.trader,
                "data": "0x" + data.hex(),
                "value": "0x0",
                "chainId": await self._engine.chain_id(),
                "description": f"setDelegateWithSig({delegate})",
            }
        )
        return await self._route(calldata, wait)

    async def revoke_delegate(self, delegate: str, *, wait: bool = True) -> ExecutionReceipt:
        """Remove a delegate (trader-signed; kills in-flight intents)."""
        self._require_caller_is_signer("removeDelegate")
        calldata = await self._txb.calldata(
            "/v2/delegate/remove", trader=self.trader, delegate=delegate
        )
        return await self._route(calldata, wait)

    # ------------------------------------------------------------------ claims / misc

    async def claim_rebate(self, *, wait: bool = True) -> ExecutionReceipt:
        """Claim accumulated referral rebates (caller must be the referrer)."""
        return await self._passthrough_or_direct(
            "/v2/referral/claim-rebate", {"caller": self.trader}, wait, delegatable=False
        )

    async def claim_keeper_rewards(self, *, wait: bool = True) -> ExecutionReceipt:
        return await self._passthrough_or_direct(
            "/v2/misc/claim-keeper-rewards", {"caller": self.trader}, wait, delegatable=False
        )

    async def add_to_buffer(self, amount: Num, *, wait: bool = True) -> ExecutionReceipt:
        """PROTOCOL-INTERNAL: USDC injection into the protocol buffer
        (VaultManager). Not part of the public trading surface — intentionally
        undocumented; regular users should never need this.

        Needs a prior USDC approval to the VaultManager address
        (``approve_usdc(amount, spender=meta["addresses"]["vaultManager"])``).
        """
        return await self._passthrough_or_direct(
            "/v2/misc/add-to-buffer",
            {"caller": self.trader, "amountUsdc": amount},
            wait,
            delegatable=False,
        )

    # ------------------------------------------------------------------ builder codes

    async def register_builder_code(
        self,
        code: str,
        *,
        fee_collector: str,
        is_percent_fee: bool = True,
        fee_percent: Num | None = None,
        fixed_fee_usdc: Num | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        """Register a builder code (partner fee registry; feePercent 1 = 1%)."""
        return await self._passthrough_or_direct(
            "/v2/misc/builder-code/register",
            {
                "caller": self.trader,
                "code": code,
                "isPercentFee": is_percent_fee,
                "feePercent": fee_percent,
                "fixedFeeUsdc": fixed_fee_usdc,
                "feeCollector": fee_collector,
            },
            wait,
            delegatable=False,
        )

    async def modify_builder_code(
        self,
        code: str,
        *,
        fee_collector: str,
        is_percent_fee: bool = True,
        fee_percent: Num | None = None,
        fixed_fee_usdc: Num | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        return await self._passthrough_or_direct(
            "/v2/misc/builder-code/modify",
            {
                "caller": self.trader,
                "code": code,
                "isPercentFee": is_percent_fee,
                "feePercent": fee_percent,
                "fixedFeeUsdc": fixed_fee_usdc,
                "feeCollector": fee_collector,
            },
            wait,
            delegatable=False,
        )
