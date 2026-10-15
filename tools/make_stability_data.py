#!/usr/bin/env python3
"""Regenerate the thesis dataset from benchmarks/stability.

    python3 tools/make_stability_data.py [THESIS_DATA_DIR]      (default ~/Projects/thesis/data)

Writes <dir>/stability_data.json and copies the CSVs, result JSONs and logs to <dir>/stability/.
Everything measured is read from the files in benchmarks/stability; only the labels (which script
version was deployed, interpretations, findings) are written here.
"""
import collections, csv, glob, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "benchmarks", "stability"))
DEST = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/Projects/thesis/data")
SM_FIXED = "2026-10-08T16:32:00"       # subnet-manager layout changed (setup_opensm.yml)
FIX_DEPLOYED = "2026-10-01T16:30:00"   # fixed lustre-startup deployed between the 16:15 and 16:38 runs


def rd(name):
    p = os.path.join(SRC, name)
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []


def logs_by_cmd(prefix):
    return {os.path.basename(f): open(f).read() for f in glob.glob(os.path.join(SRC, "logs", prefix + "_*.log"))}


def cold_boot_runs():
    v2, settle = rd("coldboot_v2.csv"), {r["started"]: r for r in rd("coldboot_settle.csv")}
    logs = logs_by_cmd("coldboot")
    def log_for(started):
        key = started.replace("-", "").replace(":", "")
        c = sorted(f for f in logs if f[9:24] <= key)
        return c[-1] if c else None
    runs = collections.OrderedDict()
    for r in v2:
        runs.setdefault(r["started"], []).append(r)
    out = []
    for started, rows in runs.items():
        lg = log_for(started)
        t = logs.get(lg, "")
        m = re.search(r"--- after run %s: (HEALTHY|PROBLEMS)\s+\(lfs df: (\d+) OST, (\d+) MDT" % rows[0]["run"], t)
        seg = t.split("=== run %s/" % rows[0]["run"])[1].split("=== run ")[0] if ("=== run %s/" % rows[0]["run"]) in t else ""
        i = re.search(r"V SUMMARY ok=(\d+) bad=(\d+) err=(\d+) seconds=(\d+)", seg)
        mw = [int(r["mgs_wait_s"]) for r in rows if r["mgs_wait_s"]]
        comp = [int(r["unit_complete_s"]) for r in rows if r["unit_complete_s"]]
        st = settle.get(started)
        others = [int(r["boot_s"]) for r in rows if "Head-1" not in r["node"]]
        out.append({
            "date": started, "script": "legacy" if started < FIX_DEPLOYED else "fixed", "mode": rows[0]["mode"],
            "head1_delay_s": int(rows[0]["head1_delay_s"]),
            "nodes_mounted": sum(r["mounted"] == "yes" for r in rows), "nodes_total": len(rows),
            "fatal_retries_total": sum(int(r["fatal_retries"] or 0) for r in rows),
            "head1_os_up_s": int([r["boot_s"] for r in rows if "Head-1" in r["node"]][0]),
            "other_nodes_os_up_s_range": [min(others), max(others)],
            "mgs_wait_s_max": max(mw) if mw else None, "mgs_wait_s_min": min(mw) if mw else None,
            "all_units_complete_s": max(comp) if comp else None,
            "pool_fully_visible_after_mounted_s": int(st["settle_s"]) if st and st["settle_s"] else None,
            "lfs_df_after": {"result": m.group(1) if m else None, "osts": int(m.group(2)) if m else None,
                             "mdts": int(m.group(3)) if m else None},
            "integrity": ({"files_ok": int(i[1]), "files_bad": int(i[2]), "files_unreadable": int(i[3]),
                           "verify_seconds": int(i[4])} if i else None),
            "log": "stability/logs/" + str(lg),
            "per_node": [{"node": r["node"], "os_up_s": int(r["boot_s"]), "unit_begin_s": int(r["unit_begin_s"]),
                          "mgs_wait_s": int(r["mgs_wait_s"]) if r["mgs_wait_s"] else None,
                          "unit_complete_s": int(r["unit_complete_s"]), "fatal_retries": int(r["fatal_retries"] or 0)}
                         for r in rows]})
    return out


def first_coarse():
    g = collections.OrderedDict()
    for r in rd("coldboot.csv"):
        g.setdefault((r["run"], r["started"]), []).append(r)
    return [{"date": k[1], "script": "legacy", "mode": "graceful (coarse first version of the test)", "run": int(k[0]),
             "nodes_mounted": 10, "nodes_total": 10, "all_mounted_s_after_power_on_loop": int(v[0]["mounted_s"]),
             "note": "one cluster-wide poll time; clock starts after the IPMI power-on loop"} for k, v in g.items()]


EXTRA_COLD = [
    {"date": "2026-10-01T13:14", "script": "legacy", "mode": "power-on after ~3 months off (IPMI, all at once)",
     "nodes_mounted": 2, "nodes_total": 10, "result": "FAIL",
     "detail": "Both heads mounted; all 8 computes failed: 'MGS not reachable after 300s' (wall 168 s). Head-1 (MGS) reached the OS about 2.5 min after the computes.",
     "source": "thesis notes/15"},
    {"date": "2026-10-01T16:26", "script": "legacy", "mode": "graceful", "head1_delay_s": 10, "nodes_mounted": 9,
     "nodes_total": 10, "result": "FAIL (interrupted by operator, evidence from journal)",
     "detail": "Run 3 of the legacy series: Compute-2 gave up after 145 s waiting for the MGS and stayed unmounted; OST0002 mounted, OST0003 missing; no retry in the legacy unit.",
     "log": "stability/logs/coldboot_20261001T160755.log"},
]


def result_files(pattern):
    out = []
    for f in sorted(glob.glob(os.path.join(SRC, pattern))):
        d = json.load(open(f))
        d.pop("health_after", None)
        d["file"] = "stability/" + os.path.basename(f)
        out.append(d)
    return out


NOTES = {
    "nodeloss": {
        "Rocky-Compute-5": "Mirrors were never resynced before the loss: reads with the node down failed (ok=0, err=11), resync found stale=12 (every written file); the in-flight write and a new-file create each blocked until the node returned (about 950 s). No data lost.",
        "Rocky-Head-2": "Test directory on MDT1 (new directories alternate between MDT0 and MDT1): in-flight write blocked 240 s (timeout), 2 of 53 creates failed after 60 s. 25/25 files intact.",
        "Rocky-Head-1": "MGS + MDT0 lost: in-flight write blocked 562 s; client EVICTED by MDT0 on return (abort_recov); first 2 read-backs failed with I/O errors, 26 ok; no corruption.",
    },
}


def soak_data():
    rows = rd("soak.csv")
    if not rows:
        return None
    MB = 8.388608 / 1000   # MiB/s -> Gbit/s (fio KiB/s / 1024 = MiB/s)
    rounds = [{"round": int(r["round"]), "ts": r["ts"], "nodes_ok": int(r["nodes_ok"]),
               "read_mib_s": int(r["read_MBps"]), "write_mib_s": int(r["write_MBps"]),
               "read_gbit_s": round(int(r["read_MBps"]) * MB, 3), "write_gbit_s": round(int(r["write_MBps"]) * MB, 3),
               "combined_gbit_s": round((int(r["read_MBps"]) + int(r["write_MBps"])) * MB, 3),
               "io_errors": int(r["io_errors"]), "new_dmesg_errors": int(r["new_dmesg_errors"]),
               "new_ib_errors": int(r["new_ib_errors"]), "osts": int(r["osts"]), "healthy": r["healthy"] == "True"}
              for r in rows]
    summary = json.load(open(os.path.join(SRC, "soak_summary.json"))) if os.path.exists(os.path.join(SRC, "soak_summary.json")) else None
    return {"description": "6 h soak 2026-10-15: mixed 70/30 random fio, 1 MiB direct, iodepth 8, 2 jobs, 2 GiB files per node, 5 min fio per round on all 8 computes",
            "unit_note": "MiB/s as recorded; Gbit/s = MiB/s x 8.388608 / 1000", "summary": summary, "rounds": rounds}


def main():
    nl = result_files("nodeloss_*.json")
    for n in nl:
        n["interpretation"] = NOTES["nodeloss"].get(n.get("victim"))
        n.pop("fail_list", None)
    rf = result_files("readfail_*.json")
    for r in rf:
        r["scenario"] = ("OSTs of the victim deactivated on MDS+client 38 s into the outage" if r.get("deactivate")
                         else "no manual action")
    rb = [{"run": int(r["run"]), "ts": r["ts"], "playbook_rc": int(r["playbook_rc"]), "elapsed_s": int(r["elapsed_s"]),
           "healthy": r["healthy"] == "True", "problems": r["problems"],
           "sm_layout": "OpenSM on all 10 nodes, equal priority" if r["ts"] < SM_FIXED else "OpenSM on heads only, Head-1 prio 14 / Head-2 prio 13"}
          for r in rd("rebootloop.csv")]
    data = {
        "metadata": {
            "description": "Stability tests of the Lustre 2.17.0 cluster (RDMA/o2ib, FLR), 2026-10-01 and 2026-10-08. Source of truth: UJEP-LAB/benchmarks/stability; tooling UJEP-LAB/tools/stability.py; regenerate with tools/make_stability_data.py.",
            "cluster": "10 nodes: 2 heads (MGS+MDT0 on Head-1, MDT1 on Head-2) + 8 computes (16 OSTs)",
            "kernel": "5.14.0-611.13.1_lustre.el9.x86_64 (Rocky Linux 9.7)",
            "units": "seconds unless noted; cold-boot times relative to the first IPMI power-on command",
            "scripts": {"legacy": "lustre-startup with iteration-counted timeouts: real MGS wait limit about 145-170 s, LNET wait about 11 s, no retry",
                        "fixed": "lustre-startup with $SECONDS deadlines (MGS 600 s, LNET 120 s) and Restart=on-failure"},
            "caveats": [
                "Small number of runs per condition; not statistics.",
                "Per-node times use node clocks corrected against the controller (+-1-2 s).",
                "Restart=on-failure retry path was not exercised.",
                "Hard power-off cold boots are not representative of production (two power lines, 2 UPS each, scheduled shutdowns).",
                "Node-loss and readfail runs used 256 MB dd files pinned with lfs mirror create; the hung operations are as long as the outage, which differs between runs (see per-run outage_s / t_back - t_kill)."]},
        "cold_boot_runs": first_coarse() + EXTRA_COLD + cold_boot_runs(),
        "node_loss_runs": nl,
        "read_failover_runs": rf,
        "rolling_reboot_runs": rb,
        "soak": soak_data(),
        "findings": [
            {"id": "F1", "title": "Legacy startup script times out early", "result": "MGS wait limit is about 145-170 s instead of 300 s (loop counts iterations, not seconds); LNET wait about 11 s instead of 60 s."},
            {"id": "F2", "title": "Head-1 (MGS) is always the last node up", "result": "Reaches the OS about 190 s after its own power-on versus about 90 s for other blades."},
            {"id": "F3", "title": "Startup fix verified", "result": "With wall-clock deadlines computes waited up to 344 s for the MGS (Head-1 held 240 s) and all 10 nodes mounted with 0 fatal retries."},
            {"id": "F4", "title": "Data integrity across unclean power-off", "result": "40/40 files sha256-identical after each of 2 hard power-offs of all 10 nodes."},
            {"id": "F5", "title": "OST recovery window after unclean stop", "result": "After a hard stop of all nodes only 2 of 16 OSTs were visible for another 275-292 s (5:00 recovery window; MDT with abort_recov is denied as new client). Graceful shutdown: pool complete immediately. Accepted (scheduled shutdowns)."},
            {"id": "F6", "title": "Kernel update would break the boot", "result": "dnf update installed Rocky 9.8 kernel on Compute-2, UPDATEDEFAULT=yes made it the default; no Lustre modules on boot. Fixed: kernel* excluded, UPDATEDEFAULT=no."},
            {"id": "F7", "title": "FLR is delayed mirroring", "result": "Writes land on one mirror; the other stays stale until lfs mirror resync (stale=12/12 and 20/20 right after writing). Without resync, data on a lost node is unavailable until it returns."},
            {"id": "F8", "title": "Reads fail over automatically when mirrors are in sync", "result": "Node loss with resynced mirrors: 246-292 reads ok during a 240 s outage, longest stall 3-41 s, 0 failures after return."},
            {"id": "F9", "title": "Writes and creates block on a dead OSS unless its OSTs are deactivated", "result": "Without action: no write completed during the outage, one create blocked 344 s. With the dead OSTs deactivated on MDS+client: 21 writes and 180 creates ok, only the in-flight operations failed (51-57 s); 38/38 written files intact."},
            {"id": "F10", "title": "Metadata is not redundant", "result": "New directories alternate between MDT0 and MDT1; losing a head stalls the directories on its MDT (write 240 s, creates failed after 60 s). Head-1 loss also evicts clients on return (abort_recov): first 2 read-backs I/O errors."},
            {"id": "F11", "title": "Rolling reboot can leave a node's IB port in INIT", "result": "Loop 1 of 2 passed (10/10). Loop 2: Head-2's port stayed INIT about 10 min (no SM activated it); both head OpenSMs STANDBY; OpenSM runs on all 10 nodes with equal priority. Recovered by restarting OpenSM on Head-1."},
            {"id": "F12", "title": "Deterministic subnet-manager layout fixes the rolling reboot", "result": "OpenSM only on the heads (Head-1 priority 14, Head-2 13), off on the computes; reboot.yml waits for the IB port ACTIVE. Rolling reboot repeated: 3 of 3 loops passed (about 1520-1540 s each), pool HEALTHY. Small sample; cause not fully proven (why the previous master did not activate Head-2's port is unexplained)."},
            {"id": "F14", "title": "6-hour soak: no errors, no drift", "result": "36 rounds, 8/8 nodes and 16 OSTs healthy every round, 0 I/O / dmesg / IB errors. Combined throughput plateau 23.07 +- 0.13 Gbit/s (CV 0.57%) after a 7.3% step down in rounds 1-5; first half vs second half of the plateau differs by 0.07%. About 28.5 TiB moved (estimate)."},
            {"id": "F13", "title": "Graceful shutdown order was wrong", "result": "The old shutdown.yml powered the heads off first; the computes' umount of /mnt/lustre then hung more than 6 minutes against dead servers (serial play, 7 more nodes pending). New order: clients unmount everywhere, computes power off together, then Head-2, then Head-1 (MGS + MDT0) last. Not yet run end to end."}],
        "tests_planned": [
            {"test": "24 h soak (the 6 h soak is done)", "requirement": "R4", "status": "not run"},
            {"test": "HPL (LINPACK) GFLOPS on 1/2/4/8 computes and all 10 nodes", "requirement": "-", "status": "prepared, not run (benchmarks/hpl)"},
            {"test": "periodic mirror resync + automatic OST deactivation (watchdog), then repeat node loss", "requirement": "R5", "status": "not run"},
            {"test": "retry path, Head-1 held 600 s", "requirement": "R4", "status": "not run"},
            {"test": "cache-bypassed fio matrix, repeated, 1/2/4/8 clients", "requirement": "R3", "status": "not run"},
            {"test": "VM layer: live migration, node loss with VMs", "requirement": "R8", "status": "blocked (no KVM hosts yet)"}]}
    data["findings"].sort(key=lambda f: int(f["id"][1:]))
    os.makedirs(os.path.join(DEST, "stability", "logs"), exist_ok=True)
    with open(os.path.join(DEST, "stability_data.json"), "w") as f:
        json.dump(data, f, indent=1)
    for pat in ("*.csv", "NEXT.md", "README.md", "*.json"):
        for f in glob.glob(os.path.join(SRC, pat)):
            shutil.copy(f, os.path.join(DEST, "stability"))
    for f in glob.glob(os.path.join(SRC, "logs", "*.log")):
        shutil.copy(f, os.path.join(DEST, "stability", "logs"))
    print(f"cold_boot_runs={len(data['cold_boot_runs'])} node_loss={len(nl)} read_failover={len(rf)} rolling_reboot={len(rb)} findings={len(data['findings'])} -> {DEST}")


if __name__ == "__main__":
    main()
