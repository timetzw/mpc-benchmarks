# prepare_iteration_inputs.py
import sys
import json
import os

def load_party_selected_tx_strings(party_id_str, base_dir="Player-Data"):
    """Loads Party's initially selected transactions (binary strings)."""
    filepath = os.path.join(base_dir, f"Input-P{party_id_str}-1")
    selected_txs = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                selected_txs.append(line.strip())
    except FileNotFoundError:
        print(f"Warning (prepare_iteration_inputs): Party input file not found: {filepath}")
    return selected_txs

def main():
    if len(sys.argv) != 6:
        print("Usage: python3 prepare_iteration_inputs.py <PARTY_ID> <CANDIDATE_PREFIXES_FILE_JSON> <MAX_PREFIX_SLOTS> <TRANSACTION_SPACE_BITS> <CURRENT_LEVEL_NUM>")
        sys.exit(1)

    try:
        party_id = int(sys.argv[1])
        candidate_prefixes_file = sys.argv[2]
        max_prefix_slots = int(sys.argv[3])
        # transaction_space_bits = int(sys.argv[4]) # Not strictly needed by this script if lengths are in candidate_prefixes
        current_level_num = int(sys.argv[5])
    except ValueError:
        print("Error: PARTY_ID, MAX_PREFIX_SLOTS, CURRENT_LEVEL_NUM must be integers.")
        sys.exit(1)

    # Load candidate prefixes for the current iteration (shared by orchestrator)
    candidate_prefixes_info_this_level = [] # List of dicts [{'level':l, 'prefix_len':pl, 'prefix_str':ps}, ...]
    num_active_prefixes_this_level = 0
    try:
        with open(candidate_prefixes_file, 'r') as f:
            data = json.load(f)
            candidate_prefixes_info_this_level = data.get("candidate_prefixes_info", [])
            num_active_prefixes_this_level = data.get("num_active_prefixes", 0)
            # current_level_from_file = data.get("current_level", -1) # Could also get level from here
    except Exception as e:
        print(f"Error loading candidate prefixes from {candidate_prefixes_file}: {e}")
        sys.exit(1)
    
    if num_active_prefixes_this_level != len(candidate_prefixes_info_this_level):
        print(f"Error: Mismatch between num_active_prefixes ({num_active_prefixes_this_level}) and length of candidate_prefixes_info ({len(candidate_prefixes_info_this_level)}).")
        sys.exit(1)

    if num_active_prefixes_this_level > max_prefix_slots:
        print(f"Error: Number of active prefixes ({num_active_prefixes_this_level}) exceeds MAX_PREFIX_SLOTS ({max_prefix_slots}).")
        sys.exit(1)

    party_selected_tx_bin_list = load_party_selected_tx_strings(str(party_id))
    
    # Initialize counts for all MAX_PREFIX_SLOTS, default to 0
    party_mpc_input_counts = [0] * max_prefix_slots

    # Populate counts for the active prefixes for this iteration
    for idx in range(num_active_prefixes_this_level):
        prefix_info = candidate_prefixes_info_this_level[idx]
        prefix_to_check = prefix_info['prefix_str']
        prefix_len = prefix_info['prefix_len'] # Length of the current prefix to check
        
        current_slot_count = 0
        if prefix_len == 0: # Root prefix case
            current_slot_count = len(party_selected_tx_bin_list)
        else:
            for party_tx_bin in party_selected_tx_bin_list:
                if len(party_tx_bin) >= prefix_len and party_tx_bin.startswith(prefix_to_check):
                    current_slot_count += 1
        party_mpc_input_counts[idx] = current_slot_count

    # Prepare lines to write to Player-Data/Input-P<party_id>-0
    lines_to_write = []
    if party_id == 0: # Party 0 provides public inputs first
        lines_to_write.append(str(num_active_prefixes_this_level))
        lines_to_write.append(str(current_level_num)) # Pass current level being processed
    else: # Other parties provide dummy values for these public inputs
        lines_to_write.append(str(0)) # Dummy for num_active_prefixes
        lines_to_write.append(str(0)) # Dummy for current_level_num
        
    for count_val in party_mpc_input_counts:
        lines_to_write.append(str(count_val))

    mpc_input_file = os.path.join("Player-Data", f"Input-P{party_id}-0")
    try:
        with open(mpc_input_file, 'w') as f_out:
            for line in lines_to_write:
                f_out.write(line + '\n')
        # print(f"  Party {party_id}: Wrote {len(lines_to_write)} lines to {mpc_input_file} for MPC iteration (level {current_level_num}).")
    except IOError as e:
        print(f"  Error writing MPC input file {mpc_input_file} for Party {party_id}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()