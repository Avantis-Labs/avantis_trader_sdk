"""AWS KMS signer (optional extra: ``pip install avantis-trader-sdk-v2[kms]``).

Signs raw 32-byte digests with a KMS ECDSA (secp256k1) key and adapts them to
EIP-712 messages, transactions, and EIP-7702 authorizations. The private key
never leaves KMS.
"""

from __future__ import annotations

from typing import Any

import rlp
from eth_account._utils.legacy_transactions import (
    encode_transaction,
    serializable_unsigned_transaction_from_dict,
)
from eth_account.messages import _hash_eip191_message, encode_typed_data
from eth_utils import keccak, to_bytes, to_checksum_address

from .base import BaseSigner

_SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def _der_public_key_to_address(der: bytes) -> str:
    from pyasn1.codec.der.decoder import decode as der_decode
    from pyasn1.type import namedtype, univ

    class _AlgId(univ.Sequence):
        componentType = namedtype.NamedTypes(
            namedtype.NamedType("algorithm", univ.ObjectIdentifier()),
            namedtype.OptionalNamedType("parameters", univ.Any()),
        )

    class _SPKI(univ.Sequence):
        componentType = namedtype.NamedTypes(
            namedtype.NamedType("algorithm", _AlgId()),
            namedtype.NamedType("subjectPublicKey", univ.BitString()),
        )

    record, _ = der_decode(der, asn1Spec=_SPKI())
    pubkey_bytes = int(record["subjectPublicKey"].asBinary(), 2).to_bytes(65, "big")
    return to_checksum_address(keccak(pubkey_bytes[1:])[-20:])


def _der_signature_to_rs(der: bytes) -> tuple[int, int]:
    from pyasn1.codec.der.decoder import decode as der_decode
    from pyasn1.type import namedtype, univ

    class _Sig(univ.Sequence):
        componentType = namedtype.NamedTypes(
            namedtype.NamedType("r", univ.Integer()),
            namedtype.NamedType("s", univ.Integer()),
        )

    record, _ = der_decode(der, asn1Spec=_Sig())
    r, s = int(record["r"]), int(record["s"])
    if s > _SECP256K1_N // 2:  # enforce low-s
        s = _SECP256K1_N - s
    return r, s


class KmsSigner(BaseSigner):
    def __init__(self, kms_key_id: str, region_name: str = "us-east-1") -> None:
        import boto3

        self._key_id = kms_key_id
        self._kms = boto3.client("kms", region_name=region_name)
        pub = self._kms.get_public_key(KeyId=self._key_id)["PublicKey"]
        self._address = _der_public_key_to_address(pub)

    @property
    def address(self) -> str:
        return self._address

    # ------------------------------------------------------------------ core

    def _sign_hash(self, msg_hash: bytes) -> tuple[int, int, int]:
        """Returns (v, r, s) with v in {27, 28}."""
        from eth_account import Account

        resp = self._kms.sign(
            KeyId=self._key_id,
            Message=msg_hash,
            MessageType="DIGEST",
            SigningAlgorithm="ECDSA_SHA_256",
        )
        r, s = _der_signature_to_rs(resp["Signature"])
        for v in (27, 28):
            sig = r.to_bytes(32, "big") + s.to_bytes(32, "big") + bytes([v])
            if Account._recover_hash(msg_hash, signature=sig).lower() == self._address.lower():
                return v, r, s
        raise ValueError("KMS signature does not recover to the key's address")

    # ------------------------------------------------------------------ BaseSigner

    def sign_typed_data(self, full_message: dict[str, Any]) -> tuple[bytes, bytes]:
        signable = encode_typed_data(full_message=full_message)
        msg_hash = _hash_eip191_message(signable)
        v, r, s = self._sign_hash(msg_hash)
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big") + bytes([v])
        return signature, msg_hash

    def sign_transaction(self, tx: dict[str, Any]) -> tuple[bytes, str]:
        unsigned = serializable_unsigned_transaction_from_dict(tx)
        tx_hash = unsigned.hash()
        v, r, s = self._sign_hash(tx_hash)
        if "gasPrice" not in tx:  # typed (EIP-1559) txs use y_parity
            v = v - 27
        encoded = encode_transaction(unsigned, vrs=(v, r, s))
        return encoded, "0x" + keccak(encoded).hex()

    def sign_authorization(self, chain_id: int, address: str, nonce: int) -> dict[str, Any]:
        # EIP-7702: keccak(0x05 || rlp([chain_id, address, nonce]))
        payload = rlp.encode([chain_id, to_bytes(hexstr=address), nonce])
        msg_hash = keccak(b"\x05" + payload)
        v, r, s = self._sign_hash(msg_hash)
        return {
            "address": address,
            "chainId": chain_id,
            "nonce": nonce,
            "r": "0x" + r.to_bytes(32, "big").hex(),
            "s": "0x" + s.to_bytes(32, "big").hex(),
            "yParity": v - 27,
        }
