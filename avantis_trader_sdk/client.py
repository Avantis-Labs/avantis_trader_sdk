import json
from pathlib import Path
from web3 import Web3, AsyncWeb3
from .config import CONTRACT_ADDRESSES
from .rpc.pairs_cache import PairsCache
from .rpc.asset_parameters import AssetParametersRPC
from .rpc.category_parameters import CategoryParametersRPC
from .rpc.blended import BlendedRPC
from .rpc.fee_parameters import FeeParametersRPC
from .rpc.trading_parameters import TradingParametersRPC
from .rpc.snapshot import SnapshotRPC
from .rpc.trade import TradeRPC
from .utils import decoder
from .feed.feed_client import FeedClient


class TraderClient:
    """
    This class provides methods to interact with the Avantis smart contracts.
    """

    def __init__(self, provider_url, l1_provider_url="https://eth.llamarpc.com"):
        """
        Constructor for the TraderClient class.

        Args:
            provider_url: The URL of the Ethereum node provider.
        """
        self.web3 = Web3(
            Web3.HTTPProvider(provider_url, request_kwargs={"timeout": 60})
        )
        self.async_web3 = AsyncWeb3(
            AsyncWeb3.AsyncHTTPProvider(provider_url, request_kwargs={"timeout": 60})
        )

        self.l1_web3 = Web3(
            Web3.HTTPProvider(l1_provider_url, request_kwargs={"timeout": 60})
        )

        self.l1_async_web3 = AsyncWeb3(
            AsyncWeb3.AsyncHTTPProvider(l1_provider_url, request_kwargs={"timeout": 60})
        )

        self.contracts = self.load_contracts()
        self.chain_id = self.web3.eth.chain_id

        self.utils = {
            "decoder": lambda *args, **kwargs: decoder(self.web3, *args, **kwargs)
        }

        self.pairs_cache = PairsCache(self)
        self.asset_parameters = AssetParametersRPC(self)
        self.category_parameters = CategoryParametersRPC(self)
        self.blended = BlendedRPC(self)
        self.fee_parameters = FeeParametersRPC(self)
        self.trading_parameters = TradingParametersRPC(self)
        self.snapshot = SnapshotRPC(self)
        self.trade = TradeRPC(self, FeedClient)

    def load_contract(self, name):
        """
        Loads the contract ABI and address from the local filesystem.

        Args:
            name: The name of the contract.

        Returns:
            A Contract object.
        """
        abi_path = Path(__file__).parent / "abis" / f"{name}.sol" / f"{name}.json"
        with open(abi_path) as abi_file:
            abi = json.load(abi_file)
        address = CONTRACT_ADDRESSES[name]
        return self.async_web3.eth.contract(address=address, abi=abi["abi"])

    def load_contracts(self):
        """
        Loads all the contracts mentioned in the config from the local filesystem.

        Returns:
            A dictionary containing the contract names as keys and the Contract objects as values.
        """
        return {name: self.load_contract(name) for name in CONTRACT_ADDRESSES.keys()}

    async def read_contract(self, contract_name, function_name, *args, decode=True):
        """
        Calls a read-only function of a contract.

        Args:
            contract_name: The name of the contract.
            function_name: The name of the function.
            args: The arguments to the function.

        Returns:
            The result of the function call.
        """
        contract = self.contracts.get(contract_name)
        if not contract:
            raise ValueError(f"Contract {contract_name} not found")

        raw_data = await contract.functions[function_name](*args).call()

        if decode:
            return self.utils["decoder"](contract, function_name, raw_data)

        return raw_data

    async def write_contract(
        self, private_key, contract_name, function_name, *args, **kwargs
    ):
        """
        Calls a write function of a contract.

        Args:
            private_key: The private key of the wallet.
            contract_name: The name of the contract.
            function_name: The name of the function.
            args: The arguments to the function.

        Returns:
            The transaction hash or the transaction object if private key is None.
        """
        contract = self.contracts.get(contract_name)
        if not contract:
            raise ValueError(f"Contract {contract_name} not found")

        transaction = contract.functions[function_name](*args).build_transaction(kwargs)

        if private_key is None:
            return transaction

        signed_txn = await self.sign_transaction(private_key, transaction)
        tx_hash = await self.send_and_get_transaction_hash(signed_txn)
        return tx_hash

    async def sign_transaction(self, private_key, transaction):
        """
        Signs a transaction.

        Args:
            private_key: The private key of the wallet.
            transaction: The transaction object.

        Returns:
            The signed transaction object.
        """
        return await self.async_web3.eth.account.sign_transaction(
            transaction, private_key
        )

    async def send_and_get_transaction_hash(self, signed_txn):
        """
        Gets the transaction hash.

        Args:
            signed_txn: The signed transaction object.

        Returns:
            The transaction hash.
        """
        return await self.async_web3.eth.send_raw_transaction(signed_txn.rawTransaction)

    async def wait_for_transaction_receipt(self, tx_hash):
        """
        Waits for the transaction to be mined.

        Args:
            tx_hash: The transaction hash.

        Returns:
            The transaction receipt.
        """
        return await self.async_web3.eth.wait_for_transaction_receipt(tx_hash)

    async def sign_and_get_receipt(self, private_key, transaction):
        """
        Signs a transaction and waits for it to be mined.

        Args:
            private_key: The private key of the wallet.
            transaction: The transaction object.

        Returns:
            The transaction receipt.
        """
        signed_txn = await self.sign_transaction(private_key, transaction)
        tx_hash = await self.send_and_get_transaction_hash(signed_txn)
        return await self.wait_for_transaction_receipt(tx_hash)

    async def get_transaction_count(self, address):
        """
        Gets the transaction count.

        Args:
            address: The address.

        Returns:
            The transaction count.
        """
        return await self.async_web3.eth.get_transaction_count(address)

    async def get_gas_price(self):
        """
        Gets the gas price.

        Returns:
            The gas price.
        """
        return await self.async_web3.eth.gas_price

    async def get_chain_id(self):
        """
        Gets the chain id.

        Returns:
            The chain id.
        """
        return await self.async_web3.eth.chain_id

    async def get_balance(self, address):
        """
        Gets the balance.

        Args:
            address: The address.

        Returns:
            The balance.
        """
        return await self.async_web3.eth.get_balance(address)

    async def get_usdc_balance(self, address):
        """
        Gets the USDC balance.

        Args:
            address: The address.

        Returns:
            The USDC balance.
        """
        balance = await self.read_contract("USDC", "balanceOf", address, decode=False)
        return balance / 10**6

    async def get_gas_estimate(self, transaction):
        """
        Gets the gas estimate.

        Args:
            transaction: The transaction object.

        Returns:
            The gas estimate.
        """
        return await self.async_web3.eth.estimate_gas(transaction)

    async def get_transaction_hex(self, transaction):
        """
        Gets the transaction hex.

        Args:
            transaction: The transaction object.

        Returns:
            The transaction hex.
        """
        return transaction.hex()
