"""Compact tapes of DSM's recorded games, in the builder's format (data/dsm_tapes/<sub>/<episode>.json.gz), plus what the
hire normalisation needs. One replay at a time (32 MB each), memory-gated.

Keys: episode, submission, seat, seed, created, rewards, shops (31 day-start unlocked-shop lists), boards (30 day-start
boards as 10 row strings of 2-char labels, weeds ' w', same encoding as data/mg_tapes), cash (30), actions (719),
hands_by_step (720: DSM's hand count at the start of each step), opp_actions (719).
The self-play game gives two tapes (one per seat).
"""
import gc, gzip, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from extract_mg_events import tile_label

OUT = ROOT / 'data/dsm_tapes/56444344'


def main():
    import psutil
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for path in sorted((ROOT / 'data/dsm_replays').glob('episode-*-replay.json')):
        while psutil.virtual_memory().available / 1e9 < 2.5:
            time.sleep(20)
        eid = path.name.split('-')[1]
        r = json.loads(path.read_text(encoding='utf-8'))
        steps = r['steps']
        if len(steps) < 720:
            continue
        names = r['info'].get('TeamNames') or []
        for seat, nm in enumerate(names):
            if 'DSM' not in (nm or ''):
                continue
            out = OUT / f'{eid}{"" if names.count(nm) == 1 else "_s" + str(seat)}.json.gz'
            if out.exists():
                continue
            obs = lambda t: steps[t][0]['observation']
            tape = dict(episode=int(eid), submission=56444344, seat=seat, seed=r['info'].get('seed'), rewards=r.get('rewards'),
                        shops=[obs(min(719, d * 24))['town']['unlocked_shops'] for d in range(31)],
                        boards=[[''.join(f'{tile_label(t):>2s}' for t in row) for row in obs(d * 24)['farms'][seat]['tiles']] for d in range(30)],
                        cash=[obs(d * 24)['farms'][seat]['money'] for d in range(30)],
                        actions=[steps[t + 1][seat].get('action') or {} for t in range(719)],
                        hands_by_step=[len(obs(t)['farms'][seat]['hands']) for t in range(720)],
                        opp_actions=[steps[t + 1][1 - seat].get('action') or {} for t in range(719)])
            with gzip.open(out, 'wt', encoding='utf-8') as f:
                json.dump(tape, f, separators=(',', ':'))
            n += 1
        del r, steps
        gc.collect()
    print(n, 'DSM tapes written to', OUT)


if __name__ == '__main__':
    main()
