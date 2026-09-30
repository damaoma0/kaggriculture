"""Fetch the whole Kaggriculture leaderboard (rank, team_id, team, score) to
results/fresh/newphase_20260923/leaderboard_full.json. Uses the kagglesdk client directly so
the pagination token can be read (the CLI wrapper only prints it)."""
import io, json
from pathlib import Path
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.competitions.types.competition_api_service import ApiGetLeaderboardRequest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/newphase_20260923/leaderboard_full.json'


def main():
    api = KaggleApi(); api.authenticate()
    rows, token, rank = [], None, 0
    while True:
        with api.build_kaggle_client() as kaggle:
            req = ApiGetLeaderboardRequest()
            req.competition_name = 'kaggriculture'
            api._set_paging(req, 200, token)
            resp = kaggle.competitions.competition_api_client.get_leaderboard(req)
        subs = resp.submissions or []
        for r in subs:
            rank += 1
            rows.append(dict(rank=rank, team_id=r.team_id, team=r.team_name, score=r.score, date=str(r.submission_date)))
        token = resp.next_page_token
        if not token or not subs:
            break
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with io.open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False)
    print(len(rows), 'teams')


if __name__ == '__main__':
    main()
