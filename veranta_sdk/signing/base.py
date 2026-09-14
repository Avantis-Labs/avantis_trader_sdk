"""Signer interface.

One interface, multiple key backends. The signer does not know about traders
or delegates: identity resolution lives in the client config; the signer just
produces secp256k1 signatures.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseSigner(ABC):
    """Abstract signer: local key today; KMS/hosted signers can plug in later."""

    @property
    @abstractmethod
    def address(self) -> str:
        """Checksummed address of the signing key."""

    @abstractmethod
    def sign_typed_data(self, full_message: dict[str, Any]) -> tuple[bytes, bytes]:
        """Sign an EIP-712 message.

        ``full_message`` must contain ``types`` (including ``EIP712Domain``),
        ``primaryType``, ``domain``, and ``message``.

        Returns ``(signature, message_hash)`` where signature is 65-byte
        r||s||v (v in {27, 28}) and message_hash is the EIP-712 digest.
        """

    @abstractmethod
    def sign_transaction(self, tx: dict[str, Any]) -> tuple[bytes, str]:
        """Sign a transaction dict; returns ``(raw_tx_bytes, tx_hash)``."""

    @abstractmethod
    def sign_authorization(self, chain_id: int, address: str, nonce: int) -> dict[str, Any]:
        """Sign an EIP-7702 set-code authorization.

        Returns a dict with ``address``, ``chainId``, ``nonce``, ``r``, ``s``,
        ``yParity`` (ints for chainId/nonce/yParity, 0x-hex for the rest).
        """
