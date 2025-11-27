#!/bin/bash

# --- CONFIGURATION ---
# Prefix for your nodes (e.g., Rocky-Compute-1, Rocky-Compute-2...)
NODE_PREFIX="Rocky-Eth1-"
# Range of nodes
START_NODE=1
END_NODE=8

# The physical disks you inserted
DISK_1="/dev/sdb"
DISK_2="/dev/sdc"

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

        # 1. Create Mount Points
        mkdir -p $MOUNT_1
        mkdir -p $MOUNT_2

        # 2. Get UUIDs dynamically (Safety check)
        UUID1=\$(blkid -s UUID -o value $DISK_1)
        UUID2=\$(blkid -s UUID -o value $DISK_2)

        if [ -z "\$UUID1" ] || [ -z "\$UUID2" ]; then
            echo "❌ ERROR: Could not read UUIDs for $DISK_1 or $DISK_2."
            echo "   Are the disks formatted? (Run mkfs.xfs first if not!)"
            exit 1
        fi

        echo "   Found UUID for $DISK_1: \$UUID1"
        echo "   Found UUID for $DISK_2: \$UUID2"

        # 3. Add to fstab (Only if not already there)
        # We use grep to check if the UUID exists to avoid duplicates

        if ! grep -q "\$UUID1" /etc/fstab; then
            echo "UUID=\$UUID1  $MOUNT_1  xfs  defaults  0  0" >> /etc/fstab
            echo "   ✅ Added $DISK_1 to fstab"
        else
            echo "   ⚠️  $DISK_1 is already in fstab. Skipping."
        fi

        if ! grep -q "\$UUID2" /etc/fstab; then
            echo "UUID=\$UUID2  $MOUNT_2  xfs  defaults  0  0" >> /etc/fstab
            echo "   ✅ Added $DISK_2 to fstab"
        else
            echo "   ⚠️  $DISK_2 is already in fstab. Skipping."
        fi

        # 4. Mount everything
	systemctl daemon-reload
        mount -a

        # 5. Verify
        echo "   📊 Current Mounts:"
        df -h | grep "/mnt"

	# 6. Add disks to storage pool
	echo "Adding disks to pool"
	/opt/beegfs/sbin/beegfs-setup-storage -p /mnt/ssd1/beegfs_storage -s X -i ${I}01 -m controller -f
	/opt/beegfs/sbin/beegfs-setup-storage -p /mnt/ssd2/beegfs_storage -s X -i ${I}02

	# 7. start storage
	systemctl enable --now beegfs-storage
	
EOF

done
