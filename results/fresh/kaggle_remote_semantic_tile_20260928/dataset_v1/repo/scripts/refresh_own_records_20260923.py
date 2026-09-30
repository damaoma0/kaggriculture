"""Incremental read-only Kaggle refresh with an explicit new-game manifest."""
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from kaggle.api.kaggle_api_extended import KaggleApi

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/records_refresh_20260923'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    api = KaggleApi()
    api.authenticate()
    manifest = dict(fetched=datetime.now(timezone.utc).isoformat(), submissions={})
    for sub in (56395605, 56368334):
        folder = ROOT / f'data/ladder_panel/{sub}'
        folder.mkdir(parents=True, exist_ok=True)
        eps = [dict(id=e.id, created=str(e.create_time), state=str(e.state),
                    agents=[dict(submission=a.submission_id, index=a.index, reward=a.reward,
                                 team=a.team_name, team_id=a.team_id) for a in (e.agents or [])])
               for e in api.competition_list_episodes(sub)]
        (OUT / f'inventory_{sub}.json').write_text(json.dumps(eps, indent=2), encoding='utf8')
        complete = [e for e in eps if 'COMPLETED' in e['state'] and len(e['agents']) == 2
                    and sum(a['submission'] == sub for a in e['agents']) == 1
                    and all(a['reward'] is not None for a in e['agents'])]
        new = [e for e in complete if not (folder / f"{e['id']}.json.gz").exists()]
        status = dict(total=len(eps), completed=len(complete), existing=len(complete)-len(new),
                      requested=[e['id'] for e in new], downloaded=[], failed=[])
        manifest['submissions'][str(sub)] = status
        print(sub, 'completed',len(complete),'new',len(new),flush=True)
        raw = OUT / 'raw'
        raw.mkdir(exist_ok=True)
        for e in new:
            eid = e['id']
            try:
                api.competition_episode_replay(eid, str(raw), quiet=True)
                path = raw / f'episode-{eid}-replay.json'
                r = json.loads(path.read_text(encoding='utf8'))
                steps = r['steps']
                if len(steps) != 720:
                    raise ValueError(f'Expected 720 steps, got {len(steps)}')
                seat = next(a['index'] for a in e['agents'] if a['submission'] == sub)
                g = dict(episode=eid, created=e['created'], submission=sub, seat=seat,
                         seed=r['info']['seed'], names=r['info'].get('TeamNames'), rewards=r['rewards'],
                         opponent=next(a for a in e['agents'] if a['index'] != seat),
                         shops=[steps[min(719,d*24)][0]['observation']['town']['unlocked_shops'] for d in range(31)],
                         our_actions=[steps[t+1][seat].get('action') or {} for t in range(719)],
                         opp_actions=[steps[t+1][1-seat].get('action') or {} for t in range(719)])
                with gzip.open(folder / f'{eid}.json.gz', 'wt', encoding='utf8') as f:
                    json.dump(g, f, separators=(',', ':'))
                assert path.resolve().parent == raw.resolve()
                path.unlink()
                status['downloaded'].append(eid)
                print('ok',eid,flush=True)
            except Exception as ex:
                status['failed'].append(dict(episode=eid, error=type(ex).__name__))
                print('failed',eid,type(ex).__name__,flush=True)
            (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('done',flush=True)

if __name__ == '__main__':
    main()
