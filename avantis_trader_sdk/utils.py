from web3 import Web3


def is_tuple_type(type_):
    return type_.startswith("tuple")


def is_array_type(type_):
    return type_.endswith("[]")


def process_output_types(abi_outputs):
    """Processes ABI outputs, handling tuples based on their components."""
    processed_types = []
    for output in abi_outputs:
        output_type = output["type"]  # Get the type string
        if is_array_type(output_type):
            # Assuming arrays will always contain types, not data
            processed_types.append(output_type)
        elif is_tuple_type(output_type):
            # Recursively process the tuple's components
            processed_components = process_output_types(output["components"])
            tuple_str = f"({','.join(processed_components)})"  # Construct tuple string
            processed_types.append(tuple_str)
        else:
            processed_types.append(output_type)
    return processed_types


def assign_names_to_decoded(decoded_output, abi_outputs):
    """Assigns names from ABI outputs to values in a decoded tuple/array."""
    if not isinstance(decoded_output, (list, tuple)):
        return decoded_output  # Not an array or tuple

    result = {}
    for output, value in zip(abi_outputs, decoded_output):
        if "components" in output:
            result[output["name"]] = assign_names_to_decoded(
                value, output["components"]
            )
        elif output["type"] == "bytes32":  # Check for bytes32
            result[output["name"]] = Web3.to_hex(value)  # Convert to hex string
        else:
            result[output["name"]] = value
    return result


# def auto_decode(contract, function_name, *args):
#     # Get the function from the contract
#     function = getattr(contract.functions, function_name)

#     # Call the function with the provided arguments
#     raw_output = function(*args).call()

#     # Get the ABI for the function
#     abi_outputs = [output for output in contract.abi if output.get('name') == function_name][0]['outputs']

#     # Decode the output
#     output_types = [output['type'] for output in abi_outputs]
#     decoded_output = Web3.codec.decode(output_types, raw_output)

#     # Convert the decoded output to a structured object
#     structured_output = convert_array_to_object(abi_outputs, decoded_output)

#     return structured_output


def decoder(web3, contract, function_name, raw_output):
    abi_outputs = [
        output for output in contract.abi if output.get("name") == function_name
    ][0]["outputs"]

    output_types = process_output_types(abi_outputs)
    decoded_output = raw_output
    if not isinstance(raw_output, list):
        decoded_output = web3.codec.decode(output_types, raw_output)
    decoded_output = assign_names_to_decoded(decoded_output, abi_outputs)
    return decoded_output
