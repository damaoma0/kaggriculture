"""Report: Mother-Goose's recorded sequence against our frozen benchmark, net of the tape handicap.

Reads results/fresh/tape_vs_bench/{mg,calib}-<episode>-<seat>.json written by tape_vs_bench.py.

  1. Full-game head-to-head for each arm, and the paired difference MG minus calibration on the same
     seed, seat and shop sequence: the policy advantage net of the cost of being a frozen tape.
  2. Validity: first board divergence, first failed command, and two break definitions —
       strict:   the first day with at least max(5, 2% of commands) failed commands;
       coherent: the first day failed commands reach 5% of the day's commands, or sold units fall
                 below half the original game's fulfilment of the same requests.
     Failure rates are shown by phase so the reader can judge coherence directly.
  3. Margins at fixed checkpoints, restricted to games still coherent then.
  4. Labour, land and the exact revenue decomposition (report_efficiency) over the common coherent
     window, and over the full game marked as partly unreliable.
"""
import json, random, statistics as st
from market_corpus import ROOT
import report_efficiency as R

OUT = ROOT / 'results/fresh/tape_vs_bench'
PHASES = ((0, 6), (6, 12), (12, 18), (18, 24), (24, 30))
ARMS = (('mg', 'Mother-Goose tape'), ('mg40', 'Mother-Goose tape, cushion 40'),
        ('mg500', 'Mother-Goose tape, cushion 500'), ('calib', 'our own benchmark tape (calibration)'))


def load():
    rows = {}
    for path in OUT.glob('*.json'):
        if path.name.count('-') != 2:
            continue
        r = json.loads(path.read_text(encoding='utf-8'))
        rows.setdefault(r['arm'], {})[(r['episode'], r['seat'])] = r
    return rows


def day_series(daily):
    out = []
    for d in range(1, len(daily)):
        a, b = daily[d - 1], daily[d]
        pa, pb = a['physical'], b['physical']
        fails = sum(pb.get(k, 0) - pa.get(k, 0) for k in ('no_effect', 'missing_worker_commands', 'malformed_commands'))
        cmds = (pb.get('commands', 0) - pa.get('commands', 0)
                + pb.get('missing_worker_commands', 0) - pa.get('missing_worker_commands', 0))
        sold = sum(b['sold_units'].values()) - sum(a['sold_units'].values())
        req = sum(b['sell_requested'].values()) - sum(a['sell_requested'].values())
        out.append(dict(fails=fails, commands=cmds, sold=sold, requested=req))
    return out


def breaks(r):
    tape, orig = day_series(r['tape_daily']), day_series(r['original_daily'])
    strict = coherent = None
    for d, (x, o) in enumerate(zip(tape, orig)):
        sell_collapse = (o['sold'] >= 5 and o['requested'] > 0 and x['requested'] > 0
                         and x['sold'] / x['requested'] < 0.5 * o['sold'] / o['requested'])
        if strict is None and (x['fails'] >= max(5, 0.02 * max(1, x['commands'])) or sell_collapse):
            strict = d
        if coherent is None and ((x['commands'] >= 50 and x['fails'] >= 0.05 * x['commands']) or sell_collapse):
            coherent = d
    rates = []
    for lo, hi in PHASES:
        f = sum(x['fails'] for x in tape[lo:hi])
        c = sum(x['commands'] for x in tape[lo:hi])
        rates.append(100.0 * f / c if c else 0.0)
    orig_rates = []
    for lo, hi in PHASES:
        f = sum(x['fails'] for x in orig[lo:hi])
        c = sum(x['commands'] for x in orig[lo:hi])
        orig_rates.append(100.0 * f / c if c else 0.0)
    return strict, coherent, rates, orig_rates


def ci(values, n=10000, seed=11):
    rng = random.Random(seed)
    draws = sorted(st.mean(rng.choice(values) for _ in values) for _ in range(n))
    return draws[int(0.025 * n)], draws[int(0.975 * n) - 1]


def row_at(daily, day):
    s = daily[min(day, len(daily) - 1)]
    return dict(physical=s['physical'], tile_hours=s['tile_hours'], revenue=s['revenue'],
                sold_units=s['sold_units'], spend=s['spend'], cash=s['money'])


def section_head_to_head(rows):
    print('## 1. Full-game head-to-head against the live frozen benchmark')
    out = {}
    for arm, label in ARMS:
        if arm not in rows:
            continue
        rs = list(rows[arm].values())
        w = sum(1 for r in rs if r['margin'] > 0)
        t = sum(1 for r in rs if r['margin'] == 0)
        l = sum(1 for r in rs if r['margin'] < 0)
        margins = [r['margin'] for r in rs]
        lo, hi = ci(margins)
        wl, wh = ci([100.0 * (m > 0) for m in margins])
        out[arm] = dict(n=len(rs), wins=w, ties=t, losses=l, mean_margin=st.mean(margins), ci=(lo, hi),
                        win_ci=(wl, wh), tape_cash=st.mean(r['tape_cash'] for r in rs),
                        bench_cash=st.mean(r['bench_cash'] for r in rs))
        print(f"{label:40s} {w}W-{t}T-{l}L of {len(rs)} | win rate {100*w/len(rs):.1f}% (95% CI {wl:.1f}-{wh:.1f}) | "
              f"margin {st.mean(margins):+,.0f} (95% CI {lo:+,.0f} to {hi:+,.0f}) | tape cash "
              f"{out[arm]['tape_cash']:,.0f} vs benchmark {out[arm]['bench_cash']:,.0f}")
    mg = rows['mg']
    orig_mg = [r['original_cash'][r['seat']] for r in mg.values()]
    orig_opp = [r['original_cash'][1 - r['seat']] for r in mg.values()]
    print(f"   for reference, Mother-Goose's original games: its cash {st.mean(orig_mg):,.0f} vs its opponents {st.mean(orig_opp):,.0f}")
    for arm, label in ARMS:
        if arm == 'calib' or arm not in rows:
            continue
        paired = [rows[arm][k]['margin'] - rows['calib'][k]['margin'] for k in rows[arm] if k in rows['calib']]
        lo, hi = ci(paired)
        better = sum(1 for p in paired if p > 0)
        print(f"   {label} minus calibration, paired on seed/seat/shops (n={len(paired)}): "
              f"{st.mean(paired):+,.0f} (95% CI {lo:+,.0f} to {hi:+,.0f}); better in {better}/{len(paired)}")
        out[f'{arm}_minus_calibration'] = dict(n=len(paired), mean=st.mean(paired), ci=(lo, hi), better=better)
    return out


def section_validity(rows):
    print('\n## 2. How long each tape stays valid')
    out = {}
    for arm, label in ARMS:
        if arm not in rows:
            continue
        rs = list(rows[arm].values())
        exact = [r['validity']['t_exact'] for r in rs]
        firsts = [r['validity']['first_fail_day'] for r in rs]
        info = [breaks(r) for r in rs]
        strict = [x[0] for x in info]
        coherent = [x[1] for x in info]
        rates = [x[2] for x in info]
        orig = [x[3] for x in info]
        def desc(v, unit):
            real = [x for x in v if x is not None]
            return (f"never in {sum(1 for x in v if x is None)}/{len(v)}; otherwise median {unit} "
                    f"{st.median(real):.0f} (range {min(real)}-{max(real)})") if real else f'never in {len(v)}/{len(v)}'
        print(f"-- {label} (n={len(rs)})")
        print(f"   board first differs from the recorded board: {desc(exact, 'step')}")
        print(f"   first failed command: {desc(firsts, 'day')}")
        print(f"   strict break (>= max(5, 2%) failures or sale collapse): {desc(strict, 'day')}")
        print(f"   coherence break (>= 5% failures or sale collapse):      {desc(coherent, 'day')}")
        print('   failed-command rate by phase, tape vs its original game: ' + ', '.join(
            f"days {lo}-{hi-1}: {st.mean(r[i] for r in rates):.2f}% vs {st.mean(o[i] for o in orig):.2f}%"
            for i, (lo, hi) in enumerate(PHASES)))
        out[arm] = dict(t_exact=exact, first_fail_day=firsts, strict_break=strict, coherent_break=coherent,
                        fail_rate_by_phase=[st.mean(r[i] for r in rates) for i in range(len(PHASES))],
                        original_fail_rate_by_phase=[st.mean(o[i] for o in orig) for i in range(len(PHASES))])
    return out


def section_checkpoints(rows):
    print('\n## 3. Cash margin at checkpoints, games still coherent at that day')
    print('   (mid-season cash undervalues standing crops and animals; the final margin is the verdict)')
    out = {}
    for arm, label in ARMS:
        if arm not in rows:
            continue
        rs = list(rows[arm].values())
        line = []
        for day in (3, 6, 9, 12, 15, 18, 21, 24, 30):
            ok = [r for r in rs if (breaks(r)[1] is None or breaks(r)[1] >= day)]
            if not ok:
                line.append(f'day {day}: none coherent')
                continue
            m = [r['tape_daily'][min(day, len(r['tape_daily']) - 1)]['money']
                 - r['bench_daily'][min(day, len(r['bench_daily']) - 1)]['money'] for r in ok]
            line.append(f'day {day}: {st.mean(m):+,.0f} (n={len(ok)})')
            out.setdefault(arm, {})[day] = dict(n=len(ok), margin=st.mean(m))
        print(f"-- {label}: " + '; '.join(line))
    return out


def section_decomposition(rows, window_day, arm='mg'):
    print(f'\n## 4. Labour, land and revenue decomposition: Mother-Goose tape ({arm}) minus live benchmark')
    out = {}
    for label, day, pick in ((f'coherent window, through day {window_day}', window_day,
                              lambda r: breaks(r)[1] is None or breaks(r)[1] >= window_day),
                             ('full game (after the break, unreliable)', 30, lambda r: True)):
        rs = [r for r in rows[arm].values() if pick(r)]
        if not rs:
            print(f"\n### {label}: no game is still coherent at that point; nothing to decompose")
            out[label] = dict(n=0)
            continue
        tape = [row_at(r['tape_daily'], day) for r in rs]
        bench = [row_at(r['bench_daily'], day) for r in rs]
        a, b = R.aggregate(tape), R.aggregate(bench)
        by_factor, by_product, spend, total = R.decompose(a, b)
        print(f"\n### {label}: n={len(rs)} games, cash gap {a['cash'] - b['cash']:+,.0f}")
        for name, rows_ in (('Mother-Goose tape', tape), ('live benchmark', bench)):
            x = R.aggregate(rows_)
            p = x['phys']
            hire = x['spend'].get('HIRE', 0.0)
            print(f"   {name:18s} hire ${hire:6.0f} | effective {p.get('effective', 0):6.0f} | eff/100$ "
                  f"{100 * p.get('effective', 0) / hire if hire else 0:5.1f} | moves/eff "
                  f"{p.get('moves', 0) / max(1, p.get('effective', 0)):4.2f} | productive tile-days {x['productive']:6.0f} "
                  f"| util {100 * x['productive'] / x['land']:4.1f}% | fallow {x['fallow']:5.0f}")
        for k, lab in (('land', 'land'), ('utilisation', 'utilisation'), ('portfolio', 'portfolio (crop/animal mix)'),
                       ('yield_', 'yield per tile-day'), ('price', 'price realisation')):
            print(f"   revenue via {lab:28s} {by_factor[k]:+9,.0f}")
        for k, v in spend.items():
            print(f"   spend: {k:36s} {v:+9,.0f}")
        print('   by product (portfolio / yield / price): ' + ', '.join(
            f"{p[:5]} {by_product[p]['portfolio']:+.0f}/{by_product[p]['yield_']:+.0f}/{by_product[p]['price']:+.0f}"
            for p in R.PRODUCTS))
        out[label] = dict(n=len(rs), cash_gap=a['cash'] - b['cash'], revenue_by_factor=dict(by_factor),
                          spend=spend, by_product=by_product)
    return out


def main():
    rows = load()
    summary = dict(head_to_head=section_head_to_head(rows), validity=section_validity(rows),
                   checkpoints=section_checkpoints(rows))
    summary['decomposition'] = {}
    for arm in ('mg', 'mg40', 'mg500'):
        if arm not in rows:
            continue
        coherent = [breaks(r)[1] for r in rows[arm].values()]
        days = sorted(30 if c is None else c for c in coherent)
        window = max(3, days[len(days) // 4])  # a window at least three-quarters of games reach coherently
        summary['decomposition'][arm] = section_decomposition(rows, window, arm)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    print('\nwrote', OUT / 'summary.json')


if __name__ == '__main__':
    main()
