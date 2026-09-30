"""Bounded read-only leaderboard snapshot; no replay downloads or submissions."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/leader_library_refresh_20260922'

if __name__ == '__main__':
    if '--child' in sys.argv:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        rows = api.competition_leaderboard_view('kaggriculture', page_size=5)
        values = [{k: str(getattr(r, k, None)) for k in ['team_id', 'team_name', 'rank', 'score']} for r in rows]
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'leaderboard.json').write_text(json.dumps(values, indent=2), encoding='utf-8')
        print(json.dumps(values))
        inventory = []
        teams = [(int(r['team_id']), r['team_name']) for r in values[:3]] + [(16730612, 'Unknown Mother-Goose')]
        for team_id, team_name in teams:
            subs = api.competition_team_submissions(team_id)
            detail = [{k: str(getattr(s, k, None)) for k in ('id', 'date_submitted', 'public_score')} for s in subs]
            if not subs:
                inventory.append(dict(team_id=team_id, team=team_name, submissions=[]))
                continue
            def score(s):
                try:
                    return float(getattr(s, 'public_score', 0) or 0)
                except (ValueError, TypeError):
                    return 0
            chosen = max(subs, key=score)
            eps = api.competition_list_episodes(int(chosen.id))
            complete = [e for e in eps if 'COMPLETED' in str(e.state)]
            item = dict(team_id=team_id, team=team_name, submissions=detail, selected_submission=int(chosen.id),
                        api_returned_episodes=len(eps), api_returned_completed=len(complete),
                        completed_episode_ids=[e.id for e in complete],
                        note='Counts describe the API response window, not guaranteed full history. Replays not downloaded.')
            inventory.append(item)
            (OUT / 'inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
            print(json.dumps({k:v for k,v in item.items() if k != 'completed_episode_ids'}), flush=True)
    else:
        try:
            p = subprocess.run([sys.executable, str(Path(__file__)), '--child'], capture_output=True, text=True, timeout=35)
            print(p.stdout[-4000:])
            print('exit', p.returncode)
            if p.returncode:
                print('Error class:', p.stderr.splitlines()[-1][:200] if p.stderr else 'unknown')
        except subprocess.TimeoutExpired:
            print('Current leaderboard request timed out after 35 seconds; no fresh ranking verified.')
