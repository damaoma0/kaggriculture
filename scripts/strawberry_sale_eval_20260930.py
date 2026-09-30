"""Offline strawberry SALE-TIMING evaluator on the recorded b2b games (2026-09-30).

Keeps production, the frozen opponent's executed sales (units per tick and their order positions) and the town draws
FIXED, and lets a sale policy choose the tick at which each of OUR strawberries is sold:
  * a unit is available from the tick it enters our shed in the recorded game (market model `our_in`: harvest
    deliveries, same-day rush deliveries, and the midnight dump at t % 24 == 0);
  * our shed holds <= 100 items: strawberries held at tick t plus the OTHER goods recorded in the shed at t
    (frame sh[t]) must fit, so a policy that holds longer is forced to sell the excess (as the executor's capacity
    rule does) -- `--nocap` drops the constraint as a sensitivity;
  * units still unsold after step 718 count at 0 (every policy sells what is left at step 718, as the executor does).
Every unit is re-priced with the engine's price function, unit by unit, with the engine's lockstep interleaving of
the two players' orders (SM.market_step). Our strawberry order sits at queue index 0 ('front', what the proposed
v18z hook A6 does); `--idx back` puts it behind every opponent order (the other bound). The recorded schedule keeps
its recorded order structure and reproduces the recorded revenues exactly.
Objective: MARGIN delta = (our strawberry revenue - recorded) - (opponent strawberry revenue - recorded).

Opponent observables a deployable rule may use (all public at the tick it decides):
  * the market inventory / price entering the tick (exact), the unlocked shops (so the draw schedule of today);
  * the opponent's PAST sales per tick (inventory change - our sales + draws; exact because strawberries cannot be
    bought);
  * the opponent's visible strawberries: harvested so far (yield drops on its public board) minus sold so far
    ('pending'), plus the yield standing on its board today. The board itself is not in our recordings; the
    rival's harvest events come from the engine-hooked trace (item_trace/x_n18rc8x_src, DSM's game, same frozen
    rival commands) and a unit harvested on day d is credited as visible from the start of day d (strawberry yield
    only grows at the day refresh, so it was on the board then) -- a conservative subset of the visible yield.
No rule uses the opponent's future orders, its shed, or anything else private. (The recommended rule uses only the
holdings = harvested - sold; adding the standing yield, `ripe=True`, makes it sell too early: +158 instead of +1,017.)

Policies: recorded; oracle (exact DP over our cumulative sales, knows the rival's future: upper bound) and restricted
oracles (no shed cap / recorded units per day / post-draw ticks only); arrival; post_draw_all; dawn_h0 / dawn_h1;
even6 (equal lots at post-tick hours 1,5,..,21); recorded+24h; nextprice (own price now >= projected next post-draw
price); rival_empty8 (hold while the rival holds < 8); hold_best (RECOMMENDED, make_hold_rule(**BEST)); its day-29
executor variant; hold_perfect_fc (same rule fed the rival's actual future sales: diagnostic, not deployable).

Result (2026-09-30, 21 main games = 9 worlds x {dsm, n18rc127} + rush world arms n18rc194d/206d/207d), mean margin
delta: oracle +2,569; hold_best +1,017 (18/21 better, worst -226; our 12 games +1,474; leave-one-world-out +756);
even6 +197; arrival -921; dawn_h1 -525. On the 75 other cached arms: hold_best +1,169 (74/75 better), even6 +460.
Rush world strawberry margin under hold_best: 194d -828, 206d -547 (+281 vs base; recorded -826), 207d -1,622.

usage: strawberry_sale_eval_20260930.py [--games main|rush|other|all] [--idx front|back] [--nocap] [--cv] [--mech]
                                        [--verbose] [--json OUT]
  main: the 21 games above; other: every other cached b2b game; --cv: leave-one-world-out choice of (H, theta, win);
  --mech: where the rule's margin comes from. About 20 s for main (single process, no games are run).
"""
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import strawberry_market_20260930 as SM  # noqa: E402

ITEM = "STRAWBERRY"
N = 719
TPD = 24
TRACE = SM.TRACE
IMIN, IMAX = 9000, 11200
_PR = np.array([SM.price(ITEM, i) for i in range(IMIN, IMAX)], dtype=np.float64)
_FP = np.concatenate([[0.0], np.cumsum(_PR)])      # F(I) = sum_{i < I} price(i)   (index I - IMIN)
_P = SM.MARKET_PARAMS[ITEM]


def F(I):
    return _FP[np.asarray(I) - IMIN]


def P(I):
    return _PR[np.asarray(I) - IMIN]


def pcont(x):
    """engine price curve without rounding / floor (for planning with fractional forecasts)"""
    base, I0, T = _P["base"], _P["I0"], _P["T"]
    if x < I0:
        amp = _P["below_target"] * base / math.sqrt(T)
        return base + amp * math.sqrt(I0 - x)
    amp = _P["above_target"] * base / T
    return max(1.0, base - amp * (x - I0))


# ------------------------------------------------------------------------------------------------------ inputs
MAIN = [(c, g) for c in SM.CASES for g in ("dsm", "n18rc127.p0")] + \
       [("114393058", "n18rc194d.p0"), ("114393058", "n18rc206d.p0"), ("114393058", "n18rc207d.p0")]
RUSH = [("114393058", "n18rc194d.p0"), ("114393058", "n18rc206d.p0"), ("114393058", "n18rc207d.p0")]


def rival_harvest(case, seat):
    """rival STRAWBERRY harvest units per tick from the engine trace (public: its board's yield drops)"""
    f = TRACE / f"dsm3q-{case}.items.json"
    h = [0] * N
    if not f.exists():
        return None
    j = json.loads(f.read_text())
    if int(j.get("our_seat", seat)) != seat:
        return None
    for e in j["events"]:
        if e[0] == "produced" and e[1] == 1 - seat and e[5] == ITEM and 0 <= int(e[2]) < N:
            h[int(e[2])] += int(e[6]) if isinstance(e[6], (int, float)) else 1
    return h


def prepare(case, game):
    G, A = SM.load_game(case, game)
    m = SM.load_market(case, game, ITEM, G=G, A=A)
    seat = m["seat"]
    fr = G["frames"]
    other = [sum(int(v) for k, v in (f.get("sh") or {}).items() if k != ITEM) for f in fr]
    oo = m["_orders"]["opp"]
    o = m["opp_sales"]
    k0 = [min(oo[t][0] if oo[t] else 0, o[t]) for t in range(N)]
    B = [SM.MARKET_I0] * (N + 1)                   # inventory path without any of our sales
    for t in range(N):
        B[t + 1] = B[t] + o[t] - m["draws"][t]
    harv = rival_harvest(m["case"], seat)
    return dict(case=m["case"], game=game, seat=seat, m=m, arr=list(m["our_in"]), other=other,
                cap=[100 - x for x in other], o=list(o), oo=oo, k0=k0, rest=[o[t] - k0[t] for t in range(N)],
                d=list(m["draws"]), B=B, shops=[f.get("s") or [] for f in fr], harv=harv,
                rec_our=sum(m["our_revenue"]), rec_opp=sum(m["opp_revenue"]), rec_q=list(m["our_sales"]),
                our_orders=m["_orders"]["us"])


# ------------------------------------------------------------------------------------------------------ exact evaluation
def evaluate(Pg, q, idx=0, recorded=False, detail=False):
    """exact re-pricing of our schedule q[t] (units sold in step t) against the frozen opponent"""
    seat = Pg["seat"]
    inv, stock = SM.MARKET_I0, 0
    our = opp = 0
    cap_viol = short = 0
    per = defaultdict(lambda: [0, 0, 0, 0]) if detail else None      # day -> our units, our rev, opp units, opp rev
    for t in range(N):
        stock += Pg["arr"][t]
        if stock > Pg["cap"][t]:
            cap_viol += 1
        want = int(q[t])
        if want > stock:
            short += want - stock
            want = stock
        if recorded:
            ours = list(Pg["our_orders"][t])
        else:
            ours = ([0] * idx + [want]) if idx < 10 else ([0] * 10 + [want])
        sells = [None, None]
        sells[seat], sells[1 - seat] = ours, Pg["oo"][t]
        have = [0, 0]
        have[seat], have[1 - seat] = (stock if recorded else want), Pg["o"][t]
        inv, sold, rev, _ = SM.market_step(ITEM, inv, sells, have)
        stock -= sold[seat]
        our += rev[seat]
        opp += rev[1 - seat]
        if detail:
            r = per[t // TPD]
            r[0] += sold[seat]; r[1] += rev[seat]; r[2] += sold[1 - seat]; r[3] += rev[1 - seat]
        inv -= Pg["d"][t]
    res = dict(our=our, opp=opp, own_delta=our - Pg["rec_our"], opp_delta=opp - Pg["rec_opp"],
               margin_delta=(our - Pg["rec_our"]) - (opp - Pg["rec_opp"]), unsold=stock, cap_viol=cap_viol,
               short=short)
    if detail:
        res["per_day"] = dict(per)
    return res


def run_policy(Pg, policy, idx=0, cap=True, **kw):
    """online runner: policy(Pg, t, inv, stock, ctx) -> units to sell now, from observables only; the runner adds
    the capacity-forced sales (held + next tick's own arrivals must fit next tick's room) and sells all at 718"""
    seat = Pg["seat"]
    inv, stock = SM.MARKET_I0, 0
    q = [0] * N
    ctx = dict(kw)
    ctx["opp_hist"] = [0] * N        # opponent units sold per past tick (observable after the tick)
    for t in range(N):
        stock += Pg["arr"][t]
        want = int(policy(Pg, t, inv, stock, ctx)) if stock > 0 else 0
        if cap and t + 1 < N:
            need = stock - want + Pg["arr"][t + 1] - Pg["cap"][t + 1]
            if need > 0:
                want += need
        if t == N - 1:
            want = stock
        want = max(0, min(want, stock))
        q[t] = want
        ours = ([0] * idx + [want]) if idx < 10 else ([0] * 10 + [want])
        sells = [None, None]
        sells[seat], sells[1 - seat] = ours, Pg["oo"][t]
        have = [0, 0]
        have[seat], have[1 - seat] = want, Pg["o"][t]
        inv, sold, rev, _ = SM.market_step(ITEM, inv, sells, have)
        stock -= sold[seat]
        ctx["opp_hist"][t] = sold[1 - seat]
        inv -= Pg["d"][t]
    return q


# ------------------------------------------------------------------------------------------------------ oracle (exact DP)
def _tickval(Pg, t, I, q):
    """margin of step t (our revenue - opponent revenue of this step) with our q units at order index 0,
    vectorised over the inventory I (engine lockstep: common rounds pay both sides the same quote and cancel)"""
    k0, rest = Pg["k0"][t], Pg["rest"][t]
    if k0 == 0 and rest == 0:
        return F(I + q) - F(I)
    mm = min(q, k0)
    base = I + 2 * mm
    v = np.zeros_like(I, dtype=np.float64)
    if q > k0:
        v += F(base + (q - k0)) - F(base)
    if k0 > q:
        v -= F(base + (k0 - q)) - F(base)
    if rest:
        v -= F(I + q + k0 + rest) - F(I + q + k0)
    return v


def oracle(Pg, cap=True, allowed=None, fix_days=False):
    """margin-optimal schedule (upper bound: knows the opponent's future sales). Exact DP over S = our units sold
    so far (inventory entering t = B[t] + S). allowed(t) -> False forbids selling at t (restricted oracles);
    fix_days: units sold per day fixed to the recorded ones (only the hour within the day is optimised)."""
    arr = Pg["arr"]
    Ac = np.cumsum(arr)
    At = int(Ac[-1])
    S = np.arange(At + 1)
    NEG = -1e15
    lb = [max(0, int(Ac[t]) + Pg["other"][t] - 100) if cap else 0 for t in range(N)] + [0]
    ub = [At] * (N + 1)
    if fix_days:
        cs = np.concatenate([[0], np.cumsum(Pg["rec_q"])])
        for t in range(0, N + 1, TPD):
            lb[t] = ub[t] = int(cs[t])
    V = np.zeros((N + 1, At + 1))
    for t in range(N - 1, -1, -1):
        a_prev = int(Ac[t - 1]) if t > 0 else 0
        a_now = int(Ac[t])
        I = Pg["B"][t] + S
        Vn = V[t + 1]
        valid_next = (S <= a_now) & (S >= lb[t + 1]) & (S <= ub[t + 1])
        can = allowed is None or allowed(t) or t == N - 1
        if Pg["k0"][t] == 0 and Pg["rest"][t] == 0 and can:
            W = np.where(valid_next, F(I) + Vn, NEG)
            suf = np.maximum.accumulate(W[::-1])[::-1]
            v = suf - F(I)
        else:
            v = np.full(At + 1, NEG)
            # a forbidden tick still allows the capacity-forced minimum (units that would not fit next tick)
            force = np.maximum(0, lb[t + 1] - S)
            qmax = a_now
            for qq in range(0, qmax + 1):
                S2 = S + qq
                ok = (S2 <= At) if can else ((S2 <= At) & (force == qq))
                S2c = np.minimum(S2, At)
                cand = _tickval(Pg, t, I, qq) + np.where(ok & valid_next[S2c], Vn[S2c], NEG)
                v = np.maximum(v, cand)
        v = np.where((S <= a_prev) & (S >= lb[t]) & (S <= ub[t]), v, NEG)
        V[t] = v
    # forward recovery
    q = [0] * N
    s = 0
    for t in range(N):
        a_now = int(Ac[t])
        I = np.array([Pg["B"][t] + s])
        best, bq = None, 0
        can = allowed is None or allowed(t) or t == N - 1
        for qq in range(0, a_now - s + 1):
            s2 = s + qq
            if s2 < lb[t + 1] or s2 > ub[t + 1]:
                continue
            if not can and qq != max(0, lb[t + 1] - s):
                continue
            val = float(_tickval(Pg, t, I, qq)[0]) + V[t + 1][s2]
            if best is None or val > best + 1e-9:
                best, bq = val, qq
        q[t] = bq
        s += bq
    return q, float(V[0][0])


# ------------------------------------------------------------------------------------------------------ simple policies
def pol_arrival(Pg, t, inv, stock, ctx):
    return Pg["arr"][t]


def pol_every(Pg, t, inv, stock, ctx):
    return stock


def pol_post(Pg, t, inv, stock, ctx):          # right after a draw (post-tick hours 1, 5, 9, ...)
    return stock if t % 4 == 1 else 0


def pol_dawn0(Pg, t, inv, stock, ctx):
    return stock if t % TPD == 0 else 0


def pol_dawn1(Pg, t, inv, stock, ctx):
    return stock if t % TPD == 1 else 0


def pol_even(Pg, t, inv, stock, ctx):
    """equal lots over the remaining post-tick hours of the day (1, 5, 9, 13, 17, 21); last lot at 21 sells all"""
    h = t % TPD
    if h % 4 != 1:
        return 0
    left = (21 - h) // 4 + 1
    return int(math.ceil(stock / left))


def pol_shift(Pg, t, inv, stock, ctx):
    """recorded schedule delayed by ctx['lag'] ticks (illustration)"""
    lag = ctx.get("lag", 24)
    return Pg["rec_q"][t - lag] if t >= lag else 0


# ------------------------------------------------------------------------------------------------------ rival-aware rules
def draws_ahead(shops, t0, H):
    """town draws of strawberries in steps t0 .. t0+H-1 with today's unlocked shops (tomorrow's new shop unknown)"""
    return [SM.draw(ITEM, t, shops) for t in range(t0, min(N, t0 + H))]


def slope(x):
    """price drop caused by one more unit at inventory x (continuous engine curve)"""
    return pcont(x) - pcont(x + 1)


class RivalView:
    """what the rival's public state tells us at the start of tick t (before its market):
    holdings  = strawberries it harvested through t-1 (board yield drops) - strawberries it sold through t-1
                (market history); exact, because strawberries cannot be bought
    ripe      = yield it harvests later today (standing on its board since the day refresh; conservative)
    hazard f_h = share of its holdings it sold at hour h over the last `win` days (days >= 11), shrunk toward its
                pooled share (prior weight `prior` holding-ticks) and to `f0` before it has any history"""

    def __init__(self, Pg, win=3, prior=20.0, f0=0.08, post_only_prior=True):
        self.h = Pg["harv"] or [0] * N
        self.win, self.prior, self.f0 = win, prior, f0
        self.cum_h = np.concatenate([[0], np.cumsum(self.h)])
        self.sold = 0
        self.expo = defaultdict(float)     # (day, hour) -> holdings exposed
        self.hit = defaultdict(float)      # (day, hour) -> units sold
        self.post_only_prior = post_only_prior

    def holdings(self, t):
        return max(0, int(self.cum_h[t]) - self.sold)

    def ripe_today(self, t):
        end = (t // TPD + 1) * TPD
        return int(self.cum_h[min(end, N)] - self.cum_h[t])

    def observe(self, t, opp_units):
        H = self.holdings(t)
        d, h = t // TPD, t % TPD
        if H > 0 and d >= 11:
            self.expo[(d, h)] += H
            self.hit[(d, h)] += min(opp_units, H)
        self.sold += opp_units

    def hazards(self, t):
        d0 = t // TPD
        days = range(max(11, d0 - self.win), d0 + 1)
        ex = [sum(self.expo.get((d, h), 0.0) for d in days) for h in range(TPD)]
        hi = [sum(self.hit.get((d, h), 0.0) for d in days) for h in range(TPD)]
        tot_e, tot_h = sum(ex), sum(hi)
        if tot_e <= 0:
            if self.post_only_prior:
                return [self.f0 * 4 if h % 4 == 1 else 0.0 for h in range(TPD)]
            return [self.f0] * TPD
        pooled = tot_h / tot_e
        return [(hi[h] + self.prior * pooled) / (ex[h] + self.prior) for h in range(TPD)]

    def forecast(self, t, H, ripe=True, rate=False):
        """expected rival units per tick for ticks t .. t+H-1"""
        f = self.hazards(t)
        Hh = self.holdings(t) + (self.ripe_today(t) if ripe else 0)
        out = []
        for k in range(t, min(N, t + H)):
            x = f[k % TPD] * Hh
            out.append(x)
            Hh -= x
        return out


def make_hold_rule(H=24, theta=0.0, win=3, prior=20.0, f0=0.08, ripe=True, same_tick=0.5, frac=1.0,
                   minpx=0, perfect=False, phase=None, lot=0, nohold="all", endgame_day=None, day0=0):
    """SELL-NOW-IF rule (deployable). At tick t with stock > 0:
        o[j]  = expected rival units in tick j (RivalView.forecast), D = today's-shop draws, I = market inventory
        for every later tick k <= t+H:  hold_gain(k) = P(I_k) - P(I) - sum_{t<=j<k} o[j] * slope(I_j)
                                        - same_tick * o[k] * slope(I_k)
            with I_j = I + sum_{t<=i<j} (o[i] - D[i])   (our units held; the rival's sales and the draws move it)
        (linear side: hold_gain = 1.92 * (draws before k - 2 * rival units before k))
        sell the whole stock now (times `frac`) if max_k hold_gain(k) <= theta, else hold.
    same_tick: share of the rival's units in tick k assumed to go before ours (lockstep at index 0 ~ 0.5)."""

    def pol(Pg, t, inv, stock, ctx):
        rv = ctx.get("_rv")
        if rv is None:
            rv = ctx["_rv"] = RivalView(Pg, win=win, prior=prior, f0=f0)
        # observe everything up to t-1 (the runner records opp_hist after each tick)
        while ctx.get("_seen", 0) < t:
            s_ = ctx.get("_seen", 0)
            rv.observe(s_, ctx["opp_hist"][s_])
            ctx["_seen"] = s_ + 1
        Hh = min(H, N - 1 - t)
        if Hh <= 0:
            return stock
        if endgame_day is not None and t // TPD >= endgame_day:
            return stock                     # the executor's last-day rule: everything, every tick
        if t // TPD < day0:
            return stock if (phase is None or t % 4 == phase) else 0
        if phase is not None and t % 4 != phase:
            return 0
        if perfect:                          # DIAGNOSTIC ONLY (not deployable): the rival's actual future sales
            o = [float(x) for x in Pg["o"][t:t + Hh + 1]]
            D = Pg["d"][t:t + Hh + 1]
        else:
            o = rv.forecast(t, Hh + 1, ripe=ripe)
            D = draws_ahead(Pg["shops"][t], t, Hh + 1)
        p0 = pcont(inv)
        Ij = float(inv)
        ext = 0.0
        best = -1e9
        for j in range(Hh + 1):
            if j > 0 and (phase is None or (t + j) % 4 == phase):
                g = pcont(Ij) - p0 - ext - same_tick * o[j] * slope(Ij)
                if g > best:
                    best = g
            ext += o[j] * slope(Ij)
            Ij += o[j] - D[j]
        if best <= theta and pcont(inv) >= minpx:
            if nohold == "even":             # no hold value: the day's equal lot instead of everything
                left = (21 - t % TPD) // 4 + 1 if t % TPD <= 21 else 1
                return int(math.ceil(stock / max(1, left)))
            return int(math.ceil(stock * frac))
        return min(stock, lot)

    return pol


def make_nextprice_rule(win=1, prior=20.0):
    """own-price 'sell now if the price now >= the projected price at the next opportunity' (next post-draw tick):
    projected inventory = I + expected rival units (RivalView) - today's-shop draws over the next 4 ticks"""
    def pol(Pg, t, inv, stock, ctx):
        rv = ctx.get("_rv")
        if rv is None:
            rv = ctx["_rv"] = RivalView(Pg, win=win, prior=prior)
        while ctx.get("_seen", 0) < t:
            s_ = ctx.get("_seen", 0)
            rv.observe(s_, ctx["opp_hist"][s_])
            ctx["_seen"] = s_ + 1
        if t + 4 >= N:
            return stock
        if t % 4 != 1:
            return 0
        o = rv.forecast(t, 4, ripe=False)
        D = draws_ahead(Pg["shops"][t], t, 4)
        return stock if pcont(inv) >= pcont(inv + sum(o) - sum(D)) else 0
    return pol


def make_rival_empty_rule(th=8):
    """hold while the rival's public holdings (harvested - sold) are below th, else sell all at the post-draw tick"""
    def pol(Pg, t, inv, stock, ctx):
        rv = ctx.get("_rv")
        if rv is None:
            rv = ctx["_rv"] = RivalView(Pg)
        while ctx.get("_seen", 0) < t:
            s_ = ctx.get("_seen", 0)
            rv.observe(s_, ctx["opp_hist"][s_])
            ctx["_seen"] = s_ + 1
        if t % 4 != 1:
            return 0
        return stock if rv.holdings(t) >= th else 0
    return pol


# the recommended deployable rule (make_hold_rule doc; report in __main__): chosen on the 21 main games, checked by
# leave-one-world-out (--cv) and on the 75 other cached games (--games other)
BEST = dict(H=30, theta=4.0, win=1, prior=20.0, same_tick=0.5, ripe=False, phase=1)

# ------------------------------------------------------------------------------------------------------ driver
POLICIES = [
    ("arrival", pol_arrival, {}),
    ("post_draw_all", pol_post, {}),
    ("dawn_h0", pol_dawn0, {}),
    ("dawn_h1", pol_dawn1, {}),
    ("even6", pol_even, {}),
    ("recorded+24h", pol_shift, {"lag": 24}),
    ("nextprice", None, {}),
    ("rival_empty8", None, {}),
    ("hold_best", None, {}),
    ("hold_best_endgame29", None, {}),
    ("hold_perfect_fc", None, {}),         # diagnostic only: the same rule fed the rival's actual future sales
]
SHOW = ("oracle", "oracle_dayfixed", "arrival", "dawn_h1", "even6", "nextprice", "hold_best", "hold_perfect_fc")


def _policy_fn(name, fn):
    if fn is not None:
        return fn
    if name == "nextprice":
        return make_nextprice_rule()
    if name == "rival_empty8":
        return make_rival_empty_rule(8)
    if name == "hold_best":
        return make_hold_rule(**BEST)
    if name == "hold_best_endgame29":
        return make_hold_rule(**dict(BEST, endgame_day=29))
    if name == "hold_perfect_fc":
        return make_hold_rule(**dict(BEST, perfect=True, theta=0.0, same_tick=1.0))
    raise KeyError(name)


def evaluate_game(Pg, idx=0, cap=True, policies=None, with_oracle=True):
    out = {}
    rec = evaluate(Pg, Pg["rec_q"], recorded=True)
    assert rec["our"] == Pg["rec_our"] and rec["opp"] == Pg["rec_opp"], (Pg["case"], Pg["game"], rec)
    out["recorded"] = rec
    if with_oracle:
        for name, kw in (("oracle", dict(cap=cap)), ("oracle_nocap", dict(cap=False)),
                         ("oracle_dayfixed", dict(cap=cap, fix_days=True)),
                         ("oracle_postdraw", dict(cap=cap, allowed=lambda t: t % 4 == 1))):
            q, val = oracle(Pg, **kw)
            r = evaluate(Pg, q, idx=0)
            r["dp_exact"] = abs((r["our"] - r["opp"]) - val) < 1e-6   # False only where the $1 floor binds
            r["dp_value"] = val
            out[name] = r
    for name, fn, kw in (policies or POLICIES):
        q = run_policy(Pg, _policy_fn(name, fn), idx=idx, cap=cap, **kw)
        out[name] = evaluate(Pg, q, idx=idx)
    out["hold_best_idx_back"] = evaluate(Pg, run_policy(Pg, _policy_fn("hold_best", None), idx=10, cap=cap), idx=10)
    return out


def _games(which):
    if which == "main":
        return list(MAIN)
    if which == "rush":
        return list(RUSH)
    main_set = set(MAIN)
    out = []
    for f in sorted(SM.B2B.glob("dsm3q-*.game.json.gz")):
        case, game = f.name[len("dsm3q-"):-len(".game.json.gz")].split(".", 1)
        if which == "other" and (case, game) in main_set:
            continue
        out.append((case, game))
    return out


def summarise(rows, names):
    """means over games: all, ours (not DSM's own game), dsm, world-weighted, the three rush-world arms"""
    groups = [("all", [r for r in rows]), ("ours", [r for r in rows if r[1] != "dsm"]),
              ("dsm", [r for r in rows if r[1] == "dsm"]), ("rush3", [r for r in rows if (r[0], r[1]) in RUSH])]
    out = {}
    for k in names:
        d = {}
        for gname, g in groups:
            if not g:
                continue
            md = np.array([r[2][k]["margin_delta"] for r in g])
            d[gname] = dict(n=len(g), margin=float(md.mean()), own=float(np.mean([r[2][k]["own_delta"] for r in g])),
                            opp=float(np.mean([r[2][k]["opp_delta"] for r in g])), better=int((md > 0).sum()),
                            worse=int((md < 0).sum()), worst=float(md.min()))
        ws = sorted(set(r[0] for r in rows))
        d["world_weighted"] = float(np.mean([np.mean([r[2][k]["margin_delta"] for r in rows if r[0] == w]) for w in ws]))
        out[k] = d
    return out


def lowo_cv(PGs, grid=None):
    """leave-one-world-out choice of (H, theta, win) for the hold rule: pick on the other worlds, score the held-out"""
    grid = grid or [(H, th, w) for H in (16, 24, 30, 36, 48) for th in (2.0, 4.0, 6.0, 8.0, 10.0) for w in (1, 2, 3)]
    M = {}
    for H, th, w in grid:
        fn = make_hold_rule(**dict(BEST, H=H, theta=th, win=w))
        M[(H, th, w)] = np.array([evaluate(Pg, run_policy(Pg, fn))["margin_delta"] for Pg in PGs])
    worlds = sorted(set(Pg["case"] for Pg in PGs))
    wid = np.array([Pg["case"] for Pg in PGs])
    test, picks = [], {}
    for w in worlds:
        tr = wid != w
        best = max(M, key=lambda k: M[k][tr].mean())
        picks[w] = (best, float(M[best][~tr].mean()), int((~tr).sum()))
        test.extend(M[best][~tr].tolist())
    top = sorted(M, key=lambda k: -M[k].mean())[:8]
    return dict(picks=picks, lowo_mean=float(np.mean(test)),
                lowo_world_weighted=float(np.mean([v[1] for v in picks.values()])),
                top_in_sample=[(k, round(float(M[k].mean()), 1)) for k in top])


def _unit_prices(Pg, q, recorded=False):
    """per unit of ours, FIFO by arrival: (arrival tick, sale tick, price); opponent revenue per tick"""
    seat = Pg["seat"]
    inv, stock, fifo, units, opp_t = SM.MARKET_I0, 0, [], [], [0] * N
    for t in range(N):
        fifo += [t] * Pg["arr"][t]
        stock += Pg["arr"][t]
        sells = [None, None]
        sells[seat], sells[1 - seat] = (list(Pg["our_orders"][t]) if recorded else [q[t]]), Pg["oo"][t]
        have = [0, 0]
        have[seat], have[1 - seat] = (stock if recorded else q[t]), Pg["o"][t]
        inv, sold, rev, f = SM.market_step(ITEM, inv, sells, have)
        for _i, pid, _qi, qp in f:
            if pid == seat:
                units.append((fifo.pop(0), t, qp))
            else:
                opp_t[t] += qp
        stock -= sold[seat]
        inv -= Pg["d"][t]
    return units, opp_t


def mechanism(PGs, rule=None):
    """where the rule's margin comes from, over our games (not DSM's): own revenue gain by the arrival day of the
    unit, opponent revenue change by the day of its sale, holding while the rival holds none, lockstep share"""
    rule = rule or make_hold_rule(**BEST)
    PH = (("d<=17", range(0, 18)), ("d18-21", range(18, 22)), ("d22-29", range(22, 30)))
    own_by, opp_by = defaultdict(float), defaultdict(float)
    n = held = held0 = tot = lock = lock_r = pre = pre_r = 0
    dp_rule, dp_rec = [], []
    for Pg in PGs:
        if Pg["game"] == "dsm":
            continue
        n += 1
        q = run_policy(Pg, rule)
        ur, opr = _unit_prices(Pg, q)
        uc, opc = _unit_prices(Pg, None, recorded=True)
        for (a1, _t1, p1), (_a2, _t2, p2) in zip(ur, uc):
            own_by[next(k for k, rg in PH if a1 // TPD in rg)] += p1 - p2
        for t in range(N):
            opp_by[next(k for k, rg in PH if t // TPD in rg)] += opr[t] - opc[t]
        cumh = np.concatenate([[0], np.cumsum(Pg["harv"])])
        cso = np.concatenate([[0], np.cumsum(Pg["o"])])
        nxt, nn = [None] * N, None
        for t in range(N - 1, -1, -1):
            nn = t if Pg["o"][t] > 0 else nn
            nxt[t] = nn
        for a, t, p in ur:
            tot += 1
            held += t - a
            held0 += sum(1 for k in range(a, t) if cumh[k] - cso[k] <= 0)
            lock += Pg["o"][t] > 0
            pre += Pg["o"][t] == 0 and nxt[t] is not None and nxt[t] - t <= 4
            dp_rule.append(p - Pg["m"]["price"][a])
        for a, t, p in uc:
            lock_r += Pg["o"][t] > 0
            pre_r += Pg["o"][t] == 0 and nxt[t] is not None and nxt[t] - t <= 4
            dp_rec.append(p - Pg["m"]["price"][a])
    return dict(games=n, own_gain_by_arrival_day={k: round(v / n) for k, v in own_by.items()},
                opp_change_by_sale_day={k: round(v / n) for k, v in opp_by.items()},
                mean_hold_ticks=held / max(1, tot), share_hold_rival_empty=held0 / max(1, held),
                same_tick_as_rival=(lock / max(1, tot), lock_r / max(1, tot)),
                within_4_before_rival=(pre / max(1, tot), pre_r / max(1, tot)),
                price_minus_arrival_quote=(float(np.mean(dp_rule)), float(np.mean(dp_rec))))


def main(argv):
    which = argv[argv.index("--games") + 1] if "--games" in argv else "main"
    idx = 10 if ("--idx" in argv and argv[argv.index("--idx") + 1] == "back") else 0
    cap = "--nocap" not in argv
    t0 = time.time()
    rows, PGs = [], []
    for case, game in _games(which):
        try:
            Pg = prepare(case, game)
        except FileNotFoundError as e:
            print("skip", case, game, e)
            continue
        if Pg["harv"] is None:
            print("skip", case, game, "(no rival harvest trace)")
            continue
        res = evaluate_game(Pg, idx=idx, cap=cap)
        rows.append((case, game, res))
        PGs.append(Pg)
        if which in ("main", "rush") or "--verbose" in argv:
            print(f"{case} {game:13s} rec our {Pg['rec_our']:6d} opp {Pg['rec_opp']:6d} |" +
                  "".join(f" {k}={res[k]['margin_delta']:+.0f}" for k in SHOW), flush=True)
    names = [k for k in rows[0][2] if k != "recorded"]
    S = summarise(rows, names)
    print(f"\nmargin delta vs the recorded schedule (our strawberry revenue gain - opponent's), {len(rows)} games,"
          f" our order at {'the back' if idx else 'queue index 0'}, shed cap {'on' if cap else 'off'}")
    print(f"{'policy':22s} {'all':>8s} {'own':>7s} {'opp':>7s} {'ours':>8s} {'dsm':>8s} {'w-world':>8s} {'rush3':>8s}"
          f" {'better/worse':>12s} {'worst':>7s}")
    nan = float("nan")
    for k in names:
        d = S[k]
        a = d["all"]
        print(f"{k:22s} {a['margin']:+8.0f} {a['own']:+7.0f} {a['opp']:+7.0f} {d.get('ours', {}).get('margin', nan):+8.0f}"
              f" {d.get('dsm', {}).get('margin', nan):+8.0f} {d['world_weighted']:+8.0f}"
              f" {d.get('rush3', {}).get('margin', nan):+8.0f} {a['better']:5d}/{a['worse']:<5d}  {a['worst']:+7.0f}")
    bad = [(r[0], r[1], k) for r in rows for k in ("oracle", "oracle_nocap", "oracle_dayfixed", "oracle_postdraw")
           if not r[2][k]["dp_exact"]]
    print("oracle DP value == exact re-pricing:", "all games" if not bad else f"NOT for {bad}")
    rush = {(r[0], r[1]): r[2] for r in rows if (r[0], r[1]) in RUSH}
    if len(rush) == 3:
        print("\nrush world 114393058: strawberry margin (our revenue - opponent revenue) per arm, and rush - base")
        for k in ["recorded"] + names:
            vals = [rush[g][k]["our"] - rush[g][k]["opp"] for g in RUSH]
            print(f"  {k:22s} 194d {vals[0]:+7d}  206d {vals[1]:+7d} ({vals[1] - vals[0]:+6d})  207d {vals[2]:+7d}"
                  f" ({vals[2] - vals[0]:+6d})")
    out = dict(games=[(r[0], r[1]) for r in rows], summary=S,
               per_game={f"{r[0]}.{r[1]}": {k: {kk: vv for kk, vv in v.items() if kk != "per_day"}
                                            for k, v in r[2].items()} for r in rows}, best=BEST)
    if "--cv" in argv:
        cv = lowo_cv(PGs)
        out["lowo"] = {"picks": {w: [list(v[0]), v[1], v[2]] for w, v in cv["picks"].items()},
                       "lowo_mean": cv["lowo_mean"], "lowo_world_weighted": cv["lowo_world_weighted"],
                       "top_in_sample": cv["top_in_sample"]}
        print("\nleave-one-world-out (H, theta, win) of the hold rule:")
        for w, (k, m, n) in cv["picks"].items():
            print(f"  held-out {w}: picked {k} -> {m:+7.0f} on its {n} games")
        print(f"  LOWO mean over games {cv['lowo_mean']:+.0f}, world-weighted {cv['lowo_world_weighted']:+.0f};"
              f" top in-sample {cv['top_in_sample'][:4]}")
    if "--mech" in argv:
        mech = mechanism(PGs)
        out["mechanism"] = mech
        print("\nmechanism of hold_best over our games:", json.dumps(mech, default=str))
    if "--json" in argv:
        Path(argv[argv.index("--json") + 1]).write_text(json.dumps(out, default=str, indent=1))
    print(f"{time.time() - t0:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1:])
