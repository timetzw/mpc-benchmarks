FROM ubuntu:20.04
WORKDIR /root

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

RUN git clone https://github.com/data61/MP-SPDZ -b v0.1.9
WORKDIR /root/MP-SPDZ
RUN git config --global url."https://github.com/".insteadOf git://github.com/
RUN git submodule update --init mpir
RUN make -j4 mpir

RUN echo CXX = clang++ >> CONFIG.mine
RUN echo USE_NTL = 1 >> CONFIG.mine

RUN make -j4 replicated-ring-party.x
RUN make -j4 shamir-party.x malicious-shamir-party.x semi2k-party.x
RUN make -j4 chaigear-party.x
RUN echo MY_CFLAGS += -DFIXED_REGISTERS=1 >> CONFIG.mine
RUN make -j4 yao-party.x

ADD dot.mpc Programs/Source
ADD dot4.mpc Programs/Source

RUN ./compile.py dot 100000
RUN ./compile.py -DB 32 dot 100000 B
RUN ./compile.py dot4 100000

RUN Scripts/setup-ssl.sh 4
RUN seq 100000 > Player-Data/Input-P0-0
RUN seq 100000 > Player-Data/Input-P1-0
RUN seq 100000 > Player-Data/Input-P2-0
RUN seq 100000 > Player-Data/Input-P3-0

ADD run*.sh ./
RUN bash run-shamir4.sh # New 4-party shamir run for dot4

# --- Setup for anonymous_inclusion.mpc with 4 Parties ---

# 1. Add your MPC script to the Programs/Source directory in the Docker image
# Make sure 'anonymous_inclusion.mpc' is in the same directory as your Dockerfile,
# or adjust the source path accordingly.
ADD anonymous_inclusion.mpc Programs/Source/

ARG NUM_PARTIES_ARG=4

# Compile, passing the NUM_PARTIES_ARG
RUN ./compile.py anonymous_inclusion ${NUM_PARTIES_ARG}

# Set up SSL for the same number of parties
RUN Scripts/setup-ssl.sh ${NUM_PARTIES_ARG}
# 4. Prepare input files for each of the 4 parties
# According to your parameters:
# - num_tx_per_party = 3 (each party votes for 3 transactions)
# - max_tx_id_length = 3 (transaction IDs are 3 bits long, so decimals 0-7)
# The input format (as per our last revision of anonymous_inclusion.mpc)
# should be decimal integers, one per line.

# Inputs for Party 0 (example: votes for "001", "101", "110" -> decimals 1, 5, 6)
RUN printf "1\n5\n6\n" > Player-Data/Input-P0-0

# Inputs for Party 1 (example: votes for "010", "101", "111" -> decimals 2, 5, 7)
RUN printf "2\n5\n7\n" > Player-Data/Input-P1-0

# Inputs for Party 2 (example: votes for "001", "011", "100" -> decimals 1, 3, 4)
RUN printf "1\n3\n4\n" > Player-Data/Input-P2-0

# Inputs for Party 3 (example: votes for "100", "110", "000" -> decimals 4, 6, 0)
RUN printf "4\n6\n0\n" > Player-Data/Input-P3-0

# --- End of setup for anonymous_inclusion.mpc ---
# 5. Add your new custom run script to the MP-SPDZ root and make it executable
ADD run_anon_incl_shamir.sh ./
RUN chmod +x ./run_anon_incl_shamir.sh

# 6. Execute the MPC computation using your new script
# This will run the 4-party Shamir protocol for 'anonymous_inclusion'.
# Output from the script (launch messages, completion messages) and from the
# MPC parties (redirected to Logs/P* files) will be visible during the Docker build.
RUN ./run_anon_incl_shamir.sh 4