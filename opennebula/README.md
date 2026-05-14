::include{file=../shared/ansible_base.md}

> [!IMPORTANT]
> Storage layer (Lustre 2.17.0 + RDMA + lustre-startup.service) is shared with the `lustre/` project. This folder layers OpenNebula on top: KVM hypervisors on compute nodes, frontend on head nodes, Lustre at `/mnt/lustre` as the shared filesystem datastore.

## Architecture

| Role | Nodes | Purpose |
|---|---|---|
| OpenNebula frontend (oned, sunstone, fireedge, MariaDB) | Rocky-Head-1 (primary), Rocky-Head-2 (HA standby — optional) | Cluster management API + Web UI |
| KVM hypervisors | Rocky-Compute-1..8 | Run VMs (qemu-kvm + libvirt + opennebula-node-kvm) |
| Shared storage | All 10 nodes mount Lustre at `/mnt/lustre` | VM disks, images, and templates live here |

**Datastore strategy:** `/var/lib/one/datastores/` is bind-mounted (or symlinked) onto `/mnt/lustre/one/datastores/`. With `DS_MAD=fs` + `TM_MAD=shared` every host sees the same VM image / disk paths, so **live migration works for free** (no disk copy — just CPU/RAM state transfer over the IB fabric via IPoIB).

**Network layout:**
- **Ethernet** (192.168.1.0/24): management, Sunstone Web UI, IPMI
- **InfiniBand / IPoIB** (10.0.0.0/24): node-to-node traffic, Lustre RDMA, VM-to-VM traffic (when bridge is on IPoIB)
- **VM bridges** (TBD in later stage): `br0` for VM external Ethernet; optional `ib-br0` for VMs needing high-bandwidth interconnect via IPoIB

## Stage roadmap

**Stages 0-6 + cold-boot fix: storage layer** (Lustre — same as in `lustre/`, copied verbatim so this folder is self-contained):

| Stage | Playbook | Purpose |
|---|---|---|
| 0 | `stage0_bootstrap.yml` | Python 3.9 bootstrap on fresh Rocky |
| 1 | `stage1_core_setup.yml` | NTP, IB, OpenSM, hosts, firewall, storage prep |
| 2 | `stage2_install_lustre.yml` | Lustre RPMs + LNET |
| 3 | `stage3_configure_mgs.yml` | MGS on Head-1 |
| 4 | `stage4_configure_mds.yml` | MDTs |
| 5 | `stage5_configure_oss.yml` | OSTs on compute |
| 6 | `stage6_mount_clients.yml` | `/mnt/lustre` on all nodes |
| — | `setup_lustre_startup.yml` | Cold-boot orchestrator (`lustre-startup.service`) |

**Stages 7+: OpenNebula workload layer** (this folder's actual purpose):

| Stage | Playbook | Purpose |
|---|---|---|
| 7 | `stage7_opennebula_prereqs.yml` | EPEL + CRB, OpenNebula 6.10 repo, SELinux permissive, firewall ports |
| 8 | `stage8_etcd_cluster.yml` | 3-node etcd cluster (Head-1, Head-2, Compute-1) — DCS for Patroni |
| 9 | `stage9_patroni_postgres.yml` | PostgreSQL 16 + Patroni on both heads; synchronous streaming replication; auto-failover via etcd Raft |
| 10 | `stage10_db_vip.yml` | HAProxy + keepalived VIP `192.168.1.249:5432` routing to whichever head Patroni reports as primary |
| 11 | `stage11_opennebula_frontend.yml` | OpenNebula frontend on Head-1 pointing at the DB VIP |
| 12+ | (to be written) | oned Raft HA on Head-2, KVM hosts on compute, Lustre datastore, TLS, test VM, users/groups |

**Why etcd + Patroni instead of vanilla streaming replication?** Because 2-node Postgres replication without an external arbiter has no safe way to do automatic failover (can't distinguish "primary died" from "primary partitioned"). A 3-node etcd cluster (heads + one compute) provides the quorum-based arbiter, so Patroni can elect a new leader without risking split-brain. The third etcd member is lightweight — etcd uses <100 MB RAM and minimal CPU; co-locating it with KVM workload on Compute-1 is fine.

## Quick reference

```bash
# Frontend (Head-1)
oneuser list                      # List users
onehost list                      # List KVM hypervisors
onedatastore list                 # List datastores
onevm list                        # List VMs
journalctl -u opennebula -f       # oned logs

# Sunstone Web UI
https://rocky-head-1.lab.local:9869/   # or whichever hostname/IP
```

## Workload-layer rejection history

OpenNebula was selected after exhaustive elimination of alternatives. The investigation is documented at `../docs/oVirt.md`, the top-level `Mellanox_SB7790.pdf` (group-phase 12-OS / driver matrix that ruled out Proxmox, FreeBSD, Windows, Harvester, Debian), and `../CLAUDE.md` (project notes). Summary:

- Hardware-driven: only RHEL-family + NVIDIA blessed drivers achieve the full 100 Gb/s on the SB7790 IB-only switch. That alone rules out Proxmox / FreeBSD / Windows / SUSE-based Harvester / generic Debian.
- Complexity-driven: OpenStack tested, never reached a working state ("build it yourself").
- Bug-driven: oVirt + Lustre dies on the VDSM xleases O_DIRECT alignment mismatch (open upstream, no fix).
- Ecosystem-driven: K3s + Rancher + Helm combination doesn't work on K3s specifically.
- K8s (kubeadm + Rancher) deployed and worked end-to-end (stages 7-17 in `lustre/playbooks/`, retired by `stage18_wipe_for_opennebula.yml`). Wiped to make room for OpenNebula because the cloud-platform model fits a school cluster better than the container-platform model.
