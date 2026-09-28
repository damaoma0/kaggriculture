"""Read-only dawn capacity screen, not a counterfactual land valuation.

Reads eight completed frozen V8 games. No agent, engine, or future data enters
a policy. Productive cells include crops, occupied pens, and empty structures;
weeds are reported separately. Counts cannot certify feasible travel or jobs.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = Path(r'C:\Users\xyygl\Documents\kaggriculture\results\fresh\semantic_strategy_20260928')
OUT = ROOT / 'results/fresh/semantic_kb115lt2_recovery/diagnostics/land_capacity_v2'


def count(farm):
    kinds = Counter()
    fourth = Counter()
    for y, row in enumerate(farm['tiles']):
        for x, tile in enumerate(row):
            if isinstance(tile, dict):
                label = tile.get('crop') or tile.get('animal') or tile.get('kind', 'UNKNOWN')
            else:
                label = str(tile)
            kinds[label] += 1
            if x >= 5 and y >= 5:
                fourth[label] += 1
    crops = ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON')
    assets = crops + ('COW', 'SHEEP', 'GOOSE', 'PASTURE', 'COOP')
    return dict(land=len(farm['unlocked_quadrants']), kinds=dict(kinds),
                asset_cells=sum(kinds[k] for k in assets),
                crop_cells=sum(kinds[k] for k in crops),
                southeast=dict(fourth), southeast_assets=sum(fourth[k] for k in assets))


def main():
    rows = []
    hashes = {}
    for i in range(8):
        path = STUDY / f'runs/strategy_v8_kb115lt2_readiness/development/live/live-{i:02}.json'
        raw = path.read_bytes()
        hashes[str(path)] = hashlib.sha256(raw).hexdigest()
        game = json.loads(raw)
        assert game['completed']
        seat = game['case']['seat']
        sides = []
        for player in (seat, 1-seat):
            days = [dict(day=r['day'], **count(r['current_observation']['own_farm']))
                    for r in game['diagnostics'][player]]
            assert len(days) == 30 and [r['day'] for r in days] == list(range(30))
            sides.append(dict(player=player, fourth_land_first_dawn=next(
                (r['day'] for r in days if r['land'] == 4), None),
                max_asset_cells=max(r['asset_cells'] for r in days),
                asset_days_over_75=[r['day'] for r in days if r['asset_cells'] > 75], days=days))
        rows.append(dict(case=game['case']['id'], margin=game['margin'], own=sides[0], rival=sides[1]))
    value = dict(scope='READ_ONLY_DEVELOPMENT_DAWN_CAPACITY_SCREEN',
        source_sha256=hashes, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), cases=rows,
        limits=['Dawn cell counts do not include same-day temporary overlap or establish feasible routing.',
                '75 is the geometric capacity of three 25-cell quadrants; shed access coordinates remain plantable in the official engine.',
                'Existing crop and animal identities cannot be moved into another quadrant.',
                'No profits, sales receipts or counterfactual savings are attributed to individual land cells.',
                'No gameplay, policy changes, qualification inputs or outcome selection.'],
        supersedes='land_capacity_v1 incorrectly subtracted shed access cells; its artifact is retained as invalid geometry.')
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'audit.json'
    assert not target.exists(), 'Preserve completed diagnostic evidence'
    target.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(path=str(target), sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        cases=[dict(case=r['case'], own_fourth=r['own']['fourth_land_first_dawn'],
                    rival_fourth=r['rival']['fourth_land_first_dawn'],
                    own_peak=r['own']['max_asset_cells'], rival_peak=r['rival']['max_asset_cells'],
                    own_days_over_75=r['own']['asset_days_over_75']) for r in rows]), indent=2))


if __name__ == '__main__':
    main()
