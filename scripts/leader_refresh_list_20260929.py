"""List the current top teams' submissions and completed episodes on Kaggle (listing only - no replay downloads): per
team and submission the score, date, completed 2-agent episodes, how many are already on disk (data/leader_tapes), and
how many were played against one of OUR submissions (MGT family). Writes the plan for a selective harvest.

usage: leader_refresh_list_20260929.py [--top 8] [--subs 3] [--out results/fresh/leader_refresh_20260929/listing.json]"""
import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--subs", type=int, default=3)
    ap.add_argument("--out", default="results/fresh/leader_refresh_20260929/listing.json")
    a = ap.parse_args()
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    ours = {int(s.ref if hasattr(s, "ref") else s.id) for s in api.competition_submissions("kaggriculture")}
    print("our submissions:", len(ours), sorted(ours)[-8:], flush=True)
    lb = api.competition_leaderboard_view("kaggriculture")[: a.top]
    have = set()
    for d in (ROOT / "data/leader_tapes").glob("*_*"):
        have.update(int(p.name.split(".")[0]) for p in d.glob("*.json.gz"))
    rows = []
    for r in lb:
        tid = int(r.team_id)
        subs = api.competition_team_submissions(tid)

        def sc(s):
            try:
                return float(getattr(s, "public_score", 0) or 0)
            except (TypeError, ValueError):
                return 0.0
        subs = sorted(subs, key=sc, reverse=True)[: a.subs]
        for s in subs:
            eps = [e for e in api.competition_list_episodes(int(s.id))
                   if "COMPLETED" in str(e.state) and len(e.agents or []) == 2]
            vs_ours = []
            for e in eps:
                opp = [int(getattr(ag, "submission_id", 0) or 0) for ag in (e.agents or [])]
                if any(o in ours for o in opp):
                    vs_ours.append(int(e.id))
            new = [int(e.id) for e in eps if int(e.id) not in have]
            rows.append(dict(team_id=tid, team=r.team_name, team_score=float(r.score), submission=int(s.id),
                             score=sc(s), date=str(getattr(s, "date", "")), episodes=len(eps), new=len(new),
                             new_ids=new, vs_ours=vs_ours))
            print(f"{r.team_name[:24]:24s} sub {s.id} score {sc(s):7.1f} episodes {len(eps):4d} new {len(new):4d} "
                  f"vs ours {len(vs_ours)}", flush=True)
            time.sleep(0.5)
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(ours=sorted(ours), rows=rows), indent=1))
    print("new episodes total:", sum(x["new"] for x in rows), "| vs ours:", sum(len(x["vs_ours"]) for x in rows), "->", out)


if __name__ == "__main__":
    main()
