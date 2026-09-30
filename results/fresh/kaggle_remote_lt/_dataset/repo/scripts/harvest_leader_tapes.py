"""Direction 2: for each current top team, find its best-scoring submission, download up to K completed
episodes, and keep only the compact tape (shop reveal order, that team's 719 recorded actions, rewards,
opponent). Raw replays (~32 MB) are deleted again; a compact tape is ~50 KB.

usage: harvest_leader_tapes.py <team_id>[,<team_id>...] [K=40]
Output: data/leader_tapes/<team_id>_<submission>/<episode>.json.gz  and an index.json per team.
"""
import gzip, io, json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KAGGLE = ROOT / '.venv/Scripts/kaggle.exe'
RAW = ROOT / 'data/leader_tapes/_raw'
OUTROOT = ROOT / 'data/leader_tapes'


def shop_seq(unlocked_by_day):
    seq, seen = [], 0
    for cur in unlocked_by_day:
        while len(cur) > seen:
            seq.append(cur[seen]); seen += 1
        if len(seq) >= 8:
            break
    return seq[:8]


def handle(job):
    outdir, team, eid = job
    out = outdir / f'{eid}.json.gz'
    if out.exists():
        return 'have'
    path = RAW / f'episode-{eid}-replay.json'
    RAW.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        subprocess.run([str(KAGGLE), 'competitions', 'replay', str(eid), '-p', str(RAW), '-q'],
                       capture_output=True, timeout=300)
        if not path.exists():
            return 'FAILED download'
    try:
        r = json.loads(path.read_text(encoding='utf-8'))
        steps = r['steps']
        if len(steps) < 720:
            return 'short'
        names = r['info'].get('TeamNames') or []
        seat = next((i for i, n in enumerate(names) if team.lower() in (n or '').lower()), None)
        if seat is None:
            return 'team not in replay'
        g = dict(episode=eid, seat=seat, seed=r['info']['seed'], names=names, rewards=r['rewards'],
                 shops=shop_seq([steps[min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(31)]),
                 actions=[steps[t + 1][seat].get('action') or {} for t in range(719)],
                 opp_actions=[steps[t + 1][1 - seat].get('action') or {} for t in range(719)])
        outdir.mkdir(parents=True, exist_ok=True)
        with gzip.open(out, 'wt', encoding='utf-8') as f:
            json.dump(g, f, separators=(',', ':'))
    finally:
        path.unlink(missing_ok=True)
    return 'ok'


def main():
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi(); api.authenticate()
    team_ids = [int(x) for x in sys.argv[1].split(',')]
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    lb = {r['team_id']: r for r in json.loads((ROOT / 'results/fresh/newphase_20260923/leaderboard_full.json').read_text(encoding='utf-8'))}
    for tid in team_ids:
        team = lb.get(tid, {}).get('team', str(tid))
        subs = api.competition_team_submissions(tid)
        def sc(s):
            try:
                return float(getattr(s, 'public_score', 0) or 0)
            except (TypeError, ValueError):
                return 0.0
        best = max(subs, key=sc)
        eps = [e for e in api.competition_list_episodes(int(best.id))
               if 'COMPLETED' in str(e.state) and len(e.agents or []) == 2]
        eps = eps[:K]
        outdir = OUTROOT / f'{tid}_{best.id}'
        print(f'{team} (id {tid}) best submission {best.id} score {sc(best)}: {len(eps)} episodes to fetch', flush=True)
        counts = {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            for st in pool.map(handle, [(outdir, team, e.id) for e in eps]):
                counts[st] = counts.get(st, 0) + 1
        print('   ', counts, flush=True)
        with io.open(outdir / 'index.json', 'w', encoding='utf-8') as f:
            json.dump(dict(team_id=tid, team=team, submission=int(best.id), score=sc(best),
                           episodes=[e.id for e in eps]), f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
