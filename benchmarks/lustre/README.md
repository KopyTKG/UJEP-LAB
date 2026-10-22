# Lustre performance matrix (cache-controlled)

Results and interpretation: [RESULTS.md](RESULTS.md) (generated), thesis note 18, thesis `data/lustre_perf_data.json`.

```bash
python3 tools/lustre_bench.py plan                 # what `run` would do, time estimate
python3 tools/lustre_bench.py baseline             # read-only raw SSD test + SATA link speed per drive (~5 min)
python3 tools/lustre_bench.py control --reps 2     # OSS cache off vs on, same workload (~20 min)
python3 tools/lustre_bench.py run                  # matrix: default/tuned x 1,4,8 clients x 3 repeats (~1 h)
python3 tools/make_lustre_data.py                  # RESULTS.md + thesis dataset from the CSVs
```

Files: `lustre_matrix.csv` (every run), `matrix_<ts>.json` (with per-client values), `control.csv`, `baseline.csv`, `logs/`.

**Known issue (2026-10-22):** the matrix was measured while two SSDs (OST5 on Compute-3, OST13 on Compute-7) ran on a
3.0 Gbit/s SATA link after link errors, and two more showed CRC errors. Fix the cabling/backplane for those bays, then
re-run `baseline` (all 16 drives should read about 530 MiB/s at 6.0 Gbit/s) and the matrix. See thesis note 18.
