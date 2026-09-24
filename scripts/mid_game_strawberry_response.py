"""Mid-game strawberry response: is DSM's strawberry tile count at days 9/12/15/18 more responsive to
strawberry-buying shops revealed by day 6/9/12 than our own 584-tape (UMG-old) library?

Uses only the already-parsed exact-board caches from the earlier leader-response study
(results/fresh/newphase_20260923/leader_response/{dsm_cache,umg_cache}.json). No games are simulated.

Straw-buying shops: BRUNCH_SPOT, ICE_CREAM_SHOP, SMOOTHIE_SHOP, FARMERS_MARKET (each 6/day; the
question's "early=shops1-4 / late=shops5-8" split is by unlock order, not by type).

Output: results/fresh/newphase_20260923/strawberry/mid_game_response.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESP = ROOT / 'results/fresh/newphase_20260923/leader_response'
OUT = ROOT / 'results/fresh/newphase_20260923/strawberry'
STRAW_SHOPS = {'BRUNCH_SPOT', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP', 'FARMERS_MARKET'}


def straw_count(shops_by_day, day):
    day = min(day, len(shops_by_day) - 1)
    return sum(1 for s in shops_by_day[day] if s in STRAW_SHOPS)


def bucket(n):
    return '0' if n <= 0 else ('1' if n == 1 else '2+')


def load_dsm():
    d = json.loads((RESP / 'dsm_cache.json').read_text(encoding='utf-8'))
    rows = []
    for key, g in d.items():
        shops = g['shops_by_day']
        for seat in ('0', '1'):
            pf = g['per_farm'].get(seat)
            if not pf:
                continue
            dc = pf['day_counts']
            if len(dc) < 19:
                continue
            rows.append(dict(key=key + ':' + seat, shops_by_day=shops, day_counts=dc))
    return rows


def load_umg():
    d = json.loads((RESP / 'umg_cache.json').read_text(encoding='utf-8'))
    rows = []
    for ep, g in d.items():
        dc = g['day_counts']
        if len(dc) < 19:
            continue
        rows.append(dict(key=str(ep), shops_by_day=g['shops_by_day'], day_counts=dc))
    return rows


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def analyze(rows, source):
    out = dict(source=source, n=len(rows), cutoffs={})
    for cutoff in (6, 9, 12):
        cut = dict(cutoff_day=cutoff, buckets={})
        by_bucket = {}
        for r in rows:
            n_straw = straw_count(r['shops_by_day'], cutoff)
            by_bucket.setdefault(bucket(n_straw), []).append(r)
        for b in ('0', '1', '2+'):
            grp = by_bucket.get(b, [])
            if not grp:
                continue
            entry = dict(n=len(grp))
            for target_day in (9, 12, 15, 18):
                if target_day <= cutoff - 3:      # target must be at/after the reveal to be a response, not a pre-period echo
                    continue
                vals = [r['day_counts'][target_day].get('STRAWBERRY', 0) for r in grp
                        if target_day < len(r['day_counts'])]
                entry[f'straw_tiles_day{target_day}'] = round(mean(vals), 2) if vals else None
            cut['buckets'][b] = entry
        # responsiveness slope: (mean tiles | bucket 2+) - (mean tiles | bucket 0), per target day
        slopes = {}
        for target_day in (9, 12, 15, 18):
            if target_day <= cutoff - 3:
                continue
            key = f'straw_tiles_day{target_day}'
            lo = cut['buckets'].get('0', {}).get(key)
            hi = cut['buckets'].get('2+', {}).get(key)
            if lo is not None and hi is not None:
                slopes[key] = round(hi - lo, 2)
        cut['responsiveness_2plus_minus_0'] = slopes
        out['cutoffs'][str(cutoff)] = cut
    return out


def main():
    dsm_rows = load_dsm()
    umg_rows = load_umg()
    dsm = analyze(dsm_rows, 'dsm')
    umg = analyze(umg_rows, 'umg_old_library')
    result = dict(dsm=dsm, umg_old=umg)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'mid_game_response.json').write_text(json.dumps(result, indent=1), encoding='utf-8')

    print(f'DSM n={dsm["n"]}, UMG-old n={umg["n"]}\n')
    for cutoff in (6, 9, 12):
        print(f'--- strawberry-buying shops revealed by day {cutoff} ---')
        for source, data in (('DSM', dsm), ('UMG-old (our library)', umg)):
            c = data['cutoffs'][str(cutoff)]
            print(f'  {source}:')
            for b in ('0', '1', '2+'):
                e = c['buckets'].get(b)
                if not e:
                    continue
                cells = ', '.join(f'd{k[-2:] if k[-2].isdigit() else k[-1]}={v}' for k, v in e.items() if k != 'n')
                print(f'    demand={b:<3} n={e["n"]:<4} {cells}')
            print(f'    responsiveness (2+ minus 0 bucket): {c["responsiveness_2plus_minus_0"]}')
        print()


if __name__ == '__main__':
    main()
