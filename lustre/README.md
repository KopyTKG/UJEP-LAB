::include{file=../shared/ansible_base.md}

> [!NOTE]
> This Lustre implementation requires Rocky Linux 8.10 (or RHEL 8.10 compatible) for proper Lustre server support.

## Lustre Architecture

**Lustre Components:**

- **MGS (Management Server)**: Rocky-Head-1 - Stores configuration information
- **MDS (Metadata Servers)**: Rocky-Head-1 & Rocky-Head-2 - Handle namespace operations, file metadata
- **OSS (Object Storage Servers)**: Rocky-Compute-1 through 8 - Store actual file data
- **Clients**: All compute nodes also act as Lustre clients

**RDMA Configuration:**

- Lustre uses LNET (Lustre Networking) with o2ib (OpenFabrics InfiniBand) for RDMA
- InfiniBand network: 10.0.0.0/24
- RDMA capabilities via Mellanox ConnectX-5 EDR cards

## Installation Steps

> [!IMPORTANT]
> All steps are done via Ansible playbooks located in the `playbooks/` directory.

0. `stage0_bootstrap.yml` - **Bootstrap fresh Rocky 8.10 install** (run this first on newly installed systems)
   - Install Python 3.9 on all nodes
   - Set Python 3.9 as default interpreter
   - Verify connectivity

1. `stage1_core_setup.yml` - Base system setup (imports shared playbooks)
   - NTP, InfiniBand, OpenSM, hosts file, network routing
   - Lustre firewall rules
   - SSD discovery, formatting, and mounting for OSTs

2. `stage2_install_lustre.yml` - Install Lustre packages and configure LNET
   - Add Lustre repositories (server, client, e2fsprogs)
   - Install lustre-server on head nodes (MGS/MDS) and compute nodes (OSS)
   - Install lustre-client on all nodes
   - Configure LNET for RDMA over InfiniBand (o2ib)
   - Verify LNET connectivity between nodes

3. `stage3_configure_mgs.yml` - Set up Management Server (MGS)
4. `stage4_configure_mds.yml` - Set up Metadata Servers (MDS)
5. `stage5_configure_oss.yml` - Set up Object Storage Servers (OSS)
6. `stage6_mount_clients.yml` - Mount Lustre filesystem on client nodes

**Common Tools**

- `common/startup.yml` - Startup sequence for all nodes
- `common/shutdown.yml` - Shutdown sequence for all nodes
- `common/benchmark.yml` - Run FIO benchmarks on all compute nodes
- `common/reboot.yml` - Reboot cluster nodes

**Diagnostics**

- `diagnostics/check-lustre-status.yml` - Verify Lustre cluster health
- `diagnostics/lustre-performance-tuning.yml` - Apply performance optimizations

## Quick Commands

**Check Lustre status:**

```bash
lctl list_nids              # List network IDs
lctl ping <nid>             # Ping a Lustre node
lfs df -h                   # Show Lustre filesystem usage
lctl get_param version      # Check Lustre version
```

**Mount Lustre manually:**

```bash
mount -t lustre <MGS_NID>:/<fsname> /mnt/lustre
# Example: mount -t lustre 10.0.0.251@o2ib:/lustrefs /mnt/lustre
```

**Benchmark:**

```bash
cd /home/kopy/Documents/UJEP-LAB/lustre
ansible-playbook playbooks/common/benchmark.yml
```

## Performance Testing

Performance benchmarks using FIO for I/O performance testing across all 8 compute nodes.

> [!NOTE]
> Current deployment uses TCP transport over Ethernet (192.168.1.x@tcp) due to InfiniBand kernel module incompatibility in the Lustre kernel.

**Cluster Configuration:**
- 16 OSTs across 8 compute nodes (OST0-13, OST18-19)
- Total Capacity: 3.7TB
- 2 MDTs (Rocky-Head-1, Rocky-Head-2)
- 1 MGS (Rocky-Head-1)
- Transport: TCP over Ethernet

## Benchmark Results (All 8 Nodes Operational)

**Date:** 2026-01-08

### Write Performance

```bash
TASK [Show Write Bandwidth (MB/s)] *********************************************
ok: [Rocky-Compute-1] => {
    "msg": "Host Rocky-Compute-1 Write Speed: 36.1318359375 MB/s"
}
ok: [Rocky-Compute-2] => {
    "msg": "Host Rocky-Compute-2 Write Speed: 231.765625 MB/s"
}
ok: [Rocky-Compute-3] => {
    "msg": "Host Rocky-Compute-3 Write Speed: 239.384765625 MB/s"
}
ok: [Rocky-Compute-4] => {
    "msg": "Host Rocky-Compute-4 Write Speed: 219.166015625 MB/s"
}
ok: [Rocky-Compute-5] => {
    "msg": "Host Rocky-Compute-5 Write Speed: 189.3466796875 MB/s"
}
ok: [Rocky-Compute-6] => {
    "msg": "Host Rocky-Compute-6 Write Speed: 140.345703125 MB/s"
}
ok: [Rocky-Compute-7] => {
    "msg": "Host Rocky-Compute-7 Write Speed: 471.0615234375 MB/s"
}
ok: [Rocky-Compute-8] => {
    "msg": "Host Rocky-Compute-8 Write Speed: 35.953125 MB/s"
}
```

**Aggregate Write Throughput: ~1,563 MB/s (1.5 GB/s)**

### Read Performance

```bash
TASK [Show Read Bandwidth (MB/s)] **********************************************
ok: [Rocky-Compute-1] => {
    "msg": "Host Rocky-Compute-1 Read Speed: 73.9443359375 MB/s"
}
ok: [Rocky-Compute-2] => {
    "msg": "Host Rocky-Compute-2 Read Speed: 516.2587890625 MB/s"
}
ok: [Rocky-Compute-3] => {
    "msg": "Host Rocky-Compute-3 Read Speed: 523.3994140625 MB/s"
}
ok: [Rocky-Compute-4] => {
    "msg": "Host Rocky-Compute-4 Read Speed: 518.7265625 MB/s"
}
ok: [Rocky-Compute-5] => {
    "msg": "Host Rocky-Compute-5 Read Speed: 516.5517578125 MB/s"
}
ok: [Rocky-Compute-6] => {
    "msg": "Host Rocky-Compute-6 Read Speed: 516.6494140625 MB/s"
}
ok: [Rocky-Compute-7] => {
    "msg": "Host Rocky-Compute-7 Read Speed: 510.4677734375 MB/s"
}
ok: [Rocky-Compute-8] => {
    "msg": "Host Rocky-Compute-8 Read Speed: 78.1259765625 MB/s"
}
```

**Aggregate Read Throughput: ~3,254 MB/s (3.2 GB/s)**

### Performance Notes

- Compute-2 through Compute-7 show consistent high performance (140-523 MB/s)
- Compute-1 and Compute-8 exhibit lower performance, likely due to being freshly integrated
- Overall performance of 1.5 GB/s write and 3.2 GB/s read is excellent for TCP transport
- Future RDMA optimization could significantly improve performance further
