"""agents/mgt_dsm_cx.py -> agents/mgt_dsm_cxr.py: two repair layers for replaying DSM's recorded commands on days 6-10
(user 2026-09-29: "why we can't be action-exact in days 6-10?" -> "let's do both").

Failure chain measured in n18rcx11 (scripts/failed_cmds_20260929.py, lead-dsm-114436723 / lead-mmpq-114320525):
day 6 the replay pays land + seeds and starts day 7 with $3; three day-7 wheat buys are refused, 11 FEEDs fail on the
cows' first production night (a missed feed on a production day wipes the care bank), the day-8 dawn trip sells 2 milk
where DSM sells ~12 and raises ~$1.7k by hour 6 (DSM buys its 3rd quadrant at day 8 hour 6-7 from $79-511 at dawn); the
$2,000 quadrant is never bought, and every tape command on it fails (61-94 a day on days 8-11).

  feed_first   every step: wheat the tape's FEEDs need over the next 24 steps minus the wheat in the shed / hands / this
               step's buys; if short, a BUY_PRODUCT WHEAT for the deficit goes first, and this step's BUY_SEED /
               BUY_ANIMAL / BUY_LAND orders that would leave less cash than that wheat costs are held back (never HIRE:
               one missing hand shifts every later hand's commands)
  land_retry   while we own fewer quadrants than the tape has bought by this step, BUY_LAND goes first whenever the cash
               covers it

usage: make_dsm_router_repair_20260929.py"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_dsm_cx.py"
DST = ROOT / "agents/mgt_dsm_cxr.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "terminal_liquidation": True,
    # tunables''', '''    "terminal_liquidation": True,
    "feed_first": False,       # repair (2026-09-29): the tape's feed wheat before seeds / animals / land
    "land_retry": False,       # repair (2026-09-29): a land purchase the tape made and we could not afford is retried
    # tunables''')
    s = sub(s, '''            if cfg["budget_guard"]:
                self._budget_guard(action, view, route, step)''', '''            if cfg["budget_guard"]:
                self._budget_guard(action, view, route, step)
            if cfg.get("land_retry"):
                self._land_retry(action, view, route, step)
            if cfg.get("feed_first"):
                self._feed_first(action, view, route, step)''')
    s = sub(s, '''    # ---- layer: room_guard ----------------------------------------------------''', '''    # ---- repair layers (2026-09-29) ------------------------------------------------
    def _land_retry(self, action, view, route, step):
        # target = the quadrants on the TAPE'S OWN BOARD (today's hour 0; tomorrow's once the tape has placed its land
        # order today) - not a count of BUY_LAND orders: DSM repeats the order (4 on day 8 in one tape), and counting them
        # bought a 4th quadrant DSM never owned (n18rcx12, +4,000 land; all 88 library tapes end with 3 quadrants)
        tape = self.routes[route]
        labs = globals().get("_MGT_TAPES")
        if not labs or not isinstance(route, int) or not (0 <= route < len(labs)):
            return
        lab = labs[route]["lab"]
        day = step // 24
        quads = lambda b: (100 - sum(1 for x in b if str(x).strip() == "L")) // 25
        target = quads(lab[min(day, len(lab) - 1)])
        if any(isinstance(tape[t], dict) and any(o and o[0] == "BUY_LAND" for o in (tape[t].get("market") or []))
               for t in range(day * 24, min(step + 1, len(tape)))):
            target = quads(lab[min(day + 1, len(lab) - 1)])
        market = action.setdefault("market", [])
        if view.quadrants >= target or any(o and o[0] == "BUY_LAND" for o in market):
            return
        extra = view.quadrants - 1
        if 0 <= extra < len(LAND_PRICES) and view.money >= LAND_PRICES[extra] and self._room_for_order(market):
            market.insert(0, ["BUY_LAND"])
            self.diagnostics["repair_land_retry"] = self.diagnostics.get("repair_land_retry", 0) + 1

    def _room_for_order(self, market):
        """the 10-order cap silently drops orders past index 9: make room by dropping the last non-HIRE order"""
        if len(market) < self.cfg["max_orders"]:
            return True
        for i in range(len(market) - 1, -1, -1):
            if market[i] and market[i][0] != "HIRE":
                del market[i]
                return True
        return False

    def _feed_first(self, action, view, route, step):
        tape = self.routes[route]
        feeds = 0
        for t in range(step, min(step + 24, len(tape))):
            a = tape[t] if isinstance(tape[t], dict) else {}
            for u in [a.get("farmer") or ["PASS"]] + list(a.get("hands") or []):
                if u and u[0] == "FEED":
                    feeds += 1
        market = action.setdefault("market", [])
        buying = sum(max(1, _int(o[2]) if len(o) > 2 else 1) for o in market
                     if o and o[0] == "BUY_PRODUCT" and len(o) > 1 and o[1] == "WHEAT")
        need = feeds - view.shed.get("WHEAT", 0) - view.in_hands("WHEAT") - buying
        if need <= 0:
            return
        wp = max(1, view.prices.get("WHEAT", 25))
        reserve = need * (wp + 2)
        cash = view.money + sum(max(0, _int(o[2]) if len(o) > 2 else 1) * view.prices.get(o[1], 0)
                                for o in market if o and o[0] == "SELL" and len(o) > 1)
        kept = []
        for o in market:
            cost = 0
            if o and o[0] == "BUY_SEED" and len(o) > 1:
                cost = SEED_PRICE.get(o[1], 0) * max(1, _int(o[2]) if len(o) > 2 else 1)
            elif o and o[0] == "BUY_ANIMAL" and len(o) > 1:
                cost = ANIMAL_COST.get(o[1], 0) * max(1, _int(o[2]) if len(o) > 2 else 1)
            elif o and o[0] == "BUY_LAND":
                extra = view.quadrants - 1
                cost = LAND_PRICES[extra] if 0 <= extra < len(LAND_PRICES) else 0
            if cost and cash - cost < reserve:
                self.diagnostics["repair_feed_held_" + o[0]] = self.diagnostics.get("repair_feed_held_" + o[0], 0) + 1
                continue
            cash -= cost
            kept.append(o)
        action["market"] = kept
        if self._room_for_order(kept):
            kept.insert(0, ["BUY_PRODUCT", "WHEAT", int(need)])
        self.diagnostics["repair_feed_wheat"] = self.diagnostics.get("repair_feed_wheat", 0) + int(need)

    # ---- layer: room_guard ----------------------------------------------------''')
    s = sub(s, "'terminal_liquidation': True}}", "'terminal_liquidation': True, 'feed_first': True, 'land_retry': True}}")
    # expose the chassis and a solvency check for the caller's early handover (user 2026-09-29: fix n18rcx14's swing -
    # 114565764 -16.7k: the replay spent like DSM without DSM's income, purchases refused, day-10 milk 3 vs 12)
    s = sub(s, """agent.mgt_telemetry = _MGT_REPORT""", """def mgt_replay_shortfall(observation, horizon=24):
    \"\"\"the tape's purchases over the next `horizon` steps (land, seeds, animals, feed wheat / fertilizer, hires) minus
    our cash and the value of the stock the tape plans to sell in that window (the budget guard's own arithmetic)\"\"\"
    ch = getattr(_MGT_IMPL, "chassis", None)
    if ch is None:
        return 0.0
    step = _step_of(observation)
    player = _int(_get(observation, "player", 0))
    st = ch._state(player, step)
    route = st.get("route")
    if route not in ch.routes:
        return 0.0
    view = _View(observation, player, ch.cfg)
    budget, _need = ch._block_requirements(view, route, step, step + horizon)
    cash = view.money
    for item in PRODUCTS:
        planned = ch.future_sells(route, item, step) - ch.future_sells(route, item, step + horizon)
        cash += min(view.shed.get(item, 0), planned) * view.prices.get(item, 0)
    return float(budget - cash)


def mgt_replay_distance(observation):
    \"\"\"tiles where our board differs from the current tape's own board for today (the router's Hamming distance,
    weeds ignored) - how far the replay has drifted from the game its commands were recorded in\"\"\"
    ch = getattr(_MGT_IMPL, "chassis", None)
    if ch is None:
        return 0
    step = _step_of(observation)
    player = _int(_get(observation, "player", 0))
    route = ch._state(player, step).get("route")
    if not isinstance(route, int) or not (0 <= route < len(_MGT_TAPES)):
        return 0
    lab = _MGT_TAPES[route]["lab"]
    farm = (_get(observation, "farms", []) or [])[player]
    return int(_mgt_hamming(_mgt_labels(_mgt_board(farm)), lab[min(step // 24, len(lab) - 1)]))


agent.mgt_telemetry = _MGT_REPORT""")
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()
