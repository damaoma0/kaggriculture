"""Does a V9-lite tape switch after a late Yarn reveal strand sheep that y3's late-Yarn layer is servicing?
Compares the diagnostic V9-lite+y3 runs (agents/mgt_v9lite_diag.py: exposes y3's overlay counters and V9's switch days)
with y3 on the same recorded worlds. usage: v9_strand_interaction.py"""
import gzip, json, glob, numpy as np
from pathlib import Path


def load(pat):
    d = {}
    for f in glob.glob(pat):
        r = json.load(open(f))
        d[str(r['episode'])] = r
    return d


diag = load('results/fresh/ladder_panel/mgt_v9lite_diag/*.json')
lite = load('results/fresh/ladder_panel/mgt_v9litepkg3/*.json')
y3 = {**load('results/fresh/kaggle_remote_y2/y3verify/output/*/out/mgt_y3/*.json'),
      **load('results/fresh/kaggle_remote_y2/p2750eval/output/*/out/mgt_y3/*.json')}
same = sum(1 for e in diag if e in lite and round(diag[e]['final']) == round(lite[e]['final']) and round(diag[e]['rival']) == round(lite[e]['rival']))
print(f'diagnostic copy plays identically to the package in {same} of {len(diag)} worlds')


def world(ep):
    for sub in ('p2750', '56368334'):
        p = Path(f'data/ladder_panel/{sub}/{ep}.json.gz')
        if p.exists():
            return json.load(gzip.open(p, 'rt', encoding='utf-8'))


rows = []
for e, r in diag.items():
    if e not in y3:
        continue
    ov, oy = r['overlay'], y3[e]['overlay']
    sw = sorted(int(k.split('_d')[1]) for k in ov if k.startswith('v9_route_d'))
    shops = world(e)['shops']                  # 31 day-start lists of visible shops
    yarn_days = []                             # days on which a (further) Yarn Store became visible
    for d in range(1, len(shops)):
        if shops[d].count('YARN_STORE') > shops[d - 1].count('YARN_STORE'):
            yarn_days.append(d)
    late_yarn = [d for d in yarn_days if d >= 12]
    after = [d for d in sw if any(y <= d for y in late_yarn)]
    rows.append(dict(ep=e, switches=sw, late_yarn=late_yarn, switch_after_late_yarn=bool(after),
                     d_margin=r['margin'] - y3[e]['margin'],
                     d_sheep_lost=ov.get('sheep_lost', 0) - oy.get('sheep_lost', 0),
                     d_orphan_days=ov.get('orphan_days', 0) - oy.get('orphan_days', 0),
                     d_yarn_service=ov.get('yarn_service', 0) - oy.get('yarn_service', 0),
                     d_topups=ov.get('topup_tasks', 0) - oy.get('topup_tasks', 0),
                     d_wool=r['sold'].get('WOOL', 0) - y3[e]['sold'].get('WOOL', 0)))
print(f'{len(rows)} worlds; with a V9 switch {sum(1 for x in rows if x["switches"])}; '
      f'switch after a late Yarn reveal {sum(1 for x in rows if x["switch_after_late_yarn"])}')
for grp, sel in (('switch after late Yarn', [x for x in rows if x['switch_after_late_yarn']]),
                 ('other V9 switches', [x for x in rows if x['switches'] and not x['switch_after_late_yarn']])):
    if not sel:
        print(grp, 'none'); continue
    f = lambda k: np.mean([x[k] for x in sel])
    print(f'{grp:24s} n={len(sel):2d} margin {f("d_margin"):+7.0f}  sheep lost {f("d_sheep_lost"):+.2f}  orphan days '
          f'{f("d_orphan_days"):+.2f}  yarn service {f("d_yarn_service"):+.1f}  top-ups {f("d_topups"):+.1f}  wool sold {f("d_wool"):+.1f}')
for x in sorted(rows, key=lambda x: x['d_margin'])[:6]:
    print('  worst', x)
json.dump(rows, open('results/fresh/newphase_20260923/v9_strand_interaction.json', 'w'), indent=1)
