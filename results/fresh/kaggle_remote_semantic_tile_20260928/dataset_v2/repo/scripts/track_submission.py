"""Ladder record of one submission, with the same count of first games of reference submissions for comparison.
Uses the Kaggle episodes API (results, opponent team) and the saved full leaderboard for opponent ratings (CURRENT
ratings, not at-game-time: the API has no per-game rating; see scripts/analyze_ladder_ratings_seats.py).
usage: track_submission.py <sub> [ref_sub ...]"""
import json, sys, time
from pathlib import Path
from kaggle.api.kaggle_api_extended import KaggleApi

ROOT = Path(__file__).resolve().parents[1]
LB = ROOT / 'results/fresh/newphase_20260923/leaderboard_full.json'


def games(api, sub):
    out = []
    for e in api.competition_list_episodes(sub):
        ag = [a for a in (e.agents or [])]
        me = next((a for a in ag if a.submission_id == sub), None)
        op = next((a for a in ag if a.submission_id != sub), None)
        if me is None or op is None or me.reward is None or op.reward is None:
            continue
        out.append(dict(t=str(e.create_time), res=1 if me.reward > op.reward else (0 if me.reward < op.reward else 0.5),
                        margin=me.reward - op.reward, opp=op.team_name, opp_id=op.team_id))
    return sorted(out, key=lambda g: g['t'])


def band(r):
    return 'unrated' if r is None else ('3000+' if r >= 3000 else '2750-3000' if r >= 2750 else '2500-2750' if r >= 2500 else '<2500')


def main():
    api = KaggleApi(); api.authenticate()
    lb = {r['team_id']: float(r['score']) for r in json.loads(LB.read_text(encoding='utf-8'))}
    subs = [int(s) for s in sys.argv[1:]]
    main_games = games(api, subs[0])
    n = len(main_games)
    print(f'{time.strftime("%Y-%m-%d %H:%M")}  submission {subs[0]}: {n} games')
    for s in subs:
        g = games(api, s)[:n]
        w = sum(x['res'] for x in g)
        by = {}
        for x in g:
            b = band(lb.get(x['opp_id']))
            by.setdefault(b, [0, 0])
            by[b][0] += x['res']; by[b][1] += 1
        bands = '  '.join(f'{b} {v[0]:g}-{v[1] - v[0]:g}' for b, v in sorted(by.items()))
        print(f'  {s}: first {len(g)} games {w:g}-{len(g) - w:g} ({100 * w / max(1, len(g)):.0f}%), mean margin '
              f'{sum(x["margin"] for x in g) / max(1, len(g)):+.0f} | {bands}')


if __name__ == '__main__':
    main()
