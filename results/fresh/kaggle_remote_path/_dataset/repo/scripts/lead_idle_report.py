"""Idle passes vs dropped maintenance jobs, from the executor's idle trace (CFG idle_trace; one jsonl per game).

usage: lead_idle_report.py <trace_dir> [<trace_dir> ...]
Dropped job = a job of a fresh sem_maintenance solve at hour 23 (value > 0, non-optional) that hour 23 does not do;
its value is the module's coin value of doing it today. Each dropped job is attributed to ONE reason:
  not_in_tasks      the executor's task list at hour 23 does not contain that command on the tile
                    (stale job cache / legacy rules for new assets / a plan job occupying the tile)
  no_idle           no unit passed idle while the job was open that day (crew capacity)
  otherwise the most frequent reason among the idle passes that coexisted with it:
  taken             another unit held the job (reserved) and did not finish it
  lack:<items>      the item is neither carried nor in the shed (no pickup possible)
  plant_late        plant pipeline cannot finish today
  valid             the idle unit had a valid cost for it (dispatcher should have taken it)
Also: idle passes per game by what that unit saw (all open tasks taken / lacking items / nothing open).
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def main():
    files = [f for d in sys.argv[1:] for f in sorted(Path(d).glob('*.jsonl'))]
    games = len(files)
    val = Counter()
    cnt = Counter()
    by_cmd = Counter()
    by_kind = Counter()
    reach = Counter()
    idle_kind = Counter()
    idle_late = Counter()
    noop = Counter()
    days_seen = 0
    work = Counter()
    dropped_total = 0.0
    examples = defaultdict(list)
    for f in files:
        for line in open(f, encoding='utf-8'):
            r = json.loads(line)
            days_seen += 1
            for j in r['dropped']:
                v = j['value']
                dropped_total += v
                by_cmd[j['cmd']] += v
                by_kind[j['kind']] += v
                if not j['in_task']:
                    key = 'not_in_tasks' + (' (plan job on tile)' if str(j['idx']) in r['plan_open23'] else '')
                elif not j['idle']:
                    key = 'no_idle'
                else:
                    rc = Counter(p[2] for p in j['idle'])
                    key = rc.most_common(1)[0][0]
                    # reachable: some idle pass could have walked there and done it before the day ended
                    ok = any(p[3] is not None and p[2] in ('taken', 'valid') and p[0] + p[3] + 1 <= 23 for p in j['idle'])
                    reach[(key, ok)] += v
                    if key == 'taken':
                        # the idle unit was nearer than the job's owner at some pass (a hand-over would have helped)
                        nearer = any(p[2] == 'taken' and len(p) > 5 and p[5] is not None and p[3] < p[5]
                                     and p[0] + p[3] + 1 <= 23 for p in j['idle'])
                        reach[('taken: idle nearer than owner and reachable', nearer)] += v
                val[key] += v
                cnt[key] += 1
                if len(examples[key]) < 4 and v >= 30:
                    examples[key].append((f.name[:18], r['day'], j['idx'], j['cmd'], j['kind'], v, j['first_open'],
                                          j['idle'][:3]))
            for h, u, pos, inv, c, nopen in r['idle']:
                if nopen == 0:
                    k = 'nothing open'
                elif set(c) == {'taken'}:
                    k = 'all open taken'
                elif any(x.startswith('lack') for x in c) and 'valid' not in c:
                    k = 'lack items (rest taken)'
                elif 'valid' in c:
                    k = 'valid task left'
                else:
                    k = '+'.join(sorted(c))
                idle_kind[k] += 1
                if h >= 18:
                    idle_late[k] += 1
            for b in r['noop']:
                noop[','.join(b['ops'])] += 1
    g = max(1, games)
    for f in files:
        for line in open(f, encoding='utf-8'):
            r = json.loads(line)
            if 9 <= r['day'] <= 26 and 'work' in r:
                work.update(r['work'])
                work['unit_steps'] += 24 * r['n']
    if work:
        tot = work['unit_steps']
        print('days 9-26 unit-steps per game %.0f: ' % (tot / g) + ', '.join(
            '%s %.1f%%' % (k, 100 * v / tot) for k, v in sorted(work.items()) if k not in ('unit_steps', 'opval')))
        print('value of executed maintenance ops per game (days 9-26): %.0f' % (work['opval'] / g))
    print(f'{games} games, {days_seen} day records; dropped job value per game {dropped_total / g:,.0f}')
    print('\ndropped value per game by reason (jobs per game):')
    for k, v in val.most_common():
        print(f'  {k:32s} {v / g:8,.0f}  ({cnt[k] / g:5.1f})')
    print('\n  of which reachable by an idle unit before 23h (taken / valid only):')
    for (k, ok), v in sorted(reach.items()):
        print(f'    {k:28s} reachable={ok}: {v / g:8,.0f}')
    print('\ndropped value per game by command:', {k: round(v / g) for k, v in by_cmd.most_common()})
    print('dropped value per game by job kind:', {k: round(v / g) for k, v in by_kind.most_common()})
    print('\nidle passes per game by what the idle unit saw (all hours / hours >= 18):')
    for k, v in idle_kind.most_common():
        print(f'  {k:32s} {v / g:7.1f} / {idle_late[k] / g:7.1f}')
    print('\nat-tile no-op passes per game by the tile ops:', {k: round(v / g, 1) for k, v in noop.most_common(8)})
    print('\nexamples:')
    for k, ex in examples.items():
        for e in ex:
            print(' ', k, e)


if __name__ == '__main__':
    main()
