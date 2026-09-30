"""Download recent replays of Mother-Goose's two new submissions (56331731, 56331777) into
data/leaders_20260919/ and write results/fresh/leader_segments/sample_20260919.json in the same shape as
sample.json ({'sample': [{'id', 'agents': [{'sub', 'team', 'reward', 'initial', 'updated'}]}]}).

Selection: the most recent N completed two-agent episodes of each submission (recent games are the ones most
likely to face the newest public agents). Each download has a timeout; failures are reported, not retried.
Usage: python fetch_mg_new.py [n_first=30] [n_second=12]
"""
import json, subprocess, sys
from market_corpus import ROOT

SUBS = (56331731, 56331777)
OUT = ROOT / 'data/leaders_20260919'
LB = ROOT / 'results/fresh/leaderboard_20260919'
KAGGLE = ROOT / '.venv/Scripts/kaggle.exe'


def main():
    counts = (int(sys.argv[1]) if len(sys.argv) > 1 else 30, int(sys.argv[2]) if len(sys.argv) > 2 else 12)
    OUT.mkdir(parents=True, exist_ok=True)
    sample = []
    for sub, n in zip(SUBS, counts):
        d = json.loads((LB / f'episodes_{sub}.json').read_text(encoding='utf-8'))
        eps = [e for e in d['episodes'] if e.get('state') == 'COMPLETED' and len(e.get('agents', [])) == 2]
        eps.sort(key=lambda e: e['createTime'], reverse=True)
        for e in eps[:n]:
            eid = e['id']
            path = OUT / f'episode-{eid}-replay.json'
            if not path.exists():
                try:
                    subprocess.run([str(KAGGLE), 'competitions', 'replay', str(eid), '-p', str(OUT), '-q'],
                                   timeout=180, check=True, capture_output=True)
                except Exception as exc:
                    print(f'FAILED {eid}: {type(exc).__name__}', flush=True)
                    continue
            if not path.exists():
                found = list(OUT.glob(f'*{eid}*'))
                print(f'MISSING {eid}: files {found}', flush=True)
                continue
            agents = sorted(e['agents'], key=lambda a: a.get('index', 0))
            sample.append(dict(id=eid, created=e['createTime'], agents=[
                dict(sub=a.get('submissionId'), team=a.get('teamId'), reward=a.get('reward'),
                     initial=a.get('initialScore'), updated=a.get('updatedScore')) for a in agents]))
            print(f'ok {eid} sub {sub} ({path.stat().st_size // 1_000_000} MB)', flush=True)
    (ROOT / 'results/fresh/leader_segments/sample_20260919.json').write_text(json.dumps({'sample': sample}), encoding='utf-8')
    print(f'done: {len(sample)} replays')


if __name__ == '__main__':
    main()
