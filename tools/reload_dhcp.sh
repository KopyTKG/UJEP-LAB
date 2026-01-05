# !/bin/bash

NODES_COUNT=8

HOST_PREFIX="Rocky-OKD-Host-"

echo "--- Preparing to reload ip $NODES_COUNT nodes (1 to $NODES_COUNT) ---"
echo "--- Targeting hosts like: ${HOST_PREFIX}I ---"
echo

for I in $(seq 1 $NODES_COUNT); do
    
    NODE="${HOST_PREFIX}${I}"
    
    echo "--- Sending reload command to **$NODE** ---"
    ssh -t -o ConnectTimeout=5 "root@$NODE" 'nmcli connection reload'

    if [ $? -eq 0 ]; then
        echo "**SUCCESS:** Reaload command sent to $NODE."
	ssh -t -o ConnectTimeout=5 "root@$NODE" 'ip addr show | grep inet'
    else
        echo "**FAILURE:** Could not connect or send command to $NODE. (Check connectivity/keys)"
    fi
    echo
done

echo "--- Reload process initiation complete ---"
