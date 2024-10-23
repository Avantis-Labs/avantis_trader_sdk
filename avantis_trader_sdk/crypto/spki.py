from typing import Tuple

from Crypto.Hash import keccak
from eth_account.account import Account
from eth_utils import to_checksum_address
from pyasn1.codec.der.decoder import decode as der_decode
from pyasn1.type import namedtype, univ


class SPKIAlgorithmIdentifierRecord(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("algorithm", univ.ObjectIdentifier()),
        namedtype.OptionalNamedType("parameters", univ.Any()),
    )


class SPKIRecord(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("algorithm", SPKIAlgorithmIdentifierRecord()),
        namedtype.NamedType("subjectPublicKey", univ.BitString()),
    )


class ECDSASignatureRecord(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("r", univ.Integer()),
        namedtype.NamedType("s", univ.Integer()),
    )


def public_key_int_to_eth_address(pubkey: int) -> str:
    """
    Given an integer public key, calculate the ethereum address.
    """
    hex_string = hex(pubkey).replace("0x", "")
    padded_hex_string = hex_string.replace("0x", "").zfill(130)[2:]

    k = keccak.new(digest_bits=256)
    k.update(bytes.fromhex(padded_hex_string))
    return to_checksum_address(bytes.fromhex(k.hexdigest())[-20:].hex())


def der_encoded_public_key_to_eth_address(pubkey: bytes) -> str:
    """
    Given a KMS Public Key, calculate the ethereum address.
    """
    received_record, _ = der_decode(pubkey, asn1Spec=SPKIRecord())
    return public_key_int_to_eth_address(
        int(received_record["subjectPublicKey"].asBinary(), 2)
    )


def get_sig_r_s(signature: bytes) -> Tuple[int, int]:
    """
    Given a KMS signature, calculate r and s.
    """
    received_record, _ = der_decode(signature, asn1Spec=ECDSASignatureRecord())
    r = int(received_record["r"].prettyPrint())
    s = int(received_record["s"].prettyPrint())

    max_value_on_curve = (
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
    )

    if 2 * s >= max_value_on_curve:
        # s is on wrong side of curve, flip it
        s = max_value_on_curve - s
    return r, s


def get_sig_v(msg_hash: bytes, r: int, s: int, expected_address: str) -> int:
    """
    Given a message hash, r, s and an ethereum address, recover the
    recovery parameter v.
    """
    acc = Account()
    recovered = acc._recover_hash(msg_hash, vrs=(27, r, s))
    recovered2 = acc._recover_hash(msg_hash, vrs=(28, r, s))
    expected_checksum_address = to_checksum_address(expected_address)

    if recovered == expected_checksum_address:
        return 0
    elif recovered2 == expected_checksum_address:
        return 1

    raise ValueError("Invalid Signature, cannot compute v, addresses do not match!")


def get_sig_r_s_v(
    msg_hash: bytes, signature: bytes, address: str
) -> Tuple[int, int, int]:
    """
    Given a message hash, a KMS signature and an ethereum address calculate r,
    s, and v.
    """
    r, s = get_sig_r_s(signature)
    v = get_sig_v(msg_hash, r, s, address)
    return r, s, v
