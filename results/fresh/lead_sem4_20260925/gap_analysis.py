"""sem4 gap analysis (2026-09-25). Stored results only, one process, no games.

Question: how far behind the leader are we when we follow its plan on all four quadrants?
Inputs: results/fresh/lead_sem4_20260925/{LEADER,T0,T,S,S0,D,Dp}/<ep>.json (scripts/lead_sem4.py play(); 7 arms x 48
leader worlds, run on Kaggle kernels kgr-sem4a-s0 / kgr-sem4b-s0) and worlds.json. Prints the tables (stdout); writes
gap_per_game.json (per-game decomposition, all arms).

Three reasons (positive = leader ahead; every line adds to the cash gap with residual 0 in every game):
  gap = cash_L - cash_X = (rev_L - rev_X) - (spend_L - spend_X) - (wages_L - wages_X) - (land_L - land_X)
  (checked: final = 3,000 + revenue - purchases - wages - land in all 336 files)
  rev_L - rev_X = A + C1 + C2 per product, at the leader's average realised price PL (deep_decomp.py convention):
    A  = (harvested_L - harvested_X) x PL        (fertilizer: sold units, so its use on crops is inside A)
    C1 = -[(harv_L - sold_L) - (harv_X - sold_X)] x PL = fed wheat + midnight discards + wheat bought + held at end
    C2 = sold_X x (PL - PX) = timing + market depth
         timing = sold_X x sum_d (wL_d - wX_d) x pX~_d   (our units moved onto the leader's sale-day mix, our daily price)
         depth  = sold_X x sum_d wL_d x (pL~_d - pX~_d)  (same-day price gap: the market depth of the different volume)
  1. LESS PRODUCTION = A + purchases (seeds, animals, wheat, fertilizer) + land + fed + discards + wheat-bought resale
  2. MORE LABOUR COST = wages_X - wages_L
  3. BAD SALE TIMING = C2 timing (units sold on other days than the leader) + units still held at the end
  (market depth shown separately; memo: the part of timing explained by LATER SUPPLY, i.e. our harvests of that product
   coming on later days: sold_X x sum_d (sL_d - sX_d) x pX~_d with s = the daily harvest mix; crops and animal
   products only, because daily wheat purchases / feeds and daily fertilizer use were not recorded.)
  Wheat bought as product vs seed: the play() ledger keys purchases by item only. Seeds bought = plantings (seeds
  left over at the end = 0) gives wheat product units = bought - planted; the implied price per product unit is
  checked to be a plausible wheat price, and a lower bound (held at end >= 0) is reported with it.
"""
import json
import math
import random
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

from scipy import stats

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ARMS = ['LEADER', 'T0', 'T', 'S', 'S0', 'D', 'Dp']
OURS = ARMS[1:]
LAB = {'Dp': 'D+'}
PRODUCTS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']
CROPS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON']
ANIMALS = ['COW', 'SHEEP', 'GOOSE']
SEED = {'WHEAT': 10, 'CARROT': 20, 'TOMATO': 50, 'STRAWBERRY': 100, 'MELON': 80}
QN = ['first', 'second', 'third', 'fourth']
QCOST = {'first': 'free', 'second': '$1,000', 'third': '$2,000', 'fourth': '$4,000'}
MAINT = ['WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE', 'COLLECT_FERTILIZER']
NB = 10000


def lab(a):
    return LAB.get(a, a)


# ---------------------------------------------------------------- statistics
def tci(xs):
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, m, m
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    return m, m - h, m + h


_BS = {}


def bci(xs):
    n = len(xs)
    if n not in _BS:
        rng = random.Random(20260925 + n)
        _BS[n] = [[rng.randrange(n) for _ in range(n)] for _ in range(NB)]
    ms = sorted(sum(xs[i] for i in idx) / n for idx in _BS[n])
    return ms[int(0.025 * NB)], ms[int(0.975 * NB) - 1]


def f0(v):
    return f'{v:+,.0f}'


def ft(xs):
    m, lo, hi = tci(xs)
    return f'{m:+,.0f} ({lo:+,.0f}..{hi:+,.0f})'


def ftb(xs):
    m, lo, hi = tci(xs)
    bl, bh = bci(xs)
    return f'{m:+,.0f} | {lo:+,.0f}..{hi:+,.0f} | {bl:+,.0f}..{bh:+,.0f}'


# ---------------------------------------------------------------- load
def load():
    W = json.loads((OUT / 'worlds.json').read_text(encoding='utf-8'))['worlds']
    worlds = {w['episode']: w for w in W}
    R = {a: {} for a in ARMS}
    for a in ARMS:
        for f in sorted((OUT / a).glob('1*.json')):
            r = json.loads(f.read_text(encoding='utf-8'))
            R[a][r['episode']] = r
    common = sorted(set(worlds).intersection(*[set(v) for v in R.values()]))
    return worlds, R, common


# ---------------------------------------------------------------- per-game decomposition
def daily(r, key, p):
    return [dd.get(key, {}).get(p, 0) for dd in r['days']]


def interp(prices):
    obs = [d for d in range(30) if prices[d] is not None]
    if not obs:
        return [0.0] * 30
    out = []
    for d in range(30):
        if prices[d] is not None:
            out.append(prices[d])
            continue
        lo = [o for o in obs if o < d]
        hi = [o for o in obs if o > d]
        if lo and hi:
            a, b = lo[-1], hi[0]
            out.append(prices[a] + (prices[b] - prices[a]) * (d - a) / (b - a))
        else:
            out.append(prices[lo[-1]] if lo else prices[hi[0]])
    return out


# base potential of one planting (full water, no fertilizer, harvested by day 29), from
# results/fresh/t_gap_20260925/deep_decomp.py (pot / prod_days), engine kaggle_environments 1.32.7
POTC = {"WHEAT": dict(first=2, interval=0, max=6, ongoing=False, pot=4),
        "CARROT": dict(first=2, interval=0, max=4, ongoing=False, pot=3),
        "TOMATO": dict(first=8, interval=1, max=4, ongoing=True),
        "STRAWBERRY": dict(first=10, interval=2, max=4, ongoing=True),
        "MELON": dict(first=10, interval=0, max=6, ongoing=False, pot=6)}
CUTOFF = {"STRAWBERRY": 13, "TOMATO": 18, "MELON": 19, "WHEAT": 25, "CARROT": 26}   # mgt_lead / mgt_lead_exact / mgt_lead_sem CFG plant_cutoff
PRODUCT_OF = {'COW': 'MILK', 'SHEEP': 'WOOL', 'GOOSE': 'EGG'}


def pot(crop, d):
    c = POTC[crop]
    if c['ongoing']:
        return sum(1 for j in range(c['max']) if d + c['first'] - 1 + j * c['interval'] <= 28)
    room = 29 - d
    if room < c['first']:
        return 0
    return 6 if crop == 'MELON' else min(c['pot'], room)


def output_split(L, X, PL, cutoff_applies):
    """exact split of sum_p A_p: crops n x pot/n x units/pot; animal products animal-days x units/animal-day;
    fertilizer sold units. Returns dict of lines (sum = A total)."""
    out = Counter()
    for c in CROPS:
        agg = {}
        for s, r in (('L', L), ('X', X)):
            n = potv = post = 0
            for d, dd in enumerate(r['days']):
                k = dd.get('plant', {}).get(c, 0)
                n += k
                potv += k * pot(c, d)
                if d > CUTOFF[c]:
                    post += k * pot(c, d)
            agg[s] = dict(n=n, pot=potv, post=post, h=r['totals']['harvested'].get(c, 0))
        hL, hX = agg['L']['h'], agg['X']['h']
        rL = hL / agg['L']['pot'] if agg['L']['pot'] else None
        rX = hX / agg['X']['pot'] if agg['X']['pot'] else None
        if rL is None and rX is None:
            out['O_crop_care'] += (hL - hX) * PL[c]
            continue
        rL = rX if rL is None else rL
        rX = rL if rX is None else rX
        plant_term = (agg['L']['pot'] - agg['X']['pot']) * rL * PL[c]
        care_term = agg['X']['pot'] * (rL - rX) * PL[c]
        err = (hL - hX) * PL[c] - plant_term - care_term
        care_term += err       # only when a side harvests on zero potential
        cut_term = agg['L']['post'] * rL * PL[c] if cutoff_applies else 0.0
        out['O_plant_cutoff'] += cut_term
        out['O_plantings'] += plant_term - cut_term
        out['O_crop_care'] += care_term
    for sp, prod in PRODUCT_OF.items():
        ad = {s: sum(q['occ_tile_days'].get(sp, 0) for q in r['quadrants'].values()) for s, r in (('L', L), ('X', X))}
        h = {s: r['totals']['harvested'].get(prod, 0) for s, r in (('L', L), ('X', X))}
        yL = h['L'] / ad['L'] if ad['L'] else (h['X'] / ad['X'] if ad['X'] else 0.0)
        yX = h['X'] / ad['X'] if ad['X'] else yL
        t1 = (ad['L'] - ad['X']) * yL * PL[prod]
        t2 = ad['X'] * (yL - yX) * PL[prod]
        t2 += (h['L'] - h['X']) * PL[prod] - t1 - t2
        out['O_animal_days'] += t1
        out['O_animal_yield'] += t2
    out['O_fert_sold'] = (L['totals']['sold'].get('FERTILIZER', 0) - X['totals']['sold'].get('FERTILIZER', 0)) * PL['FERTILIZER']
    return out


def wheat_prod_bought(t):
    """(estimate, lower bound) of wheat bought as product; estimate assumes seeds bought = plantings."""
    bw, pw = t['bought'].get('WHEAT', 0), t['plant'].get('WHEAT', 0)
    est = max(0, bw - pw)
    fed = t['eff_ops'].get('FEED', 0)
    lo = max(0, fed + t['discards'].get('WHEAT', 0) + t['sold'].get('WHEAT', 0) - t['harvested'].get('WHEAT', 0))
    return est, min(lo, est)


def decompose(L, X):
    tL, tX = L['totals'], X['totals']
    H = {s: Counter(t['harvested']) for s, t in (('L', tL), ('X', tX))}
    Q = {s: Counter(t['sold']) for s, t in (('L', tL), ('X', tX))}
    RV = {s: Counter(t['rev']) for s, t in (('L', tL), ('X', tX))}
    PL, PX = {}, {}
    for p in PRODUCTS:
        PL[p] = RV['L'][p] / Q['L'][p] if Q['L'][p] else (RV['X'][p] / Q['X'][p] if Q['X'][p] else 0.0)
        PX[p] = RV['X'][p] / Q['X'][p] if Q['X'][p] else PL[p]
    gap = L['final'] - X['final']
    A, C1, C2 = {}, {}, {}
    for p in PRODUCTS:
        hL, hX = (H['L'][p], H['X'][p]) if p != 'FERTILIZER' else (Q['L'][p], Q['X'][p])
        A[p] = (hL - hX) * PL[p]
        C1[p] = -((hL - Q['L'][p]) - (hX - Q['X'][p])) * PL[p]
        C2[p] = Q['X'][p] * (PL[p] - PX[p])
    # purchases
    def spend_split(t):
        s = Counter()
        for k, v in t['spend'].items():
            if k in ANIMALS:
                s['animals'] += v
            elif k == 'WHEAT':
                s['wheat'] += v
            elif k == 'FERTILIZER':
                s['fert'] += v
            else:
                s['seeds'] += v
        return s
    sL, sX = spend_split(tL), spend_split(tX)
    purch = {k: sX[k] - sL[k] for k in set(sL) | set(sX)}
    land = tX['land_spend'] - tL['land_spend']
    wages = tX['wages'] - tL['wages']
    # C1 components
    bpL, bpL_lo = wheat_prod_bought(tL)
    bpX, bpX_lo = wheat_prod_bought(tX)
    fedL, fedX = tL['eff_ops'].get('FEED', 0), tX['eff_ops'].get('FEED', 0)
    c1_fed = -(fedL - fedX) * PL['WHEAT']
    c1_bought = (bpL - bpX) * PL['WHEAT']
    c1_disc = sum(-(tL['discards'].get(p, 0) - tX['discards'].get(p, 0)) * PL[p] for p in PRODUCTS if p != 'FERTILIZER')
    c1_all = sum(C1.values())
    c1_held = c1_all - c1_fed - c1_bought - c1_disc
    # bounds on the held line from the wheat product lower bounds: held = c1_all - fed - disc - (bpL - bpX) PL
    held_alt = [c1_all - c1_fed - c1_disc - (a - b) * PL['WHEAT'] for a, b in ((bpL, bpX_lo), (bpL_lo, bpX))]
    heldu = {}
    for s, t, bp in (('L', tL, bpL), ('X', tX, bpX)):
        hu = Counter()
        for p in PRODUCTS:
            if p == 'FERTILIZER':
                continue
            v = t['harvested'].get(p, 0) - t['sold'].get(p, 0) - t['discards'].get(p, 0)
            if p == 'WHEAT':
                v += bp - t['eff_ops'].get('FEED', 0)
            hu[p] = v
        heldu[s] = hu
    # C2 split
    timing, depth, supply_t, units_moved = {}, {}, {}, {}
    for p in PRODUCTS:
        qL, rL = daily(L, 'sold', p), daily(L, 'rev', p)
        qX, rX = daily(X, 'sold', p), daily(X, 'rev', p)
        QL_, QX_ = sum(qL), sum(qX)
        if QL_ == 0 or QX_ == 0:
            timing[p], depth[p], supply_t[p], units_moved[p] = 0.0, C2[p], 0.0, 0.0
            continue
        pLi = interp([rL[d] / qL[d] if qL[d] else None for d in range(30)])
        pXi = interp([rX[d] / qX[d] if qX[d] else None for d in range(30)])
        wL = [x / QL_ for x in qL]
        wX = [x / QX_ for x in qX]
        timing[p] = QX_ * sum((wL[d] - wX[d]) * pXi[d] for d in range(30))
        depth[p] = QX_ * sum(wL[d] * (pLi[d] - pXi[d]) for d in range(30))
        assert abs(timing[p] + depth[p] - C2[p]) < 1e-6, (X['arm'], X['episode'], p)
        units_moved[p] = QX_ * 0.5 * sum(abs(wL[d] - wX[d]) for d in range(30))
        supply_t[p] = 0.0
        if p not in ('WHEAT', 'FERTILIZER'):
            hL, hX = daily(L, 'harv', p), daily(X, 'harv', p)
            if sum(hL) and sum(hX):
                sL_ = [x / sum(hL) for x in hL]
                sX_ = [x / sum(hX) for x in hX]
                supply_t[p] = QX_ * sum((sL_[d] - sX_[d]) * pXi[d] for d in range(30))
    lines = dict(
        P_output=sum(A.values()),
        P_seeds=purch.get('seeds', 0), P_animals=purch.get('animals', 0), P_land=land,
        P_wheat_fert_purch=purch.get('wheat', 0) + purch.get('fert', 0) + c1_bought,
        P_wheat_fed=c1_fed, P_discards=c1_disc,
        L_wages=wages,
        S_timing=sum(timing.values()), S_held_end=c1_held,
        M_depth=sum(depth.values()),
    )
    resid = gap - sum(lines.values())
    assert abs(resid) < 1e-6, (X['arm'], X['episode'], resid)
    lines['PRODUCTION'] = sum(v for k, v in lines.items() if k.startswith('P_'))
    lines['LABOUR'] = wages
    lines['TIMING'] = lines['S_timing'] + lines['S_held_end']
    lines['DEPTH'] = lines['M_depth']
    lines['memo_later_supply'] = sum(supply_t.values())
    lines['memo_timing_rest'] = lines['S_timing'] - lines['memo_later_supply']
    lines['memo_held_lo'] = min(held_alt + [c1_held])
    lines['memo_held_hi'] = max(held_alt + [c1_held])
    lines['memo_prod_plus_depth'] = lines['PRODUCTION'] + lines['DEPTH']
    osp = output_split(L, X, PL, X['arm'] in ('T0', 'T', 'S', 'S0'))
    assert abs(sum(osp.values()) - lines['P_output']) < 1e-6, (X['arm'], X['episode'])
    lines.update(osp)
    return dict(gap=gap, lines=lines, A=A, C1=C1, C2=C2, timing=timing, depth=depth, supply_t=supply_t,
                units_moved=units_moved, PL=PL, PX=PX, heldu=heldu,
                wheat_bp=(bpL, bpL_lo, bpX, bpX_lo),
                wheat_bp_price={s: ((t['spend'].get('WHEAT', 0) - SEED['WHEAT'] * t['plant'].get('WHEAT', 0)) / bp if bp else None)
                                for s, t, bp in (('L', tL, bpL), ('X', tX, bpX))})


# ---------------------------------------------------------------- report
def main():
    worlds, R, common = load()
    n = len(common)
    team = {e: worlds[e]['team'] for e in common}
    teams = sorted(set(team.values()))
    coll = {a: sorted(e for e in common if R[a][e]['opp_collapse']) for a in ARMS}
    collapse = sorted({e for e in common if worlds[e]['flags'] or any(R[a][e]['opp_collapse'] for a in ARMS)})
    clean = [e for e in common if e not in collapse]
    rep_ok = [e for e in common if round(R['LEADER'][e]['final']) == round(worlds[e]['leader_final'])
              and round(R['LEADER'][e]['opp_final']) == round(worlds[e]['opp_final_recorded'])]
    DEC = {a: {e: decompose(R['LEADER'][e], R[a][e]) for e in common} for a in OURS}
    fin = {a: {e: R[a][e]['final'] for e in common} for a in ARMS}
    gap = {a: {e: fin['LEADER'][e] - fin[a][e] for e in common} for a in OURS}
    o = []
    P = o.append

    # ================= header / answer
    P('# sem4: how far behind the leader are we when we follow its plan on all four quadrants?')
    P('')
    P('2026-09-25. Stored results only (`results/fresh/lead_sem4_20260925/gap_analysis.py`, one process, no games). '
      f'n = {n} leader worlds (4 teams x 12: {", ".join(teams)}), 7 arms, 336 games run on Kaggle (kernels kgr-sem4a-s0 / '
      'kgr-sem4b-s0; reproduction check kgr-sem4r-s0 passed first). Leader world = the leader\'s recorded game: same seed, '
      'same forced shop sequence, the opponent replaying its recorded actions; our agent takes the leader\'s seat. '
      'Every arm that uses the mgt_lead executor runs with p1_min_value 30, release_stale_d True, fert_hold 1; '
      'no value-aware tie-break (thread Q) anywhere except D+ (the deploy as is).')
    P('')
    P('| arm | what it follows | layout | removals |')
    P('|---|---|---|---|')
    P('| LEADER | the leader\'s own recorded actions (control: must reproduce the recorded cash) | leader | leader |')
    P('| T0 | the leader\'s exact plan (counts, timing, hands, sales) | the leader\'s tiles | none of live plants (a crop is dug only when finished) |')
    P('| **T** | the leader\'s exact plan | the leader\'s tiles | **the leader\'s exact removals of live crops** (same cohort, same day, +1 day window) |')
    P('| S | the leader\'s semantic plan (counts and timing only) | ours: most care nearest the shed | removals as counts |')
    P('| S0 | the leader\'s semantic plan | the deploy\'s nearest-centre rule | removals as counts |')
    P('| D | our own full deploy plan (this episode excluded from retrieval), same executor settings | deploy | deploy |')
    P('| D+ | the current deploy as is (tie_value 1), reference | deploy | deploy |')
    P('')
    P('**The user\'s "tile-exact with the exact removals" question is arm T** (T0 is the same without removals).')
    P('')
    P(f'Checks: LEADER reproduces the recorded final cash and the recorded opponent cash in {len(rep_ok)}/{n} worlds '
      '(its cash is the "leader cash" below); final = 3,000 + revenue - purchases - wages - land holds to the coin in all '
      '336 files; every three-reason line below adds to the gap with residual 0 in every game. Replayed-opponent collapse '
      '(opponent final < 0.8 x recorded, or known): ' + '; '.join(f'{lab(a)} {len(coll[a])}' for a in OURS) +
      f'; union {len(collapse)} worlds ({", ".join(map(str, collapse))}), leaving {len(clean)} worlds clean in every arm.')
    P('')

    # ================= 1. final cash
    P('## 1. Final cash and gap to the leader (positive gap = leader ahead)')
    P('')
    P(f'Leader mean final {st.mean(fin["LEADER"][e] for e in common):,.0f} (n={n}); clean {st.mean(fin["LEADER"][e] for e in clean):,.0f} (n={len(clean)}). '
      'Mean gap | paired-t 95% CI | bootstrap 95% CI (10,000 world resamples). Ratio = our final / leader final, mean over worlds.')
    P('')
    P(f'| arm | mean final | gap, all {n} | t CI | bootstrap CI | ratio | worlds ahead of leader | gap, clean {len(clean)} | t CI | bootstrap CI | ratio clean |')
    P('|---|---:|---:|---|---|---:|---:|---:|---|---|---:|')
    for a in OURS:
        g = [gap[a][e] for e in common]
        gc = [gap[a][e] for e in clean]
        P(f'| {lab(a)} | {st.mean(fin[a][e] for e in common):,.0f} | {ftb(g)} | '
          f'{st.mean(fin[a][e] / fin["LEADER"][e] for e in common):.3f} | {sum(1 for x in g if x < 0)}/{n} | {ftb(gc)} | '
          f'{st.mean(fin[a][e] / fin["LEADER"][e] for e in clean):.3f} |')
    P('')

    # ================= 2. exact removals
    P('## 2. Value of the exact removals: T0 -> T')
    P('')
    d_rm = [fin['T'][e] - fin['T0'][e] for e in common]
    d_rmc = [fin['T'][e] - fin['T0'][e] for e in clean]
    P(f'T - T0 (positive = removals help): all {n}: {ftb(d_rm)}, T better in {sum(1 for x in d_rm if x > 0)}/{n}; '
      f'clean {len(clean)}: {ftb(d_rmc)}. Per team: ' + '; '.join(
          f'{t} {ft([fin["T"][e] - fin["T0"][e] for e in common if team[e] == t])}' for t in teams) + ' (n=12 each).')
    P('')
    P('**Exact removals are worth nothing measurable** (CI covers 0; point estimate slightly negative). Why, from the '
      'stored ledgers and the engine code:')
    P('')
    # removal accounting table
    P('| arm | strawberry planted | dug live | ended (turned to weed, 0 yield left) | rotted (weed with yield left) | died unwatered | tomato planted | dug live | ended | rotted | unwatered | removals issued (straw / tom) | productions forfeited by the removals |')
    P('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|')
    for a in ARMS:
        ts = [R[a][e]['totals'] for e in common]
        m = lambda f: sum(f(t) for t in ts) / n
        lg = Counter()
        for e in common:
            lg.update({k: v for k, v in (R[a][e].get('agent_log') or {}).items() if k.startswith('rm_')})
        iss = (f"{lg.get('rm_issued_STRAWBERRY', lg.get('rm_sel_STRAWBERRY', 0)) / n:.1f} / "
               f"{lg.get('rm_issued_TOMATO', lg.get('rm_sel_TOMATO', 0)) / n:.1f}") if lg else ''
        cells = []
        for c in ('STRAWBERRY', 'TOMATO'):
            cells += [f"{m(lambda t: t['plant'].get(c, 0)):.1f}", f"{m(lambda t: t['dug_live'].get(c, 0)):.1f}",
                      f"{m(lambda t: t['deaths'].get('ended_' + c, 0)):.1f}", f"{m(lambda t: t['deaths'].get('rotted_' + c, 0)):.1f}",
                      f"{m(lambda t: t['deaths'].get('unwatered_' + c, 0)):.1f}"]
        P(f'| {lab(a)} | ' + ' | '.join(cells) + f" | {iss} | {(lg.get('rm_forfeit_prods', 0) / n):.1f} |")
    P('')
    P('- Engine (kaggle_environments 1.32.7, `_daily_refresh_plants` / `_decay_plants`): when an ongoing crop makes its '
      'last production, its `max_lifespan_step` is set to hour 0 of the next day; from then on it loses one yield unit '
      'every 2 steps and becomes a WEED as soon as its yield is <= 0. A strawberry makes its 4th and last production at '
      'age 16 (tomato: age 11); if that yield is harvested, the plant is a WEED at hour 0 of age 17 (tomato 12).')
    P('- The leaders dig 82% of their strawberries at age 16 and 92% of their tomatoes at age 11, after harvesting '
      '(`agents/mgt_lead_exact.py` docstring, from data/leader_semantics). Those removals only free the tile a few hours '
      'before the engine would turn the plant into a weed anyway; the replant then needs a DIG either way. So there '
      'is almost nothing to gain from copying them, which is what T - T0 shows.')
    P('- T issues 20.7 strawberry and 9.6 tomato removals a game but digs only 12.6 / 6.2 live plants. The table accounts '
      'for the rest: T0 (no removals) has 19.6 strawberries that end on their own; T has 12.6 dug live + 6.6 ended = '
      '19.2, and 1.0 more rotted. So the missing ~8 strawberry removals are plants T did not reach on the leader\'s '
      'removal day; by the next day (the +1 window, `rm_late` 1) an age-16 strawberry is already a weed and the DIG, if '
      'any, is a weed DIG, which the dig counter (DIG of a PLANT tile) does not count. This is inferred from the counts '
      'and the engine rule; per-dig ages were not recorded, so it is not proven dig by dig.')
    P('- The same rule explains why "dead-plant removals" are 0 in every arm including LEADER: a finished, harvested '
      'plant is already a WEED at hour 0 of the next day, so a later DIG on it is a weed DIG (the leader lets 8.9 '
      'strawberries and 3.1 tomatoes a game end this way). The ~4.5 per game the semantics build counted as dead-plant '
      'removals are weed clearings by construction.')
    P('- Removals before a plant\'s last production forfeit productions: 15.0 a game for T (`rm_forfeit_prods`; S 11.0, '
      'S0 17.8). T copies that cost; the gain (an earlier replant) needs the replant to happen on time.')
    P('')

    # ================= 3. chain
    P('## 3. Decomposition of the gap: leader -> T -> S -> D')
    P('')
    P('Paired differences in final cash (positive = the second arm named is ahead). Mean | paired-t 95% CI | bootstrap 95% CI; '
      'W = worlds where the difference is positive.')
    P('')
    P(f'| step | meaning | all {n} | t CI | bootstrap CI | W | clean {len(clean)} | t CI | bootstrap CI | W |')
    P('|---|---|---:|---|---|---:|---:|---|---|---:|')
    steps = [('LEADER', 'T', 'leader -> T: execution with the leader\'s exact plan and tiles (incl. exact removals); = -gap(T)'),
             ('LEADER', 'T0', 'leader -> T0: the same without removals'),
             ('T0', 'T', 'T0 -> T: the leader\'s exact removals'),
             ('T', 'S', 'T -> S: our care-order layout instead of the leader\'s tiles (semantic plan, count removals)'),
             ('S0', 'S', 'S0 -> S: which layout rule (care order vs the deploy\'s nearest-centre)'),
             ('T', 'S0', 'T -> S0: deploy layout instead of the leader\'s tiles'),
             ('S', 'D', 'S -> D: our own plan instead of the leader\'s counts (same executor settings)'),
             ('D', 'Dp', 'D -> D+: the current deploy as is (tie_value 1)'),
             ('LEADER', 'Dp', 'leader -> D+: the whole remaining gap of the current deploy')]
    for a, b, nm in steps:
        d = [fin[b][e] - fin[a][e] for e in common]
        dc = [fin[b][e] - fin[a][e] for e in clean]
        P(f'| {lab(a)} -> {lab(b)} | {nm} | {ftb(d)} | {sum(1 for x in d if x > 0)} | {ftb(dc)} | {sum(1 for x in dc if x > 0)} |')
    P('')

    # ================= 4. per team
    P('## 4. Gap to the leader per team (n=12 each; clean n in brackets)')
    P('')
    P('| arm | ' + ' | '.join(f'{t}: gap (t CI) / boot CI / clean' for t in teams) + ' |')
    P('|---|' + '---|' * len(teams))
    for a in OURS:
        cells = []
        for t in teams:
            es = [e for e in common if team[e] == t]
            ec = [e for e in clean if team[e] == t]
            g = [gap[a][e] for e in es]
            bl, bh = bci(g)
            cells.append(f'{ft(g)} / {bl:+,.0f}..{bh:+,.0f} / {st.mean(gap[a][e] for e in ec):+,.0f} [{len(ec)}]')
        P(f'| {lab(a)} | ' + ' | '.join(cells) + ' |')
    P('')
    P('| leader final by team | ' + ' | '.join(f'{t} {st.mean(fin["LEADER"][e] for e in common if team[e] == t):,.0f}' for t in teams) + ' |')
    P('|---|' + '---|' * len(teams))
    P('')

    # ================= 5. three reasons
    P('## 5. The three reasons for each arm\'s gap (positive = leader ahead; the numbered lines add to the gap)')
    P('')
    P('Valued at the leader\'s average realised price per product (as in results/fresh/t_gap_20260925/deep_decomp.py). '
      'Mean with paired-t 95% CI over worlds.')
    P('')
    rows3 = [('GAP', 'CASH GAP'),
             ('PRODUCTION', '**1. less production** (subtotal)'),
             ('P_output', '  fewer units harvested (fertilizer: sold), at the leader\'s price'),
             ('O_plant_cutoff', '    = crops: leader plantings after our plant_cutoff day (skipped by design; T0/T/S/S0 only)'),
             ('O_plantings', '    + crops: other missing planting potential (fewer / later plantings)'),
             ('O_crop_care', '    + crops: fewer units per potential unit (deaths, decay, water / fertilizer bonus)'),
             ('O_animal_days', '    + animal products: fewer animal-days on the board'),
             ('O_animal_yield', '    + animal products: output per animal-day'),
             ('O_fert_sold', '    + fertilizer sold'),
             ('P_seeds', '  seeds: the leader spends more (-) / less (+)'),
             ('P_animals', '  animals bought'),
             ('P_land', '  land (the leader buys all 4 quadrants: 7,000)'),
             ('P_wheat_fert_purch', '  wheat / fertilizer bought (cost - resale value at the leader\'s price)'),
             ('P_wheat_fed', '  wheat fed to animals'),
             ('P_discards', '  output lost at the 100-item shed cap at midnight'),
             ('LABOUR', '**2. more labour cost** (our wages - the leader\'s)'),
             ('TIMING', '**3. bad sale timing** (subtotal)'),
             ('S_timing', '  our units sold on other days than the leader (at our daily prices)'),
             ('S_held_end', '  units still unsold at the end'),
             ('DEPTH', '**market depth** (separate: same-day price gap from the different volume)'),
             ('memo_prod_plus_depth', 'memo: less production net of market depth'),
             ('memo_later_supply', 'memo: part of the timing line explained by our harvests coming later (crops + animal products)'),
             ('memo_timing_rest', 'memo: rest of the timing line (holding, and wheat / fertilizer timing)')]
    for sel_name, sel in (('all', common), ('clean', clean)):
        P(f'### {sel_name} worlds (n={len(sel)})')
        P('')
        P('| line | ' + ' | '.join(lab(a) for a in OURS) + ' |')
        P('|---|' + '---:|' * len(OURS))
        for k, nm in rows3:
            cells = []
            for a in OURS:
                xs = [DEC[a][e]['gap'] if k == 'GAP' else DEC[a][e]['lines'][k] for e in sel]
                cells.append(ft(xs))
            P(f'| {nm} | ' + ' | '.join(cells) + ' |')
        P('')
        P('Bootstrap 95% CI of the four subtotals: ' + '; '.join(
            f"{lab(a)}: " + ', '.join(f"{nm} {bci([DEC[a][e]['lines'][k] for e in sel])[0]:+,.0f}..{bci([DEC[a][e]['lines'][k] for e in sel])[1]:+,.0f}"
                                      for k, nm in (('PRODUCTION', 'prod'), ('LABOUR', 'labour'), ('TIMING', 'timing'), ('DEPTH', 'depth')))
            for a in OURS))
        P('')
    held_rng = {a: (st.mean(DEC[a][e]['lines']['memo_held_lo'] for e in common), st.mean(DEC[a][e]['lines']['memo_held_hi'] for e in common)) for a in OURS}
    bpp = [DEC['T'][e]['wheat_bp_price'][s] for e in common for s in ('L', 'X') if DEC['T'][e]['wheat_bp_price'][s]]
    bpp += [DEC[a][e]['wheat_bp_price']['X'] for a in OURS if a != 'T' for e in common if DEC[a][e]['wheat_bp_price']['X']]
    P(f'Wheat bought as product (not recorded apart from wheat seed): estimated as bought - planted; implied price per product unit '
      f'{min(bpp):.1f}..{max(bpp):.1f} (median {st.median(bpp):.1f}) over all games, a normal early-season wheat price. The '
      '"unsold at the end" line moves to "wheat bought" if some seeds were left unplanted; its range with the lower bound '
      '(held >= 0) is ' + '; '.join(f'{lab(a)} {lo:+,.0f}..{hi:+,.0f}' for a, (lo, hi) in held_rng.items()) + ' (mean per game).')
    P('')
    # units moved
    P('Units sold on other days than the leader (sale-day mix distance x our units sold), mean per game:')
    P('')
    P('| arm | ' + ' | '.join(PRODUCTS) + ' | all |')
    P('|---|' + '---:|' * (len(PRODUCTS) + 1))
    for a in OURS:
        um = [st.mean(DEC[a][e]['units_moved'][p] for e in common) for p in PRODUCTS]
        P(f'| {lab(a)} | ' + ' | '.join(f'{x:.0f}' for x in um) + f' | {sum(um):.0f} |')
    P('')

    # ================= 6. by product
    P('## 6. Revenue gap by product (leader - ours = production A + unsold C1 + price C2), mean per game, all worlds')
    P('')
    P('| arm | ' + ' | '.join(PRODUCTS) + ' | total revenue gap | purchases + land + wages gap | = cash gap |')
    P('|---|' + '---:|' * (len(PRODUCTS) + 3))
    for a in OURS:
        rg = {p: st.mean(DEC[a][e]['A'][p] + DEC[a][e]['C1'][p] + DEC[a][e]['C2'][p] for e in common) for p in PRODUCTS}
        tot = sum(rg.values())
        P(f'| {lab(a)} | ' + ' | '.join(f0(rg[p]) for p in PRODUCTS) + f' | {f0(tot)} | {f0(st.mean(gap[a][e] for e in common) - tot)} | '
          f'{f0(st.mean(gap[a][e] for e in common))} |')
    P('')
    P('Units harvested (fertilizer: collected) and sold per game, and average price, leader vs each arm:')
    P('')
    P('| product | ' + ' | '.join(lab(a) for a in ARMS) + ' |')
    P('|---|' + '---|' * len(ARMS))
    for p in PRODUCTS:
        cells = []
        for a in ARMS:
            ts = [R[a][e]['totals'] for e in common]
            h = st.mean(t['harvested'].get(p, 0) for t in ts)
            q = st.mean(t['sold'].get(p, 0) for t in ts)
            rv = sum(t['rev'].get(p, 0) for t in ts)
            qs = sum(t['sold'].get(p, 0) for t in ts)
            cells.append(f'{h:.0f} / {q:.0f} @ {rv / qs if qs else 0:.0f}')
        P(f'| {p} | ' + ' | '.join(cells) + ' |')
    P('')
    P('Plantings per game by crop (in brackets: on days after our plant_cutoff day, '
      + ', '.join(f'{c} {CUTOFF[c]}' for c in CROPS) + '), animals bought, animal-days on the board, empty coop / '
      'pasture tile-days, land:')
    P('')
    P('| arm | ' + ' | '.join(CROPS) + ' | ' + ' | '.join(f'{s} bought' for s in ANIMALS) + ' | '
      + ' | '.join(f'{s}-days' for s in ANIMALS) + ' | empty coop / pasture tile-days | land spend |')
    P('|---|' + '---:|' * (len(CROPS) + 2 * len(ANIMALS) + 2))
    for a in ARMS:
        ts = [R[a][e]['totals'] for e in common]
        cells = []
        for c in CROPS:
            tot = st.mean(t['plant'].get(c, 0) for t in ts)
            post = st.mean(sum(dd.get('plant', {}).get(c, 0) for d, dd in enumerate(R[a][e]['days']) if d > CUTOFF[c]) for e in common)
            cells.append(f'{tot:.1f} ({post:.1f})')
        ad = [st.mean(sum(q['occ_tile_days'].get(s, 0) for q in R[a][e]['quadrants'].values()) for e in common) for s in ANIMALS]
        emp = st.mean(sum(q['occ_tile_days'].get('S_COOP', 0) + q['occ_tile_days'].get('S_PASTURE', 0)
                          for q in R[a][e]['quadrants'].values()) for e in common)
        P(f'| {lab(a)} | ' + ' | '.join(cells) + ' | '
          + ' | '.join(f"{st.mean(t['bought'].get(s, 0) for t in ts):.1f}" for s in ANIMALS) + ' | '
          + ' | '.join(f'{x:.0f}' for x in ad) + f' | {emp:.0f} | {st.mean(t["land_spend"] for t in ts):,.0f} |')
    P('')

    P('Plantings inside our planting window (day <= plant_cutoff), and planting-days behind the leader (sum over days of '
      'the leader\'s cumulative in-window plantings minus ours, when positive); arms that follow the leader\'s counts:')
    P('')
    P('| arm | ' + ' | '.join(f'{c} in window / days behind' for c in CROPS) + ' |')
    P('|---|' + '---|' * len(CROPS))
    for a in ['LEADER', 'T0', 'T', 'S', 'S0']:
        cells = []
        for c in CROPS:
            inw = st.mean(sum(dd.get('plant', {}).get(c, 0) for d, dd in enumerate(R[a][e]['days']) if d <= CUTOFF[c]) for e in common)
            behind = []
            for e in common:
                cl = cx = b = 0
                for d in range(CUTOFF[c] + 1):
                    cl += R['LEADER'][e]['days'][d].get('plant', {}).get(c, 0)
                    cx += R[a][e]['days'][d].get('plant', {}).get(c, 0)
                    b += max(0, cl - cx)
                behind.append(b)
            cells.append(f'{inw:.1f} / {st.mean(behind):.0f}')
        P(f'| {lab(a)} | ' + ' | '.join(cells) + ' |')
    P('')

    # ================= 7. quadrants
    P('## 7. Where the gap sits: per quadrant')
    P('')
    P('Harvested units (HARVEST and COLLECT_FERTILIZER) are attributed to the tile the unit stood on. Output value = units x '
      'the LEADER\'s average price in that world (comparable across arms); "own-price income" = units x the arm\'s own average '
      'price (as in the panel report). Held tile-days = unlocked tile-days (25 tiles x days held); occupied = a crop, animal '
      'or structure at day start. Means per game, all worlds.')
    P('')
    qval = {a: {e: {} for e in common} for a in ARMS}
    for a in ARMS:
        for e in common:
            PLe = DEC['T'][e]['PL']
            for q in QN:
                hv = R[a][e]['quadrants'][q]['harvested']
                qval[a][e][q] = sum(v * PLe.get(p, 0) for p, v in hv.items())
    P('| arm | quadrant | held tile-days | occupied tile-days | output value (leader prices) | per held tile-day | per occupied tile-day | own-price income | gap to leader output (t CI) |')
    P('|---|---|---:|---:|---:|---:|---:|---:|---|')
    for a in ARMS:
        for q in QN:
            qs = [R[a][e]['quadrants'][q] for e in common]
            held = st.mean(x['unlocked_tile_days'] for x in qs)
            occ = st.mean(sum(v for k, v in x['occ_tile_days'].items() if k not in ('EMPTY', 'WEED')) for x in qs)
            val = st.mean(qval[a][e][q] for e in common)
            inc = st.mean(x['income'] for x in qs)
            g = '' if a == 'LEADER' else ft([qval['LEADER'][e][q] - qval[a][e][q] for e in common])
            P(f'| {lab(a)} | {q} ({QCOST[q]}) | {held:.0f} | {occ:.0f} | {val:,.0f} | {val / held if held else 0:.1f} | '
              f'{val / occ if occ else 0:.1f} | {inc:,.0f} | {g} |')
    P('')
    P('Output gap to the leader by quadrant as a share of the cash gap (leader-price output; the output gap is gross: it '
      'also includes fertilizer the leader spreads and wheat it feeds):')
    P('')
    P('| arm | cash gap | output gap all quadrants | first | second | third | fourth |')
    P('|---|---:|---:|---:|---:|---:|---:|')
    for a in OURS:
        cg = st.mean(gap[a][e] for e in common)
        qg = {q: st.mean(qval['LEADER'][e][q] - qval[a][e][q] for e in common) for q in QN}
        P(f'| {lab(a)} | {f0(cg)} | {f0(sum(qg.values()))} | ' + ' | '.join(f'{f0(qg[q])} ({qg[q] / cg:.0%})' for q in QN) + ' |')
    P('')
    for a in ('T', 'S', 'D'):
        P(f'Output gap to the leader by quadrant x product for {lab(a)} (leader prices, mean per game; positive = leader ahead):')
        P('')
        P('| product | ' + ' | '.join(QN) + ' | all |')
        P('|---|' + '---:|' * 5)
        colt = Counter()
        for p in PRODUCTS:
            vals = []
            for q in QN:
                v = st.mean((R['LEADER'][e]['quadrants'][q]['harvested'].get(p, 0) - R[a][e]['quadrants'][q]['harvested'].get(p, 0))
                            * DEC['T'][e]['PL'][p] for e in common)
                vals.append(v)
                colt[q] += v
            P(f'| {p} | ' + ' | '.join(f0(v) for v in vals) + f' | {f0(sum(vals))} |')
        P('| all | ' + ' | '.join(f0(colt[q]) for q in QN) + f' | {f0(sum(colt.values()))} |')
        P('')
    P('Harvested units by product per quadrant (mean per game):')
    P('')
    for q in QN:
        P(f'**{q} quadrant ({QCOST[q]})**')
        P('')
        P('| arm | ' + ' | '.join(PRODUCTS) + ' | unwatered plants | rotted plants (units lost) | escaped animals |')
        P('|---|' + '---:|' * (len(PRODUCTS) + 3))
        for a in ARMS:
            qs = [R[a][e]['quadrants'][q] for e in common]
            dth = Counter()
            for x in qs:
                for k, v in x['deaths'].items():
                    dth[k.split('_')[0]] += v
            ru = sum(sum(x['rot_units'].values()) for x in qs) / n
            P(f'| {lab(a)} | ' + ' | '.join(f"{st.mean(x['harvested'].get(p, 0) for x in qs):.0f}" for p in PRODUCTS)
              + f" | {dth['unwatered'] / n:.1f} | {dth['rotted'] / n:.1f} ({ru:.1f}) | {dth['escaped'] / n:.1f} |")
        P('')
    P('Quadrant occupancy by kind (tile-days per game at day start):')
    P('')
    kinds = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'COW', 'SHEEP', 'GOOSE', 'EMPTY', 'WEED']
    P('| arm | quadrant | ' + ' | '.join(kinds) + ' | other |')
    P('|---|---|' + '---:|' * (len(kinds) + 1))
    for a in ARMS:
        for q in QN:
            qs = [R[a][e]['quadrants'][q]['occ_tile_days'] for e in common]
            tot = st.mean(sum(x.values()) for x in qs)
            vals = [st.mean(x.get(k, 0) for x in qs) for k in kinds]
            P(f'| {lab(a)} | {q} | ' + ' | '.join(f'{v:.0f}' for v in vals) + f' | {tot - sum(vals):.0f} |')
    P('')
    P('Maintenance ops by quadrant (mean per game; W / F / C / H / FE / CF):')
    P('')
    P('| arm | ' + ' | '.join(QN) + ' |')
    P('|---|' + '---|' * 4)
    for a in ARMS:
        cells = []
        for q in QN:
            ops = Counter()
            for e in common:
                ops.update(R[a][e]['quadrants'][q]['ops'])
            cells.append('/'.join(f'{ops[k] / n:.0f}' for k in ('WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE', 'COLLECT_FERTILIZER')))
        P(f'| {lab(a)} | ' + ' | '.join(cells) + ' |')
    P('')

    # ================= 8. work ledger
    P('## 8. Work ledger (mean per game, all worlds)')
    P('')
    P('| arm | unit-steps | moves | idle (PASS) | no-effect cmds | maint ops | WATER | FEED | CARE | HARVEST | FERTILIZE | COLLECT_F | PLANT | DIG | moves / maint op | shed pickups (items) | deposits | hires | wages | midnight cap discards |')
    P('|---|' + '---:|' * 20)
    for a in ARMS:
        ts = [R[a][e]['totals'] for e in common]
        mm = lambda f: st.mean(f(t) for t in ts)
        eo = lambda k: mm(lambda t: t['eff_ops'].get(k, 0))
        P(f"| {lab(a)} | {mm(lambda t: t['unit_steps']):,.0f} | {mm(lambda t: t['moves']):,.0f} | {mm(lambda t: t['passes']):,.0f} | "
          f"{mm(lambda t: sum(t['noeff'].values())):,.0f} | {mm(lambda t: t['maint_ops_eff']):,.0f} | "
          + ' | '.join(f'{eo(k):,.0f}' for k in MAINT + ['PLANT', 'DIG'])
          + f" | {mm(lambda t: t['moves']) / mm(lambda t: t['maint_ops_eff']):.2f} | {mm(lambda t: t['pickups']):.0f} ({mm(lambda t: t['pickup_items']):.0f}) | "
          f"{mm(lambda t: t['deposits']):.0f} | {mm(lambda t: t['hires']):.0f} | {mm(lambda t: t['wages']):,.0f} | {mm(lambda t: t['discards_total']):.1f} |")
    P('')
    P('Deaths and losses (mean per game): unwatered plants by crop, rotted plants and units lost to decay, escaped animals.')
    P('')
    P('| arm | unwatered W/C/T/S/M | rotted plants W/C/T/S/M | rot units W/C/T/S/M | escaped cow/sheep/goose | cap discards by product |')
    P('|---|---|---|---|---|---|')
    for a in ARMS:
        ts = [R[a][e]['totals'] for e in common]
        dd = lambda key: '/'.join(f"{st.mean(t['deaths'].get(key + c, 0) for t in ts):.1f}" for c in CROPS)
        esc = '/'.join(f"{st.mean(t['deaths'].get('escaped_' + s, 0) for t in ts):.1f}" for s in ANIMALS)
        disc = Counter()
        for t in ts:
            disc.update(t['discards'])
        P(f"| {lab(a)} | {dd('unwatered_')} | {dd('rotted_')} | {dd('rot_units_')} | {esc} | "
          + ', '.join(f'{k} {v / n:.1f}' for k, v in disc.most_common() if v / n >= 0.1) + ' |')
    P('')
    # daily labour: hands match
    P('Hands per day vs the leader\'s (day-start hands over 30 days): ' + '; '.join(
        f"{lab(a)} {st.mean(sum(dd['hands'] for dd in R[a][e]['days']) for e in common):.0f} vs "
        f"{st.mean(sum(dd['target_hands'] for dd in R[a][e]['days']) for e in common):.0f}" for a in OURS) + '.')
    P('')

    # ================= per world
    P('## 9. Per world: final cash, ratio to the leader, gap')
    P('')
    P('LEADER column = the LEADER arm\'s final (= recorded leader cash in every world). Cells: our final / ratio / gap (positive = leader ahead).')
    P('')
    P('| world | team | leader | ' + ' | '.join(lab(a) for a in OURS) + ' | collapse in |')
    P('|---|---|---:|' + '---|' * len(OURS) + '---|')
    for e in common:
        cl = ','.join(lab(a) for a in ARMS if R[a][e]['opp_collapse']) + (' (known)' if worlds[e]['flags'] else '')
        P(f"| {e} | {team[e]} | {fin['LEADER'][e]:,.0f} | " + ' | '.join(
            f"{fin[a][e]:,.0f} / {fin[a][e] / fin['LEADER'][e]:.3f} / {gap[a][e]:+,.0f}" for a in OURS) + f' | {cl} |')
    P('')

    txt = '\n'.join(o) + '\n'
    slim = {a: {str(e): dict(gap=DEC[a][e]['gap'], lines=DEC[a][e]['lines'], A=DEC[a][e]['A'], C1=DEC[a][e]['C1'],
                             C2=DEC[a][e]['C2'], timing=DEC[a][e]['timing'], depth=DEC[a][e]['depth'],
                             supply_t=DEC[a][e]['supply_t'], units_moved=DEC[a][e]['units_moved'],
                             wheat_bp=DEC[a][e]['wheat_bp'], quadrant_value_leader_prices=qval[a][e],
                             leader_quadrant_value=qval['LEADER'][e])
                for e in common} for a in OURS}
    (OUT / 'gap_per_game.json').write_text(json.dumps(slim, default=str), encoding='utf-8')
    print(txt)


if __name__ == '__main__':
    main()
