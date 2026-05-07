# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains infrastructure automation for a university thesis project: deploying RDMA-enabled distributed file systems for VM/Docker clustering on a Rocky Linux HPC cluster. The cluster consists of 2 head/controller nodes and 8 compute nodes connected via InfiniBand.

**Project Goal: Stable RDMA-enabled storage layer for a Kubernetes-based VM/container cluster**

Originally framed around OpenNebula on Lustre. Pivoted to Kubernetes (originally K3s, then full kubeadm) for ecosystem reasons. The storage-layer choice is the active question — see "Current State" below.

**Current State (2026-05-07)**

- OS: Rocky Linux 9.7 on all 10 nodes
- Kernel: `5.14.0-611.13.1_lustre.el9.x86_64` (Lustre kernel set as default via `grubby`)
- Lustre 2.17.0 deployed with RDMA over InfiniBand (`o2ib(ibs1)`), 2 MDTs + 16 OSTs + FLR for redundancy. Aggregate: 1.38 GB/s write, 2.77 GB/s read.
- **RDMA was enabled via a BTF-stripping workaround**: Lustre kernel ships without IB drivers; copying the stock kernel's `ib_core`, `mlx5_ib`, `rdma_cm`, `ib_ipoib` modules and running `strip --strip-debug --remove-section=.BTF` on each `.ko` allows them to load alongside the Lustre kernel. Full writeup in `lustre/ROCKY9_RDMA_BREAKTHROUGH.md`.
- **K3s deployment was working** (stages 7-11 in `lustre/playbooks/`) but was abandoned for full Kubernetes (kubeadm) due to K3s ecosystem limitations (dead Dashboard Helm repo, basic-auth workarounds).
- **kubeadm migration playbooks written** (stages 7-14 with `_k8s_` / kubeadm names) but not yet executed.

> [!NOTE]
> **Lustre cold-boot stabilized 2026-05-07** via `lustre-startup.service`, deployed cluster-wide by `lustre/playbooks/setup_lustre_startup.yml`. The orchestrator handles the three previously-broken pieces: it binds `/dev/loop10` before MGS mount, discovers the MDT disk by Lustre volume label (defeating `/dev/sda↔sdb` swap on Supermicro reboots), and serializes OST mounts with race-tolerant retries. fstab MGS+MDT lines on heads are commented out so the orchestrator is the single source of truth. Failures are loud (no `nofail`-masking). Validated: Compute-1 reboot ~30s, Head-1 reboot ~75s incl. MDT recovery. See `docs/Lustre.md` for the full evaluation.

**Filesystem Verdicts (chronological):**

- **Ceph** (rejected): Significant software overhead limiting raw IOPS. Documented in `docs/Ceph.md`.
- **BeeGFS** (rejected): Community/OSS edition only supports RAID0. `docs/BeeGFS.md`.
- **NFS + Pacemaker + TargetCLI** (rejected): Head node instability after every reboot. `docs/NFS_PCS_TargetCLI.md`.
- **GlusterFS** (rejected): RDMA support removed in current versions.
- **Lustre** (selected): RDMA + FLR + cold-boot stabilization via `lustre-startup.service`. Hits all four hard requirements (performance, redundancy, stability, RDMA) where each prior candidate failed exactly one. `docs/Lustre.md`.

## Repository Structure

```
.
├── lustre/           # Lustre implementation (Rocky 9.7 + 2.17.0 + RDMA + cold-boot orchestrator) — production target
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

- **OS**: Rocky Linux 9.7 (re-installed 2026-01-13 to enable Lustre 2.17.0 RDMA via the BTF-stripping technique)

## Running Ansible Playbooks

All playbooks must be run from their respective project directories:

```bash
cd lustre/  # or nfs/ or glusterfs/
ansible-playbook playbooks/<playbook-name>.yml --ask-vault-pass
```

### Lustre Storage Playbooks (Stages 0–6)

**Status: Lustre 2.17.0 with RDMA (o2ib) deployed. Marked as not suitable for production due to cold-boot fragility — see Current State section above.**

0. `stage0_bootstrap.yml` — Python 3.9 bootstrap on fresh Rocky install
1. `stage1_core_setup.yml` — Shared base setup (NTP, IB, OpenSM, hosts, firewall) + storage prep
2. `stage2_install_lustre.yml` — Lustre 2.17.0 RPMs (el9.7) + LNET configuration
3. `stage3_configure_mgs.yml` — MGS on Rocky-Head-1 (loop device `/dev/loop10` backed by `/var/lib/lustre/mgt.img`)
4. `stage4_configure_mds.yml` — Metadata Targets on both heads (physical SSDs)
5. `stage5_configure_oss.yml` — 16 OSTs on compute SSDs
6. `stage6_mount_clients.yml` — Mount `/mnt/lustre` on clients

### K3s deployment (Stages 7–11) — superseded

Working K3s deployment on Lustre, abandoned in favor of full kubeadm. Files retained for reference: `stage7_deploy_k3s.yml`, `stage8_deploy_metallb.yml`, `stage9_deploy_ingress.yml`, `stage10_tls_and_dashboard.yml`, `stage11_deploy_monitoring.yml`.

### Kubeadm deployment (Stages 7–15) — deployed 2026-05-07

7. `stage7_uninstall_k3s.yml` — idempotent K3s residue cleanup
8. `stage8_k8s_prereqs.yml` — containerd + kubeadm/kubelet/kubectl, swap off, sysctl, firewall
9. `stage9_control_plane_ha.yml` — keepalived VIP `192.168.1.250` + HAProxy on `:8443`
10. `stage10_cluster_init.yml` — `kubeadm init/join` + Flannel CNI + Lustre StorageClass/PV
11. `stage11_metallb.yml` — MetalLB L2 (pool `192.168.1.200-220`)
12. `stage12_ingress.yml` — Nginx Ingress, LoadBalancer-typed
13. `stage13_tls.yml` — self-signed CA + wildcard `*.lab.local` + Helm install
14. `stage14_helm_monitoring.yml` — kube-prometheus-stack via Helm
15. `stage15_rancher.yml` — Rancher Manager for cluster + user management UI
16. `stage16_rancher_repos.yml` — Curated Helm chart catalog seed (bitnami, grafana, jupyterhub, gitea, harbor, minio, argo, prometheus-community, jetstack)

User management is via Rancher. Headlamp was originally deployed in stage 13 but retired in favor of Rancher's built-in multi-backend authentication (local users, OIDC, AD, GitHub) which fits the school-cluster use case. The TLS cert generation and Helm install pieces of stage 13 remain because they're shared infrastructure for stages 14 and 15.

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
