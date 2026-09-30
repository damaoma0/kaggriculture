"""Prepare the stage-1 DSM40 day-6 count-oracle diagnostic, without games."""
import gzip
import hashlib
import json
from pathlib import Path
import argparse

from semantic_tile_inputs_20260928 import ROOT, load_executor, read_panel, extract_game, strict_input


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='semantic_inputs_oracle_d6_40_locked_v2')
    args = parser.parse_args()
    out = ROOT / 'results/fresh/semantic_strategy_20260928'
    executor = load_executor()
    inputs, sources = {}, {}
    for team, episode in read_panel(ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt'):
        semantic_path = ROOT / 'data/leader_semantics' / team / f'{episode}.json.gz'
        tape_path = ROOT / 'data/leader_tapes/16732748_56498734' / f'{episode}.json.gz'
        sem = json.loads(gzip.decompress(semantic_path.read_bytes()))
        tape = json.loads(gzip.decompress(tape_path.read_bytes()))
        assert (int(episode), sem['meta']['seat']) == (int(tape['episode']), tape['seat'])
        exact = executor.TilePlanView(executor.Target(sem)).to_dict()
        game = strict_input(extract_game(sem, exact, handoff_day=6)[0])
        assert game['handoff_day'] == game['initial_state']['day'] == 6
        assert len(game['opening_plan']['board']) == 7
        assert all(event[0] < 6 for event in game['opening_plan']['events'])
        locked = {str(t) for t, label in enumerate(game['initial_state']['board']) if label == ' L'}
        assert locked == {t for t, cell in game['initial_state']['tiles'].items() if cell.get('locked')}
        inputs[episode] = game
        sources[episode] = dict(seat=tape['seat'], seed=tape['seed'],
            semantic_path=semantic_path.relative_to(ROOT).as_posix(), semantic_sha256=sha(semantic_path),
            tape_path=tape_path.relative_to(ROOT).as_posix(), tape_sha256=sha(tape_path),
            action_keys=dict(dsm='actions', opponent='opp_actions'),
            actual_day29_hires=game['days'][29]['hands'], observed_locked_tiles=len(locked))
    path = out / (args.name + '.json')
    assert not path.exists(), 'Preserve existing frozen artifacts; select a new --name.'
    path.write_text(json.dumps(inputs, separators=(',', ':')), encoding='utf-8')
    audit = dict(scope='COMPONENT_DIAGNOSTIC_NOT_NEW_WORLD_POLICY', games_executed=0,
        input_sha256=sha(path), builder_sha256=sha(Path(__file__)),
        extractor_sha256=sha(ROOT / 'scripts/semantic_tile_inputs_20260928.py'),
        target_adapter_sha256=sha(ROOT / 'agents/mgt_lead_kb115lt.py'), sources=sources,
        observations='Both original action prefixes must recreate actual day-6 public/private farm state.',
        future_input='Coordinate-free actual tile-change counts, retirement counts, hires and land additions only; no first-harvest timing.',
        limitation='Actual future semantic counts are an explicit oracle for component diagnosis, not a causal new-world policy.')
    (out / (args.name + '_audit.json')).write_text(json.dumps(audit, indent=2), encoding='utf-8')
    print(json.dumps(dict(worlds=len(inputs), input_sha256=audit['input_sha256'], games_executed=0)))


if __name__ == '__main__':
    main()
