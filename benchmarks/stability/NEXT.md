# Next week: remaining stability tests

Status after 2026-10-01 (details: thesis `notes/15`): startup fix proven for graceful cold boots (4/4, up to a
240 s Head-1 delay), integrity 40/40 across a hard power-off, hard-power-off pool delay (~5 min) understood and
accepted (two power lines, UPS, scheduled shutdowns, so `abort_recov` on OSTs is deliberately NOT added).
**Not yet tested: failure tolerance (R5), rolling reboots, long-run stability.** That is this list.

All commands from the repo root; every run logs to `logs/` (see README.md). After each test tell me which one
finished and I read the logs and update note 15.

## Before starting (10 min)
1. `just stab-selftest`
2. `just health`  -> must be HEALTHY (16 OST, 2 MDT, `_lustre` kernel on all 10). Fix first if not.
3. `just stab-prep`  (fio on computes, `/mnt/lustre/stab`)
4. Loose end: `just sh compute 'dnf check-update --exclude="kernel*" | head -3'` (did the update on Compute-6..8 finish?)

## Priority 1: node loss (R5, the thesis requirement)
Hard power-off of one node during continuous mirrored writes, power back on, verify.

| # | Command | Est. time | Question |
|---|---|---|---|
| 1 | `just nodeloss Rocky-Compute-5` | ~25 min | Does FLR keep I/O going and the data intact when a blade dies? |
| 2 | `just nodeloss Rocky-Compute-8` | ~25 min | Same, different blade (rules out a one-node fluke) |
| 3 | `just nodeloss Rocky-Head-2` | ~20 min | MDT1 lost, no mirrors: how long is metadata/I/O stalled, any damage? |
| 4 | `just nodeloss Rocky-Head-1` | ~25 min | MGS + MDT0 lost: the hard case. Expect clients to hang until it is back (Head-1 needs ~190 s to boot) |

Pass criteria (compute victims):
- layout check passes (mirrors on the OSTs asked for), otherwise the test aborts by itself: then fix the assumption, not the cluster
- verify #1 (victim still down), #2 (after return) and #3 (after resync): `ok=<all written> bad=0 err=0`
- `resync`: `failed=0`; `MIRRORVERIFY mismatch=0`
- `recovery_to_mount_s` under ~300 s, health after = HEALTHY
- record, not pass/fail: longest write stall, failed writes, metadata probe latency. Open question: do writes block, fail with EIO, or continue on the surviving mirror.

Pass criteria (head victims): stalled operations resume after the head is back; `bad=0`; no data loss; stall about equals downtime plus recovery.

Risk: a hard power-off of an active OSS/MDS. Test data lives only in `/mnt/lustre/stab`; existing data on the filesystem is the old `k8s*` leftovers and test files.

## Priority 2: rolling reboots (~2 h for 4 loops)
`just rebootloop 4`  (heads first, serial, each node waits for its Lustre mount; health after every loop)
Pass: every loop rc=0 and HEALTHY. Note: this is a maintenance-window simulation with live clients, Head-1 (MGS) goes away while the computes are mounted. Expect brief hiccups; record how long.

## Priority 3: confirm the fix at scale (optional, ~1.5 h)
- `just coldboot 3 --head1-delay 240`  (3 more graceful runs at twice the old limit)
- Airtight before/after: `just startup-deploy false`, `just coldboot 1 --head1-delay 240` (expect computes FATAL at ~145 s and stay unmounted; rescue with `just lustre-up`), then `just startup-deploy` again. Do not forget the last step.
- Retry path: `just coldboot 1 --head1-delay 600` (~35 min; expect `fatal_retries` >= 1 on the computes and everything mounted in the end)

## Priority 4: soak (run overnight, last)
- `just soak 1` first as a shake-down (fio present, numbers sane), then `just soak 24 --stop-on-fail`
- Watch in `soak.csv`: `healthy` stays True, `new_dmesg_errors` and `new_ib_errors` stay about 0, throughput does not drift down.

## Order and rough budget
Day 1: setup, node loss 1-4 (about 2 h). Day 2: rolling reboots, optional priority 3 (about 3-4 h). Overnight: soak 24 h.

## Not covered here (separate, later)
- R3 numbers with cache bypass (note 14, section 1): fio matrix, repeated runs, scaling 1/2/4/8 clients.
- VM layer tests once KVM hosts exist (live migration under load, node loss with VMs running).
