"""Synchronous facade and AWS KMS signing.

- ``Veranta`` mirrors ``AsyncVeranta`` for scripts that don't use asyncio.
- ``KmsSigner`` keeps the key in AWS KMS (install extra: veranta-sdk[kms]).
"""

from veranta_sdk import Veranta


def main() -> None:
    # --- sync client ---
    client = Veranta()  # env config, same as AsyncVeranta
    print("meta chainId:", client.meta()["chainId"])
    receipt = client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)
    print("tx:", receipt.tx_hash)
    client.close()

    # --- KMS signer ---
    # from veranta_sdk.signing import KmsSigner
    # signer = KmsSigner("your-kms-key-id", region_name="us-east-1")
    # client = Veranta(signer=signer, trader_address="0xYourWallet")


if __name__ == "__main__":
    main()
