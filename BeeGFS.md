# BeeGFS journey

- Start: 13-11-2025

## Adding repository and installing BeeGFS

```bash
sudo wget https://www.beegfs.io/release/beegfs_8.2/dists/beegfs-rhel10.repo -O /etc/yum.repos.d/beegfs-rhel10.repo
sudo rpm --import https://www.beegfs.io/release/beegfs_8.2/gpg/GPG-KEY-beegfs
```

```bash
sudo dnf update
```

### Controller node

```bash
sudo yum install -y beegfs-client beegfs-tools beegfs-utils beegfs-mgmtd beegfs-meta beegfs-mon # libbeegfs-ib - if RDMA is needed
sudo dnf install -y kernel-devel gcc make
```

#### Setup conn password

```bash
dd if=/dev/random of=/etc/beegfs/conn.auth bs=128 count=1
chown root:root /etc/beegfs/conn.auth
chmod 400 /etc/beegfs/conn.auth

sudo scp /etc/beegfs/conn.auth root@Rocky-OKD-Host-1:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-OKD-Host-2:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-OKD-Host-3:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-OKD-Host-4:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-OKD-Host-5:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-OKD-Host-6:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-OKD-Host-7:/etc/beegfs/conn.auth
sudo scp /etc/beegfs/conn.auth root@Rocky-OKD-Host-8:/etc/beegfs/conn.auth
```

#### Disable TLS

```bash
vim /etc/beegfs/beegfs-mgmtd.toml
```

Set `TLS-disable = true`

#### Initialize management service

```bash
firewall-cmd --add-port=8008/tcp --permanent
firewall-cmd --add-port=8008/udp --permanent
firewall-cmd --add-port=8010/tcp --permanent
firewall-cmd --add-port=8005/tcp --permanent
firewall-cmd --add-port=8005/udp --permanent
firewall-cmd --add-port=8004/tcp --permanent
firewall-cmd --add-port=8004/udp --permanent
firewall-cmd --reload
```

```bash
systemctl enable --now beegfs-mgmtd
```

#### Setup metadata device

```bash
fdisk -l

wipefs -a /dev/sdX  # replace sdX with the actual device name
wipefs -a /dev/sdY  # replace sdY with the actual device name

pvcreate /dev/sdX /dev/sdY
vgcreate beegfs_meta_vg /dev/sdX /dev/sdY
lvcreate -l 100%FREE -n beegfs_meta_lv beegfs_meta_vg
mkfs.ext4 /dev/beegfs_meta_vg/beegfs_meta_lv

mkdir /mnt/beegfs_meta

blkid
vim /etc/fstab # add entry for mounting
mount -a # might need (systemctl daemon-reload) first
```

#### Setting up BeeGFS metadata device

```bash
/opt/beegfs/sbin/beegfs-setup-meta -p /mnt/beegfs_meta/beegfs_metadata -i 99 -m controller -f
```

#### Start metadata service

```bash
systemctl enable --now beegfs-meta
```

#### Setting up BeeGFS monitor service

TBD

#### Setting up BeeGFS client

```bash
/opt/beegfs/sbin/beegfs-setup-client -m controller
```

### Storage node

```bash
sudo yum install -y beegfs-storage beegfs-tools beegfs-utils beegfs-client  # libbeegfs-ib - if RDMA is needed
sudo dnf install -y kernel-devel gcc make
```

#### Prepare storage

```bash
fdisk -l

wipefs -a /dev/sdX  # replace sdX with the actual device name
parted /dev/sdX mklabel gpt

sudo mkfs.xfs -f /dev/sdX

mkdir myraid1
mkdir myraid2

blkid

vim /etc/fstab # add entries for mounting

mount -a # might need (systemctl daemon-reload) first
```

#### Setting up BeeGFS storage device

```bash
/opt/beegfs/sbin/beegfs-setup-storage -p /mnt/myraid1/beegfs_storage -s X -i X01 -m controller -f
/opt/beegfs/sbin/beegfs-setup-storage -p /mnt/myraid2/beegfs_storage -s X -i X02
```

## Testing BeeGFS

**Write benchmark**

```bash
beegfs benchmark start --block-size=1MiB --size=5GiB --num-tasks=48 --watch=1s
```

**Cleanup benchmark data**

```bash
beegfs benchmark cleanup
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
