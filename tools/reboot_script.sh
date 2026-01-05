#!/bin/bash

# Define the number of nodes (from 1 up to this number)
NODES_COUNT=8

# Define the hostname prefix
HOST_PREFIX="Rocky-OKD-Host-"

echo "--- Preparing to reboot $NODES_COUNT nodes (1 to $NODES_COUNT) ---"
echo "--- Targeting hosts like: ${HOST_PREFIX}I ---"
echo

# The for loop iterates from 1 up to the value of NODES_COUNT
# The sequence {1..$NODES_COUNT} generates the numbers 1 2 3 ... 8
for I in $(seq 1 $NODES_COUNT); do
    
    # Construct the full hostname for the current iteration
    NODE="${HOST_PREFIX}${I}"
    
    echo "--- Sending reboot command to **$NODE** ---"
    
    # Execute the reboot command on the remote server via SSH.
    # The user is hardcoded as 'root' in the SSH command.
    ssh -t -o ConnectTimeout=5 "root@$NODE" 'sudo reboot now'

    # Check the exit status of the SSH command (0 = success, non-zero = failure)
    if [ $? -eq 0 ]; then
        echo "**SUCCESS:** Reboot command sent to $NODE."
    else
        echo "**FAILURE:** Could not connect or send command to $NODE. (Check connectivity/keys)"
    fi
    echo
done

echo "--- Reboot process initiation complete ---"
