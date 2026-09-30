"""Freeze V9 and fetch an outcome-blind, rating-stratified replay panel."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
import random
import secrets
import shutil
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PAYLOAD = OUT / 'payload'
BASE = ROOT / 'results/fresh/tape_exact_speed_20260923_01a0_v2/payload'

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding='utf-8')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def freeze():
    if (OUT / 'source_manifest.json').exists():
        manifest = json.loads((OUT / 'source_manifest.json').read_text())
        for name, expected in manifest['sha256'].items():
            assert sha(PAYLOAD / name) == expected, name
        return
    manifest = json.loads((BASE / 'manifest.json').read_text())
    for name, expected in manifest['sha256'].items():
        assert sha(BASE / name) == expected, name
        target = PAYLOAD / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BASE / name, target)
    extra = 'data/router_refresh_20260922/v56/main.py'
    target = PAYLOAD / extra
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / extra, target)
    manifest['sha256'][extra] = sha(target)
    manifest['parent_manifest_sha256'] = sha(BASE / 'manifest.json')
    manifest['protocol'] = 'V9 unchanged; paired fresh random worlds and separately reported rated-opponent recordings.'
    write(OUT / 'source_manifest.json', manifest)
    master = secrets.randbits(128)
    rng = random.Random(master)
    # Independent of outcomes and separate from the untouched qualification seeds.
    seeds = rng.sample(range(1_000_000_000, 4_000_000_000), 32)
    shop_names = ['BAKERY', 'FARMERS_MARKET', 'ICE_CREAM_SHOP', 'PET_CAFE',
                  'PIZZA_SHOP', 'SMOOTHIE_SHOP', 'BRUNCH_SPOT', 'YARN_STORE']
    # Verify these names against the frozen official engine before any games run.
    worlds = [dict(world=i, seed=seed, seat=i % 2,
                   shops=[rng.choice(shop_names) for _ in range(8)])
              for i, seed in enumerate(seeds)]
    specs = [dict(w, id=f'random-{w["world"]:02d}-{opponent}', kind='live',
                  opponent=opponent) for w in worlds for opponent in ('v56', 'original_m1')]
    write(OUT / 'random_design.json', dict(master_seed=master, worlds=worlds, specs=specs,
          reveals=[12,15,18], candidate_count=7, expanded=2, worlds_per_finalist=8,
          protocol='32 new IID uniform shop worlds, same worlds crossed with V56 and original m1; 16 worlds in each seat. Native m1 versus unchanged V9. No seed, opponent identity, future shops or recorded actions enter choose(). Fixed shops remove policy-dependent shop RNG drift. No tuning or outcome filtering. Search is unbounded for coverage; measured 1s+60s time-bank feasibility is reported separately.'))
    print('FROZEN ' + json.dumps(dict(files=len(manifest['sha256']), fresh_pairs=len(specs), master_seed=master)), flush=True)

def fetch_metadata():
    from kaggle.api.kaggle_api_extended import KaggleApi
    from kagglesdk.competitions.types.competition_api_service import ApiGetLeaderboardRequest
    api = KaggleApi(); api.authenticate()
    path = OUT / 'leaderboard_snapshot.json'
    if not path.exists():
        with api.build_kaggle_client() as kaggle:
            req = ApiGetLeaderboardRequest(); req.competition_name = 'kaggriculture'
            api._set_paging(req, 200, None)
            response = kaggle.competitions.competition_api_client.get_leaderboard(req)
        rows = [dict(rank=i+1, team_id=r.team_id, team=r.team_name, score=float(r.score),
                     date=str(r.submission_date)) for i,r in enumerate(response.submissions or [])]
        assert rows and rows[-1]['score'] < 2750, 'Fetch another leaderboard page before sampling'
        write(path, dict(fetched_utc=datetime.now(timezone.utc).isoformat(), rows=rows))
    board = json.loads(path.read_text())
    design = json.loads((OUT / 'random_design.json').read_text())
    rng = random.Random(design['master_seed'] ^ 0x7265706c6179)
    selected = []
    excluded_episodes = {int(p.stem.split('.')[0]) for folder in
        ('rival_library', 'modern_rival_library') for p in
        (PAYLOAD / 'results/fresh/value_tape_followup_20260923' / folder).glob('*.json.gz')}
    for lower in (2750,2812.5,2875,2937.5):
        candidates = [r for r in board['rows'] if lower <= r['score'] < lower+62.5
                      and r['team_id'] != 16823930]
        rng.shuffle(candidates)
        chosen = 0
        for team in candidates:
            cache = OUT / 'api_metadata' / f"team-{team['team_id']}.json"
            if cache.exists():
                meta = json.loads(cache.read_text())
            else:
                submissions = api.competition_team_submissions(team['team_id'])
                values = [dict(id=int(s.id), score=float(s.public_score), date=str(s.date_submitted))
                          for s in submissions if s.public_score is not None]
                meta = dict(team=team, fetched_utc=datetime.now(timezone.utc).isoformat(), submissions=values)
                write(cache, meta)
            eligible = [s for s in meta['submissions'] if lower <= s['score'] < lower+62.5]
            if not eligible:
                continue
            submission = max(eligible, key=lambda s:s['score'])
            ep_path = OUT / 'api_metadata' / f"submission-{submission['id']}.json"
            if ep_path.exists():
                episodes = json.loads(ep_path.read_text())['episodes']
            else:
                eps = api.competition_list_episodes(submission['id'])
                episodes = [dict(id=int(e.id), created=str(e.create_time), state=str(e.state),
                    agents=[dict(submission=int(a.submission_id), seat=int(a.index), reward=a.reward,
                                 team=a.team_name, team_id=a.team_id) for a in e.agents or []]) for e in eps]
                write(ep_path, dict(fetched_utc=datetime.now(timezone.utc).isoformat(), episodes=episodes))
            eligible_eps = [e for e in episodes if 'COMPLETED' in e['state'] and len(e['agents']) == 2
                and sum(a['submission'] == submission['id'] for a in e['agents']) == 1
                and e['id'] not in excluded_episodes]
            picks = []
            for seat in (0,1):
                pool = [e for e in eligible_eps if any(a['seat'] == seat and a['submission'] == submission['id'] for a in e['agents'])]
                rng.shuffle(pool)
                picks += pool[:2]
            if len(picks) < 4:
                continue
            selected.append(dict(team=team, submission=submission, band=[lower,lower+62.5], episodes=picks))
            excluded_episodes.update(e['id'] for e in picks)
            print('SELECTED ' + json.dumps(dict(team=team['team'], submission=submission,
                episodes=[e['id'] for e in picks])), flush=True)
            chosen += 1
            if chosen == 2:
                break
        assert chosen == 2, f'Not enough teams with recordings in band {lower}'
    path = OUT / 'recording_design.json'
    value = dict(selected=selected, sampled_without_reward_filter=True,
        protocol='Two teams per 62.5-point stratum in [2750,3000), best qualifying active submission per team. Four uniformly sampled completed episodes per submission, two in each opponent seat; 32 unique recordings, excluding all 115 training episodes. Rating is the specific submission score when fetched, not its team maximum. Retain failures. Frozen playback is not a reactive opponent.')
    if path.exists():
        assert json.loads(path.read_text()) == value
    else:
        write(path, value)

def fetch_replays():
    from kaggle.api.kaggle_api_extended import KaggleApi
    api=KaggleApi(); api.authenticate()
    design = json.loads((OUT / 'recording_design.json').read_text())
    rawdir = OUT / 'download'; rawdir.mkdir(exist_ok=True)
    for team in design['selected']:
        for ep in team['episodes']:
            eid = ep['id']; target = OUT / 'recordings' / f'{eid}.json.gz'
            if target.exists():
                continue
            raw = rawdir / f'episode-{eid}-replay.json'
            if not raw.exists():
                api.competition_episode_replay(eid, str(rawdir), quiet=True)
            r = json.loads(raw.read_text(encoding='utf-8'))
            steps = r['steps']
            assert len(steps) == 720, (eid, len(steps))
            opp = next(a['seat'] for a in ep['agents'] if a['submission'] == team['submission']['id'])
            game = dict(episode=eid, seed=r['info']['seed'], opponent_seat=opp,
                opponent=team['team']['team'], submission=team['submission'], metadata=ep,
                names=r['info'].get('TeamNames'), rewards=r['rewards'],
                configuration=r['configuration'], raw_sha256=sha(raw),
                shops=[steps[min(719,d*24)][0]['observation']['town']['unlocked_shops'] for d in range(31)],
                actions=[[steps[t+1][s].get('action') or {} for t in range(719)] for s in range(2)],
                # Daily full observations verify replay fidelity and preserve exact weed changes.
                observations=[dict(step=t, seats=[steps[t][s]['observation'] for s in range(2)])
                              for t in sorted(set([0,719] + list(range(24,719,24))))])
            target.parent.mkdir(exist_ok=True)
            with gzip.open(target,'wt',encoding='utf-8') as f:
                json.dump(game,f,separators=(',',':'))
            # Only this task's explicitly resolved downloaded temporary file is removed.
            assert raw.resolve().parent == rawdir.resolve()
            raw.unlink()
            print('FETCHED ' + json.dumps(dict(episode=eid, opponent=game['opponent'],
                rating=team['submission']['score'], bytes=target.stat().st_size)), flush=True)

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('mode', choices=['freeze','metadata','replays'])
    args=p.parse_args()
    {'freeze':freeze,'metadata':fetch_metadata,'replays':fetch_replays}[args.mode]()
