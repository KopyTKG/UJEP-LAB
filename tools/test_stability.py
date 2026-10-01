#!/usr/bin/env python3
"""Offline tests for tools/stability.py: pure parsers + the `health` command driven
through fake ansible binaries. Run: python3 tools/test_stability.py"""
import json, os, stat, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stability as S

LFSDF_OK = "\n".join(
    [f"lustrefs-MDT000{i}_UUID 66.9G 2.3M 61.0G 1% /mnt/lustre[MDT:{i}]" for i in range(2)] +
    [f"lustrefs-OST{i:04x}_UUID 233.8G 1.5M 221.9G 1% /mnt/lustre[OST:{i}]" for i in range(16)] +
    ["", "filesystem_summary:       3.7T     24.2M      3.5T   1% /mnt/lustre"])


class Parsers(unittest.TestCase):
    def test_lfsdf(self):
        r = S.parse_lfsdf(LFSDF_OK)
        self.assertEqual((r["osts"], r["mdts"], r["bad"], r["size"]), (16, 2, 0, "3.7T"))
        r = S.parse_lfsdf(LFSDF_OK.replace("lustrefs-OST0005_UUID 233.8G", "lustrefs-OST0005_UUID : inactive device"))
        self.assertEqual(r["bad"], 1)

    def test_kv(self):
        self.assertEqual(S.kv("A=1\nB = two\nnoise\n")["B"], "two")

    def test_stripe_osts(self):
        txt = "lmm_objects:\n  - 0: { l_ost_idx: 4, l_fid: [0x1:0x2:0x0] }\n  - 0: { l_ost_idx: 10, l_fid: x }"
        self.assertEqual(S.parse_stripe_osts(txt), [4, 10])

    def test_boot(self):
        out = ("NOW=1000.0\nBTIME=900\n"
               "950.5 Rocky-Compute-1 lustre-startup[1]: <13>Oct 1 x lustre-startup: Lustre startup begin (host=Rocky-Compute-1)\n"
               "951.0 Rocky-Compute-1 lustre-startup[2]: Waiting for MGS at 10.0.0.251@o2ib...\n"
               "951.0 Rocky-Compute-1 lustre-startup[2]: <13>Oct 1 x lustre-startup: Waiting for MGS at 10.0.0.251@o2ib...\n"
               "990.0 Rocky-Compute-1 lustre-startup[3]: MGS reachable\n"
               "995.0 Rocky-Compute-1 lustre-startup[4]: Lustre startup complete\n"
               "960.0 Rocky-Compute-1 lustre-startup[9]: <13>x lustre-startup: FATAL: boom\n")
        e = S.parse_boot(out, ctrl_now=990.0)       # node clock is 10 s ahead of controller
        self.assertAlmostEqual(e["boot"], 890.0)
        self.assertAlmostEqual(e["begin"], 940.5)
        self.assertAlmostEqual(e["reach"] - e["wait"], 39.0)
        self.assertAlmostEqual(e["complete"], 985.0)
        self.assertEqual(e["fatal"], 1)

    def test_io(self):
        w = "".join(f"W {t}.0 {t + 3}.0 /f{i} dd_rc=0\n" for i, t in enumerate([100, 103, 106]))
        w += "W 109.0 200.0 /f3 dd_rc=0\nW 200.0 260.0 /f4 dd_rc=1\n"
        p = "P 100.0 100.01 rc=0\nP 101.0 161.0 rc=0\nP 170.0 170.02 rc=1\n"
        r = S.analyse_io(S.parse_writer(w), S.parse_probe(p), t_kill=108, t_back=250)
        self.assertEqual(r["files_written_ok"], 4)
        self.assertEqual(r["files_write_failed"], 1)
        self.assertEqual(r["median_file_s_before_loss"], 3)
        self.assertEqual(r["slowest_file_s"], 91.0)
        self.assertEqual(r["files_slow_after_loss"], 1)
        self.assertEqual(r["probe_failed"], 1)
        self.assertEqual(r["probe_max_latency_s"], 60.0)


FAKE_ANSIBLE = r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
pattern = a[0]
cmd = a[a.index("-a") + 1] if "-a" in a else ""
state = json.load(open(os.environ["FAKE_STATE"]))
hosts = state["hosts"] if pattern in ("cluster", "all") else pattern.split(",")
def one(h):
    if h in state.get("unreachable", []):
        return {"unreachable": True, "msg": "ssh timeout"}
    if "lfs df" in cmd:
        return {"rc": 0, "stdout": state["lfsdf"]}
    if "KERNEL=" in cmd:
        comp = h.startswith("Rocky-Compute")
        return {"rc": 0, "stdout": "\n".join([
            "KERNEL=" + state.get("kernel", {}).get(h, "5.14.0-611.13.1_lustre.el9.x86_64"), "UNIT=active", "MOUNT=yes",
            "OSTS=" + ("2" if comp else "0"), "NID=10.0.0.1@o2ib", "DMESG_ERR=0", "IB_symbol_error=0"])}
    return {"rc": 0, "stdout": ""}
print(json.dumps({"plays": [{"tasks": [{"hosts": {h: one(h) for h in hosts}}]}]}))
'''

FAKE_INV = r'''#!/usr/bin/env python3
import json
hv = {}
heads = ["Rocky-Head-1", "Rocky-Head-2"]
comps = [f"Rocky-Compute-{i}" for i in range(1, 9)]
for i, h in enumerate(heads + comps):
    hv[h] = {"ansible_host": f"192.168.1.{i + 1}"}
print(json.dumps({"_meta": {"hostvars": hv}, "controller": {"hosts": heads}, "compute": {"hosts": comps}}))
'''


class HealthCommand(unittest.TestCase):
    def run_health(self, **state):
        with tempfile.TemporaryDirectory() as d:
            for name, body in (("ansible", FAKE_ANSIBLE), ("ansible-inventory", FAKE_INV)):
                p = os.path.join(d, name)
                with open(p, "w") as f:
                    f.write(body)
                os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
            base = {"hosts": [f"Rocky-Head-{i}" for i in (1, 2)] + [f"Rocky-Compute-{i}" for i in range(1, 9)],
                    "lfsdf": LFSDF_OK}
            base.update(state)
            sp = os.path.join(d, "state.json")
            with open(sp, "w") as f:
                json.dump(base, f)
            env = dict(os.environ, PATH=d + os.pathsep + os.environ["PATH"], FAKE_STATE=sp, STAB_LOGDIR=d)
            r = subprocess.run([sys.executable, os.path.join(HERE, "stability.py"), "health"],
                               capture_output=True, text=True, env=env)
            return r

    def test_healthy(self):
        r = self.run_health()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("HEALTHY", r.stdout)
        self.assertIn("log: ", r.stdout)

    def test_wrong_kernel_and_missing_ost(self):
        df = LFSDF_OK.replace("lustrefs-OST0005_UUID 233.8G", "lustrefs-OST0005_UUID : inactive")
        r = self.run_health(kernel={"Rocky-Compute-2": "5.14.0-687.50.1.el9_8.x86_64"}, lfsdf=df)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Rocky-Compute-2: kernel 5.14.0-687", r.stdout)
        self.assertIn("inactive", r.stdout)

    def test_unreachable(self):
        r = self.run_health(unreachable=["Rocky-Compute-3"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("Rocky-Compute-3: unreachable", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
