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

    if transaction_space_bits < 0:
        print("Error: TRANSACTION_SPACE_BITS cannot be negative.")
        sys.exit(1)
    if mempool_size < 0:
        print("Error: MEMPOOL_SIZE cannot be negative.")
        sys.exit(1)

    if transaction_space_bits == 0:
        max_possible_txs = 1 # Only one possible "transaction": the empty string ""
    else:
        max_possible_txs = 2**transaction_space_bits

    if mempool_size > max_possible_txs:
        print(f"Error: MEMPOOL_SIZE ({mempool_size}) cannot exceed the maximum possible unique transactions "
              f"for {transaction_space_bits} bits, which is {max_possible_txs}.")
        sys.exit(1)

    random.seed(RANDOM_SEED)
    print(f"Using fixed random seed: {RANDOM_SEED}")

    generated_binary_txs_set = set()
    
    if transaction_space_bits == 0:
        if mempool_size >= 1:
            generated_binary_txs_set.add("")
    else:
        attempts = 0
        # Heuristic to prevent potential infinite loop if mempool_size is pathologically close to max_possible_txs
        # and random generation is unlucky for a long time.
        max_attempts = mempool_size * 100 + 1000 
        while len(generated_binary_txs_set) < mempool_size:
            attempts += 1
            if attempts > max_attempts and mempool_size > 0:
                print(f"Warning: Could not generate {mempool_size} unique transactions after {max_attempts} attempts. "
                      f"Generated {len(generated_binary_txs_set)} instead. Check parameters (e.g., if mempool_size is too close to 2^bits).")
                break
            
            random_int = random.randint(0, (2**transaction_space_bits) - 1)
            binary_tx = format(random_int, f'0{transaction_space_bits}b')
            generated_binary_txs_set.add(binary_tx)

    # Convert set of binary strings to a sorted list of binary strings
    mempool_tx_ids_binary_sorted = sorted(list(generated_binary_txs_set))

    output_dir = "Player-Data"
    output_file = os.path.join(output_dir, "mempool_definition.json")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    try:
        with open(output_file, 'w') as f:
            json.dump(mempool_tx_ids_binary_sorted, f, indent=4)
        print(f"Successfully generated {len(mempool_tx_ids_binary_sorted)} unique binary transactions.")
        print(f"Mempool definition (list of binary strings) saved to: {output_file}")
        # print(f"Sample transactions (binary): {mempool_tx_ids_binary_sorted[:10]}")
    except IOError as e:
        print(f"Error writing to file {output_file}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()