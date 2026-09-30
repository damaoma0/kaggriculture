"""V5 with a borrowed observation inside each private simulation only.

The frozen native policy reads its observation without mutating it or retaining
mutable aliases. An optional audit checks that contract on every simulated
turn. Rival-world tiles, engine state, and all agent memory are still copied.
"""
import ast
from functools import lru_cache
from hashlib import sha256
import inspect
from pathlib import Path
from types import FunctionType

import value_tape_search_v5 as F

PLANNER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()
SUPPORTED_AGENT = '1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470'


def mutable_ids(value, seen=None):
    """Audit helper; not part of the fast path."""
    seen = set() if seen is None else seen
    if isinstance(value, (dict, list, set)):
        if id(value) in seen:
            return seen
        seen.add(id(value))
        for item in value.values() if isinstance(value, dict) else value:
            mutable_ids(item, seen)
    elif isinstance(value, tuple):
        for item in value:
            mutable_ids(item, seen)
    return seen


class Runtime(F.Runtime):
    def __init__(self, audit=False):
        assert F.V.SOURCE_SHA256 == SUPPORTED_AGENT, 'Re-audit observation ownership after changing the native agent'
        self.audit = audit
        self.audited_turns = 0
        super().__init__()
        tree = ast.parse(inspect.getsource(F.V2.rollout))
        replacements = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'entry':
                arg = node.args[0]
                assert isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == 'deepcopy'
                node.args[0] = arg.args[0]
                replacements += 1
        assert replacements == 1
        namespace = dict(self.rollout_impl.__globals__)
        exec(compile(ast.fix_missing_locations(tree), '<borrowed_observation_rollout>', 'exec'), namespace)
        self.rollout_impl = namespace['rollout']

    def reset(self, memory=None, route=None, until=None):
        entry = super().reset(memory, route, until)
        if not self.audit:
            return entry
        snapshot = F.observation_copy
        ids = mutable_ids
        keys = F.V.MEMORY_KEYS
        def checked(obs):
            before = snapshot(obs)
            source_ids = ids(obs)
            action = entry(obs)
            assert obs == before, 'Native policy mutated its observation'
            retained = ids([self.chassis.players, *[self.ns[k] for k in keys]])
            assert not source_ids & retained, 'Policy retained mutable observation state'
            assert not source_ids & ids(action), 'Action aliases observation state'
            self.audited_turns += 1
            return action
        # shortlist inspects the native entry's namespace as well as calling it.
        return FunctionType(checked.__code__, self.ns, checked.__name__, closure=checked.__closure__)


@lru_cache(maxsize=1)
def runtime():
    return Runtime()


_choose = FunctionType(F.choose.__code__, dict(F.choose.__globals__, runtime=runtime,
    PLANNER_SHA256=PLANNER_SHA256), 'borrowed_observation_choose', F.choose.__defaults__)
_choose.__kwdefaults__ = F.choose.__kwdefaults__


def choose(obs, memory, *, count=7):
    selected, decision = _choose(obs, memory, count=count)
    decision['protocol'] = ('V4 search and admission; V5 reset isolation; frozen read-only native policy '
        'borrows each private simulation observation. No approximation, candidate pruning, or scenario removal.')
    return selected, decision
