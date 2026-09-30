"""What do the leaders put on the fourth quadrant (SE) after buying it, and how many hands do they hire around it?
usage: leader_se_usage.py"""
import gzip, json, glob, collections, statistics as st
from pathlib import Path
NAMES = {'16623559': 'DECEM', '16730612': 'MG', '16770421': 'Vadim', '16732748': 'DSM'}
SE = [y * 10 + x for x in range(5, 10) for y in range(5, 10)]


def lab(b):
    if isinstance(b, list) and b and len(b[0]) == 2:
        return b
    s = ''.join(b)
    return [s[i:i + 2] for i in range(0, len(s), 2)]


for t, name in NAMES.items():
    comp = collections.Counter(); n = 0; hands_before = []; hands_after = []; hands_no = []
    for f in glob.glob(f'data/leader_semantics/{t}/*.json.gz'):
        g = json.load(gzip.open(f, 'rt'))
        L = [lab(d['board']) for d in g['days']]
        se_day = next((d for d in range(30) if all(L[d][j] != ' L' for j in SE)), None)
        hp = [d['labour']['hands_present'] for d in g['days']]
        if se_day is None:
            hands_no.append(st.mean(hp[12:28])); continue
        n += 1
        for d in range(se_day + 1, 29):
            comp.update(L[d][j] for j in SE)
        hands_before.append(st.mean(hp[6:se_day])); hands_after.append(st.mean(hp[se_day:28]))
    tot = sum(comp.values()) or 1
    print(f"{name:6s} SE games {n}: SE tile-days by label (share) " + ', '.join(f"{k.strip() or 'empty'} {v / tot:.0%}" for k, v in comp.most_common(7)))
    if hands_before:
        print(f"        hands/day days 6..SE {st.mean(hands_before):.1f} -> SE..27 {st.mean(hands_after):.1f}" + (f" | games without SE, days 12-27: {st.mean(hands_no):.1f}" if hands_no else ''))
