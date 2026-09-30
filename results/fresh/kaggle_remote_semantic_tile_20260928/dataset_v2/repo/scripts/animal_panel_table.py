"""Panel table from animal_diag JSONs (results/fresh/threads_20260928/animal/diag/<ep>_<arm>.json): per species and world,
leader vs arm: animal-days, fed / cared shares, production nights unfed, units produced, bank wipes, cap loss, escapes,
units sold / revenue, midnight deletions; plus a check that the replayed final cash equals the multi run's.

usage: animal_panel_table.py <arm> [--detail]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from animal_diag import summarize  # noqa: E402
from run_arms import PANEL13  # noqa: E402

DIAG = ROOT / 'results/fresh/threads_20260928/animal/diag'
M = ROOT / 'results/fresh/sector_20260925/multi'
KEYS = ['animal_days', 'fed', 'cared', 'fed_cared', 'prod_nights', 'prod_unfed', 'wipe', 'bank_at_prod', 'units', 'cap_loss',
        'escaped', 'bought', 'harvested', 'sold', 'revenue', 'opp_rev', 'deleted', 'held_end']


def main():
    arm = sys.argv[1]
    detail = '--detail' in sys.argv
    tot = {w: {sp: {k: 0 for k in KEYS} for sp in ('GOOSE', 'COW', 'SHEEP')} for w in ('leader', arm)}
    n = 0
    for g in PANEL13:
        ep = g.split(':')[1]
        f = DIAG / f'{ep}_{arm}.json'
        if not f.exists():
            print(ep, 'missing')
            continue
        r = json.loads(f.read_text())
        mf = M / arm.upper() / f'{ep}.json'
        chk = ''
        if mf.exists():
            mm = json.loads(mf.read_text())['money']['30']
            chk = 'cash OK' if [round(x) for x in mm] == [round(x) for x in r[arm]['final']] else f'CASH MISMATCH {mm} vs {r[arm]["final"]}'
        n += 1
        line = [ep, chk]
        for who in ('leader', arm):
            s = summarize(r[who])
            for sp, v in s.items():
                for k in KEYS:
                    tot[who][sp][k] += v[k]
            if detail:
                line.append(who + ': ' + ' '.join('%s u%d/s%d f%d/%d c%d pu%d' % (sp[0], v['units'], v['sold'], v['fed'], v['animal_days'],
                                                                                v['cared'], v['prod_unfed']) for sp, v in s.items()))
        print(' | '.join(line))
    print(f'\nPANEL TOTALS over {n} worlds (per world in brackets)')
    for sp in ('GOOSE', 'COW', 'SHEEP'):
        print(sp)
        for who in ('leader', arm):
            v = tot[who][sp]
            print('  %-7s' % who, ' '.join('%s=%d(%.1f)' % (k, v[k], v[k] / max(1, n)) for k in KEYS))


if __name__ == '__main__':
    main()
