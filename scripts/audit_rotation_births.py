"""Check the inferred donor cohort labels against all available hourly UMG states."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/fresh/rotation_experiments'


def main():
    births = json.loads((OUT/'donor_birth_days.json').read_text())
    sources = json.loads((ROOT/'results/fresh/dsm_visualizer/leader_tile_change_comparison.json').read_text(encoding='utf-8'))['umgSources']
    counts = dict(games=0, productive=0, inferred=0, correct=0, wrong=0)
    examples = []
    for meta in sources:
        expected = births.get(str(meta['episode']))
        if expected is None:
            continue
        replay = json.loads((ROOT/meta['path']).read_text(encoding='utf-8'))
        counts['games'] += 1
        for day in range(30):
            board = replay['steps'][day*24][0]['observation']['farms'][meta['seat']]['tiles']
            for y, row in enumerate(board):
                for x, tile in enumerate(row):
                    if not isinstance(tile, dict) or not (tile.get('crop') or tile.get('animal')):
                        continue
                    counts['productive'] += 1
                    inferred = expected[day][y*10+x]
                    if inferred < 0:
                        continue
                    counts['inferred'] += 1
                    actual = tile.get('planted_day', tile.get('placed_day'))
                    counts['correct' if actual == inferred else 'wrong'] += 1
                    if actual != inferred and len(examples) < 15:
                        examples.append(dict(episode=meta['episode'], day=day, tile=[x,y], actual=actual, inferred=inferred))
        if counts['games'] % 20 == 0:
            print(json.dumps(counts), flush=True)
    result = dict(**counts, examples=examples)
    (OUT/'birth_audit.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
