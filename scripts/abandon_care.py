"""Abandonment research (2026-09-26): value of the care our arms skipped on days they DID feed (partial service).
Each of our animals is re-simulated with the recorded feeding but cared on every fed day (engine day rule: a fed+cared
day banks +1, a production pays 1 + bank if fed that day, else 1 and the bank is wiped; max_held ignored because
harvests are not modelled); the extra units are sold the morning after the production (hour 8) and repriced exactly
(abandon_market.reprice). Also counts keep-alive feeding (a fed day right after an unfed day on a live animal).
usage: abandon_care.py <side,...> <panel>"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import abandon_market as AM  # noqa: E402

if __name__ == '__main__':
    sides = sys.argv[1].split(',')
    games = Path(sys.argv[2]).read_text().replace(',', ' ').split()
    for side in sides:
        T = Counter()
        for g in games:
            ep = g.split(':')[1]
            R = json.loads((AM.RDIR / side / f'{ep}.json').read_text(encoding='utf-8'))
            adds = defaultdict(list)
            for k, a in R['animals'].items():
                who, x, y, pd, kind = k.split(',')
                if who != '0':
                    continue
                item = AM.PROD[kind]
                bank = None
                prev_fed = None
                for d, fed, cared, bank0, yb, prod, made, esc in a['nights']:
                    if bank is None:
                        bank = bank0
                    if d >= 11 and fed and prev_fed == 0:
                        T[kind + '|keepalive_feeds'] += 1
                    if d >= 11 and fed:
                        T[kind + '|feeds'] += 1
                        T[kind + '|care_added'] += 0 if cared else 1
                    prev_fed = fed
                    if esc:
                        break
                    if prod:
                        u = 1 + (bank if fed else 0)
                        if d >= 11 and u > made:
                            adds[item].append((min(718, (d + 1) * 24 + 8), u - made))
                            T[kind + '|units'] += u - made
                        bank = 0
                    if fed:
                        bank += 1
            for item, ad in adds.items():
                o, r = AM.reprice(R, item, ad)
                T['own'] += o
                T['rival'] += r
        n = len(games)
        print(f"{side:6s} care on every fed day: +units/world " + ', '.join(f"{kd} {T[kd + '|units'] / n:.0f}" for kd in ('COW', 'SHEEP', 'GOOSE'))
              + f" | own {T['own'] / n:+.0f} rival {T['rival'] / n:+.0f} margin {(T['own'] - T['rival']) / n:+.0f} | extra CARE actions "
              + ', '.join(f"{kd} {T[kd + '|care_added'] / n:.0f}" for kd in ('COW', 'SHEEP', 'GOOSE'))
              + ' | keep-alive feeds (fed after an unfed day) ' + ', '.join(f"{kd} {T[kd + '|keepalive_feeds'] / max(1, T[kd + '|feeds']):.0%}" for kd in ('COW', 'SHEEP', 'GOOSE')))
