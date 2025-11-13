# BeeGFS journey

- Start: 13-11-2025

## Adding repository and installing BeeGFS

```sh
sudo wget https://www.beegfs.io/release/beegfs_8.2/dists/beegfs-rhel10.repo -O /etc/yum.repos.d/beegfs-rhel10.repo
sudo rpm --import https://www.beegfs.io/release/beegfs_8.2/gpg/GPG-KEY-beegfs
```

```sh
sudo dnf update
```

### Controller node

```sh
sudo yum install -y beegfs-client beegfs-tools beegfs-utils beegfs-mgmtd beegfs-meta beegfs-admon # libbeegfs-ib - if RDMA is needed
```

### Storage node

```sh
sudo yum install -y beegfs-storage beegfs-tools beegfs-utils beegfs-client  # libbeegfs-ib - if RDMA is needed
```
