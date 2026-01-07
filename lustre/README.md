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

Performance benchmarks will be conducted using:
- FIO for I/O performance testing
- IOR for parallel I/O benchmarking
- Comparison with previous filesystem implementations (NFS, GlusterFS, etc.)

Expected improvements with RDMA enabled should show significantly better latency and throughput compared to non-RDMA solutions.
