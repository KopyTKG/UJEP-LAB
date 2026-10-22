#!/usr/bin/env python3
"""Turn benchmarks/lustre/*.csv into RESULTS.md and the thesis dataset.

    python3 tools/make_lustre_data.py [THESIS_DATA_DIR]      (default ~/Projects/thesis/data)

Writes benchmarks/lustre/RESULTS.md (tables), <dir>/lustre_perf_data.json and copies CSVs and logs to <dir>/lustre/.
All numbers are computed from the CSV/JSON files; only the hardware-finding facts (read live from the nodes on
2026-10-22 with dmesg and smartctl) are written down here.
"""
import csv, glob, json, os, shutil, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
SRC = os.path.join(REPO, "benchmarks", "lustre")
DEST = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/Projects/thesis/data")
G = 8.388608 / 1000          # MiB/s -> Gbit/s
PHASES = [("seq_write", "Sequential write, 1 MiB blocks"), ("seq_read", "Sequential read, 1 MiB blocks"),
          ("rand_read_4k", "Random read, 4 KiB"), ("rand_write_4k", "Random write, 4 KiB")]
KS = (1, 4, 8)

HARDWARE = {
    "observed": "2026-10-22, read with dmesg/smartctl after the benchmark stages",
    "summary": "Three SATA links showed errors when all 16 pool SSDs were driven at their ~530 MB/s limit; two were downshifted by the kernel to SATA II (3.0 Gbit/s). SMART CRC error counters (attribute 199) are non-zero exactly on the affected drives; uncorrectable/media errors are 0 everywhere; no filesystem or I/O errors in dmesg; fio saw 0 errors. Pattern = signal integrity on specific bays (cable, connector or backplane), not failing drives.",
    "downshifted_to_3_0_gbit": [
        {"node": "Rocky-Compute-7", "device": "sdb", "ata": "ata6", "downshift": "2026-10-22 14:43:37", "crc_errors": 13, "first_error": "14:40:05", "failed_commands": 95, "link_resets": 4, "raw_seq_read_mib_s": 271.6},
        {"node": "Rocky-Compute-3", "device": "sda", "ata": "ata6", "ost": "OST5", "downshift": "2026-10-22 14:44:02", "crc_errors": 16, "first_error": "14:41:24", "failed_commands": 163, "link_resets": 8, "raw_seq_read_mib_s": 271.7}],
    "errors_but_still_6_0_gbit": [
        {"node": "Rocky-Compute-3", "device": "sdc", "ata": "ata7", "crc_errors": 23, "resets_during_matrix": ["14:44:27", "15:28:33", "15:43:02", "15:53:55"]},
        {"node": "Rocky-Compute-1", "device": "sda", "ata": "ata7", "ost": "OST0", "crc_errors": 2, "reset": "14:40:35"},
        {"node": "Rocky-Compute-7", "device": "sda", "crc_errors": 1}],
    "clean": "Compute-2, 4, 5, 6, 8 and all other drives: 0 link errors, 0 CRC errors",
    "context": "March 2026: all drives read 528-531 MiB/s. The 6 h soak (about 170 MB/s per drive) showed no link errors. The first errors came at 14:40, within minutes of the first full-speed read load (control stage), so the whole matrix (14:51 to about 16:00) ran with two drives at half speed.",
    "action": "Reseat or replace the SATA cables/backplane connectors of Compute-3 (both pool bays), Compute-7 (sdb) and Compute-1 (sda), then re-run `tools/lustre_bench.py baseline` and the matrix; until then avoid driving all drives to saturation."}


def rd(name):
    p = os.path.join(SRC, name)
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []


def matrix():
    cells = {}
    for r in rd("lustre_matrix.csv"):
        cells.setdefault((r["phase"], r["config"], int(r["clients"])), []).append(r)
    out = {}
    for key, rs in cells.items():
        bw = [float(x["bw_mib_s"]) for x in rs]
        out[key] = {"n": len(rs), "bw_mean": st.mean(bw), "bw_stdev": st.stdev(bw) if len(bw) > 1 else 0.0,
                    "iops_mean": st.mean(int(x["iops"]) for x in rs), "lat_mean_us": st.mean(float(x["lat_mean_us"]) for x in rs),
                    "errors": sum(int(x["errors"]) for x in rs)}
    return out


def baseline():
    rows = rd("baseline.csv")
    seq = {(r["node"], r["device"]): float(r["bw_MiBps"]) for r in rows if r["test"] == "raw_seq_read"}
    rnd = {(r["node"], r["device"]): int(r["iops"]) for r in rows if r["test"] == "raw_rand_read"}
    return seq, rnd


def march_write():
    v = []
    for f in sorted(glob.glob(os.path.join(REPO, "benchmarks", "20260326T12*_ssd_baseline_*_write.json"))):
        v.append(json.load(open(f))["jobs"][0]["write"]["bw"] / 1024)
    return v


def control():
    rows = rd("control.csv")
    out = {}
    for r in rows:
        out.setdefault((r["oss_cache"], r["phase"]), []).append(float(r["bw_MiBps"]))
    return out


def tables(m, seq, rnd, wr, ctl):
    md = []
    sum_seq = sum(seq.values())
    full = st.mean([v for v in seq.values() if v > 400]) * len(seq) if seq else 0
    wsum = st.mean(wr) * 16 if wr else 0
    md.append("### Aggregate throughput, MiB/s (Gbit/s), mean over 3 repeats, direct I/O, OSS caches off\n")
    for ph, title in PHASES:
        md.append(f"**{title}**\n\n| config | 1 client | 4 clients | 8 clients |\n|---|---|---|---|")
        for cfg in ("default", "tuned"):
            cols = []
            for k in KS:
                c = m.get((ph, cfg, k))
                cols.append(f"{c['bw_mean']:,.0f} +- {c['bw_stdev']:,.0f} ({c['bw_mean'] * G:.1f})" if c else "-")
            md.append(f"| {cfg} | " + " | ".join(cols) + " |")
        md.append("")
    md.append("**Random 4 KiB, aggregate IOPS (mean)**\n\n| phase | config | 1 client | 4 clients | 8 clients |\n|---|---|---|---|---|")
    for ph in ("rand_read_4k", "rand_write_4k"):
        for cfg in ("default", "tuned"):
            md.append(f"| {ph} | {cfg} | " + " | ".join(f"{m[(ph, cfg, k)]['iops_mean']:,.0f}" if (ph, cfg, k) in m else "-" for k in KS) + " |")
    md.append("")
    if ctl:
        md.append("### Cache control: 8 clients, tuned layout, 128 GiB working set\n\n| OSS cache | write MiB/s | read MiB/s (Gbit/s) |\n|---|---|---|")
        for state in ("off", "on"):
            w = st.mean(ctl.get((state, "seq_write"), [0])); r = st.mean(ctl.get((state, "seq_read"), [0]))
            md.append(f"| {state} | {w:,.0f} | {r:,.0f} ({r * G:.0f}) |")
        md.append("")
    md.append("### Drive ceilings\n")
    md.append(f"- Raw sequential read of the 16 pool SSDs, one at a time, measured after the link downshifts: sum **{sum_seq:,.0f} MiB/s** ({sum_seq * G:.1f} Gbit/s); "
              f"14 drives at 528-531 MiB/s, 2 at about 272 MiB/s (SATA II link).")
    md.append(f"- Same 16 drives at full speed (14 measured x 16): about **{full:,.0f} MiB/s**; spec 16 x 540 MB/s = 8,240 MiB/s.")
    md.append(f"- Bare-SSD sequential write measured in March 2026 (before the OSTs were formatted): mean {st.mean(wr):.0f} MiB/s per drive, 16 drives about **{wsum:,.0f} MiB/s**.\n")
    r8d, r8t = m.get(("seq_read", "default", 8)), m.get(("seq_read", "tuned", 8))
    w8t = m.get(("seq_write", "tuned", 8))
    if r8d and r8t and w8t:
        md.append("### How close to the drives\n")
        md.append(f"- Best cold read (default, 8 clients) {r8d['bw_mean']:,.0f} MiB/s = **{r8d['bw_mean'] / sum_seq * 100:.0f}%** of the measured drive sum ({sum_seq:,.0f}), {r8d['bw_mean'] / full * 100:.0f}% of 16 full-speed drives.")
        md.append(f"- Tuned, 8 clients: {r8t['bw_mean']:,.0f} MiB/s = {r8t['bw_mean'] / sum_seq * 100:.0f}% of the measured sum: more stripes and RPCs in flight do not help once every drive is busy.")
        md.append(f"- Best write (tuned, 8 clients) {w8t['bw_mean']:,.0f} MiB/s = **{w8t['bw_mean'] / wsum * 100:.0f}%** of the March bare-SSD write sum; the rest is Lustre/ldiskfs overhead.\n")
    return "\n".join(md)


def main():
    m, (seq, rnd), wr, ctl = matrix(), baseline(), march_write(), control()
    md = tables(m, seq, rnd, wr, ctl)
    with open(os.path.join(SRC, "RESULTS.md"), "w") as f:
        f.write("# Lustre performance results, 2026-10-22\n\nGenerated by `tools/make_lustre_data.py` from the CSV files in this folder.\n\n" + md + "\n")
    data = {"metadata": {"description": "Lustre 2.17.0 (o2ib RDMA) cache-controlled performance matrix, 8 computes as clients, 2026-10-22",
                         "tool": "tools/lustre_bench.py (fio 3.35, libaio, direct=1, 4 jobs per client, 4 GiB per job, 45 s runtime for the time-based phases)",
                         "configs": {"default": "stripe 1 x 4 MiB, max_rpcs_in_flight 8, max_dirty_mb 2000, read-ahead 1024/256", "tuned": "stripe 4 x 4 MiB, max_rpcs_in_flight 32, max_dirty_mb 64, read-ahead 256/128 (client side of the March 2026 tuning)"},
                         "oss_cache": "read_cache_enable=0 and writethrough_cache_enable=0 as found; the control stage switched them on and restored 0",
                         "caveat": "The whole matrix ran with two SSDs (OST5 on Compute-3, OST13 on Compute-7) on a 3.0 Gbit/s SATA link and a third (OST4) intermittently resetting; read ceilings are therefore lower than the full-speed 16-drive figure. See hardware_finding.",
                         "units": "MiB/s as measured; Gbit/s = MiB/s x 8.388608 / 1000"},
            "matrix": [{"phase": ph, "config": cfg, "clients": k, **{kk: round(v, 2) if isinstance(v, float) else v for kk, v in c.items()}, "bw_gbit_s": round(c["bw_mean"] * G, 3)}
                       for (ph, cfg, k), c in sorted(m.items())],
            "control": {f"oss_cache_{s}_{p}": [round(x, 1) for x in v] for (s, p), v in sorted(ctl.items())},
            "baseline_raw_read_per_ssd": [{"node": n, "device": d, "seq_read_mib_s": v, "rand_read_4k_iops": rnd.get((n, d))} for (n, d), v in sorted(seq.items())],
            "march_2026_bare_ssd_write_mib_s_per_node": [round(x, 1) for x in wr],
            "hardware_finding": HARDWARE}
    os.makedirs(os.path.join(DEST, "lustre", "logs"), exist_ok=True)
    with open(os.path.join(DEST, "lustre_perf_data.json"), "w") as f:
        json.dump(data, f, indent=1)
    for p in glob.glob(os.path.join(SRC, "*.csv")) + glob.glob(os.path.join(SRC, "matrix_*.json")) + [os.path.join(SRC, "RESULTS.md")]:
        shutil.copy(p, os.path.join(DEST, "lustre"))
    for p in glob.glob(os.path.join(SRC, "logs", "*.log")):
        shutil.copy(p, os.path.join(DEST, "lustre", "logs"))
    print(f"matrix cells={len(data['matrix'])} baseline drives={len(seq)} -> {DEST}")
    print(md)


if __name__ == "__main__":
    main()
