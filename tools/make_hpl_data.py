#!/usr/bin/env python3
"""Regenerate the thesis HPL dataset from benchmarks/hpl.

    python3 tools/make_hpl_data.py [THESIS_DATA_DIR]      (default ~/Projects/thesis/data)

Writes <dir>/hpl_data.json and copies hpl.csv, the raw HPL outputs and the README to <dir>/hpl/.
Measured values come from hpl.csv and the raw outputs; hardware/software labels are written here.
"""
import csv, glob, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "benchmarks", "hpl"))
DEST = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/Projects/thesis/data")


def runs():
    rows = [r for r in csv.DictReader(open(os.path.join(SRC, "hpl.csv"))) if r["gflops"]]
    one = next((float(r["gflops"]) for r in rows if r["nodes"] == "1"), None)
    out = []
    for r in rows:
        k, g = int(r["nodes"]), float(r["gflops"])
        raw = glob.glob(os.path.join(SRC, "logs", f"hpl_{r['timestamp']}_k{k}.txt"))
        txt = open(raw[0]).read() if raw else ""
        t0 = re.search(r"HPL_pdgesv\(\) start time (.*)", txt)
        t1 = re.search(r"HPL_pdgesv\(\) end time (.*)", txt)
        upd = re.search(r"Max aggregated wall time update[ .]*:\s+([0-9.]+)", txt)
        res = re.search(r"=\s+([0-9.eE+-]+) \.+ (PASSED|FAILED)", txt)
        out.append({
            "timestamp": r["timestamp"], "nodes": k, "includes_heads": r["includes_heads"] == "True",
            "mpi_ranks": int(r["mpi_ranks"]), "threads_per_rank": int(r["threads_per_rank"]), "mpi_net": r["mpi_net"],
            "N": int(r["N"]), "NB": int(r["NB"]), "grid_PxQ": [int(r["P"]), int(r["Q"])],
            "time_s": float(r["time_s"]), "gflops": g, "tflops": round(g / 1000, 3), "gflops_per_node": round(g / k, 1),
            "rpeak_gflops_at_2.2ghz": round(float(r["rpeak_gflops_at_nominal_ghz"]), 1),
            "efficiency_pct_of_rpeak_2.2ghz": float(r["efficiency_pct"]),
            "scaling_efficiency_vs_1_node_pct": round(g / one / k * 100, 1) if one else None,
            "residual": res.group(1) if res else None, "residual_passed": r["residual_passed"] == "True",
            "mpirun_rc": int(r["mpirun_rc"]), "solve_start": t0.group(1).strip() if t0 else None,
            "solve_end": t1.group(1).strip() if t1 else None,
            "update_phase_s": float(upd.group(1)) if upd else None,
            "raw_output": f"hpl/logs/hpl_{r['timestamp']}_k{k}.txt" if raw else None})
    return out


def main():
    data = {
        "metadata": {
            "description": "HPL (LINPACK) double-precision benchmark on the UJEP-LAB cluster, 2026-10-22. Source: UJEP-LAB/benchmarks/hpl (hpl.csv, logs); playbooks opennebula/playbooks/hpl_setup.yml, hpl_run.yml; regenerate with tools/make_hpl_data.py.",
            "hardware_per_node": "2 x Intel Xeon E5-2650 v4 (12 cores each, 24 cores, 48 threads), 64 GiB DDR4 (62.26 GiB visible), ConnectX-5 EDR 100 Gbit/s",
            "nodes": "8 computes (Rocky-Compute-1..8) plus 2 heads (Rocky-Head-1/2, Lustre MGS/MDT servers)",
            "software": {"os": "Rocky Linux 9.7, kernel 5.14.0-611.13.1_lustre.el9", "hpl": "2.3 (sha256 32c5c17d22330e6f2337b681aded51637fb6008d3f0eb7c277b163fadd612830)",
                         "mpi": "Open MPI 4.1.1 (distro), pml ucx over UCX 1.19.1 (rc_verbs/ud_verbs on mlx5_0, RDMA)",
                         "blas": "OpenBLAS 0.3.29, threaded build (libopenblasp), CBLAS interface", "compiler": "gcc 11.5.0, -O3 -march=haswell"},
            "configuration": "one MPI rank per socket (2 per node), 12 BLAS threads per rank bound to the socket; NB=192; PFACT right, RFACT Crout, 1ring-modified broadcast, lookahead 1, mix swap; xhpl run from local disk on every node",
            "matrix_size_rule": "N = sqrt(frac * node_memory * nodes / 8) rounded down to a multiple of NB; frac 0.75 for 1 and 5 nodes, 0.70 for 10 nodes",
            "rpeak_note": "Rpeak = nodes x 24 cores x 16 DP FLOP/cycle x 2.2 GHz (nominal base). Observed clocks during the runs averaged about 2.5-2.6 GHz over all logical CPUs (including idle hyper-threads), so efficiency against the nominal figure is not a hard ceiling.",
            "caveats": ["The 10-node run includes the two Lustre servers (heads), used nice 10 and 70% memory for safety; Lustre stayed responsive (lfs df about 0.014 s).",
                        "Single runs, no repetitions; one block size (NB 192); distro OpenBLAS, not Intel MKL.",
                        "Power draw was not measured; the lab breaker limit was the reason for the 1 -> 5 -> 10 node ramp."]},
        "runs": runs(),
        "findings": [
            {"id": "H1", "title": "HPL scales almost linearly over InfiniBand", "result": "713.5 GFLOPS on 1 node, 3,476.5 on 5 (97.5% scaling), 6,751.0 on all 10 nodes (94.6% scaling, 79.9% of the nominal 8.45 TFLOPS peak); all residual checks PASSED. The fabric and MPI over RDMA cost about 5% at 10 nodes."},
            {"id": "H2", "title": "Distro OpenBLAS: libopenblas.so is the serial build", "result": "On Rocky 9 libopenblas.so is single-threaded; the threaded build is libopenblasp.so. Linking the former would have made each MPI rank use 1 core instead of 12 without any error."},
            {"id": "H3", "title": "firewalld blocks Open MPI by default", "result": "ibs1 sits in the public zone with a port whitelist; Open MPI uses dynamic ports, so multi-node launches failed ('unable to complete a TCP connection'). Fixed with a rich rule accepting only the IB subnet 10.0.0.0/24. A 1-node run never notices because it stays on the node."},
            {"id": "H4", "title": "UID mismatch on Compute-3", "result": "The `user` account has UID 1001 on Compute-3 and 1000 on all other nodes (heads included). Lustre identifies users by UID and the MDS does not know 1001, so `user` on Compute-3 gets 'Permission denied' below /mnt/lustre (root works). Worked around by staging xhpl and the run directory on local disk as root; the mismatch itself is not fixed and also matters for OpenNebula."}]}
    os.makedirs(os.path.join(DEST, "hpl", "logs"), exist_ok=True)
    with open(os.path.join(DEST, "hpl_data.json"), "w") as f:
        json.dump(data, f, indent=1)
    for p in ("hpl.csv", "README.md"):
        shutil.copy(os.path.join(SRC, p), os.path.join(DEST, "hpl"))
    for p in glob.glob(os.path.join(SRC, "logs", "*.txt")):
        shutil.copy(p, os.path.join(DEST, "hpl", "logs"))
    print(f"runs={len(data['runs'])} findings={len(data['findings'])} -> {DEST}")


if __name__ == "__main__":
    main()
