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

[!IMPORTANT](Only on controller node)

3. install opensm module

```sh
sudo dnf install opensm -y
sudo systemctl enable --now opensm
```
