"""xfix: planting fates. For every leader planting event (day, tile, crop) of data/leader_semantics, its fate in T
(results/fresh/xfix_20260925/full/<arm>/<ep>.json 'pf', the pf_log of agents/mgt_lead_fix.py = logging only) and the code
path (agents/mgt_lead.py _plan / dispatcher). Value = the planting's base potential units (deep_decomp.pot: full water,
no fertilizer, harvested by day 29) x the leader's average sale price of the crop in that world.
usage: xfix_pf_report.py [arm=Fpf] -> results/fresh/xfix_20260925/pf_report_<arm>.txt"""
import glob, gzip, json, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, 'results/fresh/t_gap_20260925')
import deep_decomp as DD
arm = sys.argv[1] if len(sys.argv) > 1 else 'Fpf'
OUT = Path('results/fresh/xfix_20260925')
PER = [(0, 5), (6, 11), (12, 17), (18, 23), (24, 29)]
PATH = {
    'leader tile, same day': 'planted as the leader did',
    'leader tile, late': '_plan keeps the job on the leader tile; not executed on day pd (labour / seeds / land)',
    'remapped: live crop growing': '_plan: our tile holds a crop not finished and not at harvest age (maxday-1) -> _free_tile',
    'remapped: live crop harvestable': '_plan: one-time crop harvestable but younger than maxday-1 (leader harvested it early) -> _free_tile',
    'remapped: structure': '_plan: our tile holds a structure / animal -> _free_tile',
    'remapped: tile taken': '_plan: another job (build / planting) already on the tile this step -> _free_tile',
    'remapped: locked': '_plan: tile locked (land not bought) -> _free_tile',
    'remapped: other': '_plan remap (sem4 / unrecorded reason)',
    'skipped: plant_cutoff': '_plan: CFG plant_cutoff (no full harvest reachable by day 29)',
    'skipped: cohort_gone': '_plan: pd < d and the leader board no longer shows the crop on its tile (no catch-up)',
    'skipped: window_expired': '_plan: late window (CFG late: strawberry 6, tomato 5, melon 3, wheat / carrot 1 days) passed',
    'skipped: no_free_tile': '_plan: tile unusable and _free_tile found no tile outside the 2-day plant reservation',
    'skipped: wait_land': '_plan: waiting for a land purchase that never came',
    'skipped: job, no seeds': 'job every step but no seeds held (market buys seeds for today\'s jobs only, cash-bound)',
    'skipped: job, never assigned': 'job with seeds but no unit took the task (distance-first greedy / plant pipeline too late: cost None after hour+c+len>24)',
    'skipped: job, assigned not planted': 'a unit was assigned but the day ended before the PLANT (walking / reassigned)',
    'not considered': 'event outside T\'s range (e.g. T already gone / day 29)',
}


def fate(r):
    if r is None:
        return 'not considered', None
    st = [v for k, v in sorted(r['days'].items(), key=lambda kv: int(kv[0]))]
    if 'planted' in st:
        k = int(r.get('planted_day', r['pd'])) - int(r['pd'])
        if not r.get('remapped'):
            return ('leader tile, same day' if k <= 0 else 'leader tile, late'), k
        why = r.get('remap') or ''
        if why.startswith('live_'):
            return ('remapped: live crop harvestable' if why.endswith('harvestable') else 'remapped: live crop growing'), k
        return {'structure': 'remapped: structure', 'tile_taken_by_another_job': 'remapped: tile taken',
                'locked': 'remapped: locked'}.get(why, 'remapped: other'), k
    last = st[-1] if st else None
    if last == 'job':
        if r.get('seed_steps', 0) == 0:
            return 'skipped: job, no seeds', None
        if r.get('assign_steps', 0) == 0:
            return 'skipped: job, never assigned', None
        return 'skipped: job, assigned not planted', None
    for s in ('plant_cutoff', 'cohort_gone', 'window_expired', 'no_free_tile', 'wait_land'):
        if s in st:
            return 'skipped: ' + s, None
    return 'skipped: ' + str(last), None


rows = defaultdict(lambda: Counter())
val = defaultdict(lambda: Counter())
lates = Counter()
n_games = 0
for f in sorted(glob.glob(str(OUT / f'full/{arm}/*.json'))):
    R = json.load(open(f))
    pf = R.get('pf') or {}
    team, ep = R['game'].split(':')
    sem = json.load(gzip.open(f'data/leader_semantics/{team}/{ep}.json.gz', 'rt', encoding='utf-8'))
    Lr = json.load(open(f'results/fresh/xopen_20260925/g1/LEADER/{ep}.json'))
    price = {}
    for p in DD.CROPS:
        u = sum(d.get('sold', {}).get(p, 0) for d in Lr['days'])
        price[p] = (sum(d.get('rev', {}).get(p, 0) for d in Lr['days']) / u) if u else DD.BASE[p]
    n_games += 1
    for d, day in enumerate(sem['days']):
        for crop, tiles in day['planted'].items():
            for tt in tiles:
                fz, k = fate(pf.get(f'{d}:{tt}'))
                per = next(i for i, (a, b) in enumerate(PER) if a <= d <= b)
                rows[(crop, per)][fz] += 1
                val[(crop, per)][fz] += DD.pot(crop, d) * price[crop]
                if fz == 'leader tile, late':
                    lates[k] += 1
fates = sorted({fz for c in rows.values() for fz in c}, key=lambda x: (not x.startswith('leader'), not x.startswith('remapped'), x))
out = [f'planting fates in {arm} ({n_games} games): count per game (value per game = base potential units x leader price)']
for crop in DD.CROPS:
    tot = sum((rows[(crop, p)] for p in range(len(PER))), Counter())
    if not tot:
        continue
    tv = sum((val[(crop, p)] for p in range(len(PER))), Counter())
    out.append(f'\n== {crop}: {sum(tot.values()) / n_games:.1f} leader plantings a game')
    out.append('  fate | ' + ' | '.join(f'd{a}-{b}' for a, b in PER) + ' | all (value)')
    for fz in fates:
        if not tot.get(fz):
            continue
        out.append(f'  {fz:34s} | ' + ' | '.join(f'{rows[(crop, p)].get(fz, 0) / n_games:5.1f}' for p in range(len(PER)))
                   + f' | {tot[fz] / n_games:5.1f} ({tv[fz] / n_games:,.0f})')
allc = sum(rows.values(), Counter())
allv = sum(val.values(), Counter())
out.append('\n== all crops, per game: count (value) and the code path')
for fz in fates:
    if allc.get(fz):
        out.append(f'  {fz:34s} {allc[fz] / n_games:6.1f} ({allv[fz] / n_games:7,.0f})  <- {PATH.get(fz, "")}')
out.append('  late by days (leader tile): ' + ', '.join(f'{k}: {v / n_games:.1f}' for k, v in sorted(lates.items())))
print('\n'.join(out))
(OUT / f'pf_report_{arm}.txt').write_text('\n'.join(out) + '\n', encoding='utf-8')
