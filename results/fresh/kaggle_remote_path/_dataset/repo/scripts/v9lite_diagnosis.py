"""V9-lite diagnosis: what the V9 reveal-day search layer adds on top of y3's tape+Yarn build, and where the LIVE
combined submission actually loses.

FRAMING (user correction, 2026-09-24): the live ladder submission 56525017 ("mgt_v9lite_y3_iofix") is ONE build --
V9-lite's reveal-day search running on top of y3's tape router and late-Yarn layer. There is no separate live "y3"
agent to play against it. Every "V9-lite vs y3" or "vs m1" number below is a PANEL measurement (recorded/frozen
opponents, our builds replayed offline) of what one layer adds on top of another -- never a live head-to-head.

Four builds share the same tape-router chassis and only add layers:
  mgt_m1            tape router alone (sell_lead + hire guard + strand rule), no late-Yarn layer, no V9 search
  mgt_y3            m1 + y3's late-Yarn layer (yarn_service, yarn_gate, rescue_pin), no V9 search
  mgt_v9litem1pkg   m1 + V9 reveal-day search (day 12/15/18 tape-switch), no late-Yarn layer
  mgt_v9litepkg3    m1 + late-Yarn layer + V9 search = combined; policy-equivalent to live submission 56525017
                     (56525017 = mgt_v9lite_y3_iofix, an output-capture-only rebuild of the same archive; see
                     docs/tape_release_20260924.md and submissions/2026-09-24-v9lite-iofix-01a0/PROVENANCE.md)

Component decomposition datasets (offline, recorded/frozen opponents unless noted):
  A. 2750-3000 exact panel, data/ladder_panel/p2750/ (185 games; same recorded world+opponent replayed under each
     build). m1, y3: results/fresh/kaggle_remote_y2/p2750eval/output/*/out/<agent>/<ep>.json.
     v9litem1pkg, v9litepkg3: results/fresh/ladder_panel/<agent>/<ep>.json.
  B. Live V56 (responsive opponent), results/fresh/newphase_20260923/y3/v56_paired{,_b}/games/<agent>-<seed>-<seat>.json
     (120 games per build: 40 + 80).
  C. 180 ladder worlds (coverage_worlds.json): m1, y3 from results/fresh/kaggle_remote_y2/y3verify/output/*/out/;
     v9litepkg3 from results/fresh/ladder_panel/. No v9litem1pkg-alone leg was run on this set (3-way only).
  D. mgt_v9lite_diag (72 worlds where the diag build, = y3+V9 with switch-day telemetry, differs from native y3):
     results/fresh/ladder_panel/mgt_v9lite_diag/*.json -- gives switch day (overlay 'v9_route_dNN') and y3's Yarn
     counters (sheep_lost, orphan_days, yarn_service, topup_tasks) per world, already computed
     (scripts/v9_strand_interaction.py, results/fresh/newphase_20260923/v9_strand_interaction.json).

LIVE combined-build loss analysis (new replay this run):
  1. scripts/ladder_panel_fetch.py 56525017 -> data/ladder_panel/56525017/<ep>.json.gz (79 completed ladder games).
  2. Losses (recorded margin < 0): 17 of 79.
  3. scripts/ladder_panel.py run mgt_v9lite_diag,mgt_y3,mgt_v9litepkg3 56525017 <17 episodes> (LP_WORKERS=1, shared
     laptop, >=3 GB free checked first) -> results/fresh/ladder_panel/{mgt_v9lite_diag,mgt_y3,mgt_v9litepkg3}/<ep>.json.
     mgt_v9lite_diag is functionally the live build with switch-day telemetry added (see agents/mgt_v9lite_diag.py);
     mgt_y3 replayed on the SAME recorded world is the no-V9-switch counterfactual.
  4. Validity: mgt_v9lite_diag's replay must reproduce the recorded (final, rival) to the dollar for each loss --
     the harness's own validity check (scripts/ladder_panel.py's convention), checked here explicitly.
  5. Per loss: did a V9 switch fire (v9_route_dNN in overlay) and on which reveal day; would the no-switch
     counterfactual (native mgt_y3, same world) have scored better; are y3's Yarn counters (sheep_lost, orphan_days,
     yarn_service) different between the diag build and native y3 in that world (yarn layer implicated).

Usage: .venv/Scripts/python.exe scripts/v9lite_diagnosis.py
Outputs: results/fresh/v9lite_diagnosis/{decomposition.json, live_losses.json, ladder_tracking.json, report.md}
"""
import glob
import gzip
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/v9lite_diagnosis'
PANEL = ROOT / 'results/fresh/ladder_panel'
P2750 = ROOT / 'data/ladder_panel/p2750'
Y3VERIFY = ROOT / 'results/fresh/kaggle_remote_y2/y3verify/output'
P2750EVAL = ROOT / 'results/fresh/kaggle_remote_y2/p2750eval/output'
V56A = ROOT / 'results/fresh/newphase_20260923/y3/v56_paired/games'
V56B = ROOT / 'results/fresh/newphase_20260923/y3/v56_paired_b/games'


def jload(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def ci(xs, n=10000, seed=7):
    if not xs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    k = len(xs)
    m = sorted(sum(rng.choices(xs, k=k)) / k for _ in range(n))
    return m[int(0.025 * n)], m[int(0.975 * n)]


# ---------------------------------------------------------------- loaders

def load_p2750_style(agent, root):
    """m1/y3 (root=P2750EVAL or Y3VERIFY): results/*/out/<agent>/*.json. v9lite*/v9litepkg3 (root=PANEL): <agent>/*.json"""
    out = {}
    if root in (P2750EVAL, Y3VERIFY):
        pat = str(root / '*' / 'out' / agent / '*.json')
    else:
        pat = str(root / agent / '*.json')
    for f in glob.glob(pat):
        d = jload(f)
        out[int(d['episode'])] = d
    return out


def load_v56(agent):
    out = {}
    for d in (V56A, V56B):
        for f in d.glob(f'{agent}-*.json'):
            r = jload(f)
            out[(r['seed'], r['seat'])] = r
    return out


# ---------------------------------------------------------------- decomposition

def rev_dict_p2750(row, rival=False):
    return row.get('rival_revenue' if rival else 'revenue', {})


def rev_dict_v56(row, rival=False):
    return row['daily'][1 if rival else 0][-1]['revenue']


def decompose(keys, M1, Y3, V9M1, COMB, margin_of, cash_of, rcash_of, rev_of, label, opp_dead_filter=None,
              skip_rival_revenue=False):
    """keys: iterable of episode ints or (seed,seat) tuples present (after filtering) in all four dicts."""
    rows = []
    for k in keys:
        if opp_dead_filter and opp_dead_filter(k):
            continue
        m1, y3, v9m1, comb = M1[k], Y3[k], V9M1[k], COMB[k]
        rows.append(dict(
            key=str(k),
            m1=margin_of(m1), y3=margin_of(y3), v9m1=margin_of(v9m1), comb=margin_of(comb),
            y3_minus_m1=margin_of(y3) - margin_of(m1),
            v9m1_minus_m1=margin_of(v9m1) - margin_of(m1),
            comb_minus_m1=margin_of(comb) - margin_of(m1),
            comb_minus_y3=margin_of(comb) - margin_of(y3),
            own_cash_comb_minus_y3=cash_of(comb) - cash_of(y3),
            rival_cash_comb_minus_y3=rcash_of(comb) - rcash_of(y3),
        ))
    n = len(rows)
    if n == 0:
        return dict(label=label, n=0)

    def agg(key):
        xs = [r[key] for r in rows]
        lo, hi = ci(xs)
        return dict(mean=statistics.mean(xs), sum=sum(xs), lo=lo, hi=hi,
                    better=sum(1 for x in xs if x > 0), worse=sum(1 for x in xs if x < 0),
                    same=sum(1 for x in xs if x == 0))

    gain = sorted(rows, key=lambda r: -r['comb_minus_y3'])
    total_gain = sum(r['comb_minus_y3'] for r in rows)
    total_pos = sum(r['comb_minus_y3'] for r in rows if r['comb_minus_y3'] > 0) or 1e-9
    top5 = sum(r['comb_minus_y3'] for r in gain[:5])
    top10 = sum(r['comb_minus_y3'] for r in gain[:10])

    # product revenue deltas: combined vs y3, own and (if the data source has itemized rival revenue) rival.
    # NOTE: the p2750eval schema (m1/y3) has no itemized rival_revenue, only a rival CASH total ('rival'); computing
    # a "delta" against an always-empty dict would silently sum the combined side's raw totals, not a delta, so
    # skip_rival_revenue=True suppresses that for datasets where either side lacks the itemized field.
    own_rev_delta, rival_rev_delta = {}, {}
    any_rival_data = False
    for k in keys:
        if opp_dead_filter and opp_dead_filter(k):
            continue
        comb, y3 = COMB[k], Y3[k]
        for prod, v in rev_of(comb, False).items():
            own_rev_delta[prod] = own_rev_delta.get(prod, 0) + v - rev_of(y3, False).get(prod, 0)
        for prod in rev_of(y3, False):
            if prod not in rev_of(comb, False):
                own_rev_delta[prod] = own_rev_delta.get(prod, 0) - rev_of(y3, False)[prod]
        if skip_rival_revenue:
            continue
        rc, ry = rev_of(comb, True), rev_of(y3, True)
        if rc or ry:
            any_rival_data = True
        for prod, v in rc.items():
            rival_rev_delta[prod] = rival_rev_delta.get(prod, 0) + v - ry.get(prod, 0)
        for prod in ry:
            if prod not in rc:
                rival_rev_delta[prod] = rival_rev_delta.get(prod, 0) - ry[prod]
    if skip_rival_revenue or not any_rival_data:
        rival_rev_delta = None

    return dict(
        label=label, n=n,
        y3_minus_m1=agg('y3_minus_m1'), v9m1_minus_m1=agg('v9m1_minus_m1'),
        comb_minus_m1=agg('comb_minus_m1'), comb_minus_y3=agg('comb_minus_y3'),
        own_cash_comb_minus_y3=agg('own_cash_comb_minus_y3'), rival_cash_comb_minus_y3=agg('rival_cash_comb_minus_y3'),
        concentration=dict(total_gain=total_gain, total_positive=total_pos,
                            top5_of_total=top5, top5_share_of_total=top5 / total_gain if total_gain else None,
                            top5_share_of_positive=top5 / total_pos,
                            top10_of_total=top10, top10_share_of_total=top10 / total_gain if total_gain else None,
                            top10_share_of_positive=top10 / total_pos),
        worst5=[{'key': r['key'], 'comb_minus_y3': r['comb_minus_y3']} for r in gain[-5:]],
        best5=[{'key': r['key'], 'comb_minus_y3': r['comb_minus_y3']} for r in gain[:5]],
        own_revenue_delta_comb_minus_y3=dict(sorted(own_rev_delta.items(), key=lambda x: -abs(x[1]))),
        rival_revenue_delta_comb_minus_y3=(dict(sorted(rival_rev_delta.items(), key=lambda x: -abs(x[1])))
                                            if rival_rev_delta is not None else None),
    )


def part_p2750():
    m1 = load_p2750_style('mgt_m1', P2750EVAL)
    y3 = load_p2750_style('mgt_y3', P2750EVAL)
    v9m1 = load_p2750_style('mgt_v9litem1pkg', PANEL)
    comb = load_p2750_style('mgt_v9litepkg3', PANEL)
    keys = sorted(set(m1) & set(y3) & set(v9m1) & set(comb))

    def opp_dead_bad(k):
        vals = [m1[k].get('opp_dead', 0), y3[k].get('opp_dead', 0), v9m1[k].get('opp_dead', 0), comb[k].get('opp_dead', 0)]
        return max(vals) - min(vals) > 40

    d = decompose(keys, m1, y3, v9m1, comb,
                  lambda r: r['margin'], lambda r: r['final'], lambda r: r['rival'],
                  rev_dict_p2750, 'p2750 (185-game exact panel, own+team-vs-team)', opp_dead_bad,
                  skip_rival_revenue=True)
    # source split (own_ladder vs team_vs_team)
    idx = jload(P2750 / 'index.json')['games']
    by_src = {}
    for k in keys:
        if opp_dead_bad(k):
            continue
        src = idx.get(str(k), {}).get('source', 'unknown')
        by_src.setdefault(src, []).append(comb[k]['margin'] - y3[k]['margin'])
    d['by_source_comb_minus_y3'] = {s: dict(n=len(v), mean=statistics.mean(v), sum=sum(v)) for s, v in by_src.items()}
    d['note'] = 'm1/y3 (p2750eval schema) have no itemized rival_revenue, only a rival cash total; rival product deltas suppressed here'
    return d


def part_v56():
    m1 = load_v56('mgt_m1')
    y3 = load_v56('mgt_y3')
    v9m1 = load_v56('mgt_v9litem1pkg')
    comb = load_v56('mgt_v9litepkg3')
    keys = sorted(set(m1) & set(y3) & set(v9m1) & set(comb))
    return decompose(keys, m1, y3, v9m1, comb,
                      lambda r: r['margin'], lambda r: r['cash'], lambda r: r['opponent_cash'],
                      rev_dict_v56, 'live V56 paired (120 games/build: v56_paired 40 + v56_paired_b 80)')


def part_180():
    """3-way only: m1, y3, combined (no v9litem1pkg-alone leg was run on this set). The y3verify pipeline ran
    'mgt_m1_rebuild2' (a verified rebuild of mgt_m1, same policy) rather than mgt_m1 itself on this 180-world set."""
    m1 = load_p2750_style('mgt_m1_rebuild2', Y3VERIFY)
    y3 = load_p2750_style('mgt_y3', Y3VERIFY)
    comb = load_p2750_style('mgt_v9litepkg3', PANEL)
    cov = set(int(x) for x in json.loads((ROOT / 'results/fresh/newphase_20260923/coverage_worlds.json').read_text(encoding='utf-8')))
    keys = sorted(set(m1) & set(y3) & set(comb) & cov)

    def opp_dead_bad(k):
        vals = [m1[k].get('opp_dead', 0), y3[k].get('opp_dead', 0), comb[k].get('opp_dead', 0)]
        return max(vals) - min(vals) > 40
    rows = []
    for k in keys:
        if opp_dead_bad(k):
            continue
        rows.append(dict(key=k, y3_minus_m1=y3[k]['margin'] - m1[k]['margin'],
                          comb_minus_m1=comb[k]['margin'] - m1[k]['margin'],
                          comb_minus_y3=comb[k]['margin'] - y3[k]['margin']))
    n = len(rows)
    if not n:
        return dict(label='180 ladder worlds (3-way: m1/y3/combined)', n=0)

    def agg(key):
        xs = [r[key] for r in rows]
        lo, hi = ci(xs)
        return dict(mean=statistics.mean(xs), sum=sum(xs), lo=lo, hi=hi,
                    better=sum(1 for x in xs if x > 0), worse=sum(1 for x in xs if x < 0), same=sum(1 for x in xs if x == 0))
    gain = sorted(rows, key=lambda r: -r['comb_minus_y3'])
    total_gain = sum(r['comb_minus_y3'] for r in rows)
    return dict(label='180 ladder worlds (3-way: m1/y3/combined; no v9litem1pkg-alone leg run here)', n=n,
                y3_minus_m1=agg('y3_minus_m1'), comb_minus_m1=agg('comb_minus_m1'), comb_minus_y3=agg('comb_minus_y3'),
                concentration=dict(total_gain=total_gain,
                                    top5_share_of_total=sum(r['comb_minus_y3'] for r in gain[:5]) / total_gain if total_gain else None,
                                    top10_share_of_total=sum(r['comb_minus_y3'] for r in gain[:10]) / total_gain if total_gain else None),
                worst5=[{'key': r['key'], 'comb_minus_y3': r['comb_minus_y3']} for r in gain[-5:]],
                best5=[{'key': r['key'], 'comb_minus_y3': r['comb_minus_y3']} for r in gain[:5]])


def part_switchday():
    """Switch-day / product breakdown of the V9 search layer's gain over y3, from the 72-world diag set
    (results/fresh/ladder_panel/mgt_v9lite_diag/: worlds where the diag build, = y3+V9 telemetry, differs from
    native y3 on the SAME recorded p2750/coverage world -- so every difference here traces to a V9 switch)."""
    diag = load_p2750_style('mgt_v9lite_diag', PANEL)
    y3_all = {**load_p2750_style('mgt_y3', Y3VERIFY), **load_p2750_style('mgt_y3', P2750EVAL)}
    rows = []
    for ep, d in diag.items():
        if ep not in y3_all:
            continue
        y3r = y3_all[ep]
        switch_days = sorted(int(kk.split('_d')[1]) for kk in d.get('overlay', {}) if kk.startswith('v9_route_d'))
        rows.append(dict(ep=ep, switch_days=switch_days, d_margin=d['margin'] - y3r['margin'],
                          d_own_cash=d['final'] - y3r['final'], d_rival_cash=d['rival'] - y3r['rival'],
                          d_wool=d.get('sold', {}).get('WOOL', 0) - y3r.get('sold', {}).get('WOOL', 0),
                          d_milk=d.get('sold', {}).get('MILK', 0) - y3r.get('sold', {}).get('MILK', 0),
                          d_strawberry=d.get('sold', {}).get('STRAWBERRY', 0) - y3r.get('sold', {}).get('STRAWBERRY', 0)))
    n = len(rows)
    by_day = {}
    for r in rows:
        key = ','.join(str(x) for x in r['switch_days']) if r['switch_days'] else 'none'
        by_day.setdefault(key, []).append(r['d_margin'])
    gain = sorted(rows, key=lambda r: -r['d_margin'])
    total = sum(r['d_margin'] for r in rows) or 1e-9
    return dict(n=n, mean_margin=statistics.mean(r['d_margin'] for r in rows) if rows else None,
                by_switch_day={k: dict(n=len(v), mean=statistics.mean(v), sum=sum(v)) for k, v in sorted(by_day.items())},
                top5_share_of_total=sum(r['d_margin'] for r in gain[:5]) / total,
                top10_share_of_total=sum(r['d_margin'] for r in gain[:10]) / total,
                own_wool_delta=sum(r['d_wool'] for r in rows), own_milk_delta=sum(r['d_milk'] for r in rows),
                own_strawberry_delta=sum(r['d_strawberry'] for r in rows),
                worst5=[{'ep': r['ep'], 'd_margin': r['d_margin'], 'switch_days': r['switch_days']} for r in gain[-5:]],
                best5=[{'ep': r['ep'], 'd_margin': r['d_margin'], 'switch_days': r['switch_days']} for r in gain[:5]])


# ---------------------------------------------------------------- live losses

LOSS_EPISODES = [112977769, 112977788, 112967455, 112957860, 112996502, 112969589, 112981251, 112983557,
                  112974276, 112967296, 112990676, 112952353, 112962570, 112998531, 112936031, 112979068, 112964929]


def world_of(ep):
    p = ROOT / f'data/ladder_panel/56525017/{ep}.json.gz'
    return json.loads(gzip.open(p, 'rt', encoding='utf-8').read())


def part_live_losses():
    diag = load_p2750_style('mgt_v9lite_diag', PANEL)
    y3 = load_p2750_style('mgt_y3', PANEL)
    comb = load_p2750_style('mgt_v9litepkg3', PANEL)
    rows = []
    for ep in LOSS_EPISODES:
        w = world_of(ep)
        recorded_margin = w['rewards'][w['seat']] - w['rewards'][1 - w['seat']]
        d = diag.get(ep)
        y = y3.get(ep)
        c = comb.get(ep)
        if d is None or y is None:
            rows.append(dict(ep=ep, recorded_margin=recorded_margin, status='not replayed'))
            continue
        dollar_match = round(d['final']) == round(d['recorded'][0]) and round(d['rival']) == round(d['recorded'][1])
        switch_days = sorted(int(k.split('_d')[1]) for k in d.get('overlay', {}) if k.startswith('v9_route_d'))
        switch_routes = {k: v - 1 for k, v in d.get('overlay', {}).items() if k.startswith('v9_route_d')}
        shops = w['shops']
        yarn_days = [dd for dd in range(1, len(shops)) if shops[dd].count('YARN_STORE') > shops[dd - 1].count('YARN_STORE')]
        late_yarn_after_switch = [sd for sd in switch_days if any(y_ <= sd + 3 for y_ in yarn_days if y_ >= sd)]
        rows.append(dict(
            ep=ep, opponent=(w.get('opponent') or {}).get('team'), recorded_margin=recorded_margin,
            diag_margin=d['margin'], diag_dollar_match=dollar_match,
            y3_noswitch_margin=y['margin'],
            v9litepkg3_margin=(c['margin'] if c else None),
            package_matches_diag=(round(c['margin']) == round(d['margin']) if c else None),
            switch_fired=bool(switch_days), switch_days=switch_days, switch_routes=switch_routes,
            noswitch_wouldve_beaten_actual=(y['margin'] > d['margin']),
            margin_lost_to_switch=(d['margin'] - y['margin']),
            yarn_days_revealed=yarn_days,
            switch_near_late_yarn_reveal=bool(late_yarn_after_switch),
            diag_own_cash=d['final'], y3_own_cash=y['final'],
            diag_rival_cash=d['rival'], y3_rival_cash=y['rival'],
            diag_overlay={k: v for k, v in d.get('overlay', {}).items() if not k.startswith('v9_route_d')},
            y3_overlay={k: v for k, v in y.get('overlay', {}).items()},
            sheep_lost_diag=d.get('overlay', {}).get('sheep_lost', 0), sheep_lost_y3=y.get('overlay', {}).get('sheep_lost', 0),
            orphan_days_diag=d.get('overlay', {}).get('orphan_days', 0), orphan_days_y3=y.get('overlay', {}).get('orphan_days', 0),
            yarn_service_diag=d.get('overlay', {}).get('yarn_service', 0), yarn_service_y3=y.get('overlay', {}).get('yarn_service', 0),
            status='ok',
        ))
    return rows


# ---------------------------------------------------------------- ladder tracking

def part_ladder():
    out = {}
    for name, args in (('track_submission', ['56525017', '56395605']),
                        ('rating_trend', ['56525017', '56395605', '--window', '40'])):
        p = subprocess.run([sys.executable, str(ROOT / f'scripts/{name}.py')] + args,
                            cwd=str(ROOT), capture_output=True, text=True, timeout=180)
        out[name] = dict(returncode=p.returncode, stdout=p.stdout, stderr=p.stderr[-2000:])
    return out


# ---------------------------------------------------------------- report

def fmt_agg(a, label):
    return f"{label}: mean {a['mean']:+,.0f} (95% CI {a['lo']:+,.0f}..{a['hi']:+,.0f}), sum {a['sum']:+,.0f}, " \
           f"better/worse/same {a['better']}/{a['worse']}/{a['same']}"


def write_report(dec_p2750, dec_v56, dec_180, switchday, losses, ladder):
    lines = []
    lines.append('# V9-lite diagnosis (2026-09-24)\n')
    lines.append('Framing: 56525017 is ONE live build (V9-lite search on top of y3 on top of m1). All "vs y3"/"vs m1"\n'
                  'numbers below are PANEL measurements of what one layer adds, not live head-to-heads.\n')

    def dec_section(d, title):
        if d.get('n', 0) == 0:
            lines.append(f'## {title}\nno paired episodes\n')
            return
        lines.append(f'## {title} (n={d["n"]})\n')
        lines.append('- ' + fmt_agg(d['y3_minus_m1'], 'y3 - m1 (Yarn layer alone)'))
        if 'v9m1_minus_m1' in d:
            lines.append('- ' + fmt_agg(d['v9m1_minus_m1'], 'v9litem1pkg - m1 (V9 search alone)'))
        lines.append('- ' + fmt_agg(d['comb_minus_m1'], 'combined - m1 (total)'))
        lines.append('- ' + fmt_agg(d['comb_minus_y3'], 'combined - y3 (what V9 search adds on top of y3)'))
        if 'own_cash_comb_minus_y3' in d:
            lines.append('- ' + fmt_agg(d['own_cash_comb_minus_y3'], 'own cash, combined - y3'))
            lines.append('- ' + fmt_agg(d['rival_cash_comb_minus_y3'], 'rival cash, combined - y3'))
        c = d.get('concentration', {})
        if c and c.get('top5_share_of_positive') is not None:
            tot_lbl = f"{c['top5_share_of_total']:.0%}" if c.get('top5_share_of_total') is not None else 'n/a'
            lines.append(f"- concentration of (combined - y3): top5 = {tot_lbl} of net total gain, "
                          f"{c['top5_share_of_positive']:.0%} of the sum of positive deltas; "
                          f"top10 = {c['top10_share_of_positive']:.0%} of the sum of positive deltas")
        if d.get('own_revenue_delta_comb_minus_y3'):
            top = list(d['own_revenue_delta_comb_minus_y3'].items())[:6]
            lines.append(f"- own revenue delta (combined-y3), top products: {top}")
        if d.get('rival_revenue_delta_comb_minus_y3'):
            top = list(d['rival_revenue_delta_comb_minus_y3'].items())[:6]
            lines.append(f"- rival revenue delta (combined-y3), top products: {top}")
        if d.get('note'):
            lines.append(f"- note: {d['note']}")
        if d.get('by_source_comb_minus_y3'):
            lines.append(f"- by source: {d['by_source_comb_minus_y3']}")
        lines.append(f"- worst5: {d.get('worst5')}")
        lines.append(f"- best5: {d.get('best5')}\n")

    dec_section(dec_p2750, 'A. 2750-3000 exact panel (185 games)')
    dec_section(dec_v56, 'B. Live V56 paired (120 games/build)')
    dec_section(dec_180, 'C. 180 ladder worlds (3-way)')

    lines.append('## D. Switch-day / product breakdown of the V9 layer\'s gain over y3 (72-world diag set)\n')
    lines.append(f"n={switchday['n']}  mean margin delta {switchday['mean_margin']:+,.0f}\n")
    lines.append(f"by switch day: {switchday['by_switch_day']}\n")
    lines.append(f"top5 share of total gain: {switchday['top5_share_of_total']:.0%}; top10: {switchday['top10_share_of_total']:.0%}\n")
    lines.append(f"own units delta: wool {switchday['own_wool_delta']:+d}  milk {switchday['own_milk_delta']:+d}  "
                 f"strawberry {switchday['own_strawberry_delta']:+d}\n")
    lines.append(f"worst5: {switchday['worst5']}\n")
    lines.append(f"best5: {switchday['best5']}\n")

    lines.append('\n## E. LIVE combined build (56525017) losing ladder games (17 of 79 completed)\n')
    ok = [r for r in losses if r['status'] == 'ok']
    lines.append(f"replayed: {len(ok)}/{len(losses)}; dollar-exact match to recorded result: "
                 f"{sum(1 for r in ok if r['diag_dollar_match'])}/{len(ok)}\n")
    switched = [r for r in ok if r['switch_fired']]
    noswitched = [r for r in ok if not r['switch_fired']]
    lines.append(f"a V9 switch fired in {len(switched)}/{len(ok)} losses; no switch fired in {len(noswitched)}/{len(ok)}\n")
    beat = [r for r in switched if r['noswitch_wouldve_beaten_actual']]
    lines.append(f"of the {len(switched)} losses where a switch fired, the no-switch counterfactual (native y3, same "
                 f"recorded world) would have scored better in {len(beat)}\n")
    lines.append('\n| ep | opp | recorded margin | diag margin | y3-noswitch margin | switch? | day(s) | y3 better w/o switch | sheep_lost d/y3 | orphan_days d/y3 | yarn_service d/y3 |')
    lines.append('|---|---|---|---|---|---|---|---|---|---|---|')
    for r in sorted(ok, key=lambda r: r['recorded_margin']):
        lines.append(f"| {r['ep']} | {r['opponent']} | {r['recorded_margin']:+.0f} | {r['diag_margin']:+.0f} | "
                     f"{r['y3_noswitch_margin']:+.0f} | {'YES' if r['switch_fired'] else 'no'} | {r['switch_days']} | "
                     f"{'YES' if r['noswitch_wouldve_beaten_actual'] else 'no'} | {r['sheep_lost_diag']}/{r['sheep_lost_y3']} | "
                     f"{r['orphan_days_diag']}/{r['orphan_days_y3']} | {r['yarn_service_diag']}/{r['yarn_service_y3']} |")
    for r in [r for r in losses if r['status'] != 'ok']:
        lines.append(f"| {r['ep']} | -- | {r['recorded_margin']:+.0f} | NOT REPLAYED | | | | | | | |")

    lines.append('\n## F. Ladder tracking (56525017 vs 56395605)\n')
    lines.append('```\n' + ladder['track_submission']['stdout'] + '\n```\n')
    lines.append('```\n' + ladder['rating_trend']['stdout'] + '\n```\n')

    (OUT / 'report.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print('A. p2750 decomposition...', flush=True)
    dec_p2750 = part_p2750()
    print('B. V56 decomposition...', flush=True)
    dec_v56 = part_v56()
    print('C. 180-world decomposition...', flush=True)
    dec_180 = part_180()
    print('D. switch-day breakdown...', flush=True)
    switchday = part_switchday()
    (OUT / 'decomposition.json').write_text(json.dumps(
        dict(p2750=dec_p2750, v56=dec_v56, ladder180=dec_180, switchday=switchday), indent=1), encoding='utf-8')

    print('E. live losses...', flush=True)
    losses = part_live_losses()
    (OUT / 'live_losses.json').write_text(json.dumps(losses, indent=1), encoding='utf-8')

    print('F. ladder tracking...', flush=True)
    ladder = part_ladder()
    (OUT / 'ladder_tracking.json').write_text(json.dumps(ladder, indent=1), encoding='utf-8')

    write_report(dec_p2750, dec_v56, dec_180, switchday, losses, ladder)
    print('done ->', OUT)


if __name__ == '__main__':
    main()
