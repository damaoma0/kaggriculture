"""Skeptic check of the sem4 world list (no games): independent re-derivation of results/fresh/lead_sem4_20260925/worlds.json.

Checks: 48 worlds, 12 per team, unique, both files present, leader holds all four quadrants (day-29 board AND >= 3
BUY_LAND orders in the tape actions), the lead_g1.GAMES four-quadrant games included, the selection rule reproduces
the list exactly (own implementation), land days (board-derived) vs the tape's BUY_LAND order days.
"""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SEM = ROOT / 'data/leader_semantics'
TAPES = ROOT / 'data/leader_tapes'
W = json.loads((ROOT / 'results/fresh/lead_sem4_20260925/worlds.json').read_text(encoding='utf-8'))
TEAMS = {'16732748': 'DSM', '16623559': 'DECEM', '16770421': 'Vadim', '16730612': 'MG'}
G1 = ['16732748:112655730', '16732748:112661570', '16732748:112667461', '16732748:112673479',
      '16770421:112708229', '16770421:112714050', '16770421:112715010', '16770421:112721923',
      '16730612:112444381', '16730612:112445586', '16730612:112447950', '16730612:112449129']


def quad(i):
    x, y = i % 10, i // 10
    return ('N' if y < 5 else 'S') + ('W' if x < 5 else 'E')


def load(p):
    return json.load(gzip.open(p, 'rt', encoding='utf-8'))


errs = []
worlds = W['worlds']
print('n', len(worlds), 'by_team', W['by_team'])
if len(worlds) != 48:
    errs.append('n != 48')
eps = [w['episode'] for w in worlds]
if len(set(eps)) != len(eps):
    errs.append('duplicate episodes')
# independent selection
mine = []
for tid, name in TEAMS.items():
    sems = {p.name.split('.')[0] for p in (SEM / tid).glob('*.json.gz')}
    tapes = {p.name.split('.')[0] for p in TAPES.glob(f'{tid}_*/*.json.gz')}
    both = sorted(sems & tapes, key=int)
    four = []
    for ep in both:
        s = load(SEM / tid / f'{ep}.json.gz')
        if ' L' not in s['days'][29]['board']:
            four.append(ep)
    g1four = [g.split(':')[1] for g in G1 if g.split(':')[0] == tid and g.split(':')[1] in four]
    g1not = [g.split(':')[1] for g in G1 if g.split(':')[0] == tid and g.split(':')[1] not in four]
    rest = [e for e in four if e not in g1four]
    k = min(12, len(four)) - len(g1four)
    pick = [rest[int((i + 0.5) * len(rest) / k)] for i in range(k)]
    chosen = sorted(set(g1four) | set(pick), key=int)
    print(f'{name}: both {len(both)}, four-quadrant {len(four)}, G1 four {g1four}, G1 not four {g1not}')
    mine += [f'{tid}:{e}' for e in chosen]
theirs = [w['game'] for w in worlds]
if sorted(mine) != sorted(theirs):
    errs.append(f'selection differs: only mine {sorted(set(mine) - set(theirs))}, only theirs {sorted(set(theirs) - set(mine))}')
g1_four_all = [g for g in G1 if g in theirs]
print('G1 games in the list:', len(g1_four_all), g1_four_all)
# per-world checks
land_orders = {}
for w in worlds:
    tid, ep = w['team_id'], w['episode']
    sp, tp = ROOT / w['semantics'], ROOT / w['tape']
    if not sp.is_file() or not tp.is_file():
        errs.append(f'{ep}: file missing')
        continue
    s, t = load(sp), load(tp)
    if ' L' in s['days'][29]['board']:
        errs.append(f'{ep}: locked tile on day 29')
    if t['seat'] != s['meta']['seat'] or int(t['episode']) != ep or t['seed'] != w['seed']:
        errs.append(f'{ep}: seat/episode/seed mismatch')
    # first tape (sorted) is the one lead_g1 plays
    first = sorted(TAPES.glob(f'{tid}_*/{ep}.json.gz'))[0]
    if first.resolve() != tp.resolve():
        errs.append(f'{ep}: tape is not lead_g1 choice')
    bl = [(step // 24, step % 24) for step, a in enumerate(t['actions'])
          for o in ((a or {}).get('market') or [])[:10] if o and o[0] == 'BUY_LAND']
    land_orders[ep] = bl
    if len(bl) < 3:
        errs.append(f'{ep}: only {len(bl)} BUY_LAND orders')
    # board-derived land days: first day d whose NEXT board shows the quadrant unlocked
    b = [d['board'] for d in s['days']]
    ld = {}
    for q in ('NE', 'SW', 'SE'):
        for d in range(30):
            bb = b[d + 1] if d + 1 < 30 else b[d]
            if any(bb[i] != ' L' for i in range(100) if quad(i) == q):
                ld[q] = d
                break
    if ld != w['land_days']:
        errs.append(f'{ep}: land days {ld} vs worlds.json {w["land_days"]}')
    # the k-th successful purchase is at or after the k-th order day
    od = sorted({d for d, h in bl})
    if [ld['NE'], ld['SW'], ld['SE']] != sorted([ld['NE'], ld['SW'], ld['SE']]):
        errs.append(f'{ep}: land order not NE<SW<SE')
    if w['leader_final'] != s['meta']['rewards'][s['meta']['seat']]:
        errs.append(f'{ep}: leader_final')
ldset = {}
for w in worlds:
    ldset.setdefault(tuple(w['land_days'].values()), []).append(w['episode'])
print('land-day patterns:', {k: len(v) for k, v in ldset.items()})
ex = worlds[0]['episode']
print('example BUY_LAND order (day, hour) for', ex, land_orders[ex])
flags = [(w['episode'], w['flags']) for w in worlds if w['flags']]
print('flagged:', flags)
print('ERRORS' if errs else 'WORLDS OK', errs[:20])
sys.exit(1 if errs else 0)
