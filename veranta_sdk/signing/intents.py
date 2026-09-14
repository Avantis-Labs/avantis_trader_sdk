"""EIP-712 intent signing with a mandatory digest correctness gate.

The tx-builder API returns ``types`` without the ``EIP712Domain`` type
(viem/MetaMask convention) and all uint/int values as decimal strings. This
module adds the domain type, converts values, signs, and asserts that the
locally computed digest equals the API-provided ``digest``. A mismatch is a
hard error (encoding drift) and the intent must never be submitted.
"""

from __future__ import annotations

from typing import Any

from ..errors import DigestMismatchError
from ..types import IntentPayload, SignedIntent
from .base import BaseSigner

_EIP712_DOMAIN_FIELDS = [
    {"name": "name", "type": "string"},
    {"name": "version", "type": "string"},
    {"name": "chainId", "type": "uint256"},
    {"name": "verifyingContract", "type": "address"},
]

_INT_TYPES = {"uint256", "int256", "uint8", "uint192", "uint64"}


def to_int_message(
    types: dict[str, list[dict[str, str]]], type_name: str, message: dict[str, Any]
) -> dict[str, Any]:
    """Convert the API's decimal-string values to ints, recursively, driven by types."""
    fields = {f["name"]: f["type"] for f in types[type_name]}
    out: dict[str, Any] = {}
    for name, value in message.items():
        t = fields[name]
        if t in _INT_TYPES:
            out[name] = int(value)
        elif t in types:  # nested struct (Trade, UpdatePositionSize)
            out[name] = to_int_message(types, t, value)
        else:  # address, bool, string, bytes32
            out[name] = value
    return out


def sign_intent(payload: IntentPayload, signer: BaseSigner) -> SignedIntent:
    """Sign an intent payload and verify the digest before returning.

    Raises DigestMismatchError if the locally computed EIP-712 hash differs
    from the API's ``digest`` field.
    """
    full_message = {
        "types": {"EIP712Domain": _EIP712_DOMAIN_FIELDS, **payload.types},
        "primaryType": payload.primary_type,
        "domain": payload.domain,
        "message": to_int_message(payload.types, payload.primary_type, payload.message),
    }
    signature, message_hash = signer.sign_typed_data(full_message)

    local_digest = "0x" + message_hash.hex()
    if local_digest.lower() != payload.digest.lower():
        raise DigestMismatchError(
            f"EIP-712 digest mismatch for {payload.intent}: "
            f"local {local_digest} != api {payload.digest}. "
            "Do NOT submit; investigate encoding drift."
        )
    return SignedIntent(
        payload=payload, signature="0x" + signature.hex(), signer=signer.address
    )
