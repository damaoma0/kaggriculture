"""Hour-0 market orders, the leader vs an arm over the 40-world panel (days 11-29): per day, the hires and SELL orders
each side issues at hour 0 (step d*24), and for the leader's hour-0 sells whether we sold that product at hour 0 too,
how many units, and why not (no stock in our shed at hour 0 / all 10 order slots used / other). Also the value of the
leader's hour-0 sells at the leader's hour-0 prices vs ours.
usage: panel_h0_orders.py <ARM> [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    while w.t < 719:
        t = w.t
        d, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if t < 264 else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264 and h == 0 and d <= 29:
            L = UE.tape_action(tape['actions'], t).get('market') or []
            A = own.get('market') or []
            shed = w.private(seat)['shed']
            c['days'] += 1
            c['L_hires'] += sum(1 for o in L if o and o[0] == 'HIRE')
            c['A_hires'] += sum(1 for o in A if o and o[0] == 'HIRE')
            c['A_orders'] += len(A)
            c['A_full'] += len(A) >= 10
            ls = {o[1]: int(o[2]) for o in L if o and o[0] == 'SELL' and len(o) > 2}
            as_ = {o[1]: int(o[2]) for o in A if o and o[0] == 'SELL' and len(o) > 2}
            c['L_sell_orders'] += len(ls)
            c['A_sell_orders'] += len(as_)
            for p, n in ls.items():
                c['L_units'] += n
                c['L|' + p] += n
                got = as_.get(p, 0)
                c['A_units_matched'] += min(n, got)
                if got <= 0:
                    have = int(shed.get(p, 0) or 0)
                    why = 'no stock' if have <= 0 else ('10 slots used' if len(A) >= 10 else 'stock but not sold')
                    c['miss|' + why] += 1
                    c['missu|' + why] += n
                    c['missp|' + p] += n
            for p, n in as_.items():
                c['A_units'] += n
                c['A|' + p] += n
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    return dict(c)


if __name__ == '__main__':
    arm = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = Counter()
    with Pool(nw) as pool:
        for c in pool.imap_unordered(job, [(g, arm) for g in games]):
            tot.update(c)
    n = len(games)
    dd = max(1, tot['days'])
    print(f'{arm} vs DSM at hour 0 (days 11-29), per day: hires DSM {tot["L_hires"] / dd:.2f} / ours {tot["A_hires"] / dd:.2f}; sell orders DSM {tot["L_sell_orders"] / dd:.2f} / '
          f'ours {tot["A_sell_orders"] / dd:.2f}; our hour-0 list full (10 orders) on {tot["A_full"] / dd:.0%} of days')
    print(f'   per world: DSM sells {tot["L_units"] / n:.1f} units at hour 0 (' + ', '.join(f'{k[2:]} {v / n:.1f}' for k, v in sorted(tot.items()) if k.startswith('L|'))
          + f'), we {tot["A_units"] / n:.1f} (' + ', '.join(f'{k[2:]} {v / n:.1f}' for k, v in sorted(tot.items()) if k.startswith('A|'))
          + f'); units of DSM\'s hour-0 sells we also sold at hour 0 {tot["A_units_matched"] / n:.1f}')
    print('   DSM hour-0 sells we did not match (orders / units a world): ' + ', '.join(
        f'{k[5:]} {v / n:.1f} / {tot["missu|" + k[5:]] / n:.1f}' for k, v in sorted(tot.items()) if k.startswith('miss|'))
          + ' | by product: ' + ', '.join(f'{k[6:]} {v / n:.1f}' for k, v in sorted(tot.items()) if k.startswith('missp|')))
