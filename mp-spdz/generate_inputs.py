# generate_inputs.py
# This script generates input files for MP-SPDZ.
# Each party randomly selects transactions (as binary strings) from the mempool.
# The selected BINARY STRINGS themselves are written to the party's input file,
# one binary string per line, in sorted order.
#
# !!! IMPORTANT !!!
# This output format (files containing binary strings like "010", "111")
# is NOT directly compatible with MP-SPDZ's standard `sint.get_input_from()`
# if that function is expected to read integers or individual bits for secret sharing.
# You will need a custom mechanism in your .mpc script to read and process these strings.
#

import sys
import random
import json
import os

# Fixed random seed for reproducibility of party inputs
RANDOM_SEED = 123 # Consistent seed for input generation

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 generate_inputs.py <NUM_PARTIES> <VOTES_PER_PARTY>")
        sys.exit(1)

    try:
        num_parties = int(sys.argv[1])
        votes_per_party = int(sys.argv[2])
    except ValueError:
        print("Error: Both NUM_PARTIES and VOTES_PER_PARTY must be integers.")
        sys.exit(1)

    if num_parties <= 0:
        print("Error: NUM_PARTIES must be a positive integer.")
        sys.exit(1)
    if votes_per_party < 0: # Allow 0 votes, resulting in empty files
        print("Error: VOTES_PER_PARTY cannot be negative.")
        sys.exit(1)

    random.seed(RANDOM_SEED)
    print(f"Using fixed random seed for input generation: {RANDOM_SEED}")

    mempool_file_path = os.path.join("Player-Data", "mempool_definition.json")
    mempool_tx_binary_strings = []

    try:
        with open(mempool_file_path, 'r') as f:
            loaded_data = json.load(f)
        if not isinstance(loaded_data, list) or \
           not all(isinstance(tx, str) for tx in loaded_data):
            print(f"Error: Mempool definition in {mempool_file_path} is not a list of binary strings.")
        else:
            mempool_tx_binary_strings = loaded_data
        print(f"Loaded {len(mempool_tx_binary_strings)} transactions (binary strings) from mempool: {mempool_tx_binary_strings[:5]}...")
    except FileNotFoundError:
        print(f"Error: Mempool file {mempool_file_path} not found. Cannot generate inputs.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Could not decode JSON from {mempool_file_path}: {e}")
        sys.exit(1)

    if not mempool_tx_binary_strings and votes_per_party > 0:
        print("Warning: Mempool is empty, but votes_per_party > 0. Input files will be empty.")
    
    num_available_txs_in_mempool = len(mempool_tx_binary_strings)
    
    transaction_space_bits = 0 # Default if mempool is empty
    if num_available_txs_in_mempool > 0:
        transaction_space_bits = len(mempool_tx_binary_strings[0])
        if not all(len(tx) == transaction_space_bits for tx in mempool_tx_binary_strings):
            print(f"Warning: Transactions in mempool definition have inconsistent lengths. Expected all to be {transaction_space_bits} bits based on the first transaction. This might lead to issues.")


    for i in range(num_parties):
        party_input_filename = os.path.join("Player-Data", f"Input-P{i}-1")
        selected_tx_strings_for_party = []

        if votes_per_party > 0 and num_available_txs_in_mempool > 0:
            num_to_select = min(votes_per_party, num_available_txs_in_mempool)
            if votes_per_party > num_available_txs_in_mempool:
                print(f"Warning: Party {i} wants to vote for {votes_per_party} TXs, "
                      f"but only {num_available_txs_in_mempool} are available. Selecting all {num_available_txs_in_mempool}.")
            
            # Randomly select transactions
            randomly_selected_txs = random.sample(mempool_tx_binary_strings, num_to_select)
            
            # Sort the selected transactions before assigning
            selected_tx_strings_for_party = sorted(randomly_selected_txs)
            
            print(f"Party {i} selected TXs (binary strings, sorted): {selected_tx_strings_for_party}")
        
        try:
            with open(party_input_filename, 'w') as f:
                for binary_tx_str in selected_tx_strings_for_party:
                    f.write(binary_tx_str + '\n') # Write the binary string itself
            print(f"Generated input file for Party {i}: {party_input_filename} with {len(selected_tx_strings_for_party)} TX binary strings.")
        except IOError as e:
            print(f"Error writing to input file {party_input_filename}: {e}")
            sys.exit(1)

    print("Input generation complete for all parties.")
    print("IMPORTANT: The generated Input-P<X>-1 files now contain one *sorted* binary string per line.")
    print("Your MP-SPDZ script's input phase must be adapted to handle this format (reading strings).")

if __name__ == "__main__":
    main()