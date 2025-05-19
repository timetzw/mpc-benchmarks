#!/bin/bash

# Script to run Shamir MPC for 'anonymous_inclusion'

if [ -z "$1" ]; then
  echo "Usage: $0 <num_parties_for_this_run>"
  echo "Example: $0 4"
  exit 1
fi

N_RUNTIME_PARTIES=$1
BASE_PROGRAM_NAME="anonymous_inclusion"
# Construct the program name based on how compile.py appends arguments
# If compile.py uses the N_RUNTIME_PARTIES as the suffix:
COMPILED_PROGRAM_NAME="${BASE_PROGRAM_NAME}-${N_RUNTIME_PARTIES}"

BASE_PORT=14000

echo "Starting ${N_RUNTIME_PARTIES}-party Shamir MPC for program ${COMPILED_PROGRAM_NAME}"

# Determine the party executable
PARTY_EXEC=""
if [ -f "./shamir-party.x" ]; then
    PARTY_EXEC="./shamir-party.x"
elif [ -f "./shamir-party.sh" ]; then
    PARTY_EXEC="./shamir-party.sh"
else
    echo "Error: Neither shamir-party.x nor shamir-party.sh found."
    exit 1
fi
echo "Using party executable: ${PARTY_EXEC}"

COMMON_OPTS="-N ${N_RUNTIME_PARTIES} -pn ${BASE_PORT}"

mkdir -p Logs
rm -f Logs/P*_${COMPILED_PROGRAM_NAME}.log # Clean previous logs for this program

echo "Launching Party 0..."
${PARTY_EXEC} -p 0 ${COMMON_OPTS} ${COMPILED_PROGRAM_NAME} > Logs/P0_${COMPILED_PROGRAM_NAME}.log 2>&1 &
PIDS[0]=$!

for i in $(seq 1 $((N_RUNTIME_PARTIES - 1)))
do
    echo "Launching Party $i..."
    ${PARTY_EXEC} -p $i ${COMMON_OPTS} ${COMPILED_PROGRAM_NAME} > Logs/P${i}_${COMPILED_PROGRAM_NAME}.log 2>&1 &
    PIDS[$i]=$!
done

echo "All parties launched. Waiting for completion..."
# ... (wait loop as before, using PIDS array) ...
for i in $(seq 0 $((N_RUNTIME_PARTIES - 1)))
do
    echo "Waiting for Party $i (PID ${PIDS[$i]}) to complete..."
    wait ${PIDS[$i]}
    RET_CODE=$?
    echo "Party $i finished with status ${RET_CODE}. Log: Logs/P${i}_${COMPILED_PROGRAM_NAME}.log"
    # if [ ${RET_CODE} -ne 0 ]; then echo "Error detected for Party $i"; fi
done

echo "All parties finished."