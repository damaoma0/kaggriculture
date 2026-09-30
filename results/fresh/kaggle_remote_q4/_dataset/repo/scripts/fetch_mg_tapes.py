"""Build a compact tape library from Mother-Goose's games: download a replay, keep only what a tape router
needs, delete the raw file.

Kept per game (data/mg_tapes/<submission>/<episode>.json.gz): episode, submission, seat, seed, opponent
(team, submission, rating), rewards, shops by day (31 entries), her 719 actions, her board labels and cash at
every day start. A raw replay is ~30 MB; a compact tape ~60 KB, so disk use stays flat.

Replays already on disk (data/leaders_20260917, data/leaders_20260919) are compacted without downloading.
Usage: python fetch_mg_tapes.py <submission> [max_new_downloads=50] [newest|oldest]
"""
import gzip, json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from market_corpus import ROOT
from extract_mg_events import tile_label

OUT = ROOT / 'data/mg_tapes'
RAW = ROOT / 'data/mg_tapes/_raw'
KAGGLE = ROOT / '.venv/Scripts/kaggle.exe'
MG_TEAM = 16730612
LOCAL = [ROOT / 'data/leaders_20260917', ROOT / 'data/leaders_20260919']


def episode_list(sub):
    for d in ('leaderboard_20260919', 'leaderboard_20260918'):
        p = ROOT / f'results/fresh/{d}/episodes_{sub}.json'
        if p.exists():
            return json.loads(p.read_text(encoding='utf-8'))['episodes']
    raise SystemExit(f'no episode list for {sub}')


def compact(path, episode, sub):
    replay = json.loads(open(path, encoding='utf-8').read())
    agents = sorted(episode['agents'], key=lambda a: a.get('index', 0))
    seat = next(i for i, a in enumerate(agents) if a.get('submissionId') == sub)
    opp = agents[1 - seat]
    steps = replay['steps']
    if len(steps) < 720:
        return None
    shops = [steps[min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(31)]
    boards, cash = [], []
    for d in range(30):
        farm = steps[d * 24][0]['observation']['farms'][seat]
        boards.append([''.join(f'{tile_label(t):>2s}' for t in row) for row in farm['tiles']])
        cash.append(farm['money'])
    actions = [steps[t + 1][seat]['action'] or {} for t in range(719)]
    return dict(episode=episode['id'], submission=sub, seat=seat, seed=replay['info'].get('seed'),
                created=episode.get('createTime'), opponent=dict(team=opp.get('teamId'), submission=opp.get('submissionId'),
                                                                 rating=opp.get('initialScore')),
                rating=agents[seat].get('initialScore'), rewards=replay['rewards'], shops=shops, boards=boards, cash=cash,
                actions=actions)


def handle(episode, sub):
    eid = episode['id']
    out = OUT / str(sub) / f'{eid}.json.gz'
    if out.exists():
        return eid, 'have'
    local = next((d / f'episode-{eid}-replay.json' for d in LOCAL if (d / f'episode-{eid}-replay.json').exists()), None)
    path, downloaded = local, False
    if path is None:
        RAW.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run([str(KAGGLE), 'competitions', 'replay', str(eid), '-p', str(RAW), '-q'], timeout=240, check=True,
                           capture_output=True)
        except Exception as exc:
            return eid, f'FAILED download {type(exc).__name__}'
        path, downloaded = RAW / f'episode-{eid}-replay.json', True
        if not path.exists():
            return eid, 'FAILED missing file'
    try:
        tape = compact(path, episode, sub)
    except Exception as exc:
        tape = None
        err = f'FAILED compact {type(exc).__name__}: {exc}'
    else:
        err = 'FAILED short replay'
    if downloaded:
        path.unlink(missing_ok=True)
    if tape is None:
        return eid, err
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, 'wt', encoding='utf-8') as f:
        json.dump(tape, f, separators=(',', ':'))
    return eid, 'downloaded' if downloaded else 'local'


def main():
    sub = int(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    order = sys.argv[3] if len(sys.argv) > 3 else 'newest'
    eps = [e for e in episode_list(sub) if e.get('state') == 'COMPLETED' and len(e.get('agents', [])) == 2
           and (next((a for a in e['agents'] if a.get('submissionId') == sub), {}).get('initialScore') or 0) >= 2500]
    eps.sort(key=lambda e: e['createTime'], reverse=(order == 'newest'))
    have = {p.name.split('.')[0] for p in (OUT / str(sub)).glob('*.json.gz')} if (OUT / str(sub)).exists() else set()
    local_ids = {p.name.split('-')[1] for d in LOCAL for p in d.glob('episode-*-replay.json')}
    todo, budget = [], limit
    for e in eps:
        if str(e['id']) in have:
            continue
        if str(e['id']) in local_ids:
            todo.append(e)
        elif budget > 0:
            todo.append(e); budget -= 1
    print(f'submission {sub}: {len(eps)} rated episodes, {len(have)} already compact, {len(todo)} to process', flush=True)
    counts = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(handle, e, sub) for e in todo]
        for f in as_completed(futures):
            eid, status = f.result()
            counts[status.split(' ')[0]] = counts.get(status.split(' ')[0], 0) + 1
            if status.startswith('FAILED'):
                print(eid, status, flush=True)
    print('done', counts, flush=True)


if __name__ == '__main__':
    main()
