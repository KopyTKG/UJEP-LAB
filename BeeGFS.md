# Initial setup of the node

## Prerequisites

### Install Chrony NTP

> [!NOTE]
> Because i am setting this up in Czech republic, i am using tik.cesnet.cz and tak.cesnet.cz as NTP servers, change them to your local NTP servers

1. Install chrony

```bash
sudo dnf install -y chrony
```

2. Configure chrony (i'll use tee for easy copy paste)

```bash
tee /etc/chrony.conf > /dev/null <<EOF
server tik.cesnet.cz iburst
server tak.cesnet.cz iburst

sourcedir /run/chrony-dhcp
driftfile /var/lib/chrony/drift
makestep 1.0 3
rtcsync
keyfile /etc/chrony.keys
ntsdumpdir /var/lib/chrony
leapsectz right/UTC
logdir /var/log/chrony
EOF
```

3. Open firewall for NTP

```bash
sudo firewall-cmd --add-service=ntp --permanent
sudo firewall-cmd --reload
```

4. Enable and start chrony

```bash
sudo systemctl enable --now chronyd
```

### Enable InfiniBand IP over IB (ib_ipoib) module to load at boot

> [!NOTE]
> Rocky Linux 10 (RHEL 10) does not load the `ib_ipoib` module by default, so we need to enable it to load at boot.

1. Create load module config file with content to load `ib_ipoib` module

```bash
sudo tee /etc/modules-load.d/ib_ipoib.conf > /dev/null <<EOF
ib_ipoib
EOF
```

2. _Reboot the system to apply changes (or skip to step 3 to load module without reboot)_

```bash
sudo reboot
```

3. Load the `ib_ipoib` module immediately

> [!NOTE]
> Reboot is not needed, you can load the module with:

```bash
sudo modprobe ib_ipoib
```

### Setup /etc/hosts file so hostnames resolve correctly over IB

```bash
sudo tee -a /etc/hosts > /dev/null <<EOF
# Ibs1
10.0.0.1 Rocky-Compute-1
10.0.0.2 Rocky-Compute-2
10.0.0.3 Rocky-Compute-3
10.0.0.4 Rocky-Compute-4
10.0.0.5 Rocky-Compute-5
10.0.0.6 Rocky-Compute-6
10.0.0.7 Rocky-Compute-7
10.0.0.8 Rocky-Compute-8
10.0.0.254 controller
# Eth 1
192.168.1.101 Rocky-Eth1-1
192.168.1.102 Rocky-Eth1-2
192.168.1.103 Rocky-Eth1-3
192.168.1.104 Rocky-Eth1-4
192.168.1.105 Rocky-Eth1-5
192.168.1.106 Rocky-Eth1-6
192.168.1.107 Rocky-Eth1-7
192.168.1.108 Rocky-Eth1-8
192.168.1.100 Controller-Eth1
# Eth 2
192.168.2.101 Rocky-Eth2-1
192.168.2.102 Rocky-Eth2-2
192.168.2.103 Rocky-Eth2-3
192.168.2.104 Rocky-Eth2-4
192.168.2.105 Rocky-Eth2-5
192.168.2.106 Rocky-Eth2-6
192.168.2.107 Rocky-Eth2-7
192.168.2.108 Rocky-Eth2-8
192.168.2.100 Controller-Eth2
EOF
```

### Install OpenSM on all nodes (required for IB subnet management)

1. Install OpenSM and enable it to start at boot

```bash
sudo dnf install opensm -y
sudo systemctl enable --now opensm
```

2. Add ip to the IB interface manually via nmtui: (_can be also done via nmcli, see below_)

```bash
sudo nmtui
```

3. Add ip to the IB interface automatically via cli command

```bash
sudo nmcli con mod ibs1 ipv4.addresses 10.0.0.x/24 ipv4.method manual
sudo nmcli con up ibs1
```

## Adding repository and installing BeeGFS

> [!NOTE]
> Update the repo URL to the latest version from BeeGFS website if needed.

Website: [https://www.beegfs.io/release/](https://www.beegfs.io/release/)

```bash
sudo wget https://www.beegfs.io/release/beegfs_8.2/dists/beegfs-rhel10.repo -O /etc/yum.repos.d/beegfs-rhel10.repo
sudo rpm --import https://www.beegfs.io/release/beegfs_8.2/gpg/GPG-KEY-beegfs
```

```bash
sudo dnf update
```

### BeeGFS components

- beeGFS Client - needed on all nodes that will access the BeeGFS filesystem
- beeGFS Management Service - needed on single node (controller) to manage the BeeGFS cluster
- beeGFS Metadata Service - needed on single node (controller) to store filesystem metadata (might cachen in future to have more speed + redundancy)
- beeGFS Storage Service - needed on all storage nodes to store the actual data

### Ports

| Service           | TCP Ports  | UDP Ports |
| ----------------- | ---------- | --------- |
| beeGFS Management | 8008, 8010 | 8008      |
| beeGFS Metadata   | 8005       | 8005      |
| beeGFS Storage    | 8003       | 8003      |
| beeGFS Client     | 8004       | 8004      |

<details>

<summary><h2>Installing Controller Node</h2></summary>

```bash
sudo yum install -y beegfs-client beegfs-tools beegfs-utils beegfs-mgmtd beegfs-meta beegfs-mon # libbeegfs-ib - if RDMA is needed
sudo dnf install -y kernel-devel gcc make
```

#### Initialize BeeGFS management configuration

```bash
sudo /opt/beegfs/sbin/beegfs-mgmtd --init
```

#### Setup conn password

```bash
sudo dd if=/dev/random of=/etc/beegfs/conn.auth bs=128 count=1
sudo chown root:root /etc/beegfs/conn.auth
sudo chmod 400 /etc/beegfs/conn.auth

sudo scp /etc/beegfs/conn.auth root@Rocky-Compute-1:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-Compute-2:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-Compute-3:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-Compute-4:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-Compute-5:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-Compute-6:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-Compute-7:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-Compute-8:/etc/beegfs/conn.auth
```

#### Disable TLS

```bash
sudo vim /etc/beegfs/beegfs-mgmtd.toml
```

Set `TLS-disable = true`

#### Initialize management service

```bash
sudo firewall-cmd --add-port=8008/tcp --permanent
sudo firewall-cmd --add-port=8008/udp --permanent
sudo firewall-cmd --add-port=8010/tcp --permanent
sudo firewall-cmd --add-port=8005/tcp --permanent
sudo firewall-cmd --add-port=8005/udp --permanent
sudo firewall-cmd --add-port=8004/tcp --permanent
sudo firewall-cmd --add-port=8004/udp --permanent
sudo firewall-cmd --reload
```

```bash
sudo systemctl enable --now beegfs-mgmtd
```

#### Setup metadata device

1. locate drives for metadata (meta can be create only on single device so to have more space use LVM)

```bash
sudo fdisk -l
```

2. clean the drives

```bash
sudo wipefs -a /dev/sdX  # replace sdX with the actual device name
sudo wipefs -a /dev/sdY  # replace sdY with the actual device name
```

3. create LVM on the drives

```bash
sudo pvcreate /dev/sdX /dev/sdY
sudo vgcreate beegfs_meta_vg /dev/sdX /dev/sdY
sudo lvcreate -l 100%FREE -n beegfs_meta_lv beegfs_meta_vg
```

4. create filesystem on the LVM logical volume (BeeGFS metadata requires `ext4` filesystem)

```bash
sudo mkfs.ext4 /dev/beegfs_meta_vg/beegfs_meta_lv
```

5. create mount point

```bash
sudo mkdir /mnt/beegfs_meta
```

6. get UUID of the new filesystem

```bash
sudo blkid
```

7. add entry to `/etc/fstab` to mount the filesystem at boot

```bash
sudo vim /etc/fstab
```

Add the following line: \_(Change `xxxxxx` to the UUID found in `blkid`)

```bash
UUID=xxxxxx  /mnt/beegfs_meta  ext4  defaults  0  0
```

8. mount the filesystem

```bash
sudo systemctl daemon-reload
sudo mount -a # might need (systemctl daemon-reload) first
```

#### Setting up BeeGFS metadata device

```bash
sudo /opt/beegfs/sbin/beegfs-setup-meta -p /mnt/beegfs_meta/beegfs_metadata -i 99 -m controller -f
```

#### Start metadata service

```bash
sudo systemctl enable --now beegfs-meta
```

#### Setting up BeeGFS monitor service

TBD

#### Setting up BeeGFS client

```bash
sudo /opt/beegfs/sbin/beegfs-setup-client -m controller
```

</details>

<details>
<summary><h2>Installing Storage (`Compute`) Node </h2></summary>

```bash
sudo yum install -y beegfs-storage beegfs-tools beegfs-utils beegfs-client  # libbeegfs-ib - if RDMA is needed
sudo dnf install -y kernel-devel gcc make
```

#### Prepare storage

1. locate drives for storage (need at least 1 drive per storage node)

```bash
sudo fdisk -l
```

2. clean the drives

```bash
sudo wipefs -a /dev/sdX  # replace sdX with the actual device name
sudo parted /dev/sdX mklabel gpt
```

3. create filesystem on the drives (BeeGFS storage requires `xfs` filesystem)

```bash
sudo mkfs.xfs -f /dev/sdX
```

4. create mount points

```bash
sudo mkdir /mnt/myraid1
```

5. get UUID of the new filesystem

```bash
sudo blkid
```

6. add entry to `/etc/fstab` to mount the filesystem at boot

```bash
sudo vim /etc/fstab # add entries for mounting
```

Add the following lines: _(Change `xxxxxx` and `yyyyyy` to the UUID found in `blkid`)_

```bash
UUID=xxxxxx  /mnt/myraid1  xfs  defaults  0  0
UUID=yyyyyy  /mnt/myraid2  xfs  defaults  0  0
```

7. mount the filesystem

```bash
sudo systemctl daemon-reload
sudo mount -a
```

#### Setting up BeeGFS storage device

> [!NOTE]
> Only the first device needs to like to controller, the rest will copy the 1st device connection settings

1. Adding first drive to storage pool X with id X01 as controller (where X is the ID of the node so like `1` - `101`)

```bash
sudo /opt/beegfs/sbin/beegfs-setup-storage -p /mnt/myraid1/beegfs_storage -s X -i X01 -m controller -f
```

2. Adding second drive to storage pool X with id X02 (where X is the ID of the node so like `1` - `102`)

```bash
sudo /opt/beegfs/sbin/beegfs-setup-storage -p /mnt/myraid2/beegfs_storage -s X -i X02
```

#### Start storage service

1. Add firewall rules

```bash
sudo firewall-cmd --add-port=8003/tcp --permanent
sudo firewall-cmd --add-port=8003/udp --permanent
sudo firewall-cmd --reload
```

2. Enable and start BeeGFS storage service

```bash
sudo systemctl enable --now beegfs-storage
```

</details>

## Testing BeeGFS

**Write benchmark**

```bash
sudo beegfs benchmark start --block-size=1MiB --size=5GiB --num-tasks=48 --watch=1s
```

**Cleanup benchmark data**

```bash
sudo beegfs benchmark cleanup
```

### Speed on 16x SSD

> [!IMPORTANT]
> New bottle neck found: Some SSDs have limited cache size, when the cache is full, the write speed drops significantly.
> Speeds start around 10GiB/s ,but in first 5 seconds the cache fills up and speed drops to around 1GiB/s

```bash
+-----------------------------------------------------------------------------------------------------+
|                                       Overall Benchmark Status                                      |
+---------------+-------------+-------+---------+----------+---------+-----------+----------+---------+
| UNINITIALIZED | INITIALIZED | ERROR | RUNNING | STOPPING | STOPPED | FINISHING | FINISHED | UNKNOWN |
+---------------+-------------+-------+---------+----------+---------+-----------+----------+---------+
|             0 |           0 |     7 |       0 |        0 |       0 |         0 |        0 |       0 |
+---------------+-------------+-------+---------+----------+---------+-----------+----------+---------+
+--------------------------------------------------------------------+
|                      Benchmark Status by Node                      |
+---------+----------------+--------+--------+-----------------------+
| NODE ID | NODE ALIAS     | STATUS | ACTION |            ERROR CODE |
+---------+----------------+--------+--------+-----------------------+
| s:1     | node_storage_1 |  error | status | I/O error from worker |
| s:2     | node_storage_2 |  error | status | I/O error from worker |
| s:4     | node_storage_4 |  error | status | I/O error from worker |
| s:5     | node_storage_5 |  error | status | I/O error from worker |
| s:6     | node_storage_6 |  error | status | I/O error from worker |
| s:7     | node_storage_7 |  error | status | I/O error from worker |
| s:8     | node_storage_8 |  error | status | I/O error from worker |
+---------+----------------+--------+--------+-----------------------+
+----------------------------------------------------------------------------+
|                             WRITE Test Summary                             |
+-----------+-------------+-----------+---------------------+----------------+
| METRIC    | THROUGHPUT  | TARGET ID | TARGET ALIAS        | ON NODE        |
+-----------+-------------+-----------+---------------------+----------------+
| Minimum   |  27.84MiB/s | s:802     | target_1-69160369-8 | node_storage_8 |
| Maximum   | 205.83MiB/s | s:101     | target_0-6916013C-1 | node_storage_1 |
| Average   |  84.93MiB/s | -         | -                   |                |
| Aggregate |   1.16GiB/s | -         | -                   |                |
+-----------+-------------+-----------+---------------------+----------------+
```

### Speed on 16x HDD

```bash

+-----------------------------------------------------------------------------------------------------+
|                                       Overall Benchmark Status                                      |
+---------------+-------------+-------+---------+----------+---------+-----------+----------+---------+
| UNINITIALIZED | INITIALIZED | ERROR | RUNNING | STOPPING | STOPPED | FINISHING | FINISHED | UNKNOWN |
+---------------+-------------+-------+---------+----------+---------+-----------+----------+---------+
|             0 |           0 |     0 |       0 |        0 |       0 |         0 |        6 |       0 |
+---------------+-------------+-------+---------+----------+---------+-----------+----------+---------+
+----------------------------------------------------------------------------+
|                             WRITE Test Summary                             |
+-----------+-------------+-----------+---------------------+----------------+
| METRIC    | THROUGHPUT  | TARGET ID | TARGET ALIAS        | ON NODE        |
+-----------+-------------+-----------+---------------------+----------------+
| Minimum   | 141.81MiB/s | s:801     | target_0-691DE943-8 | node_storage_8 |
| Maximum   | 499.76MiB/s | s:402     | target_1-691DE93D-4 | node_storage_4 |
| Average   | 239.06MiB/s | -         | -                   |                |
| Aggregate |   2.80GiB/s | -         | -                   |                |
+-----------+-------------+-----------+---------------------+----------------+

```
