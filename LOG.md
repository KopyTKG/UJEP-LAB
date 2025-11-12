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
rados bench -p benchmark 10 write --no-cleanup --block-size 4194304
```

**Read test**

```sh
rados bench -p benchmark 10 seq
```

**Cleanup**

```sh
ceph config set mon mon_allow_pool_delete true
ceph osd pool rm benchmark benchmark --yes-i-really-really-mean-it
ceph config set mon mon_allow_pool_delete false
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

## Speeds on mix 8x HDD + 8x SSD

> [!IMPORTANT]
> During test a big issue has been found that ceph does not like mixed OSD types in one pool

**Write**

```sh
rados bench -p benchmark 10 write --no-cleanup --block-size 4194304
hints = 1
Maintaining 16 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 10 seconds or 0 objects
Object prefix: benchmark_data_controller_530951
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1      16        54        38    151.98       152    0.194043    0.385203
    2      16        92        76   151.981       152    0.196817    0.357601
    3      16       139       123    163.97       188    0.157435    0.369355
    4      16       184       168   167.962       180    0.478354    0.364508
    5      16       226       210   167.964       168    0.473871    0.362843
    6      16       264       248     165.3       152    0.566235    0.367795
    7      16       312       296   169.105       192    0.184803    0.371747
    8      16       357       341   170.459       180    0.129034    0.367574
    9      16       397       381    169.29       160    0.310785    0.369737
   10      16       436       420   167.956       156    0.107872     0.36616
Total time run:         10.3741
Total writes made:      436
Write size:             4194304
Object size:            4194304
Bandwidth (MB/sec):     168.111
Stddev Bandwidth:       15.7762
Max bandwidth (MB/sec): 192
Min bandwidth (MB/sec): 152
Average IOPS:           42
Stddev IOPS:            3.94405
Max IOPS:               48
Min IOPS:               38
Average Latency(s):     0.373821
Stddev Latency(s):      0.190461
Max latency(s):         0.990528
Min latency(s):         0.0579082
Min latency(s):       0.00232347
```

**Read**

```sh
rados bench -p benchmark 10 seq
hints = 1
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       2         2         0         0         0           -           0
    1      16       144       128   511.873       512   0.0673865   0.0927786
    2      16       280       264   527.885       544    0.178962    0.107543
    3      16       391       375   499.898       444   0.0291952    0.113412
    4       3       436       433   432.925       232    0.740228    0.133473
Total time run:       4.08376
Total reads made:     436
Read size:            4194304
Object size:          4194304
Bandwidth (MB/sec):   427.058
Average IOPS:         106
Stddev IOPS:          35.0844
Max IOPS:             136
Min IOPS:             58
Average Latency(s):   0.137252
Max latency(s):       1.09661
Min latency(s):       0.0124099
```
