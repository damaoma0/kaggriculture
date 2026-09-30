"""New-opening plan, measurement 1: can a board built by the leaders' new opening hand off to our tape library?

Parses a few DSM full replays (one at a time; memory-checked) into router tile labels for days 0-14 (DSM's own seat),
then, for each day, counts how many of the 584 UMG tapes are router-eligible (tile Hamming <= 8, weeds as empty,
exactly the router's `_mgt_labels`/`_mgt_hamming`) and the minimum Hamming. Also saves DSM's day 0-8 actions, cash and
hands for the replayability test (opening_replay_probe.py).
Writes results/fresh/newphase_20260923/opening/handoff_probe.json
"""
import gc, gzip, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/newphase_20260923/opening'


def label(tile):                      # = agents/mgt_m1.py _mgt_label
    if tile == 'LOCKED':
        return ' L'
    if tile is None:
        return ' .'
    kind = tile.get('kind')
    if kind == 'PLANT':
        return str(tile.get('crop'))[:2]
    if kind == 'WEED':
        return ' .'
    if tile.get('animal'):
        return str(tile['animal'])[:2].lower()
    return str(kind)[:2].lower()


def umg_labels(board_rows):           # tape boards: 10 row strings of 2-char labels; router maps weeds ' w' -> ' .'
    s = ''.join(board_rows) if isinstance(board_rows, list) else board_rows
    return [' .' if s[i:i + 2] == ' w' else s[i:i + 2] for i in range(0, len(s), 2)]


def wait_mem(gb):
    import psutil
    while psutil.virtual_memory().available / 1e9 < gb:
        time.sleep(30)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    OUT.mkdir(parents=True, exist_ok=True)
    tapes = []
    for p in sorted((ROOT / 'data/mg_tapes').rglob('*.json.gz')):
        g = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        tapes.append(dict(ep=g['episode'], lab=[umg_labels(b) for b in g['boards']]))
    games = []
    for path in sorted((ROOT / 'data/dsm_replays').glob('episode-*-replay.json'))[:n]:
        wait_mem(2.5)
        r = json.loads(path.read_text(encoding='utf-8'))
        names = r['info'].get('TeamNames') or []
        seat = next(i for i, x in enumerate(names) if 'DSM' in (x or ''))
        steps = r['steps']
        boards, cash, hands = [], [], []
        for d in range(15):
            farm = steps[d * 24][0]['observation']['farms'][seat]
            boards.append([label(t) for row in farm['tiles'] for t in row])
            cash.append(farm['money'])
            hands.append(len(farm['hands']))
        games.append(dict(ep=r.get('id') or path.stem, seat=seat, seed=r['info'].get('seed'), boards=boards, cash=cash, hands=hands,
                          shops=[steps[min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(15)],
                          actions=[steps[t + 1][seat].get('action') or {} for t in range(0, 9 * 24)]))
        del r, steps
        gc.collect()
    rows = []
    for g in games:
        per_day = {}
        for d in range(15):
            hs = sorted(sum(1 for x, y in zip(g['boards'][d], t['lab'][d]) if x != y) for t in tapes)
            per_day[d] = dict(min_hamming=hs[0], eligible_le8=sum(h <= 8 for h in hs), median=hs[len(hs) // 2])
        rows.append(dict(ep=g['ep'], per_day=per_day))
    print(f'{len(games)} DSM games vs {len(tapes)} tapes: router eligibility (tile Hamming <= 8) of the DSM board by day')
    for d in range(15):
        mins = [r['per_day'][d]['min_hamming'] for r in rows]
        elig = [r['per_day'][d]['eligible_le8'] for r in rows]
        print(f'  day {d:2d}: min Hamming to any tape {min(mins):3d}..{max(mins):3d} (median over games {sorted(mins)[len(mins)//2]}), '
              f'eligible tapes {min(elig)}..{max(elig)}')
    # how different are DSM boards from each other (layout stability)?
    for d in (3, 6, 9, 12):
        b = [g['boards'][d] for g in games]
        pair = [sum(1 for x, y in zip(b[i], b[j]) if x != y) for i in range(len(b)) for j in range(i + 1, len(b))]
        print(f'  DSM-vs-DSM tile Hamming day {d}: median {sorted(pair)[len(pair)//2]}, max {max(pair)}')
    (OUT / 'handoff_probe.json').write_text(json.dumps(dict(rows=rows, games=games)), encoding='utf-8')


if __name__ == '__main__':
    main()
