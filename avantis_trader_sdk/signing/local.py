"""Local private-key signer backed by eth-account."""

from __future__ import annotations

from typing import Any

from eth_account import Account
from eth_account.messages import encode_typed_data

from .base import BaseSigner


class LocalSigner(BaseSigner):
    def __init__(self, private_key: str) -> None:
        self._account = Account.from_key(private_key)

    @property
    def address(self) -> str:
        return self._account.address

    def sign_typed_data(self, full_message: dict[str, Any]) -> tuple[bytes, bytes]:
        signable = encode_typed_data(full_message=full_message)
        signed = self._account.sign_message(signable)
        return bytes(signed.signature), bytes(signed.message_hash)

    def sign_transaction(self, tx: dict[str, Any]) -> tuple[bytes, str]:
        signed = self._account.sign_transaction(tx)
        return bytes(signed.raw_transaction), "0x" + signed.hash.hex()

    def sign_authorization(self, chain_id: int, address: str, nonce: int) -> dict[str, Any]:
        signed = self._account.sign_authorization(
            {"chainId": chain_id, "address": address, "nonce": nonce}
        )
        return {
            "address": address,
            "chainId": chain_id,
            "nonce": nonce,
            "r": "0x" + signed.r.to_bytes(32, "big").hex(),
            "s": "0x" + signed.s.to_bytes(32, "big").hex(),
            "yParity": signed.y_parity,
        }
