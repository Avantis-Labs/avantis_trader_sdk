from collections.abc import Mapping
from typing import Any, NamedTuple, Tuple

import boto3
from .base import BaseSigner
from eth_account._utils.signing import sign_transaction_dict
from eth_utils.curried import keccak
from hexbytes import HexBytes
from toolz import dissoc
from web3 import Web3

from ..crypto.spki import der_encoded_public_key_to_eth_address, get_sig_r_s_v


class Signature:
    """Kinda compatible Signature class"""

    def __init__(self, r: int, s: int, v: int) -> None:
        self.r = r
        self.s = s
        self.v = v

    @property
    def vrs(self) -> Tuple[int, int, int]:
        return self.v, self.r, self.s


def __getitem__(self: Any, index: Any) -> Any:
    try:
        return tuple.__getitem__(self, index)
    except TypeError:
        return getattr(self, index)


class SignedTransaction(NamedTuple):
    """Kinda compatible SignedTransaction class"""

    rawTransaction: HexBytes
    hash: HexBytes
    r: int
    s: int
    v: int

    def __getitem__(self, index: Any) -> Any:
        return __getitem__(self, index)


class KMSSigner(BaseSigner):
    def __init__(self, web3, kms_key_id, region_name="us-east-1"):
        self._web3 = web3
        self._key_id = kms_key_id
        self._kms_client = boto3.client("kms", region_name)
        self.address = self.get_public_key()

    async def sign_transaction(self, transaction):
        """
        Signs a transaction using AWS KMS.

        Args:
            transaction: The transaction object to be signed.

        Returns:
            The signed transaction object.
        """
        return await self._sign_transaction(transaction)

    def get_public_key(self):
        """
        Retrieves the public key associated with the KMS key.
        """
        eth_address = self.get_eth_address()
        return Web3.to_checksum_address(eth_address)

    def get_ethereum_address(self):
        """
        Derives the Ethereum wallet address from the public key.

        Returns:
            str: The Ethereum wallet address in checksum format.
        """
        return self.address

    async def _sign_transaction(self, transaction_dict: dict) -> SignedTransaction:
        """
        Somewhat fixed up version of Account.sign_transaction, to use the custom PrivateKey
        impl -- BasicKmsAccount
        https://github.com/ethereum/eth-account/blob/master/eth_account/account.py#L619
        """

        if not isinstance(transaction_dict, Mapping):
            raise TypeError(
                "transaction_dict must be dict-like, got %r" % transaction_dict
            )

        # allow from field, *only* if it matches the private key
        if "from" in transaction_dict:
            if transaction_dict["from"] == self.address:
                sanitized_transaction = dissoc(transaction_dict, "from")
            else:
                raise TypeError(
                    "from field must match key's %s, but it was %s"
                    % (
                        self.address,
                        transaction_dict["from"],
                    )
                )
        else:
            sanitized_transaction = transaction_dict

        if "nonce" not in sanitized_transaction:
            sanitized_transaction["nonce"] = await self._web3.eth.get_transaction_count(
                self.address
            )

        # sign transaction
        (
            v,
            r,
            s,
            encoded_transaction,
        ) = sign_transaction_dict(self, sanitized_transaction)
        transaction_hash = keccak(encoded_transaction)

        return SignedTransaction(
            rawTransaction=HexBytes(encoded_transaction),
            hash=HexBytes(transaction_hash),
            r=r,
            s=s,
            v=v,
        )

    def get_eth_address(self) -> str:
        """Calculate ethereum address for given AWS KMS key."""
        pubkey = self._kms_client.get_public_key(KeyId=self._key_id)["PublicKey"]
        return der_encoded_public_key_to_eth_address(pubkey)

    def sign_msg_hash(self, msg_hash: HexBytes) -> Signature:
        signature = self._kms_client.sign(
            KeyId=self._key_id,
            Message=bytes(msg_hash),
            MessageType="DIGEST",
            SigningAlgorithm="ECDSA_SHA_256",
        )
        act_signature = signature["Signature"]
        r, s, v = get_sig_r_s_v(msg_hash, act_signature, self.address)
        return Signature(r, s, v)
