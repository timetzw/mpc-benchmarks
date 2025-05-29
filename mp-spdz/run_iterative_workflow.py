# run_iterative_workflow.py
import sys
import os
import json
import math
import subprocess
import time

# --- Configuration (Read from Environment Variables - these are set by Dockerfile ARGs -> ENVs) ---
def get_env_int_orchestrator(var_name, default_val_str, positive=False, can_be_zero_sometimes=False):
    val_str = os.environ.get(var_name, default_val_str)
    default_val = int(default_val_str)
    try:
        val_int = int(val_str)
        if positive and val_int <= 0:
            print(f"[Orchestrator WARNING] ENV VAR {var_name} ('{val_str}') should be positive. Using default {default_val_str}.")
            return default_val
        if not can_be_zero_sometimes and val_int < 0 : # General check for negative
             print(f"[Orchestrator WARNING] ENV VAR {var_name} ('{val_str}') is negative. Using default {default_val_str}.")
             return default_val
        return val_int
    except ValueError:
        print(f"[Orchestrator WARNING] ENV VAR {var_name} ('{val_str}') is not an int. Using default {default_val_str}.")
        return default_val

NUM_PARTIES = get_env_int_orchestrator('NUM_PARTIES', '4', positive=True)
TRANSACTION_SPACE_BITS = get_env_int_orchestrator('TRANSACTION_SPACE_BITS', '40', can_be_zero_sometimes=True)
BRANCH_FACTOR_LOG2 = get_env_int_orchestrator('BRANCH_FACTOR_LOG2', '2', positive=True)
MIN_VOTES_THRESHOLD = get_env_int_orchestrator('MIN_VOTES_THRESHOLD', '2', can_be_zero_sometimes=True)
VOTES_PER_PARTY = get_env_int_orchestrator('VOTES_PER_PARTY', '10')
MEMPOOL_SIZE = get_env_int_orchestrator('MEMPOOL_SIZE', '15')

# Calculate effective MAX_PREFIX_SLOTS based on MEMPOOL_SIZE and BRANCH_FACTOR_LOG2
# This MUST match the calculation done in the .mpc script's compile-time section.
if BRANCH_FACTOR_LOG2 <= 0: # BRANCH_FACTOR_LOG2 must be positive for meaningful prefix generation
    print("CRITICAL ERROR: BRANCH_FACTOR_LOG2 from ENV must be positive for MAX_PREFIX_SLOTS calculation.")
    sys.exit(1)
effective_bf_for_calc = BRANCH_FACTOR_LOG2

# Mirrors the logic in the MPC script for MAX_PREFIX_SLOTS
if MEMPOOL_SIZE == 0 and TRANSACTION_SPACE_BITS == 0: # Only root prefix ""
    MAX_PREFIX_SLOTS_EFFECTIVE = 1
elif MEMPOOL_SIZE == 0 and TRANSACTION_SPACE_BITS > 0: # No mempool items to derive prefixes from beyond root
    MAX_PREFIX_SLOTS_EFFECTIVE = 1 # Only root will be processed by orchestrator initially
else: # MEMPOOL_SIZE > 0
    MAX_PREFIX_SLOTS_EFFECTIVE = max(1, MEMPOOL_SIZE * (2**effective_bf_for_calc))


print(f"--- Orchestrator Initial Configuration ---")
print(f"NUM_PARTIES: {NUM_PARTIES}")
print(f"TRANSACTION_SPACE_BITS: {TRANSACTION_SPACE_BITS}")
print(f"BRANCH_FACTOR_LOG2: {BRANCH_FACTOR_LOG2}")
print(f"MIN_VOTES_THRESHOLD: {MIN_VOTES_THRESHOLD}")
print(f"VOTES_PER_PARTY (for generate_inputs): {VOTES_PER_PARTY}")
print(f"MEMPOOL_SIZE (for generate_mempool & MAX_PREFIX_SLOTS base): {MEMPOOL_SIZE}")
print(f"MAX_PREFIX_SLOTS_EFFECTIVE (for MPC arrays & checks): {MAX_PREFIX_SLOTS_EFFECTIVE}")
print(f"------------------------------------")

MEMPOOL_DEF_FILE = "Player-Data/mempool_definition.json"
CANDIDATE_PREFIXES_FILE_JSON = "Player-Data/current_iteration_candidates.json"
# This is the base name of the MPC program compiled in your Dockerfile
COMPILED_MPC_PROGRAM_BASE = "anonymous_inclusion_iterative"

def generate_child_prefixes_from_parent(parent_prefix_str, parent_prefix_len, target_level_num, global_max_tx_bits, bf_log2):
    children = []
    if parent_prefix_len >= global_max_tx_bits and global_max_tx_bits > 0:
        return [] # Already at max length
    if global_max_tx_bits == 0 and parent_prefix_len == 0 :
        return [] # No children if TSB is 0 (only root prefix "" which is handled as a candidate itself)

    num_new_bits_to_add = bf_log2
    # Ensure we don't exceed global_max_tx_bits
    if parent_prefix_len + num_new_bits_to_add > global_max_tx_bits:
        num_new_bits_to_add = global_max_tx_bits - parent_prefix_len

    if num_new_bits_to_add <= 0: # No more bits to add
        return []

    actual_child_prefix_len = parent_prefix_len + num_new_bits_to_add
    for i in range(2**num_new_bits_to_add):
        child_suffix = format(i, f'0{num_new_bits_to_add}b')
        child_prefix_str = parent_prefix_str + child_suffix
        children.append({'level': target_level_num, 'prefix_len': actual_child_prefix_len, 'prefix_str': child_prefix_str})
    return children

def run_command(command_list, stage_name="Command"):
    """Executes helper scripts (like generate_mempool.py) and handles output."""
    print(f"Orchestrator: Running {stage_name}: {' '.join(command_list)}")
    process = subprocess.run(command_list, capture_output=True, text=True, check=False)
    print(f"--- Output from {stage_name} ---")
    stdout_lines = process.stdout.splitlines()
    stderr_lines = process.stderr.splitlines()

    if process.stdout:
        print("STDOUT:")
        if len(stdout_lines) > 20 and process.returncode == 0:
            for line in stdout_lines[:5]: print(line)
            print(f"... (stdout truncated - {len(stdout_lines) - 10} more lines) ...")
            for line in stdout_lines[-5:]: print(line)
        else:
            for line in stdout_lines: print(line)

    if process.stderr:
        print("STDERR:")
        for line in stderr_lines: print(line)

    print(f"--- End Output from {stage_name} (Return Code: {process.returncode}) ---")
    if process.returncode != 0:
        print(f"CRITICAL Error: {stage_name} failed with exit code {process.returncode}.")
        sys.exit(1)
    return process.stdout

def execute_mpc_computation(num_parties, compiled_mpc_program_base,
                            mpc_party_executable_name="shamir-party.x",
                            base_port=14000):
    """
    Manages the execution of the MP-SPDZ MPC computation.
    Launches parties, waits for completion, and returns P0's log content.
    """
    full_program_name = f"{compiled_mpc_program_base}-{num_parties}"
    log_dir = "Logs"
    os.makedirs(log_dir, exist_ok=True)

    mpc_executable_path = ""
    # Common locations for MP-SPDZ party executables
    possible_paths = [
        f"./{mpc_party_executable_name}",
        f"./Parties/{mpc_party_executable_name}",
        f"./{mpc_party_executable_name.replace('.x', '.sh')}", # Check for .sh wrapper
        f"./Parties/{mpc_party_executable_name.replace('.x', '.sh')}"
    ]
    for path_option in possible_paths:
        if os.path.isfile(path_option) and os.access(path_option, os.X_OK):
            mpc_executable_path = path_option
            break

    if not mpc_executable_path:
        print(f"CRITICAL Error: MPC executable '{mpc_party_executable_name}' not found or not executable "
              f"in checked locations: {possible_paths}")
        print(f"Current working directory: {os.getcwd()}")
        if os.path.exists("."): print(f"Files in '.': {os.listdir('.')}")
        if os.path.exists("Parties"): print(f"Files in 'Parties': {os.listdir('Parties')}")
        sys.exit(1)
    print(f"Orchestrator: Using MPC executable at '{mpc_executable_path}'")

    for i in range(num_parties):
        log_file_path = os.path.join(log_dir, f"P{i}_{full_program_name}.log")
        if os.path.exists(log_file_path):
            try:
                os.remove(log_file_path)
            except OSError as e:
                print(f"Warning: Could not remove old log file {log_file_path}: {e}")

    party_processes_info = []
    print(f"Orchestrator: Launching {num_parties} MPC parties for program '{full_program_name}'. Base port: {base_port}")

    for i in range(num_parties):
        party_id = i
        log_file_path = os.path.join(log_dir, f"P{party_id}_{full_program_name}.log")
        command = [
            mpc_executable_path,
            "-p", str(party_id),
            "-N", str(num_parties),
            "-pn", str(base_port),
            full_program_name
        ]
        print(f"Orchestrator: Launching Party {party_id}: {' '.join(command)} > {log_file_path}")
        try:
            log_file_handle = open(log_file_path, 'w')
            process = subprocess.Popen(command, stdout=log_file_handle, stderr=subprocess.STDOUT)
            party_processes_info.append({
                'id': party_id,
                'process': process,
                'log_file': log_file_path,
                'log_handle': log_file_handle
            })
        except Exception as e:
            print(f"CRITICAL Error launching Party {party_id}: {e}")
            for p_info in party_processes_info: # Cleanup already started
                if p_info['process'].poll() is None: p_info['process'].kill()
                p_info['log_handle'].close()
            sys.exit(1)
        time.sleep(0.1)

    print(f"Orchestrator: All {num_parties} parties launched. Waiting for completion...")
    all_successful = True
    for p_info in party_processes_info:
        player_id, process, log_file, log_handle = p_info['id'], p_info['process'], p_info['log_file'], p_info['log_handle']
        print(f"Orchestrator: Waiting for Party {player_id} (PID {process.pid}) to complete...")
        try:
            process.wait()
            log_handle.close()
            return_code = process.returncode
            print(f"Orchestrator: Party {player_id} finished with status {return_code}. Log: {log_file}")
            if return_code != 0:
                all_successful = False
                print(f"Orchestrator: ***** ERROR DETECTED FOR PARTY {player_id} *****")
        except Exception as e:
            print(f"Orchestrator: ***** EXCEPTION WAITING FOR PARTY {player_id} (PID {process.pid}) *****: {e}")
            all_successful = False
            if process.poll() is None: process.kill()
            if not log_handle.closed: log_handle.close()


    if not all_successful:
        print("CRITICAL Error: One or more MPC parties failed. Check logs in 'Logs' directory:")
        for p_info in party_processes_info:
            if p_info['process'].returncode != 0:
                print(f"--- Error Log for Party {p_info['id']} ({p_info['log_file']}) ---")
                try:
                    with open(p_info['log_file'], 'r') as f_err_log:
                        lines = f_err_log.read().splitlines()
                        if len(lines) > 20:
                            for line_idx, line_content in enumerate(lines):
                                if line_idx < 10 or line_idx >= len(lines) - 10: print(line_content)
                                elif line_idx == 10: print("...")
                        else:
                            for line_content in lines: print(line_content)
                except Exception as e_log:
                    print(f"Could not read error log {p_info['log_file']}: {e_log}")
                print("--- End Error Log ---")
        sys.exit(1)

    print("Orchestrator: All MPC parties finished successfully.")
    p0_log_file = os.path.join(log_dir, f"P0_{full_program_name}.log")
    mpc_output_log_content = ""
    try:
        with open(p0_log_file, 'r') as f:
            mpc_output_log_content = f.read()
        print(f"Orchestrator: Successfully read P0 log: {p0_log_file}")
    except Exception as e:
        print(f"CRITICAL Error reading P0 log file '{p0_log_file}': {e}")
        sys.exit(1)
    return mpc_output_log_content

def main():
    print("--- Orchestrator: Starting Anonymous Inclusion Workflow ---")
    if not os.path.exists("Player-Data"):
        os.makedirs("Player-Data")
        print("Created Player-Data directory.")

    print("\n--- Stage 0: Initial Data Generation ---")
    run_command(["python3", "./generate_mempool.py", str(TRANSACTION_SPACE_BITS), str(MEMPOOL_SIZE)], "Mempool Generation")
    print(f"Orchestrator: For generate_inputs.py, using NUM_PARTIES={NUM_PARTIES}, VOTES_PER_PARTY={VOTES_PER_PARTY}")
    run_command(["python3", "./generate_inputs.py", str(NUM_PARTIES), str(VOTES_PER_PARTY)], "Party Inputs (Selected TXs) Generation")
    print("Initial data generation complete.")

    current_level_num = 0
    passing_parent_prefixes_info = [{'level': 0, 'prefix_len': 0, 'prefix_str': ""}]
    final_inclusion_list_tx_ids = []

    max_conceptual_level = 0
    if TRANSACTION_SPACE_BITS > 0 and BRANCH_FACTOR_LOG2 > 0:
        max_conceptual_level = math.ceil(TRANSACTION_SPACE_BITS / BRANCH_FACTOR_LOG2)
    elif TRANSACTION_SPACE_BITS == 0:
        max_conceptual_level = 0 # Only level 0 (root) will be processed

    iteration_count = 0
    max_iterations = max(1, max_conceptual_level + 5) # At least 1 iteration for TSB=0

    while current_level_num <= max_conceptual_level and passing_parent_prefixes_info and iteration_count < max_iterations:
        iteration_count += 1
        print(f"\n--- Stage Iteration: Processing Level {current_level_num} ---")

        candidate_prefixes_info_for_this_level = []
        if current_level_num == 0:
            candidate_prefixes_info_for_this_level = list(passing_parent_prefixes_info) # Use a copy
        else:
            for parent_info in passing_parent_prefixes_info:
                children = generate_child_prefixes_from_parent(
                    parent_info['prefix_str'], parent_info['prefix_len'],
                    current_level_num, TRANSACTION_SPACE_BITS, BRANCH_FACTOR_LOG2)
                candidate_prefixes_info_for_this_level.extend(children)

        unique_candidates_dict = {p['prefix_str']: p for p in candidate_prefixes_info_for_this_level}
        candidate_prefixes_info_for_this_level = sorted(list(unique_candidates_dict.values()), key=lambda x: (x['prefix_len'], x['prefix_str']))
        num_active_prefixes = len(candidate_prefixes_info_for_this_level)
        print(f"Level {current_level_num}: {num_active_prefixes} unique candidate prefixes generated to check.")

        if num_active_prefixes == 0:
            if current_level_num == 0 and TRANSACTION_SPACE_BITS > 0 : # Should have root if TSB>0
                print("CRITICAL Error: Root level (L0) has 0 candidates despite TSB > 0. This shouldn't occur if root prefix is properly initialized.")
                sys.exit(1)
            elif current_level_num == 0 and TRANSACTION_SPACE_BITS == 0: # Root '' is the only candidate
                if not any(p['prefix_str'] == "" for p in candidate_prefixes_info_for_this_level):
                     print("CRITICAL Error: Root level (L0) for TSB=0 case does not have the empty string prefix candidate.")
                     sys.exit(1)
                # Continue, as the single "" prefix will be processed
            else: # Levels > 0 with no candidates means prior level had no passers
                print(f"Level {current_level_num}: No active prefixes generated from previous level's results. Stopping.")
                break
        
        if num_active_prefixes > MAX_PREFIX_SLOTS_EFFECTIVE:
            print(f"CRITICAL Error: Active prefixes ({num_active_prefixes}) for L{current_level_num} "
                  f"exceeds MAX_PREFIX_SLOTS_EFFECTIVE ({MAX_PREFIX_SLOTS_EFFECTIVE}). Check MPC configuration.")
            sys.exit(1)

        with open(CANDIDATE_PREFIXES_FILE_JSON, 'w') as f:
            json.dump({"candidate_prefixes_info": candidate_prefixes_info_for_this_level,
                       "num_active_prefixes": num_active_prefixes,
                       "current_level": current_level_num}, f)

        print(f"Orchestrator: Triggering input prep for {NUM_PARTIES} parties for L{current_level_num} "
              f"(Num active prefixes: {num_active_prefixes}, MPC array capacity: {MAX_PREFIX_SLOTS_EFFECTIVE})...")
        for i in range(NUM_PARTIES):
            run_command(["python3", "./prepare_iteration_inputs.py", str(i),
                         CANDIDATE_PREFIXES_FILE_JSON, str(MAX_PREFIX_SLOTS_EFFECTIVE),
                         str(TRANSACTION_SPACE_BITS), str(current_level_num)],
                        f"Input Prep P{i} L{current_level_num}")

        print(f"Orchestrator: Running MPC for level {current_level_num} using base program '{COMPILED_MPC_PROGRAM_BASE}' directly from Python...")
        
        # *** CHOOSE THE CORRECT MP-SPDZ PARTY EXECUTABLE HERE ***
        # This should match the protocol your .mpc script is compiled for/expects.
        # Examples: "shamir-party.x", "replicated-ring-party.x", "semi2k-party.x", "mascot-party.x"
        chosen_mpc_party_executable = "shamir-party.x" 
        mpc_output_log = execute_mpc_computation(
            num_parties=NUM_PARTIES,
            compiled_mpc_program_base=COMPILED_MPC_PROGRAM_BASE,
            mpc_party_executable_name=chosen_mpc_party_executable
        )

        print(f"Orchestrator: Parsing MPC output (from P0's log) for level {current_level_num}...")
        new_passing_prefixes_info = []
        active_slots_reported_by_mpc = 0
        current_level_from_mpc_log = -1

        for line in mpc_output_log.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("ITERATION_INFO:"):
                try:
                    parts = line_stripped.split(',')
                    for part in parts:
                        part_stripped = part.strip()
                        if part_stripped.startswith("Active Prefix Slots for this level"):
                            active_slots_reported_by_mpc = int(part_stripped.split('=')[1].strip().split(' ')[0])
                        elif part_stripped.startswith("Current Level"):
                            current_level_from_mpc_log = int(part_stripped.split('=')[1].strip())
                    if active_slots_reported_by_mpc > 0 and current_level_from_mpc_log != -1: break
                except Exception as e:
                    print(f"Warning (Orchestrator): Could not fully parse ITERATION_INFO: '{line_stripped}' - {e}")

        active_slots_to_parse = num_active_prefixes # Default to orchestrator's knowledge
        if active_slots_reported_by_mpc > 0 and active_slots_reported_by_mpc <= num_active_prefixes:
            active_slots_to_parse = active_slots_reported_by_mpc
        elif active_slots_reported_by_mpc > num_active_prefixes :
             print(f"Warning: MPC reported {active_slots_reported_by_mpc} active slots, but orchestrator only generated {num_active_prefixes} candidates for L{current_level_num}. "
                   f"Parsing up to orchestrator's count ({num_active_prefixes}).")
        elif active_slots_reported_by_mpc == 0 and num_active_prefixes > 0:
             print(f"Warning: MPC reported 0 active slots for L{current_level_num}, but orchestrator expected {num_active_prefixes}. "
                   f"Using orchestrator's count ({num_active_prefixes}) for parsing results.")


        print(f"Orchestrator: Parsing results for up to {active_slots_to_parse} active slots (L{current_level_num}).")
        parsed_results_count = 0
        for line in mpc_output_log.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("RAW_ITERATION_RESULT:"):
                parts_dict = {}
                try:
                    raw_parts = line_stripped.split(" ")
                    for item in raw_parts[1:]:
                        if "=" in item:
                            key_value_pair = item.split("=", 1)
                            if len(key_value_pair) == 2: parts_dict[key_value_pair[0].strip()] = key_value_pair[1].strip()
                    if not all(k in parts_dict for k in ["SlotIndex", "MeetsThreshold", "Level"]): continue
                    
                    slot_index = int(parts_dict["SlotIndex"])
                    meets_threshold = int(parts_dict["MeetsThreshold"])
                    level_from_result = int(parts_dict["Level"])

                    if level_from_result != current_level_num:
                        print(f"Warning (Orchestrator): Mismatched level in result line! Expected {current_level_num}, got {level_from_result}. Line: '{line_stripped}'")
                        continue

                    if slot_index < active_slots_to_parse:
                        parsed_results_count +=1
                        if slot_index < len(candidate_prefixes_info_for_this_level):
                            current_candidate_info = candidate_prefixes_info_for_this_level[slot_index]
                            if meets_threshold == 1:
                                new_passing_prefixes_info.append(current_candidate_info)
                                if (current_candidate_info['prefix_len'] == TRANSACTION_SPACE_BITS and TRANSACTION_SPACE_BITS > 0) or \
                                   (TRANSACTION_SPACE_BITS == 0 and current_candidate_info['prefix_len'] == 0):
                                    final_inclusion_list_tx_ids.append(current_candidate_info['prefix_str'])
                                    print(f"Orchestrator: ADDED to final inclusion list (L{current_level_num}): '{current_candidate_info['prefix_str']}'")
                        else:
                             print(f"CRITICAL Warning (Orchestrator): SlotIndex {slot_index} (L{current_level_num}) from MPC output "
                                   f"is within active_slots_to_parse ({active_slots_to_parse}) but out of bounds for current "
                                   f"candidates list (len {len(candidate_prefixes_info_for_this_level)}). Desync likely.")
                except Exception as e:
                    print(f"Warning (Orchestrator): Error parsing MPC result line '{line_stripped}': {e}")
        
        print(f"Orchestrator: Parsed {parsed_results_count} RAW_ITERATION_RESULT lines for L{current_level_num}.")
        passing_parent_prefixes_info = new_passing_prefixes_info
        print(f"Level {current_level_num}: Found {len(passing_parent_prefixes_info)} prefixes meeting threshold to become parents for the next level.")

        if not passing_parent_prefixes_info and current_level_num < max_conceptual_level :
            print(f"Level {current_level_num}: No prefixes passed threshold to seed the next level. Terminating iterative search.")
            break

        processed_max_depth_this_iteration = False
        if candidate_prefixes_info_for_this_level:
            if any(p['prefix_len'] == TRANSACTION_SPACE_BITS for p in candidate_prefixes_info_for_this_level) and TRANSACTION_SPACE_BITS > 0:
                processed_max_depth_this_iteration = True
        elif current_level_num == 0 and TRANSACTION_SPACE_BITS == 0:
             if any(p['prefix_len'] == 0 for p in candidate_prefixes_info_for_this_level): # check if root prefix was candidate
                processed_max_depth_this_iteration = True


        if processed_max_depth_this_iteration:
             print(f"Level {current_level_num}: Processed candidate prefixes at max depth ({TRANSACTION_SPACE_BITS} bits). Terminating iterative search.")
             break
        
        if current_level_num >= max_conceptual_level :
             print(f"Level {current_level_num}: Reached max conceptual level ({max_conceptual_level}). Terminating iterative search.")
             break
        
        current_level_num += 1
        if iteration_count >= max_iterations:
            print(f"Warning: Reached max iterations ({max_iterations}). Terminating.")
            break

    print("\n--- Orchestrator: Workflow Complete ---")
    print("Final Anonymous Inclusion List (Unique TX IDs Meeting Threshold at Full Length):")
    unique_final_tx_ids = sorted(list(set(final_inclusion_list_tx_ids)))
    if unique_final_tx_ids:
        for tx_id in unique_final_tx_ids:
            print(f"Included TX ID: '{tx_id}'") # Added quotes for clarity, esp. for empty string
    else:
        print("No transaction IDs met the threshold for inclusion at their full length.")

if __name__ == "__main__":
    main()