"""Experimental timed work-order executor; retains the public production plan.

Requires data/router_work_orders.json and the public router in this repository.
This is not an arbitrary-board planner or a standalone competition submission.
"""
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'agents/public/tschinkel_router_v31.py'
spec = importlib.util.spec_from_file_location('scheduler_public', SOURCE)
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)
LIBRARY = json.loads((ROOT / 'data/router_work_orders.json').read_text())
assert LIBRARY['router_sha256'] == sha256(SOURCE.read_bytes()).hexdigest()


class Scheduler:
    def __init__(self):
        self.router = public.Agent()
        self.completed = set()
        self.start = None
        self.stats = Counter()

    def act(self, obs):
        step = int(obs['step'])
        if self.start is None:
            self.start = step
        # Select branches using the original observed-state rules.
        self.router.act(obs)
        route = self.router.R[self.router.cur]
        base = route[step]
        day = step // 24
        orders = LIBRARY['templates'][self.router.cur]['days'].get(str(day), {})
        farm = obs['farms'][obs['player']]
        positions = [farm['farmer'], *farm['hands']]
        source_actions = [base['farmer'], *base['hands']]
        actions = []
        for worker, (x, y) in enumerate(positions):
            tasks = orders.get(str(worker), [])
            def key(t):return (worker,t['step'],t.get('waypoint',False))
            task = None
            for t in tasks:
                if t['step'] < self.start or key(t) in self.completed:continue
                if t.get('waypoint') and step >= t['step'] and t['target']==[x,y]:
                    self.completed.add(key(t));continue
                task=t;break
            action = ['PASS']
            if task is not None:
                tx, ty = task['target']
                distance = abs(tx-x) + abs(ty-y)
                if distance and distance >= task['step']-step:
                    moves = [op for op, (dx, dy) in public.MOVES.items()
                             if abs(tx-x-dx)+abs(ty-y-dy) < distance]
                    original = source_actions[worker][0] if worker < len(source_actions) else 'PASS'
                    action = [original if original in moves else moves[0]]
                elif not distance and step >= task['step']:
                    action = list(task['action'])
                    self.completed.add(key(task))
                    self.stats['tasks_attempted'] += 1
                    self.stats['late_tasks'] += step > task['step']
                    self.stats['lateness_turns'] += step-task['step']
            actions.append(action)
        # Reuse source weed repair and projected-shed market rules, with our
        # chosen unit actions. Restore the immutable route before returning.
        replacement = dict(base, farmer=actions[0], hands=actions[1:])
        route[step] = replacement
        try:
            result = self.router.act(obs)
        finally:
            route[step] = base
        self.stats['calls'] += 1
        return result


_agent = None


def agent(obs):
    global _agent
    if _agent is None or obs['step'] == 0:
        _agent = Scheduler()
    return _agent.act(obs)
