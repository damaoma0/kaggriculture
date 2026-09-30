"""Inventory-constrained reassignment of remaining daily work-order chains.

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


def schedule_cost(tasks, pos, step):
    """Predict unfinished tasks and total tardiness, respecting chain order."""
    time=step; x,y=pos; missed=0; late=0
    for task in tasks:
        tx,ty=task['target']
        time=max(time+abs(tx-x)+abs(ty-y),task['step'])
        if not task.get('waypoint'):
            missed += time >= (step//24+1)*24
            late += max(0,time-task['step'])
            time += 1
        x,y=tx,ty
    return missed,late


class Scheduler:
    def __init__(self):
        self.router = public.Agent()
        self.completed = set()
        self.start = None
        self.stats = Counter()
        self.assignment=[]
        self.day=-1

    def allocate(self, obs, orders, route):
        step=int(obs['step']);farm=obs['farms'][obs['player']]
        positions=[farm['farmer'],*farm['hands']]
        if self.day!=step//24:
            self.day=step//24;self.assignment=list(range(len(positions)))
        self.assignment.extend(range(len(self.assignment),len(positions)))
        # Until today's last hire, worker identities and positions determine
        # spawn locations. Preserve them rather than invalidating that plan.
        if any(o[0]=='HIRE' for a in route[step:min(len(route),(self.day+1)*24)] for o in a.get('market',[])):
            return
        inventories=obs['private']['inventories']
        signatures=[tuple(sorted((k,v) for k,v in inv.items() if v)) for inv in inventories]
        remaining={role:[t for t in orders.get(str(role),[]) if t['step']>=self.start and
                         (role,t['step'],t.get('waypoint',False)) not in self.completed]
                   for role in self.assignment}
        costs={(w,r):schedule_cost(remaining[r],pos,step) for w,pos in enumerate(positions) for r in self.assignment}
        # Greedy pair exchanges over complete remaining chains. Each exchange
        # strictly decreases the global lexicographic (missed, tardiness) cost,
        # so this terminates. Zero-lateness schedules retain their assignment.
        while True:
            best=None
            for i in range(len(positions)):
                for j in range(i+1,len(positions)):
                    if signatures[i]!=signatures[j]:continue
                    a,b=self.assignment[i],self.assignment[j]
                    old=tuple(x+y for x,y in zip(costs[i,a],costs[j,b]))
                    new=tuple(x+y for x,y in zip(costs[i,b],costs[j,a]))
                    gain=tuple(x-y for x,y in zip(old,new))
                    if new<old and (best is None or gain>best[0]):best=(gain,i,j)
            if best is None:break
            gain,i,j=best
            self.assignment[i],self.assignment[j]=self.assignment[j],self.assignment[i]
            self.stats['chain_swaps']+=1
            self.stats['predicted_missed_reduction']+=gain[0]
            self.stats['predicted_tardiness_reduction']+=gain[1]

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
        self.allocate(obs,orders,route)
        actions = []
        for worker, (x, y) in enumerate(positions):
            role=self.assignment[worker]
            tasks = orders.get(str(role), [])
            def key(t):return (role,t['step'],t.get('waypoint',False))
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
