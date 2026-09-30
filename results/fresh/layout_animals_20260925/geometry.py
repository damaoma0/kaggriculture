"""Where do animals sit relative to the shed, compared with crops? Stored data only (no games, no engine).

Leaders: data/leader_semantics/<team>/<episode>.json.gz (day-start boards, maintenance.FERTILIZE tiles, built/dug,
labour.command_counts, market). 'co' is resolved per tile from the build history (BUILD_COOP -> empty coop, BUILD_PASTURE
-> cow, since cows/sheep need a pasture and geese a coop); 'co' with no build record -> co_unknown.
Ours: results/fresh/lead_cycles/<agent>/<episode>.json records that carry 'boards' (lead_cycles.py 2026-09-25 format:
'co' = cow, 'Co'/'Pa' = empty coop/pasture, 'we' = weed; per-tile crop states -> fertilized tiles).

Distance to shed = Manhattan distance to the nearest of the four shed tiles (4,4),(5,4),(4,5),(5,5) (those tiles are
farmable, distance 0). Quadrants: 1st NW x0-4,y0-4; 2nd NE x5-9,y0-4; 3rd SW x0-4,y5-9; 4th SE x5-9,y5-9. Each
quadrant has the same distance profile: 1 tile at d0, 2 at d1, 3 at d2, ... mean 4.0; uniform share d<=2 = 6/25 = 24%.

usage: .venv/Scripts/python.exe results/fresh/layout_animals_20260925/geometry.py
Output: geometry.txt, geometry.json next to this file.
"""
import glob
import gzip
import json
import os
import statistics as st
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
OUT = os.path.dirname(os.path.abspath(__file__))
TEAMS = [('16732748', 'DSM'), ('16623559', 'DECEM'), ('16770421', 'Vadim'), ('16730612', 'MG'),
         ('16681125', 'MMPQ'), ('16915014', 'Boey')]
OURS = ['mgt_lpv_dep6', 'mgt_lpv_q4']
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
WIN = [(0, 5), (6, 11), (12, 17), (18, 23), (24, 29)]
WNAME = ['0-5', '6-11', '12-17', '18-23', '24-29']
QN = ['1st NW', '2nd NE', '3rd SW', '4th SE']
ANIMALS = ('sheep', 'cow', 'goose')
STRUCTS = ('pasture_empty', 'coop_empty')
CROPS = ('ST', 'TO', 'ME', 'WH', 'CA')
ROWS = list(ANIMALS) + ['ANIMALS', 'co_unknown'] + list(STRUCTS) + ['ANIM+STRUCT'] + list(CROPS) + ['CROPS', 'OCCUPIED']
GROUP = {'ANIMALS': ANIMALS, 'ANIM+STRUCT': ANIMALS + STRUCTS, 'CROPS': CROPS,
         'OCCUPIED': ANIMALS + STRUCTS + CROPS + ('co_unknown',)}


def xy(i):
    return i % 10, i // 10


def dist(i):
    x, y = xy(i)
    return min(abs(x - a) + abs(y - b) for a, b in SHED)


def quad(i):
    x, y = xy(i)
    return (x >= 5) + 2 * (y >= 5)


def win(d):
    return d // 6


DIST = [dist(i) for i in range(100)]
QUAD = [quad(i) for i in range(100)]


def detour(c, animals):
    """extra steps to pass by an animal on the way from the shed to tile c (0 = an animal lies on a shortest path)."""
    if not animals:
        return None
    cx, cy = xy(c)
    best = 99
    for a in animals:
        ax, ay = xy(a)
        via = min(abs(sx - ax) + abs(sy - ay) for sx, sy in SHED) + abs(ax - cx) + abs(ay - cy)
        best = min(best, via - DIST[c])
    return best


class Acc:
    def __init__(self):
        self.n = defaultdict(int)            # (w, cat) -> tile-days
        self.sd = defaultdict(int)           # (w, cat) -> sum of distances
        self.h = defaultdict(Counter)        # (w, cat) -> distance histogram
        self.qn = defaultdict(int)           # (q, cat) -> tile-days (quadrant unlocked)
        self.qsd = defaultdict(int)
        self.qh = defaultdict(Counter)
        self.qwn = defaultdict(int)          # (q, w, cat)
        self.qwsd = defaultdict(int)
        self.qdays = Counter()               # q -> game-days unlocked
        self.ring = defaultdict(int)         # (w, ring, cat) -> tile-days, ring in 0,1,2
        self.gd = Counter()                  # w -> game-days
        self.games = 0
        self.game_rows = []                  # per game dict
        self.fert = []                       # per game fertilizer dict
        self.unlock = defaultdict(list)      # q -> unlock day per game
        self.other = Counter()
        self.visit = Counter()               # (group, op) -> tile-days with that effective op (leaders only)

    def board(self, d, cats):
        w = win(d)
        self.gd[w] += 1
        unlocked_q = set(QUAD[i] for i in range(100) if cats[i] != 'locked')
        for q in unlocked_q:
            self.qdays[q] += 1
        for i, c in enumerate(cats):
            dd, q = DIST[i], QUAD[i]
            keys = [c] + [g for g, mem in GROUP.items() if c in mem]
            for k in keys:
                self.n[(w, k)] += 1
                self.sd[(w, k)] += dd
                self.h[(w, k)][dd] += 1
                if q in unlocked_q:
                    self.qn[(q, k)] += 1
                    self.qsd[(q, k)] += dd
                    self.qh[(q, k)][dd] += 1
                    self.qwn[(q, w, k)] += 1
                    self.qwsd[(q, w, k)] += dd
                if dd <= 2:
                    self.ring[(w, dd, k)] += 1


def classify_leader(board, lastbuild):
    cats = []
    for i, lab in enumerate(board):
        if lab == ' L':
            cats.append('locked')
        elif lab == ' .':
            cats.append('empty')
        elif lab in CROPS:
            cats.append(lab)
        elif lab == 'sh':
            cats.append('sheep')
        elif lab == 'go':
            cats.append('goose')
        elif lab == 'pa':
            cats.append('pasture_empty')
        elif lab == 'co':
            b = lastbuild.get(i)
            cats.append('coop_empty' if b == 'BUILD_COOP' else 'cow' if b == 'BUILD_PASTURE' else 'co_unknown')
        else:
            cats.append('other:' + lab)
    return cats


def classify_ours(board):
    m = {' L': 'locked', ' .': 'empty', 'we': 'empty', 'sh': 'sheep', 'go': 'goose', 'co': 'cow',
         'Pa': 'pasture_empty', 'Co': 'coop_empty'}
    cats = []
    for k in range(0, 200, 2):
        lab = board[k:k + 2]
        cats.append(lab if lab in CROPS else m.get(lab, 'other:' + lab))
    return cats


def game_row(acc, boards_cats, extra):
    a = [DIST[i] for d, cats in enumerate(boards_cats) if d >= 6 for i, c in enumerate(cats) if c in ANIMALS]
    c = [DIST[i] for d, cats in enumerate(boards_cats) if d >= 6 for i, c_ in enumerate(cats) if c_ in CROPS]
    ad0 = sum(1 for d, cats in enumerate(boards_cats) if d >= 6 for i, x in enumerate(cats) if x in ANIMALS and DIST[i] == 0)
    row = dict(anim_mean=st.mean(a) if a else None, crop_mean=st.mean(c) if c else None, anim_td=len(a),
               crop_td=len(c), anim_d0=ad0)
    row.update(extra)
    acc.game_rows.append(row)


def fert_game(acc, per_day):
    """per_day: list of (fertilized tiles, live animal tiles, live crop tiles)."""
    fd, fdet, cdet, nf_noanim = [], [], [], 0
    for ftiles, an, crops in per_day:
        for t in ftiles:
            fd.append(DIST[t])
            dt = detour(t, an)
            if dt is None:
                nf_noanim += 1
            else:
                fdet.append(dt)
        for t in crops:
            dt = detour(t, an)
            if dt is not None:
                cdet.append(dt)
    return dict(fert_n=len(fd), fert_dist_sum=sum(fd), fert_det=Counter(fdet), crop_det=Counter(cdet),
                fert_noanimal=nf_noanim)


def run_leaders():
    accs = {}
    files_used = {}
    for tid, name in TEAMS:
        acc = Acc()
        files = sorted(glob.glob(os.path.join(ROOT, 'data', 'leader_semantics', tid, '*.json.gz')))
        files_used[name] = (os.path.join('data', 'leader_semantics', tid), len(files))
        cash_ok = 0
        for f in files:
            with gzip.open(f, 'rt', encoding='utf-8') as fh:
                g = json.load(fh)
            cash_ok += bool(g['meta'].get('cash_match'))
            lastbuild = {}
            bc, fertday = [], []
            collect = fert_applied = 0
            unl = {}
            for d, day in enumerate(g['days']):
                cats = classify_leader(day['board'], lastbuild)
                for x in cats:
                    if x.startswith('other:'):
                        acc.other[x] += 1
                acc.board(d, cats)
                bc.append(cats)
                for q in range(4):
                    if q not in unl and any(cats[i] != 'locked' for i in range(100) if QUAD[i] == q):
                        unl[q] = d
                an = [i for i, x in enumerate(cats) if x in ANIMALS]
                cr = [i for i, x in enumerate(cats) if x in CROPS]
                ft = (day.get('maintenance') or {}).get('FERTILIZE') or []
                fertday.append((ft, an, cr))
                mt = day.get('maintenance') or {}
                hv = set((day.get('harvested') or {}).get('tiles') or [])
                for grp, tiles in (('ANIMALS', an), ('CROPS', cr)):
                    for t in tiles:
                        ops = [o for o in ('WATER', 'FEED', 'CARE', 'FERTILIZE') if t in (mt.get(o) or [])]
                        if t in hv:
                            ops.append('HARVEST')
                        acc.visit[(grp, 'tile_days')] += 1
                        acc.visit[(grp, 'visited')] += bool(ops)
                        acc.visit[(grp, 'ops')] += len(ops)
                        for o in ops:
                            acc.visit[(grp, o)] += 1
                collect += ((day.get('labour') or {}).get('command_counts') or {}).get('COLLECT_FERTILIZER', 0)
                fert_applied += len(ft)
                for t in (day.get('dug') or []):
                    lastbuild.pop(t, None)
                for kind, tiles in (day.get('built') or {}).items():
                    for t in tiles:
                        lastbuild[t] = kind
            mk = [day.get('market') or {} for day in g['days']]
            fb = sum((m.get('bought_units') or {}).get('FERTILIZER', 0) for m in mk)
            fs = sum((m.get('sold_units') or {}).get('FERTILIZER', 0) for m in mk)
            for q, d in unl.items():
                acc.unlock[q].append(d)
            game_row(acc, bc, dict(episode=g['meta']['episode']))
            fg = fert_game(acc, fertday)
            fg.update(collect_cmds=collect, fert_tiles=fert_applied, fert_bought=fb, fert_sold=fs,
                      live_animal_days=sum(len(a) for _, a, _ in fertday))
            acc.fert.append(fg)
            acc.games += 1
        acc.cash_ok = cash_ok
        accs[name] = acc
    return accs, files_used


def run_ours():
    accs, files_used = {}, {}
    for agent in OURS:
        acc = Acc()
        d0 = os.path.join(ROOT, 'results', 'fresh', 'lead_cycles', agent)
        files = sorted(glob.glob(os.path.join(d0, '*.json')))
        used = 0
        for f in files:
            with open(f, encoding='utf-8') as fh:
                r = json.load(fh)
            if not r.get('boards'):
                continue
            used += 1
            bc, fertday = [], []
            states = r.get('states') or []
            for d, b in enumerate(r['boards']):
                cats = classify_ours(b)
                for x in cats:
                    if x.startswith('other:'):
                        acc.other[x] += 1
                acc.board(d, cats)
                bc.append(cats)
                an = [i for i, x in enumerate(cats) if x in ANIMALS]
                cr = [i for i, x in enumerate(cats) if x in CROPS]
                ft = []
                if d + 1 < len(states):
                    s0, s1 = states[d], states[d + 1]
                    for k, v in s1.items():
                        p = s0.get(k)
                        if p and p[0] == v[0] and p[1] == v[1]:
                            if v[3] > p[3]:
                                ft.append(int(k))
                        elif v[1] == d and v[3] >= d:        # planted and fertilized the same day
                            ft.append(int(k))
                fertday.append((ft, an, cr))
            for q in range(4):
                days = [d for d, u in enumerate(r.get('unlocked') or []) if ['NW', 'NE', 'SW', 'SE'][q] in u]
                if days:
                    acc.unlock[q].append(days[0])
            wk = r.get('work') or []
            collect = sum(v.get('op_COLLECT_FERTILIZER', 0) for day in wk for v in day.values())
            fcmd = sum(v.get('op_FERTILIZE', 0) for day in wk for v in day.values())
            game_row(acc, bc, dict(episode=r['panel'].get('episode'), margin=r['panel'].get('margin')))
            fg = fert_game(acc, fertday)
            fg.update(collect_cmds=collect, fert_tiles=fg['fert_n'], fert_cmds=fcmd, fert_bought=None,
                      fert_sold=(r.get('sold') or {}).get('FERTILIZER', 0),
                      live_animal_days=sum(len(a) for _, a, _ in fertday))
            acc.fert.append(fg)
            acc.games += 1
        files_used[agent] = (os.path.relpath(d0, ROOT), used)
        acc.cash_ok = None
        accs[agent] = acc
    return accs, files_used


def merge(accs):
    tot = Acc()
    for a in accs.values():
        for attr in ('n', 'sd', 'qn', 'qsd', 'qwn', 'qwsd', 'ring'):
            for k, v in getattr(a, attr).items():
                getattr(tot, attr)[k] += v
        for attr in ('h', 'qh'):
            for k, v in getattr(a, attr).items():
                getattr(tot, attr)[k].update(v)
        tot.gd.update(a.gd)
        tot.qdays.update(a.qdays)
        tot.games += a.games
        tot.game_rows += a.game_rows
        tot.fert += a.fert
        for q, v in a.unlock.items():
            tot.unlock[q] += v
        tot.other.update(a.other)
        tot.visit.update(a.visit)
    return tot


def fmt(x, nd=2):
    return '   -' if x is None else f'{x:.{nd}f}'


def pct(a, b):
    return '   -' if not b else f'{100 * a / b:4.0f}%'


def table_distance(acc, L):
    L.append(f'  mean distance to shed (tiles per game-day in brackets); uniform unlocked tile = 4.00')
    L.append('  ' + f'{"asset":13s}' + ''.join(f'{w:>14s}' for w in WNAME + ['all']))
    gdall = sum(acc.gd.values())
    for row in ROWS:
        cells = []
        for w in range(5):
            n = acc.n[(w, row)]
            cells.append(f'{fmt(acc.sd[(w, row)] / n) if n else "   -"} ({n / max(1, acc.gd[w]):4.1f})')
        n = sum(acc.n[(w, row)] for w in range(5))
        s = sum(acc.sd[(w, row)] for w in range(5))
        cells.append(f'{fmt(s / n) if n else "   -"} ({n / max(1, gdall):4.1f})')
        if n:
            L.append('  ' + f'{row:13s}' + ''.join(f'{c:>14s}' for c in cells))


def table_shares(acc, L):
    L.append('  share of tile-days at distance 0 / <=1 / <=2 (uniform unlocked tile: 4% / 12% / 24%)')
    L.append('  ' + f'{"group":13s}' + ''.join(f'{w:>19s}' for w in WNAME + ['all']))
    for row in ('ANIMALS', 'sheep', 'cow', 'goose', 'ANIM+STRUCT', 'CROPS', 'ST', 'TO', 'ME', 'WH', 'CA'):
        cells = []
        for ws in [[w] for w in range(5)] + [list(range(5))]:
            h = Counter()
            for w in ws:
                h.update(acc.h[(w, row)])
            n = sum(h.values())
            cells.append('   -' if not n else
                         f'{100 * h[0] / n:3.0f}/{100 * (h[0] + h[1]) / n:3.0f}/{100 * (h[0] + h[1] + h[2]) / n:3.0f}%')
        L.append('  ' + f'{row:13s}' + ''.join(f'{c:>19s}' for c in cells))


def table_rings(acc, L):
    L.append('  ring occupancy, tiles per game-day: d0 = the 4 shed tiles; d1-2 = the 20 tiles at distance 1-2')
    L.append('  (unlocked | animals | empty pasture/coop | crops | empty)')
    L.append('  ' + f'{"window":8s}' + f'{"d0 (4 tiles)":>36s}' + f'{"d1-2 (20 tiles)":>40s}')
    for w in range(5):
        gd = max(1, acc.gd[w])
        cells = []
        for rings in ([0], [1, 2]):
            tot = sum(acc.ring[(w, r, c)] for r in rings for c in
                      ('empty',) + ANIMALS + STRUCTS + CROPS + ('co_unknown',)) + \
                sum(v for (w_, r_, c_), v in acc.ring.items() if w_ == w and r_ in rings and c_.startswith('other:'))
            an = sum(acc.ring[(w, r, 'ANIMALS')] for r in rings)
            stc = sum(acc.ring[(w, r, c)] for r in rings for c in STRUCTS)
            cr = sum(acc.ring[(w, r, 'CROPS')] for r in rings)
            em = sum(acc.ring[(w, r, 'empty')] for r in rings)
            cells.append(f'{tot / gd:5.1f} | {an / gd:4.1f} | {stc / gd:4.1f} | {cr / gd:4.1f} | {em / gd:4.1f}')
        L.append('  ' + f'{WNAME[w]:8s}' + f'{cells[0]:>36s}' + f'{cells[1]:>40s}')


def table_quadrants(acc, L):
    L.append('  per quadrant, days the quadrant is unlocked; distance = to the quadrant\'s inner (shed) corner')
    L.append('  ' + f'{"quadrant":9s}{"unlock d":>9s}{"anim/gd":>8s}{"crop/gd":>8s}{"anim mean":>10s}{"crop mean":>10s}'
             f'{"anim d0/<=2":>13s}{"crop d0/<=2":>13s}{"corner tile: anim/struct/crop/empty":>38s}')
    for q in range(4):
        qd = acc.qdays[q]
        if not qd:
            continue
        ud = acc.unlock.get(q) or []
        uds = f'{st.median(ud):.0f}' if ud else '-'
        ha, hc = acc.qh[(q, 'ANIMALS')], acc.qh[(q, 'CROPS')]
        na, nc = sum(ha.values()), sum(hc.values())
        corner = {k: acc.qh[(q, k)][0] for k in ('ANIMALS', 'CROPS', 'empty')}
        cs = sum(acc.qh[(q, c)][0] for c in STRUCTS)
        L.append('  ' + f'{QN[q]:9s}{uds:>9s}{na / qd:8.1f}{nc / qd:8.1f}'
                 f'{fmt(acc.qsd[(q, "ANIMALS")] / na) if na else "   -":>10s}{fmt(acc.qsd[(q, "CROPS")] / nc) if nc else "   -":>10s}'
                 f'{(pct(ha[0], na) + "/" + pct(ha[0] + ha[1] + ha[2], na)) if na else "-":>13s}'
                 f'{(pct(hc[0], nc) + "/" + pct(hc[0] + hc[1] + hc[2], nc)) if nc else "-":>13s}'
                 f'{pct(corner["ANIMALS"], qd) + "/" + pct(cs, qd) + "/" + pct(corner["CROPS"], qd) + "/" + pct(corner["empty"], qd):>38s}')


def table_quadrant_windows(acc, L):
    L.append('  animal mean distance / crop mean distance per quadrant and window (- = none)')
    L.append('  ' + f'{"quadrant":9s}' + ''.join(f'{w:>13s}' for w in WNAME))
    for q in range(4):
        cells = []
        for w in range(5):
            na, nc = acc.qwn[(q, w, 'ANIMALS')], acc.qwn[(q, w, 'CROPS')]
            a = fmt(acc.qwsd[(q, w, 'ANIMALS')] / na) if na else '   -'
            c = fmt(acc.qwsd[(q, w, 'CROPS')] / nc) if nc else '   -'
            cells.append(f'{a}/{c}')
        L.append('  ' + f'{QN[q]:9s}' + ''.join(f'{c:>13s}' for c in cells))


def quant(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))]


def table_games(acc, L):
    rows = [r for r in acc.game_rows if r['anim_mean'] is not None and r['crop_mean'] is not None]
    if not rows:
        L.append('  no game with both animals and crops on days 6-29')
        return
    diff = [r['anim_mean'] - r['crop_mean'] for r in rows]
    L.append(f'  game level, days 6-29 (n={len(rows)} of {acc.games} games with animals): animal mean {st.mean(r["anim_mean"] for r in rows):.2f}, '
             f'crop mean {st.mean(r["crop_mean"] for r in rows):.2f}; animal-minus-crop mean {st.mean(diff):+.2f} '
             f'(p10 {quant(diff, .1):+.2f}, median {quant(diff, .5):+.2f}, p90 {quant(diff, .9):+.2f}); '
             f'animals closer in {sum(d < 0 for d in diff)}/{len(rows)} games; '
             f'animal tile-days on a shed tile {sum(r["anim_d0"] for r in rows) / max(1, sum(r["anim_td"] for r in rows)):.0%}')


def table_fert(acc, L, ours=False):
    F = acc.fert
    g = max(1, len(F))
    fn = sum(f['fert_n'] for f in F)
    fdet, cdet = Counter(), Counter()
    for f in F:
        fdet.update(f['fert_det'])
        cdet.update(f['crop_det'])
    nfd, ncd = sum(fdet.values()), sum(cdet.values())
    an_n = sum(acc.n[(w, 'ANIMALS')] for w in range(5))
    an_mean = sum(acc.sd[(w, 'ANIMALS')] for w in range(5)) / max(1, an_n)
    line = (f'  fertilizer per game: COLLECT_FERTILIZER commands {sum(f["collect_cmds"] for f in F) / g:.0f}, '
            f'FERTILIZE tiles {fn / g:.0f}' + (f' (FERTILIZE commands {sum(f["fert_cmds"] for f in F) / g:.0f})' if ours else '') +
            (f', fertilizer bought {sum(f["fert_bought"] for f in F) / g:.1f}' if not ours else '') +
            f', sold {sum(f["fert_sold"] for f in F) / g:.0f}; live animal-days {sum(f["live_animal_days"] for f in F) / g:.0f}')
    L.append(line)
    L.append(f'  fertilized tiles: mean distance {sum(f["fert_dist_sum"] for f in F) / max(1, fn):.2f} (animals {an_mean:.2f}); '
             f'detour to pass a live animal on the way from the shed: 0 steps {pct(fdet[0], nfd)}, <=2 {pct(sum(v for k, v in fdet.items() if k <= 2), nfd)} '
             f'of {nfd} fertilized tile-days (all live crop tile-days: 0 steps {pct(cdet[0], ncd)}, <=2 {pct(sum(v for k, v in cdet.items() if k <= 2), ncd)}); '
             f'fertilized with no live animal on the board {sum(f["fert_noanimal"] for f in F)}')


def report(name, acc, files, L, ours=False):
    L.append('')
    L.append('=' * 150)
    src = files if isinstance(files, str) else ''
    L.append(f'{name}: n={acc.games} games' + (f' (cash_match {acc.cash_ok}/{acc.games})' if acc.cash_ok is not None else '') + f'  {src}')
    table_distance(acc, L)
    table_shares(acc, L)
    table_rings(acc, L)
    table_quadrants(acc, L)
    table_quadrant_windows(acc, L)
    table_games(acc, L)
    table_fert(acc, L, ours)
    v = acc.visit
    if v:
        parts = []
        for grp in ('ANIMALS', 'CROPS'):
            n = max(1, v[(grp, 'tile_days')])
            parts.append(f'{grp.lower()} visited on {100 * v[(grp, "visited")] / n:.0f}% of tile-days, {v[(grp, "ops")] / n:.2f} effective ops/tile-day ('
                         + ', '.join(f'{o} {100 * v[(grp, o)] / n:.0f}%' for o in ('FEED', 'CARE', 'WATER', 'FERTILIZE', 'HARVEST') if v[(grp, o)]) + ')')
        L.append('  care frequency (maintenance tiles + harvested tiles, excl. COLLECT_FERTILIZER which has no tile record): ' + '; '.join(parts))
    if acc.other:
        L.append(f'  unrecognised labels (tile-days): {dict(acc.other)}')


def summary(accs):
    out = {}
    for name, acc in accs.items():
        n_a = sum(acc.n[(w, 'ANIMALS')] for w in range(5))
        n_c = sum(acc.n[(w, 'CROPS')] for w in range(5))
        ha, hc = Counter(), Counter()
        for w in range(5):
            ha.update(acc.h[(w, 'ANIMALS')])
            hc.update(acc.h[(w, 'CROPS')])
        out[name] = dict(
            games=acc.games,
            animal_mean=sum(acc.sd[(w, 'ANIMALS')] for w in range(5)) / max(1, n_a),
            crop_mean=sum(acc.sd[(w, 'CROPS')] for w in range(5)) / max(1, n_c),
            animal_share_d0=ha[0] / max(1, n_a), animal_share_le1=(ha[0] + ha[1]) / max(1, n_a),
            animal_share_le2=(ha[0] + ha[1] + ha[2]) / max(1, n_a),
            crop_share_d0=hc[0] / max(1, n_c), crop_share_le1=(hc[0] + hc[1]) / max(1, n_c),
            crop_share_le2=(hc[0] + hc[1] + hc[2]) / max(1, n_c),
            by_window={WNAME[w]: {k: (acc.sd[(w, k)] / acc.n[(w, k)] if acc.n[(w, k)] else None) for k in ROWS}
                       for w in range(5)},
            tiles_per_gameday={WNAME[w]: {k: acc.n[(w, k)] / max(1, acc.gd[w]) for k in ROWS} for w in range(5)},
            unlock_median={QN[q]: (st.median(v) if v else None) for q, v in acc.unlock.items()},
        )
    return out


ANIMAL_OPS = ('FEED', 'CARE', 'COLLECT_FERTILIZER')
CROP_OPS = ('WATER', 'FERTILIZE', 'PLANT')
SHED_OPS = ('PICKUP', 'PLACE', 'DROP')


class Seq:
    """per-unit-day command sequences: where does the fertilizer of each FERTILIZE command come from?"""

    def __init__(self):
        self.c = Counter()
        self.games = 0

    def unit_day(self, cmds):
        c = self.c
        coll = pick = 0                 # collected-first consumption
        coll2 = pick2 = 0               # shed-first consumption
        n_f = n_col = 0
        src = Counter()
        first_crop = None
        col_before_crop = 0
        shed_between = 0
        last_col_k = None
        for k, cm in enumerate(cmds):
            op = cm[0] if cm else 'PASS'
            item = cm[1] if len(cm) > 1 else None
            n = cm[2] if len(cm) > 2 and isinstance(cm[2], int) else 1
            if op == 'COLLECT_FERTILIZER':
                coll += 1
                coll2 += 1
                n_col += 1
                last_col_k = k
                if first_crop is None:
                    col_before_crop += 1
            elif op == 'PICKUP' and item == 'FERTILIZER':
                pick += n
                pick2 += n
                c['pickup_fert_cmds'] += 1
                c['pickup_fert_units'] += n
            elif op == 'PLACE' and item == 'FERTILIZER':
                c['place_fert_cmds'] += 1
                c['place_fert_units'] += n
            elif op == 'FERTILIZE':
                n_f += 1
                if coll > 0:
                    src['collected'] += 1
                    coll -= 1
                    if last_col_k is not None and any((cmds[j][0] if cmds[j] else 'PASS') in SHED_OPS
                                                      for j in range(last_col_k + 1, k)):
                        shed_between += 1
                elif pick > 0:
                    src['shed'] += 1
                    pick -= 1
                else:
                    src['none'] += 1
                if pick2 > 0:
                    src['shed_lb'] += 1
                    pick2 -= 1
                elif coll2 > 0:
                    src['collected_lb'] += 1
                    coll2 -= 1
            if op in CROP_OPS and first_crop is None:
                first_crop = k
        c['collect_cmds'] += n_col
        c['fert_cmds'] += n_f
        for k, v in src.items():
            c['fert_src_' + k] += v
        c['coll_used_same_unit_day'] += src['collected']
        c['shed_op_between_collect_and_fert'] += shed_between
        if n_col:
            c['unit_days_collect'] += 1
            if first_crop is not None:
                c['collect_cmds_in_ud_with_crop_op'] += n_col
                c['collects_before_first_crop_op'] += col_before_crop
        if n_f:
            c['unit_days_fert'] += 1
            had_col = src['collected'] > 0
            had_pick = src['shed'] > 0
            c['ud_fert_' + ('both' if had_col and had_pick else 'collected_only' if had_col else
                            'shed_only' if had_pick else 'no_source')] += 1

    def game(self, actions):
        """actions: list of per-step dicts {'farmer': cmd, 'hands': [cmd, ...]}"""
        self.games += 1
        days = defaultdict(lambda: defaultdict(list))
        for s, a in enumerate(actions):
            if isinstance(a, str):
                a = json.loads(a)
            if not a:
                continue
            d = s // 24
            f = a.get('farmer')
            days[d]['F'].append(list(f) if f else ['PASS'])
            for i, h in enumerate(a.get('hands') or []):
                days[d][i].append(list(h) if h else ['PASS'])
        for d, units in days.items():
            for u, cmds in units.items():
                self.unit_day(cmds)


def seq_report(name, sq, L):
    c, g = sq.c, max(1, sq.games)
    fc = max(1, c['fert_cmds'])
    ud = max(1, c['unit_days_fert'])
    L.append(f'  {name:26s} n={sq.games:3d}  per game: COLLECT {c["collect_cmds"] / g:5.0f}  FERTILIZE {c["fert_cmds"] / g:5.0f}  '
             f'PICKUP FERTILIZER {c["pickup_fert_cmds"] / g:5.1f} cmds / {c["pickup_fert_units"] / g:5.1f} units  '
             f'PLACE FERTILIZER {c["place_fert_units"] / g:5.1f} units')
    L.append(f'  {"":26s}        FERTILIZE sourced by the same unit\'s earlier COLLECT that day: {100 * c["fert_src_collected"] / fc:4.0f}% '
             f'(shed-first bound {100 * c["fert_src_collected_lb"] / fc:4.0f}%), shed PICKUP {100 * c["fert_src_shed"] / fc:4.0f}%, '
             f'no visible source {100 * c["fert_src_none"] / fc:4.0f}%; shed op between collect and fertilize '
             f'{100 * c["shed_op_between_collect_and_fert"] / max(1, c["fert_src_collected"]):3.0f}% of collected-sourced')
    L.append(f'  {"":26s}        unit-days with FERTILIZE {c["unit_days_fert"] / g:5.1f}/game: collected-only '
             f'{100 * c["ud_fert_collected_only"] / ud:3.0f}%, shed-only {100 * c["ud_fert_shed_only"] / ud:3.0f}%, both '
             f'{100 * c["ud_fert_both"] / ud:3.0f}%, none {100 * c["ud_fert_no_source"] / ud:3.0f}%; '
             f'COLLECTs used by the same unit the same day {100 * c["coll_used_same_unit_day"] / max(1, c["collect_cmds"]):3.0f}%; '
             f'COLLECTs in unit-days that also do crop ops (WATER/FERTILIZE/PLANT) {100 * c["collect_cmds_in_ud_with_crop_op"] / max(1, c["collect_cmds"]):3.0f}%, '
             f'of those issued before the unit\'s first crop op {100 * c["collects_before_first_crop_op"] / max(1, c["collect_cmds_in_ud_with_crop_op"]):3.0f}%')


def run_sequences(L):
    L.append('')
    L.append('=' * 150)
    L.append('PART 2. Fertilizer source per FERTILIZE command, from recorded per-step unit commands (commands, not verified '
             'effects). Leaders: data/leader_tapes/<team>_<sub>/<episode>.json.gz (the leader seat\'s "actions", same '
             'episodes as the semantics corpus). Ours: per-step actions from results/fresh/lead_world_trace/<agent>_<ep>.json '
             '(dep6 byte-identical to the kaggle_remote_lead/wtr2 copies; final cash equals the lead_cycles record in 12/12 '
             'worlds for dep6 and for q4). NOTE agents/mgt_lpv_dep6.py predates fert_hold (agents/mgt_lead_deploy.py now '
             'defaults fert_hold 1, commit 9fc1035), so no stored sequence covers the fert_hold build. Sourcing is counted per unit-day (inventories dump at midnight; hands vanish).')
    tot = Seq()
    res = {}
    for tid, name in TEAMS:
        sq = Seq()
        missing = 0
        for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'leader_semantics', tid, '*.json.gz'))):
            ep = os.path.basename(f).split('.')[0]
            cand = sorted(glob.glob(os.path.join(ROOT, 'data', 'leader_tapes', f'{tid}_*', f'{ep}.json.gz')))
            if not cand:
                missing += 1
                continue
            with gzip.open(cand[0], 'rt', encoding='utf-8') as fh:
                t = json.load(fh)
            sq.game(t['actions'])
            tot.game(t['actions'])
        seq_report(name + (f' (missing tapes {missing})' if missing else ''), sq, L)
        res[name] = dict(sq.c, games=sq.games)
    for k, v in tot.c.items():
        pass
    seq_report('ALL LEADERS', tot, L)
    res['ALL_LEADERS'] = dict(tot.c, games=tot.games)
    for agent in OURS:
        sq = Seq()
        for f in sorted(glob.glob(os.path.join(ROOT, 'results', 'fresh', 'lead_world_trace', f'{agent}_*.json'))):
            with open(f, encoding='utf-8') as fh:
                r = json.load(fh)
            sq.game(r['actions'])
        seq_report(f'OURS {agent}', sq, L)
        res[agent] = dict(sq.c, games=sq.games)
    return res


def main():
    L = ['Animal vs crop placement relative to the shed (stored data only; no games run). Script: '
         'results/fresh/layout_animals_20260925/geometry.py',
         'Distance = Manhattan to the nearest shed tile (4,4),(5,4),(4,5),(5,5); those 4 tiles are farmable (d0). '
         'Every quadrant: 1 tile d0, 2 d1, 3 d2, 4 d3, 5 d4, 4 d5, 3 d6, 2 d7, 1 d8 (mean 4.0).',
         'Leader boards = day start; leader "co" resolved by build history (BUILD_COOP -> empty coop, BUILD_PASTURE -> cow).',
         'Fertilized tiles: leaders = maintenance.FERTILIZE (effective); ours = per-tile fertilized_until_day increases between '
         'day starts (lead_cycles states). Detour = min over live animals of d(shed,animal)+d(animal,tile)-d(shed,tile).']
    leaders, lf = run_leaders()
    for name, acc in leaders.items():
        report(name, acc, f'{lf[name][0]} ({lf[name][1]} files)', L)
    allacc = merge(leaders)
    allacc.cash_ok = sum(a.cash_ok for a in leaders.values())
    report('ALL LEADERS (pooled tile-days; Boey 40 games, others 100)', allacc, 'data/leader_semantics/*', L)
    ours, of = run_ours()
    for name, acc in ours.items():
        report(f'OURS {name} (12 p2750 worlds, lead_cycles records)', acc, f'{of[name][0]} ({of[name][1]} files with boards)', L, ours=True)
    seq = run_sequences(L)
    txt = '\n'.join(L) + '\n'
    with open(os.path.join(OUT, 'geometry.txt'), 'w', encoding='utf-8') as fh:
        fh.write(txt)
    allmap = dict(leaders)
    allmap['ALL_LEADERS'] = allacc
    allmap.update(ours)
    with open(os.path.join(OUT, 'geometry.json'), 'w', encoding='utf-8') as fh:
        json.dump(dict(summary=summary(allmap), files=dict(leaders=lf, ours=of), fertilizer_sequences=seq), fh, indent=1)
    print(txt)


if __name__ == '__main__':
    main()
