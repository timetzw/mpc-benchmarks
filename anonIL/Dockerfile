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

RUN make -j4 mascot-party.x
RUN make -j4 replicated-ring-party.x
RUN make -j4 shamir-party.x malicious-shamir-party.x semi2k-party.x
RUN make -j4 chaigear-party.x
RUN echo MY_CFLAGS += -DFIXED_REGISTERS=1 >> CONFIG.mine
# RUN make -j4 yao-party.x


# --- Setup for Iterative Anonymous Inclusion ---

# 1. Add your NEW MPC script and Python helper scripts
ADD anonymous_inclusion_iterative.mpc Programs/Source/
ADD generate_mempool.py ./
ADD generate_inputs.py ./
ADD prepare_iteration_inputs.py ./
ADD run_iterative_workflow.py ./
ADD parse_log.py ./

RUN chmod +x ./generate_mempool.py \
             ./generate_inputs.py \
             ./prepare_iteration_inputs.py \
             ./run_iterative_workflow.py \
             ./parse_log.py

# 2. Setup Configuration parameters
ARG NUM_PARTIES_ARG=4
ARG TRANSACTION_SPACE_BITS_ARG=3
ARG BRANCH_FACTOR_LOG2_ARG=1
ARG MIN_VOTES_THRESHOLD_ARG=2
ARG MEMPOOL_SIZE_ARG=6
ARG VOTES_PER_PARTY_ARG=2

ENV NUM_PARTIES=${NUM_PARTIES_ARG}
ENV TRANSACTION_SPACE_BITS=${TRANSACTION_SPACE_BITS_ARG}
ENV BRANCH_FACTOR_LOG2=${BRANCH_FACTOR_LOG2_ARG}
ENV MIN_VOTES_THRESHOLD=${MIN_VOTES_THRESHOLD_ARG}
ENV MEMPOOL_SIZE=${MEMPOOL_SIZE_ARG}
ENV VOTES_PER_PARTY=${VOTES_PER_PARTY_ARG}
ENV MAX_PREFIX_SLOTS=${MEMPOOL_SIZE_ARG}
ENV PLAYERS=${NUM_PARTIES}

# 3. Compile the MPC script (once)
# The .mpc script now reads all its config from ENV variables.
# NUM_PARTIES is also read from ENV by the .mpc script's compile-time Python.

RUN ./compile.py Programs/Source/anonymous_inclusion_iterative.mpc ${NUM_PARTIES}

# 4. Setup SSL (if needed for the protocol, e.g., some *-party.x require it)
RUN Scripts/setup-ssl.sh ${NUM_PARTIES}

# 5. Execute the entire iterative workflow using the Python orchestrator
RUN python3 ./run_iterative_workflow.py shamir

# --- End of setup for Iterative Anonymous Inclusion ---

CMD ["bash"]