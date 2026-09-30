"""Skeptic check 1: position rebuild, unit counts and the per-game counts the report quotes (own code).

  ours   : rebuilt positions vs the tracer's idle-record positions (tracer file matched to its episode by per-day
           move / op counts, own matcher); hands per day vs HIRE orders.
  leader : no tracer. Independent check against data/leader_semantics (built from full replays with observations,
           cash reproduced): per-day hands present vs 'labour.hires_arrived', and per-day tile multisets of
           WATER / FEED / CARE / FERTILIZE commands at the rebuilt positions vs 'maintenance' tile lists.
  counts : work commands, actual busy unit-steps, unit-days, present unit-steps per game (report: ours 2877 / 7138 /
           4132 total / 7869, leader 3659 / 7298 / 3875 / 7366).
usage: verify_rebuild.py
"""
import gzip
import json
from collections import Counter

import verify_common as V

OPS = ('WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE', 'COLLECT_FERTILIZER')


def day_counts(days, d):
    c = Counter()
    for u, seq in days[d].items():
        for h, p, op, cmd in seq:
            if op in V.MV:
                c['move'] += 1
            elif op in OPS:
                c['op_' + op] += 1
            elif op == 'PASS':
                c['pass'] += 1
    return c


def counts(days):
    c = Counter()
    for d in range(30):
        for u, seq in days[d].items():
            c['unit_days'] += 1
            c['present'] += len(seq)
            c['busy'] += V.busy_of(seq)
            c['work'] += sum(1 for h, p, op, cmd in seq if V.is_work(p, op))
            c['moves'] += sum(1 for h, p, op, cmd in seq if op in V.MV)
            c['pickup'] += sum(1 for h, p, op, cmd in seq if op == 'PICKUP')
            c['shed_drop'] += sum(1 for h, p, op, cmd in seq if op in ('DROP',) or (op == 'PLACE' and p in V.SHEDSET))
            c['struct_on_shed_tile'] += sum(1 for h, p, op, cmd in seq if p in V.SHEDSET and op in ('BUILD_PASTURE', 'BUILD_COOP'))
            c['odd_ops'] += sum(1 for h, p, op, cmd in seq if V.is_work(p, op) and op not in V.BOUGHT | set(OPS) | {'DIG', 'HARVEST'})
    return c


def main():
    out = []
    tracers = V.load_tracer_files()
    keys = ('move', 'op_WATER', 'op_FEED', 'op_CARE', 'op_HARVEST', 'op_FERTILIZE', 'pass')
    tot = {'ours': Counter(), 'leader': Counter()}
    used = set()
    for ep in V.OURS:
        g = V.load_ours(ep)
        days, pos_at = V.rebuild(g['actions'])
        best = None
        for name, rr in tracers.items():
            if name in used:
                continue
            ok = sum(1 for r in rr if all(r['work'].get(k, 0) == day_counts(days, r['day']).get(k, 0) for k in keys))
            if best is None or ok > best[0]:
                best = (ok, name)
        used.add(best[1])
        rr = tracers[best[1]]
        pos_ok = pos_bad = 0
        badex = []
        for r in rr:
            for rec in r['idle']:
                h, u, p = rec[0], rec[1], tuple(rec[2])
                ps = pos_at.get(r['day'] * 24 + h)
                if ps is not None and u < len(ps) and ps[u] == p:
                    pos_ok += 1
                else:
                    pos_bad += 1
                    if len(badex) < 3:
                        badex.append((r['day'], h, u, p, ps[u] if ps and u < len(ps) else None))
        # hands per day vs HIRE orders issued that day
        hire_short = []
        for d in range(30):
            nh = max((len(g['actions'][t].get('hands') or []) for t in range(d * 24, min(719, d * 24 + 24))), default=0)
            hires = sum(1 for t in range(d * 24, min(719, d * 24 + 24)) for o in (g['actions'][t].get('market') or []) if o and o[0] == 'HIRE')
            if hires != nh:
                hire_short.append((d, hires, nh))
        c = counts(days)
        tot['ours'].update(c)
        out.append(dict(side='ours', ep=ep, seat=g['seat'], tracer=best[1], tracer_days=best[0], tracer_n=len(rr),
                        tracer_seat=int(best[1].split('_')[-1].split('.')[0]), pos_ok=pos_ok, pos_bad=pos_bad, badex=badex,
                        hire_vs_hands=hire_short, counts=dict(c)))
    for team, ep in V.LEADER:
        g = V.load_leader(team, ep)
        days, pos_at = V.rebuild(g['actions'])
        sem = json.load(gzip.open(V.ROOT / f'data/leader_semantics/{team}/{ep}.json.gz', 'rt', encoding='utf-8'))
        hands_bad, tile_ok, tile_bad, tile_detail = [], Counter(), Counter(), []
        for d in range(30):
            nh = max((len(g['actions'][t].get('hands') or []) for t in range(d * 24, min(719, d * 24 + 24))), default=0)
            lab = sem['days'][d]['labour'] if d < len(sem['days']) else None
            if lab is not None and d < 29 and lab.get('hands_present') != nh:
                hands_bad.append((d, nh, lab.get('hires_arrived'), lab.get('hands_present')))
            if lab is None:
                continue
            mt = sem['days'][d]['maintenance']
            for op in ('WATER', 'FEED', 'CARE', 'FERTILIZE'):
                reb = Counter()
                for u, seq in days[d].items():
                    for h, p, o, cmd in seq:
                        if o == op:
                            reb[p[1] * 10 + p[0]] += 1
                sm = Counter(mt.get(op, []))
                inter = sum((reb & sm).values())
                tile_ok[op] += inter
                tile_ok['sem_total'] += sum(sm.values())
                tile_bad[op] += sum(reb.values()) - inter
                if sum(sm.values()) - inter > 0 or sum(reb.values()) - inter > 0:
                    tile_detail.append((d, op, sum(reb.values()), sum(sm.values()), inter))
        c = counts(days)
        tot['leader'].update(c)
        out.append(dict(side='leader', ep=ep, team=team, seat=g['seat'], hands_mismatch_days=hands_bad,
                        tile_ok=dict(tile_ok), tile_extra_in_rebuild=dict(tile_bad), tile_detail=tile_detail[:8],
                        counts=dict(c)))
    L = ['VERIFY 1: rebuild / unit counts / per-game counts (own code)']
    for r in out:
        if r['side'] == 'ours':
            L.append(f"  ours {r['ep']} seat {r['seat']}: tracer {r['tracer']} {r['tracer_days']}/{r['tracer_n']} days, "
                     f"tracer seat {r['tracer_seat']}; idle positions {r['pos_ok']}/{r['pos_ok'] + r['pos_bad']} {r['badex'] or ''}; "
                     f"days HIRE orders != hands {r['hire_vs_hands']}")
        else:
            to, tb = sum(v for k, v in r['tile_ok'].items() if k != 'sem_total'), sum(r['tile_extra_in_rebuild'].values())
            L.append(f"  leader {r['ep']} seat {r['seat']}: days (0-28) hands list != engine hands_present {r['hands_mismatch_days']}; "
                     f"engine-effective maintenance ops matched at rebuilt tiles {to}/{r['tile_ok']['sem_total']}, rebuilt ops not effective {tb} {r['tile_ok']} "
                     f"(extra {r['tile_extra_in_rebuild']}) mism days(first 8) {r['tile_detail']}")
    for s in ('ours', 'leader'):
        c = tot[s]
        L.append(f"  {s}: per game work cmds {c['work'] / 12:.0f}, actual busy {c['busy'] / 12:.0f}, moves {c['moves'] / 12:.0f}, "
                 f"present {c['present'] / 12:.0f}, unit-days total {c['unit_days']}, PICKUP {c['pickup'] / 12:.0f}, shed drops {c['shed_drop'] / 12:.0f}, "
                 f"structures built on shed tiles {c['struct_on_shed_tile']}, other work ops {c['odd_ops']}")
    (V.HERE / 'verify_rebuild.json').write_text(json.dumps(out, indent=1, default=str), encoding='utf-8')
    (V.HERE / 'verify_rebuild.txt').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('\n'.join(L))


if __name__ == '__main__':
    main()


