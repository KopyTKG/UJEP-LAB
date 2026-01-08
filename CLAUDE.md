# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains infrastructure automation for a university thesis project: deploying RDMA-enabled distributed file systems for VM/Docker clustering on a Rocky Linux HPC cluster. The cluster consists of 2 head/controller nodes and 8 compute nodes connected via InfiniBand.

**Project Goal: OpenNebula Cloud Platform with RDMA-Enabled Storage**

The infrastructure stack consists of:
1. **Lustre filesystem** (RDMA over InfiniBand) - Shared storage layer for VM images, disks, and data
2. **OpenNebula** - Cloud orchestration platform for VM/container management
3. **Head nodes** - OpenNebula frontend services (oned, sunstone, scheduler)
4. **Compute nodes** - KVM hypervisors for running VMs + Lustre OSS for storage

**Current Focus: Lustre with RDMA over InfiniBand**

- All nodes reinstalled with Rocky Linux 8.10 for Lustre server compatibility
- **CRITICAL**: Current deployment uses Lustre 2.15.4 (el8.9) which does NOT support RDMA on Rocky 8.10
  - Lustre kernel 4.18.0-513.9.1 (RHEL 8.5 based) lacks InfiniBand drivers
  - Currently running over TCP/Ethernet (192.168.1.x@tcp) instead of RDMA
  - Performance: 1.5 GB/s write, 3.2 GB/s read (TCP limited)
- **Solution**: Upgrade to Lustre 2.15.8 which has el8.10 support with InfiniBand drivers
  - Available: https://downloads.whamcloud.com/public/lustre/lustre-2.15.8/el8.10/
  - Will enable RDMA via LNET (o2ib) for 10-40 GB/s performance
  - RDMA critical for VM disk I/O performance and live migration capabilities

**Previous Filesystem Tests (Rejected):**

- **Ceph**: Significant software overhead limiting performance
- **BeeGFS**: OSS/Community version only supports RAID0
- **NFS with Pacemaker/TargetCLI**: Stability issues after reboots
- **GlusterFS**: RDMA support removed in recent versions

## Repository Structure

```
.
├── lustre/           # Lustre implementation (CURRENT - Rocky 8.10, RDMA enabled)
├── nfs/              # NFS + Pacemaker + TargetCLI implementation (deprecated)
├── glusterfs/        # GlusterFS implementation (deprecated - no RDMA)
├── beegfs/           # BeeGFS implementation (deprecated)
├── docs/             # Documentation for each filesystem solution
├── shared/           # Shared Ansible resources
│   ├── playbooks/    # Common playbooks used by all implementations
│   └── ansible_base.md  # Ansible setup guide
└── tools/            # Utility scripts for cluster management
```

Each filesystem directory is a self-contained Ansible project with:

- `hosts.ini` - Ansible inventory defining controller and compute nodes
- `ansible.cfg` - Ansible configuration
- `playbooks/` - Ansible playbooks for setup and management
- `group_vars/all/secret.yml` - Ansible vault for sensitive data (sudo passwords, etc.)

**Shared Playbooks** (`shared/playbooks/`):

Common playbooks imported by all filesystem implementations:
- `cluster_base_setup.yml` - NTP, InfiniBand, OpenSM, hosts file, network routing
- `prepare_compute_storage.yml` - SSD discovery, formatting, and mounting (customizable per FS)

**Lustre-specific inventory groups:**

- `mgs` - Management Server (Rocky-Head-1)
- `mds` - Metadata Servers (Rocky-Head-1 & Rocky-Head-2) - also run OpenNebula frontend
- `oss` - Object Storage Servers (all compute nodes) - also run KVM hypervisors
- `lustre_clients` - Client mount points (all nodes need access to shared storage)

**OpenNebula Role Mapping:**

- **Head nodes**: OpenNebula frontend (oned, sunstone, scheduler) + Lustre MGS/MDS
- **Compute nodes**: KVM hypervisors for VMs + Lustre OSS for distributed storage
- **Shared Storage**: Lustre mounted on all nodes for VM images, VM disks, and shared data

## Cluster Architecture

**Network Configuration:**

- Ethernet: 192.168.1.0/24 (management network)
  - Head nodes: 192.168.1.251-252
  - Compute nodes: 192.168.1.101-108
- InfiniBand: 10.0.0.0/24 (IPoIB for storage traffic)
  - Head nodes: 10.0.0.251-252
  - Compute nodes: 10.0.0.1-8
- IPMI: 192.168.50.0/24 (out-of-band management)

**Hardware:**

**Total Nodes:** 10

- 2x Head/Controller Nodes (Rocky-Head-1, Rocky-Head-2)
- 8x Compute/Storage Nodes (Rocky-Compute-1 to Rocky-Compute-8)

_Cluster Configuration:_

- **Chassis**: 2U Supermicro SYS-6028TR-HTR server
- **Blade Count**: 4x X10DRT-H motherboards

_Per-Blade Specifications:_

- **CPUs**: 2x Intel Xeon E5-2650 v4 @ 2.20GHz (12 cores each, 24 cores total per blade)
- **RAM**: 8x 8GiB DDR4 ECC (64GiB total per blade)
- **InfiniBand**: 1x Mellanox ConnectX-5 EDR 100GbE (RDMA capable)

_Storage:_

- **Data Storage**: Samsung 256GB SSDs (model: MZ7TY256) on compute nodes for Lustre OSTs

_Networking:_

- **InfiniBand Switch**: Mellanox SB7790 (EDR switch)
- **InfiniBand Interface**: ibs1 (configured for IPoIB)
- **Subnet Manager**: OpenSM for InfiniBand subnet management

_Software:_

- **OS**: Rocky Linux 8.10 (RHEL 8.10 compatible) - required for Lustre server compatibility

## Running Ansible Playbooks

All playbooks must be run from their respective project directories:

```bash
cd lustre/  # or nfs/ or glusterfs/
ansible-playbook playbooks/<playbook-name>.yml --ask-vault-pass
```

### Lustre Implementation Playbooks (Sequential) - CURRENT

**Current Status: Lustre 2.15.4 (el8.9) - TCP only, NO RDMA**

Initial deployment complete with 16 OSTs (3.7TB), but running over TCP/Ethernet due to kernel limitations.

**Sequential Playbooks:**

0. `stage0_bootstrap.yml` - Bootstrap Python 3.9 on fresh Rocky 8.10 install (run once after OS installation)
1. `stage1_core_setup.yml` - Imports shared base setup + Lustre firewall + storage prep
2. `stage2_install_lustre.yml` - Install Lustre packages (server on head/compute, client on all) + configure LNET
3. `stage3_configure_mgs.yml` - Set up Management Server (MGS) on Rocky-Head-1
4. `stage4_configure_mds.yml` - Set up Metadata Servers (MDS) on head nodes
5. `stage5_configure_oss.yml` - Set up Object Storage Servers (OSS) on compute nodes
6. `stage6_mount_clients.yml` - Mount Lustre filesystem on client nodes

**REQUIRED: Upgrade to Lustre 2.15.8 for RDMA Support**

Current Lustre 2.15.4 kernel (4.18.0-513.9.1, RHEL 8.5 based) lacks InfiniBand drivers. Upgrade required:

1. Update `stage2_install_lustre.yml`: Change repo URLs from `el8.9` to `el8.10` and version `2.15.4` to `2.15.8`
2. Stop Lustre services on all nodes: `umount /mnt/lustre`, `umount /mnt/ost*`, `umount /mnt/mdt*`, `umount /mnt/mgt`
3. Upgrade Lustre packages: `dnf upgrade lustre lustre-dkms`
4. Reboot to new kernel (should be 4.18.0-553.x series with IB drivers)
5. Verify IB modules loaded: `lsmod | grep ib_ipoib`
6. Reconfigure LNET for RDMA: Change all NIDs from `192.168.1.x@tcp` to `10.0.0.x@o2ib`
7. Reformat MGS with o2ib: `mkfs.lustre --mgs --reformat --mgsnode=10.0.0.251@o2ib /dev/loop10`
8. Reformat all MDTs with o2ib NIDs
9. Reformat all 16 OSTs with o2ib MGS node
10. Remount filesystem and verify RDMA: `lctl ping 10.0.0.251@o2ib`
11. Benchmark performance (expect 10-40 GB/s aggregate)

**Lustre-specific commands:**

```bash
# Check Lustre status
lctl list_nids                    # List Lustre network IDs
lctl ping <nid>                   # Ping a Lustre node
lfs df -h                         # Show Lustre filesystem usage
lctl get_param version            # Check Lustre version

# Mount Lustre manually
mount -t lustre 10.0.0.251@o2ib:/lustrefs /mnt/lustre
```

### NFS Implementation Playbooks (Sequential) - DEPRECATED

Run these playbooks in order to set up the NFS HA cluster:

1. `1_setup_core_install.yml` - Configure time sync, InfiniBand, and OpenSM
2. `2_setup_compute_storage.yml` - Configure storage on compute nodes with targetcli LUNs
3. `3_setup_controller_aggregation.yml` - Set up NFS server with Pacemaker on Head 1
4. `4_head_1-setup_raid.yml` - Configure software RAID6 from exported LUNs
5. `5_head_1-setup_ha.yml` - Configure Pacemaker resources for NFS/TargetCLI
6. `6_head_2-join_ha.yml` - Join Head 2 to the Pacemaker cluster
7. `7_setup_client_mount.yml` - Mount NFS shares on compute nodes

### GlusterFS Implementation Playbooks (Sequential) - DEPRECATED

1. `stage1.yml` - Basic cluster setup, InfiniBand networking, compute node SSD preparation
2. `stage2.yml` or `new-stage2.yml` - GlusterFS installation and configuration
3. `stage3.yml` - Volume creation and client setup
4. `stage4.yml` - Additional configuration

**Note**: GlusterFS deprecated due to lack of RDMA support in current versions.

### Common Utility Playbooks

All implementations include these utilities in `playbooks/common/`:

- `startup.yml` - Start all cluster nodes in correct sequence
- `shutdown.yml` - Gracefully shut down all cluster nodes
- `reboot.yml` - Reboot cluster nodes
- `update.yml` - Update packages
- `benchmark.yml` - Run FIO benchmarks on all compute nodes

### Lustre Diagnostics

- `diagnostics/check-lustre-status.yml` - Verify Lustre cluster health and LNET status
- `diagnostics/lustre-performance-tuning.yml` - Apply RDMA and performance optimizations

### Legacy Diagnostics

- GlusterFS: `diagnostics/check-gluster-setup.yml`, `glusterfs-optimizations.yml`
- NFS: Various rescue and configuration playbooks

## Testing and Benchmarking

Run benchmarks to test storage performance:

```bash
cd lustre/  # or nfs/ or glusterfs/
ansible-playbook playbooks/common/benchmark.yml
```

**Benchmarking tools:**

- **FIO**: Sequential/random read/write testing across all compute nodes in parallel
- **IOR**: Parallel I/O benchmarking (Lustre-specific)

**Expected Performance with RDMA:**

- Significantly reduced latency compared to IPoIB-only solutions
- Higher aggregate throughput due to RDMA offloading
- Better CPU efficiency (kernel bypass via RDMA)
- Critical for OpenNebula VM workloads: faster VM disk I/O and live migration performance

Results show per-node performance and can be aggregated for total cluster throughput. Lustre with RDMA (o2ib) should demonstrate substantial improvements over previous NFS and GlusterFS implementations, directly benefiting VM performance in OpenNebula.

## Ansible Configuration

**Inventory Variables** (`hosts.ini`):

- `ansible_user` - SSH user for connections (typically 'user')
- `ansible_become` - Use sudo for privilege escalation
- `ansible_ssh_private_key_file` - Path to SSH private key
- `ib_ip` - InfiniBand IP derived from ethernet IP last octet
- `ipmi_host` - IPMI interface IP for out-of-band management
- `ipmi_user` - IPMI username (stored in vault)

**Vault Secrets** (`group_vars/all/secret.yml`):

- `ansible_become_pass` - Sudo password
- `hacluster_password` - Pacemaker cluster password (NFS only)

Create/edit vault: `ansible-vault edit group_vars/all/secret.yml`

## Key Implementation Details

**InfiniBand Setup:**

- Kernel module `ib_ipoib` must be loaded for IP over InfiniBand
- OpenSM service manages InfiniBand subnet management
- NetworkManager configures ibs1 interface with static IPs
- **Lustre RDMA**: Uses LNET with o2ib (OpenFabrics InfiniBand) for RDMA operations
  - LNET network configuration: `o2ib(ibs1)` for InfiniBand RDMA
  - Network Identifier (NID) format: `10.0.0.X@o2ib`

**Time Synchronization:**

- All nodes sync time via Chrony using CESNET NTP servers (tik.cesnet.cz, tak.cesnet.cz)
- Critical for Pacemaker cluster operations

**Storage Node Logic:**

- Controller nodes: IB IP derived from last octet of ethernet IP (e.g., 192.168.1.251 → 10.0.0.251)
- Compute nodes: IB IP uses node number from hostname (e.g., Rocky-Compute-3 → 10.0.0.3)

**Disk Identification:**

- Storage disks identified by stable `/dev/disk/by-id/ata-*` paths
- Model string matching prevents accidental formatting of wrong disks
- XFS filesystem used for compute node storage volumes
