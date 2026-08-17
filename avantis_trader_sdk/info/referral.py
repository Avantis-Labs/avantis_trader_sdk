"""Referral actions: codes, gasless registration, ownership transfer.

Referral contract calls are msg.sender-scoped (no delegatedAction wrapping),
so direct calldata requires signer == caller. Gasless variants use the
referral WithSig intents (signed by the referrer/referee themselves) wrapped
via the relayer passthrough.
"""

from __future__ import annotations

from eth_abi import encode as abi_encode
from eth_utils import keccak, to_bytes

from ..base_api import ExecutingApi
from ..errors import ConfigError
from ..types import CallData, ExecutionReceipt

_REGISTER_CODE_WITH_SIG = keccak(text="registerCodeWithSig(bytes,bytes)")[:4]
_SET_CODE_WITH_SIG = keccak(text="setTraderReferralCodeByUserWithSig(bytes,bytes)")[:4]


class ReferralApi(ExecutingApi):
    """client.referral: actions execute as the SDK's signing key."""

    @property
    def caller(self) -> str:
        signer = self._engine.signer
        if signer is None:
            raise ConfigError("Referral actions require a signing key.")
        return signer.address

    # ------------------------------------------------------------------ core actions

    async def register_code(self, code: str, *, wait: bool = True) -> ExecutionReceipt:
        """Register a referral code owned by the caller."""
        return await self._passthrough_or_direct(
            "/v2/referral/register-code", {"caller": self.caller, "code": code}, wait,
            delegatable=False,
        )

    async def set_code(self, code: str, *, wait: bool = True) -> ExecutionReceipt:
        """Attach the caller to someone else's referral code."""
        return await self._passthrough_or_direct(
            "/v2/referral/set-code", {"caller": self.caller, "code": code}, wait,
            delegatable=False,
        )

    async def register_code_gasless(self, code: str, *, wait: bool = True) -> ExecutionReceipt:
        """Sign a RegisterCodeReq intent and relay registerCodeWithSig."""
        intent = await self._txb.intent(
            "/v2/intents/referral-register-code", referrer=self.caller, code=code
        )
        return await self._with_sig(intent, _REGISTER_CODE_WITH_SIG, wait)

    async def set_code_gasless(self, code: str, *, wait: bool = True) -> ExecutionReceipt:
        """Sign a SetTraderReferralCodeByUserReq intent and relay it."""
        intent = await self._txb.intent(
            "/v2/intents/referral-set-code", referee=self.caller, code=code
        )
        return await self._with_sig(intent, _SET_CODE_WITH_SIG, wait)

    # ------------------------------------------------------------------ special / ownership

    async def request_special_code(self, code: str, *, wait: bool = True) -> ExecutionReceipt:
        return await self._passthrough_or_direct(
            "/v2/referral/request-special-code", {"caller": self.caller, "code": code}, wait,
            delegatable=False,
        )

    async def cancel_request(self, *, wait: bool = True) -> ExecutionReceipt:
        return await self._passthrough_or_direct(
            "/v2/referral/cancel-request", {"caller": self.caller}, wait, delegatable=False
        )

    async def relinquish_code(self, *, wait: bool = True) -> ExecutionReceipt:
        return await self._passthrough_or_direct(
            "/v2/referral/relinquish-code", {"caller": self.caller}, wait, delegatable=False
        )

    async def set_code_by_owner(
        self, code: str, trader: str, *, wait: bool = True
    ) -> ExecutionReceipt:
        """Approve a pending private-code request (code owner only)."""
        return await self._passthrough_or_direct(
            "/v2/referral/set-code-by-owner",
            {"caller": self.caller, "code": code, "trader": trader},
            wait,
            delegatable=False,
        )

    async def transfer_ownership(
        self, code: str, new_owner: str, *, wait: bool = True
    ) -> ExecutionReceipt:
        return await self._passthrough_or_direct(
            "/v2/referral/transfer-ownership",
            {"caller": self.caller, "code": code, "newOwner": new_owner},
            wait,
            delegatable=False,
        )

    async def accept_ownership(self, code: str, *, wait: bool = True) -> ExecutionReceipt:
        return await self._passthrough_or_direct(
            "/v2/referral/accept-ownership", {"caller": self.caller, "code": code}, wait,
            delegatable=False,
        )

    # ------------------------------------------------------------------ helpers

    async def _with_sig(self, intent, selector: bytes, wait: bool) -> ExecutionReceipt:
        from ..signing import sign_intent

        signer = self._engine.signer
        if signer is None:
            raise ConfigError("Gasless referral actions require a signing key.")
        signed = sign_intent(intent, signer)
        referral = intent.domain["verifyingContract"]
        data = selector + abi_encode(
            ["bytes", "bytes"],
            [to_bytes(hexstr=signed.signature), to_bytes(hexstr=intent.encoded_intent)],
        )
        calldata = CallData.model_validate(
            {
                "to": referral,
                "from": signer.address,
                "data": "0x" + data.hex(),
                "value": "0x0",
                "chainId": await self._engine.chain_id(),
                "description": f"{intent.intent} withSig",
            }
        )
        return await self._route(calldata, wait)
