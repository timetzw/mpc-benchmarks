# MP‑SPDZ Anonymous Inclusion List

This repository packages an **MP‑SPDZ‑based implementation** of the Anonymous Inclusion List (AIL) protocol inside a self‑contained Docker image.  It is adapted from the benchmark suite of the [MP‑SPDZ paper](https://eprint.iacr.org/2020/521) and the framework survey by [Hastings *et al.*](https://github.com/MPC-SOK/frameworks).

---

## Quick‑Start Usage

```bash
# 1. Clone/enter the project root then navigate to the MP‑SPDZ folder
cd anonIL

# 2. Build the image (choose any tag you like)
docker build -t <name> .

# 3. Run an interactive container
docker run -it <name>

# 4. Inside the container, execute the orchestrator at any time
python3 run_iterative_workflow.py

# 5. Examine the raw MPC logs
cat Logs/mpc_run.log
```

> **Tip:** Re‑running `python3 run_iterative_workflow.py` will regenerate input files and start a fresh MPC round without rebuilding the image.

---

## MP‑SPDZ Framework

MP‑SPDZ offers highly‑optimised arithmetic and many protocol variants (SPDZ, SPDZ2k, MASCOT…).

* **Orchestrator.** `run_iterative_workflow.py` generates per‑iteration inputs, invokes `Scripts/shamir.sh`, and parses outputs.

### Design Overview

```text
┌──────────────┐       generate_mempool.py
│   mempool    │◀─────────────────────────┐
└──────────────┘                          │
                                          │
Player-Data/Input-P{i}-1   prepare_iteration_inputs.py
           ▲                             │
           │                             ▼
       per‑party votes       Player-Data/Input-P{i}-0
                                   ▲
                                   │
                 run_iterative_workflow.py (this script)
                                   │
                                   ▼
                       Scripts/shamir.sh → MP‑SPDZ runtime
                                   │
                                   ▼
                        Logs/mpc_run.log + stdout
```

* **Status.** The orchestrator is parameter‑agnostic (any committee size, tree fan‑out, etc.).  Performance profiling is ongoing.

---

## Container Details

| Component      | Path in image       | Notes                                                 |
| -------------- | ------------------- | ----------------------------------------------------- |
| MP‑SPDZ source | `/root/MP-SPDZ`     | Pulled via sub‑module during build.                   |
| AIL scripts    | `/root/anonIL`      | Contains orchestrator, helpers, and *.mpc* code.      |
| Logs           | `/root/anonIL/Logs` | `mpc_run.log` accumulates one section per tree level. |

---

