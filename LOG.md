#### 30-10-2025

- Reinstalling all systems to Rocky linux 10.0
- Cleaning up HDDs from old CEPH setup
- Prep for OKD

### OKD

- Needs 3 nodes as "masters" (in prod not used as workers)
- meaning that the cluster would lose 3 OKD nodes from worker pool
- That means we are not using it

### Migration to Open Nebula

### Needed setup commands

1. add ib_ipoib module to /etc/modules-load.d/ib_ipoib.conf

```sh
sudo vim /etc/modules-load.d/ib_ipoib.conf
```

add line: `ib_ipoib`

2. add hosts on ib network (10.0.0.0/24)

```sh
sudo vim /etc/hosts
```

add lines:

```
10.0.0.1 Rocky-OKD-Host-1
10.0.0.2 Rocky-OKD-Host-2
10.0.0.3 Rocky-OKD-Host-3
10.0.0.4 Rocky-OKD-Host-4
10.0.0.5 Rocky-OKD-Host-5
10.0.0.6 Rocky-OKD-Host-6
10.0.0.7 Rocky-OKD-Host-7
10.0.0.8 Rocky-OKD-Host-8

10.0.0.254 controller
```

> [!IMPORTANT]
> ON ALL NODES

3. install opensm module

```sh
sudo dnf install opensm -y
sudo systemctl enable --now opensm
```

```sh
sudo nmtui # set static ip on ib interface in 10.0.0.x subnet (x = node number)
```

> [!IMPORTANT]
> Install ceph-squid

4. Install chrony ntp

```sh
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/chrony.sh | sudo bash
```

5. Install ceph

```sh
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/ceph.sh | sudo bash
```

> [!CAUTION]
> Bootstrap only on controller node

```sh
sudo cephadm bootstrap --mon-ip 10.0.0.254 # Needs to be on the IPoIB network for the ceph cluster to use 100gbps
```

> [!NOTE]
> For easier setup it is recommended to create root ssh key on controller node and share the .pub to all nodes

generate ssh key on controller node

```sh
ssh-keygen
```

then show public key

```sh
cat ~/.ssh/id_ed25519.pub
```

create copy cmd

```sh
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICv..." >> ~/.ssh/authorized_keys
```

then install ssh keys on all nodes

```sh
ssh-copy-id -f -i /etc/ceph/ceph.pub root@Rocky-OKD-Host-*
```

> [!IMPORTANT]
> Root password login is disabled on all nodes
> So you need to copy ssh key manually first time

then on controller node run

```sh
sudo ceph orch host add Rocky-OKD-Host-1
sudo ceph orch host add Rocky-OKD-Host-2
sudo ceph orch host add Rocky-OKD-Host-3
sudo ceph orch host add Rocky-OKD-Host-4
sudo ceph orch host add Rocky-OKD-Host-5
sudo ceph orch host add Rocky-OKD-Host-6
sudo ceph orch host add Rocky-OKD-Host-7
sudo ceph orch host add Rocky-OKD-Host-8
```

> [!IMPORTANT]
> Ceph is on https://controller:8443 (192.168.1.200 as for this lab setup)

### Next steps

1. Setup OSDs on all nodes

- `ll /dev/disk/by-id/wwn-*` to find disks
- `wipefs -a /dev/sdX` to clean disks
- `sudo ceph orch daemon add osd Rocky-OKD-Host-X:/dev/disk/by-id/wwn-XXXX` to add OSD

### Testing the speed of the ceph cluster

```sh
ceph osd pool create benchmark 64 64
```

**Write test**

```sh
rados bench -p benchmark 10 write --block-size 4194304
```

**Read test**

```sh
rados bench -p benchmark 10 seq
```

**Cleanup**

```sh
ceph osd pool rm benchmark benchmark --yes-i-really-really-mean-it
```

## Speeds on all HDD

> [!IMPORTANT]
> During test a big issue has been found that disks are heavily limited by IOPS on ceph cluster

**Write**

```sh
rados bench -p benchmark 10 write --no-cleanup --block-size 4194304
hints = 1
Maintaining 16 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 10 seconds or 0 objects
Object prefix: benchmark_data_controller_115538
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1      16        63        47    187.92       188     0.14866    0.280023
    2      16       116       100   199.923       212    0.205767    0.277006
    3      16       169       153   203.924       212    0.183315    0.294263
    4      16       230       214   213.923       244   0.0772566    0.288087
    5      16       272       256   204.727       168    0.396065    0.293771
    6      16       326       310   206.593       216    0.314677    0.300614
    7      16       384       368   210.211       232    0.350264    0.294811
    8      16       440       424   211.924       224    0.314712    0.295449
    9      16       495       479   212.817       220    0.278219    0.295796
   10      16       544       528   211.128       196    0.166084    0.295981
Total time run:         10.32
Total writes made:      544
Write size:             4194304
Object size:            4194304
Bandwidth (MB/sec):     210.854
Stddev Bandwidth:       22.1349
Max bandwidth (MB/sec): 244
Min bandwidth (MB/sec): 168
Average IOPS:           52
Stddev IOPS:            5.53373
Max IOPS:               61
Min IOPS:               42
Average Latency(s):     0.300001
Stddev Latency(s):      0.161065
Max latency(s):         0.862328
Min latency(s):         0.063151
```

**Read**

```sh
rados bench -p benchmark 10 seq
hints = 1
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       2         2         0         0         0           -           0
    1      16       154       138   551.777       552   0.0613755    0.098897
    2      16       320       304   607.793       664    0.127268    0.101212
    3      16       492       476   634.404       688   0.0647372   0.0976329
Total time run:       3.5181
Total reads made:     544
Read size:            4194304
Object size:          4194304
Bandwidth (MB/sec):   618.516
Average IOPS:         154
Stddev IOPS:          18.1475
Max IOPS:             172
Min IOPS:             138
Average Latency(s):   0.0995232
Max latency(s):       0.780926
Min latency(s):       0.014887
```

```sh
rados bench -p benchmark 100 seq
hints = 1
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       2         2         0         0         0           -           0
    1      16       276       260   1039.83      1040  0.00621783   0.0570613
Total time run:       1.80244
Total reads made:     544
Read size:            4194304
Object size:          4194304
Bandwidth (MB/sec):   1207.25
Average IOPS:         301
Stddev IOPS:          0
Max IOPS:             260
Min IOPS:             260
Average Latency(s):   0.047933
Max latency(s):       0.541004
Min latency(s):       0.00232347
```
