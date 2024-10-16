import asyncio
from concurrent.futures import ThreadPoolExecutor
from web3 import __version__ as web3_version

web3_major_version = int(web3_version.split(".")[0])


class AsyncWeb3Wrapper:
    def __init__(self, web3, async_web3=None):
        self.web3 = web3
        self.async_web3 = async_web3
        self.executor = ThreadPoolExecutor(max_workers=4)

    def load_contract(self, name, abi, address):
        """
        Loads the contract based on whether it's v5 or v6.

        Args:
            name: The name of the contract.
            abi: The ABI of the contract.
            address: The address of the contract.

        Returns:
            Contract object.
        """
        if web3_major_version >= 6 and self.async_web3:
            return self.async_web3.eth.contract(address=address, abi=abi)
        else:
            contract = self.web3.eth.contract(address=address, abi=abi)
            return AsyncContractWrapper(contract)

    async def call_contract_function(self, contract, function_name, *args):
        """
        Calls a contract function in an async manner, regardless of Web3 version.

        Args:
            contract: The contract object.
            function_name: The name of the function.
            args: The arguments for the function.

        Returns:
            The result of the function call.
        """
        if web3_major_version >= 6:
            return await getattr(contract.functions, function_name)(*args).call()
        else:
            # Use run_in_executor to make the synchronous call async
            return await asyncio.get_event_loop().run_in_executor(
                self.executor, getattr(contract.functions, function_name)(*args).call
            )

    async def send_transaction(self, contract, function_name, *args, **kwargs):
        """
        Sends a transaction (write operation) to the contract.
        """
        if web3_major_version >= 6:
            transaction = await getattr(contract.functions, function_name)(
                *args
            ).build_transaction(kwargs)
        else:
            transaction = contract.functions[function_name](*args).build_transaction(
                kwargs
            )

        return transaction


class AsyncContractFunctionCallWrapper:
    def __init__(self, function_call):
        self.function_call = function_call
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def call(self):
        """
        Async method for executing the contract function call in an asynchronous manner.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.function_call.call)


class AsyncContractFunctionWrapper:
    def __init__(self, function):
        self.function = function

    def __call__(self, *args, **kwargs):
        """
        This method makes the object callable and prepares the contract function call.
        It returns an instance of AsyncContractFunctionCallWrapper which has an async `.call()`.
        """
        function_call = self.function(*args, **kwargs)

        return AsyncContractFunctionCallWrapper(function_call)


class AsyncContractFunctionsWrapper:
    def __init__(self, contract_functions):
        self.contract_functions = contract_functions

    def __getattr__(self, item):
        """
        This method is called when a contract function is accessed (like 'pairsCount').
        """
        contract_function = getattr(self.contract_functions, item)
        return AsyncContractFunctionWrapper(contract_function)


class AsyncContractWrapper:
    def __init__(self, contract):
        self.contract = contract

    def __getattr__(self, item):
        """
        This method is called when an attribute (like a contract function) is accessed.
        """
        if item == "functions":
            return AsyncContractFunctionsWrapper(self.contract.functions)

        return getattr(self.contract, item)
