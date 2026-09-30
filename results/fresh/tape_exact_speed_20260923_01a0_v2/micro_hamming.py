"""Actual tape-board working set; correctness and cache-sizing diagnostic."""
import json
import time
import run_local as H

H.verify()
N, _, points = H.imports()
entry = N.V.fresh_agent()
ns = entry.__globals__
obs = points[0]['obs']
board = ns['_mgt_labels'](ns['_mgt_board'](obs['farms'][int(obs['player'])]))
boards = [tape['lab'][day] for day in range(12, 30) for tape in ns['_MGT_TAPES']]
original = ns['_mgt_hamming']
expected = [original(board, other) for other in boards]
rows = []
for size in (8192, 32768):
    packed = N.PackedHamming(original, maxsize=size)
    for repeat in range(3):
        for name, match in [('original', original), ('packed', packed)]:
            t0, c0 = time.perf_counter(), time.process_time()
            actual = [match(board, other) for other in boards]
            row = dict(size=size, repeat=repeat, matcher=name,
                wall_seconds=time.perf_counter()-t0, cpu_seconds=time.process_time()-c0,
                cache=packed.encode.cache_info()._asdict())
            assert actual == expected
            rows.append(row)
            print(json.dumps(row), flush=True)
H.write(H.ROOT/'hamming_microbenchmark.json', dict(pairs=len(boards), rows=rows,
    caution='Component diagnostic on fixed boards, not full-search timing or policy evidence.'))
