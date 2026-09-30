"""Build the route-order research variants as NEW files (the main agents are not touched):
base = agents/mgt_lead_deploy.py (ff1 + tie_value defaults) + ws2 (hand_stock 1)
  rs1 = + sweep continuation: among near-equal costs prefer an open task on a tile adjacent to the unit's last tile op
  rs2 = rs1 + batched wheat (a unit fetching wheat takes enough for the open FEED jobs near its target) + pick_cap 6 / 8
  rs3 = rs2 + fertilizer chain (a unit needing fertilizer may collect it from an animal on the way instead of the shed)
usage: lead_rs_build.py        -> agents/mgt_lpv_tw0.py (base = new default + ws2), agents/mgt_lpv_rs1.py, rs2, rs3

Tie order in the greedy (costs are integer steps + integer penalties; keep_bonus 1.5): sweep bonus 0.5 (rs) + value
term <= 0.4 (Q) < 1 step, so distance always dominates; adjacency outranks value; then iteration order (unit, tile).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIE = ("                    c = c + (-min(4000.0, S['tval'].get(idx, (0.0, 23))[0]) * 1e-4)   # value-aware tie-break: "
       "equal-cost tasks go to the tile worth most today (q4 thread, 2026-09-25)\n")


def sub(s, a, b, name):
    assert s.count(a) == 1, (name, a[:70], s.count(a))
    return s.replace(a, b)


def base():
    s = (ROOT / 'agents/mgt_lead_deploy.py').read_bytes().decode('utf-8').replace('\r\n', '\n')
    assert s.count(TIE) == 1, 'the deploy must carry the tie_value default line (2026-09-25)'
    s = sub(s, TIE + '''                if best is None or c < best[0]:''',
            TIE + '''                if RS_CFG["sweep"]:
                    lo_ = S.setdefault("last_op", {}).get(u)
                    if lo_ is not None and abs(lo_ % 10 - idx % 10) + abs(lo_ // 10 - idx // 10) == 1:
                        c -= RS_CFG["sweep_bonus"]   # sweep continuation: next to the unit's last tile op
                if best is None or c < best[0]:''', 'greedy')
    # research config block (after the executor CFG)
    s = sub(s, '\n_SMNS = None\n',
            '\nRS_CFG = {"sweep": 0, "sweep_bonus": 0.5, "wheat_batch": 0, "wheat_batch_r": 3, "wheat_batch_max": 6, '
            '"fert_chain": 0}   # lead_rs_build.py research switches\nCFG.update({"hand_stock": 1})   # ws2\n_SMNS = None\n', 'cfg')
    # last tile op per unit (reset daily)
    s = sub(s, '''    if S["day"] != day:
        S["day"] = day
        S["assign"] = {}
''', '''    if S["day"] != day:
        S["day"] = day
        S["assign"] = {}
        S["last_op"] = {}
''', 'day reset')
    s = sub(s, '''        if act is None:
            assign.pop(u, None)
            actions[u] = ["PASS"]
        else:
            actions[u] = list(act)

    # ---- diagnostics''', '''        if act is None:
            assign.pop(u, None)
            actions[u] = ["PASS"]
        else:
            actions[u] = list(act)
            S.setdefault("last_op", {})[u] = idx

    # ---- diagnostics''', 'last op')
    # batched wheat in the task pickup (after the hand_stock amount)
    s = sub(s, '''            if CFG["hand_stock"] and k == "WHEAT":
                amt = min(shed_left[k], max(0, need[k] - inv.get(k, 0)) + CFG["hs_buffer"])
            amt = max(1, amt)''', '''            if CFG["hand_stock"] and k == "WHEAT":
                amt = min(shed_left[k], max(0, need[k] - inv.get(k, 0)) + CFG["hs_buffer"])
            if RS_CFG["wheat_batch"] and k == "WHEAT":
                want_ = need.get("WHEAT", 0)
                for j_, (o_, n_, p_) in tasks.items():
                    if j_ == idx or n_.get("WHEAT", 0) <= 0 or (j_ in taken and assign.get(u) != j_):
                        continue
                    if abs(j_ % 10 - tgt[0]) + abs(j_ // 10 - tgt[1]) <= RS_CFG["wheat_batch_r"]:
                        want_ += n_["WHEAT"]
                amt = min(shed_left[k], max(1, min(RS_CFG["wheat_batch_max"], want_) - inv.get(k, 0)))
                S["log"]["rs_wheat_batch"] += 1
            amt = max(1, amt)''', 'wheat batch')
    # fertilizer chain: animals with fertilizer ready are a source (cost + action)
    s = sub(s, '''    def usable_ops(u, ops, need):
        """ops this unit can run at the tile now (items carried or obtainable at the shed)."""
        inv = invs[u]
        lack = {k for k, v in need.items() if inv.get(k, 0) < v and shed_left.get(k, 0) <= 0}''',
            '''    chain_src = [i_ for i_ in range(100) if RS_CFG["fert_chain"] and _animal(_tile(tiles, i_))
                 and _tile(tiles, i_).get("fertilizer_available")]

    def chain_route(u, tgt):
        """(cost, animal tile) of collecting fertilizer on the way to tgt, or None."""
        best_ = None
        for a_ in chain_src:
            ap = (a_ % 10, a_ // 10)
            c_ = _dist(pos[u], ap) + 1 + _dist(ap, tgt)
            if best_ is None or c_ < best_[0]:
                best_ = (c_, a_)
        return best_

    def usable_ops(u, ops, need):
        """ops this unit can run at the tile now (items carried or obtainable at the shed)."""
        inv = invs[u]
        lack = {k for k, v in need.items() if inv.get(k, 0) < v and shed_left.get(k, 0) <= 0
                and not (k == "FERTILIZER" and chain_src)}''', 'usable_ops')
    s = sub(s, '''        if miss:
            s = _near_shed(p)
            c = _dist(p, s) + len(miss) + _dist(s, tgt)
        else:
            c = _dist(p, tgt)''', '''        if RS_CFG["fert_chain"] and chain_src and invs[u].get("FERTILIZER", 0) < need.get("FERTILIZER", 0) \\
                and "FERTILIZER" not in miss:
            miss = miss + ["FERTILIZER"]          # obtainable from an animal even when the shed has none
        if miss:
            s = _near_shed(p)
            c = _dist(p, s) + len(miss) + _dist(s, tgt)
            if RS_CFG["fert_chain"] and miss == ["FERTILIZER"] and chain_src:
                cr = chain_route(u, tgt)
                if cr is not None and (cr[0] < c or shed_left.get("FERTILIZER", 0) <= 0):
                    c = cr[0]
        else:
            c = _dist(p, tgt)''', 'cost chain')
    s = sub(s, '''        if miss:
            s = _near_shed(p)
            if p != s:
                actions[u] = _step_toward(p, s)
                continue
            k = miss[0]''', '''        if RS_CFG["fert_chain"] and chain_src and inv.get("FERTILIZER", 0) < need.get("FERTILIZER", 0):
            miss_ne = [k_ for k_ in miss if k_ != "FERTILIZER"]
            # already on the target with other work there (e.g. a survival water): do that first
            other_here = p == tgt and any(o_[0] != "FERTILIZE" for o_ in usable_ops(u, ops, need))
            if not miss_ne and not other_here:
                cr = chain_route(u, tgt)
                s_ = _near_shed(p)
                via_shed = _dist(p, s_) + 1 + _dist(s_, tgt) if shed_left.get("FERTILIZER", 0) > 0 else None
                if cr is not None and (via_shed is None or cr[0] < via_shed):
                    ap = (cr[1] % 10, cr[1] // 10)
                    if p != ap:
                        actions[u] = _step_toward(p, ap)
                    else:
                        actions[u] = ["COLLECT_FERTILIZER"]
                        chain_src.remove(cr[1])
                        S["log"]["rs_fert_chain"] += 1
                    continue
        if miss:
            s = _near_shed(p)
            if p != s:
                actions[u] = _step_toward(p, s)
                continue
            k = miss[0]''', 'action chain')
    return s


def main():
    s0 = base()
    variants = {
        'tw0': {},
        'rs1': {"sweep": 1},
        'rs2': {"sweep": 1, "wheat_batch": 1},
        'rs3': {"sweep": 1, "wheat_batch": 1, "fert_chain": 1},
    }
    for name, over in variants.items():
        s = s0
        if over:
            s = sub(s, 'CFG.update({"hand_stock": 1})   # ws2\n',
                    'CFG.update({"hand_stock": 1})   # ws2\nRS_CFG.update(%r)   # variant %s\n' % (over, name), name)
        if name in ('rs2', 'rs3'):
            s = s.replace('CFG.update({"hand_stock": 1})   # ws2\n',
                          'CFG.update({"hand_stock": 1, "pick_cap": {"WHEAT": 6, "FERTILIZER": 8}})   # ws2 + pick_cap\n', 1)
        out = ROOT / f'agents/mgt_lpv_{name}.py'
        out.write_bytes(s.encode('utf-8'))
        print(out)


if __name__ == '__main__':
    main()
