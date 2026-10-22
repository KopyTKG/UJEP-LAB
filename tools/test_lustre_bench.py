#!/usr/bin/env python3
"""Offline tests for tools/lustre_bench.py (fio JSON parsing, aggregation, command building)."""
import json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lustre_bench as L


def fio_doc(read_bw=0, write_bw=0, iops=0, lat_mean_ns=0, p99_ns=0, error=0):
    blank = {"bw": 0, "iops": 0.0, "lat_ns": {"mean": 0.0}, "clat_ns": {"percentile": {"99.000000": 0}}, "total_err": 0}
    r = dict(blank, bw=read_bw, iops=iops, lat_ns={"mean": lat_mean_ns}, clat_ns={"percentile": {"99.000000": p99_ns}})
    w = dict(blank, bw=write_bw, iops=iops, lat_ns={"mean": lat_mean_ns}, clat_ns={"percentile": {"99.000000": p99_ns}})
    return {"fio version": "fio-3.35", "jobs": [{"jobname": "bench", "error": error, "read": r, "write": w}]}


class Parsing(unittest.TestCase):
    def test_parse_with_noise(self):
        txt = "fio: warning something\n" + json.dumps(fio_doc(read_bw=2048)) + "\ntrailing text\n"
        self.assertEqual(L.parse_fio(txt)["jobs"][0]["read"]["bw"], 2048)
        self.assertIsNone(L.parse_fio("no json here"))
        self.assertIsNone(L.parse_fio(""))

    def test_metrics_units(self):
        m = L.job_metrics(fio_doc(read_bw=1048576, iops=1000, lat_mean_ns=250000, p99_ns=900000), "read")
        self.assertAlmostEqual(m["bw_mib_s"], 1024.0)          # fio bw is KiB/s
        self.assertAlmostEqual(m["lat_mean_us"], 250.0)
        self.assertAlmostEqual(m["lat_p99_us"], 900.0)
        self.assertIsNone(L.job_metrics({"jobs": []}, "read"))

    def test_aggregate(self):
        a = L.job_metrics(fio_doc(write_bw=1024 * 300, iops=100, lat_mean_ns=1_000_000, p99_ns=3_000_000), "write")
        b = L.job_metrics(fio_doc(write_bw=1024 * 100, iops=50, lat_mean_ns=3_000_000, p99_ns=9_000_000), "write")
        g = L.aggregate([a, None, b])
        self.assertEqual(g["clients_ok"], 2)
        self.assertAlmostEqual(g["bw_mib_s"], 400.0)
        self.assertEqual(g["iops"], 150)
        self.assertAlmostEqual(g["lat_mean_us"], 2000.0)
        self.assertAlmostEqual(g["lat_p99_us_worst"], 9000.0)
        self.assertIsNone(L.aggregate([None, None]))

    def test_cells(self):
        rows = [{"config": "default", "clients": "1", "phase": "seq_read", "bw_mib_s": x} for x in (100, 110, 120)]
        s = L.summarize_cells(rows)[0]
        self.assertEqual((s["n"], s["mean_mib_s"]), (3, 110))
        self.assertAlmostEqual(s["stdev_mib_s"], 10.0)


class Commands(unittest.TestCase):
    def test_same_job_name_in_every_phase(self):
        cmds = [L.fio_cmd("/mnt/lustre/bench/x/$(hostname)", ph, "4G", 45, 5) for ph in L.PHASES]
        self.assertTrue(all("--name=bench " in c for c in cmds))          # files are reused across phases
        self.assertTrue(all("--direct=1" in c for c in cmds))             # client cache bypassed

    def test_write_is_size_based_reads_are_time_based(self):
        w = L.fio_cmd("/d", "seq_write", "4G", 45, 5)
        r = L.fio_cmd("/d", "seq_read", "4G", 45, 5)
        self.assertNotIn("--time_based", w)
        self.assertIn("--time_based --runtime=45 --ramp_time=5", r)
        self.assertIn("--norandommap", L.fio_cmd("/d", "rand_read_4k", "4G", 45, 5))
        self.assertNotIn("--norandommap", r)

    def test_configs(self):
        self.assertEqual(L.CONFIGS["default"]["stripe"], 1)
        self.assertEqual(L.CONFIGS["tuned"]["stripe"], 4)
        self.assertEqual(L.CONFIGS["tuned"]["set"]["osc.*.max_rpcs_in_flight"], "32")
        self.assertNotIn("sync_journal", json.dumps(L.CONFIGS))           # durability setting is not touched


if __name__ == "__main__":
    unittest.main(verbosity=2)
