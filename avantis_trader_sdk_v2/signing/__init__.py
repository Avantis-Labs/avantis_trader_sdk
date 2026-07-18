from .base import BaseSigner
from .intents import sign_intent, to_int_message
from .local import LocalSigner

__all__ = ["BaseSigner", "KmsSigner", "LocalSigner", "sign_intent", "to_int_message"]


def __getattr__(name: str):
    if name == "KmsSigner":  # lazy: boto3 is an optional extra
        from .kms import KmsSigner

        return KmsSigner
    raise AttributeError(name)
