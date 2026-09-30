"""DIAGNOSTIC (rev, rnd) and FIX-candidate (val) copies of a deploy build with a different tie-break in the executor's greedy dispatcher.

usage: q4_tie_variant.py <base agent file> <name> rev|rnd|val|val0   -> agents/mgt_lpv_<name>.py
The greedy matching (`while free: for u in free: for idx in tasks: ... if c < best[0]`) keeps the FIRST (unit, tile)
of equal cost; tasks are inserted in tile-index order 0..99 (row-major), so ties go to rows 0-4 (the NW and NE
quadrants) before rows 5-9 (SW, SE). The copy adds a tiny epsilon (< 0.001; costs differ by >= 0.5 otherwise) so that
ties are resolved differently without changing any non-tied choice:
  rev  ties go to the HIGHEST tile index (rows 9..0: south first)
  rnd  ties go by a per-step pseudo-random order of tiles (deterministic hash of tile, unit, step)
  val  ties go to the tile whose jobs are worth most today (S['tval'][idx][0]: the maintenance module's coin values
       of the tile's jobs, or plan_value for plan jobs; capped at 4,000 so the epsilon stays < 0.4 < the 0.5 cost grid)
       -- the one FIX candidate (the tie-break is value-aware, distance still decides every non-tie)
  val0 control: the val code path with the term multiplied by 0 (must reproduce the base build to the dollar)
Nothing else changes (survival routes and _near_shed keep their own orders). Never used as a default.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
base, name, mode = sys.argv[1], sys.argv[2], sys.argv[3]
s = (ROOT / base).read_text(encoding='utf-8')
old = """                c = cost2(u, idx)
                if c is None:
                    continue
                if best is None or c < best[0]:
                    best = (c, u, idx)"""
assert s.count(old) == 1, s.count(old)
if mode == 'rev':
    eps = "(99 - idx) * 1e-6"
elif mode == 'rnd':
    eps = "((idx * 7919 + u * 104729 + day * 24 * 31 + hour * 131) % 997) * 1e-6"
elif mode == 'val':
    eps = "(-min(4000.0, S['tval'].get(idx, (0.0, 23))[0]) * 1e-4)"
elif mode == 'val0':       # control: the same code path with the term multiplied by 0 (must equal the base build)
    eps = "(0.0 * -min(4000.0, S['tval'].get(idx, (0.0, 23))[0]) * 1e-4)"
else:
    raise SystemExit('mode rev|rnd|val|val0')
new = f"""                c = cost2(u, idx)
                if c is None:
                    continue
                c = c + {eps}   # DIAGNOSTIC tie-break ({mode}), q4_tie_variant.py
                if best is None or c < best[0]:
                    best = (c, u, idx)"""
s = s.replace(old, new)
out = ROOT / f'agents/mgt_lpv_{name}.py'
out.write_bytes(s.encode('utf-8'))
print(out)
