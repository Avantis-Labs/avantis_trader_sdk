import json
from pathlib import Path
from web3 import Web3, AsyncWeb3
from .config import CONTRACT_ADDRESSES
from .rpc.pairs_cache import PairsCache
from .rpc.asset_parameters import AssetParametersRPC
from .utils import decoder


class TraderClient:
    def __init__(self, provider_url):
        self.web3 = Web3(Web3.HTTPProvider(provider_url))
        self.async_web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(provider_url))
        self.contracts = self.load_contracts()
        self.utils = {
            "decoder": lambda *args, **kwargs: decoder(self.web3, *args, **kwargs)
        }
        self.pairs_cache = PairsCache(self)
        self.asset_parameters = AssetParametersRPC(self)

    def load_contract(self, name):
        abi_path = Path(__file__).parent / "abis" / f"{name}.sol" / f"{name}.json"
        with open(abi_path) as abi_file:
            abi = json.load(abi_file)
        address = CONTRACT_ADDRESSES[name]
        return self.async_web3.eth.contract(address=address, abi=abi["abi"])

    def load_contracts(self):
        return {name: self.load_contract(name) for name in CONTRACT_ADDRESSES.keys()}

    async def read_contract(self, contract_name, function_name, *args):
        contract = self.contracts.get(contract_name)
        if not contract:
            raise ValueError(f"Contract {contract_name} not found")
        return await contract.functions[function_name](*args).call()
