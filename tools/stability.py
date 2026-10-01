#!/usr/bin/env python3
"""Stability tests for the Lustre cluster. Run through `just` (see justfile).

Every command tees its whole console output to
benchmarks/stability/logs/<command>_<timestamp>.log and writes a structured
result (CSV row(s) / JSON) next to the other results, so a run can be parsed
later without having seen the terminal. The last line of each log is
`RESULT_JSON {...}`.

Commands:
  health                     snapshot: kernel, unit, mount, OSTs, NIDs, dmesg errors, IB counters
  prep                       install fio on computes, create /mnt/lustre/stab
  coldboot [--runs N] [--hard] [--head1-delay S] [--integrity N]
  rebootloop [--runs N] [--limit X]
  nodeloss [--victim NODE] [--files N] [--pre S] [--down S]
  soak [--hours H] [--round S]

Clock note: per-node times come from node clocks, corrected with an offset
measured against this machine at collection time (+-1-2 s).
"""
import argparse, csv, json, os, re, statistics, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", "opennebula"))
OUT = os.path.normpath(os.path.join(HERE, "..", "benchmarks", "stability"))
LOGDIR = os.environ.get("STAB_LOGDIR") or os.path.join(OUT, "logs")
STAB = "/mnt/lustre/stab"      # test data on Lustre
LOCAL = "/var/tmp/stab"        # per-node scratch (survives reboot)
EXPECT_OSTS, EXPECT_MDTS = 16, 2
LOG = None


# ---------------------------------------------------------------- logging
class Log:
    def __init__(self, name):
        os.makedirs(LOGDIR, exist_ok=True)
        self.ts = time.strftime("%Y%m%dT%H%M%S")
        self.path = os.path.join(LOGDIR, f"{name}_{self.ts}.log")
        self.f = open(self.path, "w", buffering=1)
        self.say(f"# {name} started {time.strftime('%Y-%m-%dT%H:%M:%S%z')} argv={sys.argv}")

    def say(self, msg=""):
        print(msg, flush=True)
        self.f.write(msg + "\n")

    def raw(self, msg):  # log only (raw tool output)
        self.f.write(msg.rstrip("\n") + "\n")

    def result(self, obj):
        self.f.write("RESULT_JSON " + json.dumps(obj, default=str) + "\n")
        self.say(f"\nlog: {self.path}")


def say(msg=""):
    LOG.say(msg)


# ---------------------------------------------------------------- ansible helpers
def run(cmd, timeout=None, env=None, stream=False):
    e = dict(os.environ)
    e.update(env or {})
    if not stream:
        return subprocess.run(cmd, cwd=PROJECT, text=True, capture_output=True, timeout=timeout, env=e)
    p = subprocess.Popen(cmd, cwd=PROJECT, text=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=e)
    out = []
    for line in p.stdout:
        say(line.rstrip("\n"))
        out.append(line)
    p.wait()
    return subprocess.CompletedProcess(cmd, p.returncode, "".join(out), "")


def playbook(path, extra=None, limit=None):
    cmd = ["ansible-playbook", path]
    if limit:
        cmd += ["--limit", limit]
    if extra:
        cmd += ["-e", json.dumps(extra)]
    say(f"$ {' '.join(cmd)}")
    return run(cmd, stream=True).returncode


def adhoc(pattern, cmd, timeout=180, become=True):
    """Run a shell command on hosts via ansible; returns {host: {rc, stdout, stderr, unreachable}}."""
    args = ["ansible", pattern, "-T", "15", "-m", "shell", "-a", cmd] + (["-b"] if become else [])
    LOG.raw(f"$ ansible {pattern} -m shell -a {cmd!r}")
    try:
        r = run(args, timeout=timeout + 30,
                env={"ANSIBLE_STDOUT_CALLBACK": "json", "ANSIBLE_LOAD_CALLBACK_PLUGINS": "1"})
    except subprocess.TimeoutExpired:
        LOG.raw("!! adhoc timed out")
        return {}
    i = r.stdout.find("{")
    try:
        data = json.loads(r.stdout[i:])
    except Exception:
        LOG.raw(f"!! adhoc unparsable output: rc={r.returncode} stdout={r.stdout[:500]!r} stderr={r.stderr[:500]!r}")
        return {}
    hosts = {}
    for play in data.get("plays", []):
        for task in play.get("tasks", []):
            for h, v in task.get("hosts", {}).items():
                hosts[h] = v
    for h, v in sorted(hosts.items()):
        LOG.raw(f"  [{h}] rc={v.get('rc')} unreachable={v.get('unreachable', False)} "
                f"stdout={str(v.get('stdout', ''))[:2000]!r}")
    return hosts


def good(v):
    return bool(v) and not v.get("unreachable") and v.get("rc") == 0


def kv(text):
    d = {}
    for line in (text or "").splitlines():
        if "=" in line:
            k, _, val = line.partition("=")
            d[k.strip()] = val.strip()
    return d


def inventory():
    r = run(["ansible-inventory", "--list"])
    inv = json.loads(r.stdout)
    hv = inv["_meta"]["hostvars"]
    heads = sorted(inv["controller"]["hosts"])
    computes = sorted(inv["compute"]["hosts"], key=lambda h: int(h.rsplit("-", 1)[1]))
    ips = {h: hv[h]["ansible_host"] for h in heads + computes}
    return heads, computes, ips


def pingable(ip):
    return subprocess.run(["ping", "-c1", "-W1", ip], capture_output=True).returncode == 0


def copy_file(host, text, dest, mode="0755"):
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as t:
        t.write(text)
        src = t.name
    try:
        args = ["ansible", host, "-b", "-m", "copy", "-a", f"src={src} dest={dest} mode={mode}"]
        r = run(args, env={"ANSIBLE_STDOUT_CALLBACK": "json", "ANSIBLE_LOAD_CALLBACK_PLUGINS": "1"})
        return '"failed": true' not in r.stdout and "UNREACHABLE" not in r.stdout
    finally:
        os.unlink(src)


def power(nodes, state):
    return playbook("playbooks/common/power.yml", {"nodes": list(nodes), "power_state": state}) == 0


# ---------------------------------------------------------------- health
HEALTH_CMD = r"""echo "KERNEL=$(uname -r)"; echo "UNIT=$(systemctl is-active lustre-startup)";
mountpoint -q /mnt/lustre && echo MOUNT=yes || echo MOUNT=no;
echo "OSTS=$(lctl dl 2>/dev/null | grep -c obdfilter)"; echo "NID=$(lctl list_nids 2>/dev/null | grep o2ib)";
echo "DMESG_ERR=$(dmesg 2>/dev/null | grep -c -E 'LustreError|LNetError|Call Trace|BUG:|soft lockup')";
for f in symbol_error link_downed port_rcv_errors port_xmit_discards link_error_recovery; do
  echo "IB_$f=$(cat /sys/class/infiniband/*/ports/1/counters/$f 2>/dev/null | head -1)"; done"""

LFSDF_CMD = "timeout 90 lfs df 2>&1"


def parse_lfsdf(text):
    n_ost = len(re.findall(r"OST[0-9a-f]{4}_UUID", text))
    n_mdt = len(re.findall(r"MDT[0-9a-f]{4}_UUID", text))
    bad = [l for l in text.splitlines()
           if re.search(r"inactive|temporarily unavailable|Cannot send|No such device", l)]
    m = re.search(r"filesystem_summary:\s+(\S+)\s+(\S+)\s+(\S+)", text)
    return {"osts": n_ost, "mdts": n_mdt, "bad": len(bad), "size": m.group(1) if m else None}


def health(label="health", heads=None, computes=None):
    heads, computes, _ = (heads, computes, None) if heads else inventory()
    res = adhoc("cluster", HEALTH_CMD)
    df = adhoc(heads[0], LFSDF_CMD, timeout=120).get(heads[0], {})
    nodes, problems = {}, []
    for h in heads + computes:
        v = res.get(h)
        if not good(v):
            nodes[h] = {"reachable": False}
            problems.append(f"{h}: unreachable")
            continue
        d = kv(v["stdout"])
        d["reachable"] = True
        nodes[h] = d
        want = "2" if h in computes else "0"
        if "_lustre" not in d.get("KERNEL", ""):
            problems.append(f"{h}: kernel {d.get('KERNEL')}")
        if d.get("UNIT") != "active":
            problems.append(f"{h}: lustre-startup {d.get('UNIT')}")
        if d.get("MOUNT") != "yes":
            problems.append(f"{h}: /mnt/lustre not mounted")
        if d.get("OSTS") != want:
            problems.append(f"{h}: serves {d.get('OSTS')} OSTs, expected {want}")
    fs = parse_lfsdf(df.get("stdout", "")) if good(df) else {"osts": 0, "mdts": 0, "bad": 0, "size": None}
    if fs["osts"] != EXPECT_OSTS or fs["mdts"] != EXPECT_MDTS or fs["bad"]:
        problems.append(f"lfs df: {fs['osts']} OST / {fs['mdts']} MDT / {fs['bad']} inactive")
    say(f"--- {label}: {'HEALTHY' if not problems else 'PROBLEMS'}  "
        f"(lfs df: {fs['osts']} OST, {fs['mdts']} MDT, {fs['size']})")
    for h in heads + computes:
        d = nodes[h]
        if d.get("reachable"):
            say(f"  {h:16} kernel={d['KERNEL'][:26]:26} unit={d['UNIT']:7} mount={d['MOUNT']:3} "
                f"osts={d['OSTS']} dmesg_err={d['DMESG_ERR']} nid={d['NID']}")
        else:
            say(f"  {h:16} UNREACHABLE")
    for p in problems:
        say(f"  ! {p}")
    return {"healthy": not problems, "problems": problems, "fs": fs, "nodes": nodes}


def settle(heads, timeout=300, every=15):
    """After all nodes report mounted, wait for `lfs df` (from Head-1) to show every OST and MDT.
    Returns (seconds until complete or None, last counts, history). An OST that is mounted on its node
    can still be missing here while the MDS has not (re)connected to it (seen after hard power-off)."""
    t0, hist = time.time(), []
    while True:
        df = adhoc(heads[0], LFSDF_CMD, timeout=120).get(heads[0], {})
        fs = parse_lfsdf(df.get("stdout", "")) if good(df) else {"osts": 0, "mdts": 0, "bad": 0}
        el = round(time.time() - t0)
        seen = sorted(set(int(x, 16) for x in re.findall(r"OST([0-9a-f]{4})_UUID", df.get("stdout", ""))))
        hist.append((el, fs["osts"], fs["mdts"], fs["bad"]))
        say(f"  settle +{el}s: {fs['osts']} OST / {fs['mdts']} MDT / {fs['bad']} inactive"
            + ("" if fs["osts"] == EXPECT_OSTS else f"  missing OSTs {sorted(set(range(EXPECT_OSTS)) - set(seen))}"))
        if fs["osts"] == EXPECT_OSTS and fs["mdts"] == EXPECT_MDTS and not fs["bad"]:
            return el, fs, hist
        if time.time() - t0 > timeout:
            return None, fs, hist
        time.sleep(every)


# ---------------------------------------------------------------- client scripts
WRITER = r"""#!/bin/bash
# usage: writer.sh DIR CHUNK MAXFILES DD_TIMEOUT   (files must be pre-created in DIR as w_NNNNN)
D=$1; CHUNK=$2; MAX=$3; TMO=$4
mkdir -p /var/tmp/stab; rm -f /var/tmp/stab/ok_list /var/tmp/stab/fail_list
i=0
while [ $i -lt $MAX ] && [ ! -e /var/tmp/stab/stop ]; do
  f=$D/w_$(printf %05d $i)
  s=$(date +%s.%N)
  timeout $TMO dd if=$CHUNK of=$f bs=1M oflag=direct conv=notrunc status=none 2>/var/tmp/stab/dd.err
  rc=$?
  e=$(date +%s.%N)
  if [ $rc -eq 0 ]; then echo $f >> /var/tmp/stab/ok_list; else echo $f >> /var/tmp/stab/fail_list; fi
  echo "W $s $e $f dd_rc=$rc"
  i=$((i+1))
done
echo "W DONE $(date +%s.%N)"
"""

PROBE = r"""#!/bin/bash
# metadata probe: create a new file every second, log latency / rc
D=$1; n=0
while [ ! -e /var/tmp/stab/stop ]; do
  s=$(date +%s.%N)
  timeout 60 touch $D/probe_$n >/dev/null 2>&1; rc=$?
  e=$(date +%s.%N)
  echo "P $s $e rc=$rc"
  n=$((n+1)); sleep 1
done
echo "P DONE $(date +%s.%N)"
"""

VERIFY = r"""#!/bin/bash
# usage: verify.sh LISTFILE REFSHA   -> one line per file, then a SUMMARY line
REF=$2; ok=0; bad=0; err=0; s0=$(date +%s)
while read -r f; do
  timeout 600 dd if=$f bs=1M iflag=direct status=none 2>/dev/null | sha256sum > /var/tmp/stab/v.sum
  rc=${PIPESTATUS[0]}
  h=$(cut -d' ' -f1 /var/tmp/stab/v.sum)
  if [ $rc -ne 0 ]; then err=$((err+1)); echo "V ERR $f rc=$rc"
  elif [ "$h" = "$REF" ]; then ok=$((ok+1))
  else bad=$((bad+1)); echo "V BAD $f"; fi
done < "$1"
echo "V SUMMARY ok=$ok bad=$bad err=$err seconds=$(( $(date +%s) - s0 ))"
"""

RESYNC = r"""#!/bin/bash
# usage: resync.sh DIR -> resync stale mirrors, then verify mirrors agree
D=$1; stale=0; fixed=0; rsfail=0; s0=$(date +%s)
for f in $(ls $D/w_* 2>/dev/null | sort); do
  if lfs getstripe $f 2>/dev/null | grep -q stale; then
    stale=$((stale+1))
    if timeout 600 lfs mirror resync $f >/dev/null 2>&1; then fixed=$((fixed+1)); else rsfail=$((rsfail+1)); echo "R FAIL $f"; fi
  fi
done
echo "R RESYNC stale=$stale resynced=$fixed failed=$rsfail seconds=$(( $(date +%s) - s0 ))"
mv=0; mm=0; s1=$(date +%s)
for f in $(cat /var/tmp/stab/ok_list 2>/dev/null); do
  if timeout 600 lfs mirror verify -v $f >/dev/null 2>&1; then mv=$((mv+1)); else mm=$((mm+1)); echo "R MIRROR-MISMATCH $f"; fi
done
echo "R MIRRORVERIFY ok=$mv mismatch=$mm seconds=$(( $(date +%s) - s1 ))"
"""


def push_scripts(client):
    ok = all([copy_file(client, WRITER, f"{LOCAL}/writer.sh"), copy_file(client, PROBE, f"{LOCAL}/probe.sh"),
              copy_file(client, VERIFY, f"{LOCAL}/verify.sh"), copy_file(client, RESYNC, f"{LOCAL}/resync.sh")])
    return ok


def client_prep(client, subdir):
    """scratch dir, 256 MB random chunk (kept), test dir; returns (ref sha, clock offset)."""
    cmd = (f"mkdir -p {LOCAL} && rm -f {LOCAL}/stop && "
           f"[ -f {LOCAL}/chunk ] || dd if=/dev/urandom of={LOCAL}/chunk bs=1M count=256 status=none; "
           f"mkdir -p {STAB}/{subdir} && chmod 777 {STAB} {STAB}/{subdir}; "
           f"echo SHA=$(sha256sum {LOCAL}/chunk | cut -d' ' -f1); echo NOW=$(date +%s.%N)")
    t = time.time()
    r = adhoc(client, cmd).get(client)
    t = (t + time.time()) / 2
    if not good(r):
        return None, None
    d = kv(r["stdout"])
    return d["SHA"], float(d["NOW"]) - t


def bg(client, script_cmd, logfile):
    """Start a script detached on the client, its console going to `logfile`."""
    return adhoc(client, f"setsid nohup {script_cmd} > {logfile} 2>&1 < /dev/null & echo started").get(client)


def fetch(client, path):
    r = adhoc(client, f"cat {path} 2>/dev/null").get(client)
    return r["stdout"] if good(r) else ""


# ---------------------------------------------------------------- analysis (pure functions)
def parse_writer(text, offset=0.0):
    rows = []
    for line in text.splitlines():
        m = re.match(r"W (\d+\.\d+) (\d+\.\d+) (\S+) dd_rc=(\d+)", line)
        if m:
            rows.append({"start": float(m[1]) - offset, "end": float(m[2]) - offset,
                         "file": m[3], "rc": int(m[4])})
    return rows


def parse_probe(text, offset=0.0):
    rows = []
    for line in text.splitlines():
        m = re.match(r"P (\d+\.\d+) (\d+\.\d+) rc=(\d+)", line)
        if m:
            rows.append({"start": float(m[1]) - offset, "end": float(m[2]) - offset, "rc": int(m[3])})
    return rows


def analyse_io(writes, probes, t_kill, t_back):
    """Stall / failure numbers around a node loss. Times are controller-clock epochs."""
    done = [w for w in writes if w["rc"] == 0]
    pre = [w["end"] - w["start"] for w in done if w["end"] < t_kill]
    med = statistics.median(pre) if pre else None
    ends = sorted(w["end"] for w in writes)
    gaps = [(b - a, a) for a, b in zip(ends, ends[1:])]
    max_gap = max(gaps) if gaps else (0, None)
    slow = [w for w in done if med and w["end"] >= t_kill and (w["end"] - w["start"]) > 3 * med]
    pl = [p["end"] - p["start"] for p in probes]
    return {
        "files_written_ok": len(done), "files_write_failed": len([w for w in writes if w["rc"] != 0]),
        "median_file_s_before_loss": med,
        "longest_gap_between_completions_s": round(max_gap[0], 1),
        "longest_gap_started_after_kill_s": round(max_gap[1] - t_kill, 1) if max_gap[1] else None,
        "files_slow_after_loss": len(slow),
        "slowest_file_s": round(max((w["end"] - w["start"] for w in writes), default=0), 1),
        "probe_total": len(probes), "probe_failed": len([p for p in probes if p["rc"] != 0]),
        "probe_max_latency_s": round(max(pl), 1) if pl else None,
        "probe_median_latency_s": round(statistics.median(pl), 3) if pl else None,
        "t_kill": t_kill, "t_back": t_back,
    }


def parse_boot(stdout, ctrl_now):
    """Boot/start timings from a node's HEALTH-style collection, in controller-clock epochs."""
    d = kv(stdout)
    off = float(d["NOW"]) - ctrl_now
    ev = {"begin": None, "wait": None, "reach": None, "complete": None, "fatal": 0}
    for line in stdout.splitlines():
        m = re.match(r"^(\d+\.\d+)\s.*?(startup begin|Waiting for MGS|MGS reachable|startup complete|FATAL)", line)
        if not m:
            continue
        t, what = float(m[1]) - off, m[2]
        if what == "startup begin" and ev["begin"] is None:
            ev["begin"] = t
        elif what == "Waiting for MGS" and ev["wait"] is None:
            ev["wait"] = t
        elif what == "MGS reachable" and ev["reach"] is None:
            ev["reach"] = t
        elif what == "startup complete":
            ev["complete"] = t
        elif what == "FATAL":
            ev["fatal"] += 1
    ev["boot"] = float(d["BTIME"]) - off
    return ev


BOOT_CMD = (r"echo NOW=$(date +%s.%N); echo BTIME=$(awk '/^btime/{print $2}' /proc/stat); "
            r"journalctl -u lustre-startup -b -o short-unix --no-pager 2>/dev/null | "
            r"grep -E 'startup begin|Waiting for MGS|MGS reachable|startup complete|FATAL'")


def collect_boot(nodes):
    t = time.time()
    res = adhoc(",".join(nodes), BOOT_CMD)
    t = (t + time.time()) / 2
    return {h: parse_boot(v["stdout"], t) for h, v in res.items() if good(v)}


# ---------------------------------------------------------------- mount polling
def poll_mounts(pattern="cluster"):
    res = adhoc(pattern, "mountpoint -q /mnt/lustre", timeout=60)
    st = {}
    for h, v in res.items():
        st[h] = "down" if v.get("unreachable") else ("mounted" if v.get("rc") == 0 else "up")
    return st


def wait_mounted(nodes, t0, timeout, every=20):
    """Poll until all `nodes` mounted; returns ({node: first_up_s}, {node: first_mounted_s}, timed_out)."""
    up, mnt = {}, {}
    while time.time() - t0 < timeout and len(mnt) < len(nodes):
        for h, s in poll_mounts(",".join(nodes)).items():
            now = round(time.time() - t0)
            if s in ("up", "mounted"):
                up.setdefault(h, now)
            if s == "mounted":
                mnt.setdefault(h, now)
        say(f"  t={round(time.time() - t0):5d}s  reachable {len(up)}/{len(nodes)}  mounted {len(mnt)}/{len(nodes)}")
        if len(mnt) < len(nodes):
            time.sleep(every)
    return up, mnt, len(mnt) < len(nodes)


def write_csv(name, header, rows):
    path = os.path.join(OUT, name)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerows(rows)
    return path


# ---------------------------------------------------------------- commands
def cmd_health(a):
    heads, computes, _ = inventory()
    r = health("health", heads, computes)
    LOG.result(r)
    return 0 if r["healthy"] else 1


def cmd_prep(a):
    heads, computes, _ = inventory()
    r = adhoc("compute", "dnf install -y fio >/dev/null 2>&1; fio --version", timeout=600)
    for h in computes:
        say(f"  {h}: fio {r.get(h, {}).get('stdout', '?').strip()}")
    r = adhoc(heads[0], f"mkdir -p {STAB} && chmod 777 {STAB} && echo ok")
    say(f"  {STAB}: {r.get(heads[0], {}).get('stdout', '?').strip()}")
    LOG.result({"prep": "done"})
    return 0


def cmd_coldboot(a):
    heads, computes, ips = inventory()
    nodes = heads + computes
    head1 = heads[0]
    allr = []
    for n in range(1, a.runs + 1):
        started = time.strftime("%Y-%m-%dT%H:%M:%S")
        mode = "hard" if a.hard else "graceful"
        say(f"\n=== run {n}/{a.runs} ({mode} shutdown, head1_delay={a.head1_delay}s, integrity={a.integrity})")
        client, ref = computes[0], None
        if a.integrity:
            ref, _ = client_prep(client, f"integrity_{LOG.ts}")
            n_files = a.integrity
            say(f"  writing {n_files} x 256 MB integrity files from {client}")
            cmd = (f"cd {STAB}/integrity_{LOG.ts} && rm -f w_*; for i in $(seq -w 0 {n_files - 1}); do "
                   f"dd if={LOCAL}/chunk of=w_$i bs=1M oflag=direct status=none || echo WRITEFAIL $i; done; "
                   f"ls w_* | sed 's#^#{STAB}/integrity_{LOG.ts}/#' > {LOCAL}/int_list; echo files=$(ls w_* | wc -l); sync")
            r = adhoc(client, cmd, timeout=1800).get(client, {})
            say(f"  {r.get('stdout', '').strip()}")
            push_scripts(client)
        if a.hard:
            say("  power OFF all (hard)")
            power(nodes, "off")
        else:
            playbook("playbooks/common/shutdown.yml")
        t = time.time()
        while any(pingable(ip) for ip in ips.values()):
            if time.time() - t > 600:
                say("!! nodes still answering ping 10 min after shutdown; aborting")
                LOG.result({"error": "shutdown did not complete"})
                return 2
            time.sleep(5)
        time.sleep(20)
        t_first = time.time()
        if a.head1_delay:
            power([h for h in nodes if h != head1], "on")
            say(f"  holding {head1} off for {a.head1_delay}s")
            time.sleep(max(0, a.head1_delay - (time.time() - t_first)))
            power([head1], "on")
        else:
            power(nodes, "on")
        t_powered = time.time() - t_first
        say(f"  power-on commands done {t_powered:.0f}s after the first one")
        up, mnt, timed_out = wait_mounted(nodes, t_first, a.timeout)
        info = collect_boot(nodes)
        rows = []
        say(f"\n  {'node':16} {'boot_s':>7} {'begin_s':>8} {'mgswait_s':>9} {'mounted_s':>9} {'fatal':>5}")
        for h in nodes:
            e = info.get(h, {})
            rel = lambda x: round(x - t_first) if x else ""
            mw = round(e["reach"] - e["wait"]) if e.get("reach") and e.get("wait") else ""
            ms = rel(e.get("complete")) if e else ""
            rows.append([n, started, mode, a.head1_delay, h, rel(e.get("boot")), rel(e.get("begin")), mw,
                         ms, mnt.get(h, ""), e.get("fatal", ""), "yes" if h in mnt else "NO"])
            say(f"  {h:16} {str(rows[-1][5]):>7} {str(rows[-1][6]):>8} {str(mw):>9} {str(ms):>9} {str(e.get('fatal', '')):>5}"
                f"{'' if h in mnt else '   NEVER MOUNTED'}")
        write_csv("coldboot_v2.csv", ["run", "started", "mode", "head1_delay_s", "node", "boot_s", "unit_begin_s",
                                      "mgs_wait_s", "unit_complete_s", "poll_mounted_s", "fatal_retries", "mounted"], rows)
        settle_s, _, settle_hist = settle(heads)
        say(f"  filesystem fully visible (16 OST + 2 MDT) after {settle_s}s" if settle_s is not None
            else "  !! filesystem NOT fully visible within 300 s of all nodes mounted")
        write_csv("coldboot_settle.csv", ["started", "run", "mode", "head1_delay_s", "settle_s"],
                  [[started, n, mode, a.head1_delay, "" if settle_s is None else settle_s]])
        h_ = health(f"after run {n}", heads, computes)
        res = {"run": n, "mode": mode, "head1_delay": a.head1_delay, "mounted": len(mnt), "of": len(nodes),
               "timed_out": timed_out, "never": [h for h in nodes if h not in mnt], "healthy": h_["healthy"],
               "problems": h_["problems"], "settle_s": settle_s, "settle_history": settle_hist, "fatal_total": sum(e.get("fatal", 0) for e in info.values())}
        if a.integrity:
            r = adhoc(client, f"{LOCAL}/verify.sh {LOCAL}/int_list {ref}", timeout=1800).get(client, {})
            summ = [l for l in r.get("stdout", "").splitlines() if l.startswith("V ")]
            for l in summ:
                say("  " + l)
            res["integrity"] = summ[-1] if summ else "no output"
        say(f"=== run {n}: {len(mnt)}/{len(nodes)} mounted" + (f"; NEVER: {res['never']}" if res["never"] else ""))
        allr.append(res)
    LOG.result({"command": "coldboot", "runs": allr})
    return 0 if all(r["mounted"] == r["of"] and r["healthy"] for r in allr) else 1


def cmd_rebootloop(a):
    heads, computes, _ = inventory()
    allr = []
    for n in range(1, a.runs + 1):
        say(f"\n=== reboot run {n}/{a.runs}")
        t = time.time()
        rc = playbook("playbooks/common/reboot.yml", limit=a.limit)
        el = round(time.time() - t)
        h = health(f"after reboot run {n}", heads, computes)
        write_csv("rebootloop.csv", ["run", "ts", "limit", "playbook_rc", "elapsed_s", "healthy", "problems"],
                  [[n, time.strftime("%Y-%m-%dT%H:%M:%S"), a.limit or "all", rc, el, h["healthy"], "; ".join(h["problems"])]])
        allr.append({"run": n, "rc": rc, "elapsed_s": el, "healthy": h["healthy"], "problems": h["problems"]})
        if rc != 0:
            say("!! reboot playbook failed; stopping")
            break
    LOG.result({"command": "rebootloop", "runs": allr})
    return 0 if all(r["rc"] == 0 and r["healthy"] for r in allr) else 1


def discover_osts(computes):
    res = adhoc(",".join(computes), """lctl dl | awk '$3=="obdfilter"{print $4}'""")
    m = {}
    for h, v in res.items():
        if good(v):
            m[h] = sorted(int(x.split("OST")[-1], 16) for x in v["stdout"].split())
    return m


def parse_stripe_osts(text):
    return sorted(set(int(x) for x in re.findall(r"l_ost_idx:\s*(\d+)", text)))


def cmd_nodeloss(a):
    heads, computes, ips = inventory()
    victim = a.victim
    is_head = victim in heads
    cands = [c for c in computes if c != victim]
    client, partner = cands[0], cands[-1]
    sub = f"nodeloss_{LOG.ts}"
    say(f"victim={victim} ({'head' if is_head else 'compute'}) client={client} partner={partner}")
    h0 = health("before", heads, computes)
    if not h0["healthy"] and not a.force:
        say("!! cluster not healthy; fix first or pass --force")
        LOG.result({"error": "unhealthy", "problems": h0["problems"]})
        return 2
    ost = discover_osts(computes)
    say(f"OSTs per compute: {ost}")
    if not is_head and not (ost.get(victim) and ost.get(partner)):
        say("!! could not discover OSTs on victim/partner; aborting")
        LOG.result({"error": "ost discovery", "osts": ost})
        return 2
    if not push_scripts(client):
        say("!! could not push scripts")
        return 2
    ref, off = client_prep(client, sub)
    if ref is None:
        say("!! client prep failed")
        return 2
    d = f"{STAB}/{sub}"
    n_files = a.files
    if is_head:
        pre = f"for i in $(seq 0 {n_files - 1}); do touch {d}/w_$(printf %05d $i); done"
    else:
        A, B = ost[victim][0], ost[partner][0]
        probe = f"{d}/layoutcheck"
        r = adhoc(client, f"lfs mirror create -N1 -c1 -o {A} -N1 -c1 -o {B} {probe} && lfs getstripe {probe}").get(client, {})
        got = parse_stripe_osts(r.get("stdout", ""))
        say(f"layout check: mirrors on OSTs {got}, wanted [{A}, {B}]")
        if got != sorted([A, B]):
            say("!! mirror placement did not come out as requested; aborting (see log)")
            LOG.raw(r.get("stdout", "") + r.get("stderr", ""))
            LOG.result({"error": "mirror layout", "got": got, "want": [A, B]})
            return 2
        pre = (f"rm -f {probe}; for i in $(seq 0 {n_files - 1}); do "
               f"lfs mirror create -N1 -c1 -o {A} -N1 -c1 -o {B} {d}/w_$(printf %05d $i) || echo CREATEFAIL $i; done")
    r = adhoc(client, pre, timeout=600).get(client, {})
    say(f"pre-created {n_files} files: {r.get('stdout', '').strip()[-200:] or 'ok'}")
    t_start = time.time()
    bg(client, f"{LOCAL}/probe.sh {d}", f"{LOCAL}/probe.log")
    bg(client, f"{LOCAL}/writer.sh {d} {LOCAL}/chunk {n_files} 240", f"{LOCAL}/writer.log")
    say(f"load running; losing {victim} in {a.pre}s")
    time.sleep(a.pre)
    t_kill = time.time()
    say(f"*** POWER OFF {victim} at +{t_kill - t_start:.0f}s")
    power([victim], "off")
    time.sleep(a.down)
    say(f"stopping writer after {a.down}s outage")
    adhoc(client, f"touch {LOCAL}/stop")
    for _ in range(60):
        if "W DONE" in fetch(client, f"{LOCAL}/writer.log"):
            break
        time.sleep(10)
    result = {"victim": victim, "client": client, "partner": None if is_head else partner,
              "files": n_files, "pre_s": a.pre, "down_s": a.down}
    ver_dir = f"{LOCAL}/ok_list"
    if not is_head:
        say("verify #1: read back all successfully written files WITH the victim still down")
        r = adhoc(client, f"{LOCAL}/verify.sh {ver_dir} {ref}", timeout=3000).get(client, {})
        v1 = [l for l in r.get("stdout", "").splitlines() if l.startswith("V ")]
        for l in v1:
            say("  " + l)
        result["verify_victim_down"] = v1[-1] if v1 else "no output"
    t_on = time.time()
    say(f"*** POWER ON {victim}")
    power([victim], "on")
    up, mnt, timed_out = wait_mounted([victim], t_on, a.timeout)
    t_back = time.time()
    result["recovery_to_mount_s"] = mnt.get(victim)
    result["recovery_timed_out"] = timed_out
    if is_head:
        time.sleep(30)
    say("verify #2: after the node is back (mirrors may be stale)")
    r = adhoc(client, f"{LOCAL}/verify.sh {ver_dir} {ref}", timeout=3000).get(client, {})
    v2 = [l for l in r.get("stdout", "").splitlines() if l.startswith("V ")]
    for l in v2:
        say("  " + l)
    result["verify_after_return"] = v2[-1] if v2 else "no output"
    if not is_head:
        say("resync stale mirrors + mirror verify")
        r = adhoc(client, f"{LOCAL}/resync.sh {d}", timeout=6000).get(client, {})
        rs = [l for l in r.get("stdout", "").splitlines() if l.startswith("R ")]
        for l in rs:
            say("  " + l)
        result["resync"] = rs
        r = adhoc(client, f"{LOCAL}/verify.sh {ver_dir} {ref}", timeout=3000).get(client, {})
        v3 = [l for l in r.get("stdout", "").splitlines() if l.startswith("V ")]
        result["verify_after_resync"] = v3[-1] if v3 else "no output"
        say("verify #3: " + result["verify_after_resync"])
    w = parse_writer(fetch(client, f"{LOCAL}/writer.log"), off)
    p = parse_probe(fetch(client, f"{LOCAL}/probe.log"), off)
    result["io"] = analyse_io(w, p, t_kill, t_back)
    result["fail_list"] = fetch(client, f"{LOCAL}/fail_list").split()
    result["health_after"] = health("after", heads, computes)
    say("\n=== I/O around the loss")
    for k, v in result["io"].items():
        say(f"  {k}: {v}")
    if not a.keep:
        adhoc(client, f"rm -rf {d}", timeout=600)
    path = os.path.join(OUT, f"nodeloss_{LOG.ts}.json")
    json.dump(result, open(path, "w"), indent=1, default=str)
    LOG.result(result)
    return 0


def cmd_soak(a):
    heads, computes, _ = inventory()
    base = health("soak start", heads, computes)
    if not base["healthy"] and not a.force:
        say("!! not healthy; pass --force to soak anyway")
        return 2
    prep = adhoc("compute", f"mkdir -p {STAB} && chmod 777 {STAB}; which fio >/dev/null && echo fio-ok || echo NO-FIO")
    if any("NO-FIO" in v.get("stdout", "") for v in prep.values()):
        say("!! fio missing on some computes: run `just stab-prep` first")
        return 2
    fio = (f"mkdir -p {STAB}/soak_$(hostname) && fio --name=soak --directory={STAB}/soak_$(hostname) --size=2G "
           f"--rw=randrw --rwmixread=70 --bs=1M --direct=1 --ioengine=libaio --iodepth=8 --numjobs=2 "
           f"--time_based --runtime={a.round} --group_reporting --output-format=json")
    end = time.time() + a.hours * 3600
    rnd, fails, allr = 0, 0, []
    dm0 = {h: int(d.get("DMESG_ERR", 0)) for h, d in base["nodes"].items() if d.get("reachable")}
    ib0 = {h: {k: d.get(k) for k in d if k.startswith("IB_")} for h, d in base["nodes"].items() if d.get("reachable")}
    while time.time() < end:
        rnd += 1
        res = adhoc("compute", fio, timeout=a.round + 300)
        rbw = wbw = errs = 0.0
        nok = 0
        for h, v in res.items():
            if not good(v):
                errs += 1
                continue
            try:
                j = json.loads(v["stdout"][v["stdout"].find("{"):])["jobs"][0]
                rbw += j["read"]["bw"] / 1024
                wbw += j["write"]["bw"] / 1024
                errs += j.get("total_err", 0)
                nok += 1
            except Exception:
                errs += 1
        hl = health(f"soak round {rnd}", heads, computes)
        dm = sum(int(d.get("DMESG_ERR", 0)) - dm0.get(h, 0) for h, d in hl["nodes"].items() if d.get("reachable"))
        ib = sum(max(0, int(d.get(k) or 0) - int(ib0.get(h, {}).get(k) or 0))
                 for h, d in hl["nodes"].items() if d.get("reachable") for k in d
                 if k.startswith("IB_") and k in ("IB_symbol_error", "IB_link_downed", "IB_port_rcv_errors"))
        row = [time.strftime("%Y-%m-%dT%H:%M:%S"), rnd, nok, round(rbw), round(wbw), int(errs), dm, ib,
               hl["fs"]["osts"], hl["healthy"], "; ".join(hl["problems"])]
        write_csv("soak.csv", ["ts", "round", "nodes_ok", "read_MBps", "write_MBps", "io_errors",
                               "new_dmesg_errors", "new_ib_errors", "osts", "healthy", "problems"], [row])
        say(f"  round {rnd}: nodes_ok={nok}/8 read={round(rbw)} write={round(wbw)} MB/s io_err={int(errs)} "
            f"new_dmesg={dm} new_ib_err={ib} healthy={hl['healthy']}")
        allr.append(row)
        fails = 0 if hl["healthy"] else fails + 1
        if fails >= 3 and a.stop_on_fail:
            say("!! 3 consecutive unhealthy rounds; stopping")
            break
    LOG.result({"command": "soak", "rounds": allr})
    return 0


def main():
    global LOG
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("health").set_defaults(fn=cmd_health)
    sub.add_parser("prep").set_defaults(fn=cmd_prep)
    c = sub.add_parser("coldboot")
    c.add_argument("--runs", type=int, default=1)
    c.add_argument("--hard", action="store_true", help="IPMI power-off instead of graceful shutdown")
    c.add_argument("--head1-delay", type=int, default=0, help="seconds to hold Head-1 (MGS) off after the others")
    c.add_argument("--integrity", type=int, default=0, help="write N x 256MB files before, verify after")
    c.add_argument("--timeout", type=int, default=1500)
    c.set_defaults(fn=cmd_coldboot)
    r = sub.add_parser("rebootloop")
    r.add_argument("--runs", type=int, default=3)
    r.add_argument("--limit")
    r.set_defaults(fn=cmd_rebootloop)
    n = sub.add_parser("nodeloss")
    n.add_argument("--victim", default="Rocky-Compute-5")
    n.add_argument("--files", type=int, default=80)
    n.add_argument("--pre", type=int, default=45)
    n.add_argument("--down", type=int, default=90)
    n.add_argument("--timeout", type=int, default=900)
    n.add_argument("--keep", action="store_true")
    n.add_argument("--force", action="store_true")
    n.set_defaults(fn=cmd_nodeloss)
    s = sub.add_parser("soak")
    s.add_argument("--hours", type=float, default=1.0)
    s.add_argument("--round", type=int, default=300)
    s.add_argument("--stop-on-fail", action="store_true")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_soak)
    a = p.parse_args()
    LOG = Log(a.cmd)
    try:
        rc = a.fn(a)
    except KeyboardInterrupt:
        say("\ninterrupted")
        LOG.result({"interrupted": True})
        rc = 130
    sys.exit(rc)


if __name__ == "__main__":
    main()
