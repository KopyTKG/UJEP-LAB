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
ceph config set mon mon_allow_pool_size_one true
ceph osd pool set benchmark size 1
ceph osd pool set benchmark min_size 1
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

## Speeds on 16x HDD

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

## Speeds on 8x SSD

**Write**

```sh
rados bench -p benchmark 10 write --no-cleanup --block-size 4194304
hints = 1
Maintaining 16 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 10 seconds or 0 objects
Object prefix: benchmark_data_controller_551593
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1      16       199       183   731.852       732    0.115359    0.086507
    2      16       369       353   705.836       680    0.106589    0.088858
    3      16       554       538   717.176       740    0.028232   0.0872118
    4      16       722       706   705.852       672   0.0679121   0.0890508
    5      16       912       896   716.661       760   0.0674792    0.088181
    6      16      1095      1079   719.191       732   0.0673337   0.0883982
    7      16      1258      1242   709.586       652   0.0250188   0.0873679
    8      16      1341      1325   662.387       332   0.0759401   0.0956633
    9      16      1435      1419   630.563       376   0.0549779      0.1002
   10      16      1467      1451   580.309       128   0.0324324    0.106636
Total time run:         10.4422
Total writes made:      1467
Write size:             4194304
Object size:            4194304
Bandwidth (MB/sec):     561.949
Stddev Bandwidth:       219.919
Max bandwidth (MB/sec): 760
Min bandwidth (MB/sec): 128
Average IOPS:           140
Stddev IOPS:            54.9797
Max IOPS:               190
Min IOPS:               32
Average Latency(s):     0.113563
Stddev Latency(s):      0.115491
Max latency(s):         0.84022
Min latency(s):         0.0218058
```

**Read**

```sh
rados bench -p benchmark 10 seq
hints = 1
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       2         2         0         0         0           -           0
    1      16       558       542    2167.7      2168   0.0319355   0.0282696
    2      15      1181      1166   2331.73      2496   0.0238033   0.0263439
Total time run:       2.4862
Total reads made:     1467
Read size:            4194304
Object size:          4194304
Bandwidth (MB/sec):   2360.23
Average IOPS:         590
Stddev IOPS:          57.9828
Max IOPS:             624
Min IOPS:             542
Average Latency(s):   0.0259646
Max latency(s):       0.143849
Min latency(s):       0.0114364
```

## Speeds on 16x SSD

**Write**

```sh
rados bench -p benchmark 10 write --no-cleanup --block-size 4194304
hints = 1
Maintaining 16 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 10 seconds or 0 objects
Object prefix: benchmark_data_controller_719811
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1      16       193       177    707.79       708     0.10247   0.0858451
    2      16       381       365   729.837       752   0.0260299   0.0813987
    3      16       562       546    727.87       724   0.0465956   0.0852349
    4      16       735       719   718.889       692   0.0544374   0.0878668
    5      16       907       891   712.669       688   0.0227168    0.087699
    6      16      1062      1046   697.204       620   0.0289681   0.0905541
    7      16      1218      1202   686.714       624    0.108092   0.0926435
    8      16      1368      1352   675.865       600   0.0277595   0.0933331
    9      16      1553      1537   682.977       740     0.03988   0.0933854
   10      16      1720      1704   681.456       668   0.0867428   0.0933901
Total time run:         10.0932
Total writes made:      1720
Write size:             4194304
Object size:            4194304
Bandwidth (MB/sec):     681.644
Stddev Bandwidth:       52.6692
Max bandwidth (MB/sec): 752
Min bandwidth (MB/sec): 600
Average IOPS:           170
Stddev IOPS:            13.1673
Max IOPS:               188
Min IOPS:               150
Average Latency(s):     0.0934786
Stddev Latency(s):      0.0676944
Max latency(s):         0.360712
Min latency(s):         0.0183195
```

**Read**

```sh
rados bench -p benchmark 10 seq
hints = 1
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       2         2         0         0         0           -           0
    1      15       435       420   1677.75      1680   0.0199348   0.0368424
    2      15      1088      1073   2142.09      2612   0.0163509   0.0286436
Total time run:       2.97427
Total reads made:     1720
Read size:            4194304
Object size:          4194304
Bandwidth (MB/sec):   2313.18
Average IOPS:         578
Stddev IOPS:          164.756
Max IOPS:             653
Min IOPS:             420
Average Latency(s):   0.0264774
Max latency(s):       0.413696
Min latency(s):       0.0112923
```

# Switching to new controller node

- New controller: Another supermicro node
- Rocky linux 10.0
- Ceph installed

> [!WARNING]
> Ceph webUI is borked after migration - needs to be fixed

## Speed

**Write**

> [!IMPORTANT]
> speed is still limited by something on ceph side

```sh
rados bench -p benchmark 30 write -t 128 --no-cleanup --block-size 4194304
hints = 1
Maintaining 128 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 30 seconds or 0 objects
Object prefix: benchmark_data_controller_4579
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1     127       163        36    143.97       144      0.8524    0.854785
    2     127       327       200   399.926       656    0.702558    0.790627
    3     127       505       378   503.917       712    0.743736    0.752519
    4     127       659       532   531.916       616    0.738608    0.777479
    5     127       832       705   563.912       692    0.760133    0.770203
    6     127      1019       892   594.571       748    0.679004    0.752213
    7     127      1184      1057   603.903       660    0.785429    0.753554
    8     127      1344      1217   608.404       640    0.688776    0.759256
    9     127      1494      1367    607.46       600     0.84685    0.763473
   10     127      1658      1531   612.304       656     0.75611    0.768159
   11     127      1832      1705   619.902       696    0.763541    0.767127
   12     127      1910      1783   594.239       312     1.29339    0.772635
   13     127      2013      1886   580.214       412     1.48654    0.810121
   14     127      2063      1936   553.055       200      1.6721    0.835135
   15     127      2123      1996   532.183       240      2.1358    0.862522
   16     127      2220      2093   523.167       388     1.58862    0.903525
   17     127      2286      2159   507.919       264     1.63754    0.930474
   18     127      2343      2216   492.367       228      2.3052    0.963188
   19     127      2368      2241   471.715       100     1.54693    0.974117
2025-11-12T17:26:04.352451+0100 min lat: 0.592842 max lat: 2.64281 avg lat: 1.02079
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
   20     127      2440      2313   462.526       288     2.18952     1.02079
   21     127      2494      2367   450.785       216      2.7979     1.05856
   22     127      2566      2439   443.382       288     1.90611     1.08266
   23     127      2671      2544   442.362       420     1.52277     1.10427
   24     127      2743      2616   435.928       288     1.49777     1.11686
   25     127      2820      2693   430.809       308     1.30215     1.13112
   26     127      2873      2746   422.392       212     1.97305     1.14348
   27     127      2944      2817   417.265       284     2.04418     1.16821
   28     127      3010      2883   411.789       264     1.50085     1.18591
   29     127      3072      2945    406.14       248     2.02269     1.20044
   30     127      3106      2979   397.135       136     2.01827     1.20871
Total time run:         30.2861
Total writes made:      3107
Write size:             4194304
Object size:            4194304
Bandwidth (MB/sec):     410.354
Stddev Bandwidth:       207.756
Max bandwidth (MB/sec): 748
Min bandwidth (MB/sec): 100
Average IOPS:           102
Stddev IOPS:            51.9391
Max IOPS:               187
Min IOPS:               25
Average Latency(s):     1.22731
Stddev Latency(s):      0.58742
Max latency(s):         2.8389
Min latency(s):         0.592842
```

**Read**

> [!Note]
> Read speed is fine

```sh
rados bench -p benchmark 30 seq -t 128
hints = 1
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1     127       726       599   2393.85      2396    0.179036    0.171497
    2     127      1480      1353   2704.59      3016    0.142302    0.172407
    3     127      2309      2182   2907.68      3316    0.158925    0.164781
    4      48      3107      3059   3027.53      3508   0.0931286    0.162635
Total time run:       4.06387
Total reads made:     3107
Read size:            4194304
Object size:          4194304
Bandwidth (MB/sec):   3058.17
Average IOPS:         764
Stddev IOPS:          121.541
Max IOPS:             877
Min IOPS:             599
Average Latency(s):   0.161357
Max latency(s):       0.324929
Min latency(s):       0.0650831
```
