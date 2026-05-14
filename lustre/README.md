::include{file=../shared/ansible_base.md}

> [!NOTE]
> **Cold-boot stabilized 2026-05-07** via `lustre-startup.service` (deployed by `playbooks/setup_lustre_startup.yml`). The orchestrator binds `/dev/loop10` for the MGS, finds the MDT disk by Lustre volume label (handles Supermicro `/dev/sda↔sdb` shuffle), serializes OST mounts to dodge the ldiskfs init race, and uses `mountpoint -q` as ground truth so `mount(8)` race output (`already mounted`, `File exists`, `Operation in progress`) doesn't false-fail. Validated by reboot on Head-1 (~75 s incl. MDT recovery) and Compute-1 (~30 s).

## Architecture

| Role | Nodes | Storage |
|---|---|---|
| MGS (Management Server) | Rocky-Head-1 | `/var/lib/lustre/mgt.img` → `/dev/loop10` → `/mnt/mgt` |
| MDS (Metadata) | Rocky-Head-1, Rocky-Head-2 | `/dev/sd*` (one 128 GB SSD each) → `/mnt/mdt0`, `/mnt/mdt1` |
| OSS (Object Storage) | Rocky-Compute-1..8 | 2× 256 GB Samsung SSDs each → `/mnt/ost0` ... `/mnt/ost15` |
| Clients | All 10 nodes | `/mnt/lustre` |

**Network**: LNET over o2ib (RDMA / InfiniBand). NID format `10.0.0.x@o2ib`. MGS NID `10.0.0.251@o2ib`.

**Filesystem name**: `lustrefs`. Total capacity: 3.7 TB raw (1.85 TB usable with 2-way FLR).

## Software stack

- Rocky Linux 9.7
- Lustre kernel: `5.14.0-611.13.1_lustre.el9.x86_64` (must be `grubby --set-default` on every node)
- Lustre version: 2.17.0
- Stock IB modules from `5.14.0-611.16.1.el9_7.x86_64` copied into the Lustre kernel tree with **BTF stripped** (`strip --strip-debug --remove-section=.BTF`). Without this, `ib_core` fails to load. See `ROCKY9_RDMA_BREAKTHROUGH.md`.

## Playbook layout

> [!IMPORTANT]
> All Ansible commands run from this directory. The vault password is read from `~/.ansible_vault_pass` (configured in `ansible.cfg`).

### Lustre stages 0–6 (storage layer)

| Stage | Playbook | Purpose |
|---|---|---|
| 0 | `stage0_bootstrap.yml` | Python 3.9 bootstrap on fresh Rocky install |
| 1 | `stage1_core_setup.yml` | NTP, InfiniBand, OpenSM, hosts, firewall, storage prep |
| 2 | `stage2_install_lustre.yml` | Install Lustre RPMs + LNET configuration |
| 3 | `stage3_configure_mgs.yml` | Format and start MGS (loop device on Head-1) |
| 4 | `stage4_configure_mds.yml` | Format and start both MDTs |
| 5 | `stage5_configure_oss.yml` | Format and start 16 OSTs |
| 6 | `stage6_mount_clients.yml` | Mount `/mnt/lustre` on all clients |

### K8s migration stages (7–15)

Replaces the prior K3s deployment (stages 7-11, kept on disk for reference: `stage7_deploy_k3s.yml`, `stage8_deploy_metallb.yml`, `stage9_deploy_ingress.yml`, `stage10_tls_and_dashboard.yml`, `stage11_deploy_monitoring.yml`).

| Stage | Playbook | Purpose |
|---|---|---|
| 7 | `stage7_uninstall_k3s.yml` | Idempotent K3s residue cleanup |
| 8 | `stage8_k8s_prereqs.yml` | containerd, kubeadm/kubelet/kubectl, swap off, sysctl, firewall |
| 9 | `stage9_control_plane_ha.yml` | keepalived VIP `192.168.1.250` + HAProxy on `:8443` |
| 10 | `stage10_cluster_init.yml` | `kubeadm init/join` + Flannel CNI + Lustre StorageClass/PV |
| 11 | `stage11_metallb.yml` | MetalLB L2 (pool `192.168.1.200-220`) |
| 12 | `stage12_ingress.yml` | Nginx Ingress, LoadBalancer-typed |
| 13 | `stage13_tls.yml` | Self-signed CA + wildcard `*.lab.local` + Helm install |
| 14 | `stage14_helm_monitoring.yml` | kube-prometheus-stack via Helm |
| 15 | `stage15_rancher.yml` | Rancher Manager (cluster + user management UI) |
| 16 | `stage16_rancher_repos.yml` | Curated Helm chart catalog (bitnami, grafana, jupyterhub, gitea, harbor, minio, argo, etc.) |
| 17 | `stage17_dynamic_provisioner.yml` | local-path-provisioner in `sharedFileSystemPath` mode → dynamic PVs as Lustre subdirs (SC `lustre-dynamic`, default) |
| 18 | `stage18_wipe_for_opennebula.yml` | Scorched-earth K8s wipe → back to Lustre baseline for OpenNebula deployment. Idempotent. Preserves lab CA/cert at `/etc/pki/ujep-lab/`. Stages 7-17 stay in repo for reference; git tag `pre-opennebula-wipe` marks the pre-wipe state. |

### Common utilities (`playbooks/common/`)

- `startup.yml` — power-on via IPMI (does **not** orchestrate Lustre service mounts; that's a known gap)
- `shutdown.yml`, `reboot.yml`, `hard-reboot.yml`, `update.yml`
- `benchmark.yml`, `benchmark-ssd-baseline.yml`, `network-benchmarks.yml`, `setup-ssd-benchmarks.yml`
- `lustre-tuning.yml` — performance tuning for o2ib

### Diagnostics (`playbooks/diagnostics/`)

- `check-lustre-status.yml`
- `lustre-performance-tuning.yml`

## Quick reference

```bash
# Health
lctl list_nids                 # Local LNET NIDs
lctl ping 10.0.0.251@o2ib      # Reach MGS over RDMA
lfs df -h                      # Lustre capacity
lctl dl                        # Local Lustre devices
lctl get_param -n version      # Lustre version

# Manual mount
mount -t lustre 10.0.0.251@o2ib:/lustrefs /mnt/lustre

# FLR (file-level replication)
lfs mirror create -N2 <path>      # 2-way mirror
lfs mirror resync <path>          # Re-sync mirrors
lfs mirror verify -v <path>       # Verify checksums match
```

## Cold-boot recovery

Automatic via `lustre-startup.service` on every node. To force a re-run:

```bash
ansible -i hosts.ini all -m shell -a "systemctl restart lustre-startup.service" --become
```

To inspect what happened on boot:

```bash
journalctl -u lustre-startup.service -b
systemctl status lustre-startup.service
```

If the service ever fails, it stops loudly (no more `nofail`-hidden failures). Manual recovery as a fallback:

```bash
# Single-node manual recovery (script does this in dependency order)
losetup /dev/loop10 /var/lib/lustre/mgt.img            # Head-1 only
mount -t lustre /dev/loop10 /mnt/mgt                   # Head-1 only
mount -t lustre $(blkid -L lustrefs-MDT0000) /mnt/mdt0 # Head-1
mount -t lustre $(blkid -L lustrefs-MDT0001) /mnt/mdt1 # Head-2
mount -a                                               # OSTs from fstab on compute
mount -t lustre 10.0.0.251@o2ib:/lustrefs /mnt/lustre  # client
```

Do **not** add `nofail` to the MGS fstab line — it propagates to ldiskfs and causes a silent `-22 EINVAL`. The current setup keeps fstab out of the MGS/MDT mount path entirely (commented out by the deploy playbook); only the orchestrator handles them.

## Performance (basic dd, RDMA enabled)

Single-node: 165 MB/s write, 331 MB/s read (limited by Samsung SSD IOPS, not RDMA).
Aggregate (8 nodes parallel): 1.38 GB/s write, 2.77 GB/s read.
With FLR 2-way mirroring: ~17% write penalty.

LNET error counters were zero across the test — RDMA is working as intended.

## See also

- `ROCKY9_RDMA_BREAKTHROUGH.md` — full technical writeup of BTF stripping and the RDMA enablement.
- `log.md` — chronological session log.
- `../docs/Lustre.md` — project-level evaluation and verdict.
