#!/bin/bash

# --- CONFIGURATION ---
# Prefix for your nodes (e.g., Rocky-Compute-1, Rocky-Compute-2...)
NODE_PREFIX="Rocky-Compute-"
# Range of nodes
START_NODE=1
END_NODE=8

# Where you want them mounted
MOUNT_1="/mnt/ssd1"
MOUNT_2="/mnt/ssd2"
# ---------------------

for i in $(seq $START_NODE $END_NODE); do
    HOST="${NODE_PREFIX}${i}"
    echo "=================================================="
    echo "🚀 Configuring Node: $HOST"
    echo "=================================================="

    # We pass the variables to the remote host using 'bash -s'
    ssh -o ConnectTimeout=5 root@$HOST "bash -s" <<EOF
	# 1. stop and disable beegfs
    	echo "Stopping beegfs services"
	systemctl stop beegfs-storage beegfs-client
	systemctl disable beegfs-storage beegfs-client

	# 2. Remove beegfs configs
	echo "Removing beegfs configurations"
	rm -rf /etc/beegfs

	# 3. Uninstall beegfs packages
	echo "Uninstalling beegfs packages"
	yum remove -y beegfs-storage beegfs-tools beegfs-utils beegfs-client libbeegfs-ib 

	# 4. Clean up firewall rules
	echo "Cleaning up firewall rules"
	echo "Remove beegfs-storage ports from firewall"
	firewall-cmd --remove-port=8003/tcp --permanent
	firewall-cmd --remove-port=8003/udp --permanent
	echo "Remove beegfs-client ports from firewall"
	firewall-cmd --remove-port=8003/tcp --permanent
	firewall-cmd --remove-port=8003/udp --permanent

	firewall-cmd --reload

	# 5. Clean mounted drives
	echo "Cleaning mounted drives"
	echo "Removing data from ${MOUNT_1}"
	rm -rf ${MOUNT_1}/*
	echo "Removing data from ${MOUNT_2}"
	rm -rf ${MOUNT_2}/*

	# 6. Remove beegfs repo
	echo "Removing beegfs repository"
	rm -f /etc/yum.repos.d/beegfs-rhel10.repo
	 
	echo "Running yum clean all"
	yum clean all
	yum update -y && yum upgrade -y

	echo "Cleanup completed on $HOST"
EOF

done

