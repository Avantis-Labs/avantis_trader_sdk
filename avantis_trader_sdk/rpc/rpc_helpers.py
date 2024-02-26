def map_output_to_pairs(pairs_info, decoded_response):
    pairs_mapped_response = {}
    for index, pair_info in pairs_info.items():
        pairs_mapped_response[pair_info.from_ + "/" + pair_info.to] = decoded_response[
            index
        ]

    return pairs_mapped_response
