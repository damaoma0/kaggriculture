"""Build a standalone experimental m1 router with a state-aware switch gate."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'agents' / 'mgt_m1.py'
TARGET = ROOT / 'agents' / 'mgt_transition_candidate.py'
FRAGMENT = ROOT / 'scripts' / 'fragments' / 'tape_transition_gate.py'


def main():
    source = SOURCE.read_text(encoding='utf-8')
    anchor = 'def _mgt_router(observation, step, state):'
    assert source.count(anchor) == 1
    source = source.replace(anchor, FRAGMENT.read_text(encoding='utf-8') + '\n\n' + anchor)
    original = '''        best = None
        ign = _MGT_IGNORE.get(_int(_get(observation, 'player', 0))) or ()'''
    replacement = '''        best = None
        ign = _MGT_IGNORE.get(_int(_get(observation, 'player', 0))) or ()'''
    assert source.count(original) == 1
    source = source.replace(original, replacement)
    original = '''            if best is None or key < best[0]:
                best = (key, d, h, i)
        best = (best[1], best[2], best[3])'''
    replacement = '''            if best is None or key < best[0]:
                best = (key, d, h, i)
        if day >= 15 and best[3] != cur and best[2] >= 3:
            risk = _mgt_switch_risk(farm, day, cur, best[3], ign)
            if not risk['safe']:
                _MGT_REPORT['unsafe_switches'] = _MGT_REPORT.get('unsafe_switches', 0) + 1
                best = (best[0], _mgt_distance(ours_vec, shops, _MGT_TAPES[cur], k),
                        _mgt_hamming(board, _MGT_TAPES[cur]['lab'][day]), cur)
        best = (best[1], best[2], best[3])'''
    assert source.count(original) == 1
    source = source.replace(original, replacement)
    TARGET.write_text(source, encoding='utf-8')
    compile(source, str(TARGET), 'exec')
    print(TARGET, TARGET.stat().st_size)


if __name__ == '__main__':
    main()
