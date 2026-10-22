# HPL (LINPACK) on the compute nodes

Measures double-precision GFLOPS of the cluster with HPL 2.3, Open MPI and OpenBLAS (distro packages).
Everything is Ansible; nothing was run on the cluster when this was written (prepared 2026-10-15), so the
first run is also the test of the setup.

## Run it

```bash
just hpl-setup      # once: packages, MPI ssh key, memlock, build HPL on Lustre (~10 min)
just hpl-quick      # sanity: 2 nodes, N=20000, a couple of minutes. Must end with "residual PASSED"
just hpl            # scaling series on 1, 2, 4, 8 computes (about 1.5-2 h in total)
just hpl 8          # one size only
just hpl 8 -e hpl_net=tcp   # MPI over IPoIB TCP instead of UCX/RDMA (fallback if UCX misbehaves)
```

Needs the cluster up and healthy (`just health`). By default the 8 computes only; the heads host the MGS/MDTs
and the Galera databases. An opt-in 10-node run is described below.

### All 10 nodes (opt-in)

```bash
just hpl-setup-heads   # once: the same install, memlock and MPI key on the 2 heads
just hpl-all           # one run on all 10 nodes (8 computes + Head-1 + Head-2), 20 ranks, grid 4 x 5, N=250,176
```

Expected: about 5.2 TFLOPS (range 4.1-6.1), run time 33-41 min, Rpeak 8.45 TFLOPS at 2.2 GHz. During the run the
heads' MGS/MDTs and databases compete with HPL for all cores, so keep Lustre idle and treat the 10-node number as
a separate data point ("all blades, including the metadata heads"), not as part of the scaling series. The column
`includes_heads` in `hpl.csv` marks these rows. `hpl_nodes` counts nodes from the pool, computes first, so k=8 is
always the 8 computes.

## What it does and changes on the cluster

- `playbooks/hpl_setup.yml`
  - installs `openmpi openmpi-devel openblas openblas-devel ucx ucx-ib ucx-rdmacm` on the computes
    (packages only, no kernel packages, so the Lustre kernel pin is not touched)
  - `/etc/security/limits.d/90-hpl-memlock.conf`: memlock unlimited for `user` (RDMA pins memory; the default is 8 MB)
  - a dedicated ssh key for MPI launches: private key on Compute-1 only, public key authorized on the computes
    only from the IB subnet (`from="10.0.0.0/24"`); there was no passwordless ssh between computes before
  - downloads HPL 2.3 from netlib to `/mnt/lustre/hpl`, records its sha256 next to it, builds `bin/rocky/xhpl`
    there, so all nodes run the same binary
- `playbooks/hpl_run.yml` (+ `hpl_run_one.yml`): for each node count k it writes `HPL.dat`, runs `mpirun` on
  Compute-1 (one rank per socket, 12 BLAS threads, bound to the socket) and appends one row to `hpl.csv`;
  the raw HPL output goes to `logs/`.

Undo: remove `/etc/security/limits.d/90-hpl-memlock.conf`, the `mpi-launch` line in `~user/.ssh/authorized_keys`
on the computes and `~/.ssh/id_mpi*` plus the "MPI launch (HPL)" block in `~/.ssh/config` on Compute-1, and
`/mnt/lustre/hpl`.

## Parameters (override with `-e`)

| Variable | Default | Meaning |
|---|---|---|
| `hpl_nodes` | `[1,2,4,8]` | node counts to run; the pool is the computes, plus the heads with `hpl_heads=true` |
| `hpl_heads` | false | include Head-1/Head-2 in the node pool (needs `hpl-setup-heads` first) |
| `hpl_mem_frac` | 0.75 | share of node memory the matrix may use; N = sqrt(frac * memory * k / 8), rounded to a multiple of NB |
| `hpl_nb` | 192 | block size (192 or 256 are typical for Haswell/OpenBLAS; worth one comparison run) |
| `hpl_ranks_per_node` / `hpl_threads` | 2 / 12 | one MPI rank per socket, 12 threads each |
| `hpl_net` | `ucx` | `ucx` (RDMA over IB) or `tcp` (IPoIB) |
| `hpl_quick` | false | 2 nodes, N=20000 |

Sizes the playbook computes for 62.3 GiB per node (checked offline with Ansible):

| Nodes | MPI ranks | Grid P x Q | N | Rpeak at 2.2 GHz |
|---|---|---|---|---|
| 1 | 2 | 1 x 2 | 79,104 | 845 GFLOPS |
| 2 | 4 | 2 x 2 | 111,936 | 1,690 |
| 4 | 8 | 2 x 4 | 158,208 | 3,379 |
| 8 | 16 | 4 x 4 | 223,872 | 6,758 |
| 10 (with heads) | 20 | 4 x 5 | 250,176 | 8,448 |

Run time is roughly 2/3 N^3 / (achieved FLOPS): about 12 min for one node and about 35 min for eight, if the
efficiency is near 75-80%.

## Reading the results

`hpl.csv` columns: timestamp, nodes, includes_heads, MPI ranks, threads per rank, MPI net, N, NB, P, Q, time, GFLOPS,
Rpeak at the nominal 2.2 GHz, efficiency %, residual passed, mpirun exit code.

- Rpeak assumes 16 double-precision FLOP/cycle/core (2 AVX2 FMA units x 4 doubles x 2) at **2.2 GHz**. The real
  AVX clock of an E5-2650 v4 under HPL is lower (about 1.8-2.2 GHz, turbo up to 2.9 GHz for light loads), so
  the efficiency column is relative to the nominal figure, not a hard ceiling; an efficiency slightly above 100%
  is possible if turbo helps. State the reference frequency when quoting it.
- A run only counts if the residual check says PASSED; a failed or crashed run is still recorded (rc and passed=False).
- Quote the scaling series (efficiency per node count): the drop from 1 to 8 nodes is what the IB fabric and the
  MPI stack cost.
- Distro OpenBLAS is simple and reproducible but usually a bit below Intel MKL's LINPACK on Broadwell; say which
  one was used.

## Things to check on the first run

1. `just hpl-setup` ends without failures; `xhpl` exists at `/mnt/lustre/hpl/hpl-2.3/bin/rocky/xhpl`.
2. `just hpl-quick` passes. If `mpirun` complains about UCX or memlock, retry with `-e hpl_net=tcp` and note it.
3. Do not run it together with the soak or other load: HPL uses all cores and a large part of the memory.
4. After the series, shut down in the usual way (`just down`).

## Setup log

**2026-10-22, first real run of `just hpl-setup`** (computes only; heads not set up):
- Packages, memlock, MPI key, download and build all worked on the second attempt. First attempt failed in the build:
  my Makefile template never defined `HPL_DEFS`, so `hpl.h` was not found. Fixed in `playbooks/hpl_setup.yml`: `HPL_DEFS`,
  `-DHPL_CALL_CBLAS`, `LAinc = -I/usr/include/openblas`.
- **`libopenblas.so` on Rocky 9 is the single-threaded build**; `libopenblasp.so` is the pthreads build. The Makefile
  links `-lopenblasp`, otherwise every MPI rank would silently use one core instead of 12 (`ldd xhpl` shows
  `libopenblasp.so.0`).
- Downloaded `hpl-2.3.tar.gz` sha256 `32c5c17d22330e6f2337b681aded51637fb6008d3f0eb7c277b163fadd612830`
  (stored next to it in `/mnt/lustre/hpl`).
- Checked without load: `xhpl` is 234,824 bytes and links libopenblasp and Open MPI 4.1.1; passwordless ssh with the MPI key
  from Compute-1 to Compute-2/5/8 works; memlock is `unlimited` in an ssh session; UCX 1.19.1 sees `mlx5_0:1` with the
  `rc_verbs`/`ud_verbs` transports (no `rc_mlx5`, which is not packaged), so `hpl_net=ucx` should run over RDMA.
- **No HPL run has been done yet.** HPL loads every core with AVX2 and draws far more power than the soak; the lab breaker
  limit (thesis note 12) has to be checked first. Plan: `just hpl-quick`, then `just hpl 1` while watching the power, then 2, 4, 8.

## Results, 2026-10-22

Open MPI 4.1.1 over UCX (RDMA), OpenBLAS 0.3.29 threaded, HPL 2.3, NB 192, one rank per socket with 12 threads. All residual checks PASSED.

| Nodes | MPI ranks | N | Grid | Time | GFLOPS | Per node | Scaling vs 1 node | % of nominal Rpeak (2.2 GHz) |
|---|---|---|---|---|---|---|---|---|
| 1 (Compute-1) | 2 | 79,104 | 1 x 2 | 463 s | 713.5 | 713.5 | 100% | 84.5% |
| 5 (Compute-1..5) | 10 | 177,024 | 2 x 5 | 1,064 s | 3,476.5 | 695.3 | 97.5% | 82.3% |
| **10 (8 computes + 2 heads)** | 20 | 241,728 | 4 x 5 | 1,395 s | **6,751.0** | 675.1 | 94.6% | 79.9% |

- The 10-node run includes the two Lustre servers (heads); it used `nice` 10 and 70% of memory (the others 75%). Lustre stayed
  responsive throughout (`lfs df` about 0.014 s).
- 98-99% of the solve time is the matrix update (DGEMM) (98.4% on 1 node, 99.2% on 5 and 10), so communication is not the bottleneck.
- Observed clocks were about 2.5-2.6 GHz averaged over all logical CPUs (idle hyper-threads included), so the percentages against
  the nominal 2.2 GHz peak are not a hard ceiling.
- Single runs; NB 192 only; distro OpenBLAS (Intel MKL would likely be 10-20% faster). The 8-computes-only point and an NB sweep
  were not run.
- Dataset: thesis `data/hpl_data.json` (regenerate with `tools/make_hpl_data.py`).

Problems met on the first real runs (all fixed in the playbooks): the Makefile template lacked `HPL_DEFS`; `libopenblas.so` is
the serial build on Rocky (use `libopenblasp`); `firewalld` blocked Open MPI's dynamic ports (rich rule for the IB subnet);
`user` has UID 1001 on Compute-3 and 1000 elsewhere, so Compute-3's `user` cannot read Lustre (xhpl and the run directory are
therefore staged on local disk by root); the first `mpirun` mapping used `ppr:2:socket` instead of one rank per socket.
