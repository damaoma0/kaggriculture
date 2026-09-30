"""Animal retirement in the stored leader corpus (no games): when does a leader stop feeding / caring an animal?

usage: lead_retirement.py [teams=16732748,16770421,16730612|all]
Per animal life (tile, species, first / last day on the board, fed / cared days) from data/leader_semantics: boards
(animal labels; an empty COOP also reads 'co', so each tile's structure comes from the build events), maintenance FEED /
CARE tile lists, and the day's market sales (index d = actual day d+1, see the progress doc's data quirk). For animals
whose feeding stops before the end: age, productions it could still have made, days left, the product's realized price
around the stop vs its base price; the same for the animals fed to the end (at their last 5 days) for comparison.
"""
import gzip
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEM = ROOT / 'data/leader_semantics'
SPEC = {'co': 'COW', 'sh': 'SHEEP', 'go': 'GOOSE'}
PROD = {'COW': 'MILK', 'SHEEP': 'WOOL', 'GOOSE': 'EGG'}
FIRST = {'COW': 8, 'SHEEP': 6, 'GOOSE': 4}
INTERVAL = {'COW': 2, 'SHEEP': 3, 'GOOSE': 1}
BASE = {'MILK': 160, 'WOOL': 200, 'EGG': 50, 'WHEAT': 25}


def productions(sp, placed, d0, d1):
    """production days in [d0, d1] (end-of-day refresh: produces on day d if d + 1 - placed - first >= 0 and % interval == 0)."""
    return sum(1 for d in range(d0, d1 + 1) if d + 1 - placed - FIRST[sp] >= 0 and (d + 1 - placed - FIRST[sp]) % INTERVAL[sp] == 0)


def price_near(days, prod, d):
    """the leader's realized average sale price of prod over actual days d-1..d+2 (market index = actual day - 1)."""
    u = r = 0
    for a in range(d - 1, d + 3):
        i = a - 1
        if 0 <= i < len(days):
            m = days[i].get('market') or {}
            u += (m.get('sold_units') or {}).get(prod, 0)
            r += (m.get('sold_revenue') or {}).get(prod, 0)
    return (r / u) if u else None


def lives(sem):
    days = sem['days']
    struct = {}
    out = []
    cur = {}
    for d, day in enumerate(days):
        for k, ts in (day.get('built') or {}).items():     # {'BUILD_PASTURE': [tiles], 'BUILD_COOP': [tiles]}
            for t in ts:
                struct[int(t)] = k.replace('BUILD_', '')
        b = day['board']
        if b is None:
            continue
        feed = set((day.get('maintenance') or {}).get('FEED', []))
        care = set((day.get('maintenance') or {}).get('CARE', []))
        present = {}
        for t, lab in enumerate(b):
            if lab in SPEC:
                sp = SPEC[lab]
                if lab == 'co' and str(struct.get(t, '')).upper().startswith('COOP'):
                    continue          # an empty coop
                present[t] = sp
        for t, sp in present.items():
            if t not in cur or cur[t]['sp'] != sp:
                if t in cur:
                    out.append(cur.pop(t))
                cur[t] = dict(tile=t, sp=sp, start=d, end=d, fed=[], cared=[])
            cur[t]['end'] = d
            if t in feed:
                cur[t]['fed'].append(d)
            if t in care:
                cur[t]['cared'].append(d)
        for t in [t for t in cur if t not in present]:
            out.append(cur.pop(t))
    out.extend(cur.values())
    return out


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else '16732748,16770421,16730612'
    teams = None if arg == 'all' else set(arg.split(','))
    files = [f for f in sorted(SEM.glob('*/*.json.gz')) if teams is None or f.parent.name in teams]
    stop, kept = defaultdict(list), defaultdict(list)
    esc = Counter()
    games = 0
    for f in files:
        sem = json.load(gzip.open(f, 'rt', encoding='utf-8'))
        games += 1
        days = sem['days']
        for L in lives(sem):
            sp = L['sp']
            if L['end'] - L['start'] < 1:
                continue
            last_feed = max(L['fed']) if L['fed'] else None
            escaped = L['end'] < 29
            if escaped:
                esc[sp] += 1
            ended_early = last_feed is not None and last_feed <= 27 and (escaped or last_feed < L['end'] - 1)
            ref = (last_feed + 1) if ended_early else max(L['start'], 24)
            if ref > 29:
                continue
            rec = dict(age=ref - L['start'], days_left=29 - ref,
                       prods_left=productions(sp, L['start'], ref, 29),
                       prods_done=productions(sp, L['start'], L['start'], ref - 1),
                       price=price_near(days, PROD[sp], ref), wheat=price_near(days, 'WHEAT', ref),
                       fed_share=len(L['fed']) / max(1, L['end'] - L['start'] + 1))
            (stop if ended_early else kept)[sp].append(rec)
    print(f'{games} games ({arg}); escapes per game: ' + ', '.join(f'{k} {v / games:.2f}' for k, v in sorted(esc.items())))
    print('| species | group | n / game | age at stop | days left | productions done / still possible | product price vs base (median) | share with price < 25% of base | wheat price |')
    print('|---|---|---|---|---|---|---|---|---|')
    for sp in ('COW', 'SHEEP', 'GOOSE'):
        for name, grp in (('feeding stopped early', stop[sp]), ('fed to the end (ref day >= 24)', kept[sp])):
            if not grp:
                continue
            pr = [r['price'] / BASE[PROD[sp]] for r in grp if r['price']]
            wh = [r['wheat'] for r in grp if r['wheat']]
            print(f"| {sp} | {name} | {len(grp) / games:.2f} | {st.median(r['age'] for r in grp):.0f} | {st.median(r['days_left'] for r in grp):.0f} | "
                  f"{st.mean(r['prods_done'] for r in grp):.1f} / {st.mean(r['prods_left'] for r in grp):.1f} | "
                  f"{(st.median(pr) if pr else float('nan')):.2f} (n={len(pr)}) | {(sum(p < 0.25 for p in pr) / len(pr) if pr else float('nan')):.0%} | "
                  f"{(st.median(wh) if wh else float('nan')):.0f} |")


if __name__ == '__main__':
    main()
