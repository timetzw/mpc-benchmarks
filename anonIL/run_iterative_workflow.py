# run_iterative_workflow.py
import sys
import os
import json
import math
import subprocess
import time

# --- Compute expected outcome ---

def compute_expected_outcome():
    """
    Compute the expected outcome by reading the initial vote data from Player-Data/Input-P*-1
    and determining which transaction IDs meet the minimum vote threshold.
    """
    print("\n--- Computing Expected Outcome (Based on Initial Votes) ---")
    
    # Dictionary to store vote counts for each transaction ID
    vote_counts = {}
    
    # Read votes from each party
    for party_id in range(NUM_PARTIES):
        input_file = f"Player-Data/Input-P{party_id}-1"
        if not os.path.exists(input_file):
            print(f"Warning: Input file {input_file} not found, skipping party {party_id}")
            continue
        
        with open(input_file, 'r') as f:
            party_votes = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        tx_id = int(line)
                        party_votes.append(tx_id)
                        # Count votes for this transaction ID
                        vote_counts[tx_id] = vote_counts.get(tx_id, 0) + 1
                    except ValueError:
                        continue
        
        print(f"Party {party_id} votes: {party_votes}")
    
    # Determine which transactions meet the threshold
    expected_included_txs = set()
    print(f"\nVote summary (threshold >= {MIN_VOTES_THRESHOLD}):")
    
    for tx_id in sorted(vote_counts.keys()):
        votes = vote_counts[tx_id]
        status = "INCLUDED" if votes >= MIN_VOTES_THRESHOLD else "EXCLUDED"
        # print(f"  TX ID {tx_id}: {votes} votes - {status}")
        
        if votes >= MIN_VOTES_THRESHOLD:
            expected_included_txs.add(tx_id)
    
    print(f"\nExpected final inclusion list: {sorted(list(expected_included_txs))}")
    return expected_included_txs


# --- Configuration ---
def get_env_int(var_name, default, positive=False, can_be_zero=False):
    val_str = os.environ.get(var_name, str(default))
    try:
        val = int(val_str)
        if positive and val <= 0: return default
        if not can_be_zero and val < 0: return default
        return val
    except ValueError:
        return default

NUM_PARTIES = get_env_int('NUM_PARTIES', 4, positive=True)
TRANSACTION_SPACE_BITS = get_env_int('TRANSACTION_SPACE_BITS', 3, can_be_zero=True)
BRANCH_FACTOR_LOG2 = get_env_int('BRANCH_FACTOR_LOG2', 1, positive=True)
MIN_VOTES_THRESHOLD = get_env_int('MIN_VOTES_THRESHOLD', 2, can_be_zero=True)
VOTES_PER_PARTY = get_env_int('VOTES_PER_PARTY', 3)
MEMPOOL_SIZE = get_env_int('MEMPOOL_SIZE', 8)

# This calculation MUST match the .mpc script
MAX_PREFIX_SLOTS_EFFECTIVE = 1 if MEMPOOL_SIZE == 0 else max(1, MEMPOOL_SIZE * (2**BRANCH_FACTOR_LOG2))

print("--- Orchestrator Configuration ---")
# ... (print statements for config) ...

CANDIDATE_PREFIXES_FILE_JSON = "Player-Data/current_iteration_candidates.json"
COMPILED_MPC_PROGRAM_BASE = "anonymous_inclusion_iterative"

def run_command(command, stage_name):
    """Executes a helper script and handles its output."""
    print(f"Orchestrator: Running {stage_name}: {' '.join(command)}")
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    
    if proc.returncode != 0:
        print(f"CRITICAL Error from {stage_name}:")
        print(proc.stdout)
        print(proc.stderr)
        sys.exit(1)
    
    return proc.stdout

def execute_mpc_computation(num_parties, program_base, iteration_level, protocol_name):
    """
    Executes the MPC computation by calling the high-level shamir.sh script.
    """
    mpc_env = os.environ.copy()
    mpc_env['PLAYERS'] = str(num_parties)

    full_program_name = f"{program_base}-{num_parties}"
    script_path = f"Scripts/{protocol_name}.sh"
    
    if not os.path.exists(script_path):
        print(f"CRITICAL: MPC script '{script_path}' not found.")
        sys.exit(1)

    cmd = [script_path, full_program_name]
    print(f"Orchestrator: Current cmd: {cmd}")
    print(f"Orchestrator: Running MPC via '{' '.join(cmd)}'")

    process = subprocess.run(cmd, capture_output=True, text=True, env=mpc_env, check=False)

    # --- START: Added log saving logic ---
    log_file_path = f"Logs/mpc_run.log"
    with open(log_file_path, 'a') as log_file:
        log_file.write(f"\n===== Iteration Level {iteration_level} =====\n")
        log_file.write(f"--- STDOUT from {protocol_name}.sh ---\n")
        log_file.write(process.stdout)
        log_file.write(f"\n--- STDERR from {protocol_name}.sh ---\n")
        log_file.write(process.stderr)
        log_file.write("=" * 30 + "\n")
    # --- END: Added log saving logic ---

    if process.returncode != 0:
        print("CRITICAL: MPC script execution failed!")
        print(f"--- STDOUT from {protocol_name}.sh ---")
        print(process.stdout)
        print(f"--- STDERR from {protocol_name}.sh ---")
        print(process.stderr)
        sys.exit(1)

    # SUCCESS: Return the captured standard output, which contains the MPC results.
    return process.stdout

def generate_child_prefixes(parent_info, level, max_bits, bf_log2):
    """Generates all child prefixes for a given parent."""
    children = []
    parent_prefix = parent_info['prefix_str']
    parent_len = parent_info['prefix_len']
    if parent_len >= max_bits: return []
    
    num_new_bits = min(bf_log2, max_bits - parent_len)
    if num_new_bits <= 0: return []

    for i in range(2**num_new_bits):
        suffix = format(i, f'0{num_new_bits}b')
        child_prefix = parent_prefix + suffix
        children.append({'level': level, 'prefix_len': len(child_prefix), 'prefix_str': child_prefix})
    return children


def main():
    print("--- Orchestrator: Starting Workflow ---")
    os.makedirs("Player-Data", exist_ok=True)
    os.makedirs("Logs", exist_ok=True)
    print("\n--- Stage 0: Initial Data Generation ---")
    run_command(["python3", "generate_mempool.py", str(TRANSACTION_SPACE_BITS), str(MEMPOOL_SIZE)], "Mempool Generation")
    run_command(["python3", "generate_inputs.py", str(NUM_PARTIES), str(VOTES_PER_PARTY)], "Party Votes Generation")
    # Remove the log file
    if os.path.exists(f"Logs/mpc_run.log"):
        os.remove(f"Logs/mpc_run.log")
    # Read protocol name from the terminal, so the program should run like: python3 run_iterative_workflow.py protocol_name
    protocol_name = sys.argv[1]
    print(f"Orchestrator: Running protocol {protocol_name}")

    level = 0
    passing_prefixes = [{'level': 0, 'prefix_len': 0, 'prefix_str': ""}]
    final_tx_ids = set()
    max_level = math.ceil(TRANSACTION_SPACE_BITS / BRANCH_FACTOR_LOG2) if BRANCH_FACTOR_LOG2 > 0 else 0

    start_time = time.monotonic()
    while level <= max_level and passing_prefixes:
        print(f"\n--- Iteration: Processing Level {level} ---")
        
        candidates = []
        if level == 0:
            candidates = passing_prefixes
        else:
            for parent in passing_prefixes:
                candidates.extend(generate_child_prefixes(parent, level, TRANSACTION_SPACE_BITS, BRANCH_FACTOR_LOG2))
        
        num_active = len(candidates)
        if num_active == 0:
            print("No more candidate prefixes to process. Stopping.")
            break
        print(f"Level {level}: Generated {num_active} candidate prefixes.")

        with open(CANDIDATE_PREFIXES_FILE_JSON, 'w') as f:
            json.dump({"candidate_prefixes_info": candidates, "num_active_prefixes": num_active}, f)
        for i in range(NUM_PARTIES):
            run_command(["python3", "prepare_iteration_inputs.py", str(i), CANDIDATE_PREFIXES_FILE_JSON, 
                        str(TRANSACTION_SPACE_BITS)], f"Input Prep P{i}")



        mpc_log = execute_mpc_computation(NUM_PARTIES, COMPILED_MPC_PROGRAM_BASE, level, protocol_name)

        print(f"Orchestrator: Parsing MPC output and applying threshold (>{MIN_VOTES_THRESHOLD-1} votes)...")
        new_passing_prefixes = []
        for line in mpc_log.splitlines():
            if line.startswith("RAW_ITERATION_RESULT:"):
                try:
                    parts = {p.split('=')[0]: p.split('=')[1] for p in line.split()[1:]}
                    slot_idx = int(parts["SlotIndex"])
                    votes = int(parts["GlobalVotes"])

                    if slot_idx < num_active and votes >= MIN_VOTES_THRESHOLD:
                        passing_candidate = candidates[slot_idx]
                        new_passing_prefixes.append(passing_candidate)
                        
                        if passing_candidate['prefix_len'] == TRANSACTION_SPACE_BITS:
                            prefix_str = passing_candidate['prefix_str']
                            tx_id = int(prefix_str, 2) if prefix_str else 0
                            final_tx_ids.add(tx_id)
                            print(f"  --> FINAL TX: ID {tx_id} (prefix '{prefix_str}') with {votes} votes.")
                except (ValueError, KeyError, IndexError) as e:
                    print(f"Warning: Could not parse result line '{line}': {e}")
                    continue
        
        passing_prefixes = new_passing_prefixes
        print(f"Level {level}: Found {len(passing_prefixes)} prefixes for next level.")
        level += 1

    end_time = time.monotonic()
    print(f"MPC Workflow completed in {end_time - start_time:.2f} seconds")

    print("\n--- Workflow Complete ---")
    print("Final Anonymous Inclusion List (Unique TX IDs):")
    if final_tx_ids:
        for tx_id in sorted(list(final_tx_ids)):
            print(f"  - TX ID: {tx_id}")
    else:
        print("  No transactions met the final threshold.")

    # Compute expected outcome
    expected_outcome = compute_expected_outcome()
    print(f"Expected outcome: {expected_outcome}")

if __name__ == "__main__":
    main()
