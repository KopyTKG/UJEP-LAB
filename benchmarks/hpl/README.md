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
