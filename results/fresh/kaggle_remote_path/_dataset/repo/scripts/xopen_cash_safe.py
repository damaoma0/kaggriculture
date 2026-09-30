"""xopen: the CASH-SAFE DATE D (stored data only, no games). Thread xopen, 2026-09-25.

D = the first day after which reinvestment is never cash-constrained. Measured on
  (1) the leader corpus data/leader_semantics (540 games, 6 teams), with the documented one-day offset of
      market.* / animals.bought / hires_arrived corrected (index i holds day i+1; index 0 holds days 0 AND 1),
  (2) OUR cash paths: G1 ledgers results/fresh/lead_ledger/{leader,ours,deploy}_<ep>.json (12 leader worlds,
      correctly dated), and the deploy's world traces in the 12 p2750 smoke worlds (lead_world_trace, several
      builds, each world with its own recorded 2750+ opponent),
  (3) our revenue by day in the 185 p2750 worlds (results/fresh/ladder_panel/mgt_lpv_tievalff, cumulative
      revenue_daily snapshots) against the day-0 exemplar's recorded revenue.

Per day t: C[t] = cash at day start, V[t] = revenue, R[t] = reinvestment = seeds + animals + wheat / fertilizer
bought + wages (fib per hire) + land. Identity C[t+1] = C[t] + V[t] - R[t] is checked for every game.
Criteria for a candidate d0 (all later days t in d0..28):
  cov(m)      C[t] >= (1+m) R[t]                     (the day's plan is funded by the morning's cash)
  grow        C[t+1] >= C[t]                         (cash grows faster than spend)
  stress(h,m) B[t] >= (1+m) R[t], B[d0] = C[d0], B[t+1] = B[t] + (1-h) V[t] - R[t]
              (the rest of the plan stays funded from the morning cash even if every later coin of revenue is
              only (1-h) of the recorded one: our prices / volumes below the leader's)
  self(Dmax,m) C[d0] >= (1+m) * sum R[d0..Dmax]        (cash alone covers the remaining plan to Dmax)

usage: .venv/Scripts/python.exe scripts/xopen_cash_safe.py
writes results/fresh/xopen_20260925/cash_safe.json and cash_safe.txt
"""
import glob
import gzip
import json
import os
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/xopen_20260925"
SEM = ROOT / "data/leader_semantics"
LEDGER = ROOT / "results/fresh/lead_ledger"
WTR = ROOT / "results/fresh/kaggle_remote_lead"
PANEL = ROOT / "results/fresh/ladder_panel/mgt_lpv_tievalff"
EXEMPLAR = ("16732748", 112655730)
LAND = [1000, 2000, 4000]
ANIMALS = {"SHEEP", "COW", "GOOSE"}
CROPS = {"WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"}
LAST = 28          # conditions checked through day 28 (day 29 = liquidation, no reinvestment that matters)
LINES = []


def say(s=""):
    LINES.append(s)
    print(s)


def fibsum(n):
    a, b, s = 1, 1, 0
    for _ in range(n):
        s += a
        a, b = b, a + b
    return s


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))
    return xs[k]


# ------------------------------------------------------------------------------------------------ corpus
def sem_flows(d):
    """-> dict(C, V, R, parts, ident_err) per corrected day 0..29. Days 0 and 1 cannot be split (index 0 holds
    both); they are reported as one block on day 1 (V[0] = R[0] = 0 placeholder, C[1] is the recorded value)."""
    days = d["days"]
    n = len(days)
    C = [float(x["cash_start"]) for x in days]
    seat = d["meta"]["seat"]
    final = float(d["meta"]["final_cash"][seat])
    L = [x["board"].count(" L") if isinstance(x["board"], str) else sum(1 for v in x["board"] if v == " L")
         for x in days]
    land = [0.0] * n
    bought_q = 0
    for t in range(n - 1):
        k = (L[t] - L[t + 1]) // 25
        for _ in range(max(0, k)):
            land[t] += LAND[min(bought_q, 2)]
            bought_q += 1
    wages = [float(fibsum(int(x["labour"]["hands_present"]))) for x in days]
    V = [0.0] * n
    parts = [Counter() for _ in range(n)]

    def mk(i):
        m = days[i]["market"]
        v = float(sum(m["sold_revenue"].values()))
        p = Counter()
        for k, s in m["bought_spend"].items():
            if k in ANIMALS:
                p["animals"] += s
            elif k == "WHEAT" and "WHEAT" in m["bought_units"] and k not in CROPS - {"WHEAT"}:
                # BUY_PRODUCT WHEAT and BUY_SEED WHEAT share the key "WHEAT"; split by unit price (seed 10)
                u = m["bought_units"]["WHEAT"]
                if u and s / u > 12:
                    p["wheat"] += s
                else:
                    p["seeds"] += s
            elif k == "FERTILIZER":
                p["fert"] += s
            else:
                p["seeds"] += s
        return v, p

    # corrected: day t (t >= 2) = index t-1; days 0+1 = index 0 (put on day 1)
    for t in range(2, n):
        V[t], parts[t] = mk(t - 1)
    V[1], parts[1] = mk(0)
    parts[1]["wages"] = wages[0] + wages[1]
    parts[1]["land"] = land[0] + land[1]
    for t in range(2, n):
        parts[t]["wages"] = wages[t]
        parts[t]["land"] = land[t]
    R = [float(sum(p.values())) for p in parts]
    # identity: C[2] = C[0] + V01 - R01 ; C[t+1] = C[t] + V[t] - R[t]; final = C[29] + V[29] - R[29]
    err = abs(C[2] - (C[0] + V[1] - R[1]))
    for t in range(2, n - 1):
        err = max(err, abs(C[t + 1] - (C[t] + V[t] - R[t])))
    # day 29: hands_present is 0 in the corpus (captured after the final step), so its wages are unknown;
    # put the residual on day 29's reinvestment (it equals the day-29 wages in the ledger-checked games)
    resid = (C[n - 1] + V[n - 1] - R[n - 1]) - final
    if resid > 0:
        parts[n - 1]["wages"] += resid
        R[n - 1] += resid
    Cn = C + [final]
    return dict(C=Cn, V=V, R=R, parts=parts, err=err)


def first_day(ok, lo=2, hi=LAST):
    """first d0 in lo..hi with ok(t) for every t in d0..hi (None if none)."""
    best = None
    for d0 in range(hi, lo - 1, -1):
        if ok(d0):
            best = d0
        else:
            break
    return best


def criteria(F, m=0.25, hs=(0.3, 0.5), dmax=14, lo=2):
    C, V, R = F["C"], F["V"], F["R"]
    out = {}
    cov = lambda t, mm: C[t] >= (1 + mm) * R[t]
    grow = lambda t: C[t + 1] >= C[t]
    for mm in (0.0, m, 1.0):
        out["cov_%g" % mm] = first_day(lambda t: cov(t, mm), lo)
    out["cov+grow"] = first_day(lambda t: cov(t, m) and grow(t), lo)

    def stress_ok(d0, h):
        B = C[d0]
        for t in range(d0, LAST + 1):
            if B < (1 + m) * R[t]:
                return False
            B += (1 - h) * V[t] - R[t]
        return True
    for h in hs + (1.0,):
        # smallest d0 from which the stressed path holds (not a suffix property: check each d0)
        out["stress_%g" % h] = next((d0 for d0 in range(lo, LAST + 1) if stress_ok(d0, h)), None)
    out["self_%d" % dmax] = next((d0 for d0 in range(lo, dmax + 1)
                                  if C[d0] >= (1 + m) * sum(R[d0:dmax + 1])), None)
    # last day the morning cash does not cover the day's reinvestment (the last bound day)
    bound = [t for t in range(lo, LAST + 1) if C[t] < R[t]]
    out["last_bound"] = max(bound) if bound else None
    return out


def dist_line(name, xs, width=34):
    got = [x for x in xs if x is not None]
    none = len(xs) - len(got)
    if not got:
        return "%-*s n=%3d  none reach it" % (width, name, len(xs))
    c = Counter(got)
    hist = " ".join("%d:%d" % (k, c[k]) for k in sorted(c))
    return "%-*s n=%3d  median %4.1f  p10 %2d  p90 %2d  max %2d  never %d | %s" % (
        width, name, len(xs), st.median(got), pct(got, 0.1), pct(got, 0.9), max(got), none, hist)


def corpus():
    say("== 1. LEADER CORPUS (data/leader_semantics, offset-corrected; days 0-1 are one block)")
    rows = []
    bad = 0
    for f in sorted(glob.glob(str(SEM / "*" / "*.json.gz"))):
        d = json.load(gzip.open(f, "rt", encoding="utf-8"))
        F = sem_flows(d)
        if F["err"] > 1.5:
            bad += 1
        team = d["meta"]["team"]
        rows.append(dict(team=team, team_id=os.path.basename(os.path.dirname(f)), ep=d["meta"]["episode"],
                         F=F, crit=criteria(F)))
    say("games %d, cash identity C[t+1] = C[t] + V - R fails (> 1.5 coins) in %d" % (len(rows), bad))
    keys = list(rows[0]["crit"])
    teams = sorted({r["team"] for r in rows})
    say("\nDistribution of D per criterion (m = 0.25 unless named; day index = first day of the safe suffix):")
    for k in keys:
        say(dist_line(k, [r["crit"][k] for r in rows]))
    say("\nPer team, median (p90) of cov+grow / stress_0.3 / stress_0.5 / last_bound:")
    for tm in teams:
        rr = [r for r in rows if r["team"] == tm]
        def mp(k):
            xs = [r["crit"][k] for r in rr if r["crit"][k] is not None]
            nn = sum(1 for r in rr if r["crit"][k] is None)
            return "%4.1f (%2s)%s" % (st.median(xs), pct(xs, 0.9), (" never %d" % nn) if nn else "") if xs else "none"
        say("  %-24s n=%3d  %s | %s | %s | %s" % (tm, len(rr), mp("cov+grow"), mp("stress_0.3"), mp("stress_0.5"),
                                                  mp("last_bound")))
    # cash profile by day
    say("\nLeader cash at day start / reinvestment that day / revenue that day (medians over 540; day 1 = days 0+1):")
    say("  day  " + " ".join("%6d" % t for t in range(1, 17)))
    for lab, key in (("C", "C"), ("R", "R"), ("V", "V")):
        say("  %-4s " % lab + " ".join("%6.0f" % st.median([r["F"][key][t] for r in rows]) for t in range(1, 17)))
    say("  C/R  " + " ".join("%6.2f" % st.median([r["F"]["C"][t] / max(1.0, r["F"]["R"][t]) for r in rows])
                              for t in range(1, 17)))
    say("  bound" + " ".join("%6.0f%%" % (100.0 * sum(1 for r in rows if r["F"]["C"][t] < r["F"]["R"][t]) / len(rows))
                            for t in range(1, 17)))
    # reinvestment composition by day (share of the season's reinvestment spent by day t)
    tot = [sum(r["F"]["R"][1:30]) for r in rows]
    say("  cum% " + " ".join("%6.0f%%" % (100 * st.median([sum(r["F"]["R"][1:t + 1]) / tt for r, tt in zip(rows, tot)]))
                             for t in range(1, 17)))
    for part in ("seeds", "animals", "land", "wheat", "fert", "wages"):
        say("  %-6s" % part[:6] + " ".join("%6.0f" % st.mean([r["F"]["parts"][t][part] for r in rows]) for t in range(1, 17)))
    return rows


# ------------------------------------------------------------------------------------------------ ours
def ledger_flows(x):
    days = x["days"]
    C = [float(d["cash"]) for d in days] + [float(x["final"])]
    V = [float(sum(d["rev"].values())) for d in days]
    R = [float(sum(d["spend"].values())) + float(d["wages"]) + float(d["land"]) for d in days]
    err = max(abs(C[t + 1] - (C[t] + V[t] - R[t])) for t in range(len(days)))
    fails = [int(sum(d["failed"].values())) for d in days]
    return dict(C=C, V=V, R=R, err=err, fails=fails)


def wtr_flows(x):
    days = x["days"]
    C = [float(d["cash0"]) for d in days] + [float(x["final"])]
    V = [float(sum(d["rev"].values())) for d in days]
    R = [C[t] + V[t] - C[t + 1] for t in range(len(days))]          # market spend + wages + land (by identity)
    mk = [float(sum(d["spend"].values())) for d in days]
    fails = [int(sum(d["failed"].values())) for d in days]
    return dict(C=C, V=V, R=R, err=0.0, fails=fails, mk=mk, rv=[float(sum(d["rrev"].values())) for d in days])


def ours(corpus_rows):
    say("\n== 2. OUR CASH PATHS")
    lead = {}
    res = {"g1": {}, "smoke": {}}
    for side in ("leader", "ours", "deploy"):
        for f in sorted(LEDGER.glob("%s_*.json" % side)):
            x = json.loads(f.read_text(encoding="utf-8"))
            F = ledger_flows(x)
            ep = int(x["episode"])
            if side == "leader":
                lead[ep] = F
            res["g1"].setdefault(side, {})[ep] = F
    say("G1 ledgers (12 leader worlds; ours = T = mgt_lead.py defaults at ledger time, deploy = mgt_lead_deploy E2):")
    say("  identity error max: " + ", ".join("%s %.1f" % (s, max(F["err"] for F in res["g1"][s].values())) for s in res["g1"]))
    for side in ("leader", "ours", "deploy"):
        rows = list(res["g1"][side].values())
        say("  %-6s " % side + " ".join("%6.0f" % st.median([F["C"][t] for F in rows]) for t in range(0, 17)) + "   (median cash, days 0-16)")
    for side in ("ours", "deploy"):
        say("  %-6s " % (side[:4] + "/L") + " ".join("%6.2f" % st.median([res["g1"][side][e]["C"][t] / max(1.0, lead[e]["C"][t])
                                                                        for e in lead]) for t in range(0, 17)) + "   (median cash / leader cash)")
    for side in ("ours", "deploy"):
        say("  %-6s " % (side[:4] + " V/L") + " ".join("%6.2f" % (sum(res["g1"][side][e]["V"][t] for e in lead) /
                                                                 max(1.0, sum(lead[e]["V"][t] for e in lead))) for t in range(0, 17)) + "   (pooled revenue / leader revenue)")
    for side in ("leader", "ours", "deploy"):
        say("  %-6s " % (side[:4] + " fail") + " ".join("%6.2f" % st.mean([res["g1"][side][e]["fails"][t] for e in lead]) for t in range(0, 17)) + "   (failed buy orders / game)")
    say("\n  D per criterion on OUR OWN flows (own C, own V, own R), G1:")
    for side in ("leader", "ours", "deploy"):
        crit = [criteria(F, lo=1) for F in res["g1"][side].values()]
        for k in ("cov_0.25", "cov+grow", "stress_0.3", "stress_0.5", "last_bound"):
            say("    " + dist_line("%s %s" % (side, k), [c[k] for c in crit], 26))
    # smoke world traces
    builds = defaultdict(dict)
    for f in glob.glob(str(WTR / "wtr*" / "output" / "*" / "out" / "repo" / "results" / "fresh" / "lead_world_trace" / "*.json")):
        b, e = os.path.basename(f)[:-5].rsplit("_", 1)
        builds[b][int(e)] = f
    keep = [b for b in sorted(builds) if len(builds[b]) == 12]
    say("\nSmoke new worlds (lead_world_trace; 12 p2750 worlds, each with its own recorded 2750+ opponent); builds: %s" % ", ".join(keep))
    main = ["mgt_lpv_dep7", "mgt_lpv_dep8", "mgt_lpv_tw0", "mgt_lpv_cf1", "mgt_lpv_ws2", "mgt_lpv_rs1", "mgt_lpv_mpt0"]
    main = [b for b in main if b in keep]
    for b in main:
        FF = {e: wtr_flows(json.load(open(p))) for e, p in builds[b].items()}
        res["smoke"][b] = FF
    ex = [r for r in corpus_rows if (r["team_id"], r["ep"]) == EXEMPLAR][0]["F"]
    for b in main:
        FF = res["smoke"][b]
        say("  %-13s C " % b[8:] + " ".join("%6.0f" % st.median([F["C"][t] for F in FF.values()]) for t in range(0, 17)))
    say("  exemplar      C " + " ".join("%6.0f" % ex["C"][t] for t in range(0, 17)) + "   (recorded, its own world)")
    for b in main[:2]:
        FF = res["smoke"][b]
        say("  %-13s V " % b[8:] + " ".join("%6.0f" % st.median([F["V"][t] for F in FF.values()]) for t in range(0, 17)))
    say("  exemplar      V " + " ".join("%6.0f" % ex["V"][t] for t in range(0, 17)) + "   (day 1 = days 0+1)")
    for b in main[:2]:
        FF = res["smoke"][b]
        say("  %-13s R " % b[8:] + " ".join("%6.0f" % st.median([F["R"][t] for F in FF.values()]) for t in range(0, 17)))
        say("  %-13s f " % b[8:] + " ".join("%6.2f" % st.mean([F["fails"][t] for F in FF.values()]) for t in range(0, 17)) + "   (failed buys / game)")
    say("  exemplar      R " + " ".join("%6.0f" % ex["R"][t] for t in range(0, 17)))
    say("\n  D per criterion on OUR OWN flows, smoke worlds (pooled over the listed builds, 12 worlds each):")
    for k in ("cov_0.25", "cov+grow", "stress_0.3", "stress_0.5", "last_bound"):
        xs = [criteria(F, lo=1)[k] for b in main for F in res["smoke"][b].values()]
        say("    " + dist_line("deploy builds %s" % k, xs, 26))
    for b in main[:2]:
        for k in ("cov+grow", "stress_0.3", "last_bound"):
            say("    " + dist_line("%s %s" % (b[8:], k), [criteria(F, lo=1)[k] for F in res["smoke"][b].values()], 26))
    return res, lead, ex


# ------------------------------------------------------------------------------------------------ dynamic rule
def dynamic(corpus_rows, res, lead, ex, m=0.25, dmin=6):
    """hand off on the first day t >= dmin at which OUR morning cash covers (1+m) x the followed plan's remaining
    reinvestment through Dmax (plan = the recorded game we follow: the leader's own game in G1, the exemplar in
    new worlds). Reports the handoff day per Dmax and how often it falls on / before the leader's own D."""
    say("\n== 3. DYNAMIC RULE: first t >= %d with our cash C(t) >= %.2f x sum of the plan's R[t..Dmax]" % (dmin, 1 + m))

    def rule(C, Rp, dmax):
        for t in range(dmin, dmax + 1):
            if C[t] >= (1 + m) * sum(Rp[t:dmax + 1]):
                return t
        return None
    # leader on its own plan (corpus); our side: T and deploy in G1 against the leader's plan (identical plan),
    # deploy builds in smoke worlds against the exemplar's plan (the plan the exact follower would carry).
    for dmax in (11, 12, 14):
        say("  Dmax = %d" % dmax)
        say("    " + dist_line("leaders (own plan, corpus)", [rule(r["F"]["C"], r["F"]["R"], dmax) for r in corpus_rows], 30))
        for side in ("leader", "ours", "deploy"):
            xs = [rule(res["g1"][side][e]["C"], lead[e]["R"], dmax) for e in lead]
            say("    " + dist_line("G1 %s vs leader plan" % side, xs, 30))
        for b in list(res["smoke"])[:3]:
            xs = [rule(F["C"], ex["R"], dmax) for F in res["smoke"][b].values()]
            say("    " + dist_line("smoke %s vs exemplar" % b[8:], xs, 30))

    # 3b: the stressed rule on OUR live numbers: at hour 0 of day t (t >= dmin), starting from our cash C(t), the
    # followed plan's days t..dmax stay funded each morning when the plan's revenue is cut by h = max(h_min, our
    # measured shortfall vs the plan over days 1..t-1): B = C(t); for s in t..dmax: B >= (1+m) Rp[s]; B += (1-h) Vp[s] - Rp[s]
    def srule(C, V, Vp, Rp, dmax, h_min=0.3):
        for t in range(dmin, dmax + 1):
            got, exp_ = sum(V[1:t]), sum(Vp[1:t])
            h = max(h_min, 1.0 - got / max(1.0, exp_))
            B, ok = C[t], True
            for s in range(t, dmax + 1):
                if B < (1 + m) * Rp[s]:
                    ok = False
                    break
                B += (1 - h) * Vp[s] - Rp[s]
            if ok:
                return t
        return None
    say("\n== 3b. STRESSED DYNAMIC RULE (own cash, plan revenue cut by max(0.3, our measured shortfall), days t..Dmax)")
    for dmax in (12, 14):
        say("  Dmax = %d" % dmax)
        say("    " + dist_line("leaders (own plan, corpus)", [srule(r["F"]["C"], r["F"]["V"], r["F"]["V"], r["F"]["R"], dmax) for r in corpus_rows], 30))
        for side in ("leader", "ours", "deploy"):
            xs = [srule(res["g1"][side][e]["C"], res["g1"][side][e]["V"], lead[e]["V"], lead[e]["R"], dmax) for e in lead]
            say("    " + dist_line("G1 %s vs leader plan" % side, xs, 30))
        for b in list(res["smoke"])[:3]:
            xs = [srule(F["C"], [0.0, F["V"][0] + F["V"][1]] + F["V"][2:], ex["V"], ex["R"], dmax) for F in res["smoke"][b].values()]
            say("    " + dist_line("smoke %s vs exemplar" % b[8:], xs, 30))


def panel_revenue(ex):
    say("\n== 4. OUR REVENUE BY DAY IN THE 185 p2750 WORLDS (mgt_lpv_tievalff = current default) vs the exemplar's recorded")
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in PANEL.glob("*.json")]
    rows = [r for r in rows if r.get("revenue_daily")]
    say("  worlds with revenue_daily: %d" % len(rows))

    def daily(cum, t):
        a = cum[min(t + 1, len(cum) - 1)]
        b = cum[min(t, len(cum) - 1)]
        return sum(a.values()) - sum(b.values())
    say("  day      " + " ".join("%6d" % t for t in range(0, 16)))
    ours = [[daily(r["revenue_daily"], t) for t in range(0, 16)] for r in rows]
    riv = [[daily(r["rival_revenue_daily"], t) for t in range(0, 16)] for r in rows]
    say("  ours p50 " + " ".join("%6.0f" % st.median([o[t] for o in ours]) for t in range(0, 16)))
    say("  ours p10 " + " ".join("%6.0f" % pct([o[t] for o in ours], 0.1) for t in range(0, 16)))
    say("  ours p90 " + " ".join("%6.0f" % pct([o[t] for o in ours], 0.9) for t in range(0, 16)))
    say("  rival p50" + " ".join("%6.0f" % st.median([o[t] for o in riv]) for t in range(0, 16)))
    exv = [0.0] + list(ex["V"][1:16])
    say("  exemplar " + " ".join("%6.0f" % v for v in exv) + "   (day 1 = its days 0+1)")
    # revenue days 0-2 (the part of the opening the deploy plays from the exemplar before retrieval)
    o02 = [sum(o[0:3]) for o in ours]
    e02 = ex["V"][1] + ex["V"][2]
    say("  revenue days 0-2: ours median %.0f (p10 %.0f, p90 %.0f) vs exemplar %.0f -> ratio median %.2f (p10 %.2f)" % (
        st.median(o02), pct(o02, 0.1), pct(o02, 0.9), e02, st.median(o02) / e02, pct(o02, 0.1) / e02))
    o311 = [sum(o[3:12]) for o in ours]
    e311 = sum(ex["V"][3:12])
    say("  revenue days 3-11: ours median %.0f (p10 %.0f, p90 %.0f) vs exemplar %.0f -> ratio median %.2f (p10 %.2f)" % (
        st.median(o311), pct(o311, 0.1), pct(o311, 0.9), e311, st.median(o311) / e311, pct(o311, 0.1) / e311))
    return dict(n=len(rows), rev02=o02, rev311=o311, ex02=e02, ex311=e311)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = corpus()
    res, lead, ex = ours(rows)
    dynamic(rows, res, lead, ex)
    pr = panel_revenue(ex)
    blob = dict(
        corpus=[dict(team=r["team"], team_id=r["team_id"], ep=r["ep"], crit=r["crit"],
                     C=r["F"]["C"], V=r["F"]["V"], R=r["F"]["R"],
                     parts=[dict(p) for p in r["F"]["parts"]]) for r in rows],
        g1={s: {str(e): dict(C=F["C"], V=F["V"], R=F["R"], fails=F["fails"]) for e, F in v.items()} for s, v in res["g1"].items()},
        smoke={b: {str(e): dict(C=F["C"], V=F["V"], R=F["R"], fails=F["fails"]) for e, F in v.items()} for b, v in res["smoke"].items()},
        panel=dict(n=pr["n"], rev02=pr["rev02"], rev311=pr["rev311"], ex02=pr["ex02"], ex311=pr["ex311"]))
    (OUT / "cash_safe.json").write_text(json.dumps(blob), encoding="utf-8")
    (OUT / "cash_safe.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
