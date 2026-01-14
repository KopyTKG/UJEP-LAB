#!/bin/bash

# Define the number of nodes (from 1 up to this number)
NODES_COUNT=8

# Define the hostname prefix
HOST_PREFIX="192.168.1.10"
SSH_KEY_PATH="/home/kopy/.ssh/ujep_lab.pub"

# Check if SSHPASS environment variable is set
if [ -z "$SSHPASS" ]; then
    echo "ERROR: SSHPASS environment variable not set"
    echo "Usage: export SSHPASS='your_password' && ./ssh-copy-id.sh"
    exit 1
fi

# Export for sshpass to use
export SSHPASS

for I in $(seq 1 $NODES_COUNT); do
    NODE="${HOST_PREFIX}${I}"
    sshpass -e ssh-copy-id -o StrictHostKeyChecking=no -i "$SSH_KEY_PATH" "user@$NODE"
    echo "Copied SSH key to $NODE"
done

# Heads
HEAD_PREFIX="192.168.1.25"
HEAD_COUNT=2
for I in $(seq 1 $HEAD_COUNT); do
    HEAD_NODE="${HEAD_PREFIX}${I}"
    sshpass -e ssh-copy-id -o StrictHostKeyChecking=no -i "$SSH_KEY_PATH" "user@$HEAD_NODE"
    echo "Copied SSH key to $HEAD_NODE"
done

