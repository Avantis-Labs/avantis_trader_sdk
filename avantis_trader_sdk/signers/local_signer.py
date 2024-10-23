from web3 import AsyncWeb3
from .base import BaseSigner


class LocalSigner(BaseSigner):
    def __init__(self, private_key, async_web3: AsyncWeb3):
        self.private_key = private_key
        self.async_web3 = async_web3

    async def sign_transaction(self, transaction):
        return self.async_web3.eth.account.sign_transaction(
            transaction, self.private_key
        )

    def get_ethereum_address(self):
        return self.async_web3.eth.account.from_key(self.private_key).address
