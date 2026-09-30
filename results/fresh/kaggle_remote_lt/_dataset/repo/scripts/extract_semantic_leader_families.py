"""Verify other 3000+ leader families through the full engine, serially."""
from pathlib import Path
import gc,gzip,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'results/fresh/tape_margin_20260924_01a0/payload/vendor'))
from extract_opening_jobs_20260924 import extract


def main():
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    from kaggle_environments.utils import structify
    from evaluate_boards import Ledger
    from collections import defaultdict
    folder=ROOT/'results/fresh/leader_opening_review_20260924_01a0'
    study=json.loads((ROOT/'results/fresh/semantic_architecture_20260924/study.json').read_text(encoding='utf8'))
    snap=json.loads((folder/'snapshot.json').read_text(encoding='utf8'))
    benchmark=json.loads((ROOT/'data/ladder_panel/p2750/index.json').read_text(encoding='utf8'))['games']
    existing={(d['episode'],d['seat']) for d in study['donors']}
    allowed={int(k):v for k,v in study['eligible_submissions'].items()}
    wanted=defaultdict(dict)
    for team in snap['inventory']:
        for sub,episodes in team['episodes'].items():
            for episode in episodes:
                if str(episode['id']) in benchmark:continue
                if not (folder/'replays'/f"episode-{episode['id']}-replay.json").exists():continue
                for agent in episode['agents']:
                    key=(int(episode['id']),int(agent['seat']))
                    submission=agent.get('submission_id')
                    if submission in allowed and key not in existing:
                        wanted[key[0]][key[1]]=submission
    out=ROOT/'results/fresh/semantic_architecture_20260924/leader_families';out.mkdir(parents=True,exist_ok=True)
    index_path=out/'index.json'
    index=json.loads(index_path.read_text()) if index_path.exists() else []
    done={(r['episode'],r['seat']) for r in index}
    for eid,seats in sorted(wanted.items()):
        if all((eid,s) in done for s in seats):continue
        result=extract(folder/'replays'/f'episode-{eid}-replay.json',E,structify,Ledger,'3000_plus_family')
        if result['transitions']!=719:raise ValueError('incomplete_replay')
        for seat,sub in seats.items():
            if (eid,seat) in done:continue
            trace=dict(episode=eid,seat=seat,team=result['teams'][seat],submission=sub,
                source_sha256=result['replay_sha256'],source='3000_plus_family',
                actions=result['actions'][str(seat)],market_success_by_order=result['market_success_by_order'][str(seat)],
                daily=[d for d in result['daily'] if d['seat']==seat],jobs=result['jobs_by_seat'][str(seat)],
                shops_by_day=result['shops_by_day'])
            path=out/f'trace-{eid}-seat{seat}.json.gz'
            with gzip.open(path,'wt',encoding='utf8') as f:json.dump(trace,f,separators=(',',':'))
            index.append(dict(episode=eid,seat=seat,team=trace['team'],submission=sub,path=path.name,
                source_sha256=trace['source_sha256'],trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),transitions=719))
            done.add((eid,seat))
        index_path.write_text(json.dumps(index,indent=2),encoding='utf8')
        print(json.dumps(dict(episode=eid,seats=seats,verified_transitions=719)),flush=True)
        del result;gc.collect()


if __name__=='__main__':main()
