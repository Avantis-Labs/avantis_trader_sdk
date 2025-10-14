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

from .signers.base import BaseSigner
from .signers.local_signer import LocalSigner
from .signers.kms_signer import KMSSigner


class TraderClient:
    """
    This class provides methods to interact with the Avantis smart contracts.
    """

    def __init__(
        self,
        provider_url,
        l1_provider_url="https://eth.llamarpc.com",
        signer: BaseSigner = None,
        feed_client: FeedClient = None,
    ):
        """
        Constructor for the TraderClient class.

        Args:
            provider_url: The URL of the Ethereum node provider.
            l1_provider_url (optional): The URL of the L1 Ethereum node provider.
            signer (optional): The signer to use for signing transactions.
        """
        if l1_provider_url != "https://eth.llamarpc.com":
            print(
                " ⚠️ Warning: l1_provider_url is deprecated and will be removed in the future."
            )

        self.web3 = Web3(
            Web3.HTTPProvider(provider_url, request_kwargs={"timeout": 60})
        )
        self.async_web3 = AsyncWeb3(
            AsyncWeb3.AsyncHTTPProvider(provider_url, request_kwargs={"timeout": 60})
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
        self.feed_client = feed_client or FeedClient()
        self.trade = TradeRPC(self, self.feed_client)

        self.signer = signer

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

    async def write_contract(self, contract_name, function_name, *args, **kwargs):
        """
        Calls a write function of a contract.

        Args:
            contract_name: The name of the contract.
            function_name: The name of the function.
            args: The arguments to the function.

        Returns:
            The transaction hash or the transaction object if signer is None.
        """
        contract = self.contracts.get(contract_name)
        if not contract:
            raise ValueError(f"Contract {contract_name} not found")

        if self.has_signer() and "from" not in kwargs:
            kwargs["from"] = self.get_signer().get_ethereum_address()

        if "chainId" not in kwargs:
            kwargs["chainId"] = self.chain_id

        if "nonce" not in kwargs:
            kwargs["nonce"] = await self.get_transaction_count(kwargs["from"])

        transaction = await contract.functions[function_name](*args).build_transaction(
            kwargs
        )

        if not self.has_signer():
            return transaction

        receipt = await self.sign_and_get_receipt(transaction)
        return receipt

    def set_signer(self, signer: BaseSigner):
        """
        Sets the signer.
        """
        self.signer = signer

    def get_signer(self):
        """
        Gets the signer.
        """
        return self.signer

    def remove_signer(self):
        """
        Removes the signer.
        """
        self.signer = None

    def has_signer(self):
        """
        Checks if the signer is set.
        """
        return self.signer is not None

    def set_local_signer(self, private_key):
        """
        Sets the local signer.
        """
        self.signer = LocalSigner(private_key, self.async_web3)

    def set_aws_kms_signer(self, kms_key_id, region_name="us-east-1"):
        """
        Sets the AWS KMS signer.
        """
        self.signer = KMSSigner(self.async_web3, kms_key_id, region_name)

    async def sign_transaction(self, transaction):
        """
        Signs a transaction.

        Args:
            transaction: The transaction object.

        Returns:
            The signed transaction object.
        """
        if not self.has_signer():
            raise ValueError(
                "No signer is set. Please set a signer using `set_signer`."
            )
        return await self.signer.sign_transaction(transaction)

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

    async def sign_and_get_receipt(self, transaction):
        """
        Signs a transaction and waits for it to be mined.

        Args:
            transaction: The transaction object.

        Returns:
            The transaction receipt.
        """
        gas_estimate = await self.get_gas_estimate(transaction)
        transaction["gas"] = gas_estimate
        signed_txn = await self.sign_transaction(transaction)
        tx_hash = await self.send_and_get_transaction_hash(signed_txn)
        return await self.wait_for_transaction_receipt(tx_hash)

    async def get_transaction_count(self, address=None):
        """
        Gets the transaction count.

        Args:
            address (optional): The address.

        Returns:
            The transaction count.
        """
        if address is None:
            address = self.get_signer().get_ethereum_address()
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

    async def get_balance(self, address=None):
        """
        Gets the balance.

        Args:
            address (optional): The address.

        Returns:
            The balance.
        """
        if address is None:
            address = self.get_signer().get_ethereum_address()
        balance = await self.async_web3.eth.get_balance(address)
        return balance / 10**18

    async def get_usdc_balance(self, address=None):
        """
        Gets the USDC balance.

        Args:
            address (optional): The address.

        Returns:
            The USDC balance.
        """
        if address is None:
            address = self.get_signer().get_ethereum_address()
        balance = await self.read_contract("USDC", "balanceOf", address, decode=False)
        return balance / 10**6

    async def get_usdc_allowance_for_trading(self, address=None):
        """
        Gets the USDC allowance for the Trading Storage contract.

        Args:
            address (optional): The address.

        Returns:
            The USDC allowance.
        """
        if address is None:
            address = self.get_signer().get_ethereum_address()

        trading_storage_address = self.contracts["TradingStorage"].address

        allowance = await self.read_contract(
            "USDC", "allowance", address, trading_storage_address, decode=False
        )
        return allowance / 10**6

    async def approve_usdc_for_trading(self, amount=100000):
        """
        Approves the USDC amount for the Trading Storage contract.

        Args:
            amount (optional): The amount to approve. Defaults to $100,000.

        Returns:
            The transaction hash.
        """
        trading_storage_address = self.contracts["TradingStorage"].address
        return await self.write_contract(
            "USDC", "approve", trading_storage_address, int(amount * 10**6)
        )

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
