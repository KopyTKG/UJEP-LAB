# Stability tests

Plan for the remaining tests: [NEXT.md](NEXT.md).

Run from the repo root with `just` (needs the venv: `just deps`, and the vault password file).
**Every command tees its whole console to `logs/<command>_<timestamp>.log`** and ends the log with a
`RESULT_JSON {...}` line; structured rows go to the CSV/JSON files here. Nothing needs to be pasted
back: say which test finished and the logs can be read from this folder.

| File | Written by |
|---|---|
| `logs/*.log` | every test (full console + raw ansible results + `RESULT_JSON`) |
| `coldboot_v2.csv` | `just coldboot` (one row per node per run: boot, unit begin, MGS wait, mounted, fatal retries) |
| `rebootloop.csv` | `just rebootloop` |
| `nodeloss_<ts>.json` | `just nodeloss` |
| `soak.csv` | `just soak` |
| `coldboot.csv` | first, coarse version of the cold-boot test (3 runs, 2026-10-01) |

## Order to run

**0. Prep (once)**
1. `just stab-selftest` &mdash; offline check of the tooling.
2. `just stab-prep` &mdash; fio on the computes, `/mnt/lustre/stab`.
3. `just health` &mdash; must say HEALTHY (2 MDT, 16 OST, `_lustre` kernel everywhere). Fix first if not.

**1. Reproduce the old startup bug (legacy script is what is deployed right now)**
4. `just coldboot 1 --head1-delay 120`  (expect: mounts, slack is thin)
5. `just coldboot 1 --head1-delay 240`  (expect: computes FATAL "MGS not reachable", never mount)

If you run `just startup-deploy false` at any point, you get the legacy script back.

**2. Apply the fix and repeat**
6. `just startup-deploy` &mdash; takes effect on the next boot (no restart needed now).
7. `just coldboot 1 --head1-delay 240`  (expect: all mount, `fatal_retries` 0, MGS wait ~240 s)
8. `just coldboot 1 --head1-delay 600`  (MGS appears ~800 s after power-on, so computes wait ~675 s: past the 600 s deadline, so this exercises `Restart=on-failure`; expect `fatal_retries` >= 1 and all mounted in the end)
9. `just coldboot 3`  (plain simultaneous power-on, like before)
10. `just coldboot 2 --hard`  (IPMI power-off, no clean unmount: MDT/OST recovery)
11. `just coldboot 2 --integrity 40`  (writes 40 x 256 MB before, sha256-verifies after the cold boot)

**3. Reboots**
12. `just rebootloop 5`

**4. Node loss under load** (hard power-off of the victim while writing mirrored files)
13. `just nodeloss Rocky-Compute-5`
14. `just nodeloss Rocky-Compute-8`
15. `just nodeloss Rocky-Head-2`  (MDT1 lost; no mirrors involved)
16. `just nodeloss Rocky-Head-1`  (MGS + MDT0 lost: the hard case, expect clients to hang until it is back)

**5. Soak**
17. `just soak 1`  (shake-down), then `just soak 24 --stop-on-fail`

## What each test answers

- **coldboot** (note 14, section 2): does Lustre come up unattended after a power-on with arbitrary skew
  between the MGS host and the rest, and how long does each node wait.
- **nodeloss**: pins one mirror of each file on the victim's OST and the other on another compute,
  writes continuously, powers the victim off after `--pre` s (45), keeps writing for `--down` s (90),
  then verifies every written file by sha256 (a) while the victim is still down, (b) after it is back,
  (c) after `lfs mirror resync`, plus `lfs mirror verify`. Reports longest write stall, failed writes,
  metadata probe latency (a new file every second), recovery time. It self-checks the mirror placement
  first and aborts without damage if the layout is not what it asked for.
- **soak**: 70/30 random mixed fio on all 8 computes in rounds, health + new dmesg errors + new IB error
  counters per round.

Known assumptions to watch in the first logs: `lfs mirror create -N1 -c1 -o <idx>` placement syntax,
the OST-index-to-node mapping (discovered from `lctl dl`), and node clocks (+-1-2 s).
