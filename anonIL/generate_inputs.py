# generate_inputs.py
# usage: python3 generate_inputs.py NUM_PARTIES VOTES_PER_PARTY
import sys
import random
import json
import os

# Fixed random seed for reproducibility
RANDOM_SEED = 1337

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 generate_inputs.py <NUM_PARTIES> <VOTES_PER_PARTY>")
        sys.exit(1)

    try:
        num_parties = int(sys.argv[1])
        votes_per_party = int(sys.argv[2])
    except ValueError:
        print("Error: Both arguments must be integers.")
        sys.exit(1)

    if num_parties <= 0 or votes_per_party < 0:
        print("Error: NUM_PARTIES must be positive and VOTES_PER_PARTY must be non-negative.")
        sys.exit(1)

    random.seed(RANDOM_SEED)
    print(f"Using fixed random seed: {RANDOM_SEED}")

    # --- Load Mempool (list of integers) ---
    mempool_file = os.path.join("Player-Data", "mempool_definition.json")
    mempool_tx_ids = []
    try:
        with open(mempool_file, 'r') as f:
            data = json.load(f)
            mempool_tx_ids = data["mempool_tx_ids"]
    except (FileNotFoundError, KeyError) as e:
        print(f"Error: Could not read mempool from {mempool_file}. Run generate_mempool.py first. Error: {e}")
        sys.exit(1)

    if not mempool_tx_ids and votes_per_party > 0:
        print("Warning: Mempool is empty, but VOTES_PER_PARTY > 0. Parties will have no votes.")
        votes_per_party = 0

    if votes_per_party > len(mempool_tx_ids):
        print(f"Warning: VOTES_PER_PARTY ({votes_per_party}) > mempool size ({len(mempool_tx_ids)}). "
              f"Each party will vote for all transactions.")
        votes_per_party = len(mempool_tx_ids)

    # --- Generate inputs for each party ---
    output_dir = "Player-Data"
    os.makedirs(output_dir, exist_ok=True)

    for i in range(num_parties):
        party_votes = random.sample(mempool_tx_ids, votes_per_party)
        print(f"Party {i} votes: {party_votes}")

        # This "raw_votes" file is read by prepare_iteration_inputs.py
        output_file = os.path.join(output_dir, f"Input-P{i}-1")

        try:
            with open(output_file, 'w') as f:
                for tx_id in party_votes:
                    f.write(str(tx_id) + '\n')
            print(f"Generated {len(party_votes)} votes for Party {i} and saved to {output_file}")
        except IOError as e:
            print(f"Error writing to file {output_file}: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
