FROM ubuntu:20.04
WORKDIR /root

# ==== Install dependencies ====
RUN apt-get update
RUN apt-get install -y make
RUN apt-get install -y git
RUN apt-get install -y clang++-6
RUN apt-get install -y libsodium-dev
RUN apt-get install -y autoconf
RUN apt-get install -y automake
RUN apt-get install -y libtool
RUN apt-get install -y yasm 
ENV TZ=Australia/Sydney
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt-get install -y texinfo
RUN apt-get install -y libboost-dev
RUN apt-get install -y libssl-dev
RUN apt-get install -y libntl-dev
RUN apt-get install -y gcc
RUN apt-get install -y libboost-system1.71-dev
RUN apt-get install -y iproute2
RUN apt-get install -y time
RUN apt-get install -y clang python3 python3-pip # Ensures python3 is installed

# ==== Clone MP-SPDZ repository ====
RUN git clone https://github.com/data61/MP-SPDZ -b v0.1.9
WORKDIR /root/MP-SPDZ
RUN git config --global url."https://github.com/".insteadOf git://github.com/
RUN git submodule update --init mpir
RUN make -j4 mpir

# ==== Configure MP-SPDZ ====
RUN echo CXX = clang++ >> CONFIG.mine
RUN echo USE_NTL = 1 >> CONFIG.mine

RUN make -j4 replicated-ring-party.x
RUN make -j4 shamir-party.x malicious-shamir-party.x semi2k-party.x
RUN make -j4 chaigear-party.x
RUN echo MY_CFLAGS += -DFIXED_REGISTERS=1 >> CONFIG.mine
# RUN make -j4 yao-party.x

# --- New Setup for anonymous_inclusion.mpc ---

# 1. Add your MPC script
ADD anonymous_inclusion.mpc Programs/Source/

# 2. Add necessary helper python scripts
ADD generate_mempool.py ./
RUN chmod +x ./generate_mempool.py
ADD generate_inputs.py ./
RUN chmod +x ./generate_inputs.py
ADD generate_local_tree.py ./
RUN chmod +x ./generate_local_tree.py

ARG NUM_PARTIES=4
ARG TRANSACTION_SPACE_BITS=40
ARG BRANCH_FACTOR_LOG2=2
ARG MIN_VOTES_THRESHOLD=2
ARG MEMPOOL_SIZE=100
ARG VOTES_PER_PARTY=10
# 3. Setup Configuration parameters for all files to ensure consistency
# ARG NUM_PARTIES=4
# ARG TRANSACTION_SPACE_BITS=3
# ARG BRANCH_FACTOR_LOG2=1
# ARG MIN_VOTES_THRESHOLD=2
# ARG MEMPOOL_SIZE=6
# ARG VOTES_PER_PARTY=3


ENV NUM_PARTIES=${NUM_PARTIES}
ENV TRANSACTION_SPACE_BITS=${TRANSACTION_SPACE_BITS}
ENV BRANCH_FACTOR_LOG2=${BRANCH_FACTOR_LOG2}
ENV MIN_VOTES_THRESHOLD=${MIN_VOTES_THRESHOLD}
ENV MEMPOOL_SIZE=${MEMPOOL_SIZE}
ENV VOTES_PER_PARTY=${VOTES_PER_PARTY}

# 4. Run helper scripts to generate mempool, local tree, and inputs
# mempool generation needs: tx_space_bits to determine how tx looks alike, and mempool_size to determine how many txs to generate
# inputs generation needs: num_parties to determine how many parties to generate inputs for, votes_per_party to determine how many tx to vote for, and all other data are directly from the output of generate_mempool.py
# local tree generation needs: num_parties to determine how many parties to generate inputs for, tx_space_bits to determine how many levels of the tree to generate, branch_factor_log2 to determine how many branches to generate, and votes_per_party to determine how many tx to vote for
# (Example: python3 ./generate_mempool.py 3 6)
RUN python3 ./generate_mempool.py ${TRANSACTION_SPACE_BITS} ${MEMPOOL_SIZE}
# (Example: python3 ./generate_inputs.py 4 3)
RUN python3 ./generate_inputs.py ${NUM_PARTIES} ${VOTES_PER_PARTY} 
# (Example: python3 ./generate_local_tree.py 4 3 1 3)
RUN python3 ./generate_local_tree.py ${NUM_PARTIES} ${TRANSACTION_SPACE_BITS} ${BRANCH_FACTOR_LOG2} ${VOTES_PER_PARTY}


# 5. Prepare for running the MPC script
# ADD run_anon_incl_shamir.sh ./
# RUN chmod +x ./run_anon_incl_shamir.sh
# RUN ./compile.py anonymous_inclusion.mpc ${NUM_PARTIES}
ADD anonymous_inclusion_aggregator.mpc Programs/Source/
ADD run_aggregator_shamir.sh ./
RUN chmod +x ./run_aggregator_shamir.sh

# Compile the NEW MPC script
RUN ./compile.py anonymous_inclusion_aggregator.mpc ${NUM_PARTIES}
RUN Scripts/setup-ssl.sh ${NUM_PARTIES}

# 7. (Optional) Execute a test run for anonymous_inclusion.mpc during build
# The run_anon_incl_shamir.sh script now calls generate_inputs.py internally.
# The Player-Data/Input-P*-0 files for anonymous_inclusion will be created by generate_inputs.py.
# The previous 'RUN printf ...' lines for anonymous_inclusion inputs are removed.
RUN ./run_aggregator_shamir.sh ${NUM_PARTIES}

# # --- End of setup for anonymous_inclusion.mpc ---


# # Set the default command to bash for interactive use if desired
CMD ["bash"]

