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
from .utils import decoder


class TraderClient:
    """
    This class provides methods to interact with the Avantis smart contracts.
    """

    def __init__(self, provider_url):
        """
        Constructor for the TraderClient class.

        Args:
            provider_url: The URL of the Ethereum node provider.
        """
        self.web3 = Web3(Web3.HTTPProvider(provider_url))
        self.async_web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(provider_url))
        self.contracts = self.load_contracts()
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

    async def read_contract(self, contract_name, function_name, *args, decode=False):
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
