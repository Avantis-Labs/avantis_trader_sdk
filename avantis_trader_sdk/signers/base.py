from abc import ABC, abstractmethod


class BaseSigner(ABC):
    """
    Base class for signers.
    """

    @abstractmethod
    async def sign_transaction(self, transaction):
        pass

    @abstractmethod
    def get_ethereum_address(self):
        pass
