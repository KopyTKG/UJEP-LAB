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
| 8 | `stage8_mariadb_galera.yml` | 3-node MariaDB Galera cluster (Head-1, Head-2, Compute-1) — wsrep multi-primary synchronous replication, own quorum |
| 9 | `stage9_db_vip.yml` | HAProxy single-writer pattern + keepalived VIP `192.168.1.249:3306` — clients see one stable endpoint regardless of which Galera node is currently active |
| 10 | `stage10_opennebula_frontend.yml` | OpenNebula 6.10 frontend on Head-1 pointing at the DB VIP via MySQL backend |
| 11+ | (to be written) | oned Raft HA on Head-2, KVM hosts on compute, Lustre datastore, TLS, test VM, users/groups |

**Why MariaDB Galera and not PostgreSQL?** Earlier rev of stages 8-10 used PostgreSQL 16 + Patroni + etcd. Works beautifully — but **OpenNebula 6.10 doesn't actually support a PostgreSQL backend** (`DB BACKEND must be sqlite or mysql`). MariaDB Galera is OpenNebula's officially documented HA DB pattern. It also turns out simpler — Galera's wsrep does its own consensus (no external etcd needed) and supports multi-primary synchronous replication out of the box. The 3-node topology (heads + Compute-1) gives quorum-safe failover. Compute-1 is lightly loaded by the DB role and stays available for KVM workload.

A `cleanup_pg_etcd_layer.yml` exists in `playbooks/` to roll back the earlier PG/Patroni/etcd state (one-off; not part of normal deploy flow).

## Quick reference

```bash
# Frontend (Head-1)
oneuser list                      # List users
onehost list                      # List KVM hypervisors
onedatastore list                 # List datastores
onevm list                        # List VMs
journalctl -u opennebula -f       # oned logs

# Sunstone Web UI (classic)
http://rocky-head-1.lab.local:9869/    # or http://192.168.1.251:9869/

# FireEdge Web UI (newer, React-based)
http://rocky-head-1.lab.local:2616/fireedge/sunstone

# Port map (heads, post-stage-10):
#   2633  oned XML-RPC  (KVM hosts connect here)
#   9869  Sunstone UI
#   2616  FireEdge UI   (NOT 2474 — 2474 is OneFlow, localhost-only by default)
#   2474  OneFlow       (localhost only)
#   5030  OneGate       (localhost only)
#   2101  event manager (localhost only)
```

## Workload-layer rejection history

OpenNebula was selected after exhaustive elimination of alternatives. The investigation is documented at `../docs/oVirt.md`, the top-level `Mellanox_SB7790.pdf` (group-phase 12-OS / driver matrix that ruled out Proxmox, FreeBSD, Windows, Harvester, Debian), and `../CLAUDE.md` (project notes). Summary:

- Hardware-driven: only RHEL-family + NVIDIA blessed drivers achieve the full 100 Gb/s on the SB7790 IB-only switch. That alone rules out Proxmox / FreeBSD / Windows / SUSE-based Harvester / generic Debian.
- Complexity-driven: OpenStack tested, never reached a working state ("build it yourself").
- Bug-driven: oVirt + Lustre dies on the VDSM xleases O_DIRECT alignment mismatch (open upstream, no fix).
- Ecosystem-driven: K3s + Rancher + Helm combination doesn't work on K3s specifically.
- K8s (kubeadm + Rancher) deployed and worked end-to-end (stages 7-17 in `lustre/playbooks/`, retired by `stage18_wipe_for_opennebula.yml`). Wiped to make room for OpenNebula because the cloud-platform model fits a school cluster better than the container-platform model.
