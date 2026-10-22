#!/usr/bin/env python3
"""Lustre performance matrix with cache effects controlled (thesis note 14, section 1 / R3).

    python3 tools/lustre_bench.py baseline            # per-SSD raw read + file-on-OST write
    python3 tools/lustre_bench.py run [--reps 3] [--clients 1,4,8] [--configs default,tuned] [--runtime 45] [--quick]
    python3 tools/lustre_bench.py control             # OSS cache off vs on, same workload (how much cache inflates reads)
    python3 tools/lustre_bench.py plan                # what `run` would do and a time estimate

Everything is fio on the 8 computes (each is client and OSS), direct I/O, JSON output, parsed and aggregated here.
Console and raw results go to benchmarks/lustre/logs; numbers to benchmarks/lustre/*.csv.

Configs ('default' = the cluster as it is; 'tuned' = the client-side part of the March 2026 tuning):
  default: stripe 1 x 4 MiB, max_rpcs_in_flight 8, max_dirty_mb 2000, read-ahead as found
  tuned:   stripe 4 x 4 MiB, max_rpcs_in_flight 32, max_dirty_mb 64, read_ahead 256 / per file 128
Runtime tunables are restored at the end. Server settings are NOT touched (sync_journal=0 from the old tuning is
not applied: it changes durability), except by `control`, which toggles the OSS read/writethrough caches and restores them.

`baseline` is read-only: raw reads of every pool SSD (fio --readonly), one at a time and both drives of a node at once.
It also reports each drive's negotiated SATA link speed. A write baseline cannot be taken this way: an OST mount
directory is not a writable directory (fio fails with ENOTDIR) and the devices must not be written while Lustre uses
them. The March 2026 bare-SSD write figures (benchmarks/*ssd_baseline*, taken before the OSTs were formatted) are
the write reference.
"""
import argparse, csv, json, os, re, statistics, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("ANSIBLE_FORKS", "16")      # clients must start together
import stability as S                              # adhoc(), good(), inventory(), Log, say

OUT = os.path.normpath(os.path.join(HERE, "..", "benchmarks", "lustre"))
BASE = "/mnt/lustre/bench"
MIBS_TO_GBIT = 8.388608 / 1000

CONFIGS = {
    "default": {"stripe": 1, "set": {}},
    "tuned": {"stripe": 4, "set": {"osc.*.max_rpcs_in_flight": "32", "osc.*.max_dirty_mb": "64",
                                   "llite.*.max_read_ahead_mb": "256", "llite.*.max_read_ahead_per_file_mb": "128"}},
}
RESTORE_KEYS = ["osc.*.max_rpcs_in_flight", "osc.*.max_dirty_mb", "llite.*.max_read_ahead_mb",
                "llite.*.max_read_ahead_per_file_mb"]
# phase: (fio rw, block size, iodepth, size-based?)
PHASES = {"seq_write": ("write", "1M", 16, True), "seq_read": ("read", "1M", 16, False),
          "rand_read_4k": ("randread", "4k", 32, False), "rand_write_4k": ("randwrite", "4k", 32, False)}


# ------------------------------------------------------------------ pure helpers (unit-tested)
def parse_fio(text):
    """First JSON document in fio's output -> dict, or None."""
    i = (text or "").find("{")
    if i < 0:
        return None
    try:
        return json.loads(text[i:])
    except Exception:
        # fio may print trailing text; cut at the last closing brace
        j = text.rfind("}")
        try:
            return json.loads(text[i:j + 1])
        except Exception:
            return None


def job_metrics(doc, direction):
    """bw MiB/s, iops, mean latency us, p99 latency us, errors for read/write of the group-reported job."""
    if not doc or not doc.get("jobs"):
        return None
    j = doc["jobs"][0]
    d = j[direction]
    clat = d.get("clat_ns", {})
    p99 = (clat.get("percentile") or {}).get("99.000000")
    lat_mean = d.get("lat_ns", {}).get("mean")
    return {"bw_mib_s": d["bw"] / 1024.0, "iops": d["iops"],
            "lat_mean_us": (lat_mean / 1000.0) if lat_mean is not None else None,
            "lat_p99_us": (p99 / 1000.0) if p99 is not None else None,
            "errors": int(j.get("error", 0)) + int(d.get("total_err", 0) if isinstance(d.get("total_err"), int) else 0)}


def aggregate(per_client):
    """Combine per-client metrics: bandwidth and IOPS add, latency is averaged (p99: worst client)."""
    ms = [m for m in per_client if m]
    if not ms:
        return None
    lat = [m["lat_mean_us"] for m in ms if m["lat_mean_us"] is not None]
    p99 = [m["lat_p99_us"] for m in ms if m["lat_p99_us"] is not None]
    return {"clients_ok": len(ms), "bw_mib_s": sum(m["bw_mib_s"] for m in ms), "iops": sum(m["iops"] for m in ms),
            "lat_mean_us": statistics.mean(lat) if lat else None, "lat_p99_us_worst": max(p99) if p99 else None,
            "errors": sum(m["errors"] for m in ms)}


def fio_cmd(directory, phase, size, runtime, ramp, jobs=4):
    rw, bs, depth, size_based = PHASES[phase]
    # the job name is part of fio's file names (bench.<job>.<n>): every phase must use the same one,
    # otherwise a read phase would create and prefill its own new files instead of reading the written ones
    c = (f"mkdir -p {directory} && fio --name=bench --directory={directory} --rw={rw} --bs={bs} --direct=1 "
         f"--ioengine=libaio --iodepth={depth} --numjobs={jobs} --size={size} --group_reporting --randrepeat=0 "
         f"--output-format=json")
    if rw.startswith("rand"):
        c += " --norandommap"
    if not size_based:
        c += f" --time_based --runtime={runtime} --ramp_time={ramp}"
    return c


def summarize_cells(rows):
    """mean / stdev over repeats for each (config, clients, phase)."""
    cells = {}
    for r in rows:
        cells.setdefault((r["config"], int(r["clients"]), r["phase"]), []).append(float(r["bw_mib_s"]))
    out = []
    for (cfg, k, ph), xs in sorted(cells.items()):
        out.append({"config": cfg, "clients": k, "phase": ph, "n": len(xs), "mean_mib_s": statistics.mean(xs),
                    "stdev_mib_s": statistics.stdev(xs) if len(xs) > 1 else 0.0})
    return out


# ------------------------------------------------------------------ cluster helpers
def csv_append(name, header, rows):
    path = os.path.join(OUT, name)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerows(rows)


def drop_caches(computes):
    S.adhoc(",".join(computes), "sync; echo 3 > /proc/sys/vm/drop_caches", timeout=120)


def get_tunables(node):
    r = S.adhoc(node, " ; ".join(f'echo "{k}=$(lctl get_param -n {k} 2>/dev/null | head -1 | tr -d " \\n")"' for k in RESTORE_KEYS)).get(node, {})
    return S.kv(r.get("stdout", ""))


def set_tunables(computes, values):
    if not values:
        return
    cmd = " ; ".join(f"lctl set_param {k}={v} >/dev/null" for k, v in values.items())
    S.adhoc(",".join(computes), cmd, timeout=120)


def run_phase(clients, run_id, phase, size, runtime, ramp):
    """Run one fio phase on all `clients` at once; returns (aggregate, per-client raw metrics)."""
    # one ad-hoc call for all clients (they start together); each host derives its own directory from its hostname
    cmd = fio_cmd(f"{BASE}/{run_id}/$(hostname)", phase, size, runtime, ramp)
    res = S.adhoc(",".join(clients), cmd, timeout=runtime + ramp + 900)
    direction = "write" if PHASES[phase][0].endswith("write") else "read"
    per = {}
    for h in clients:
        v = res.get(h)
        doc = parse_fio(v.get("stdout", "")) if S.good(v) else None
        per[h] = job_metrics(doc, direction)
        if per[h] is None:
            S.LOG.raw(f"!! {h} {phase}: no usable fio result: {str(v)[:300]}")
    return aggregate(list(per.values())), per


# ------------------------------------------------------------------ commands
def cmd_plan(a):
    reps, ks, cfgs = a.reps, [int(x) for x in a.clients.split(",")], a.configs.split(",")
    per = 55 + 3 * (a.runtime + 5 + 12) + 50
    n = len(cfgs) * len(ks) * reps
    print(f"configs {cfgs} x clients {ks} x {reps} repeats = {n} cells x 4 phases; about {per/60:.1f} min per cell -> {n*per/3600:.1f} h")
    print(f"plus baseline (~10 min) and control (~10 min). Data per client per run: 16 GiB (written, then deleted).")
    return 0


def cmd_baseline(a):
    heads, computes, _ = S.inventory()
    rows = []
    script = r'''
set -u
out=/var/tmp/lbench; rm -rf $out; mkdir -p $out
devs=$(awk '$2 ~ /^\/mnt\/ost[0-9]+$/ {print $1":"$2}' /proc/mounts)
echo "DEVS=$devs"
for d in $devs; do dev=${d%%:*}; b=$(basename $dev); echo "LINK $b $(smartctl -i $dev 2>/dev/null | sed -nE 's/.*current: ([0-9.]+) Gb.*/\1/p') $(smartctl -A $dev 2>/dev/null | awk '$1==199{print $NF}')"; done
run() { fio --output-format=json --name=$1 "${@:2}" > $out/$1.json 2>$out/$1.err; }
RT=20
# 1) raw device, read only: one at a time, then both at once
for d in $devs; do dev=${d%%:*}; b=$(basename $dev)
  run raw_seq_read_$b --filename=$dev --readonly --rw=read --bs=1M --iodepth=16 --direct=1 --ioengine=libaio --runtime=$RT --time_based
  run raw_rand_read_$b --filename=$dev --readonly --rw=randread --bs=4k --iodepth=32 --direct=1 --ioengine=libaio --runtime=$RT --time_based --norandommap
done
i=0; for d in $devs; do dev=${d%%:*}; b=$(basename $dev)
  run raw_both_seq_read_$b --filename=$dev --readonly --rw=read --bs=1M --iodepth=16 --direct=1 --ioengine=libaio --runtime=$RT --time_based & i=$((i+1)); done; wait
for f in $out/*.json; do echo "###$(basename $f .json)"; cat $f; done
rm -rf $out
'''
    S.say(f"SSD baseline on {len(computes)} computes (raw reads only), about 5 minutes")
    # the script has shell syntax (${d%%:*}, quotes) that Ansible's argument splitter rejects: ship it as a file
    if not S.copy_file(",".join(computes), script, "/var/tmp/lbench.sh", "0755"):
        S.say("!! could not copy the baseline script to the nodes")
        return 2
    res = S.adhoc(",".join(computes), "bash /var/tmp/lbench.sh; rm -f /var/tmp/lbench.sh", timeout=1800)
    for h in computes:
        v = res.get(h)
        if not S.good(v):
            S.say(f"!! {h}: failed: {str(v)[:200]}")
            continue
        text = v["stdout"]
        devs = re.search(r"DEVS=(.*)", text).group(1).split()
        for ln in re.findall(r"^LINK (\S+) (\S*) (\S*)$", text, re.M):
            S.say(f"  {h:16} {ln[0]}  SATA link {ln[1] or '?'} Gbit/s   CRC errors {ln[2] or '?'}")
        for blk in text.split("###")[1:]:
            name, _, body = blk.partition("\n")
            doc = parse_fio(body)
            if not doc:
                continue
            direction = "write" if "write" in name else "read"
            m = job_metrics(doc, direction)
            if not m:
                continue
            dev = name.rsplit("_", 1)[-1]
            test = name[: -len(dev) - 1]
            mount = next((d.split(":")[1] for d in devs if d.split(":")[0].endswith(dev)), "")
            rows.append([time.strftime("%Y-%m-%dT%H:%M:%S"), h, dev, mount, test, round(m["bw_mib_s"], 1),
                         round(m["bw_mib_s"] * MIBS_TO_GBIT, 3), round(m["iops"]), round(m["lat_mean_us"] or 0, 1),
                         round(m["lat_p99_us"] or 0, 1), m["errors"]])
    csv_append("baseline.csv", ["ts", "node", "device", "ost_mount", "test", "bw_MiBps", "bw_Gbit_s", "iops",
                               "lat_mean_us", "lat_p99_us", "errors"], rows)
    S.say(f"\n{len(rows)} measurements -> {os.path.join(OUT, 'baseline.csv')}")
    for test in sorted({r[4] for r in rows if "both" not in r[4]}):
        xs = [r[5] for r in rows if r[4] == test]
        S.say(f"  {test:22} n={len(xs):2}  mean {statistics.mean(xs):7.1f} MiB/s  min {min(xs):7.1f}  max {max(xs):7.1f}")
    both = {}
    for r in rows:
        if "both" in r[4]:
            both.setdefault((r[1], r[4]), 0)
            both[(r[1], r[4])] += r[5]
    for t in sorted({k[1] for k in both}):
        xs = [v for (n, tt), v in both.items() if tt == t]
        S.say(f"  {t:22} per-node (2 SSDs at once) mean {statistics.mean(xs):7.1f} MiB/s")
    S.LOG.result({"command": "baseline", "measurements": len(rows)})
    return 0


def cmd_run(a):
    heads, computes, _ = S.inventory()
    ks = [int(x) for x in a.clients.split(",")]
    cfgs = a.configs.split(",")
    size, runtime, ramp = ("1G", 15, 3) if a.quick else ("4G", a.runtime, 5)
    h0 = S.health("before", heads, computes)
    if not h0["healthy"] and not a.force:
        S.say("!! cluster not healthy; pass --force to run anyway")
        return 2
    S.adhoc(computes[0], f"mkdir -p {BASE} && chmod 777 {BASE}")
    orig = get_tunables(computes[0])
    S.say(f"original tunables: {orig}")
    rows, raw = [], []
    started = time.strftime("%Y%m%dT%H%M%S")
    try:
        for cfg in cfgs:
            C = CONFIGS[cfg]
            set_tunables(computes, C["set"] if C["set"] else {k: orig[k] for k in orig if orig.get(k)})
            for k in ks:
                clients = computes[:k]
                for rep in range(1, a.reps + 1):
                    run_id = f"{started}_{cfg}_c{k}_r{rep}"
                    S.say(f"\n=== {cfg} / {k} client(s) / repeat {rep}  (stripe {C['stripe']})")
                    S.adhoc(",".join(clients), f"mkdir -p {BASE}/{run_id}/$(hostname) && lfs setstripe -c {C['stripe']} -S 4M {BASE}/{run_id}/$(hostname)")
                    for phase in PHASES:
                        drop_caches(computes)
                        agg, per = run_phase(clients, run_id, phase, size, runtime, ramp)
                        if not agg:
                            S.say(f"  {phase:14} FAILED on all clients")
                            continue
                        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "repeat": rep, "config": cfg, "stripe": C["stripe"],
                               "clients": k, "phase": phase, "clients_ok": agg["clients_ok"], "bw_mib_s": round(agg["bw_mib_s"], 1),
                               "bw_gbit_s": round(agg["bw_mib_s"] * MIBS_TO_GBIT, 3), "iops": round(agg["iops"]),
                               "lat_mean_us": round(agg["lat_mean_us"] or 0, 1), "lat_p99_us_worst": round(agg["lat_p99_us_worst"] or 0, 1),
                               "errors": agg["errors"], "oss_cache": "off"}
                        rows.append(row)
                        raw.append({**row, "per_client": per})
                        csv_append("lustre_matrix.csv", list(row), [list(row.values())])
                        S.say(f"  {phase:14} {row['bw_mib_s']:9.1f} MiB/s ({row['bw_gbit_s']:6.2f} Gbit/s)  {row['iops']:>8} IOPS  "
                              f"lat {row['lat_mean_us']:8.1f} us  p99 {row['lat_p99_us_worst']:9.1f} us  err {row['errors']}")
                    S.adhoc(",".join(clients), f"rm -rf {BASE}/{run_id}", timeout=900)
    finally:
        set_tunables(computes, {k: v for k, v in orig.items() if v})   # restore what we found
        S.adhoc(computes[0], f"rm -rf {BASE}/{started}_* ; true")
        S.say("tunables restored")
    summ = summarize_cells(rows)
    with open(os.path.join(OUT, f"matrix_{started}.json"), "w") as f:
        json.dump({"started": started, "args": vars(a), "original_tunables": orig, "runs": raw, "summary": summ}, f, indent=1, default=str)
    S.say("\n=== summary (mean +- stdev over repeats, MiB/s)")
    for s in summ:
        S.say(f"  {s['config']:8} {s['clients']:>2} clients {s['phase']:14} {s['mean_mib_s']:9.1f} +- {s['stdev_mib_s']:6.1f}  (n={s['n']})")
    S.LOG.result({"command": "run", "cells": len(summ)})
    return 0


def cmd_control(a):
    """Same workload with the OSS caches off (as found) and on: how much can cache inflate the reads?"""
    heads, computes, _ = S.inventory()
    k = len(computes)
    cfg = CONFIGS["tuned"]
    size, runtime, ramp = ("1G", 15, 3) if a.quick else ("4G", a.runtime, 5)
    S.adhoc(computes[0], f"mkdir -p {BASE} && chmod 777 {BASE}")
    orig = get_tunables(computes[0])
    cache = S.adhoc(computes[0], "lctl get_param -n osd-ldiskfs.*.read_cache_enable osd-ldiskfs.*.writethrough_cache_enable | sort | uniq -c").get(computes[0], {}).get("stdout", "")
    S.say(f"OSS cache settings found (value counts): {cache.strip()!r}")
    rows = []
    try:
        set_tunables(computes, cfg["set"])
        for state, val in (("off", 0), ("on", 1)):
            S.adhoc(",".join(computes), f"lctl set_param osd-ldiskfs.*.read_cache_enable={val} osd-ldiskfs.*.writethrough_cache_enable={val} >/dev/null")
            for rep in range(1, a.reps + 1):
                run_id = f"control_{state}_r{rep}_{time.strftime('%H%M%S')}"
                S.say(f"\n=== OSS cache {state} / {k} clients / repeat {rep} (tuned layout, working set {k * 16} GiB)")
                S.adhoc(",".join(computes), f"mkdir -p {BASE}/{run_id}/$(hostname) && lfs setstripe -c {cfg['stripe']} -S 4M {BASE}/{run_id}/$(hostname)")
                drop_caches(computes)
                for phase in ("seq_write", "seq_read", "seq_read"):
                    if phase == "seq_read" and state == "off":
                        drop_caches(computes)      # cold: nothing may be cached anywhere
                    agg, _ = run_phase(computes, run_id, phase, size, runtime, ramp)
                    if agg:
                        row = [time.strftime("%Y-%m-%dT%H:%M:%S"), state, rep, phase, round(agg["bw_mib_s"], 1),
                               round(agg["bw_mib_s"] * MIBS_TO_GBIT, 3), round(agg["lat_mean_us"] or 0, 1)]
                        rows.append(row)
                        S.say(f"  oss_cache={state:3} {phase:10} {row[4]:9.1f} MiB/s ({row[5]:6.2f} Gbit/s)")
                S.adhoc(",".join(computes), f"rm -rf {BASE}/{run_id}", timeout=900)
    finally:
        S.adhoc(",".join(computes), "lctl set_param osd-ldiskfs.*.read_cache_enable=0 osd-ldiskfs.*.writethrough_cache_enable=0 >/dev/null; sync; echo 3 > /proc/sys/vm/drop_caches")
        set_tunables(computes, {k2: v for k2, v in orig.items() if v})
        S.say("OSS caches back to 0 (as found), tunables restored")
    csv_append("control.csv", ["ts", "oss_cache", "repeat", "phase", "bw_MiBps", "bw_Gbit_s", "lat_mean_us"], rows)
    S.LOG.result({"command": "control", "rows": rows})
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("baseline", cmd_baseline), ("run", cmd_run), ("control", cmd_control), ("plan", cmd_plan)):
        s = sub.add_parser(name)
        s.add_argument("--reps", type=int, default=3)
        s.add_argument("--clients", default="1,4,8")
        s.add_argument("--configs", default="default,tuned")
        s.add_argument("--runtime", type=int, default=45)
        s.add_argument("--quick", action="store_true")
        s.add_argument("--force", action="store_true")
        s.set_defaults(fn=fn)
    a = p.parse_args()
    os.makedirs(os.path.join(OUT, "logs"), exist_ok=True)
    S.LOGDIR = os.path.join(OUT, "logs")
    if a.cmd == "plan":
        sys.exit(cmd_plan(a))
    S.LOG = S.Log("lustrebench_" + a.cmd)
    try:
        rc = a.fn(a)
    except KeyboardInterrupt:
        S.say("\ninterrupted")
        S.LOG.result({"interrupted": True})
        rc = 130
    sys.exit(rc)


if __name__ == "__main__":
    main()
