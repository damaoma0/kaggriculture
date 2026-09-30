"""Compare verify_chains_main.json (independent re-derivation) with the reviewed report's events.jsonl.gz, per
seat-game, and print the dshed-0 / 'shed between' artifact breakdown. Stored data only."""
import gzip
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))


def dsh(p):
    return min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED)


def mh(p, q):
    return abs(p[0] - q[0]) + abs(p[1] - q[1])


def quad(p):
    return ('N' if p[1] < 5 else 'S') + ('W' if p[0] < 5 else 'E')


mine = json.load(open(os.path.join(HERE, 'verify_chains_main.json'), encoding='utf-8'))
theirs = {}
with gzip.open(os.path.join(HERE, 'events.jsonl.gz'), 'rt', encoding='utf-8') as f:
    for line in f:
        r = json.loads(line)
        k = f"{r['episode']}:{r['seat']}"
        if k in mine:
            theirs[k] = r

rows = []
for k, m in mine.items():
    r = theirs[k]
    F = r['fert']
    fl = [x for x in F if x['src'] == 'field']
    ch = [x for x in fl if not x['shed_between']]
    lay_a = [(x, y) for day in r['layout'] for kk, x, y in day if kk in ('COW', 'SHEEP', 'GOOSE')]
    lay_c = [(x, y) for day in r['layout'] for kk, x, y in day if kk in ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON')]
    t = {
        'collect': len(r['collect']), 'pick_units': sum(p['n'] for p in r['pick']), 'applied': len(F),
        'field_lifo': len(fl), 'field_fifo': sum(x['fifo_src'] == 'field' for x in F), 'direct_theirs': len(ch),
        'theirs_mean_dA': sum(dsh(x['A']) for x in ch) / len(ch), 'theirs_mean_dC': sum(dsh(x['C']) for x in ch) / len(ch),
        'theirs_closer': sum(dsh(x['A']) < dsh(x['C']) for x in ch) / len(ch),
        'theirs_onpath': sum(dsh(x['A']) + mh(x['A'], x['C']) == dsh(x['C']) for x in ch) / len(ch),
        'lay_animal_n': len(lay_a), 'lay_animal_mean_dshed': sum(dsh(p) for p in lay_a) / len(lay_a),
        'lay_crop_n': len(lay_c), 'lay_crop_mean_dshed': sum(dsh(p) for p in lay_c) / len(lay_c),
        'dump': sum(1 for x in r['fates'] if x['fate'] == 'autodump'),
        'deposit_units': sum(d['n'] for d in r['dep']),
        'moves': sum(u['moves'] for u in r['unit_days']),
    }
    print(f'== {k} teams={m["teams"]} agents={m["agents"]} obs_player={m["obs_player"]} rewards={m["rewards"]} '
          f'steps={m["n_steps"]} anomalies={m["anomaly"]} boundary-inferred unit-steps={m["bnd_inferred"]}')
    for key, tv in t.items():
        mv = m[key]
        flag = '' if (abs(mv - tv) < 1e-9) else '   <-- DIFF'
        print(f'   {key:24s} mine {mv:10.4f}   theirs {tv:10.4f}{flag}')
    print(f'   field FERTILIZE flagged after-shed (theirs def): {m["field_after_shed_theirs"]}; of which animal ON a '
          f'shed tile (dshed 0): {m["after_theirs_animal_dshed0"]}; after-shed under theirs but NOT under ENTERED: '
          f'{m["after_theirs_but_not_entered"]}')
    print(f'   ENTERED def: direct {m["direct_entered"]}/{m["n_fert"]} = {m["direct_entered"] / m["n_fert"]:.3f} '
          f'(theirs {m["direct_theirs"] / m["n_fert"]:.3f}); mean dA {m["entered_mean_dA"]:.2f} dC {m["entered_mean_dC"]:.2f}'
          f' closer {m["entered_closer"]:.3f} onpath {m["entered_onpath"]:.3f}; dA dist {m["entered_dA_dist"]}')
    print(f'   outbound: straight-to-animal (chain collects) theirs-def {m["theirs_straight_to_animal"]:.3f} '
          f'entered-def {m["entered_straight_to_animal"]:.3f}; pure outbound leg shed->A->C == dshed(C): '
          f'theirs-def {m["theirs_pure_outbound_leg"]:.3f} entered-def {m["entered_pure_outbound_leg"]:.3f}')
    print(f'   trips(theirs-def) {m["theirs_trips"]} stock>=1 at last shed step {m["theirs_trip_stock_ge1"]:.3f}; '
          f'collect dshed0 {m["collect_dshed0"]}/{m["collect"]}; layout animal dshed0 {m["lay_animal_dshed0"]}/'
          f'{m["lay_animal_n"]}; animal quad {m["lay_animal_quad"]} crop quad {m["lay_crop_quad"]}')
    rows.append((k, m, t))

# pooled over the sample
def pool(key_m, key_n=None):
    return sum(m[key_m] for _, m, _ in rows)

N = sum(m['n_fert'] for _, m, _ in rows)
print('\nPOOLED over', len(rows), 'seat-games, n FERTILIZE =', N)
print('  field LIFO %.3f  FIFO %.3f  direct(theirs) %.3f  direct(entered) %.3f  homog %.3f' % (
    pool('field_lifo') / N, pool('field_fifo') / N, pool('direct_theirs') / N, pool('direct_entered') / N,
    pool('homog') / N))
fa = pool('field_after_shed_theirs')
print('  after-shed (theirs) %d, of which animal on shed tile %d, not after-shed under ENTERED %d' % (
    fa, pool('after_theirs_animal_dshed0'), pool('after_theirs_but_not_entered')))
for tag in ('theirs', 'entered'):
    n = pool(f'direct_{tag}')
    w = lambda k: sum(m[f'{tag}_{k}'] * m[f'direct_{tag}'] for _, m, _ in rows) / n
    print(f'  {tag:8s} chains n={n}: mean dA {w("mean_dA"):.2f} dC {w("mean_dC"):.2f} closer {w("closer"):.3f} '
          f'onpath {w("onpath"):.3f} straight-to-animal {w("straight_to_animal"):.3f} pure-outbound-leg '
          f'{w("pure_outbound_leg"):.3f} samequad {w("samequad"):.3f}')
la = pool('lay_animal_n')
lc = pool('lay_crop_n')
print('  layout animal tile-days %d mean dshed %.2f dshed0 share %.3f; crop %d mean %.2f' % (
    la, sum(m['lay_animal_mean_dshed'] * m['lay_animal_n'] for _, m, _ in rows) / la, pool('lay_animal_dshed0') / la,
    lc, sum(m['lay_crop_mean_dshed'] * m['lay_crop_n'] for _, m, _ in rows) / lc))
q = {qq: sum(m['lay_animal_quad'][qq] for _, m, _ in rows) / la for qq in ('NW', 'NE', 'SW', 'SE')}
print('  animal quad shares', {k: round(v, 3) for k, v in q.items()})
tr = sum(m['theirs_trips_valid_shed'] for _, m, _ in rows)
print('  trip stock>=1 (theirs chains) %.3f of %d trips' % (
    sum(m['theirs_trip_stock_ge1'] * m['theirs_trips_valid_shed'] for _, m, _ in rows) / tr, tr))
