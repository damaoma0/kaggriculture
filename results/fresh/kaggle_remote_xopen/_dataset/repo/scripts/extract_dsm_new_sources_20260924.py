"""Serial exact extraction of selected new DSM public replays.

Writes only under results/fresh/coherent_opening_20260924_01a0/new_sources/traces.
Reuses the established extract_opening_jobs_20260924.extract routine.
"""
from __future__ import annotations
import argparse
import gc
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from extract_opening_jobs_20260924 import extract

SOURCE = ROOT / 'results/fresh/coherent_opening_20260924_01a0/new_sources'
OUT = SOURCE / 'traces'


def pickup_results(path, seat, actions):
    """Recover successful pickup quantity from per-step private inventories."""
    raw = path.read_bytes()
    replay = json.loads(raw)
    del raw
    steps = replay['steps']
    records = []
    for t, action in enumerate(actions):
        commands = [action.get('farmer') or ['PASS'], *(action.get('hands') or [])]
        before = steps[t][seat]['observation']['private'].get('inventories', [])
        after = steps[t + 1][seat]['observation']['private'].get('inventories', [])
        for worker, cmd in enumerate(commands):
            if not cmd or cmd[0] != 'PICKUP' or len(cmd) < 2:
                continue
            item = str(cmd[1])
            old = before[worker].get(item, 0) if worker < len(before) else 0
            new = after[worker].get(item, 0) if worker < len(after) else 0
            requested = int(cmd[2]) if len(cmd) > 2 else 1
            records.append(dict(step=t, day=t // 24, worker=worker, item=item,
                                requested=requested, filled=max(0, int(new) - int(old))))
    del replay, steps
    gc.collect()
    return records


def main():
    import psutil
    from kaggle_environments.envs.kaggriculture import kaggriculture as engine
    from kaggle_environments.utils import structify
    from evaluate_boards import Ledger

    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    selection = json.loads((SOURCE / 'replay_selection.json').read_text(encoding='utf-8'))
    chosen = selection['selected'][:args.limit] if args.limit else selection['selected']
    rows = []
    normalized_episode = None
    for seq, item in enumerate(chosen):
        path = SOURCE / item['filename']
        while psutil.virtual_memory().available < 2.6e9:
            time.sleep(20)
        # A few Kaggle records encode a terminal no-op as JSON null. The engine
        # treats that as an empty action, so use an equivalent explicit PASS
        # only for the legacy extractor's `.get('market')` access. Preserve and
        # verify the hash of the untouched source replay below.
        raw = path.read_bytes()
        source_hash = hashlib.sha256(raw).hexdigest()
        replay = json.loads(raw)
        null_actions = 0
        for step in replay['steps']:
            for player in step:
                if player.get('action') is None:
                    player['action'] = {'farmer': ['PASS'], 'hands': [], 'market': []}
                    null_actions += 1
        if null_actions:
            with tempfile.NamedTemporaryFile('w', suffix='.json', encoding='utf-8',
                                             delete=False, dir=OUT) as tmp:
                json.dump(replay, tmp, separators=(',', ':'))
                extract_path = Path(tmp.name)
        else:
            extract_path = path
        del raw, replay
        ep = extract(extract_path, engine, structify, Ledger, source='fresh32', check_normalized=(seq == 0))
        if null_actions:
            extract_path.unlink(missing_ok=True)
        ep['replay_sha256'] = source_hash
        if ep is None or ep['transitions'] != 719:
            raise RuntimeError(f"incomplete replay {item['id']}")
        seat = int(item['seat'])
        if seat >= len(ep['teams']) or ep['teams'][seat] != 'DSM':
            raise RuntimeError(f"DSM seat mismatch for {item['id']}: {ep['teams']}")
        if ep['replay_sha256'] != item['sha256']:
            raise RuntimeError(f"source hash mismatch for {item['id']}")
        first = next((v[0] for v in ep['shops_by_day'] if v), None)
        if first != item['first_shop']:
            raise RuntimeError(f"first shop mismatch for {item['id']}: {first} != {item['first_shop']}")
        if ep.get('normalized_action_parity'):
            normalized_episode = ep['episode_id']
        actions = ep['actions'][str(seat)]
        pickup = pickup_results(path, seat, actions)
        trace = dict(episode=ep['episode_id'], seat=seat, team=ep['teams'][seat],
                     submission=selection['source_submission'], source='fresh32',
                     source_sha256=ep['replay_sha256'], transitions=ep['transitions'],
                     seed=item.get('seed'), first_shop=first, actions=actions,
                     null_action_normalizations=null_actions,
                     market_success_by_order=ep['market_success_by_order'][str(seat)],
                     daily=[d for d in ep['daily'] if d['seat'] == seat],
                     jobs=ep['jobs_by_seat'][str(seat)], shops_by_day=ep['shops_by_day'],
                     pickup_success_by_step=pickup)
        target = OUT / f"trace-{ep['episode_id']}-seat{seat}.json.gz"
        with gzip.open(target, 'wt', encoding='utf-8', compresslevel=6) as f:
            json.dump(trace, f, separators=(',', ':'))
        rows.append(dict(episode=ep['episode_id'], seat=seat, team=ep['teams'][seat],
                         submission=selection['source_submission'], source_replay=item['filename'],
                         trace=target.name, source_sha256=ep['replay_sha256'],
                         trace_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                         transitions=ep['transitions'], first_shop=first,
                         pickup_requests=len(pickup), pickup_requested=sum(x['requested'] for x in pickup),
                         pickup_filled=sum(x['filled'] for x in pickup),
                         pickup_short=sum(max(0, x['requested'] - x['filled']) for x in pickup)))
        print(json.dumps(dict(episode=ep['episode_id'], seat=seat, first_shop=first,
                             transitions=ep['transitions'], pickup=len(pickup))), flush=True)
        del trace, ep, actions, pickup
        gc.collect()

    manifest = dict(schema_version=1, scope='selected fresh DSM submission replays; one DSM target-seat trace per full episode',
                    source_submission=selection['source_submission'], team_id=selection['team_id'],
                    source_selection_sha256=hashlib.sha256((SOURCE / 'replay_selection.json').read_bytes()).hexdigest(),
                    engine_sha256=hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest(),
                    transitions=719, exact_transition_parity=True,
                    normalized_action_parity_verified_episode=normalized_episode,
                    pickup='Per-step inventory deltas quantify successful quantities for PICKUP commands.',
                    episodes=rows)
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (OUT / 'index.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    (OUT / 'README.md').write_text(
        '# Fresh DSM traces\n\nEach compressed trace stores the original actions, market fills aligned to requested order slots, daily farm/private states, successful physical jobs, public shops, and successful pickup quantities from worker inventory deltas. Extraction replays each source through the Kaggle engine and checks farms, market, town, private state, and cash at every transition. The first source also receives a full normalized-action parity replay.\n',
        encoding='utf-8')
    print(json.dumps(dict(extracted=len(rows), normalized_action_parity_verified_episode=normalized_episode,
                          shops={k: sum(x['first_shop'] == k for x in rows)
                                 for k in sorted({x['first_shop'] for x in rows})},
                          pickups_requested=sum(x['pickup_requested'] for x in rows),
                          pickups_filled=sum(x['pickup_filled'] for x in rows))), flush=True)


if __name__ == '__main__':
    main()
