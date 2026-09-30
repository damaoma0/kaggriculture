"""Do Mother-Goose's NEW submissions (56331731 / 56331777) diverge in LAYOUT or only in micro? (offline, replays on disk)

For pairs of her games that share the same first k shops: is the board the same on the morning shop k+1 opens
(layout: what stands on which tile, weeds as empty), how many tiles differ, how the crop / animal COUNTS differ, and
is the action stream the same up to then (micro)? The same table for her old deterministic policy (584 compact tapes).
"""
import glob
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def label(t):
    if t == 'LOCKED':
        return ' L'
    if t is None or t.get('kind') == 'WEED':
        return ' .'
    if t.get('kind') == 'PLANT':
        return t['crop'][:2]
    if t.get('animal'):
        return t['animal'][:2].lower()
    return t['kind'][:2].lower()


def new_games():
    sub_of = {}
    for sub in (56331731, 56331777):
        f = ROOT / f'results/fresh/leaderboard_20260919/episodes_{sub}.json'
        if f.exists():
            for e in json.loads(f.read_text(encoding='utf-8'))['episodes']:
                sub_of[e['id']] = sub
    out = []
    for p in sorted(glob.glob(str(ROOT / 'data/leaders_20260919/*.json'))):
        r = json.load(open(p, encoding='utf-8'))
        names = r['info'].get('TeamNames') or []
        if not any('Mother' in (n or '') for n in names) or len(r['steps']) < 720:
            continue
        seat = next(i for i, n in enumerate(names) if 'Mother' in (n or ''))
        steps = r['steps']
        boards = [[label(t) for row in steps[d * 24][0]['observation']['farms'][seat]['tiles'] for t in row] for d in range(30)]
        acts = [json.dumps(steps[t + 1][seat].get('action') or {}, sort_keys=True) for t in range(719)]
        out.append(dict(ep=r['info'].get('EpisodeId'), sub=sub_of.get(r['info'].get('EpisodeId')), seat=seat,
                        shops=steps[719][0]['observation']['town']['unlocked_shops'], boards=boards, acts=acts))
    return out


def old_games():
    out = []
    for p in sorted(glob.glob(str(ROOT / 'data/mg_tapes/*/*.json.gz'))):
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        boards = [[(' .' if s[i:i + 2] == ' w' else s[i:i + 2]) for s in [''.join(b)] for i in range(0, 200, 2)] for b in t['boards']]
        out.append(dict(shops=t['shops'][30], boards=boards, acts=[json.dumps(a, sort_keys=True) for a in t['actions']], sub=t['submission'], seat=t['seat']))
    return out


def table(games, title, same_sub=True):
    print(f'\n{title}: {len(games)} games')
    print(f'{"same first k shops":>18} | {"pairs":>6} | {"same board":>10} | {"tiles that differ (median)":>26} | {"crop/animal COUNTS that differ (median)":>39} | {"same actions":>12}')
    for k in range(0, 6):
        day = 3 * (k + 1)
        groups = defaultdict(list)
        for g in games:
            groups[(tuple(g['shops'][:k]), g['sub'] if same_sub else 0)].append(g)
        n = same_b = same_a = 0
        ham, cnt = [], []
        for grp in groups.values():
            for i in range(len(grp)):
                for j in range(i + 1, len(grp)):
                    a, b = grp[i]['boards'][day], grp[j]['boards'][day]
                    n += 1
                    same_b += a == b
                    same_a += grp[i]['acts'][:day * 24] == grp[j]['acts'][:day * 24]
                    ham.append(sum(1 for x, y in zip(a, b) if x != y))
                    ca, cb = Counter(a), Counter(b)
                    cnt.append(sum(abs(ca[x] - cb[x]) for x in set(ca) | set(cb) if x not in (' .', ' L')))
        if n:
            ham.sort(); cnt.sort()
            print(f'{k:>18} | {n:>6} | {same_b / n:>10.0%} | {ham[len(ham) // 2]:>26} | {cnt[len(cnt) // 2]:>39} | {same_a / n:>12.0%}')


if __name__ == '__main__':
    new = new_games()
    print('new-policy games by submission:', dict(Counter(g['sub'] for g in new)))
    table(new, 'NEW submissions (pairs within the same submission)')
    table(old_games(), 'OLD policy, 584 tapes (pairs within the same submission)')
