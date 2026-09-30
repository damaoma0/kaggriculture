"""How much does price awareness move DSM's production plan? (2026-09-24)

Input: results/fresh/newphase_20260923/price_awareness/replay_extract/*.json.gz (scripts/extract_dsm_price_panel.py;
engine-exact per-step prices, cash, order fills, plantings for both players of DSM's 108 recorded episodes = 109 DSM
farm-games). Output: results.json and summary.md in the same directory. No games are simulated.

1. Level: DSM's day-d counts (8 items, d = 9..24) from the shops DSM could see (ridge, leave-one-episode-out, alpha by
   inner LOO). Incremental out-of-sample R^2 of adding, measured at day d-3 (before the window's decisions):
   PRICE_OWN (the item's own product price), PRICE_ALL (8 product prices), PRICE_OPP (the part of the 8 prices caused
   by the opponent's cumulative net sales: price(inv) - price(inv - opp_net), exogenous to DSM given shops), CASH (DSM
   money, log money), OPP (opponent count of the item, opponent cash, opponent animals, opponent crop tiles), ALL.
   Flow variant: base = shops + DSM's own day-(d-3) board, i.e. what moves the plan over the window.
   CI: bootstrap over episodes of (SSE_base - SSE_full)/SST with the LOO predictions fixed (2000 draws).
   Pre-specified channels also get a permutation p-value (block rows permuted, full LOO refit, 200 draws).
2. Timing: land purchases, first expansion animal buys, first plantings; residual SD after shops; incremental R^2 of
   cash / prices; cash gating (failed requests before the fill, slack at the fill).
3. Cash terms: a board value index V_d = sum_i v_i * count_i(d) (v_i = DSM's revenue per item-day) decomposed into
   shop-driven, price/cash/opponent-driven (incremental prediction) and unexplained parts.
4. Budget-exactness / feasibility facts from DSM's own games: day-start cash, requested vs filled orders, day-1
   hands vs the day-0 wheat price, day-6 board identity and day-6 hidden stock.
"""
import gzip, json, math, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from extract_dsm_price_panel import load_engine  # noqa: E402

OUTDIR = ROOT / 'results/fresh/newphase_20260923/price_awareness'
EX = OUTDIR / 'replay_extract'
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
PI = {p: i for i, p in enumerate(PRODUCTS)}
SELLABLE = PRODUCTS[:8]
ITEMS = ['SHEEP', 'COW', 'GOOSE', 'STRAWBERRY', 'TOMATO', 'WHEAT', 'CARROT', 'MELON']
ANIMALS = ['SHEEP', 'COW', 'GOOSE']
CROPS = ['STRAWBERRY', 'TOMATO', 'WHEAT', 'CARROT', 'MELON']
PROD_OF = dict(SHEEP='WOOL', COW='MILK', GOOSE='EGG', STRAWBERRY='STRAWBERRY', TOMATO='TOMATO', WHEAT='WHEAT',
               CARROT='CARROT', MELON='MELON')
SHOPS = ['BAKERY', 'PIZZA_SHOP', 'BRUNCH_SPOT', 'YARN_STORE', 'ICE_CREAM_SHOP', 'PET_CAFE', 'SMOOTHIE_SHOP', 'FARMERS_MARKET']
DAYS = [9, 12, 15, 18, 21, 24]
ALPHAS = (0.3, 1, 3, 10, 30, 100, 300)
K = load_engine()
RNG = np.random.default_rng(20260924)


# ----------------------------------------------------------------------------------------------------------- data
def reveal(shops_by_day):
    seq, seen = [], 0
    for cur in shops_by_day:
        while len(cur) > seen:
            seq.append(cur[seen]); seen += 1
    return seq


def shop_feats(seq, k):
    s = seq[:max(0, min(8, k))]
    return [s.count(x) for x in SHOPS] + [s[-2:].count(x) for x in SHOPS]


def net_units(orders, product, t_end):
    """Cumulative net units a player put into the market for `product` over steps < t_end (sells at price > 1 add,
    BUY_PRODUCT removes). A SELL whose coins == units filled was entirely at the $1 floor and adds nothing."""
    n = 0
    for t, op, item, req, ok, coins in orders:
        if t >= t_end or item != product or not ok:
            continue
        if op == 'SELL' and coins > ok:
            n += ok
        elif op == 'BUY_PRODUCT':
            n -= ok
    return n


def load_games():
    games = []
    for f in sorted(EX.glob('*.json.gz')):
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            r = json.load(fh)
        if r.get('n_steps', 0) < 720 or 'orders' not in r:
            continue
        seq = reveal(r['shops_day'])
        for s in r['dsm_seats']:
            o = 1 - s
            g = dict(ep=r['episode'], seat=s, opp_name=r['names'][o], self_play=len(r['dsm_seats']) == 2, seq=seq,
                     counts=[ds['counts'] for ds in r['day_state'][s]], opp_counts=[ds['counts'] for ds in r['day_state'][o]],
                     quad=[ds['quadrants'] for ds in r['day_state'][s]], seeds=[ds['seeds'] for ds in r['day_state'][s]],
                     shed=[ds['shed'] for ds in r['day_state'][s]], money=r['money'][s], opp_money=r['money'][o],
                     prices=r['prices'], inv_day=r['inventory_day'], orders=r['orders'][s], opp_orders=r['orders'][o],
                     plant=r['plant'][s], place=r['place'][s], hands=r['hands'][s], dropped=r['dropped'][s],
                     final=r['final_money'][s], opp_final=r['final_money'][o], check=r['check'])
            games.append(g)
        del r
    return games


def cnt(c, item):
    return c.get(item, 0)


def price_components(g, d):
    """Recorded price at day-d start, and the parts caused by the opponent's / DSM's cumulative net sales."""
    t = 24 * d
    rec, opp, own = [], [], []
    for p in SELLABLE:
        inv = g['inv_day'][d][PI[p]]
        pr = g['prices'][t][PI[p]]
        assert pr == K.market_price(p, inv), (p, pr, inv)
        rec.append(pr)
        opp.append(pr - K.market_price(p, inv - net_units(g['opp_orders'], p, t)))
        own.append(pr - K.market_price(p, inv - net_units(g['orders'], p, t)))
    return rec, opp, own


def window_sum(events, lo, hi, key=None):
    return sum(n for t, item, n in events if lo <= t < hi and (key is None or item == key))


def filled(orders, op, item, lo, hi):
    return sum(ok for t, o, it, req, ok, c in orders if o == op and (item is None or it == item) and lo <= t < hi)


# ----------------------------------------------------------------------------------------------------------- stats
def ridge_logo(X, y, groups, alphas=ALPHAS):
    """Leave-one-group-out ridge predictions; features standardised on the training fold; alpha by closed-form
    inner LOO on the training fold; unpenalised intercept."""
    X = np.asarray(X, float); y = np.asarray(y, float)
    n = len(y)
    if X.ndim == 1:
        X = X[:, None]
    preds = np.empty(n)
    for gv in np.unique(groups):
        te = groups == gv; tr = ~te
        Xtr, ytr = X[tr], y[tr]
        ym = ytr.mean(); yc = ytr - ym
        if X.shape[1] == 0:
            preds[te] = ym; continue
        mu = Xtr.mean(0); sd = Xtr.std(0); sd[sd == 0] = 1
        Z = (Xtr - mu) / sd
        U, S, Vt = np.linalg.svd(Z, full_matrices=False)
        Uy = U.T @ yc
        best, bmse = None, None
        ntr = len(ytr)
        for a in alphas:
            dd = S ** 2 / (S ** 2 + a)
            h = (U ** 2) @ dd + 1.0 / ntr
            res = (yc - U @ (dd * Uy)) / np.clip(1 - h, 1e-3, None)
            mse = float(np.mean(res ** 2))
            if bmse is None or mse < bmse:
                best, bmse = a, mse
        beta = Vt.T @ ((S / (S ** 2 + best)) * Uy)
        preds[te] = ((X[te] - mu) / sd) @ beta + ym
    return preds


def r2(y, p):
    y = np.asarray(y, float); sst = np.sum((y - y.mean()) ** 2)
    return float(1 - np.sum((y - p) ** 2) / sst) if sst > 0 else float('nan')


def boot_delta(y, pb, pf, groups, B=2000):
    y = np.asarray(y, float)
    ug = np.unique(groups)
    rows = [np.where(groups == gv)[0] for gv in ug]
    eb = (y - pb) ** 2; ef = (y - pf) ** 2
    out = []
    for _ in range(B):
        pick = np.concatenate([rows[i] for i in RNG.integers(0, len(ug), len(ug))])
        yy = y[pick]; sst = np.sum((yy - yy.mean()) ** 2)
        if sst <= 0:
            continue
        out.append((eb[pick].sum() - ef[pick].sum()) / sst)
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def incremental(y, Xb, Xk, groups, perm=0):
    y = np.asarray(y, float)
    if np.var(y) == 0:
        return None
    pb = ridge_logo(Xb, y, groups)
    Xf = np.hstack([np.asarray(Xb, float), np.asarray(Xk, float).reshape(len(y), -1)])
    pf = ridge_logo(Xf, y, groups)
    rb, rf = r2(y, pb), r2(y, pf)
    lo, hi = boot_delta(y, pb, pf, groups)
    res = dict(r2_base=round(rb, 3), r2_full=round(rf, 3), delta=round(rf - rb, 3), ci=[round(lo, 3), round(hi, 3)],
               resid_share_explained=round((rf - rb) / (1 - rb), 3) if rb < 1 else None, n=int(len(y)),
               sd_y=round(float(np.std(y)), 3), sd_incr_pred=round(float(np.std(pf - pb)), 3))
    if perm:
        Xk = np.asarray(Xk, float).reshape(len(y), -1)
        null = []
        for _ in range(perm):
            Xp = np.hstack([np.asarray(Xb, float), Xk[RNG.permutation(len(y))]])
            null.append(r2(y, ridge_logo(Xp, y, groups)) - rb)
        res['perm_p'] = round(float((1 + sum(v >= rf - rb for v in null)) / (1 + perm)), 3)
        res['perm_null_95'] = round(float(np.percentile(null, 95)), 3)
    res['_pb'], res['_pf'] = pb, pf
    return res


def partial_corr(y, x, Xb, groups, B=2000):
    """Correlation of y and x after removing the shop prediction (LOO) from each; slope of y on x in those residuals."""
    y = np.asarray(y, float); x = np.asarray(x, float)
    ry = y - ridge_logo(Xb, y, groups); rx = x - ridge_logo(Xb, x, groups)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return dict(r=None)
    r = float(np.corrcoef(ry, rx)[0, 1]); slope = float(np.polyfit(rx, ry, 1)[0])
    ug = np.unique(groups); rows = [np.where(groups == gv)[0] for gv in ug]
    bs, bsl = [], []
    for _ in range(B):
        pick = np.concatenate([rows[i] for i in RNG.integers(0, len(ug), len(ug))])
        if np.std(rx[pick]) == 0 or np.std(ry[pick]) == 0:
            continue
        bs.append(np.corrcoef(ry[pick], rx[pick])[0, 1]); bsl.append(np.polyfit(rx[pick], ry[pick], 1)[0])
    return dict(r=round(r, 3), r_ci=[round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)],
                slope=round(slope, 4), slope_ci=[round(float(np.percentile(bsl, 2.5)), 4), round(float(np.percentile(bsl, 97.5)), 4)],
                sd_x_resid=round(float(np.std(rx)), 2), sd_y_resid=round(float(np.std(ry)), 3),
                sd_y=round(float(np.std(y)), 3))


def strip(d):
    if isinstance(d, dict):
        return {k: strip(v) for k, v in d.items() if not str(k).startswith('_')}
    if isinstance(d, list):
        return [strip(v) for v in d]
    return d


# ----------------------------------------------------------------------------------------------------------- main
def main():
    sys.stdout.reconfigure(encoding='utf-8')
    games = load_games()
    n = len(games)
    groups = np.array([g['ep'] for g in games])
    out = dict(n_games=n, n_episodes=int(len(np.unique(groups))),
               extraction_check=dict(money_mismatch=sum(g['check']['money_mismatch'] for g in games),
                                     inventory_mismatch=sum(g['check']['inventory_mismatch'] for g in games)))
    print('games', n, 'episodes', out['n_episodes'], out['extraction_check'])

    # ---------------- per-game features at each window start w = d - 3
    comp = {g_i: {} for g_i in range(n)}
    for i, g in enumerate(games):
        for w in range(0, 28):
            comp[i][w] = price_components(g, w)

    def block(i, w, item, name):
        g = games[i]
        rec, opp, own = comp[i][w]
        if name == 'PRICE_OWN':
            return [rec[PI[PROD_OF[item]]]]
        if name == 'PRICE_OPP_OWN':
            return [opp[PI[PROD_OF[item]]]]
        if name == 'PRICE_ALL':
            return rec
        if name == 'PRICE_OPP':
            return opp
        if name == 'CASH':
            m = g['money'][24 * w]
            return [m, math.log1p(max(m, 0))]
        if name == 'OPP':
            oc = g['opp_counts'][w]
            return [cnt(oc, item), g['opp_money'][24 * w], sum(cnt(oc, a) for a in ANIMALS), sum(cnt(oc, c) for c in CROPS)]
        if name == 'ALL':
            return block(i, w, item, 'PRICE_ALL') + block(i, w, item, 'CASH') + block(i, w, item, 'OPP')
        raise KeyError(name)

    BLOCKS = ['PRICE_OWN', 'PRICE_OPP_OWN', 'PRICE_ALL', 'PRICE_OPP', 'CASH', 'OPP', 'ALL']

    # price variation facts: how much do prices differ between DSM's games, and how much of it is the opponent
    pv = {}
    for d in DAYS:
        pv[d] = {}
        for p in SELLABLE:
            rec = np.array([comp[i][d][0][PI[p]] for i in range(n)]); opp = np.array([comp[i][d][1][PI[p]] for i in range(n)])
            own = np.array([comp[i][d][2][PI[p]] for i in range(n)])
            pv[d][p] = dict(mean=round(float(rec.mean()), 1), sd=round(float(rec.std()), 1),
                            opp_part_mean=round(float(opp.mean()), 1), opp_part_sd=round(float(opp.std()), 1),
                            dsm_part_mean=round(float(own.mean()), 1), dsm_part_sd=round(float(own.std()), 1))
    out['price_variation'] = pv

    # slow sections are cached (delete _section_cache.json or pass --redo to recompute)
    cache_path = OUTDIR / '_section_cache.json'
    cache = {} if '--redo' in sys.argv or not cache_path.exists() else json.loads(cache_path.read_text(encoding='utf-8'))

    # ---------------- 1a. level and flow models
    lvl, flw = {}, {}
    for d in ([] if 'level' in cache else DAYS):
        w = d - 3
        Xs = np.array([shop_feats(g['seq'], (d - 1) // 3) for g in games], float)
        Xlag = np.array([[cnt(g['counts'][w], it) for it in ITEMS] for g in games], float)
        lvl[d], flw[d] = {}, {}
        for item in ITEMS:
            y = np.array([cnt(g['counts'][d], item) for g in games], float)
            if np.var(y) == 0:
                continue
            lvl[d][item], flw[d][item] = {}, {}
            for b in BLOCKS:
                Xk = np.array([block(i, w, item, b) for i in range(n)], float)
                lvl[d][item][b] = incremental(y, Xs, Xk, groups)
                flw[d][item][b] = incremental(y, np.hstack([Xs, Xlag]), Xk, groups)
            print('level/flow', d, item, 'base', lvl[d][item]['ALL']['r2_base'], 'ALL +', lvl[d][item]['ALL']['delta'],
                  lvl[d][item]['ALL']['ci'], '| flow base', flw[d][item]['ALL']['r2_base'], '+', flw[d][item]['ALL']['delta'], flush=True)
    if 'level' in cache:
        out['level'], out['flow'] = cache['level'], cache['flow']
    else:
        out['level'] = json.loads(json.dumps(strip(lvl), default=float)); out['flow'] = json.loads(json.dumps(strip(flw), default=float))
        cache.update(level=out['level'], flow=out['flow'])
        cache_path.write_text(json.dumps(cache, default=float), encoding='utf-8')

    # ---------------- 1b. pre-specified channels (with permutation tests)
    ch = {}
    for d in ([] if 'channels' in cache else DAYS):
        w = d - 3
        Xs = np.array([shop_feats(g['seq'], (d - 1) // 3) for g in games], float)
        Xlag = np.array([[cnt(g['counts'][w], it) for it in ITEMS] for g in games], float)
        base = np.hstack([Xs, Xlag])
        spr = np.array([comp[i][w][0][PI['STRAWBERRY']] for i in range(n)], float)
        sopp = np.array([comp[i][w][1][PI['STRAWBERRY']] for i in range(n)], float)
        wpr = np.array([comp[i][w][0][PI['WOOL']] for i in range(n)], float)
        wopp = np.array([comp[i][w][1][PI['WOOL']] for i in range(n)], float)
        hpr = np.array([comp[i][w][0][PI['WHEAT']] for i in range(n)], float)
        hopp = np.array([comp[i][w][1][PI['WHEAT']] for i in range(n)], float)
        mpr = np.array([comp[i][w][0][PI['MILK']] for i in range(n)], float)
        tpr = np.array([comp[i][w][0][PI['TOMATO']] for i in range(n)], float)
        cpr = np.array([comp[i][w][0][PI['CARROT']] for i in range(n)], float)
        tom_plant = np.array([window_sum(g['plant'], 24 * w, 24 * d, 'TOMATO') for g in games], float)
        car_plant = np.array([window_sum(g['plant'], 24 * w, 24 * d, 'CARROT') for g in games], float)
        cash = np.array([g['money'][24 * w] for g in games], float)
        st_plant = np.array([window_sum(g['plant'], 24 * w, 24 * d, 'STRAWBERRY') for g in games], float)
        sheep_buy = np.array([filled(g['orders'], 'BUY_ANIMAL', 'SHEEP', 24 * w, 24 * d) for g in games], float)
        cow_buy = np.array([filled(g['orders'], 'BUY_ANIMAL', 'COW', 24 * w, 24 * d) for g in games], float)
        anim_buy = np.array([filled(g['orders'], 'BUY_ANIMAL', None, 24 * w, 24 * d) for g in games], float)
        wheat_buy = np.array([filled(g['orders'], 'BUY_PRODUCT', 'WHEAT', 24 * w, 24 * d) for g in games], float)
        wheat_plant = np.array([window_sum(g['plant'], 24 * w, 24 * d, 'WHEAT') for g in games], float)
        sheep_d = np.array([cnt(g['counts'][d], 'SHEEP') for g in games], float)
        land_d = np.array([g['quad'][d] for g in games], float)
        spec = {
            'strawberry_plantings~strawberry_price': (st_plant, spr),
            'strawberry_plantings~strawberry_price_opp_part': (st_plant, sopp),
            'sheep_count~wool_price': (sheep_d, wpr),
            'sheep_bought~wool_price': (sheep_buy, wpr),
            'sheep_bought~wool_price_opp_part': (sheep_buy, wopp),
            'cows_bought~milk_price': (cow_buy, mpr),
            'wheat_bought~wheat_price': (wheat_buy, hpr),
            'wheat_bought~wheat_price_opp_part': (wheat_buy, hopp),
            'wheat_planted~wheat_price': (wheat_plant, hpr),
            'wheat_planted~wheat_price_opp_part': (wheat_plant, hopp),
            'tomato_planted~tomato_price': (tom_plant, tpr),
            'carrot_planted~carrot_price': (car_plant, cpr),
            'animals_bought~cash': (anim_buy, cash),
            'land_quadrants~cash': (land_d, cash),
        }
        ch[d] = {}
        for name, (y, x) in spec.items():
            if np.var(y) == 0:
                ch[d][name] = None; continue
            if np.var(x) == 0:
                ch[d][name] = dict(window=[w, d], mean_y=round(float(y.mean()), 2), note='price component constant across games'); continue
            inc = incremental(y, base, x[:, None], groups, perm=100)
            pc = partial_corr(y, x, base, groups)
            ch[d][name] = dict(window=[w, d], mean_y=round(float(y.mean()), 2), **{k: v for k, v in inc.items() if not str(k).startswith('_')},
                               partial=pc)
            print('channel', d, name, 'delta', inc['delta'], inc['ci'], 'perm_p', inc.get('perm_p'), 'r', pc.get('r'), flush=True)
    if 'channels' in cache:
        out['channels'] = cache['channels']
    else:
        out['channels'] = json.loads(json.dumps(ch, default=float))
        cache['channels'] = out['channels']
        cache_path.write_text(json.dumps(cache, default=float), encoding='utf-8')

    # ---------------- 2. timing vs quantity
    def first_fill(g, op, item, lo=0, hi=720, k=1):
        c = 0
        for t, o, it, req, ok, coins in g['orders']:
            if o == op and (item is None or it == item) and lo <= t < hi and ok:
                c += ok
                if c >= k:
                    return t
        return None

    def first_plant(g, crop, lo=0):
        for t, c, nn in g['plant']:
            if c == crop and t >= lo:
                return t
        return None

    events = {
        'land_2nd': lambda g: first_fill(g, 'BUY_LAND', '', k=1),
        'land_3rd': lambda g: first_fill(g, 'BUY_LAND', '', k=2),
        'land_4th': lambda g: first_fill(g, 'BUY_LAND', '', k=3),
        'first_goose': lambda g: first_fill(g, 'BUY_ANIMAL', 'GOOSE'),
        'first_cow_after_d5': lambda g: first_fill(g, 'BUY_ANIMAL', 'COW', lo=144),
        'first_sheep_after_d5': lambda g: first_fill(g, 'BUY_ANIMAL', 'SHEEP', lo=144),
        'first_tomato_planting': lambda g: first_plant(g, 'TOMATO'),
        'first_carrot_planting': lambda g: first_plant(g, 'CARROT'),
        'first_strawberry_after_d7': lambda g: first_plant(g, 'STRAWBERRY', lo=168),
    }
    tim = {}
    for name, fn in events.items():
        ts = [fn(g) for g in games]
        idx = [i for i, t in enumerate(ts) if t is not None]
        if len(idx) < 20:
            tim[name] = dict(n=len(idx)); continue
        y = np.array([ts[i] for i in idx], float)
        gr = groups[idx]
        med_day = int(np.median(y) // 24)
        # shops visible at the median event day; cash and prices at the start of the day before it
        wd = max(0, med_day - 1)
        Xs = np.array([shop_feats(games[i]['seq'], med_day // 3) for i in idx], float)
        cash = np.array([[games[i]['money'][24 * wd]] for i in idx], float)
        prices = np.array([comp[i][wd][0] for i in idx], float)
        oppp = np.array([comp[i][wd][1] for i in idx], float)
        rec = dict(n=len(idx), of=n, median_day=round(float(np.median(y) / 24), 2), sd_hours=round(float(np.std(y)), 1),
                   iqr_hours=round(float(np.percentile(y, 75) - np.percentile(y, 25)), 1))
        if np.var(y) == 0:
            rec['note'] = 'identical step in every game'; rec['step'] = int(y[0]); tim[name] = rec
            print('timing', name, 'identical in all games at step', int(y[0]), flush=True); continue
        pb = ridge_logo(Xs, y, gr)
        rec['shop_r2'] = round(r2(y, pb), 3)
        rec['resid_sd_hours'] = round(float(np.sqrt(np.mean((y - pb) ** 2))), 1)
        for bn, Xk in (('CASH', cash), ('PRICE_ALL', prices), ('PRICE_OPP', oppp), ('CASH+PRICE', np.hstack([cash, prices]))):
            inc = incremental(y, Xs, Xk, gr)
            if inc is None:
                continue
            rec[bn] = dict(delta=inc['delta'], ci=inc['ci'], resid_share_explained=inc['resid_share_explained'],
                           resid_sd_hours_after=round(float(np.sqrt(np.mean((y - inc['_pf']) ** 2))), 1))
        tim[name] = rec
        print('timing', name, rec['median_day'], 'sd h', rec['sd_hours'], 'resid', rec['resid_sd_hours'], 'cash +', rec['CASH']['delta'], rec['CASH']['ci'], flush=True)

    # cash gating of land purchases: failed requests before the fill, slack at the fill, hours request -> fill
    gate = {}
    for k in (1, 2, 3):
        slack, fails, wait, pre_cash_ok = [], [], [], []
        for g in games:
            lands = [(t, req, ok) for t, o, it, req, ok, c in g['orders'] if o == 'BUY_LAND']
            got = [t for t, req, ok in lands if ok]
            if len(got) < k:
                continue
            tf = got[k - 1]
            prev = got[k - 2] if k > 1 else -1
            reqs = [t for t, req, ok in lands if prev < t <= tf]
            fails.append(sum(1 for t, req, ok in lands if prev < t < tf and not ok))
            wait.append(tf - min(reqs))
            price = [1000, 2000, 4000][k - 1]
            slack.append(g['money'][tf] - price)
        if slack:
            gate[f'land_{k + 1}'] = dict(n=len(slack), failed_requests_before_fill_mean=round(float(np.mean(fails)), 2),
                                         share_with_failed_requests=round(float(np.mean(np.array(fails) > 0)), 3),
                                         hours_first_request_to_fill_median=float(np.median(wait)),
                                         cash_slack_at_fill_median=round(float(np.median(slack)), 1),
                                         cash_slack_at_fill_p10=round(float(np.percentile(slack, 10)), 1))
    # the same for animal purchases (any type) after day 5
    fr = dict(req=0, filled=0, steps_with_failure=0, steps=0)
    for g in games:
        for t, o, it, req, ok, c in g['orders']:
            if o == 'BUY_ANIMAL' and t >= 144:
                fr['req'] += req; fr['filled'] += ok; fr['steps'] += 1; fr['steps_with_failure'] += ok < req
    gate['animals_after_d5'] = fr
    tim['_cash_gating'] = gate
    out['timing'] = tim

    # ---------------- 3. cash terms: value per item-day, board value index
    rev = {p: 0.0 for p in PRODUCTS}
    for g in games:
        for t, o, it, req, ok, c in g['orders']:
            if o == 'SELL' and it in rev:
                rev[it] += c
    rev = {p: v / n for p, v in rev.items()}
    item_days = {it: float(np.mean([sum(cnt(g['counts'][d], it) for d in range(30)) for g in games])) for it in ITEMS}
    animal_days = sum(item_days[a] for a in ANIMALS)
    mean_wheat_price = float(np.mean([g['prices'][t][PI['WHEAT']] for g in games for t in range(0, 720, 24)]))
    v = {}
    for it in ITEMS:
        if it == 'WHEAT':
            v[it] = 0.8 * mean_wheat_price           # feed value: 0.8 units / tile / day at the average wheat price
        else:
            v[it] = rev[PROD_OF[it]] / item_days[it] if item_days[it] else 0.0
        if it in ANIMALS:
            v[it] += rev['FERTILIZER'] / animal_days  # sold fertilizer collected from animals
    out['value_per_item_day'] = {k: round(x, 1) for k, x in v.items()}
    out['revenue_per_game'] = {k: round(x) for k, x in rev.items()}
    out['mean_final_cash'] = round(float(np.mean([g['final'] for g in games])))
    val = {}
    for d in DAYS:
        w = d - 3
        y = np.array([sum(v[it] * cnt(g['counts'][d], it) for it in ITEMS) for g in games])
        Xs = np.array([shop_feats(g['seq'], (d - 1) // 3) for g in games], float)
        Xlag = np.array([[cnt(g['counts'][w], it) for it in ITEMS] for g in games], float)
        rows = {}

        def vblock(i, b):
            gg = games[i]
            rec, opp, _ = comp[i][w]
            oc = [gg['opp_money'][24 * w]] + [cnt(gg['opp_counts'][w], it) for it in ITEMS]
            cash = [gg['money'][24 * w], math.log1p(max(gg['money'][24 * w], 0))]
            return {'PRICE_ALL': rec, 'PRICE_OPP': opp, 'CASH': cash, 'OPP': oc, 'ALL': rec + cash + oc}[b]
        for b in ('PRICE_ALL', 'PRICE_OPP', 'CASH', 'OPP', 'ALL'):
            Xk = np.array([vblock(i, b) for i in range(n)], float)
            inc = incremental(y, Xs, Xk, groups)
            incf = incremental(y, np.hstack([Xs, Xlag]), Xk, groups)
            rem = 30 - d
            rows[b] = dict(delta=inc['delta'], ci=inc['ci'], sd_incr_coins_per_day=inc['sd_incr_pred'],
                           mean_abs_incr_coins_per_day=round(float(np.mean(np.abs(inc['_pf'] - inc['_pb']))), 1),
                           season_coins_mean_abs=round(float(np.mean(np.abs(inc['_pf'] - inc['_pb']))) * rem),
                           flow_delta=incf['delta'], flow_ci=incf['ci'],
                           flow_mean_abs_incr_coins_per_day=round(float(np.mean(np.abs(incf['_pf'] - incf['_pb']))), 1))
        pb = ridge_logo(Xs, y, groups)
        val[d] = dict(mean_value_per_day=round(float(y.mean())), sd_value_per_day=round(float(y.std())),
                      shop_r2=round(r2(y, pb), 3), sd_shop_pred=round(float(np.std(pb))),
                      resid_rmse=round(float(np.sqrt(np.mean((y - pb) ** 2)))),
                      remaining_days=30 - d, blocks=rows)
        print('value', d, val[d]['mean_value_per_day'], 'sd', val[d]['sd_value_per_day'], 'shop r2', val[d]['shop_r2'],
              'ALL +', rows['ALL']['delta'], rows['ALL']['ci'], 'mean|incr|', rows['ALL']['mean_abs_incr_coins_per_day'], flush=True)
    out['board_value'] = val

    # ---------------- 4. feasibility / budget-exactness facts
    fe = {}
    cash_days = {d: np.array([g['money'][24 * d] for g in games]) for d in range(1, 13)}
    fe['day_start_cash'] = {d: dict(median=float(np.median(c)), p10=float(np.percentile(c, 10)), p90=float(np.percentile(c, 90)),
                                    share_below_50=round(float(np.mean(c < 50)), 3), share_below_10=round(float(np.mean(c < 10)), 3))
                            for d, c in cash_days.items()}
    rf = {}
    for lo_d, hi_d in ((0, 6), (6, 12), (12, 30)):
        for op in ('HIRE', 'BUY_SEED', 'BUY_ANIMAL', 'BUY_PRODUCT', 'BUY_LAND', 'SELL'):
            req = sum(req for g in games for t, o, it, req, ok, c in g['orders'] if o == op and 24 * lo_d <= t < 24 * hi_d)
            ok = sum(ok for g in games for t, o, it, req, ok, c in g['orders'] if o == op and 24 * lo_d <= t < 24 * hi_d)
            rf[f'd{lo_d}-{hi_d - 1} {op}'] = dict(requested_per_game=round(req / n, 1), filled_per_game=round(ok / n, 1),
                                                   fill_rate=round(ok / req, 3) if req else None)
    fe['request_vs_fill'] = rf
    fe['dropped_orders_past_10_per_game'] = round(sum(x for g in games for t, x in g['dropped']) / n, 2)
    # day-1 hands vs the wheat price DSM met on day 0 (the opponent's day-0 wheat buying raises it)
    h1 = np.array([max(g['hands'][24:48]) for g in games], float)
    wp0 = np.array([g['prices'][1][PI['WHEAT']] for g in games], float)
    oppw0 = np.array([filled(g['opp_orders'], 'BUY_PRODUCT', 'WHEAT', 0, 1) for g in games], float)
    c1 = np.array([g['money'][24] for g in games], float)
    fe['day1_hands'] = dict(distribution={int(k): int(v) for k, v in zip(*np.unique(h1, return_counts=True))},
                            corr_with_wheat_price_step1=round(float(np.corrcoef(h1, wp0)[0, 1]), 3) if np.std(h1) > 0 else None,
                            corr_with_opp_day0_wheat_buy=round(float(np.corrcoef(h1, oppw0)[0, 1]), 3) if np.std(h1) > 0 and np.std(oppw0) > 0 else None,
                            wheat_price_step1_range=[float(wp0.min()), float(wp0.max())],
                            day1_start_cash_distribution={int(k): int(v) for k, v in zip(*np.unique(c1, return_counts=True))})
    # day-1..5 hands and requests
    fe['hands_by_day_opening'] = {d: {int(k): int(v) for k, v in zip(*np.unique([max(g['hands'][24 * d:24 * d + 24]) for g in games], return_counts=True))}
                                  for d in range(0, 7)}
    # day-6 board identity and hidden stock (seeds / shed)
    def key(c):
        return tuple(sorted((k, v) for k, v in c.items() if k != 'WEED'))
    from collections import Counter
    for d in (3, 6, 7, 9):
        cc = Counter(key(g['counts'][d]) for g in games)
        top, topn = cc.most_common(1)[0]
        fe[f'day{d}_board_modal_share'] = dict(share=round(topn / n, 3), modal=dict(top), n_distinct=len(cc))
    # does the day-1 execution shortfall (hands) reach the day-6 plan?
    modal6 = max(Counter(key(g['counts'][6]) for g in games).items(), key=lambda kv: kv[1])[0]
    xt = {}
    for g in games:
        h = int(max(g['hands'][24:48]))
        e = xt.setdefault(h, dict(n=0, modal_day6_board=0, day6_cash=[], day1_cash=[]))
        e['n'] += 1; e['modal_day6_board'] += key(g['counts'][6]) == modal6
        e['day6_cash'].append(g['money'][144]); e['day1_cash'].append(g['money'][24])
    fe['day1_hands_vs_day6'] = {h: dict(n=e['n'], share_modal_day6_board=round(e['modal_day6_board'] / e['n'], 3),
                                        day6_cash_median=float(np.median(e['day6_cash'])), day1_cash_median=float(np.median(e['day1_cash'])))
                                for h, e in sorted(xt.items())}
    fe['day6_board_variants'] = [[dict(k), v] for k, v in Counter(key(g['counts'][6]) for g in games).most_common()]
    fe['day6_seeds'] = Counter(json.dumps(g['seeds'][6], sort_keys=True) for g in games).most_common(6)
    fe['day6_shed'] = Counter(json.dumps(g['shed'][6], sort_keys=True) for g in games).most_common(6)
    fe['day6_cash'] = dict(median=float(np.median([g['money'][144] for g in games])),
                           p10=float(np.percentile([g['money'][144] for g in games], 10)),
                           p90=float(np.percentile([g['money'][144] for g in games], 90)))
    # opening request streams: identical across games? (market orders, days 0-5)
    streams = Counter(json.dumps([[t, o, it, req] for t, o, it, req, ok, c in g['orders'] if t < 144]) for g in games)
    fe['opening_request_stream_distinct'] = len(streams)
    fe['opening_request_stream_modal_share'] = round(streams.most_common(1)[0][1] / n, 3)
    fills = Counter(json.dumps([[t, o, it, ok] for t, o, it, req, ok, c in g['orders'] if t < 144]) for g in games)
    fe['opening_fill_stream_distinct'] = len(fills)
    out['feasibility'] = fe

    (OUTDIR / 'results.json').write_text(json.dumps(out, indent=1, default=float), encoding='utf-8')
    print('wrote', OUTDIR / 'results.json')


if __name__ == '__main__':
    main()
