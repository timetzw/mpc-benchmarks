# prepare_iteration_inputs.py
# usage: python3 prepare_iteration_inputs.py <PARTY_ID> <CANDIDATES_JSON> <TX_BITS>
import sys
import json
import os

def load_party_selected_tx_ints(party_id_str):
    """Loads a party's raw selected transaction IDs (as integers)."""
    filepath = os.path.join("Player-Data", f"Input-P{party_id_str}-1")
    selected_txs = set()
    try:
        with open(filepath, 'r') as f:
            for line in f:
                selected_txs.add(int(line.strip()))
    except FileNotFoundError:
        print(f"Warning: Party raw votes file not found: {filepath}. Assuming party has no votes.")
    except ValueError as e:
        print(f"Error: Found non-integer value in {filepath}. Error: {e}")
    return list(selected_txs)

def calculate_prefix_range(prefix_str, tx_space_bits):
    """Calculates the integer range [min, max] for a given binary prefix string."""
    prefix_len = len(prefix_str)
    if not prefix_str: # Handle root prefix case
        return 0, (2**tx_space_bits) - 1 if tx_space_bits > 0 else 0

    try:
        prefix_int = int(prefix_str, 2)
    except ValueError:
        return -1, -1

    remaining_bits = tx_space_bits - prefix_len
    range_min = prefix_int << remaining_bits
    range_max = ((prefix_int + 1) << remaining_bits) - 1
    return range_min, range_max

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 prepare_iteration_inputs.py <PARTY_ID> <CANDIDATES_JSON> <TX_BITS>")
        sys.exit(1)

    try:
        party_id = int(sys.argv[1])
        candidate_prefixes_file = sys.argv[2]
        transaction_space_bits = int(sys.argv[3])
    except ValueError:
        print("Error: PARTY_ID and TRANSACTION_SPACE_BITS must be integers.")
        sys.exit(1)

    try:
        with open(candidate_prefixes_file, 'r') as f:
            data = json.load(f)
            candidate_prefixes = data["candidate_prefixes_info"]
            num_active_prefixes = data["num_active_prefixes"]
    except Exception as e:
        print(f"Error loading candidate prefixes from {candidate_prefixes_file}: {e}")
        sys.exit(1)

    party_tx_ints = load_party_selected_tx_ints(str(party_id))
    party_mpc_input_counts = []

    for prefix_info in candidate_prefixes:
        prefix_to_check = prefix_info['prefix_str']
        range_min, range_max = calculate_prefix_range(prefix_to_check, transaction_space_bits)
        if range_min == -1:
             party_mpc_input_counts.append(0)
             continue
        count = sum(1 for tx_id in party_tx_ints if range_min <= tx_id <= range_max)
        party_mpc_input_counts.append(count)

    lines_to_write = []

    # Party 0 provides the actual number of active prefixes as a public input.
    # Other parties provide a dummy value to keep the input tape aligned.
    if party_id == 0:
        lines_to_write.append(str(num_active_prefixes))
    else:
        lines_to_write.append("0") # Dummy value

    # All parties then write their secret vote counts.
    lines_to_write.extend([str(count) for count in party_mpc_input_counts])

    mpc_input_file = os.path.join("Player-Data", f"Input-P{party_id}-0")
    try:
        with open(mpc_input_file, 'w') as f_out:
            f_out.write('\n'.join(lines_to_write) + '\n')
    except IOError as e:
        print(f"Error writing MPC input file for Party {party_id}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
