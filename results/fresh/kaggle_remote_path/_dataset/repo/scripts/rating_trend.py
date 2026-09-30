"""Rating snapshot log + result trend by time window for our live submissions.
Appends the current publicScore of each submission to results/fresh/rating_log.jsonl and prints, per submission, the
win rate and mean margin in consecutive windows of its games (oldest first), with opponents' current-leaderboard band.
usage: rating_trend.py <sub> [<sub> ...] [--window 50]"""
import json, sys, time
from pathlib import Path
from kaggle.api.kaggle_api_extended import KaggleApi
sys.path.insert(0, str(Path(__file__).parent))
from track_submission import games, band, LB

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / 'results/fresh/rating_log.jsonl'


def main():
    args = sys.argv[1:]
    w = 50
    if '--window' in args:
        i = args.index('--window'); w = int(args[i + 1]); args = args[:i] + args[i + 2:]
    subs = [int(a) for a in args]
    api = KaggleApi(); api.authenticate()
    scores = {int(s.ref): s.public_score for s in api.competition_submissions('kaggriculture')}
    lb = {r['team_id']: float(r['score']) for r in json.loads(LB.read_text(encoding='utf-8'))}
    stamp = time.strftime('%Y-%m-%d %H:%M')
    with LOG.open('a', encoding='utf-8') as f:
        for s in subs:
            f.write(json.dumps(dict(t=stamp, sub=s, score=scores.get(s))) + chr(10))
    for s in subs:
        g = games(api, s)
        print(f'{s}: rating {scores.get(s)}  games {len(g)}')
        for k in range(0, len(g), w):
            part = g[k:k + w]
            strong = [x for x in part if (lb.get(x['opp_id']) or 0) >= 2500]
            print(f'   games {k + 1:4d}-{k + len(part):4d} ({part[0]["t"][:10]}..{part[-1]["t"][:10]}): '
                  f'{sum(x["res"] for x in part):g}-{len(part) - sum(x["res"] for x in part):g} '
                  f'({100 * sum(x["res"] for x in part) / len(part):.0f}%), margin {sum(x["margin"] for x in part) / len(part):+7.0f}; '
                  f'vs >=2500: {sum(x["res"] for x in strong):g}-{len(strong) - sum(x["res"] for x in strong):g}')


if __name__ == '__main__':
    main()
