"""V8 search with exact, bounded caches for scenarios and board matching.

The candidate search and admission code is V8's unchanged function. Scenario
work is shared only inside one decision; no forecast or outcome is cached.
Board encoding uses tuple contents, so mutating or reusing a list cannot leave
a stale distance. The private runtime never changes the live agent or engine.
"""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from types import FunctionType, SimpleNamespace

import value_tape_search_v8 as B

V, F = B.V, B.F
PLANNER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()


class WorldBatch:
    """Share the observation-only work of the original eight-world model."""

    def __init__(self, obs):
        self.obs = obs
        self.day = int(obs['day'])
        self.farm = obs['farms'][1-int(obs['player'])]
        self.pool = None
        self.target = None
        self.distances = {}
        self.profile_evaluations = self.board_evaluations = 0
        model = SimpleNamespace(**vars(B.M.M))
        model.ideal_flows = self.ideal_flows
        namespace = dict(B.M.world.__globals__, M=model, select_donor=self.select_donor)
        self._world = FunctionType(B.M.world.__code__, namespace,
                                  'shared_work_world', B.M.world.__defaults__)

    def ideal_flows(self, farm, day):
        assert farm is self.farm and day == self.day
        if self.target is None:
            self.target = B.M.M.ideal_flows(farm, day)
            self.profile_evaluations += 1
        return self.target

    def select_donor(self, obs, shops, index):
        assert obs is self.obs
        model = B.M.M
        if self.pool is None:
            ranked = []
            for row in B.M.training_library():
                distance = model.board_distance(self.farm, row['farms'][self.day])
                self.distances[id(row)] = distance
                self.board_evaluations += 1
                score = distance + .6*model.shop_distance(
                    obs['town']['unlocked_shops'], row['shops'][self.day])
                ranked.append((score, row))
            ranked.sort(key=lambda x: (x[0], x[1]['episode']))
            self.pool = ranked[:12]
        choices = []
        for score, row in self.pool:
            future = sum(model.shop_distance(shops[d], row['shops'][d])
                         for d in range(self.day+3, 30, 3))
            choices.append((score + .25*future, row))
        choices.sort(key=lambda x: (x[0], x[1]['episode']))
        score, donor = choices[(index//2) % 3]
        return donor, dict(episode=donor['episode'], distance=score,
                          public_board_distance=self.distances[id(donor)])

    def world(self, obs, index):
        assert obs is self.obs, 'Create a new WorldBatch for every decision'
        return self._world(obs, index)


class PackedHamming:
    """Exact unequal-tile count, with bounded content-addressed encodings.

    Two ASCII characters occupy one 16-bit lane. OR-folding the XOR into each
    lane's bottom bit and counting those bits equals the original zip/sum.
    Unusual labels and unequal lengths retain the original implementation.
    No cache is keyed by a mutable list's identity.
    """

    def __init__(self, original, maxsize=32768):
        self.original = original
        self.encode = lru_cache(maxsize=maxsize)(self._encode)

    @staticmethod
    def _encode(labels):
        if not all(isinstance(x, str) and len(x) == 2 and x.isascii() for x in labels):
            return None
        packed = int.from_bytes(''.join(labels).encode('ascii'), 'little')
        mask = ((1 << (16*len(labels))) - 1) // 65535
        return packed, mask

    def __call__(self, a, b):
        a, b = tuple(a), tuple(b)
        if len(a) != len(b):
            return self.original(a, b)
        try:
            left, right = self.encode(a), self.encode(b)
        except TypeError:  # Preserve equality for unhashable labels, too.
            return self.original(a, b)
        if left is None or right is None:
            return self.original(a, b)
        diff = left[0] ^ right[0]
        diff |= diff >> 8
        diff |= diff >> 4
        diff |= diff >> 2
        diff |= diff >> 1
        return (diff & left[1]).bit_count()


class Runtime(B.Runtime):
    def __init__(self, *, packed_boards=True):
        super().__init__()
        self.packed_hamming = None
        if packed_boards:
            self.packed_hamming = PackedHamming(self.ns['_mgt_hamming'])
            self.ns['_mgt_hamming'] = self.packed_hamming

    def prepare(self, obs):
        super().prepare(obs)
        self.world_batch = WorldBatch(obs)


@lru_cache(maxsize=1)
def runtime():
    return Runtime()


def _world(obs, index):
    return runtime().world_batch.world(obs, index)


M = SimpleNamespace(world=_world, MODEL_SHA256=B.M.MODEL_SHA256)
_namespace = dict(B.choose.__globals__, runtime=runtime, M=M,
                  PLANNER_SHA256=PLANNER_SHA256)
choose = FunctionType(B.choose.__code__, _namespace, 'choose', B.choose.__defaults__)
choose.__kwdefaults__ = B.choose.__kwdefaults__.copy()


if __name__ == '__main__':
    raise SystemExit('Research selector: import choose(obs, own_memory).')
