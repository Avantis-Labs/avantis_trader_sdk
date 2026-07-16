"""Python port of the Gelato EIP-7702 smart-account encoding.

Replicates ``@gelatocloud/gasless`` ``toGelatoSmartAccount().encodeCallData``
(see avantis-ui-v2 node_modules) against the on-chain template
``avantis-contracts-v2/src/EIP7702Template/Eip7702Template.sol``:

1. Sign EIP-712 ``Execute(bytes32 mode,Call[] calls,uint256 nonce)`` /
   ``Call(address to,uint256 value,bytes data)`` under the domain
   ``{name: "GelatoDelegation", version: "0.0.1", chainId, verifyingContract: <signer EOA>}``.
2. ``opData = abi.encodePacked(uint192(nonce >> 64), signature)``.
3. ``executionData = abi.encode(Call[], bytes opData)`` (ERC-7821 op-data mode).
4. Calldata = ``execute(bytes32 mode, bytes executionData)`` sent **to the
   signer's own EOA** (whose code is delegated to the Gelato template).
5. An EIP-7702 authorization for the delegation template is attached to every
   relayed transaction (idempotent once the code is set).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from eth_abi import encode as abi_encode
from eth_utils import keccak, to_bytes, to_checksum_address

from ..signing.base import BaseSigner

# ERC-7821: callType=0x01 (batch), execType=0x00, selector=0x78210001 (op-data mode)
EXECUTION_MODE_OP_DATA = bytes.fromhex(
    "0100000000007821000100000000000000000000000000000000000000000000"
)

EXECUTE_SELECTOR = keccak(text="execute(bytes32,bytes)")[:4]

_EXECUTE_TYPES = {
    "Call": [
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "data", "type": "bytes"},
    ],
    "Execute": [
        {"name": "mode", "type": "bytes32"},
        {"name": "calls", "type": "Call[]"},
        {"name": "nonce", "type": "uint256"},
    ],
}

_EIP712_DOMAIN_FIELDS = [
    {"name": "name", "type": "string"},
    {"name": "version", "type": "string"},
    {"name": "chainId", "type": "uint256"},
    {"name": "verifyingContract", "type": "address"},
]


def encode_nonce(key: int, seq: int = 0) -> int:
    """ERC-7821 sequential nonce: ``(key << 64) | seq`` (key up to 192 bits)."""
    return (key << 64) | seq


def fresh_nonce(salt: int = 0) -> int:
    """Fresh nonce with a time-based key so the on-chain sequence for the key is 0.

    Mirrors the UI convention ``encodeNonce(Date.now()*1000 + i, 0)``.
    """
    return encode_nonce(int(time.time() * 1000) * 1000 + salt, 0)


@dataclass
class Call:
    to: str
    data: bytes
    value: int = 0

    @classmethod
    def from_hex(cls, to: str, data: str, value: int = 0) -> Call:
        return cls(to=to_checksum_address(to), data=to_bytes(hexstr=data), value=value)

    def as_tuple(self) -> tuple[str, int, bytes]:
        return (self.to, self.value, self.data)


@dataclass
class GelatoDelegationEncoder:
    """Builds relayer-ready type-4 payloads for one signing key."""

    signer: BaseSigner
    chain_id: int
    delegation_address: str
    builder_code: str | None = None  # optional 0x-hex calldata suffix
    _auth_cache: dict[int, dict[str, Any]] = field(default_factory=dict, repr=False)

    # -- core encoding --------------------------------------------------------

    def sign_execute(self, calls: list[Call], nonce: int) -> bytes:
        """Sign the ERC-7821 Execute digest; returns the 65-byte signature."""
        full_message = {
            "types": {"EIP712Domain": _EIP712_DOMAIN_FIELDS, **_EXECUTE_TYPES},
            "primaryType": "Execute",
            "domain": {
                "name": "GelatoDelegation",
                "version": "0.0.1",
                "chainId": self.chain_id,
                "verifyingContract": self.signer.address,
            },
            "message": {
                "mode": EXECUTION_MODE_OP_DATA,
                "calls": [{"to": c.to, "value": c.value, "data": c.data} for c in calls],
                "nonce": nonce,
            },
        }
        signature, _digest = self.signer.sign_typed_data(full_message)
        return signature

    def encode_call_data(self, calls: list[Call], nonce: int | None = None) -> bytes:
        """Full ``execute(mode, executionData)`` calldata with signed opData."""
        nonce = fresh_nonce() if nonce is None else nonce
        signature = self.sign_execute(calls, nonce)
        nonce_key = nonce >> 64
        op_data = nonce_key.to_bytes(24, "big") + signature  # abi.encodePacked(uint192, bytes)
        execution_data = abi_encode(
            ["(address,uint256,bytes)[]", "bytes"],
            [[c.as_tuple() for c in calls], op_data],
        )
        data = EXECUTE_SELECTOR + abi_encode(["bytes32", "bytes"], [EXECUTION_MODE_OP_DATA, execution_data])
        if self.builder_code:
            data += to_bytes(hexstr=self.builder_code)
        return data

    # -- authorization ---------------------------------------------------------

    def authorization(self, account_nonce: int) -> dict[str, Any]:
        """EIP-7702 set-code authorization for the Gelato delegation template."""
        if account_nonce not in self._auth_cache:
            self._auth_cache[account_nonce] = self.signer.sign_authorization(
                self.chain_id, self.delegation_address, account_nonce
            )
        return self._auth_cache[account_nonce]

    # -- relayer payload -------------------------------------------------------

    def build_type4(
        self,
        calls: list[Call],
        *,
        gas: int,
        account_nonce: int = 0,
        exec_nonce: int | None = None,
        include_authorization: bool = True,
        value: int = 0,
    ) -> dict[str, Any]:
        """Blitz-relayer ``txParams`` for a type-4 (EIP-7702) relay.

        Shape mirrors avantis-backend-monorepo blitz-relayer-app
        ``TxParamsDto`` / ``AuthorizationDto`` (numeric chainId/nonce; v and
        yParity both provided for ethers signature reconstruction).
        """
        data = self.encode_call_data(calls, exec_nonce)
        auth_list = []
        if include_authorization:
            auth = self.authorization(account_nonce)
            auth_list.append(
                {
                    "address": auth["address"],
                    "chainId": auth["chainId"],
                    "nonce": auth["nonce"],
                    "r": auth["r"],
                    "s": auth["s"],
                    "yParity": auth["yParity"],
                    "v": auth["yParity"] + 27,
                }
            )
        return {
            "to": self.signer.address,
            "data": "0x" + data.hex(),
            "value": str(value),
            "gasLimit": str(gas),
            "chainId": self.chain_id,
            "transactionType": 4,
            "authorizationList": auth_list,
        }


def delegation_code(delegation_address: str) -> str:
    """Expected EOA code once the EIP-7702 delegation is applied (0xef0100 ++ addr)."""
    return "0xef0100" + delegation_address.lower().removeprefix("0x")
