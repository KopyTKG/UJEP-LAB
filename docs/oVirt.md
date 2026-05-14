# oVirt — investigated, rejected

- Investigated: 2026-05-14
- Status considered: oVirt 4.5.7 (released 2026-01-13)
- Outcome: **NO-GO** for this cluster

Investigated as a possible replacement for the Kubernetes workload layer:
a KVM-clustering hypervisor with a polished UI, multi-tenancy, and shared
storage, sitting on top of the existing Lustre 2.17.0 + RDMA backend.

## Project status (May 2026)

- Last release **4.5.7** on **2026-01-13**. Cadence is roughly one point
  release per year (4.5.5 Dec 2023 → 4.5.6 Dec 2024 → 4.5.7 Jan 2026).
- Post-RHV EOL (August 2024), Red Hat handed the project to the community.
  Oracle continues to fund development through Oracle Linux Virtualization
  Manager. Sep 2025 project update explicitly says "no planned EOL".
- ovirt-users mailing list sees only a few substantive threads per month,
  most user-side. Developer follow-up is sparse.
- Alive but on life support. Not dead, but not vibrant.

## EL version support

- 4.5.7 supports CentOS Stream 9 / 10, RHEL 9 / 10, and derivatives
  (Rocky / Alma 9 + 10) for both Engine and Hosts.
- RHEL 10 support was added in 4.5.7 (Jan 2026) — brand new, with reported
  emulated-machine-type issues during testing.
- oVirt Node NG ISO remains CentOS Stream 9 only.

## Why it does not work here — storage

oVirt's POSIX storage domain types are: **NFS, GlusterFS, iSCSI, FCP, pNFS,
POSIX compliant FS**. The relevant one for us would be POSIX compliant FS
with Lustre mounted on every host.

Two killers:

1. **Lustre does not work as a POSIX storage domain.**
   oVirt's VDSM writes `xleases` (the external lease structure used by the
   storage domain) with a block size of **256512 bytes**. Lustre with
   `O_DIRECT` requires writes to be **4 KiB-aligned**. The result is a
   `Invalid argument` failure when VDSM tries to format the storage domain,
   so it never comes up. The canonical ovirt-users thread on this is open
   with no fix and no maintainer follow-up. Zero public success stories of
   oVirt-on-Lustre exist; every blog post that says "oVirt + Lustre" ends
   up re-exporting Lustre via NFS, which kills the RDMA point.

2. **The "obvious" fallback — GlusterFS — cannot use our 100 Gb/s
   InfiniBand fabric.**
   The Gluster RDMA transport was deprecated and removed upstream around
   the 6.x era. Current Gluster on this cluster would run over TCP/IPoIB,
   wasting the entire reason we have a Mellanox ConnectX-5 EDR fabric.
   See [GlusterFS notes](../glusterfs/README.md) — measured 70-220 MB/s
   write per node on the TCP path, vs. Lustre's RDMA path that's
   SSD-bound (165 MB/s write, 331 MB/s read per node, aggregating to
   1.38 / 2.77 GB/s across 8 nodes).

NFS over IPoIB is technically possible but again — no RDMA. iSCSI and FCP
do not apply (no SAN fabric).

## Verdict

NO-GO. Even if oVirt were a thriving project (it is not), the supported
storage options either don't actually work with Lustre (POSIX FS / xleases
bug) or can't use the RDMA fabric we built the cluster around (Gluster's
RDMA transport gone, NFS no native RDMA). The combination of an upstream
in maintenance mode, an unresolved blocker bug specific to our exact
storage stack, and zero documented success cases of oVirt+Lustre means
testing this would have burned days of work for a known dead end.

## What was picked instead

**OpenNebula** is the natural fit and was the original plan for this
cluster (CLAUDE.md still references `oned/sunstone/scheduler` on the head
nodes). Its `DS_MAD=fs` / `TM_MAD=shared` datastore is explicitly designed
for shared POSIX filesystems and the docs from 6.0 through 6.10 list
**Lustre** as a supported backend. KVM-native, runs on Rocky 9, and the
hardware roles we already have (2 heads + 8 KVM-capable compute) map
directly onto OpenNebula's frontend + node split.

## Sources

- [oVirt 4.5.7 Release Notes](https://www.ovirt.org/release/4.5.7/)
- [oVirt 4.5.7 GA blog (Jan 2026)](https://blogs.ovirt.org/2026/01/ovirt-4-5-7-is-now-generally-available/)
- [oVirt Project Update (Sep 2025)](https://blogs.ovirt.org/2025/09/ovirt-project-update/)
- [Lustre POSIX storage domain mount error thread](https://lists.ovirt.org/archives/list/users@ovirt.org/thread/2XVAJGYIJEZKR4QZWY4R2G2LZ555H5IP/)
- [oVirt PosixFSConnection feature doc](https://www.ovirt.org/develop/release-management/features/storage/posixfsconnection.html)
- [OpenNebula 6.10 NFS/NAS Datastores (Lustre listed)](https://docs.opennebula.io/6.10/open_cluster_deployment/storage_setup/nas_ds.html)
