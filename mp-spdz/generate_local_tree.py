# generate_local_tree.py (Revised to read from Input-P<id>-1)
import sys
import math
import os
import json # For loading mempool_definition.json

# --- Helper Functions ---
def load_mempool_tx_strings_from_json(filepath="Player-Data/mempool_definition.json"):
    """Loads the common mempool definition (list of binary strings)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list) or not all(isinstance(tx, str) for tx in data):
            print(f"Error: Mempool file {filepath} is not a list of strings.")
            return []
        return data
    except FileNotFoundError:
        print(f"Error: Mempool file {filepath} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}.")
        return []
    except Exception as e:
        print(f"Error loading mempool: {e}")
        return []

def generate_canonical_prefix_keys(mempool_tx_strings, max_tx_len, branch_factor_log2_val):
    """
    Generates a canonical, ordered list of prefix keys based on the public mempool.
    Each key is a dict: {'level': int, 'prefix_len': int, 'prefix_str': str}
    """
    all_mempool_prefixes_by_len = {}
    if mempool_tx_strings and max_tx_len > 0:
        for l_len in range(1, max_tx_len + 1):
            current_len_prefixes = set()
            for tx_bin_str in mempool_tx_strings:
                if len(tx_bin_str) >= l_len:
                     current_len_prefixes.add(tx_bin_str[:l_len])
            if current_len_prefixes:
                all_mempool_prefixes_by_len[l_len] = current_len_prefixes
    
    canonical_keys = [{'level': 0, 'prefix_len': 0, 'prefix_str': ""}] # Root
    if max_tx_len == 0: return canonical_keys
    if branch_factor_log2_val <= 0: return canonical_keys

    max_level_num = math.ceil(max_tx_len / branch_factor_log2_val)
    for level_num_val in range(1, int(max_level_num) + 1):
        current_processing_prefix_len = level_num_val * branch_factor_log2_val
        if current_processing_prefix_len > max_tx_len:
            current_processing_prefix_len = max_tx_len
        
        prefixes_at_this_len_set = all_mempool_prefixes_by_len.get(current_processing_prefix_len, set())
        for p_str in sorted(list(prefixes_at_this_len_set)):
            canonical_keys.append({
                'level': level_num_val,
                'prefix_len': current_processing_prefix_len,
                'prefix_str': p_str
            })
        if current_processing_prefix_len == max_tx_len: break
    return canonical_keys

def load_party_selected_tx_strings_from_mpc_input_file(party_id, expected_votes_per_party):
    """
    Loads a party's selected transactions (binary strings) from their input file.
    Now assumes these are in Player-Data/Input-P<party_id>-1 as per user log.
    """
    # MODIFIED: Read from Input-P<party_id>-1 for selected binary TX strings
    filepath = os.path.join("Player-Data", f"Input-P{party_id}-1") 
    selected_txs = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                tx_bin = line.strip()
                if tx_bin or (tx_bin == "" and len(selected_txs) < expected_votes_per_party): # Handle empty string for 0-bit TX
                    selected_txs.append(tx_bin)
        print(f"  Successfully loaded {len(selected_txs)} selected TX strings from {filepath} for Party {party_id}.")
    except FileNotFoundError:
        print(f"Warning: Party input file with selected TXs not found: {filepath}. Assuming no transactions selected by Party {party_id}.")
    return selected_txs

# --- Main Script ---
def main():
    if len(sys.argv) != 5: # NUM_PARTIES, TX_SPACE_BITS, BF_LOG2, VOTES_PER_PARTY
        print("Usage: python3 generate_local_tree.py <NUM_PARTIES> <TRANSACTION_SPACE_BITS> <BRANCH_FACTOR_LOG2> <VOTES_PER_PARTY>")
        sys.exit(1)

    try:
        num_parties = int(sys.argv[1])
        transaction_space_bits = int(sys.argv[2])
        branch_factor_log2 = int(sys.argv[3])
        votes_per_party = int(sys.argv[4])
    except ValueError:
        print("Error: All arguments must be integers.")
        sys.exit(1)

    if num_parties <= 0 or transaction_space_bits < 0 or branch_factor_log2 <= 0 or votes_per_party < 0:
        print("Error: Invalid arguments. NUM_PARTIES > 0, TRANSACTION_SPACE_BITS >= 0, BRANCH_FACTOR_LOG2 > 0, VOTES_PER_PARTY >= 0.")
        sys.exit(1)

    print(f"--- Generating Local Tree Counts for MPC Input ({num_parties} Parties) ---")
    print(f"Config: TX Space Bits={transaction_space_bits}, Branch Factor Log2={branch_factor_log2}, Expected Votes/Party From Prev Step={votes_per_party}")

    mempool_full_tx_list_from_json = load_mempool_tx_strings_from_json()
    if not mempool_full_tx_list_from_json and transaction_space_bits > 0:
        print("Warning: Public mempool definition is empty but TRANSACTION_SPACE_BITS > 0. Canonical prefixes might be limited.")

    canonical_keys = generate_canonical_prefix_keys(mempool_full_tx_list_from_json, transaction_space_bits, branch_factor_log2)
    num_slots_per_party = len(canonical_keys)

    if num_slots_per_party == 0 :
         print("Error: No canonical prefix keys generated. Check mempool or config.")
         sys.exit(1)
    
    print(f"Generated {num_slots_per_party} canonical prefix slots for MPC input structure.")

    for p_idx in range(num_parties):
        print(f"\n--- Processing Party {p_idx} ---")
        
        # Load this party's selected transactions (list of binary strings)
        # This now reads from Input-P<p_idx>-1 (or the file where generate_inputs.py places binary strings)
        party_selected_tx_bin_list = load_party_selected_tx_strings_from_mpc_input_file(p_idx, votes_per_party)
        
        actual_selected_count = len(party_selected_tx_bin_list)
        print(f"  Party {p_idx} has selected {actual_selected_count} transactions.")
        if actual_selected_count == 0 and votes_per_party > 0:
            print(f"  Warning: Party {p_idx} selected 0 transactions, but {votes_per_party} were expected. Counts will be 0.")
        
        party_mpc_input_counts = [0] * num_slots_per_party

        for key_idx, key_info in enumerate(canonical_keys):
            prefix_to_check = key_info['prefix_str']
            current_slot_count = 0
            
            if key_info['level'] == 0:
                current_slot_count = actual_selected_count
            else:
                for party_tx_bin in party_selected_tx_bin_list:
                    if len(party_tx_bin) >= key_info['prefix_len'] and \
                       party_tx_bin.startswith(prefix_to_check):
                        current_slot_count += 1
            party_mpc_input_counts[key_idx] = current_slot_count

        # This script now writes the MPC inputs (flat list of counts) to Player-Data/Input-P<p_idx>-0
        mpc_input_file_for_party = os.path.join("Player-Data", f"Input-P{p_idx}-0")
        try:
            with open(mpc_input_file_for_party, 'w') as f_out:
                for count_val in party_mpc_input_counts:
                    f_out.write(str(count_val) + '\n')
            print(f"  Successfully wrote {len(party_mpc_input_counts)} local counts for Party {p_idx} to {mpc_input_file_for_party} (for MPC).")
        except IOError as e:
            print(f"  Error writing MPC input file {mpc_input_file_for_party} for Party {p_idx}: {e}")

        # Optional: Print human-readable local tree for review
        print(f"  Party {p_idx} Local Tree (for review based on canonical prefixes):")
        # ... (rest of the review printing logic can remain the same as before) ...
        # (For brevity, I'll skip pasting that part again, it should work if party_mpc_input_counts is correct)
        root_review_count_idx = -1
        for key_idx_find_root, ki_find_root in enumerate(canonical_keys):
            if ki_find_root['level'] == 0:
                root_review_count_idx = key_idx_find_root
                break
        if root_review_count_idx != -1:
            print(f"    Root level counts: {party_mpc_input_counts[root_review_count_idx]}")
        
        # Logic to print other levels based on party_mpc_input_counts and canonical_keys
        # This can be complex to format exactly like your desired text tree from flat counts.
        # The core is that party_mpc_input_counts should now have correct non-zero values.
        # For example:
        current_printed_level = 0
        for key_idx in range(num_slots_per_party):
            key_info = canonical_keys[key_idx]
            count = party_mpc_input_counts[key_idx]
            if key_info['level'] == 0: continue # Already printed root

            if key_info['level'] != current_printed_level:
                current_printed_level = key_info['level']
                # Collect all prefixes for this level that have counts
                level_dict_for_print = {}
                for inner_key_idx in range(key_idx, num_slots_per_party):
                    inner_key_info = canonical_keys[inner_key_idx]
                    if inner_key_info['level'] != current_printed_level:
                        break # Moved to next level in canonical_keys
                    if party_mpc_input_counts[inner_key_idx] > 0:
                        level_dict_for_print[inner_key_info['prefix_str']] = party_mpc_input_counts[inner_key_idx]
                
                if level_dict_for_print:
                    dict_items_str = [f"'{k}': {v}" for k, v in sorted(level_dict_for_print.items())]
                    print(f"    Level {current_printed_level} (Prefix Len approx: {key_info['prefix_len']}): {{{', '.join(dict_items_str)}}}")


    print(f"\n--- Local count file generation for MPC input complete ---")

if __name__ == "__main__":
    main()