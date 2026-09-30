"""T-gap deep decomposition (2026-09-25). Stored data only, one process, no games.

Leader's own recorded game vs T (our leader-plan agent, agents/mgt_lead.py defaults) in the same 12 leader worlds.
Positive numbers = leader ahead (they widen the gap).

Inputs
  E1's ledger  results/fresh/kaggle_remote_lead/ledg1/output/kgr-ledg1-s0/out/repo/results/fresh/lead_ledger/
  local copy   results/fresh/lead_ledger/{leader,ours}_<ep>.json  (same 24 runs: checked field-identical to E1's on
               every field E1 has, and adds board_list / plants / overflow / shed_after, which this script needs).
Engine rules used for potentials: kaggle_environments 1.32.7 kaggriculture.py (CROPS / ANIMALS, _daily_refresh_*).

Top level (reproduces the lead's t_decomp.py): gap = A + inputs + B + land + C1 + C2, residual 0.
  A  = (harvested_L - harvested_O) x leader realised price   (fertilizer: sold units, as in t_decomp.py)
  C1 = -[(harv_L - sold_L) - (harv_O - sold_O)] x leader price
  C2 = sold_O x (leader price - our price)
Deeper splits (all exact, residual 0):
  crops    h = n x pot/planting x (1 - lost-to-death share) x (1 - decayed share) x realisation, sequential shift-share
           (first term = plantings diff x leader units per planting).
  animals  h = N x pot/animal x (1 - lost-to-escape share) x realisation; also animal-days x output per animal-day.
  fert     sold = collected + bought - applied - held_end - discarded; collected = animal-days x collection rate.
  C1       wheat: harv - sold = fed + held_end + discarded - bought; others: held_end + discarded.
  C2       timing = sold_O x sum_d (wL_d - wO_d) x pO~_d  (our units on the leader's days, at our daily price)
           volume = sold_O x sum_d wL_d x (pL_d - pO~_d)  (same-day price gap: the market depth of our lower volume)
           pO~_d = our realised price that day, linearly interpolated on days we sold nothing.
"""
import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
E1 = ROOT / 'results/fresh/kaggle_remote_lead/ledg1/output/kgr-ledg1-s0/out/repo/results/fresh/lead_ledger'
LOC = ROOT / 'results/fresh/lead_ledger'
SEM = ROOT / 'data/leader_semantics'
OUT = Path(__file__).resolve().parent

CROPS = {
    "WHEAT":      {"first": 2, "maxday": 4, "interval": 0, "max": 6, "ongoing": False, "pot": 4},
    "CARROT":     {"first": 2, "maxday": 3, "interval": 0, "max": 4, "ongoing": False, "pot": 3},
    "TOMATO":     {"first": 8, "maxday": 8, "interval": 1, "max": 4, "ongoing": True},
    "STRAWBERRY": {"first": 10, "maxday": 10, "interval": 2, "max": 4, "ongoing": True},
    "MELON":      {"first": 10, "maxday": 12, "interval": 0, "max": 6, "ongoing": False, "pot": 6},
}
ANIMALS = {"GOOSE": ("EGG", 4, 1), "COW": ("MILK", 8, 2), "SHEEP": ("WOOL", 6, 3)}   # product, first_yield_day, interval
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
BASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}
LAST_PROD_DAY = 28          # a yield produced at the end of day 28 is harvestable on day 29 (last action step 718)


# ---------------------------------------------------------------- loading
def load():
    games = []
    n_fields = 0
    for f in sorted(E1.glob('ours_*.json')):
        ep = f.stem[5:]
        pair = {}
        for side in ('leader', 'ours'):
            e1 = json.load(open(E1 / f'{side}_{ep}.json'))
            lo = json.load(open(LOC / f'{side}_{ep}.json'))
            for k in ('final', 'opp_final', 'target', 'seat', 'game'):
                assert e1[k] == lo[k], (ep, side, k)
            for d in range(30):
                for k, v in e1['days'][d].items():
                    n_fields += 1
                    if k == 'unit_spans':
                        assert sorted(map(tuple, v)) == sorted(map(tuple, lo['days'][d][k])), (ep, side, d, k)
                    else:
                        assert v == lo['days'][d][k], (ep, side, d, k)
            pair[side] = lo
        team = pair['ours']['game'].split(':')[0]
        g = json.load(gzip.open(SEM / team / f'{ep}.json.gz', 'rt', encoding='utf-8'))
        b = ''.join(g['days'][-1]['board'])
        four = [b[i:i + 2] for i in range(0, len(b), 2)].count(' L') == 0
        games.append(dict(ep=ep, team=team, four=four, L=pair['leader'], O=pair['ours']))
    return games, n_fields


def tot(side, key):
    c = Counter()
    for day in side['days']:
        c.update(day.get(key) or {})
    return c


def opk(side):
    return tot(side, 'opk')


# ---------------------------------------------------------------- stock identity
def flows(day):
    f = Counter()
    for k, v in (day.get('harv') or {}).items():
        f[k] += v
    for k, v in (day.get('bought') or {}).items():
        if k.startswith('BUY_PRODUCT:'):
            f[k.split(':')[1]] += v
    for k, v in (day.get('sold') or {}).items():
        f[k] -= v
    for k, v in (day.get('opk') or {}).items():
        op = k.split(':')[0]
        if op == 'FEED':
            f['WHEAT'] -= v
        elif op == 'FERTILIZE':
            f['FERTILIZER'] -= v
        elif op == 'COLLECT_FERTILIZER':
            f['FERTILIZER'] += v
    return f


def stock(side):
    """End-of-game holdings per product and midnight shed-cap discards; asserts the day 0-28 shed identity."""
    prev = Counter()
    disc = Counter()
    for d in range(29):
        dd = side['days'][d]
        fl = flows(dd)
        after = Counter({k: v for k, v in (dd['shed_after'] or {}).items() if k in PRODUCTS})
        for p in PRODUCTS:
            ov = (dd.get('overflow') or {}).get(p, 0)
            disc[p] += ov
            assert prev.get(p, 0) + fl.get(p, 0) - ov == after.get(p, 0), (side['episode'], side['side'], d, p)
        prev = after
    fl = flows(side['days'][29])          # day 29 has no end-of-day hook: no midnight drop, holdings = shed + carried
    held = Counter({p: prev.get(p, 0) + fl.get(p, 0) for p in PRODUCTS})
    return held, disc


# ---------------------------------------------------------------- crop plantings
def prod_days(crop, d):
    c = CROPS[crop]
    return [d + c['first'] - 1 + j * c['interval'] for j in range(c['max'])]


def pot(crop, d):
    """Base units of one planting on day d: full water, no fertilizer, harvested at full age (or on day 29)."""
    c = CROPS[crop]
    if c['ongoing']:
        return sum(1 for k in prod_days(crop, d) if k <= LAST_PROD_DAY)
    room = 29 - d
    if room < c['first']:
        return 0
    if crop == 'MELON':
        return 6
    return min(c['pot'], room)


def plantings(side):
    days = side['days']
    boards = [dd['board_list'] for dd in days]
    by_tile = defaultdict(list)
    for d, dd in enumerate(days):
        for t, c in dd['plants']:
            by_tile[t].append((d, c))
    out = []
    for t, lst in by_tile.items():
        lst.sort()
        for i, (d, c) in enumerate(lst):
            nxt = lst[i + 1][0] if i + 1 < len(lst) else None
            end, outcome = None, 'alive_end'
            for e in range(d + 1, 30):
                if nxt is not None and e > nxt:
                    break
                if boards[e][t] != c:
                    end, outcome = e - 1, ('WEED' if boards[e][t] == 'WEED' else 'removed')
                    break
            if end is None and nxt is not None:
                end, outcome = nxt, 'removed'
            out.append(dict(tile=t, crop=c, d=d, end=end, outcome=outcome, pot=pot(c, d)))
    # end-of-day deaths (unwatered) from the ledger's died counter; other WEED outcomes decayed mid-day (unharvested)
    cand = defaultdict(list)
    for p in out:
        if p['outcome'] == 'WEED':
            cand[(p['end'], p['crop'])].append(p)
    unmatched = 0
    for (k, c), ps in cand.items():
        n_d = (days[k].get('died') or {}).get('plant_' + c, 0)
        ps.sort(key=lambda p: k - p['d'])
        for j, p in enumerate(ps):
            p['outcome'] = 'died' if j < n_d else 'decayed'
        unmatched += max(0, n_d - len(ps))
    for k in range(30):
        for key, v in (days[k].get('died') or {}).items():
            if key.startswith('plant_') and (k, key[6:]) not in cand:
                unmatched += v
    for p in out:
        p['lost'] = 0
        if p['outcome'] == 'died':
            if CROPS[p['crop']]['ongoing']:
                p['lost'] = sum(1 for k in prod_days(p['crop'], p['d']) if p['end'] <= k <= LAST_PROD_DAY)
            else:
                p['lost'] = p['pot']
        p['decay_lost'] = p['pot'] if (p['outcome'] == 'decayed' and not CROPS[p['crop']]['ongoing']) else 0
    return out, unmatched


# ---------------------------------------------------------------- animals
def animals(side):
    days = side['days']
    boards = [dd['board_list'] for dd in days]
    inst = []
    for t in range(100):
        d = 0
        while d < 30:
            k = boards[d][t]
            if k in ANIMALS:
                s = d
                while d + 1 < 30 and boards[d + 1][t] == k:
                    d += 1
                inst.append(dict(tile=t, sp=k, p=s - 1, last=d, esc=d < 29))
            d += 1
    esc_ledger = sum(v for dd in days for key, v in (dd.get('died') or {}).items() if key.startswith('animal_'))
    for a in inst:
        _, first, iv = ANIMALS[a['sp']]

        def n_prod(K):
            return sum(1 for k in range(a['p'], K + 1) if (k + 1 - a['p'] - first) >= 0 and (k + 1 - a['p'] - first) % iv == 0)
        a['pot_full'] = n_prod(LAST_PROD_DAY)
        a['pot_act'] = n_prod(min(LAST_PROD_DAY, a['last'] - 1)) if a['esc'] else a['pot_full']
        a['ad'] = a['last'] - a['p']
    return inst, esc_ledger - sum(1 for a in inst if a['esc'])


# ---------------------------------------------------------------- shift-share
def shift_share(fL, fO):
    """Sequential exact decomposition of prod(fL) - prod(fO); term i = fO[:i] x (fL[i]-fO[i]) x fL[i+1:]."""
    terms = []
    for i in range(len(fL)):
        v = fL[i] - fO[i]
        for j in range(i):
            v *= fO[j]
        for j in range(i + 1, len(fL)):
            v *= fL[j]
        terms.append(v)
    return terms


def crop_factors(n, pot_all, lost, decay, h):
    if n == 0:
        return None
    pb = pot_all / n
    surv = pot_all - lost
    f_death = surv / pot_all if pot_all else 1.0
    f_decay = (surv - decay) / surv if surv else 1.0
    harv_pot = surv - decay
    r = h / harv_pot if harv_pot else None
    return [n, pb, f_death, f_decay, r]


def decompose_product(fL, fO, hL, hO, nfac):
    """Returns (terms, chain): chain = product of the leader's factors after the second one (units per potential unit),
    so terms[0] + terms[1] = (potential_L - potential_O) x chain."""
    if fL is None and fO is None:
        return [0.0] * nfac, 0.0
    if fL is None:
        fO2 = [1.0 if v is None else v for v in fO]
        return [-hO] + [0.0] * (nfac - 1), math.prod(fO2[2:])
    if fO is None:
        fL2 = [1.0 if v is None else v for v in fL]
        return [hL] + [0.0] * (nfac - 1), math.prod(fL2[2:])
    fL, fO = list(fL), list(fO)
    # degenerate factor (zero potential): borrow the other side's value so the term lands on the potential factor
    for i in range(nfac):
        if fL[i] is None:
            fL[i] = fO[i] if fO[i] is not None else 0.0
        if fO[i] is None:
            fO[i] = fL[i]
    t = shift_share(fL, fO)
    err = (hL - hO) - sum(t)
    if abs(err) > 1e-6:          # only possible when a side has h > 0 on zero potential; put it on realisation
        t[-1] += err
    return t, math.prod(fL[2:])


def plant_cutoff():
    """T's planting cutoff (agents/mgt_lead.py CFG['plant_cutoff']), parsed from the source without importing it."""
    import ast
    src = (ROOT / 'agents/mgt_lead.py').read_text(encoding='utf-8')
    i = src.index('"plant_cutoff":')
    j = src.index('}', i)
    return ast.literal_eval(src[src.index('{', i):j + 1])


# ---------------------------------------------------------------- per-game analysis
def daily(side, p):
    q = [side['days'][d].get('sold', {}).get(p, 0) for d in range(30)]
    r = [side['days'][d].get('rev', {}).get(p, 0) for d in range(30)]
    return q, r


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
            out.append(prices[(lo or hi)[-1 if lo else 0]])
    return out


CUTOFF = None


def analyse(g):
    global CUTOFF
    if CUTOFF is None:
        CUTOFF = plant_cutoff()
    L, O = g['L'], g['O']
    R = {s: tot(x, 'rev') for s, x in (('L', L), ('O', O))}
    Q = {s: tot(x, 'sold') for s, x in (('L', L), ('O', O))}
    H = {s: tot(x, 'harv') for s, x in (('L', L), ('O', O))}
    S = {s: tot(x, 'spend') for s, x in (('L', L), ('O', O))}
    B = {s: tot(x, 'bought') for s, x in (('L', L), ('O', O))}
    K = {s: opk(x) for s, x in (('L', L), ('O', O))}
    W = {s: sum(d.get('wages', 0) or 0 for d in x['days']) for s, x in (('L', L), ('O', O))}
    LAND = {s: sum(d.get('land', 0) or 0 for d in x['days']) for s, x in (('L', L), ('O', O))}
    held, disc = {}, {}
    for s, x in (('L', L), ('O', O)):
        held[s], disc[s] = stock(x)
    PL, PO = {}, {}
    for p in PRODUCTS:
        PL[p] = R['L'][p] / Q['L'][p] if Q['L'][p] else (R['O'][p] / Q['O'][p] if Q['O'][p] else 0.0)
        PO[p] = R['O'][p] / Q['O'][p] if Q['O'][p] else PL[p]
    r = dict(ep=g['ep'], team=g['team'], four=g['four'], gap=L['final'] - O['final'])
    # ---- lead's top level
    A, C1, C2 = {}, {}, {}
    for p in PRODUCTS:
        hL, hO = (H['L'][p], H['O'][p]) if p != 'FERTILIZER' else (Q['L'][p], Q['O'][p])
        A[p] = (hL - hO) * PL[p]
        C1[p] = -((hL - Q['L'][p]) - (hO - Q['O'][p])) * PL[p]
        C2[p] = Q['O'][p] * (PL[p] - PO[p])
    spend_cat = Counter()
    for s, sign in (('L', -1), ('O', 1)):
        for k, v in S[s].items():
            op, item = k.split(':')
            cat = {'BUY_SEED': 'seeds', 'BUY_ANIMAL': 'animals'}.get(op, 'buy_' + item.lower())
            spend_cat[cat] += sign * v
    r['A'], r['C1'], r['C2'] = sum(A.values()), sum(C1.values()), sum(C2.values())
    r['inputs'] = sum(spend_cat.values())
    r['wages'] = W['O'] - W['L']
    r['land'] = LAND['O'] - LAND['L']
    r['resid_top'] = r['gap'] - (r['A'] + r['inputs'] + r['wages'] + r['land'] + r['C1'] + r['C2'])
    r['A_p'], r['C1_p'], r['C2_p'], r['spend_cat'] = A, C1, C2, dict(spend_cat)
    r['PL'], r['PO'] = PL, PO
    # ---- part 1: crops
    pl, unm = {}, {}
    for s, x in (('L', L), ('O', O)):
        pl[s], unm[s] = plantings(x)
    r['death_unmatched'] = unm
    crop = {}
    for c in CROPS:
        agg = {}
        for s in ('L', 'O'):
            ps = [p for p in pl[s] if p['crop'] == c]
            plant_ctr = tot(L if s == 'L' else O, 'plant')[c]
            assert len(ps) == plant_ctr, (g['ep'], s, c, len(ps), plant_ctr)
            died = [p for p in ps if p['outcome'] == 'died']
            agg[s] = dict(n=len(ps), pot=sum(p['pot'] for p in ps), lost=sum(p['lost'] for p in ps),
                          pot_post=sum(p['pot'] for p in ps if p['d'] > CUTOFF[c]),
                          n_post=sum(1 for p in ps if p['d'] > CUTOFF[c]),
                          decay=sum(p['decay_lost'] for p in ps), h=H[s][c],
                          died=len(died), died_prem=sum(1 for p in died if p['lost'] > 0),
                          decayed=sum(1 for p in ps if p['outcome'] == 'decayed'),
                          mean_day=(sum(p['d'] for p in ps) / len(ps)) if ps else None,
                          td=sum(d['board'].get(c, 0) for d in (L if s == 'L' else O)['days']),
                          water=K[s].get('WATER:' + c, 0), fert=K[s].get('FERTILIZE:' + c, 0),
                          harv_ops=K[s].get('HARVEST:' + c, 0), dig=K[s].get('DIG:' + c, 0))
        fL = crop_factors(agg['L']['n'], agg['L']['pot'], agg['L']['lost'], agg['L']['decay'], agg['L']['h'])
        fO = crop_factors(agg['O']['n'], agg['O']['pot'], agg['O']['lost'], agg['O']['decay'], agg['O']['h'])
        t, chain = decompose_product(fL, fO, agg['L']['h'], agg['O']['h'], 5)
        terms = [v * PL[c] for v in t]
        assert abs(sum(terms) - A[c]) < 1e-6, (g['ep'], c)
        # plantings + dates = potential diff x leader chain; split by T's planting cutoff (within window vs skipped)
        post = (agg['L']['pot_post'] - agg['O']['pot_post']) * chain * PL[c]
        pre = terms[0] + terms[1] - post
        crop[c] = dict(agg=agg, terms=terms, window=[pre, post])
    r['crop'] = crop
    # ---- part 1: animals
    an, esc_unm = {}, {}
    for s, x in (('L', L), ('O', O)):
        an[s], esc_unm[s] = animals(x)
        for sp in ANIMALS:
            assert sum(a['ad'] for a in an[s] if a['sp'] == sp) == sum(d['board'].get(sp, 0) for d in x['days'])
    r['escape_unmatched'] = esc_unm
    anim = {}
    for sp, (prod, _, _) in ANIMALS.items():
        agg = {}
        for s in ('L', 'O'):
            ins = [a for a in an[s] if a['sp'] == sp]
            agg[s] = dict(N=len(ins), pot=sum(a['pot_full'] for a in ins), act=sum(a['pot_act'] for a in ins),
                          ad=sum(a['ad'] for a in ins), esc=sum(1 for a in ins if a['esc']), h=H[s][prod],
                          mean_p=(sum(a['p'] for a in ins) / len(ins)) if ins else None,
                          feed=K[s].get('FEED:' + sp, 0), care=K[s].get('CARE:' + sp, 0),
                          harv_ops=K[s].get('HARVEST:' + sp, 0), coll=K[s].get('COLLECT_FERTILIZER:' + sp, 0))

        def fac(a):
            if a['N'] == 0:
                return None
            return [a['N'], a['pot'] / a['N'], (a['act'] / a['pot']) if a['pot'] else 1.0,
                    (a['h'] / a['act']) if a['act'] else None]
        t, _ = decompose_product(fac(agg['L']), fac(agg['O']), agg['L']['h'], agg['O']['h'], 4)
        terms = [v * PL[prod] for v in t]
        assert abs(sum(terms) - A[prod]) < 1e-6
        # animal-days view
        adL, adO = agg['L']['ad'], agg['O']['ad']
        yL = agg['L']['h'] / adL if adL else (agg['O']['h'] / adO if adO else 0.0)
        yO = agg['O']['h'] / adO if adO else yL
        ad_terms = [(adL - adO) * yL * PL[prod], adO * (yL - yO) * PL[prod]]
        assert abs(sum(ad_terms) - A[prod]) < 1e-6
        anim[sp] = dict(agg=agg, terms=terms, ad_terms=ad_terms)
    r['anim'] = anim
    # ---- part 1: fertilizer (A_fert = sold diff x leader price)
    fz = {}
    for s in ('L', 'O'):
        coll = sum(v for k, v in K[s].items() if k.startswith('COLLECT_FERTILIZER:'))
        used = sum(v for k, v in K[s].items() if k.startswith('FERTILIZE:'))
        bought = B[s].get('BUY_PRODUCT:FERTILIZER', 0)
        ad = sum(sum(d['board'].get(sp, 0) for sp in ANIMALS) for d in (L if s == 'L' else O)['days'])
        assert coll + bought - used - held[s]['FERTILIZER'] - disc[s]['FERTILIZER'] == Q[s]['FERTILIZER']
        fz[s] = dict(coll=coll, used=used, bought=bought, held=held[s]['FERTILIZER'], disc=disc[s]['FERTILIZER'], ad=ad,
                     rate=coll / ad if ad else 0.0)
    pf = PL['FERTILIZER']
    rL = fz['L']['rate'] if fz['L']['ad'] else fz['O']['rate']
    rO = fz['O']['rate'] if fz['O']['ad'] else rL
    fert_terms = dict(ad=(fz['L']['ad'] - fz['O']['ad']) * rL * pf, rate=fz['O']['ad'] * (rL - rO) * pf,
                      applied=-(fz['L']['used'] - fz['O']['used']) * pf, bought=(fz['L']['bought'] - fz['O']['bought']) * pf,
                      held=-(fz['L']['held'] - fz['O']['held']) * pf, disc=-(fz['L']['disc'] - fz['O']['disc']) * pf)
    assert abs(sum(fert_terms.values()) - A['FERTILIZER']) < 1e-6
    r['fert'] = dict(side=fz, terms=fert_terms)
    # ---- part 3: C1 components
    c1 = {}
    for p in PRODUCTS:
        if p == 'FERTILIZER':
            continue
        fed = {s: (sum(v for k, v in K[s].items() if k.startswith('FEED:')) if p == 'WHEAT' else 0) for s in ('L', 'O')}
        bo = {s: (B[s].get('BUY_PRODUCT:WHEAT', 0) if p == 'WHEAT' else 0) for s in ('L', 'O')}
        for s in ('L', 'O'):
            assert H[s][p] - Q[s][p] == fed[s] + held[s][p] + disc[s][p] - bo[s], (g['ep'], s, p)
        comp = dict(fed=-(fed['L'] - fed['O']) * PL[p], held=-(held['L'][p] - held['O'][p]) * PL[p],
                    disc=-(disc['L'][p] - disc['O'][p]) * PL[p], bought=(bo['L'] - bo['O']) * PL[p])
        assert abs(sum(comp.values()) - C1[p]) < 1e-6
        c1[p] = dict(comp=comp, fed=fed, held={s: held[s][p] for s in ('L', 'O')},
                     disc={s: disc[s][p] for s in ('L', 'O')}, bought=bo)
    r['c1'] = c1
    # ---- part 2: C2 timing vs volume; timing further split into supply timing (when units become available) vs holding
    def supply(side, sname, p):
        out = []
        for d in range(30):
            dd = side['days'][d]
            v = dd.get('harv', {}).get(p, 0)
            k_ = dd.get('opk') or {}
            if p == 'WHEAT':
                v += dd.get('bought', {}).get('BUY_PRODUCT:WHEAT', 0) - sum(x for k, x in k_.items() if k.startswith('FEED:'))
            elif p == 'FERTILIZER':
                v = (sum(x for k, x in k_.items() if k.startswith('COLLECT_FERTILIZER:'))
                     + dd.get('bought', {}).get('BUY_PRODUCT:FERTILIZER', 0) - sum(x for k, x in k_.items() if k.startswith('FERTILIZE:')))
            out.append(v)
        return out
    c2 = {}
    for p in PRODUCTS:
        qL, rvL = daily(L, p)
        qO, rvO = daily(O, p)
        QL_, QO_ = sum(qL), sum(qO)
        base = dict(QL=QL_, QO=QO_, day29=(qL[29], qO[29]),
                    lotL=QL_ / max(1, sum(1 for x in qL if x)), lotO=QO_ / max(1, sum(1 for x in qO if x)))
        if QO_ == 0 or QL_ == 0:
            c2[p] = dict(base, timing=0.0, volume=C2[p], timing_alt=0.0, volume_alt=C2[p], supply_t=0.0, holding=0.0,
                         supply_t_alt=0.0, holding_alt=0.0, behind=None, cum_gap_w=None, held_back=None, ahead_sold=None,
                         dumpL=None, dumpO=None, mdL=None, mdO=None, lotL=None, lotO=None)
            continue
        pLd = [rvL[d] / qL[d] if qL[d] else None for d in range(30)]
        pOd = [rvO[d] / qO[d] if qO[d] else None for d in range(30)]
        pLi, pOi = interp(pLd), interp(pOd)
        wL = [x / QL_ for x in qL]
        wO = [x / QO_ for x in qO]
        timing = QO_ * sum((wL[d] - wO[d]) * pOi[d] for d in range(30))
        volume = QO_ * sum(wL[d] * (pLi[d] - pOi[d]) for d in range(30) if qL[d])
        timing_alt = QO_ * sum((wL[d] - wO[d]) * pLi[d] for d in range(30))
        volume_alt = QO_ * sum(wO[d] * (pLi[d] - pOi[d]) for d in range(30) if qO[d])
        assert abs(timing + volume - C2[p]) < 1e-6 and abs(timing_alt + volume_alt - C2[p]) < 1e-6, (g['ep'], p)
        sL, sO = supply(L, 'L', p), supply(O, 'O', p)
        wsL = [x / sum(sL) for x in sL]
        wsO = [x / sum(sO) for x in sO]
        supply_t = QO_ * sum((wsL[d] - wsO[d]) * pOi[d] for d in range(30))
        holding = timing - supply_t
        supply_t_alt = QO_ * sum((wsL[d] - wsO[d]) * pLi[d] for d in range(30))
        holding_alt = timing_alt - supply_t_alt
        cl = co = 0
        behind = held_back = ahead_sold = 0
        cum_gap_w = 0.0
        for d in range(30):
            cl += qL[d]
            co += qO[d]
            behind += max(0, cl - co)
            cum_gap_w += wO[d] * (cl - co)
            if d < 29:
                held_back += min(max(0, cl - co), (O['days'][d]['shed_after'] or {}).get(p, 0))
            ahead_sold += max(0, min(qO[d], co - cl))
        pb = BASE[p]
        dumpL = sum(qL[d] for d in range(30) if qL[d] and pLd[d] < 0.1 * pb)
        dumpO = sum(qO[d] for d in range(30) if qO[d] and pOd[d] < 0.1 * pb)
        mdL = sum(d * x for d, x in enumerate(qL)) / QL_
        mdO = sum(d * x for d, x in enumerate(qO)) / QO_
        c2[p] = dict(base, timing=timing, volume=volume, timing_alt=timing_alt, volume_alt=volume_alt, supply_t=supply_t,
                     holding=holding, supply_t_alt=supply_t_alt, holding_alt=holding_alt, behind=behind, cum_gap_w=cum_gap_w, held_back=held_back, ahead_sold=ahead_sold,
                     dumpL=dumpL, dumpO=dumpO, mdL=mdL, mdO=mdO)
    r['c2'] = c2
    # ---- three reasons
    cs = lambda i: sum(crop[c]['terms'][i] for c in CROPS)
    cw = lambda i: sum(crop[c]['window'][i] for c in CROPS)
    an_ = lambda i: sum(anim[sp]['terms'][i] for sp in ANIMALS)
    lines = dict(
        P_plant_window=cw(0), P_plant_cutoff=cw(1), P_crop_deaths=cs(2), P_crop_decay=cs(3), P_crop_yield=cs(4),
        P_animals=an_(0), P_animal_dates=an_(1), P_escapes=an_(2), P_animal_yield=an_(3),
        P_fert_animaldays=fert_terms['ad'], P_fert_collect=fert_terms['rate'], P_fert_applied=fert_terms['applied'],
        P_seed_animal_land=spend_cat.get('seeds', 0) + spend_cat.get('animals', 0) + r['land'],
        P_wheat_fert_purchase=(spend_cat.get('buy_wheat', 0) + spend_cat.get('buy_fertilizer', 0)
                               + c1['WHEAT']['comp']['bought'] + fert_terms['bought']),
        P_wheat_fed=c1['WHEAT']['comp']['fed'],
        P_discards=sum(c1[p]['comp']['disc'] for p in c1) + fert_terms['disc'],
        P_later_supply=sum(c2[p]['supply_t'] for p in PRODUCTS),
        P_market_depth=sum(c2[p]['volume'] for p in PRODUCTS),
        L_wages=r['wages'],
        S_holding=sum(c2[p]['holding'] for p in PRODUCTS),
        S_held_end=sum(c1[p]['comp']['held'] for p in c1) + fert_terms['held'],
    )
    other = set(spend_cat) - {'seeds', 'animals', 'buy_wheat', 'buy_fertilizer'}
    assert not other, other
    lines['resid'] = r['gap'] - sum(lines.values())
    assert abs(lines['resid']) < 1e-6, (g['ep'], lines['resid'])
    lines['PRODUCTION'] = sum(v for k, v in lines.items() if k.startswith('P_'))
    lines['LABOUR_COST'] = lines['L_wages']
    lines['SALE_TIMING'] = lines['S_holding'] + lines['S_held_end']
    lines['P_gross_A'] = r['A']
    lines['PRODUCTION_alt'] = (lines['PRODUCTION'] - lines['P_market_depth'] - lines['P_later_supply']
                               + sum(c2[p]['volume_alt'] for p in PRODUCTS) + sum(c2[p]['supply_t_alt'] for p in PRODUCTS))
    lines['SALE_TIMING_alt'] = sum(c2[p]['holding_alt'] for p in PRODUCTS) + lines['S_held_end']
    assert abs(lines['PRODUCTION_alt'] + lines['LABOUR_COST'] + lines['SALE_TIMING_alt'] - r['gap']) < 1e-6
    lines['P_plantings'] = cs(0)
    lines['P_plant_dates'] = cs(1)
    lines['C2_timing'] = sum(c2[p]['timing'] for p in PRODUCTS)
    lines['crop_care'] = lines['P_crop_deaths'] + lines['P_crop_decay'] + lines['P_crop_yield']
    lines['crop_care_net_fert'] = lines['crop_care'] + lines['P_fert_applied']
    lines['animal_care'] = lines['P_escapes'] + lines['P_animal_yield'] + lines['P_fert_collect']
    r['lines'] = lines
    return r


# ---------------------------------------------------------------- reporting
def ci(xs):
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, m, m
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    return m, m - h, m + h


def fmt(xs, w=8):
    m, lo, hi = ci(xs)
    return f"{m:+{w},.0f} ({lo:+,.0f}..{hi:+,.0f})"


def main():
    games, n_fields = load()
    rows = [analyse(g) for g in games]
    sets = [('all 12', rows), ('four-quadrant 8', [r for r in rows if r['four']])]
    o = []
    P = o.append
    P('T gap deep decomposition, 2026-09-25 (results/fresh/t_gap_20260925/deep_decomp.py; stored data only)')
    P('Leader = the leader\'s own recorded game replayed; ours = T (agents/mgt_lead.py defaults), same seed, forced shops,')
    P('recorded opponent. Positive = leader ahead (widens the gap). Means per game with 95% t-intervals.')
    P(f'Data check: results/fresh/lead_ledger/* equals E1\'s ledg1 ledger on all {n_fields:,} shared day-fields and finals;')
    P('it adds board_list / plants / overflow / shed_after. Shed stock identity closes exactly on days 0-28 for all 24 runs.')
    P('Four-quadrant games: ' + ', '.join(r['ep'] for r in rows if r['four']))
    unm = sum(v for r in rows for v in r['death_unmatched'].values())
    eunm = sum(v for r in rows for v in r['escape_unmatched'].values())
    P(f'Per-tile reconstruction: unmatched crop deaths {unm}, unmatched animal escapes {eunm} (both must be 0).')
    P('')
    P('== 0. Lead\'s top level reproduced')
    for lab, sel in sets:
        P(f'  {lab}: gap {fmt([r["gap"] for r in sel])} | A {fmt([r["A"] for r in sel])} | inputs {fmt([r["inputs"] for r in sel])}'
          f' | B wages {fmt([r["wages"] for r in sel])} | land {fmt([r["land"] for r in sel])} | C1 {fmt([r["C1"] for r in sel])}'
          f' | C2 {fmt([r["C2"] for r in sel])} | resid {max(abs(r["resid_top"]) for r in sel):.1e}')
    P('')
    names = [
        ('PRODUCTION', '1. LESS PRODUCTION (subtotal)'),
        ('P_plant_window', "   crops: fewer / later plantings inside T's planting window (missed plantings)"),
        ('P_plant_cutoff', "   crops: leader plantings after T's plant_cutoff (skipped by design)"),
        ('P_crop_deaths', '   crops: plants dying before their harvest  [labour: missed water]'),
        ('P_crop_decay', '   crops: ripe one-time crops left to decay  [labour: missed harvest]'),
        ('P_crop_yield', '   crops: fewer units per harvested planting  [labour: fertilize, tomato harvests]'),
        ('P_fert_applied', '   crops: fertilizer the leader spreads instead of selling (pays for part of the line above)'),
        ('P_animals', '   animals: fewer animals placed'),
        ('P_animal_dates', '   animals: later placement (fewer production days)'),
        ('P_escapes', '   animals: escapes (the leader lets more go; in our favour)'),
        ('P_animal_yield', '   animals: output per production day (we care / feed more; in our favour)'),
        ('P_fert_animaldays', '   fertilizer: fewer animal-days to collect from'),
        ('P_fert_collect', '   fertilizer: lower collection rate per animal-day  [labour]'),
        ('P_seed_animal_land', '   inputs: seeds / animals the leader paid more for'),
        ('P_wheat_fert_purchase', '   inputs: extra wheat / fertilizer bought (resale value at leader price - cost)'),
        ('P_wheat_fed', '   inputs: wheat fed to animals (leader feeds more)'),
        ('P_discards', '   output lost at the midnight shed cap (units carry > 100 items at day end) [labour/logistics]'),
        ('P_later_supply', '   our units become available on later (cheaper) days'),
        ('P_market_depth', '   market depth: our fewer units sell at higher prices (same-day price gap)'),
        ('LABOUR_COST', '2. MORE LABOUR COST (our wages - leader wages)'),
        ('SALE_TIMING', '3. BAD SALE TIMING (subtotal)'),
        ('S_holding', '   holding pattern: days between a unit becoming available and its sale'),
        ('S_held_end', '   stock still unsold at the end'),
        ('resid', 'residual'),
    ]
    memos = [
        ('P_gross_A', "memo: A, production at the leader's average price (before market depth)"),
        ('P_plantings', 'memo: crops fewer plantings x leader units per planting (task definition)'),
        ('P_plant_dates', 'memo: crops later planting dates (potential per planting)'),
        ('C2_timing', 'memo: C2 timing = later supply + holding pattern'),
        ('crop_care', 'memo: crop care shortfall (deaths + decay + units per harvested planting)'),
        ('crop_care_net_fert', 'memo: crop care shortfall net of the fertilizer the leader did not sell'),
        ('animal_care', 'memo: animal care (escapes + output per production day + collection)'),
        ('PRODUCTION_alt', "memo: 1. LESS PRODUCTION if C2 timing is valued at the leader's daily prices"),
        ('SALE_TIMING_alt', "memo: 3. BAD SALE TIMING if C2 timing is valued at the leader's daily prices"),
    ]
    P('== THREE REASONS (all numbered lines add to the gap exactly; positive = leader ahead)')
    hdr = f"  {'':92s} {'all 12':>30s}   {'four-quadrant 8':>30s}"
    P(hdr)
    P(f"  {'CASH GAP':92s} {fmt([r['gap'] for r in rows]):>30s}   {fmt([r['gap'] for r in rows if r['four']]):>30s}")
    for k, nm in names + memos:
        P(f"  {nm:92s} {fmt([r['lines'][k] for r in rows]):>30s}   {fmt([r['lines'][k] for r in rows if r['four']]):>30s}")
    P('')
    P('== Per game (positive = leader ahead)')
    cols = [('gap', 'gap'), ('PRODUCTION', 'PROD'), ('P_gross_A', 'A'), ('P_plant_window', 'window'), ('P_plant_cutoff', 'cutoff'),
            ('crop_care', 'cropcare'), ('P_fert_applied', 'fertapp'), ('anim_n', 'animals'), ('animal_care', 'anicare'),
            ('P_fert_animaldays', 'fertAD'), ('inp', 'inputs'), ('P_later_supply', 'latersup'),
            ('P_market_depth', 'depth'), ('LABOUR_COST', 'WAGES'), ('SALE_TIMING', 'TIMING'), ('S_holding', 'holding'),
            ('S_held_end', 'held'), ('P_discards', 'discard')]
    P('  ' + f"{'episode':10s}{'4Q':>3s}" + ''.join(f'{h:>9s}' for _, h in cols))
    for r in rows:
        ln = dict(r['lines'], gap=r['gap'])
        ln['anim_n'] = ln['P_animals'] + ln['P_animal_dates']
        ln['inp'] = ln['P_seed_animal_land'] + ln['P_wheat_fert_purchase'] + ln['P_wheat_fed']
        P('  ' + f"{r['ep']:10s}{('y' if r['four'] else 'n'):>3s}" + ''.join(f'{ln[k]:+9,.0f}' for k, _ in cols))
    P('  (A = gross production at leader price, a memo: PROD = window + cutoff + cropcare + fertapp + animals + anicare')
    P('   + fertAD + inputs + discard + latersup + depth; cropcare = deaths + decay + units per harvested planting; animals = fewer +')
    P('   later placed; anicare = escapes + output per production day + fertilizer collection; inputs = seeds/animals +')
    P('   wheat/fertilizer purchase + wheat fed)')
    P('')
    # ---- part 1 details
    P('== 1. Production shortfall A by product: shift-share terms (x leader price), means with 95% t-intervals')
    for lab, sel in sets:
        P(f'  -- {lab}')
        P(f"    {'crop':11s} {'A total':>26s} {'fewer plantings':>26s} {'later dates':>26s} {'deaths':>26s} {'decay':>26s} {'units/harvested':>26s} | {'plantings+dates: window':>26s} {'after cutoff':>26s}")
        for c in CROPS:
            P(f"    {c:11s} {fmt([r['A_p'][c] for r in sel]):>26s} " + ' '.join(f"{fmt([r['crop'][c]['terms'][i] for r in sel]):>26s}" for i in range(5))
              + ' | ' + ' '.join(f"{fmt([r['crop'][c]['window'][i] for r in sel]):>26s}" for i in range(2)))
        P(f"    {'animal':11s} {'A total':>26s} {'fewer animals':>26s} {'later placement':>26s} {'escapes':>26s} {'output/prod day':>26s} | {'fewer animal-days':>26s} {'output/animal-day':>26s}")
        for sp, (prod, _, _) in ANIMALS.items():
            P(f"    {prod:11s} {fmt([r['A_p'][prod] for r in sel]):>26s} " + ' '.join(f"{fmt([r['anim'][sp]['terms'][i] for r in sel]):>26s}" for i in range(4))
              + ' | ' + ' '.join(f"{fmt([r['anim'][sp]['ad_terms'][i] for r in sel]):>26s}" for i in range(2)))
        fk = [('ad', 'fewer animal-days'), ('rate', 'collection rate'), ('applied', 'applied to crops'), ('bought', 'bought'),
              ('held', 'held at end'), ('disc', 'discarded')]
        P(f"    {'FERTILIZER':11s} {fmt([r['A_p']['FERTILIZER'] for r in sel]):>26s} = " + '; '.join(f"{nm} {fmt([r['fert']['terms'][k] for r in sel], 6)}" for k, nm in fk))
    P('')
    P('  Physical drivers per game (means, leader / ours; all 12 | four-quadrant 8)')

    def mean_of(sel, f):
        vals = [f(r) for r in sel]
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else float('nan')
    for c in CROPS:
        parts = []
        for lab, sel in sets:
            g_ = lambda s, k: mean_of(sel, lambda r: r['crop'][c]['agg'][s][k])
            rt = lambda s, a, b: mean_of(sel, lambda r: (r['crop'][c]['agg'][s][a] / r['crop'][c]['agg'][s][b]) if r['crop'][c]['agg'][s][b] else None)
            parts.append(f"plantings {g_('L','n'):.1f}/{g_('O','n'):.1f} (after T's cutoff day {CUTOFF[c]}: {g_('L','n_post'):.1f}/{g_('O','n_post'):.1f}), mean day {g_('L','mean_day'):.1f}/{g_('O','mean_day'):.1f}, "
                         f"pot/planting {rt('L','pot','n'):.2f}/{rt('O','pot','n'):.2f}, deaths {g_('L','died'):.1f}/{g_('O','died'):.1f} "
                         f"(premature {g_('L','died_prem'):.1f}/{g_('O','died_prem'):.1f}, lost units {g_('L','lost'):.1f}/{g_('O','lost'):.1f}), "
                         f"decayed {g_('L','decayed'):.1f}/{g_('O','decayed'):.1f}, harvested {g_('L','h'):.0f}/{g_('O','h'):.0f}, "
                         f"units per harvestable pot {mean_of(sel, lambda r: r['crop'][c]['agg']['L']['h'] / max(1e-9, r['crop'][c]['agg']['L']['pot'] - r['crop'][c]['agg']['L']['lost'] - r['crop'][c]['agg']['L']['decay']) if r['crop'][c]['agg']['L']['n'] else None):.2f}/"
                         f"{mean_of(sel, lambda r: r['crop'][c]['agg']['O']['h'] / max(1e-9, r['crop'][c]['agg']['O']['pot'] - r['crop'][c]['agg']['O']['lost'] - r['crop'][c]['agg']['O']['decay']) if r['crop'][c]['agg']['O']['n'] else None):.2f}; "
                         f"ops: water per tile-day {rt('L','water','td'):.2f}/{rt('O','water','td'):.2f}, fertilize per planting {rt('L','fert','n'):.2f}/{rt('O','fert','n'):.2f}, "
                         f"harvest ops per planting {rt('L','harv_ops','n'):.2f}/{rt('O','harv_ops','n'):.2f}, dug live {g_('L','dig'):.1f}/{g_('O','dig'):.1f}")
        P(f'    {c}:')
        P(f'      all 12: {parts[0]}')
        P(f'      4Q 8  : {parts[1]}')
    for sp, (prod, _, _) in ANIMALS.items():
        parts = []
        for lab, sel in sets:
            g_ = lambda s, k: mean_of(sel, lambda r: r['anim'][sp]['agg'][s][k])
            rt = lambda s, a, b: mean_of(sel, lambda r: (r['anim'][sp]['agg'][s][a] / r['anim'][sp]['agg'][s][b]) if r['anim'][sp]['agg'][s][b] else None)
            parts.append(f"animals placed {g_('L','N'):.1f}/{g_('O','N'):.1f}, mean placement day {g_('L','mean_p'):.1f}/{g_('O','mean_p'):.1f}, "
                         f"animal-days {g_('L','ad'):.0f}/{g_('O','ad'):.0f}, base production days {g_('L','pot'):.0f}/{g_('O','pot'):.0f}, "
                         f"escapes {g_('L','esc'):.2f}/{g_('O','esc'):.2f}, {prod} {g_('L','h'):.0f}/{g_('O','h'):.0f}, "
                         f"output per animal-day {rt('L','h','ad'):.3f}/{rt('O','h','ad'):.3f}, per base production {rt('L','h','act'):.2f}/{rt('O','h','act'):.2f}; "
                         f"ops per animal-day: feed {rt('L','feed','ad'):.2f}/{rt('O','feed','ad'):.2f}, care {rt('L','care','ad'):.2f}/{rt('O','care','ad'):.2f}, "
                         f"harvest {rt('L','harv_ops','ad'):.2f}/{rt('O','harv_ops','ad'):.2f}, collect {rt('L','coll','ad'):.2f}/{rt('O','coll','ad'):.2f}")
        P(f'    {sp} ({prod}):')
        P(f'      all 12: {parts[0]}')
        P(f'      4Q 8  : {parts[1]}')
    for lab, sel in sets:
        f_ = lambda s, k: mean_of(sel, lambda r: r['fert']['side'][s][k])
        P(f"    FERTILIZER {lab}: collected {f_('L','coll'):.0f}/{f_('O','coll'):.0f} over animal-days {f_('L','ad'):.0f}/{f_('O','ad'):.0f} "
          f"(rate {f_('L','rate'):.3f}/{f_('O','rate'):.3f}), applied to crops {f_('L','used'):.0f}/{f_('O','used'):.0f}, bought {f_('L','bought'):.0f}/{f_('O','bought'):.0f}, "
          f"held at end {f_('L','held'):.1f}/{f_('O','held'):.1f}, discarded {f_('L','disc'):.1f}/{f_('O','disc'):.1f}")
    P('')
    # ---- part 2
    P('== 2. Price per unit sold (C2) by product: sale timing vs volume (market depth)')
    P("  timing = our units moved onto the leader's sale-day mix, valued at our own daily price (task definition);")
    P("  volume = leader-world minus our-world price on the leader's sale days (our lower cumulative sales and smaller lots);")
    P('  timing = later supply (net units becoming available later: harvest; wheat + bought - fed; fertilizer collected +')
    P('  bought - applied) + holding (the rest: how long units wait between availability and sale). alt: timing at leader prices.')
    for lab, sel in sets:
        P(f'  -- {lab}')
        P(f"    {'product':11s} {'C2':>24s} {'volume/depth':>24s} {'timing':>24s} {'= later supply':>24s} {'+ holding':>24s} {'timing (alt)':>24s} {'= later supply (alt)':>24s} {'+ holding (alt)':>24s}")
        for p in PRODUCTS:
            P(f"    {p:11s} {fmt([r['C2_p'][p] for r in sel], 7):>24s} {fmt([r['c2'][p]['volume'] for r in sel], 7):>24s} "
              f"{fmt([r['c2'][p]['timing'] for r in sel], 7):>24s} {fmt([r['c2'][p]['supply_t'] for r in sel], 7):>24s} "
              f"{fmt([r['c2'][p]['holding'] for r in sel], 7):>24s} {fmt([r['c2'][p]['timing_alt'] for r in sel], 7):>24s} "
              f"{fmt([r['c2'][p]['supply_t_alt'] for r in sel], 7):>24s} {fmt([r['c2'][p]['holding_alt'] for r in sel], 7):>24s}")
        P(f"    {'TOTAL':11s} {fmt([r['C2'] for r in sel], 7):>24s} {fmt([sum(r['c2'][p]['volume'] for p in PRODUCTS) for r in sel], 7):>24s} "
          f"{fmt([sum(r['c2'][p]['timing'] for p in PRODUCTS) for r in sel], 7):>24s} {fmt([sum(r['c2'][p]['supply_t'] for p in PRODUCTS) for r in sel], 7):>24s} "
          f"{fmt([sum(r['c2'][p]['holding'] for p in PRODUCTS) for r in sel], 7):>24s} {fmt([sum(r['c2'][p]['timing_alt'] for p in PRODUCTS) for r in sel], 7):>24s} "
          f"{fmt([sum(r['c2'][p]['supply_t_alt'] for p in PRODUCTS) for r in sel], 7):>24s} {fmt([sum(r['c2'][p]['holding_alt'] for p in PRODUCTS) for r in sel], 7):>24s}")
        P(f"    {'product':11s} units sold L/O | mean sale day L/O | avg price L/O | units per selling day L/O | cum units leader ahead (our sale days) | "
          f"unit-days behind schedule | of which with our stock in the shed | our units sold ahead of the leader's cum | units sold at <10% of base L/O | day-29 units L/O")
        for p in PRODUCTS:
            q = lambda k: mean_of(sel, lambda r: r['c2'][p].get(k))
            P(f"    {p:11s} {q('QL'):.0f}/{q('QO'):.0f} | {q('mdL'):.1f}/{q('mdO'):.1f} | {mean_of(sel, lambda r: r['PL'][p]):.1f}/{mean_of(sel, lambda r: r['PO'][p]):.1f} | "
              f"{q('lotL'):.1f}/{q('lotO'):.1f} | {q('cum_gap_w'):.1f} | {q('behind'):.0f} | {q('held_back'):.0f} | {q('ahead_sold'):.1f} | "
              f"{q('dumpL'):.1f}/{q('dumpO'):.1f} | {mean_of(sel, lambda r: r['c2'][p]['day29'][0]):.1f}/{mean_of(sel, lambda r: r['c2'][p]['day29'][1]):.1f}")
    P('')
    P('== Per product: revenue gap (leader minus ours) = A + C1 + C2; C2 = depth + later supply + holding')
    for lab, sel in sets:
        P(f'  -- {lab}')
        P(f"    {'product':11s} {'revenue gap':>24s} {'A production':>24s} {'C1 unsold':>24s} {'C2 depth':>24s} {'C2 later supply':>24s} {'C2 holding':>24s}")
        for p in PRODUCTS:
            P(f"    {p:11s} {fmt([r['A_p'][p] + r['C1_p'][p] + r['C2_p'][p] for r in sel], 7):>24s} {fmt([r['A_p'][p] for r in sel], 7):>24s} "
              f"{fmt([r['C1_p'][p] for r in sel], 7):>24s} {fmt([r['c2'][p]['volume'] for r in sel], 7):>24s} "
              f"{fmt([r['c2'][p]['supply_t'] for r in sel], 7):>24s} {fmt([r['c2'][p]['holding'] for r in sel], 7):>24s}")
    P('')
    # ---- part 3
    P('== 3. Produced but not sold (C1) by component (x leader price)')
    for lab, sel in sets:
        P(f'  -- {lab}')
        for p in c1_products(rows):
            comp = ' '.join(f"{k} {fmt([r['c1'][p]['comp'][k] for r in sel], 6)}" for k in ('fed', 'held', 'disc', 'bought'))
            P(f"    {p:11s} C1 {fmt([r['C1_p'][p] for r in sel], 6)} = {comp}")
        w = lambda k, s: mean_of(sel, lambda r: r['c1']['WHEAT'][k][s])
        P(f"    WHEAT units (leader/ours): fed {w('fed','L'):.0f}/{w('fed','O'):.0f}, held at end {w('held','L'):.1f}/{w('held','O'):.1f}, "
          f"discarded {w('disc','L'):.1f}/{w('disc','O'):.1f}, bought {w('bought','L'):.0f}/{w('bought','O'):.0f}; "
          f"wheat purchase spend, leader minus ours {mean_of(sel, lambda r: -r['spend_cat'].get('buy_wheat', 0)):+,.0f}; "
          f"C1-bought + spend = net wheat-purchase margin {fmt([r['c1']['WHEAT']['comp']['bought'] + r['spend_cat'].get('buy_wheat', 0) for r in sel], 5)}")
        tot_units = lambda k, s: mean_of(sel, lambda r: sum(r['c1'][p][k][s] for p in r['c1']))
        P(f"    all products units held at end {tot_units('held','L'):.1f}/{tot_units('held','O'):.1f}, discarded {tot_units('disc','L'):.1f}/{tot_units('disc','O'):.1f}")
    P('== Notes')
    for line in NOTES.strip('\n').split('\n'):
        P(line)
    txt = '\n'.join(o) + '\n'
    (OUT / 'deep.txt').write_text(txt, encoding='utf-8')
    slim = []
    for r in rows:
        slim.append({k: v for k, v in r.items()})
    (OUT / 'deep_per_game.json').write_text(json.dumps(slim, default=str, indent=1), encoding='utf-8')
    print(txt)


NOTES = """
- Mapping: every numbered line belongs to exactly one of the three reasons and they add to the gap with residual 0 in
  every game. Shift-share order for crops: plantings -> potential per planting (planting day) -> death share -> decay
  share -> units per harvestable potential; animals: animals -> potential per animal (placement day) -> escape share ->
  output per base production. Potentials follow the engine (full water, no fertilizer, harvest by day 29).
- Less production is first valued at the leader's own average price (A = +22.3k) and then corrected by market depth
  (-15.2k): the leader's extra units push its own prices down, so they are worth far less than its average price
  (112661570 wool: the leader's daily price falls to about 50 from day 21 while ours stays about 235; 112444381 milk:
  the leader's late price is 40-100 against our 200+).
- Labour cost is about 0 by construction: T hires the leader's hand count each day. Missed work shows up as less
  production instead; those lines are tagged [labour] (deaths = missed water, decay = missed harvest, units per
  harvested planting = fewer fertilizes and tomato harvests, fertilizer collection rate).
- C2 timing (+7.4k) is mostly later supply (+5.9k), i.e. production: our units exist later (sheep and geese placed
  about 1 and 3 days later, melons harvested later, extra late milk and wool). The part the sell decision owns is the
  holding pattern, +1.4k at our daily prices and +0.3k (CI crosses 0) at the leader's, plus +0.2k unsold at the end.
- T sells on the leader's cumulative schedule capped by its stock. Being behind the schedule is mostly stock-limited
  (strawberry 402 unit-days behind, 96 with stock in the shed); wheat (feed reserve) and fertilizer (fertilize reserve)
  are held back on purpose.
- T sells ahead of the leader's schedule for milk (65.6 units a game), wool (28.7) and fertilizer (35.8), and sells
  21.3 milk and 19.7 wool a game on days when its average price is under 10% of base (leader 4.8 and 8.7). These units
  come from animals T keeps feeding while the leader retires them late in the season (leader escapes 8.9 a game, mean
  day 25.1; T 4.7, day 26.7). They show up as 'escapes' and 'output per production day' in our favour at the leader's
  price, and are taken back by later supply and market depth. The ledger does not show which T rule sold them (day-29
  dump, hire funding, or the evening shed-overflow sell).
- Crop deaths are unwatered end-of-day deaths only (the ledger's died counter). Mid-day decays are separated per tile;
  an ongoing crop that dies after its last production is a retirement and costs 0.
- Shed cap: T loses 31.6 units a game at midnight against the leader's 8.7 (wheat 16.1 vs 3.2). Counted as lost output
  (production), because the stock that overflows is carried by the units, not unsold stock in the shed.
- Fertilizer: the leader spreads 207 against 127 on crops. Not selling it costs the leader 4.3k, which pays for most of
  its +5.4k crop-yield edge (net crop care +4.0k).
- The four-quadrant subset (n=8) tells the same story, with slightly larger production terms.
"""


def c1_products(rows):
    return [p for p in PRODUCTS if p != 'FERTILIZER' and any(abs(r['C1_p'][p]) > 0.5 for r in rows)]


if __name__ == '__main__':
    main()
