"""xopen report (thread xopen, 2026-09-25): stored results only, one process, no games.

  e1   leader worlds (results/fresh/xopen_20260925/g1/<arm>/<ep>.json, lead_ledger records): E0 checks, gap to the
       leader per arm with paired CIs vs T, the by-window production table (plantings / harvested units / revenue /
       cumulative revenue gap) for LEADER vs T vs the exact-opening arms, and the three-reason split of
       results/fresh/t_gap_20260925/deep_decomp.py (analyse() imported unchanged) for each arm against the leader
  e2   new worlds (results/fresh/xopen_20260925/e2/<agent>/<ep>.json): margin vs the paired baseline (t and bootstrap
       CIs), own / rival, and the xopen logs (breakages, repairs, cuts, handoff, cash / animals / plantings by day)

usage: xopen_report.py e1 [--dir results/fresh/xopen_20260925/g1] [--arms LEADER,T,X5,X8,X11,Xdyn] [--out e1.txt]
       xopen_report.py e2 [--base mgt_lpv_xo0] [--arms mgt_lpv_xopen,...] [--out e2.txt]
"""
import gzip
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTD = ROOT / 'results/fresh/xopen_20260925'
sys.path.insert(0, str(ROOT / 'results/fresh/t_gap_20260925'))
sys.path.insert(0, str(ROOT / 'scripts'))
WINDOWS = [(0, 5), (6, 8), (9, 11), (12, 14), (15, 17), (18, 20), (21, 23), (24, 26), (27, 29)]
CLEAN9 = {112444381, 112445586, 112447950, 112449129, 112655730, 112661570, 112667461, 112714050, 112721923}
LINES = []
SET = 'all'
CLEANV = {}


def say(s=''):
    LINES.append(s)
    print(s)


def tci(xs):
    from scipy import stats
    n = len(xs)
    m = sum(xs) / n if n else float('nan')
    if n < 2:
        return m, m, m
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    return m, m - h, m + h


def bci(xs, n=10000, seed=7):
    rng = random.Random(seed)
    k = len(xs)
    if not k:
        return float('nan'), float('nan')
    ms = sorted(sum(rng.choices(xs, k=k)) / k for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n)]


def fmt(xs, w=7):
    m, lo, hi = tci(xs)
    blo, bhi = bci(xs)
    return f'{m:+{w},.0f} (t {lo:+,.0f}..{hi:+,.0f}; boot {blo:+,.0f}..{bhi:+,.0f})'


# ================================================================================================= E1
def load_g1(d, arms):
    rows = defaultdict(dict)
    for arm in arms:
        for f in sorted((d / arm).glob('*.json')):
            r = json.loads(f.read_text(encoding='utf-8'))
            rows[arm][int(r['episode'])] = r
    return rows


def team_of(r):
    return str(r['game']).split(':')[0]


def four_q(r):
    team, ep = str(r['game']).split(':')
    g = json.load(gzip.open(ROOT / f'data/leader_semantics/{team}/{ep}.json.gz', 'rt', encoding='utf-8'))
    b = ''.join(g['days'][-1]['board'])
    return [b[i:i + 2] for i in range(0, len(b), 2)].count(' L') == 0


def wsum(r, key, a, b):
    return sum(sum((r['days'][d].get(key) or {}).values()) for d in range(a, b + 1))


def e1(argv):
    d = OUTD / 'g1'
    arms = ['LEADER', 'T', 'X5', 'X8', 'X11', 'Xdyn']
    out = OUTD / 'e1_report.txt'
    i = 0
    while i < len(argv):
        if argv[i] == '--dir':
            d = ROOT / argv[i + 1]; i += 2
        elif argv[i] == '--arms':
            arms = argv[i + 1].split(','); i += 2
        elif argv[i] == '--out':
            out = OUTD / argv[i + 1]; i += 2
        elif argv[i] == '--set':
            global SET
            SET = argv[i + 1]; i += 2
        else:
            i += 1
    extra = [a for a in ('X30', 'ORIG', 'F11') if (d / a).exists()]
    R = load_g1(d, arms + extra)
    L = R['LEADER']
    eps = sorted(set.intersection(*[set(R[a]) for a in arms if R[a]]))
    if SET == 'g1':
        import lead_g1
        eps = [e for e in eps if any(g.endswith(str(e)) for g in lead_g1.GAMES)]
    elif SET == 'sem4':
        w = json.loads((ROOT / 'results/fresh/lead_sem4_20260925/worlds.json').read_text(encoding='utf-8'))['worlds']
        keep = {int(x['episode']) for x in w}
        eps = [e for e in eps if e in keep]
    clean = [e for e in eps if all(R[a][e]['opp_final'] >= 0.8 * R[a][e]['target_opp'] for a in arms if R[a] and e in R[a])]
    say(f'E1 leader worlds ({SET}): {len(eps)} worlds with every arm {arms}; clean (no replayed opponent below 0.8x '
        f'its recorded cash in any arm): {len(clean)}')
    # ---- E0
    say('\n== E0 controls')
    for e, r in sorted(R.get('X30', {}).items()):
        say(f'  X30 (replay all game) {e}: final {r["final"]:,.0f} vs recorded {r["target"]:,.0f} -> {"OK" if abs(r["final"] - r["target"]) < 0.5 else "MISMATCH"}')
    for e, r in sorted(L.items()):
        if abs(r['final'] - r['target']) >= 0.5:
            say(f'  LEADER replay {e}: MISMATCH {r["final"]} vs {r["target"]}')
    say(f'  LEADER replay reproduces the recorded cash: {sum(1 for r in L.values() if abs(r["final"] - r["target"]) < 0.5)}/{len(L)}')
    for e, r in sorted(R.get('ORIG', {}).items()):
        t = R['T'].get(e)
        if t:
            same = abs(r['final'] - t['final']) < 0.5 and all(a.get('cash') == b.get('cash') for a, b in zip(r['days'], t['days']))
            say(f'  ORIG (frozen mgt_lead.py) {e}: {r["final"]:,.0f} vs T (xopen_day -1) {t["final"]:,.0f}, every day-start cash equal: {same} -> {"OK" if same else "MISMATCH"}')
    for e, r in sorted(R.get('F11', {}).items()):
        t = R['X11'].get(e)
        if t:
            say(f'  F11 (follow mode) {e}: {r["final"]:,.0f} vs X11 (replay) {t["final"]:,.0f} -> {"identical" if abs(r["final"] - t["final"]) < 0.5 else "DIFF"}')
    # ---- gap table
    say('\n== Final cash: gap to the leader (leader - arm; positive = behind) and paired vs T (arm - T), per game')
    say('| arm | n | mean final | gap to leader | ratio mean12 / mean11 / clean9 | vs T (arm - T) | better/worse vs T | handoff day |')
    say('|---|---:|---:|---|---|---|---|---|')
    for a in arms:
        if not R[a]:
            continue
        es = [e for e in eps if e in R[a]]
        gap = [L[e]['final'] - R[a][e]['final'] for e in es]
        rat = [R[a][e]['final'] / L[e]['target'] for e in es]
        r12 = sum(rat) / len(rat)
        r11 = [x for e, x in zip(es, rat) if e != 112708229]
        rc = [x for e, x in zip(es, rat) if e in CLEAN9]
        vs = [R[a][e]['final'] - R['T'][e]['final'] for e in es if e in R['T']]
        vsc = [R[a][e]['final'] - R['T'][e]['final'] for e in es if e in R['T'] and e in clean]
        CLEANV[a] = vsc
        bw = f"{sum(1 for x in vs if x > 0)}/{sum(1 for x in vs if x < 0)}"
        hd = Counter((R[a][e].get('xo') or {}).get('D') for e in es)
        hd_s = ' '.join(f'{k}:{v}' for k, v in sorted(hd.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)) if k is not None) or '-'
        say(f'| {a} | {len(es)} | {sum(R[a][e]["final"] for e in es) / len(es):,.0f} | {fmt(gap)} | '
            f'{r12:.3f} / {sum(r11) / max(1, len(r11)):.3f} / {sum(rc) / max(1, len(rc)):.3f} | '
            f'{fmt(vs) if a != "T" and a != "LEADER" else "-"} | {bw if a not in ("T", "LEADER") else "-"} | {hd_s} |')
    say(f'\n  paired vs T on the clean worlds (n={len(clean)}): ' + '; '.join(
        f"{a} {fmt(v)} better {sum(1 for x in v if x > 0)}/{len(v)}" for a, v in CLEANV.items() if a not in ('T', 'LEADER') and v))
    if SET == 'g1':
        c9 = [e for e in eps if e in CLEAN9]
        say('  paired vs T on the G1 convention clean9: ' + '; '.join(
            f"{a} {fmt([R[a][e]['final'] - R['T'][e]['final'] for e in c9])} better {sum(1 for e in c9 if R[a][e]['final'] > R['T'][e]['final'])}/{len(c9)}"
            for a in arms if a not in ('T', 'LEADER') and R[a]))
    # ---- opponent collapse check
    say('\n  replayed opponent final / recorded (min over worlds; < 0.8 = collapse, inflates our ratio): ' +
        ', '.join(f"{a} {min(R[a][e]['opp_final'] / max(1.0, R[a][e]['target_opp']) for e in eps):.2f}" for a in arms if R[a]))
    # ---- windows
    say('\n== By day window, mean per game: plantings | harvested units | revenue | cumulative revenue gap to the leader (end of window)')
    hdr = '| window | ' + ' | '.join(f'{a} plant / harv / rev / cum gap' for a in arms if R[a]) + ' |'
    say(hdr)
    say('|---|' + '---|' * len([a for a in arms if R[a]]))
    cum = {a: 0.0 for a in arms}
    for (lo, hi) in WINDOWS:
        cells = []
        for a in arms:
            if not R[a]:
                continue
            pl = sum(wsum(R[a][e], 'plant', lo, hi) for e in eps) / len(eps)
            hv = sum(wsum(R[a][e], 'harv', lo, hi) for e in eps) / len(eps)
            rv = sum(wsum(R[a][e], 'rev', lo, hi) for e in eps) / len(eps)
            lv = sum(wsum(L[e], 'rev', lo, hi) for e in eps) / len(eps)
            cum[a] += lv - rv
            cells.append(f'{pl:.1f} / {hv:.0f} / {rv:,.0f} / {cum[a]:+,.0f}')
        say(f'| d{lo}-{hi} | ' + ' | '.join(cells) + ' |')
    # post-handoff revenue gap (windows after the handoff) with CIs
    say('\n== Revenue gap to the leader by window with 95% CI (leader - arm, per game), and the change vs T (T gap - arm gap)')
    for a in arms:
        if a == 'LEADER' or not R[a]:
            continue
        parts = []
        for (lo, hi) in WINDOWS:
            g = [wsum(L[e], 'rev', lo, hi) - wsum(R[a][e], 'rev', lo, hi) for e in eps]
            m, l_, h_ = tci(g)
            parts.append(f'd{lo}-{hi} {m:+,.0f} ({l_:+,.0f}..{h_:+,.0f})')
        say(f'  {a}: ' + '; '.join(parts))
    for a in arms:
        if a in ('LEADER', 'T') or not R[a]:
            continue
        g_post = [sum(wsum(L[e], 'rev', lo, hi) - wsum(R[a][e], 'rev', lo, hi) for lo, hi in WINDOWS if lo >= 12) for e in eps]
        t_post = [sum(wsum(L[e], 'rev', lo, hi) - wsum(R['T'][e], 'rev', lo, hi) for lo, hi in WINDOWS if lo >= 12) for e in eps]
        say(f'  revenue gap days 12-29: {a} {fmt(g_post)} | T {fmt(t_post)} | share of T\'s day 12-29 gap left: '
            f'{sum(g_post) / max(1.0, sum(t_post)):.2f}')
        h_post = [sum(wsum(L[e], 'harv', lo, hi) - wsum(R[a][e], 'harv', lo, hi) for lo, hi in WINDOWS if lo >= 12) for e in eps]
        ht_post = [sum(wsum(L[e], 'harv', lo, hi) - wsum(R['T'][e], 'harv', lo, hi) for lo, hi in WINDOWS if lo >= 12) for e in eps]
        say(f'  harvested units gap days 12-29: {a} {fmt(h_post, 5)} | T {fmt(ht_post, 5)}')
    # ---- cash by day
    say('\n== Cash at day start / leader (mean over worlds), days 0-15')
    for a in arms:
        if not R[a]:
            continue
        vals = []
        for dd in range(16):
            xs = [R[a][e]['days'][dd]['cash'] / max(1.0, L[e]['days'][dd]['cash']) for e in eps if L[e]['days'][dd]['cash']]
            vals.append(f'{sum(xs) / len(xs):.2f}' if xs else '-')
        say(f'  {a:6s} ' + ' '.join(vals))
    # ---- first day after the handoff
    say('\n== First day after the handoff (T takes over): failed buys, PASS unit-steps, plantings, hires vs the leader that day')
    for a in arms:
        if a in ('LEADER', 'T') or not R[a]:
            continue
        fb = pa = plo = pll = hi_o = hi_l = 0
        n = 0
        for e in eps:
            D = (R[a][e].get('xo') or {}).get('D')
            if D is None or D > 29:
                continue
            n += 1
            do, dl = R[a][e]['days'][D], L[e]['days'][D]
            fb += sum(do['failed'].values())
            pa += do['passes'] - dl['passes']
            plo += sum(do['plant'].values())
            pll += sum(dl['plant'].values())
            hi_o += len(do['hires'])
            hi_l += len(dl['hires'])
        if n:
            say(f'  {a}: {n} games; failed buys {fb / n:.1f}, extra PASS unit-steps vs leader {pa / n:+.1f}, plantings {plo / n:.1f} vs '
                f'leader {pll / n:.1f}, hires {hi_o / n:.1f} vs {hi_l / n:.1f}')
    # ---- three reasons (deep_decomp.analyse, unchanged) per arm vs the leader
    try:
        import deep_decomp as DD
    except Exception as exc:
        say(f'\n(deep_decomp not importable: {exc})')
        return
    say('\n== THREE REASONS (results/fresh/t_gap_20260925/deep_decomp.py analyse(), unchanged): gap = 1 + 2 + 3, per game, 95% t-CI')
    four = {e: four_q(L[e]) for e in eps}
    lines_by_arm = {}
    for a in arms:
        if a == 'LEADER' or not R[a]:
            continue
        rows = []
        for e in eps:
            g = dict(ep=str(e), team=team_of(L[e]), four=four[e], L=L[e], O=R[a][e])
            try:
                rows.append(DD.analyse(g))
            except AssertionError as exc:
                say(f'  {a} {e}: analyse assertion {exc}')
        lines_by_arm[a] = rows
    keys = [('gap', 'CASH GAP'), ('PRODUCTION', '1. LESS PRODUCTION'), ('P_plant_window', '   crops: missed / later plantings in T\'s window'),
            ('P_plant_cutoff', '   crops: leader plantings after T\'s cutoff'), ('crop_care', '   crops: care (deaths + decay + units/harvest)'),
            ('P_fert_applied', '   crops: fertilizer spread instead of sold'), ('anim_n', '   animals: fewer + later placed'),
            ('animal_care', '   animals: care (escapes + output + collection)'), ('P_fert_animaldays', '   fertilizer: fewer animal-days'),
            ('inp', '   inputs (seeds/animals, wheat/fert purchase, wheat fed)'), ('P_discards', '   midnight shed-cap discards'),
            ('P_later_supply', '   units available later'), ('P_market_depth', '   market depth'),
            ('LABOUR_COST', '2. MORE LABOUR COST (wages)'), ('SALE_TIMING', '3. BAD SALE TIMING'),
            ('P_gross_A', 'memo: A = production at leader price')]
    arms_d = [a for a in arms if a in lines_by_arm]
    say(f"  {'':52s} " + ' '.join(f'{a:>30s}' for a in arms_d))
    for k, nm in keys:
        cells = []
        for a in arms_d:
            vals = []
            for r in lines_by_arm[a]:
                ln = dict(r['lines'], gap=r['gap'])
                ln['anim_n'] = ln['P_animals'] + ln['P_animal_dates']
                ln['inp'] = ln['P_seed_animal_land'] + ln['P_wheat_fert_purchase'] + ln['P_wheat_fed']
                vals.append(ln[k])
            m, lo, hi = tci(vals)
            cells.append(f'{m:+8,.0f} ({lo:+,.0f}..{hi:+,.0f})')
        say(f'  {nm:52s} ' + ' '.join(f'{c:>30s}' for c in cells))
    # animals placed and plantings (engine-rule reconstruction of deep_decomp)
    say('\n== Animals: placed per game and mean placement day (leader / arm), from the day-start boards')
    for a in arms_d:
        parts = []
        for sp in ('GOOSE', 'COW', 'SHEEP'):
            nl = sum(r['anim'][sp]['agg']['L']['N'] for r in lines_by_arm[a]) / len(lines_by_arm[a])
            no = sum(r['anim'][sp]['agg']['O']['N'] for r in lines_by_arm[a]) / len(lines_by_arm[a])
            pl_ = [r['anim'][sp]['agg']['L']['mean_p'] for r in lines_by_arm[a] if r['anim'][sp]['agg']['L']['mean_p'] is not None]
            po_ = [r['anim'][sp]['agg']['O']['mean_p'] for r in lines_by_arm[a] if r['anim'][sp]['agg']['O']['mean_p'] is not None]
            parts.append(f'{sp} {nl:.1f}/{no:.1f} day {sum(pl_) / max(1, len(pl_)):.1f}/{sum(po_) / max(1, len(po_)):.1f}')
        say(f'  {a}: ' + '; '.join(parts))
    say('\n== Crop plantings per game (leader / arm)')
    for a in arms_d:
        parts = []
        for c in ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON'):
            nl = sum(r['crop'][c]['agg']['L']['n'] for r in lines_by_arm[a]) / len(lines_by_arm[a])
            no = sum(r['crop'][c]['agg']['O']['n'] for r in lines_by_arm[a]) / len(lines_by_arm[a])
            hl = sum(r['crop'][c]['agg']['L']['h'] for r in lines_by_arm[a]) / len(lines_by_arm[a])
            ho = sum(r['crop'][c]['agg']['O']['h'] for r in lines_by_arm[a]) / len(lines_by_arm[a])
            parts.append(f'{c[:5]} {nl:.1f}/{no:.1f} (harv {hl:.0f}/{ho:.0f})')
        say(f'  {a}: ' + '; '.join(parts))
    out.write_text('\n'.join(LINES) + '\n', encoding='utf-8')
    json.dump({a: [dict(ep=r['ep'], gap=r['gap'], lines=r['lines']) for r in rows] for a, rows in lines_by_arm.items()},
              open(OUTD / f'e1_deep_per_game_{SET}.json', 'w'), indent=1, default=str)


# ================================================================================================= E2
def load_e2(name):
    rows = {}
    for f in sorted((OUTD / 'e2' / name).glob('*.json')):
        r = json.loads(f.read_text(encoding='utf-8'))
        rows[int(r['episode'])] = r
    return rows


def e2(argv):
    base, arms, out = 'mgt_lpv_xo0', ['mgt_lpv_xopen_off', 'mgt_lpv_xopen', 'mgt_lpv_xopen_d11', 'mgt_lpv_xopen_naive'], OUTD / 'e2_report.txt'
    i = 0
    while i < len(argv):
        if argv[i] == '--base':
            base = argv[i + 1]; i += 2
        elif argv[i] == '--arms':
            arms = argv[i + 1].split(','); i += 2
        elif argv[i] == '--out':
            out = OUTD / argv[i + 1]; i += 2
        else:
            i += 1
    B = load_e2(base)
    say(f'E2 new worlds: baseline {base} ({len(B)} worlds)')
    say('| arm | n | mean margin | vs baseline (arm - base) | better/worse/same | own vs base | rival vs base | opp tape broken |')
    say('|---|---:|---:|---|---|---:|---:|---:|')
    A = {a: load_e2(a) for a in arms}
    for a in arms:
        es = sorted(set(A[a]) & set(B))
        if not es:
            continue
        d = [A[a][e]['margin'] - B[e]['margin'] for e in es]
        own = sum(A[a][e]['final'] - B[e]['final'] for e in es) / len(es)
        riv = sum(A[a][e]['rival'] - B[e]['rival'] for e in es) / len(es)
        broken = sum(1 for e in es if A[a][e]['opp_dead'] - B[e]['opp_dead'] > 40)
        bw = f"{sum(1 for x in d if x > 0.5)}/{sum(1 for x in d if x < -0.5)}/{sum(1 for x in d if abs(x) <= 0.5)}"
        say(f'| {a} | {len(es)} | {sum(A[a][e]["margin"] for e in es) / len(es):,.0f} | {fmt(d)} | {bw} | {own:+,.0f} | {riv:+,.0f} | {broken} |')
    for a in arms:
        rows = A[a]
        if not rows or not any(r.get('xo') for r in rows.values()):
            continue
        say(f'\n== {a}: xopen logs (per game means unless stated)')
        n = len(rows)
        hd = Counter((r['xo'] or {}).get('D') for r in rows.values())
        rs = Counter((r['xo'] or {}).get('D_reason') for r in rows.values())
        say(f'  handoff day: {dict(sorted(hd.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)))}; reasons {dict(rs)}')
        errs = [(e, r['xo'].get('errors')) for e, r in rows.items() if (r.get('xo') or {}).get('errors')]
        say(f'  games with follower errors: {len(errs)} {errs[:3]}')
        picks = Counter(json.dumps([p.get("key") for p in (r["xo"].get("plans") or [])]) for r in rows.values())
        say(f'  plans followed (day 0 [, day-6 re-pick, day-9]): {dict(picks)}')
        cnt = Counter()
        byday = defaultdict(Counter)
        for r in rows.values():
            cnt.update(r['xo'].get('counts') or {})
            for dd, c in (r['xo'].get('by_day') or {}).items():
                byday[int(dd)].update(c)
        say('  event counts per game: ' + ', '.join(f'{k} {v / n:.1f}' for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])[:40]))
        say('  breakages by day and cause (per game):')
        for dd in sorted(byday):
            c = {k: v for k, v in byday[dd].items() if k.startswith('breakage')}
            if c:
                say(f'    d{dd}: ' + ', '.join(f'{k[9:]} {v / n:.1f}' for k, v in sorted(c.items(), key=lambda kv: -kv[1])))
        say('  repairs by day (per game): ' + '; '.join(
            f"d{dd}: " + ', '.join(f'{k[7:]} {v / n:.1f}' for k, v in sorted(byday[dd].items()) if k.startswith('repair:'))
            for dd in sorted(byday) if any(k.startswith('repair:') for k in byday[dd])))
        cuts = [c for r in rows.values() for c in (r['xo'].get('cuts') or [])]
        say(f'  failsafe cuts: {len(cuts) / n:.1f} per game; deferred {sum(1 for c in cuts if c["action"] == "defer") / n:.1f}, '
            f'cancelled {sum(1 for c in cuts if c["action"] == "cancel") / n:.1f}')
        byitem = defaultdict(list)
        for c in cuts:
            byitem[(c['item'], c['action'])].append(c)
        for (it, act), cs in sorted(byitem.items(), key=lambda kv: -len(kv[1]))[:15]:
            evs = [c['ev_loss'] for c in cs if c.get('ev_loss') is not None]
            rat = [c['ratio'] for c in cs if c.get('ratio') is not None]
            days = Counter(c['day'] for c in cs)
            say(f'    {it:18s} {act:7s} {len(cs) / n:5.1f}/game, coins {sum(c["coins"] for c in cs) / n:7.0f}/game, '
                f'EV lost {sum(evs) / max(1, len(evs)):6.1f}, EV/coin {sum(rat) / max(1, len(rat)):.4f}, days {dict(sorted(days.items()))}')
        dbd = defaultdict(float)
        for r in rows.values():
            for dd, v in (r['xo'].get('deferred_by_day') or {}).items():
                dbd[int(dd)] += v / n
        say('  coins deferred (max queue) by day: ' + ' '.join(f'd{dd}:{v:.0f}' for dd, v in sorted(dbd.items())))
        for key, lab in (('cash_by_day', 'cash at day start'), ('plan_cash_by_day', "the recording's cash")):
            vals = []
            for dd in range(16):
                xs = [float((r['xo'].get(key) or {}).get(str(dd))) for r in rows.values() if (r['xo'].get(key) or {}).get(str(dd)) is not None]
                vals.append(f'{sum(xs) / len(xs):,.0f}' if xs else '-')
            say(f'  {lab:22s} d0-15: ' + ' '.join(vals))
        base_cash = []
        for dd in range(16):
            xs = [B[e]['xo'].get('cash_by_day', {}).get(str(dd)) for e in rows if e in B and (B[e].get('xo') or {}).get('cash_by_day')]
            xs = [float(x) for x in xs if x is not None]
            base_cash.append(f'{sum(xs) / len(xs):,.0f}' if xs else '-')
        say(f"  {'baseline cash':22s} d0-15: " + ' '.join(base_cash))
        pl = defaultdict(Counter)
        an = defaultdict(Counter)
        for r in rows.values():
            for dd, c in (r['xo'].get('plants_by_day') or {}).items():
                pl[int(dd)].update(c)
            for dd, c in (r['xo'].get('placed_by_day') or {}).items():
                an[int(dd)].update(c)
        say('  plantings by day (per game): ' + ' '.join(f'd{dd}:{sum(pl[dd].values()) / n:.1f}' for dd in sorted(pl) if dd <= 15))
        say('  animals placed by day (per game): ' + ' '.join(f'd{dd}:' + '/'.join(f'{an[dd].get(s, 0) / n:.1f}' for s in ('GOOSE', 'COW', 'SHEEP'))
                                                        for dd in sorted(an) if dd <= 15) + '  (goose/cow/sheep)')
        ham = defaultdict(list)
        for r in rows.values():
            for dd, v in (r['xo'].get('ham_by_day') or {}).items():
                ham[int(dd)].append(v)
        say('  Hamming to the followed recording at day start: ' + ' '.join(f'd{dd}:{sum(v) / len(v):.1f}' for dd, v in sorted(ham.items())))
        tm = [r['xo'].get('tmax', 0) for r in rows.values()]
        say(f"  follower max s/step {max(tm):.3f}; deploy max s/step {max((r.get('dep_tmax') or 0) for r in rows.values()):.3f}")
    out.write_text('\n'.join(LINES) + '\n', encoding='utf-8')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'e2':
        e2(sys.argv[2:])
    else:
        e1(sys.argv[2:] if len(sys.argv) > 1 else [])
