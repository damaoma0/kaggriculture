"""Skeptic check: 'COLLECT reached by walking straight from the shed' with and without animals standing ON a shed tile
(trivially straight), from the reviewed events.jsonl.gz (whose per-game records matched verify_chains_main.py on 7
seat-games). Also collect->fertilize lag for direct chains incl. on-shed-tile animals. Stored data only."""
import gzip, json, os, statistics as stt
HERE = os.path.dirname(os.path.abspath(__file__))
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))
dsh = lambda p: min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED)
n = s = n1 = s1 = 0
lag_rep, lag_all = [], []
with gzip.open(os.path.join(HERE, 'events.jsonl.gz'), 'rt', encoding='utf-8') as f:
    for line in f:
        r = json.loads(line)
        for c in r['collect']:
            d = dsh(c['A'])
            n += 1; s += c['since_shed'] == d
            if d > 0:
                n1 += 1; s1 += c['since_shed'] == d
        for x in r['fert']:
            if x['src'] == 'field':
                if not x['shed_between']:
                    lag_rep.append(x['t'] - x['tA']); lag_all.append(x['t'] - x['tA'])
                elif dsh(x['A']) == 0:
                    lag_all.append(x['t'] - x['tA'])
print(f'straight: all collects {s}/{n} = {s/n:.3f}; excluding animals on a shed tile {s1}/{n1} = {s1/n1:.3f}')
print(f'lag direct as reported: n {len(lag_rep)} mean {sum(lag_rep)/len(lag_rep):.2f} median {stt.median(lag_rep)}; '
      f'incl. on-shed-tile animals: n {len(lag_all)} mean {sum(lag_all)/len(lag_all):.2f} median {stt.median(lag_all)}')
