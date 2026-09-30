"""Kaggle overage-bank trace of our live ladder games (2026-09-30): the live package's guard switches to lean search at
32 s of overage used, lean2 at 46 s, the greedy dispatcher at 57 s (checked each morning from day 6). The compact ladder
games do not keep remainingOverageTime, so this re-downloads each raw replay (~32 MB, deleted again) and keeps both
seats' remaining bank per step plus the step statuses: results/fresh/ladder_live_20260930/<sub>/bank/<episode>.json.

usage: ladder_bank_trace_20260930.py --sub 56676484 [--threads 2]"""
import argparse
import gzip
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KAGGLE = ROOT / ".venv/Scripts/kaggle.exe"


def one(job):
    ep, seat, out, raw = job
    if out.exists():
        return ep, "have"
    path = raw / f"episode-{ep}-replay.json"
    try:
        if not path.exists():
            subprocess.run([str(KAGGLE), "competitions", "replay", str(ep), "-p", str(raw), "-q"], capture_output=True,
                           timeout=300)
        r = json.loads(path.read_text(encoding="utf-8"))
        st = r["steps"]
        bank = [[s[i]["observation"].get("remainingOverageTime") for s in st] for i in (0, 1)]
        status = [[s[i].get("status") for s in st] for i in (0, 1)]
        out.write_text(json.dumps(dict(episode=ep, seat=seat, bank=bank, final_status=r.get("statuses"),
                                       odd_status=[[t, i, status[i][t]] for i in (0, 1) for t in range(len(st))
                                                   if status[i][t] not in ("ACTIVE", "DONE", "INACTIVE")])), "utf-8")
        return ep, "ok"
    except Exception as e:                         # noqa: BLE001 - report and continue with the next game
        return ep, f"FAILED {type(e).__name__}"
    finally:
        path.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default="56676484")
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    out = ROOT / "results/fresh/ladder_live_20260930" / a.sub / "bank"
    raw = ROOT / "data/ladder_panel/_raw"
    out.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    jobs = []
    for p in sorted((ROOT / "data/ladder_panel" / a.sub).glob("*.json.gz")):
        x = json.load(gzip.open(p, "rt", encoding="utf-8"))
        jobs.append((x["episode"], int(x["seat"]), out / f"{x['episode']}.json", raw))
    counts = {}
    with ThreadPoolExecutor(max_workers=a.threads) as pool:
        for ep, s in pool.map(one, jobs):
            counts[s.split()[0]] = counts.get(s.split()[0], 0) + 1
            if s != "ok" and s != "have":
                print(ep, s, flush=True)
    print(counts)


if __name__ == "__main__":
    main()


def guard_days(bank_seat, lean=32.0, lean2=46.0, greedy=57.0):
    """first day whose morning check (hour 0, days >= 6: the observation of step 24 d) sees used >= each threshold"""
    out = {}
    for name, thr in (("lean", lean), ("lean2", lean2), ("greedy", greedy)):
        out[name] = next((d for d in range(6, 30) if bank_seat[d * 24] is not None and 60 - bank_seat[d * 24] >= thr),
                         None)
    return out
