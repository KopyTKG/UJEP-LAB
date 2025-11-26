#!/bin/bash

# Define the number of nodes (from 1 up to this number)
NODES_COUNT=8

# Define the hostname prefix
HOST_PREFIX="Rocky-Compute-"

CMD="
"

for I in $(seq 1 $NODES_COUNT); do
    NODE="${HOST_PREFIX}${I}"
    ssh -t -o ConnectTimeout=5 "root@$NODE" "$CMD"
    echo
done
