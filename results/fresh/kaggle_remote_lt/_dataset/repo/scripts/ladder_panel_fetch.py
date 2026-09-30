"""Build the LADDER PANEL: every recorded ladder game of one of our submissions, compacted to what a counterfactual
needs (seed, shops by day, the OPPONENT's 719 recorded actions, both recorded results, names, seats).

A raw replay is ~32 MB and downloads in ~2 s; the compact game is ~50 KB (data/ladder_panel/<submission>/<episode>.json.gz)
and the raw file is deleted again. Games already compacted are skipped, so re-running adds the new ladder games.
usage: ladder_panel_fetch.py [submission=56368334] [team="Ghost Rule"]
"""
import gzip
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KAGGLE = ROOT / '.venv/Scripts/kaggle.exe'
RAW = ROOT / 'data/ladder_panel/_raw'


def episodes(sub):
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    out = []
    for e in api.competition_list_episodes(sub):
        agents = [dict(submission=a.submission_id, index=a.index, reward=a.reward, team=a.team_name, team_id=a.team_id) for a in (e.agents or [])]
        out.append(dict(id=e.id, created=str(e.create_time), state=str(e.state), agents=agents))
    return out


def handle(job):
    sub, team, e = job
    out = ROOT / f'data/ladder_panel/{sub}/{e["id"]}.json.gz'
    if out.exists():
        return e['id'], 'have'
    local = ROOT / f'data/ladder_t10/episode-{e["id"]}-replay.json'
    path = local if local.exists() else RAW / f'episode-{e["id"]}-replay.json'
    if not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(KAGGLE), 'competitions', 'replay', str(e['id']), '-p', str(RAW), '-q'], capture_output=True, timeout=300)
        if not path.exists():
            return e['id'], 'FAILED download'
    try:
        r = json.loads(path.read_text(encoding='utf-8'))
        steps = r['steps']
        if len(steps) < 720:
            return e['id'], 'short replay'
        names = r['info'].get('TeamNames') or []
        seat = next(i for i, n in enumerate(names) if team.lower() in (n or '').lower())
        game = dict(episode=e['id'], created=e['created'], submission=sub, seat=seat, seed=r['info']['seed'], names=names,
                    rewards=r['rewards'], opponent=next((a for a in e['agents'] if a['submission'] != sub), None),
                    shops=[steps[min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(31)],
                    opp_actions=[steps[t + 1][1 - seat].get('action') or {} for t in range(719)],
                    our_actions=[steps[t + 1][seat].get('action') or {} for t in range(719)])
        out.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(out, 'wt', encoding='utf-8') as f:
            json.dump(game, f, separators=(',', ':'))
    finally:
        if path != local:
            path.unlink(missing_ok=True)
    return e['id'], 'ok'


def main():
    sub = int(sys.argv[1]) if len(sys.argv) > 1 else 56368334
    team = sys.argv[2] if len(sys.argv) > 2 else 'Ghost Rule'
    eps = [e for e in episodes(sub) if 'COMPLETED' in e['state'] and len(e['agents']) == 2
           and sum(1 for a in e['agents'] if a['submission'] == sub) == 1]
    print(f'{len(eps)} completed ladder games of {sub}', flush=True)
    counts = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for ep, status in pool.map(handle, [(sub, team, e) for e in eps]):
            counts[status] = counts.get(status, 0) + 1
    print(counts)


if __name__ == '__main__':
    main()
