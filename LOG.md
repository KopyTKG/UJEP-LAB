# CEPH journey

- Start: 30-10-2025

> [!NOTE]
> CEPH has not been proper for the lab usage due to low IOPS speeds and high latency causing issues with low Raw speed.

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
ceph osd pool set benchmark size 1 --yes-i-really-mean-it
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

## Writes

### 1 replica

```sh
rados bench -p benchmark 30 write -t 64 --no-cleanup --block-size 4194304
hints = 1
Maintaining 64 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 30 seconds or 0 objects
Object prefix: benchmark_data_controller_16514
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1      63       401       338   1351.76      1352    0.174807    0.153774
    2      63       712       649    1297.8      1244   0.0961064    0.187513
    3      63      1175      1112   1482.46      1852    0.125368    0.164995
    4      63      1581      1518   1517.79      1624    0.278766    0.163434
    5      63      1928      1865   1491.79      1388     0.18839    0.164952
    6      63      2141      2078   1385.14       852    0.187521    0.179567
    7      63      2500      2437   1392.38      1436    0.135001    0.180065
    8      63      2907      2844    1421.8      1628    0.123993    0.177284
    9      63      3275      3212   1427.36      1472    0.164925    0.175791
   10      63      3662      3599    1439.4      1548    0.143553    0.175803
   11      63      4055      3992   1451.44      1572    0.189064    0.173537
   12      63      4442      4379   1459.47      1548    0.154183    0.173319
   13      63      4842      4779   1470.26      1600    0.160642    0.172139
   14      63      5266      5203   1486.37      1696     0.13602    0.170297
   15      63      5608      5545   1478.47      1368    0.201995    0.170912
   16      63      5829      5766   1441.31       884    0.347437    0.173152
   17      63      6020      5957   1401.46       764    0.222117    0.180044
   18      63      6078      6015   1336.49       232     0.90314    0.184668
   19      63      6196      6133   1290.99       472    0.686013    0.190154
2025-11-12T17:52:38.608427+0100 min lat: 0.0727997 max lat: 1.46897 avg lat: 0.197376
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
   20      63      6466      6403   1280.43      1080    0.187127    0.197376
   21      63      6554      6491   1236.21       352     1.75505      0.1997
   22      63      6854      6791   1234.56      1200    0.795286    0.205622
   23      63      6941      6878   1196.01       348    0.571981    0.208952
   24      63      7135      7072   1178.51       776    0.206945    0.214811
   25      63      7270      7207   1152.97       540    0.122467    0.220746
   26      63      7400      7337   1128.62       520    0.459628    0.222418
   27      63      7534      7471   1106.67       536    0.212581    0.229037
   28      63      7698      7635   1090.57       656    0.410623    0.230936
   29      63      7853      7790   1074.34       620      0.4763    0.233441
   30      63      8001      7938   1058.26       592    0.219089    0.239644
Total time run:         31.0021
Total writes made:      8002
Write size:             4194304
Object size:            4194304
Bandwidth (MB/sec):     1032.45
Stddev Bandwidth:       493.041
Max bandwidth (MB/sec): 1852
Min bandwidth (MB/sec): 232
Average IOPS:           258
Stddev IOPS:            123.26
Max IOPS:               463
Min IOPS:               58
Average Latency(s):     0.241985
Stddev Latency(s):      0.240581
Max latency(s):         1.85913
Min latency(s):         0.0727997
```

### 2 replicas

```sh
rados bench -p benchmark 30 write -t 64 --no-cleanup --block-size 4194304
hints = 1
Maintaining 64 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 30 seconds or 0 objects
Object prefix: benchmark_data_controller_16975
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1      63       190       127   507.908       508    0.324782    0.350391
    2      63       400       337   673.892       840    0.272918    0.325861
    3      63       560       497   662.563       640    0.266481    0.347558
    4      63       744       681   680.892       736     0.33286    0.348962
    5      63       908       845   675.888       656    0.354036    0.355562
    6      63      1098      1035   689.886       760    0.348473    0.349892
    7      63      1279      1216   694.745       724    0.287008    0.352956
    8      63      1457      1394    696.89       712    0.272222    0.355545
    9      63      1640      1577   700.781       732    0.269772    0.355049
   10      63      1786      1723   689.092       584    0.529762    0.357546
   11      63      1942      1879   683.166       624    0.349474    0.364259
   12      63      2081      2018   672.564       556    0.366881    0.371905
   13      63      2194      2131   655.593       452    0.626423    0.374692
   14      63      2290      2227   636.189       384    0.612364    0.387848
   15      63      2406      2343   624.706       464    0.997421    0.399872
   16      63      2535      2472   617.908       516    0.431558    0.404652
   17      63      2673      2610   614.027       552    0.516144    0.408947
   18      63      2797      2734   607.467       496    0.447618    0.411862
   19      63      2906      2843   598.439       436    0.360511    0.420072
2025-11-12T17:54:34.337599+0100 min lat: 0.178304 max lat: 1.66958 avg lat: 0.42381
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
   20      63      3007      2944   588.714       404    0.521352     0.42381
   21      63      3156      3093   589.057       596    0.439468    0.427364
   22      63      3246      3183   578.644       360    0.642274    0.433921
   23      63      3388      3325   578.178       568    0.483544    0.435993
   24      63      3495      3432   571.918       428    0.558535     0.43961
   25      63      3572      3509    561.36       308    0.550019    0.447149
   26      63      3664      3601    553.92       368    0.519946     0.45441
   27      63      3780      3717   550.587       464    0.525884    0.457596
   28      63      3869      3806   543.636       356    0.509287    0.464369
   29      63      3988      3925   541.301       476    0.569383    0.465565
   30      63      4068      4005   533.922       320    0.728015    0.471281
Total time run:         30.184
Total writes made:      4069
Write size:             4194304
Object size:            4194304
Bandwidth (MB/sec):     539.225
Stddev Bandwidth:       144.317
Max bandwidth (MB/sec): 840
Min bandwidth (MB/sec): 308
Average IOPS:           134
Stddev IOPS:            36.0792
Max IOPS:               210
Min IOPS:               77
Average Latency(s):     0.471038
Stddev Latency(s):      0.198782
Max latency(s):         1.66958
Min latency(s):         0.0376623
```

## 256 PGS

### 1 replica

```sh
rados bench -p benchmark 30 write -t 64 --no-cleanup --block-size 4194304
hints = 1
Maintaining 64 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 30 seconds or 0 objects
Object prefix: benchmark_data_controller_17883
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1      63       382       319   1275.76      1276    0.151745    0.173676
    2      63       750       687   1373.76      1472     0.11721    0.175267
    3      63      1165      1102   1469.09      1660    0.177787    0.165238
    4      63      1509      1446   1445.77      1376    0.155189    0.170127
    5      63      1909      1846   1476.57      1600    0.158118    0.168681
    6      63      2343      2280   1519.75      1736     0.12906    0.165619
    7      63      2615      2552   1458.05      1088    0.337587    0.166371
    8      63      2821      2758   1378.78       824   0.0993155    0.183261
    9      63      3003      2940   1306.46       728    0.517656    0.183711
   10      63      3232      3169    1267.4       916    0.120824     0.19883
   11      63      3577      3514   1277.62      1380    0.197856    0.196294
   12      63      3913      3850   1283.14      1344    0.145344    0.196933
   13      63      4193      4130   1270.57      1120    0.108751    0.199581
   14      63      4469      4406   1258.66      1104    0.213403    0.200548
   15      63      4642      4579   1220.88       692     0.23207    0.204516
   16      63      4868      4805   1201.06       904    0.634536    0.208199
   17      63      5016      4953   1165.23       592    0.520339    0.212402
   18      63      5132      5069   1126.27       464    0.155028     0.22396
   19      63      5366      5303   1116.25       936    0.194563    0.226586
2025-11-12T17:57:34.727597+0100 min lat: 0.0796817 max lat: 2.06854 avg lat: 0.229346
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
   20      63      5522      5459   1091.63       624    0.263091    0.229346
   21      63      5746      5683    1082.3       896    0.284541    0.233193
   22      63      6010      5947    1081.1      1056    0.142857    0.234983
   23      63      6069      6006   1044.35       236    0.670821    0.235186
   24      63      6273      6210   1034.83       816    0.299673    0.244025
   25      63      6556      6493   1038.71      1132    0.300399    0.243793
   26      63      6796      6733   1035.68       960    0.294957    0.244458
   27      63      7047      6984    1034.5      1004    0.206322    0.245738
   28      63      7110      7047   1006.55       252    0.692392    0.246058
   29      63      7291      7228   996.804       724     0.24417    0.254222
   30      63      7392      7329   977.042       404    0.479716     0.25699
Total time run:         30.1809
Total writes made:      7393
Write size:             4194304
Object size:            4194304
Bandwidth (MB/sec):     979.824
Stddev Bandwidth:       394.553
Max bandwidth (MB/sec): 1736
Min bandwidth (MB/sec): 236
Average IOPS:           244
Stddev IOPS:            98.6384
Max IOPS:               434
Min IOPS:               59
Average Latency(s):     0.259513
Stddev Latency(s):      0.25114
Max latency(s):         2.06854
Min latency(s):         0.0210532
```

### 2 replicas

> ![IMPORTANT]
> Test was unstable - speeds vary wildly from 20MB/s to 600MB/s

```sh
rados bench -p benchmark 30 write -t 64 --no-cleanup --block-size 4194304
hints = 1
Maintaining 64 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 30 seconds or 0 objects
Object prefix: benchmark_data_controller_19565
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1      63       108        45   179.965       180    0.542074     0.39141
    2      63       108        45   89.9847         0           -     0.39141
    3      63       108        45     59.99         0           -     0.39141
    4      63       108        45   44.9928         0           -     0.39141
    5      63       108        45   35.9945         0           -     0.39141
    6      63       117        54   35.9946       7.2     5.45322     1.20575
    7      63       117        54   30.8524         0           -     1.20575
    8      63       121        58   28.9956         8      7.6287     1.64094
    9      63       121        58   25.7739         0           -     1.64094
   10      63       121        58   23.1965         0           -     1.64094
   11      63       121        58   21.0877         0           -     1.64094
   12      63       121        58   19.3304         0           -     1.64094
   13      63       127        64   19.6893       4.8     12.6007     2.65346
   14      63       131        68   19.4256        16     12.8587     3.24978
   15      63       147        84   22.3966        64     14.2901     5.34395
   16      63       147        84   20.9969         0           -     5.34395
   17      63       160        97   22.8201        26     11.2241     6.38275
   18      63       162        99   21.9967         8     17.1836     6.52116
   19      63       173       110   23.1544        44     5.73344     6.55053
2025-11-12T18:01:16.426297+0100 min lat: 0.298035 max lat: 17.1836 avg lat: 6.51383
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
   20      63       175       112   22.3967         8     4.50927     6.51383
   21      63       175       112   21.3301         0           -     6.51383
   22      63       175       112   20.3606         0           -     6.51383
   23      63       175       112   19.4753         0           -     6.51383
   24      63       179       116   19.3304         4     9.11723     6.72728
   25      63       179       116   18.5572         0           -     6.72728
   26      63       179       116   17.8434         0           -     6.72728
   27      63       179       116   17.1826         0           -     6.72728
   28      63       179       116   16.5689         0           -     6.72728
```

```sh
rados bench -p benchmark 30 write -t 64 --no-cleanup --block-size 4194304
hints = 1
Maintaining 64 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 30 seconds or 0 objects
Object prefix: benchmark_data_controller_20133
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1      63       174       111   443.909       444    0.365929    0.396266
    2      63       319       256   511.907       580    0.273912    0.419157
    3      63       458       395   526.576       556    0.503379    0.407265
    4      63       594       531    530.91       544    0.392948    0.433406
    5      63       696       633   506.317       408    0.398633    0.474253
    6      63       747       684   455.926       204    0.878058     0.49543
    7      63       847       784   447.929       400    0.628127    0.528286
    8      63       907       844   421.934       240     1.42958     0.54089
    9      63      1040       977   434.155       532    0.322162    0.570321
   10      63      1133      1070   427.936       372    0.236833    0.585117
   11      63      1232      1169   425.028       396     1.25991    0.586539
   12      63      1381      1318   439.269       596     0.74982    0.564733
   13      63      1508      1445    444.55       508    0.472741    0.556666
   14      63      1569      1506   430.223       244    0.898126    0.561955
   15      63      1723      1660   442.603       616    0.412943    0.561736
   16      63      1858      1795   448.686       540    0.421627    0.557993
   17      63      1899      1836   431.938       164     1.10613     0.56618
   18      63      2055      1992   442.604       624    0.533054      0.5653
   19      63      2150      2087   439.306       380    0.303389    0.572143
2025-11-12T18:03:59.139421+0100 min lat: 0.157033 max lat: 2.89192 avg lat: 0.5641
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
   20      63      2245      2182   436.338       380    0.821391      0.5641
   21      63      2390      2327   443.174       580    0.518717     0.56516
   22      63      2492      2429   441.573       408    0.977707    0.566259
   23      63      2579      2516   437.502       348    0.349567    0.574357
   24      63      2673      2610   434.938       376     1.55188    0.576626
   25      63      2736      2673   427.619       252    0.870929    0.578401
   26      63      2814      2751   423.171       312    0.734637    0.585443
   27      63      2891      2828   418.903       308     1.34598    0.590317
   28      63      2971      2908   415.369       320    0.806376    0.602177
   29      63      3026      2963   408.631       220     1.76943     0.61279
   30      63      3144      3081   410.741       472    0.552516    0.612746
   31       6      3145      3139   404.974       232     0.89136    0.612666
Total time run:         31.5255
Total writes made:      3145
Write size:             4194304
Object size:            4194304
Bandwidth (MB/sec):     399.042
Stddev Bandwidth:       135.933
Max bandwidth (MB/sec): 624
Min bandwidth (MB/sec): 164
Average IOPS:           99
Stddev IOPS:            33.9833
Max IOPS:               156
Min IOPS:               41
Average Latency(s):     0.614452
Stddev Latency(s):      0.431624
Max latency(s):         6.60457
Min latency(s):         0.0584013
```

## 128 PGS

### 1 replica

```sh
rados bench -p benchmark 30 write -t 64 --no-cleanup --block-size 4194304
hints = 1
Maintaining 64 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 30 seconds or 0 objects
Object prefix: benchmark_data_controller_20714
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1      63       491       428   1711.68      1712    0.116716    0.135146
    2      63       819       756   1511.73      1312    0.179324    0.147402
    3      63      1097      1034   1378.46      1112    0.154135    0.154669
    4      63      1265      1202   1201.83       672    0.403008    0.165055
    5      63      1781      1718    1374.2      2064    0.191958    0.181427
    6      63      2200      2137   1424.45      1676    0.258597    0.175293
    7      63      2592      2529   1444.92      1568    0.145453    0.169884
    8      63      2982      2919   1459.27      1560    0.153123    0.165697
    9      63      3401      3338   1483.33      1676    0.162483    0.170039
   10      63      3773      3710   1483.76      1488    0.106222     0.17067
   11      63      4174      4111   1494.67      1604    0.132329    0.169668
   12      63      4517      4454   1484.43      1372    0.178596    0.169102
   13      63      4902      4839   1488.68      1540    0.125944    0.170362
   14      63      5141      5078   1450.63       956    0.231741    0.173495
   15      63      5221      5158   1375.25       320    0.623122    0.177392
   16      63      5473      5410   1352.28      1008    0.324889    0.184981
   17      63      5572      5509   1296.02       396    0.206176    0.195316
   18      63      5900      5837    1296.9      1312     0.14329    0.196012
   19      63      6121      6058   1275.16       884    0.231641    0.198124
2025-11-12T18:05:36.566176+0100 min lat: 0.0729188 max lat: 3.29821 avg lat: 0.201475
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
   20      63      6354      6291      1258       932    0.219725    0.201475
   21      63      6566      6503   1238.46       848    0.254061    0.204106
   22      63      6767      6704   1218.71       804    0.485575    0.207448
   23      63      7003      6940   1206.76       944    0.242371    0.210021
   24      63      7253      7190   1198.13      1000    0.243771    0.211664
   25      63      7555      7492   1198.52      1208    0.391679    0.212266
   26      63      7732      7669   1179.65       708    0.383134    0.213684
   27      63      7950      7887   1168.25       872    0.323032     0.21623
   28      63      8107      8044   1148.95       628    0.341538    0.220513
   29      63      8298      8235   1135.68       764    0.287623    0.223548
   30      25      8445      8420   1122.48       740   0.0424255    0.226228
   31       5      8445      8440   1088.86        80    0.556438    0.227324
Total time run:         31.3559
Total writes made:      8445
Write size:             4194304
Object size:            4194304
Bandwidth (MB/sec):     1077.31
Stddev Bandwidth:       463.903
Max bandwidth (MB/sec): 2064
Min bandwidth (MB/sec): 80
Average IOPS:           269
Stddev IOPS:            115.976
Max IOPS:               516
Min IOPS:               20
Average Latency(s):     0.228749
Stddev Latency(s):      0.222687
Max latency(s):         3.29821
Min latency(s):         0.0216263
```

### 2 replicas

```sh
rados bench -p benchmark 30 write -t 64 --no-cleanup --block-size 4194304
hints = 1
Maintaining 64 concurrent writes of 4194304 bytes to objects of size 4194304 for up to 30 seconds or 0 objects
Object prefix: benchmark_data_controller_23911
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
    0       0         0         0         0         0           -           0
    1      63       246       183   731.837       732    0.286804     0.25382
    2      63       448       385   769.851       808    0.250371    0.288966
    3      63       647       584   778.523       796    0.271689    0.295531
    4      63       908       845    844.85      1044    0.241282    0.285189
    5      63      1157      1094   875.047       996    0.198433     0.27986
    6      63      1357      1294   862.516       800    0.412603     0.28014
    7      63      1572      1509   862.134       860    0.178713    0.287363
    8      63      1791      1728   863.847       876    0.234394     0.28674
    9      63      1959      1896   842.518       672    0.667376    0.291315
   10      63      2173      2110   843.847       856    0.354713       0.294
   11      63      2392      2329   846.753       876    0.295579    0.294647
   12      63      2630      2567   855.508       952    0.271922    0.292362
   13      63      2821      2758   848.461       764    0.357209      0.2953
   14      63      3064      3001   857.275       972     0.19091    0.293023
   15      63      3303      3240   863.847       956    0.227238    0.291914
   16      63      3507      3444   860.849       816    0.244586    0.293195
   17      63      3730      3667   862.672       892    0.586463    0.292258
   18      63      3925      3862   858.074       780     0.60732     0.29371
   19      63      4122      4059   854.379       788    0.270129    0.295456
2025-11-12T18:14:57.466131+0100 min lat: 0.158345 max lat: 0.73501 avg lat: 0.295726
  sec Cur ops   started  finished  avg MB/s  cur MB/s last lat(s)  avg lat(s)
   20      63      4345      4282   856.253       892    0.161069    0.295726
   21      63      4468      4405   838.902       492    0.552807    0.298345
   22      63      4551      4488   815.858       332    0.546964    0.304887
   23      63      4706      4643   807.338       620    0.276238    0.313003
   24      63      4852      4789   798.028       584    0.411942    0.316286
   25      63      4968      4905   784.664       464    0.430986    0.322152
   26      63      5089      5026   773.097       484    0.494067    0.325833
   27      63      5200      5137   760.905       444    0.644407    0.330431
   28      63      5298      5235   747.728       392    0.950192    0.335903
   29      63      5442      5379   741.803       576    0.359591    0.341605
   30      63      5553      5490   731.874       444    0.463325    0.344309
   31       5      5554      5549   715.877       236    0.657421    0.345703
Total time run:         31.6521
Total writes made:      5554
Write size:             4194304
Object size:            4194304
Bandwidth (MB/sec):     701.88
Stddev Bandwidth:       216.683
Max bandwidth (MB/sec): 1044
Min bandwidth (MB/sec): 236
Average IOPS:           175
Stddev IOPS:            54.1707
Max IOPS:               261
Min IOPS:               59
Average Latency(s):     0.347518
Stddev Latency(s):      0.187443
Max latency(s):         3.139
Min latency(s):         0.0816921
```

# New testing (POWER PROFILES)

isntall `tuned-adm`

```sh
dnf install -y tuned
```

start tuned service

```sh
systemctl enable --now tuned
```

GO NUTS

```sh
tuned-adm profile latency-performance
tuned-adm active
```
