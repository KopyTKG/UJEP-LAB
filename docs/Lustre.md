# Lustre journey

- Start: 2026-01-07
- Stabilized: 2026-05-07

> [!NOTE]
> Lustre is the production-target storage layer for this cluster. After traversing four other distributed-FS candidates (each rejected on a different hard requirement), Lustre 2.17.0 with RDMA + FLR was stabilized end-to-end on 2026-05-07 via a custom `lustre-startup.service` orchestrator.

## Verdict

| Aspect | Result |
|---|---|
| RDMA over InfiniBand | ✅ Working (after BTF-stripping workaround) |
| Aggregate throughput | ✅ 1.38 GB/s write, 2.77 GB/s read (basic dd, RDMA) |
| Node-level redundancy | ✅ FLR (File-Level Replication) verified |
| Cold-boot survival | ✅ Stabilized via `lustre-startup.service` (2026-05-07) |
| Suitability for K8s persistent storage | ✅ Self-healing on power events |

## Why Lustre vs. the alternatives

Each of the four prior candidates failed on a *different* hard requirement, leaving Lustre as the only solution that meets all of them:

| Filesystem | Failed requirement |
|---|---|
| Ceph | Performance (~100 MB/s on this hardware due to protocol overhead) |
| BeeGFS Community | Redundancy (RAID0-only OSS) |
| NFS + Pacemaker + TargetCLI | Stability (head nodes nuked themselves on every reboot) |
| GlusterFS | RDMA (support removed in current versions) |
| **Lustre + FLR + lustre-startup.service** | **All four met** |

## Timeline

### Phase 1: Rocky 8.10 + Lustre 2.15.4 (2026-01-07 → 2026-01-08)

- Initial deploy on Rocky 8.10. Got 16 OSTs across 8 compute nodes, 14 OSTs first cycle (Compute-8 wedged), full 16 after re-integration.
- Performance under TCP transport: 1.5 GB/s write, 3.2 GB/s read aggregate.
- **Showstopper**: Lustre 2.15.4 ships an RHEL-8.5-based kernel (`4.18.0-513.9.1.el8_lustre`) that lacks InfiniBand drivers entirely. Stuck on Ethernet TCP — the entire 100 Gbps EDR fabric was unused.
- Attempted to copy IB modules from stock 8.10 kernel → kABI-incompatible.
- Cleanup attempt to revert kernel left all 8 compute nodes in emergency mode (`fstab` referenced Lustre mounts, stock kernel missing ldiskfs).

### Phase 2: Rocky 9.7 + Lustre 2.17.0 — BTF breakthrough (2026-01-13)

- Reinstalled all 10 nodes with Rocky 9.7 (manually, via 4× Ventoy USB).
- Lustre 2.17.0 ships a kernel of its own (`5.14.0-611.13.1_lustre.el9`) that still lacks IB drivers — same problem.
- **Discovery**: copying stock IB modules into the Lustre kernel tree fails at load with `Too many levels of symbolic links` (errno 40). dmesg revealed the real cause: BTF (BPF Type Format) validation failure, not symlinks.
- **Fix**: `strip --strip-debug --remove-section=.BTF` on each `.ko`, then `depmod -a`. ib_core, mlx5_ib, rdma_cm, ib_ipoib all loaded clean. Lustre's `ko2iblnd` then loaded over them.
- LNET reconfigured for `o2ib(ibs1)`. NIDs flipped from `192.168.1.x@tcp` to `10.0.0.x@o2ib`.
- Reformatted MGS, both MDTs, all 16 OSTs with `--mgsnode=10.0.0.251@o2ib`. Filesystem came up clean.
- Performance verified: 1.38 GB/s write / 2.77 GB/s read aggregate. Zero LNET errors.

### Phase 3: FLR for redundancy (2026-01-13 evening)

- Default Lustre layout = striped RAID0 over 16 OSTs → ~9% annual data loss probability. Unacceptable.
- Discovered Lustre 2.17.0's built-in FLR (File-Level Replication) — cross-OST mirroring at the file level, transparent to clients.
- Verified with `lfs mirror create -N2`: 2 mirrors on different blades, `lfs mirror verify` showed matching CRCs.
- Performance cost ~17% on mirrored writes (137 MB/s vs 165 MB/s).
- Three-tier strategy designed: critical VMs mirrored, regular VMs striped, scratch unprotected.

### Phase 4: K3s on top (2026-03-26)

- Stages 7-11 added: K3s v1.32.4 (HA via embedded etcd), MetalLB, Nginx Ingress, Dashboard with TLS, kube-prometheus-stack via the K3s `HelmChart` CRD.
- Lustre `/mnt/lustre` exposed as a K8s `StorageClass` (hostPath PV).
- Worked, but K3s ecosystem frustrations (dead Dashboard Helm repo, basic-auth hacks) prompted a planned pivot to full K8s via kubeadm.
- Cluster powered off. Sat for ~6 weeks.

### Phase 5: Cold-boot reveals fragility (2026-05-07)

The cluster came back up with `/mnt/lustre` not mounted on any node. Investigation:

1. **MGS missing.** `/var/lib/lustre/mgt.img` is a 10 GB sparse file (Head-1 has no spare physical disk for the MGT — `/dev/sda` is taken by MDT0000). Mounting requires `losetup /dev/loop10 mgt.img` first. Nothing in the boot sequence does this — `fstab` assumes the device exists.
2. **`nofail` is a footgun on the MGS line.** Even when loop10 was bound manually, `mount` failed with `-22 EINVAL`. dmesg: `ldiskfs: Unknown parameter 'nofail'`. The mount(8) `nofail` option propagates straight through to ldiskfs, which rejects it. With `nofail` set, systemd silently treats the failure as success.
3. **Two OSTs lost an `_netdev` race.** OST0001 and OST0007 (the *second* SSD on Compute-1 and Compute-4 respectively) didn't auto-mount. Likely cause: systemd parallel mounts race with ldiskfs module init on each node. `nofail` again hides the failure.
4. **Cascade**: with MGS down, even mounted OSTs can't serve clients (clients need to read the config log from MGS first). Result: every client mount times out at `-110 ETIMEDOUT`, with no obvious cause.

Manual recovery sequence (clients down → OSTs down → MDTs down → MGS down → losetup → MGS up → MDTs up → OSTs up → clients up) brought the filesystem back. Verified: 16 OSTs, 3.7 TB, write test from a client succeeded.

But the underlying issue is not fixed:
- No systemd unit binds `/dev/loop10` at boot.
- `nofail` on the MGS fstab line still hides ldiskfs rejection.
- OST `_netdev` race is still latent.

A `lustre-startup.service` per node-role would solve all three. Implemented later the same day — see Phase 6.

### Phase 6: Stabilization via lustre-startup.service (2026-05-07 evening)

After eliminating Ceph, BeeGFS, NFS, and GlusterFS each on a different axis, switching storage layers a fifth time would have meant restarting four months of work for a marginal-at-best gain on disk-bound (SATA III, ~8 GB/s aggregate ceiling) hardware. The pragmatic choice was to fix the boot orchestration, not the filesystem.

`lustre-startup.service` deployed cluster-wide (`lustre/playbooks/setup_lustre_startup.yml`):

- **Bash orchestrator at `/usr/local/sbin/lustre-startup`** detects node role from hostname (Head-1 / Head-2 / Compute-N) and brings the filesystem up in dependency order: LNET → MGS → MDT → OSTs → client.
- **Loop device handled explicitly:** `losetup /dev/loop10 /var/lib/lustre/mgt.img` runs before MGS mount, so the MGT block device exists when needed.
- **MGS mounted with no extra options** so `nofail` cannot propagate to ldiskfs.
- **MDT block device discovered by Lustre volume label** (`blkid -L lustrefs-MDT0000`) instead of `/dev/sda`, defeating Supermicro's reboot-time `sda↔sdb` shuffle.
- **Race-tolerant `robust_mount` helper** uses `mountpoint -q` as ground truth (not mount(8) exit code) and treats `already mounted` / `File exists` / `Operation in progress` as "re-check, possibly already mounted" rather than failure. Up to 5 retries with 3s backoff.
- **fstab neutralized for MGS+MDT on heads** (commented out by the playbook); OST fstab entries retained on compute nodes since the orchestrator's race-tolerance handles their ldiskfs init race.
- **`lustre-startup.service` systemd unit:** `After=network-online.target opensm.service`, `Type=oneshot`, `RemainAfterExit=yes`, `TimeoutStartSec=600`. Failures surface in `systemctl --failed` and `journalctl -u lustre-startup.service`.

Validation:

- **Compute-1 cold reboot:** Lustre fully back in ~30 s. Script handled the OST mtab race (`/mnt/ost1` got "Operation already in progress" on first try, re-checked mountpoint, found it mounted, moved on).
- **Head-1 cold reboot (worst case — MDT0000 reboots while 9 other clients are connected):** ~75 s end-to-end including MDT recovery wait. Script bound loop10, mounted MGS via the loop device, found MDT disk by volume label (`/dev/sdb`), mounted MDT, mounted client. Service `active (exited)` with status `0/SUCCESS`.
- **Idempotent re-runs:** verified on all 10 nodes — script detects already-mounted state and exits 0 without changes.

Trade-off worth noting: Lustre's default MDT recovery window adds 3-5 minutes on every MDT remount (defensive behavior for crash-recovery scenarios with pending client state). On clean cold boot there is no pending state to recover, so the wait is pure waste. Mitigation now in the orchestrator: **MDT mounts use `-o abort_recov`**, which skips the recovery window. Cost: surviving clients in single-node-reboot scenarios get briefly evicted by the new MDS instance and reconnect in seconds. For a clean cold boot or planned reboot this is strictly faster.

### Validated cold-boot test (2026-05-07)

Full cluster shutdown via `playbooks/common/shutdown.yml` → IPMI power-on via `playbooks/common/startup.yml`. Three tests run before declaring victory:

| Test | Result | Lesson |
|---|---|---|
| #1 | Most scripts hung in `wait_for_mgs`. `lctl ping` can wedge indefinitely on cold boot while RDMA queue pairs are establishing — the script's outer 180s timeout never fires because `lctl ping` never returns. | Wrap each `lctl` call in `timeout(1)`. |
| #2 | All scripts progressed past MGS-wait, reached `start_client`, and blocked there for the full ~5 min MDT recovery window. | Add `-o abort_recov` to MDT mount. |
| #3 | **All 10 services active 56 s after SSH ready** (4:26 total wall time, of which ~3:30 was Supermicro POST + IPMI ramp). | ✅ |

The `abort_recov` change cut MDT recovery from ~3 min to ~25 s. The bounded-`lctl` change ensures any future RDMA wedge surfaces as a loud failure within 5 min instead of hanging silently forever.

## Outcome

The thesis goal — **stable RDMA-enabled storage for a K8s/VM workload cluster** — is met:

- Self-healing across power events ✅
- Compatible with stock systemd boot semantics (the orchestrator is one extra unit, not a custom init) ✅
- Diagnosable: failures are loud, journalctl shows full trace, `systemctl status` is the single source of truth ✅
- Performance: 14-28× the throughput Ceph delivered on the same hardware, at the disk ceiling rather than the network ceiling ✅

## What was learned

- **BTF-stripping** is a reproducible technique for using stock-kernel OOT modules (IB drivers, others) inside vendor kernels. Documented in `lustre/ROCKY9_RDMA_BREAKTHROUGH.md`. Likely useful for Lustre, ZFS, or any other stack that ships a custom kernel.
- **`nofail` should never be applied to a critical filesystem** unless paired with explicit health checks. It converts a loud failure into a silent one.
- **Loop-backed MGS** is a lab convenience that introduces a hidden boot dependency. Production deployments should use a dedicated block device or a properly-managed loopback systemd unit.
- **Lustre `_netdev` mounts depend on Lustre Networking, not just IP networking.** systemd's `network-online.target` is reached before LNET is up, leading to races on cold start.

## Hardware/configuration snapshot

- OS: Rocky Linux 9.7
- Kernel: `5.14.0-611.13.1_lustre.el9.x86_64` (with BTF-stripped stock IB modules)
- Lustre: 2.17.0 with FLR
- Transport: o2ib (RDMA over InfiniBand)
- Network: Mellanox ConnectX-5 EDR 100 Gbps, switch SB7790
- Topology: 1 MGS (Head-1, loop device), 2 MDTs (heads, physical SSDs), 16 OSTs (8 compute × 2 SSDs)
- Capacity: 3.7 TB (1.85 TB usable with 2-way FLR)

## See also

- `lustre/ROCKY9_RDMA_BREAKTHROUGH.md` — full technical writeup of the BTF discovery and FLR validation.
- `lustre/log.md` — chronological session log including today's cold-boot postmortem.
- `lustre/README.md` — current operational state and recovery procedure.
