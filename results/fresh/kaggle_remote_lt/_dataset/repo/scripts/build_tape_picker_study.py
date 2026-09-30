"""Build isolated tape-picker variants from the unchanged mgt_m1 submission."""
from hashlib import sha256
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "agents/mgt_m1.py"
INSERT = "        d = _mgt_distance(ours_vec, shops, t, k)\n"

RECENT = '''
def _mgt_picker_extra(observation, farm, board, t, day, shops, k, cur, i):
    # The last revealed shop changes the near-term product opportunity. Compare
    # its product mix explicitly: cumulative demand cannot tell apart orderings.
    if day > 15 or k < 2:
        return 0.0
    actual = _MGT_DEMAND.get(shops[-1], {})
    donor = _MGT_DEMAND.get(t['shops'][k - 1], {})
    return 1.25 * sum(_MGT_WEIGHT[p] * abs(actual.get(p, 0) - donor.get(p, 0))
                      for p in _MGT_PRODUCTS)

'''

COHORT = '''
def _mgt_picker_extra(observation, farm, board, t, day, shops, k, cur, i):
    # A tape's tile label omits crop age. Infer each donor's planting day from
    # its day-start board trajectory, then compare it with the live cohort.
    # This is a conservative continuity cost, capped per crop because a donor
    # can replant the same crop between snapshots.
    extra = 0.0
    for y, row in enumerate(farm['tiles']):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict) or tile.get('kind') != 'PLANT':
                continue
            crop = tile.get('crop')
            if crop not in ('STRAWBERRY', 'TOMATO'):
                continue
            j = y * 10 + x
            label = crop[:2]
            if t['lab'][day][j] != label:
                extra += 2.0
                continue
            first = day
            while first > 0 and t['lab'][first - 1][j] == label:
                first -= 1
            donor_day = first - 1
            live_day = tile.get('planted_day')
            if isinstance(live_day, int):
                extra += 1.25 * min(3, abs(live_day - donor_day))
    return extra

'''


def main():
    source = SOURCE.read_text(encoding="utf-8")
    assert source.count(INSERT) == 1
    assert source.count("def _mgt_router(observation, step, state):") == 1
    built = {}
    for name, helper in (("mgt_pick_recent", RECENT), ("mgt_pick_cohort", COHORT)):
        code = source.replace("def _mgt_router(observation, step, state):", helper + "def _mgt_router(observation, step, state):", 1)
        code = code.replace(INSERT, INSERT + "            d += _mgt_picker_extra(observation, farm, board, t, day, shops, k, cur, i)\n", 1)
        target = ROOT / "agents" / (name + ".py")
        target.write_text(code, encoding="utf-8")
        built[name] = {"source_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
                       "sha256": sha256(target.read_bytes()).hexdigest(),
                       "path": str(target.relative_to(ROOT))}
    t10 = (ROOT / "agents/mgt_t10.py").read_text(encoding="utf-8")
    assert t10.count(INSERT) == 1
    name = "mgt_t10_recent"
    code = t10.replace("def _mgt_router(observation, step, state):", RECENT + "def _mgt_router(observation, step, state):", 1)
    code = code.replace(INSERT, INSERT + "            d += _mgt_picker_extra(observation, farm, board, t, day, shops, k, cur, i)\n", 1)
    target = ROOT / "agents" / (name + ".py")
    target.write_text(code, encoding="utf-8")
    built[name] = {"source_sha256": sha256((ROOT / "agents/mgt_t10.py").read_bytes()).hexdigest(),
                   "sha256": sha256(target.read_bytes()).hexdigest(),
                   "path": str(target.relative_to(ROOT))}
    name = "mgt_t10_reveal_safe"
    code = t10.replace("def _mgt_router(observation, step, state):", RECENT + "def _mgt_router(observation, step, state):", 1)
    code = code.replace("        for i, t in enumerate(_MGT_TAPES):\n",
                        "        cur_h = _mgt_hamming(board, _MGT_TAPES[cur]['lab'][day])\n"
                        "        incumbent_recent = _mgt_picker_extra(observation, farm, board, _MGT_TAPES[cur], day, shops, k, cur, cur)\n"
                        "        for i, t in enumerate(_MGT_TAPES):\n", 1)
    code = code.replace(INSERT, INSERT +
                        "            d += (_mgt_picker_extra(observation, farm, board, t, day, shops, k, cur, i)\n"
                        "                  if h <= cur_h else incumbent_recent)\n", 1)
    target = ROOT / "agents" / (name + ".py")
    target.write_text(code, encoding="utf-8")
    built[name] = {"source_sha256": sha256((ROOT / "agents/mgt_t10.py").read_bytes()).hexdigest(),
                   "sha256": sha256(target.read_bytes()).hexdigest(),
                   "path": str(target.relative_to(ROOT))}
    name = "mgt_m1_reveal_safe"
    code = source.replace("def _mgt_router(observation, step, state):", RECENT + "def _mgt_router(observation, step, state):", 1)
    code = code.replace("        for i, t in enumerate(_MGT_TAPES):\n",
                        "        cur_h = _mgt_hamming(board, _MGT_TAPES[cur]['lab'][day])\n"
                        "        incumbent_recent = _mgt_picker_extra(observation, farm, board, _MGT_TAPES[cur], day, shops, k, cur, cur)\n"
                        "        for i, t in enumerate(_MGT_TAPES):\n", 1)
    code = code.replace(INSERT, INSERT +
                        "            d += (_mgt_picker_extra(observation, farm, board, t, day, shops, k, cur, i)\n"
                        "                  if h <= cur_h else incumbent_recent)\n", 1)
    target = ROOT / "agents" / (name + ".py")
    target.write_text(code, encoding="utf-8")
    built[name] = {"source_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
                   "sha256": sha256(target.read_bytes()).hexdigest(),
                   "path": str(target.relative_to(ROOT))}
    for base_name in ("mgt_t10_reveal_safe", "mgt_m1_reveal_safe"):
        old = ROOT / "agents" / (base_name + ".py")
        code = old.read_text(encoding="utf-8")
        naive = "        cur_h = _mgt_hamming(board, _MGT_TAPES[cur]['lab'][day])\n"
        exact = ("        cur_lab = _MGT_TAPES[cur]['lab'][day]\n"
                 "        cur_h = _mgt_hamming(board, cur_lab) if not (ign or aw != 1) else sum(\n"
                 "            (aw if (x in _MGT_ANIMAL_LABELS or y in _MGT_ANIMAL_LABELS) else 1)\n"
                 "            for x, y in zip(board, cur_lab) if x is not None and x != y)\n")
        assert code.count(naive) == 1
        new_name = base_name + "2"
        target = ROOT / "agents" / (new_name + ".py")
        target.write_text(code.replace(naive, exact, 1), encoding="utf-8")
        built[new_name] = {"source_sha256": sha256(old.read_bytes()).hexdigest(),
                           "sha256": sha256(target.read_bytes()).hexdigest(),
                           "path": str(target.relative_to(ROOT))}
    print(json.dumps(built, indent=2))


if __name__ == "__main__":
    main()
