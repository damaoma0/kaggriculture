"""Download a reproducible DSM replay sample and build an offline tape explorer.

Run: .venv/Scripts/python.exe scripts/build_dsm_visualizer.py [--limit 12]
Use --limit 108 for the full September 22 inventory; cached replays are reused.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import gzip
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data/dsm_replays'
INVENTORY = ROOT / 'results/fresh/leader_library_refresh_20260922/inventory.json'


def fetch(eid):
    path = CACHE / f'episode-{eid}-replay.json'
    if not path.exists():
        subprocess.run([sys.executable, '-m', 'kaggle', 'competitions', 'replay', str(eid),
                        '-p', str(CACHE), '-q'], check=True, timeout=120, capture_output=True)
    return path


def extract(path, submission):
    replay = json.loads(path.read_text(encoding='utf-8'))
    if len(replay['steps']) != 720:
        raise ValueError('Replay is not a complete 720-frame game')
    names = replay['info']['TeamNames']
    seat = names.index('DSM')
    tiles, index, frames = [], {}, []
    def tile_id(tile):
        key = json.dumps(tile, sort_keys=True, separators=(',', ':'))
        if key not in index:
            index[key] = len(tiles)
            tiles.append(tile)
        return index[key]
    for t, step in enumerate(replay['steps']):
        obs = step[0]['observation']
        farms = []
        for s, farm in enumerate(obs['farms']):
            private_obs = step[s]['observation']
            private = private_obs.get('private') if private_obs.get('player') == s else None
            farms.append(dict(money=farm['money'], units=[farm['farmer']]+farm['hands'],
                              board=[tile_id(tile) for row in farm['tiles'] for tile in row],
                              private=private,
                              action=replay['steps'][t+1][s].get('action') if t+1 < len(replay['steps']) else None))
        frames.append(dict(farms=farms, prices=obs['market']['prices'], shops=obs['town']['unlocked_shops']))
    return dict(id=replay['info']['EpisodeId'], submission=submission, names=names, seat=seat,
                rewards=replay['rewards'], tiles=tiles, frames=frames)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--limit', type=int, default=12)
    args = ap.parse_args()
    if args.limit < 1:
        ap.error('--limit must be positive')
    entry = next(e for e in json.loads(INVENTORY.read_text()) if e['team'] == 'DSM')
    ids = entry['completed_episode_ids']
    count = min(args.limit, len(ids))
    selected = [ids[round(i*(len(ids)-1)/max(1, count-1))] for i in range(count)]
    CACHE.mkdir(parents=True, exist_ok=True)
    games, failures = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [(eid, pool.submit(fetch, eid)) for eid in selected]
        for eid, future in futures:
            try:
                game = extract(future.result(), entry['selected_submission'])
                if game['id'] != eid:
                    raise ValueError('Downloaded episode ID does not match inventory')
                detail = dict(tiles=game.pop('tiles'), frames=game.pop('frames'))
                game['packed'] = base64.b64encode(gzip.compress(
                    json.dumps(detail, separators=(',', ':')).encode('utf-8'))).decode('ascii')
                games.append(game)
                print(f'Loaded {eid} ({len(games)}/{count})', flush=True)
            except Exception as exc:
                failures.append(dict(id=eid, error=type(exc).__name__))
                print(f'Could not load {eid}: {type(exc).__name__}', flush=True)
    if not games:
        raise SystemExit('No replays could be loaded.')
    data = dict(games=games, available=len(ids), selected=count, failures=failures,
                snapshot='2026-09-22', submission=entry['selected_submission'])
    # Keep the full library offline without eagerly parsing every hourly frame.
    payload = json.dumps(data, separators=(',', ':')).replace('<', '\\u003c')
    template = (ROOT/'scripts/fragments/dsm_visualizer.html').read_text(encoding='utf-8')
    out = ROOT/'viz/dsm-tapes.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(template.replace('__DATA__', payload), encoding='utf-8')
    print(f'Built {out}: {len(games)} games, {out.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()
