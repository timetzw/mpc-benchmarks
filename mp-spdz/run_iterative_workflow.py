# run_iterative_workflow.py
import sys
import os
import json
import math
import subprocess

# --- Configuration (Read from Environment Variables - these are set by Dockerfile ARGs -> ENVs) ---
# Use the exact ARG names from your Dockerfile for defaults if needed, but ENV should provide them.
# Your current ARGs for the test:
# ARG NUM_PARTIES_ARG=4
# ARG TRANSACTION_SPACE_BITS_ARG=40 
# ARG BRANCH_FACTOR_LOG2_ARG=2
# ARG MIN_VOTES_THRESHOLD_ARG=2
# ARG MEMPOOL_SIZE_ARG=15
# ARG VOTES_PER_PARTY_ARG=10

def get_env_int_orchestrator(var_name, default_val_str, positive=False, can_be_zero_sometimes=False):
    val_str = os.environ.get(var_name, default_val_str)
    default_val = int(default_val_str)
    try:
        val_int = int(val_str)
        if positive and val_int <= 0:
            print(f"[Orchestrator WARNING] ENV VAR {var_name} ('{val_str}') should be positive. Using default {default_val_str}.")
            return default_val
        if not can_be_zero_sometimes and val_int < 0 :
             print(f"[Orchestrator WARNING] ENV VAR {var_name} ('{val_str}') is negative. Using default {default_val_str}.")
             return default_val
        return val_int
    except ValueError:
        print(f"[Orchestrator WARNING] ENV VAR {var_name} ('{val_str}') is not an int. Using default {default_val_str}.")
        return default_val

NUM_PARTIES = get_env_int_orchestrator('NUM_PARTIES', '4', positive=True)
TRANSACTION_SPACE_BITS = get_env_int_orchestrator('TRANSACTION_SPACE_BITS', '40', can_be_zero_sometimes=True) # TSB=0 is valid
BRANCH_FACTOR_LOG2 = get_env_int_orchestrator('BRANCH_FACTOR_LOG2', '2', positive=True)
MIN_VOTES_THRESHOLD = get_env_int_orchestrator('MIN_VOTES_THRESHOLD', '2', can_be_zero_sometimes=True)
VOTES_PER_PARTY = get_env_int_orchestrator('VOTES_PER_PARTY', '10') # Matches your log
MEMPOOL_SIZE = get_env_int_orchestrator('MEMPOOL_SIZE', '15')         # Matches your log

# Calculate effective MAX_PREFIX_SLOTS based on MEMPOOL_SIZE and BRANCH_FACTOR_LOG2
# This MUST match the calculation done in the .mpc script's compile-time section.
if BRANCH_FACTOR_LOG2 < 0: # Should be validated positive by get_env_int
    print("CRITICAL ERROR: BRANCH_FACTOR_LOG2 from ENV is invalid for MAX_PREFIX_SLOTS calculation.")
    sys.exit(1)
effective_bf_for_calc = BRANCH_FACTOR_LOG2

mempool_size_for_calc = MEMPOOL_SIZE
if mempool_size_for_calc <= 0:
    if TRANSACTION_SPACE_BITS == 0: mempool_size_for_calc = 1
    else: mempool_size_for_calc = 1 # Default base if no mempool items but TSB > 0
    print(f"Orchestrator: MEMPOOL_SIZE from ENV is '{MEMPOOL_SIZE}', using base {mempool_size_for_calc} for MAX_PREFIX_SLOTS_EFFECTIVE calculation.")
MAX_PREFIX_SLOTS_EFFECTIVE = max(1, mempool_size_for_calc * (2**effective_bf_for_calc))

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
COMPILED_MPC_PROGRAM_BASE = "anonymous_inclusion_iterative" 

def generate_child_prefixes_from_parent(parent_prefix_str, parent_prefix_len, target_level_num, global_max_tx_bits, bf_log2):
    children = []
    if parent_prefix_len >= global_max_tx_bits and global_max_tx_bits > 0: 
        return []
    if global_max_tx_bits == 0 and parent_prefix_len == 0 : 
        return []
    num_new_bits_to_add = bf_log2
    if parent_prefix_len + num_new_bits_to_add > global_max_tx_bits:
        num_new_bits_to_add = global_max_tx_bits - parent_prefix_len
    if num_new_bits_to_add <= 0: return []
    actual_child_prefix_len = parent_prefix_len + num_new_bits_to_add
    for i in range(2**num_new_bits_to_add):
        child_suffix = format(i, f'0{num_new_bits_to_add}b')
        child_prefix_str = parent_prefix_str + child_suffix
        children.append({'level': target_level_num, 'prefix_len': actual_child_prefix_len, 'prefix_str': child_prefix_str})
    return children

def run_command(command_list, stage_name="Command"):
    print(f"Orchestrator: Running {stage_name}: {' '.join(command_list)}")
    process = subprocess.run(command_list, capture_output=True, text=True, check=False)
    print(f"--- Output from {stage_name} ---")
    stdout_lines = process.stdout.splitlines()
    stderr_lines = process.stderr.splitlines()
    if len(stdout_lines) > 20 and process.returncode == 0 :
        for line in stdout_lines[:5]: print(line)
        print(f"... (stdout truncated - {len(stdout_lines) - 10} more lines) ...")
        for line in stdout_lines[-5:]: print(line)
    elif process.stdout: print("STDOUT:\n" + process.stdout)
    if process.stderr: print("STDERR:\n" + process.stderr)
    print(f"--- End Output from {stage_name} (Return Code: {process.returncode}) ---")
    if process.returncode != 0:
        print(f"CRITICAL Error: {stage_name} failed with exit code {process.returncode}.")
        sys.exit(1)
    return process.stdout

def main():
    print("--- Orchestrator: Starting Anonymous Inclusion Workflow ---")
    if not os.path.exists("Player-Data"): os.makedirs("Player-Data"); print("Created Player-Data directory.")

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
    
    iteration_count = 0
    max_iterations = max_conceptual_level + 5

    while current_level_num <= max_conceptual_level and passing_parent_prefixes_info and iteration_count < max_iterations:
        iteration_count += 1
        print(f"\n--- Stage Iteration: Processing Level {current_level_num} ---")

        candidate_prefixes_info_for_this_level = []
        if current_level_num == 0:
            candidate_prefixes_info_for_this_level = passing_parent_prefixes_info
        else:
            for parent_info in passing_parent_prefixes_info:
                children = generate_child_prefixes_from_parent(
                    parent_info['prefix_str'], parent_info['prefix_len'],
                    current_level_num, TRANSACTION_SPACE_BITS, BRANCH_FACTOR_LOG2)
                candidate_prefixes_info_for_this_level.extend(children)
        
        unique_candidates_dict = {p['prefix_str']: p for p in candidate_prefixes_info_for_this_level}
        candidate_prefixes_info_for_this_level = sorted(unique_candidates_dict.values(), key=lambda x: (x['prefix_len'], x['prefix_str']))
        num_active_prefixes = len(candidate_prefixes_info_for_this_level)
        print(f"Level {current_level_num}: {num_active_prefixes} unique candidate prefixes generated.")
        
        if num_active_prefixes == 0:
            if current_level_num == 0: sys.exit("CRITICAL Error: Root level has 0 candidates.")
            else: print(f"Level {current_level_num}: No active prefixes from previous level. Stopping."); break
        
        if num_active_prefixes > MAX_PREFIX_SLOTS_EFFECTIVE:
            print(f"CRITICAL Error: Active prefixes ({num_active_prefixes}) for L{current_level_num} "
                  f"exceeds MAX_PREFIX_SLOTS_EFFECTIVE ({MAX_PREFIX_SLOTS_EFFECTIVE}).")
            sys.exit(1)

        with open(CANDIDATE_PREFIXES_FILE_JSON, 'w') as f:
            json.dump({"candidate_prefixes_info": candidate_prefixes_info_for_this_level,
                       "num_active_prefixes": num_active_prefixes,
                       "current_level": current_level_num}, f)

        print(f"Orchestrator: Triggering input prep for {NUM_PARTIES} parties for L{current_level_num} (MPC capacity: {MAX_PREFIX_SLOTS_EFFECTIVE})...")
        for i in range(NUM_PARTIES):
            run_command(["python3", "./prepare_iteration_inputs.py", str(i), 
                         CANDIDATE_PREFIXES_FILE_JSON, str(MAX_PREFIX_SLOTS_EFFECTIVE), 
                         str(TRANSACTION_SPACE_BITS), str(current_level_num)], 
                        f"Input Prep P{i} L{current_level_num}")

        mpc_run_script = "./run_aggregator_shamir.sh"
        print(f"Orchestrator: Running MPC for level {current_level_num}...")
        mpc_output_log = run_command([mpc_run_script, str(NUM_PARTIES)], f"MPC Run L{current_level_num}")
        
        print(f"Orchestrator: Parsing MPC output for level {current_level_num}...")
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
                    if active_slots_reported_by_mpc > 0 and current_level_from_mpc_log != -1 : break 
                except Exception as e:
                    print(f"Warning (Orchestrator): Could not parse ITERATION_INFO: '{line_stripped}' - {e}")
        
        if active_slots_reported_by_mpc == 0 and num_active_prefixes > 0:
             print(f"Warning: MPC reported 0 active slots for L{current_level_num}, but orchestrator expected {num_active_prefixes}. Using orchestrator's count for parsing.")
             active_slots_to_parse = num_active_prefixes
        else:
            active_slots_to_parse = active_slots_reported_by_mpc
        
        print(f"Orchestrator: Parsing results for {active_slots_to_parse} active slots (L{current_level_num}).")

        for line in mpc_output_log.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("RAW_ITERATION_RESULT:"):
                parts_dict = {}
                try:
                    raw_parts = line_stripped.split(" ") 
                    for item in raw_parts[1:]: 
                        if "=" in item:
                            key_value_pair = item.split("=", 1)
                            if len(key_value_pair) == 2: parts_dict[key_value_pair[0]] = key_value_pair[1]
                    
                    if not all(k in parts_dict for k in ["SlotIndex", "MeetsThreshold", "Level"]): continue 
                        
                    slot_index = int(parts_dict["SlotIndex"])
                    meets_threshold = int(parts_dict["MeetsThreshold"])
                    
                    if slot_index < active_slots_to_parse: 
                        if slot_index < len(candidate_prefixes_info_for_this_level): 
                            current_candidate_info = candidate_prefixes_info_for_this_level[slot_index]
                            
                            # Debug print to see what's being considered
                            # print(f"DEBUG Orchestrator: Candidate for check: Prefix='{current_candidate_info['prefix_str']}', "
                            #       f"Len={current_candidate_info['prefix_len']}, TSB={TRANSACTION_SPACE_BITS}, "
                            #       f"MeetsThresholdMPC={meets_threshold}")

                            if meets_threshold == 1:
                                new_passing_prefixes_info.append(current_candidate_info)
                                
                                if current_candidate_info['prefix_len'] == TRANSACTION_SPACE_BITS and TRANSACTION_SPACE_BITS > 0:
                                    final_inclusion_list_tx_ids.append(current_candidate_info['prefix_str'])
                                    print(f"DEBUG Orchestrator: ADDED to final inclusion list: {current_candidate_info['prefix_str']}")
                        else:
                             print(f"CRITICAL Warning (Orchestrator): SlotIndex {slot_index} (L{current_level_num}) from MPC output is out of bounds for candidates list (len {len(candidate_prefixes_info_for_this_level)}). Desync likely.")
                except Exception as e:
                    print(f"Warning (Orchestrator): Error parsing MPC result line '{line_stripped}': {e}")

        passing_parent_prefixes_info = new_passing_prefixes_info 
        print(f"Level {current_level_num}: Found {len(passing_parent_prefixes_info)} prefixes meeting threshold for next level.")

        if not passing_parent_prefixes_info and current_level_num < max_conceptual_level :
            print(f"Level {current_level_num}: No prefixes passed threshold. Terminating.")
            break
        
        processed_max_depth_this_iteration = False
        if candidate_prefixes_info_for_this_level: 
            if candidate_prefixes_info_for_this_level[0]['prefix_len'] == TRANSACTION_SPACE_BITS and TRANSACTION_SPACE_BITS > 0:
                processed_max_depth_this_iteration = True
        elif current_level_num == 0 and TRANSACTION_SPACE_BITS == 0 : 
            processed_max_depth_this_iteration = True

        if processed_max_depth_this_iteration:
             print(f"Level {current_level_num}: Processed prefixes at max depth ({TRANSACTION_SPACE_BITS} bits). Terminating.")
             break
        if current_level_num >= max_conceptual_level : 
             print(f"Level {current_level_num}: Reached max conceptual level. Terminating.")
             break
        current_level_num += 1

    print("\n--- Orchestrator: Workflow Complete ---")
    print("Final Anonymous Inclusion List (TX IDs Meeting Threshold at Full Length):")
    if final_inclusion_list_tx_ids:
        for tx_id in sorted(list(set(final_inclusion_list_tx_ids))): 
            print(f"Included TX ID: {tx_id}")
    else:
        print("No transaction IDs met the threshold for inclusion at their full length.")

if __name__ == "__main__":
    main()