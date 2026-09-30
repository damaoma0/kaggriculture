"""Tables for search_ceiling.py: reads rows_both.jsonl (+ rows_*_long*.jsonl when present), writes report.txt."""
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUCKETS = ((0, 2), (3, 11), (12, 17), (18, 23), (24, 29))


def load(name):
    p = HERE / name
    return [json.loads(x) for x in open(p, encoding='utf-8')] if p.exists() else []


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def q(xs, f):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(f * len(xs)))] if xs else 0.0


def main():
    rows = load(sys.argv[1] if len(sys.argv) > 1 else 'rows_both.jsonl')
    meta = json.loads((HERE / 'meta_both.json').read_text()) if (HERE / 'meta_both.json').exists() else []
    longs = [r for p in sorted(HERE.glob('rows_*long*.jsonl')) for r in load(p.name)]
    L = []
    w = L.append
    sides = [s for s in ('ours', 'leader') if any(r['side'] == s for r in rows)]
    G = {s: len({r['ep'] for r in rows if r['side'] == s}) for s in sides}
    R = {s: [r for r in rows if r['side'] == s] for s in sides}
    w('SEARCH CEILING ON OUR OWN DAYS (stored data only; results/fresh/search_ceiling_20260925/search_ceiling.py)')
    w('')
    w('Files used')
    w('  ours   = current default deploy (tie_value) + passive dropped-job tracer, Kaggle run wtr7 agent mgt_lpv_mpt0,')
    w('           12 smoke worlds: results/fresh/kaggle_remote_lead/wtr7/output/kgr-wtr7-s0/out/repo/results/fresh/')
    w('           lead_world_trace/mgt_lpv_mpt0_<ep>.json (actions) + lead_idle/mp0/*.jsonl (tracer, matched to episodes')
    w('           by per-day command counts). These are the newest default traces (dep7 = older ff1-era default).')
    w('  leader = data/leader_tapes/<team>_*/<ep>.json.gz for the 12 scripts/lead_g1.GAMES (DSM x4, Vadim x4, UMG x4).')
    for m in meta:
        extra = ''
        if m['side'] == 'ours':
            extra = f"  tracer {Path(m['tracer_file']).name} matched {m['tracer_match_days']}/29 days, seat {m['tracer_seat']}={m['seat']}, " \
                    f"rebuilt positions vs tracer idle positions {m['pos_check_ok']}/{m['pos_check_ok'] + m['pos_check_bad']}"
        else:
            extra = f"  {m.get('team')}"
        w(f"    {m['side']:<6} {m['ep']} seat {m['seat']}{extra}")
    w('  Hands = the returned hands list (ours: one failed hire on one world-day; the leader over-requests HIRE, so HIRE')
    w('  orders overcount its hands). Days 0-29 (day 29 has 23 steps). n = unit-days / days / games as stated per table.')
    w('')

    # ---------------------------------------------------------------- 1. model check
    w('1. MODEL CHECK: model steps (labour_search.finish of the unit\'s own jobs in its own order) vs actual busy steps')
    w('   (first hour .. last non-PASS command) per unit-day.')
    w('   | side | instance | unit-days | frozen (route does not fit, > 24) | model / actual busy per game | |model-actual|<=2 | model < actual-2 | model > actual+2 |')
    for s in sides:
        ud = [(r, u) for r in R[s] for u in r['unit_days']]
        n = len(ud)
        m = sum(u['model'] for _, u in ud)
        a = sum(u['actual'] for _, u in ud)
        wi = sum(1 for _, u in ud if abs(u['model'] - u['actual']) <= 2)
        lt = sum(1 for _, u in ud if u['model'] < u['actual'] - 2)
        gt = sum(1 for _, u in ud if u['model'] > u['actual'] + 2)
        fz_ls = sum(r['frozen_ls'] for r in R[s])
        m_ls = sum(r['model_ls'] for r in R[s])
        w(f"   | {s} | labour_search.instance (unit-index order) | {n} | {fz_ls} ({pct(fz_ls, n):.1f}%) | {m_ls / G[s]:.0f} / {a / G[s]:.0f} | | | |")
        w(f"   | {s} | time-order constraint (used below) | {n} | {sum(r['frozen'] for r in R[s])} ({pct(sum(r['frozen'] for r in R[s]), n):.1f}%) | "
          f"{m / G[s]:.0f} / {a / G[s]:.0f} ({pct(m - a, a):+.1f}%) | {pct(wi, n):.1f}% | {pct(lt, n):.1f}% | {pct(gt, n):.1f}% |")
    w('   Where the actual steps go vs the model (per game, time-order instance, all unit-days incl. frozen):')
    w('   | side | actual moves / model travel | work cmds (= model cmds) | actual shed cmds / model pickups+drops | actual mid-route PASS / model wait | actual busy / model |')
    for s in sides:
        g = G[s]
        am = sum(r['actual_moves'] for r in R[s]) / g
        mt = sum(r['model']['travel'] for r in R[s]) / g
        wk = sum(r['actual_work'] for r in R[s]) / g
        mc = sum(r['model']['cmds'] for r in R[s]) / g
        sh = sum(r['actual_shed'] for r in R[s]) / g
        pk = sum(r['model']['pickups'] + r['model']['drops'] for r in R[s]) / g
        ps = sum(r['actual_pass'] for r in R[s]) / g
        wt = sum(r['model']['wait'] for r in R[s]) / g
        ab = sum(r['actual_busy'] for r in R[s]) / g
        mb = sum(r['model']['busy'] for r in R[s]) / g
        w(f"   | {s} | {am:.0f} / {mt:.0f} | {wk:.0f} / {mc:.0f} | {sh:.0f} / {pk:.0f} | {ps:.0f} / {wt:.0f} | {ab:.0f} / {mb:.0f} |")
    for s in sides:
        tw = sum(r['cal'].get('tiles worked by two units', 0) for r in R[s])
        rv = sum(r['a']['1.0']['order']['reversed'] for r in R[s])
        pr = sum(r['a']['1.0']['order']['pairs'] for r in R[s])
        w(f"   {s}: jobs on a tile another unit worked earlier the same day: {tw / len(R[s]):.1f} a day (order kept: the later "
          f"job waits for the earlier job's threshold hour, the earlier job may not start after it); order pairs "
          f"reversed in the 1 s search solutions: {rv} of {pr}")
    w('   Units that do not fit the model (time-order instance): finish = model end hour, actual = busy steps,')
    w('   no_rel = model end hour with all release times dropped.')
    for s in sides:
        fz = [(r['ep'], r['day'], f) for r in R[s] for f in r['frozen_diag']]
        cause = Counter('release' if f['finish_no_release'] <= 24 else 'route' for _, _, f in fz)
        w(f"   {s}: {len(fz)} unit-days frozen; fit without releases: {cause['release']}, still too long: {cause['route']}")
        for ep, day, f in fz[:40]:
            w(f"     ep {ep} day {day:>2} unit {f['u']:>2}: start {f['start']}, jobs {f['jobs']}, finish {f['finish']}, actual {f['actual']}, no_rel {f['finish_no_release']}")
        if len(fz) > 40:
            w(f"     ... {len(fz) - 40} more in rows_both.jsonl (frozen_diag)")
    w('')

    # ---------------------------------------------------------------- 2a. same jobs, same units
    w('2a. SAME JOBS, SAME UNITS: model cost of the actual arrangement vs the min-sum search (busy unit-steps = sum over')
    w('    units of route end - first hour; frozen units kept as they are). Per game (sum over days / games).')
    w('    | side | games | days | unit-days | present unit-steps | work cmds | actual busy | model (our arrangement) | search 0.3 s | search 1 s | model->1 s | actual->1 s |')
    for s in sides:
        g = G[s]
        ps = sum(r['present_steps'] for r in R[s]) / g
        wk = sum(r['model']['cmds'] for r in R[s]) / g
        ab = sum(r['actual_busy'] for r in R[s]) / g
        mb = sum(r['model']['busy'] for r in R[s]) / g
        a3 = sum(r['a']['0.3']['model']['busy'] for r in R[s]) / g
        a1 = sum(r['a']['1.0']['model']['busy'] for r in R[s]) / g
        w(f"    | {s} | {g} | {len(R[s])} | {sum(len(r['unit_days']) for r in R[s])} | {ps:.0f} | {wk:.0f} | {ab:.0f} | {mb:.0f} | {a3:.0f} | {a1:.0f} | "
          f"{a1 - mb:+.0f} ({pct(a1 - mb, mb):+.1f}%) | {a1 - ab:+.0f} ({pct(a1 - ab, ab):+.1f}%) |")
    w('    Walking and steps per work command (per game):')
    w('    | side | actual moves | model travel (ours) | search travel 0.3 s | search travel 1 s | walking saved model->1 s | actual busy/op | model busy/op | search busy/op 1 s |')
    for s in sides:
        g = G[s]
        am = sum(r['actual_moves'] for r in R[s]) / g
        mt = sum(r['model']['travel'] for r in R[s]) / g
        t3 = sum(r['a']['0.3']['model']['travel'] for r in R[s]) / g
        t1 = sum(r['a']['1.0']['model']['travel'] for r in R[s]) / g
        wk = sum(r['model']['cmds'] for r in R[s]) / g
        ab = sum(r['actual_busy'] for r in R[s]) / g
        mb = sum(r['model']['busy'] for r in R[s]) / g
        a1 = sum(r['a']['1.0']['model']['busy'] for r in R[s]) / g
        w(f"    | {s} | {am:.0f} | {mt:.0f} | {t3:.0f} | {t1:.0f} | {t1 - mt:+.0f} ({pct(t1 - mt, mt):+.1f}%) | {ab / wk:.2f} | {mb / wk:.2f} | {a1 / wk:.2f} |")
    w('    By day range (per day, mean over games; busy steps; search = 1 s):')
    w('    | side | days | n days | units | work cmds | actual busy | model | search | model->search | model travel | search travel |')
    for s in sides:
        for lo, hi in BUCKETS:
            X = [r for r in R[s] if lo <= r['day'] <= hi]
            if not X:
                continue
            mb = st.mean(r['model']['busy'] for r in X)
            a1 = st.mean(r['a']['1.0']['model']['busy'] for r in X)
            w(f"    | {s} | {lo}-{hi} | {len(X)} | {st.mean(r['units'] for r in X):.1f} | {st.mean(r['model']['cmds'] for r in X):.0f} | "
              f"{st.mean(r['actual_busy'] for r in X):.0f} | {mb:.0f} | {a1:.0f} | {pct(a1 - mb, mb):+.1f}% | "
              f"{st.mean(r['model']['travel'] for r in X):.0f} | {st.mean(r['a']['1.0']['model']['travel'] for r in X):.0f} |")
    w('    Per game (ours / leader), model -> search 1 s busy steps:')
    for s in sides:
        per = defaultdict(lambda: [0, 0, 0])
        for r in R[s]:
            per[r['ep']][0] += r['actual_busy']
            per[r['ep']][1] += r['model']['busy']
            per[r['ep']][2] += r['a']['1.0']['model']['busy']
        w('     ' + s + ': ' + ', '.join(f"{ep}: {v[1]}->{v[2]} ({pct(v[2] - v[1], v[1]):+.1f}%)" for ep, v in per.items()))
    if longs:
        w('    Convergence check (long budget on a day subset; same days at 0.3 s / 1 s / long):')
        for s in sides:
            X = [r for r in longs if r['side'] == s]
            if not X:
                continue
            lb = [k for k in X[0]['a'] if k not in ('0.3', '1.0')][0]
            mb = sum(r['model']['busy'] for r in X)
            vals = {k: sum(r['a'][k]['model']['busy'] for r in X) for k in ('0.3', '1.0', lb)}
            w(f"     {s}: {len(X)} days (every 5th day, 12 games): model {mb}, " + ', '.join(f"{k} s {v} ({pct(v - mb, mb):+.1f}%)" for k, v in vals.items())
              + f"; {lb} s run: t95 mean {st.mean(r['a'][lb]['t95'] for r in X):.2f} s, p95 {q([r['a'][lb]['t95'] for r in X], .95):.2f} s")
            for lo, hi in ((0, 11), (12, 23), (24, 29)):
                Y = [r for r in X if lo <= r['day'] <= hi]
                if Y:
                    mb2 = sum(r['model']['busy'] for r in Y)
                    w(f"       days {lo}-{hi} ({len(Y)} days): " + ', '.join(
                        f"{k} s {pct(sum(r['a'][k]['model']['busy'] for r in Y) - mb2, mb2):+.1f}%" for k in ('0.3', '1.0', lb)))
    w('')

    # ---------------------------------------------------------------- 2b. hands dropped
    w('2b. HANDS THE SEARCH CAN DROP with all the day\'s jobs still done (labour_search.search on the actual routes;')
    w('    fib wages of the latest hires). Idle hands = hired but no tile work at all that day (dropped for free).')
    w('    | side | budget | hand-days / game | hands with jobs / day | hands dropped / day | dropped-hand-days / game | idle hand-days / game | wages paid / game | wages saved / game (jobs only) | incl. idle |')
    for s in sides:
        g = G[s]
        for b in ('0.3', '1.0'):
            w(f"    | {s} | {b} s | {sum(r['hired'] for r in R[s]) / g:.0f} | {st.mean(r['worked'] for r in R[s]):.2f} | "
              f"{st.mean(r['b'][b]['saved'] for r in R[s]):.2f} | {sum(r['b'][b]['saved'] for r in R[s]) / g:.1f} | "
              f"{sum(r['idle_hands'] for r in R[s]) / g:.1f} | {sum(r['wage_paid'] for r in R[s]) / g:,.0f} | "
              f"{sum(r['b'][b]['wage_saved'] for r in R[s]) / g:,.0f} | {sum(r['b'][b]['wage_saved_incl_idle'] for r in R[s]) / g:,.0f} |")
    for s in sides:
        c = Counter(r['b']['1.0']['saved'] for r in R[s])
        w(f"    {s} (1 s) distribution of hands dropped per day: " + ', '.join(f"{k}: {pct(v, len(R[s])):.0f}%" for k, v in sorted(c.items())))
        for lo, hi in BUCKETS:
            X = [r for r in R[s] if lo <= r['day'] <= hi]
            if X:
                w(f"      days {lo}-{hi}: hands with jobs {st.mean(r['worked'] for r in X):.2f} -> {st.mean(r['worked'] - r['b']['1.0']['saved'] for r in X):.2f}, "
                  f"wages saved {sum(r['b']['1.0']['wage_saved'] for r in X) / G[s]:,.0f} / game")
    w('')

    # ---------------------------------------------------------------- 2c. dropped jobs
    C_ = [r for r in R.get('ours', []) if 'c' in r]
    if C_:
        g = G['ours']
        w('2c. OURS: the tracer\'s jobs left open at 23h (fresh maintenance solve, value > 0, minus hour-23 ops; production-')
        w('    affecting = units > 0) inserted by value into the same crew\'s routes before midnight (release = hour the job')
        w('    first appeared in the executor\'s task list, 0 if it never did). Per game.')
        w('    | set | jobs | coin value | prod. jobs | prod. value | units |')
        for k, lab in (('all', 'dropped at 23h (tracer)'), ('fit_actual', 'fit into OUR routes as they are (model)'),
                       ('fit_search', 'fit after the min-sum search (1 s)')):
            n = sum(r['c'][k].get('n', 0) for r in C_) / g
            v = sum(r['c'][k].get('value', 0) for r in C_) / g
            npd = sum(r['c'][k].get('n_prod', 0) for r in C_) / g
            vp = sum(r['c'][k].get('v_prod', 0) for r in C_) / g
            un = sum(r['c'][k].get('units', 0) for r in C_) / g
            w(f"    | {lab} | {n:.1f} | {v:,.0f} | {npd:.1f} | {vp:,.0f} | {un:.1f} |")
        w('    By command (jobs / value per game: dropped -> fit as they are -> fit after search):')
        for cmd in ('WATER', 'FERTILIZE', 'COLLECT_FERTILIZER', 'CARE', 'FEED', 'HARVEST'):
            vals = []
            for k in ('all', 'fit_actual', 'fit_search'):
                vals.append((sum(r['c'][k].get('n_' + cmd, 0) for r in C_) / g, sum(r['c'][k].get('v_' + cmd, 0) for r in C_) / g))
            w(f"      {cmd:<19} " + ' -> '.join(f"{n:.1f} / {v:,.0f}" for n, v in vals))
        for key in ('in_task', 'not_in_task'):
            vals = [(sum(r['c'][k].get('n_' + key, 0) for r in C_) / g, sum(r['c'][k].get('v_' + key, 0) for r in C_) / g)
                    for k in ('all', 'fit_actual', 'fit_search')]
            w(f"      {key:<19} " + ' -> '.join(f"{n:.1f} / {v:,.0f}" for n, v in vals))
        w(f"      jobs whose idle passes saw 'lack:<item>' (item neither carried nor in the shed; the model assumes stock): "
          + ' -> '.join(f"{sum(r['c'][k].get('n_lack_seen', 0) for r in C_) / g:.1f}" for k in ('all', 'fit_actual', 'fit_search')))
        for lo, hi in BUCKETS:
            X = [r for r in C_ if lo <= r['day'] <= hi]
            if X:
                w(f"      days {lo}-{hi}: dropped {sum(r['c']['all'].get('n', 0) for r in X) / g:.1f} ({sum(r['c']['all'].get('value', 0) for r in X) / g:,.0f}) -> "
                  f"fit as is {sum(r['c']['fit_actual'].get('n', 0) for r in X) / g:.1f} ({sum(r['c']['fit_actual'].get('value', 0) for r in X) / g:,.0f}) -> "
                  f"after search {sum(r['c']['fit_search'].get('n', 0) for r in X) / g:.1f} ({sum(r['c']['fit_search'].get('value', 0) for r in X) / g:,.0f})")
        w('')

    ap = HERE / 'append_check.txt'
    if ap.exists():
        w('    Lower bound without any re-routing (append_check.py): the SAME units continue after their ACTUAL last command')
        w('    (actual timing, not the model), a detour to the shed first when a job needs wheat / fertilizer:')
        for line in ap.read_text(encoding='utf-8').splitlines():
            w('    ' + line)
    # tracer: when did the dropped jobs first appear (a morning plan sees only the hour-0 ones)
    tf = [m['tracer_file'] for m in meta if m.get('tracer_file')]
    if tf:
        root = HERE.parents[2]
        fo = Counter()
        why = Counter()
        for f in tf:
            for line in open(root / f, encoding='utf-8'):
                r = json.loads(line)
                for j in r['dropped']:
                    h = j.get('first_open')
                    fo['never in tasks' if h is None else 'hour 0' if h == 0 else 'hours 1-11' if h < 12 else 'hours 12-17' if h < 18 else 'hours 18-23'] += 1
                    if not j['in_task']:
                        why['not_in_tasks'] += 1
                    elif not j['idle']:
                        why['no idle pass while open'] += 1
                    else:
                        why[Counter(p_[2] for p_ in j['idle']).most_common(1)[0][0]] += 1
        n = sum(fo.values())
        w('    Tracer (all 12 games): when the dropped jobs first entered the executor task list: '
          + ', '.join(f"{k} {pct(v, n):.0f}%" for k, v in sorted(fo.items())))
        w('    ... and the tracer own reason (lead_idle_report attribution): ' + ', '.join(f"{k} {pct(v, n):.0f}%" for k, v in why.most_common()))
        w('')

    # ---------------------------------------------------------------- 4. timing
    w('4. SEARCH TIME PER DAY (this laptop, one process, pure Python, shared machine)')
    w('    min-sum (a) runs to its budget; t95 = time at which it had 95% of its final saving.')
    w('    labour_search.search (b) stops when no further hand can be emptied (can overrun: checks between hands).')
    w('    | side | search | budget | days | mean s | p50 | p95 | max | t95 mean / p95 |')
    for s in sides:
        for b in ('0.3', '1.0'):
            xs = [r['a'][b]['secs'] for r in R[s]]
            t95 = [r['a'][b]['t95'] for r in R[s]]
            w(f"    | {s} | min-sum | {b} | {len(xs)} | {st.mean(xs):.3f} | {q(xs, .5):.3f} | {q(xs, .95):.3f} | {max(xs):.3f} | {st.mean(t95):.3f} / {q(t95, .95):.3f} |")
        for b in ('0.3', '1.0'):
            xs = [r['b'][b]['secs'] for r in R[s]]
            w(f"    | {s} | hand-drop | {b} | {len(xs)} | {st.mean(xs):.3f} | {q(xs, .5):.3f} | {q(xs, .95):.3f} | {max(xs):.3f} | |")
    # ---------------------------------------------------------------- summary (placed at the top)
    S_ = []
    if set(sides) == {'ours', 'leader'}:
        def tot(s, f):
            return sum(f(r) for r in R[s]) / G[s]
        o_ab, o_mb = tot('ours', lambda r: r['actual_busy']), tot('ours', lambda r: r['model']['busy'])
        o_a1 = tot('ours', lambda r: r['a']['1.0']['model']['busy'])
        l_ab, l_mb = tot('leader', lambda r: r['actual_busy']), tot('leader', lambda r: r['model']['busy'])
        l_a1 = tot('leader', lambda r: r['a']['1.0']['model']['busy'])
        o_mt, o_t1 = tot('ours', lambda r: r['model']['travel']), tot('ours', lambda r: r['a']['1.0']['model']['travel'])
        l_mt, l_t1 = tot('leader', lambda r: r['model']['travel']), tot('leader', lambda r: r['a']['1.0']['model']['travel'])
        o_wk, l_wk = tot('ours', lambda r: r['model']['cmds']), tot('leader', lambda r: r['model']['cmds'])
        mid = {s: [r for r in R[s] if 12 <= r['day'] <= 23] for s in sides}
        gm = {s: pct(sum(r['a']['1.0']['model']['busy'] for r in mid[s]) - sum(r['model']['busy'] for r in mid[s]),
                     sum(r['model']['busy'] for r in mid[s])) for s in sides}
        S_.append('SUMMARY (per game; ours = 12 smoke worlds, current default deploy; leader = 12 G1 worlds; model = labour_search')
        S_.append("time model, order constraint in time order; busy = unit-steps from a unit's first hour to its route end)")
        S_.append(f"  work commands / game: ours {o_wk:.0f}, leader {l_wk:.0f}. Busy unit-steps: actual ours {o_ab:.0f} / leader {l_ab:.0f}; "
                  f"model of the actual arrangement {o_mb:.0f} / {l_mb:.0f}; min-sum search 1 s {o_a1:.0f} / {l_a1:.0f}.")
        S_.append(f"  gap of the actual arrangement to the search (model): ours {pct(o_a1 - o_mb, o_mb):+.1f}% ({o_a1 - o_mb:+.0f} steps), leader "
                  f"{pct(l_a1 - l_mb, l_mb):+.1f}% ({l_a1 - l_mb:+.0f}); days 12-23: ours {gm['ours']:+.1f}%, leader {gm['leader']:+.1f}%. "
                  f"Walking: ours {o_mt:.0f} -> {o_t1:.0f} ({pct(o_t1 - o_mt, o_mt):+.1f}%), leader {l_mt:.0f} -> {l_t1:.0f} ({pct(l_t1 - l_mt, l_mt):+.1f}%).")
        ov = {s: (tot(s, lambda r: r['actual_moves'] - r['model']['travel']),
                  tot(s, lambda r: r['actual_shed'] - r['model']['pickups'] - r['model']['drops']),
                  tot(s, lambda r: r['actual_pass'] - r['model']['wait'])) for s in sides}
        S_.append(f"  execution overhead beyond the model (actual - model): ours {o_ab - o_mb:+.0f} ({pct(o_ab - o_mb, o_mb):+.1f}%) = moves "
                  f"{ov['ours'][0]:+.0f}, shed commands {ov['ours'][1]:+.0f}, PASS-vs-wait {ov['ours'][2]:+.0f}; leader {l_ab - l_mb:+.0f} "
                  f"({pct(l_ab - l_mb, l_mb):+.1f}%) = moves {ov['leader'][0]:+.0f}, shed {ov['leader'][1]:+.0f}, PASS-vs-wait {ov['leader'][2]:+.0f} "
                  f"(extra moves = walking beyond the model's Manhattan route with one pickup per item type at the start and one delivery).")
        S_.append(f"  busy steps per work command: ours actual {o_ab / o_wk:.2f} / model {o_mb / o_wk:.2f} / search {o_a1 / o_wk:.2f}; leader "
                  f"{l_ab / l_wk:.2f} / {l_mb / l_wk:.2f} / {l_a1 / l_wk:.2f}.")
        S_.append(f"  hands droppable with all jobs done (1 s): ours {st.mean(r['b']['1.0']['saved'] for r in R['ours']):.2f} a day, "
                  f"wages {tot('ours', lambda r: r['b']['1.0']['wage_saved']):,.0f} of {tot('ours', lambda r: r['wage_paid']):,.0f}; leader "
                  f"{st.mean(r['b']['1.0']['saved'] for r in R['leader']):.2f} a day, {tot('leader', lambda r: r['b']['1.0']['wage_saved']):,.0f} of "
                  f"{tot('leader', lambda r: r['wage_paid']):,.0f}.")
        if C_:
            gg = G['ours']
            S_.append(f"  dropped jobs (tracer): {sum(r['c']['all'].get('n', 0) for r in C_) / gg:.1f} ({sum(r['c']['all'].get('value', 0) for r in C_) / gg:,.0f} coins); "
                      f"fit after the search at the same crew {sum(r['c']['fit_search'].get('n', 0) for r in C_) / gg:.1f} "
                      f"({sum(r['c']['fit_search'].get('value', 0) for r in C_) / gg:,.0f}); into our routes as scored by the model "
                      f"{sum(r['c']['fit_actual'].get('n', 0) for r in C_) / gg:.1f} ({sum(r['c']['fit_actual'].get('value', 0) for r in C_) / gg:,.0f}); "
                      f"by only continuing after the actual last command (no re-routing, actual timing): see 2c (append-only).")
        S_.append('  CAVEATS: the model gives each unit ONE pickup per item type at its start and unlimited shed stock, ignores')
        S_.append("  within-day flows (wheat harvested then fed) and carry-over; the jobs are those actually done (plus the tracer's")
        S_.append('  dropped jobs), not what a planner would choose; the leader has 4.5% frozen unit-days (untouched) vs ours 0.8%;')
        S_.append('  the search is not converged at 1 s (5 s adds about 2 points for ours, 1 for the leader), so the gaps are lower')
        S_.append("  bounds of the model ceiling; tracer coin values are the maintenance module's values, not realised cash.")
        S_.append('')
    L = L[:2] + S_ + L[2:]
    (HERE / 'report.txt').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
