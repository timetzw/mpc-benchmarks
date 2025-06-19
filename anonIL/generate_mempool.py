# generate_mempool.py
# usage: python3 generate_mempool.py TRANSACTION_SPACE_BITS MEMPOOL_SIZE
import sys
import random
import json
import os

# Fixed random seed for reproducibility
RANDOM_SEED = 42

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 generate_mempool.py <TRANSACTION_SPACE_BITS> <MEMPOOL_SIZE>")
        sys.exit(1)

    try:
        transaction_space_bits = int(sys.argv[1])
        mempool_size = int(sys.argv[2])
    except ValueError:
        print("Error: Both arguments must be integers.")
        sys.exit(1)

    if transaction_space_bits < 0 or mempool_size < 0:
        print("Error: TRANSACTION_SPACE_BITS and MEMPOOL_SIZE cannot be negative.")
        sys.exit(1)

    # If TSB is 0, there is only one possible transaction, represented as integer 0.
    max_possible_txs = 1 if transaction_space_bits == 0 else 2**transaction_space_bits

    if mempool_size > max_possible_txs:
        print(f"Error: MEMPOOL_SIZE ({mempool_size}) cannot exceed the maximum possible unique transactions "
              f"for {transaction_space_bits} bits, which is {max_possible_txs}.")
        sys.exit(1)

    random.seed(RANDOM_SEED)
    print(f"Using fixed random seed: {RANDOM_SEED}")

    # Generate a set of unique random integers
    if transaction_space_bits == 0:
        generated_tx_ids_set = {0} if mempool_size >= 1 else set()
    else:
        # random.sample is efficient for generating unique elements
        population = range(max_possible_txs)
        generated_tx_ids_set = set(random.sample(population, mempool_size))

    mempool_tx_ids_sorted = sorted(list(generated_tx_ids_set))

    output_dir = "Player-Data"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "mempool_definition.json")

    try:
        with open(output_file, 'w') as f:
            # The mempool is now a JSON object containing a list of integers
            json.dump({"mempool_tx_ids": mempool_tx_ids_sorted}, f, indent=4)
        print(f"Successfully generated {len(mempool_tx_ids_sorted)} unique integer transactions.")
        print(f"Mempool definition (list of integers) saved to: {output_file}")
    except IOError as e:
        print(f"Error writing to file {output_file}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
