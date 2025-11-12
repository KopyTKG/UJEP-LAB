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
