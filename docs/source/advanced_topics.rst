Advanced Topics
---------------

read_contract
^^^^^^^^^^^^^^^
The ``read_contract`` method allows you to call a read-only function of a contract. This method is useful when you want to retrieve information from a contract without modifying its state.

**Parameters:**

- ``contract_name`` (str): The name of the contract.
- ``function_name`` (str): The name of the function.
- ``args``: The arguments to the function.
- ``decode`` (bool, optional): A boolean indicating whether to decode the result.

**Returns:**

- The result of the function call.

**Example Usage:**

.. code-block:: python

   pairs_count = await trader_client.read_contract("PairStorage", "pairsCount")
   print("Pairs Count:", pairs_count)

