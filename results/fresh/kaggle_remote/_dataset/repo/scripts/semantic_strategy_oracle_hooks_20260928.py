"""Exact executor hooks copied from frozen strategy_v4_modern4_finance.

Component-oracle diagnostics only; the engine and KB115LT are unchanged.
"""
from semantic_strategy_financing_20260928 import capital_pacing_products as _capital_pacing_products

def _unlock_execution(state, obs, day, hour):
    """Newly purchased land needs the executor's existing hourly dispatcher.

    KB's tier routes are fixed at dawn and omit then-locked squares. Switching
    only after an observed unlock retains the frozen executor implementation,
    uses actual worker positions, and restores tier planning at the next dawn.
    """
    if not state["config"].get("reactive_land_unlock") or state.get("unlock_switched"):
        return
    unlocked = len(obs["farms"][int(obs["player"])]["unlocked_quadrants"])
    if unlocked <= state["morning_land"]:
        return
    kb = state["kb"]
    kb.CFG.update(sd_tier=0, sd_budget0=.7, sd_budget=.35, sd_step_cap=.8, sd_plan_once=0)
    if kb._S is not None:
        kb._S.pop("tier", None)  # Some market guards also consult this cached route.
        for field in ("assign", "walk"):
            kb._S.get(field, {}).clear()
        lower = kb._sd_state(kb._S)
        lower["routes"].clear(); lower["walk"].clear()
        lower["lastP"] = None
        lower["first_of_day"] = True
    state["unlock_switched"] = True
    state["daily_diagnostic"]["observed_land_unlock"] = dict(day=day, hour=hour, unlocked=unlocked,
        execution="existing hourly dispatcher until next dawn")

def _finance_execution(state, obs):
    """Release observed shed goods only while today's admitted inputs need cash."""
    kb = state["kb"]
    books, audit = _capital_pacing_products(
        obs, kb._T, kb._S, state["executor_defaults"]["sd_books_sell"],
        state["config"].get("early_financing"), kb._walk_cap)
    kb.CFG["sd_books_sell"] = books
    if audit["active"]:
        state["daily_diagnostic"].setdefault("early_financing", []).append(audit)
