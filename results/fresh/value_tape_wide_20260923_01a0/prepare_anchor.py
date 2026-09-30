"""Additional control-exact replay panel, motivated by frozen-opening failures.

No original cases are removed or retuned. Sample only episodes where the actual
opponent was our original m1 submission, then require native control equality.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import gc
import gzip
import hashlib
import json
import random
import sys
import time

OUT=Path(__file__).resolve().parent
ORIGINAL=56395605

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=True),encoding='utf-8')

def metadata():
    from kaggle.api.kaggle_api_extended import KaggleApi
    api=KaggleApi();api.authenticate()
    cache=OUT/'anchor_api/our_episodes.json'
    if cache.exists():episodes=json.loads(cache.read_text())['episodes']
    else:
        es=api.competition_list_episodes(ORIGINAL)
        episodes=[dict(id=int(e.id),created=str(e.create_time),state=str(e.state),
            agents=[dict(submission=int(a.submission_id),seat=int(a.index),reward=a.reward,
                team=a.team_name,team_id=a.team_id) for a in e.agents or []]) for e in es]
        write(cache,dict(fetched_utc=datetime.now(timezone.utc).isoformat(),episodes=episodes))
    existing={int(p.name.split('.')[0]) for p in (OUT/'recordings').glob('*.json.gz')}
    training={int(p.name.split('.')[0]) for p in (OUT/'payload/results/fresh/value_tape_followup_20260923').glob('*rival_library/*.json.gz')}
    pool=[e for e in episodes if 'COMPLETED' in e['state'] and len(e['agents'])==2
        and sum(a['submission']==ORIGINAL for a in e['agents'])==1 and e['id'] not in existing|training]
    # Team leaderboard score is an upper bound, never a substitute for the played
    # submission's rating. Restrict lookups to possibly eligible teams.
    board=json.loads((OUT/'leaderboard_snapshot.json').read_text())['rows']
    eligible_teams={r['team_id'] for r in board if r['score']>=2750}
    teams=sorted(set(a['team_id'] for e in pool for a in e['agents'] if a['submission']!=ORIGINAL)
                 & eligible_teams)
    scores={}
    for team in teams:
        f=OUT/'anchor_api'/f'team-{team}.json'
        earlier=OUT/'api_metadata'/f'team-{team}.json'
        if f.exists():rows=json.loads(f.read_text())['submissions']
        elif earlier.exists():rows=json.loads(earlier.read_text())['submissions']
        else:
            try:
                subs=api.competition_team_submissions(team)
                rows=[dict(id=int(s.id),score=float(s.public_score),date=str(s.date_submitted))
                    for s in subs if s.public_score is not None]
                write(f,dict(fetched_utc=datetime.now(timezone.utc).isoformat(),submissions=rows))
                time.sleep(.75)
            except Exception as exc:
                response=getattr(exc,'response',None)
                status=getattr(response,'status_code',None)
                retry_after=response.headers.get('Retry-After') if response is not None else None
                print('API_STOP '+json.dumps(dict(team=team,status=status,retry_after=retry_after,error_type=type(exc).__name__)),flush=True)
                raise
        scores.update({r['id']:r['score'] for r in rows})
    eligible=[]
    for e in pool:
        opp=next(a for a in e['agents'] if a['submission']!=ORIGINAL)
        score=scores.get(opp['submission'])
        if score is not None and 2750<=score<=3000:
            eligible.append(dict(episode=e,opponent=opp,rating=score))
    seed=json.loads((OUT/'random_design.json').read_text())['master_seed'] ^ 0x616e63686f72
    rng=random.Random(seed);selected=[]
    for opp_seat in (0,1):
        group=sorted((r for r in eligible if r['opponent']['seat']==opp_seat),key=lambda r:r['episode']['id'])
        rng.shuffle(group);selected+=group[:8]
    assert selected,dict(eligible=len(eligible),selected=len(selected))
    design=dict(master_seed=seed,original_submission=ORIGINAL,eligible=eligible,selected=selected,
        protocol='Additional panel of up to 16 pairs, sampled without reward filtering after original 32-replay panel exposed collapsed openings. Only actual original-m1 games, opponent specific active-submission rating in [2750,3000] at fetch. Up to eight games in each own seat; use all available if fewer. Original cases retained. Native control must reproduce both recorded cash, hourly physical boards and private stocks before candidate evaluation. No policy tuning.')
    target=OUT/'anchor_design.json'
    if target.exists():assert json.loads(target.read_text())==design
    else:write(target,design)
    print('ANCHOR_DESIGN '+json.dumps(dict(original_episodes=len(episodes),eligible=len(eligible),
        selected=len(selected),teams=len(set(r['opponent']['team_id'] for r in selected)),
        ratings=[r['rating'] for r in selected])),flush=True)

def downloads():
    from kaggle.api.kaggle_api_extended import KaggleApi
    api=KaggleApi();api.authenticate()
    design=json.loads((OUT/'anchor_design.json').read_text());rawdir=OUT/'anchor_download';rawdir.mkdir(exist_ok=True)
    for row in design['selected']:
        ep=row['episode'];eid=ep['id'];target=OUT/'recordings'/f'{eid}.json.gz'
        if target.exists():continue
        raw=rawdir/f'episode-{eid}-replay.json'
        if not raw.exists():api.competition_episode_replay(eid,str(rawdir),quiet=True)
        r=json.loads(raw.read_text(encoding='utf-8'));steps=r['steps'];assert len(steps)==720
        game=dict(episode=eid,seed=r['info']['seed'],opponent_seat=row['opponent']['seat'],
            opponent=row['opponent']['team'],submission=dict(id=row['opponent']['submission'],score=row['rating']),
            metadata=ep,names=r['info'].get('TeamNames'),rewards=r['rewards'],configuration=r['configuration'],
            raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
            shops=[steps[min(719,d*24)][0]['observation']['town']['unlocked_shops'] for d in range(31)],
            actions=[[steps[t+1][s].get('action') or {} for t in range(719)] for s in range(2)],
            observations=[dict(step=t,seats=[steps[t][s]['observation'] for s in range(2)])
                for t in sorted(set([0,719]+list(range(24,719,24))))])
        with gzip.open(target,'wt',encoding='utf-8') as f:json.dump(game,f,separators=(',',':'))
        assert raw.resolve().parent==rawdir.resolve();raw.unlink()
        del r,steps,game;gc.collect()
        print('FETCHED_ANCHOR '+str(eid),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['metadata','downloads']);args=p.parse_args()
    {'metadata':metadata,'downloads':downloads}[args.mode]()
