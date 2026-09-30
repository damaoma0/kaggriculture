"""Aggregate failure check over OUR ladder games: all losses plus an equal number of wins (fixed random sample).

Downloads each replay (kaggle competitions replay, ~32 MB, deleted again after tracing), runs ladder_trace.py --brief
in a 4-worker pool, and compares losses with wins: recorded-vs-submitted action mismatches, commands with no effect,
HIRE shortfalls, orders over the cap, lowest cash, animals lost before the end-of-season wind-down and whether the
loss followed a tape switch, final-tape mismatch.
usage: ladder_batch.py [n_wins=24]
"""
import json
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/ladder_t10'
RAW = ROOT / 'data/ladder_t10'
KAGGLE = ROOT / '.venv/Scripts/kaggle.exe'
PY = ROOT / '.venv/Scripts/python.exe'
KEEP = {110933872}


def handle(g):
    ep = g['id']
    out = OUT / f'trace_{ep}.json'
    if out.exists():
        return ep, 'have'
    path = RAW / f'episode-{ep}-replay.json'
    if not path.exists():
        r = subprocess.run([str(KAGGLE), 'competitions', 'replay', str(ep), '-p', str(RAW), '-q'], capture_output=True, timeout=300)
        if not path.exists():
            return ep, 'FAILED download ' + r.stderr.decode(errors='replace')[-120:]
    r = subprocess.run([str(PY), str(ROOT / 'scripts/ladder_trace.py'), str(path), '--brief'], capture_output=True, timeout=1200,
                       env=dict(__import__('os').environ, PYTHONIOENCODING='utf-8'))
    if ep not in KEEP:
        path.unlink(missing_ok=True)
    return ep, 'ok' if out.exists() else 'FAILED trace ' + r.stderr.decode(errors='replace')[-200:]


def main():
    n_wins = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    games = json.loads((OUT / 'games.json').read_text(encoding='utf-8'))
    losses = [g for g in games if g['mine'] < g['theirs']]
    wins = [g for g in games if g['mine'] > g['theirs']]
    random.Random(20260920).shuffle(wins)
    todo = losses + wins[:n_wins]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for ep, status in pool.map(handle, todo):
            print(ep, status, flush=True)
    rows = []
    for g in todo:
        f = OUT / f'trace_{g["id"]}.json'
        if f.exists():
            rows.append(dict(g, **json.loads(f.read_text(encoding='utf-8'))))
    for label, G in (('LOSSES', [r for r in rows if r['mine'] < r['theirs']]), ('WINS', [r for r in rows if r['mine'] > r['theirs']])):
        k = max(1, len(G))
        early = [[x for x in r['lost'] if x[0] < 25] for r in G]
        after_switch = 0
        for r, L in zip(G, early):
            days = {h[0] for h in r['switches'][1:]}
            after_switch += sum(1 for d, _ in L if any(0 <= d - s <= 3 for s in days))
        print(f'\n{label} (n={len(G)}): mean final {sum(r["mine"] for r in G) / k:,.0f}, margin {sum(r["mine"] - r["theirs"] for r in G) / k:+,.0f}')
        print(f'   action mismatches vs the submitted file: {sum(r["mismatch"] for r in G)} in total; status problems: {sum(1 for r in G if r["status"])} games; lowest overage {min((r["overage_min"] or 60) for r in G):.1f} s')
        print(f'   commands with no effect: {sum(r["dead_total"] for r in G) / k:.1f} a game of {sum(r["commands"] for r in G) / k:,.0f} ({sum(r["dead_total"] for r in G) / max(1, sum(r["commands"] for r in G)):.2%}); max {max(r["dead_total"] for r in G)}')
        print(f'   games with a HIRE shortfall: {sum(1 for r in G if r["hire_short"])}; with orders over the cap: {sum(1 for r in G if r["over_cap"])}; lowest cash under 20: {sum(1 for r in G if r["min_cash"][0] < 20)} games')
        print(f'   animals lost before day 25: {sum(len(L) for L in early)} in {sum(1 for L in early if L)} games ({after_switch} within 3 days of a tape switch)')
        print(f'   router: switches after day 12 in {sum(1 for r in G if any(h[0] > 12 for h in r["switches"]))} games; final-tape shops equal to the world (last four): {sum(1 for r in G if r.get("tape_shops") and sorted(r["tape_shops"][4:]) == sorted(r["shops"][4:]))}')
        print(f'   our final minus the final tape\'s ORIGINAL result: {sum(r["rewards"][r["seat"]] - r.get("tape_final", 0) for r in G if r.get("tape_final")) / max(1, sum(1 for r in G if r.get("tape_final"))):+,.0f}')
    (OUT / 'batch.json').write_text(json.dumps(rows, default=list), encoding='utf-8')


if __name__ == '__main__':
    main()
