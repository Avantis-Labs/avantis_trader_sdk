"""Synchronous facade and AWS KMS signing.

- ``Avantis`` mirrors ``AsyncAvantis`` for scripts that don't use asyncio.
- ``KmsSigner`` keeps the key in AWS KMS (install extra: avantis-trader-sdk[kms]).
"""

from avantis_trader_sdk import Avantis


def main() -> None:
    # --- sync client ---
    client = Avantis()  # env config, same as AsyncAvantis
    print("meta chainId:", client.meta()["chainId"])
    receipt = client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)
    print("tx:", receipt.tx_hash)
    client.close()

    # --- KMS signer ---
    # from avantis_trader_sdk.signing import KmsSigner
    # signer = KmsSigner("your-kms-key-id", region_name="us-east-1")
    # client = Avantis(signer=signer, trader_address="0xYourWallet")


if __name__ == "__main__":
    main()
