"""Skeptic check: list TeamNames of every stored DSM replay by string scan (no json.load of steps).
Writes verify_chains_teams.json. Stored data only."""
import glob, json, os, re, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
out = {}
cnt = collections.Counter()
for fp in sorted(glob.glob(os.path.join(ROOT, 'data', 'dsm_replays', 'episode-*-replay.json'))):
    with open(fp, encoding='utf-8') as f:
        s = f.read()
    m = re.search(r'"TeamNames"\s*:\s*(\[[^\]]*\])', s)
    names = json.loads(m.group(1)) if m else None
    ep = os.path.basename(fp).split('-')[1]
    out[ep] = names
    for n in (names or []):
        cnt[n] += 1
    del s
print(len(out), 'files')
print('files without TeamNames:', [k for k, v in out.items() if v is None])
print('name counts (top 15):', cnt.most_common(15))
print('files with DSM seat count:', collections.Counter(sum(1 for n in (v or []) if n == 'DSM') for v in out.values()))
print('names containing dsm (any case):', sorted({n for n in cnt if 'dsm' in n.lower()}))
json.dump(out, open(os.path.join(HERE, 'verify_chains_teams.json'), 'w'), indent=0)
