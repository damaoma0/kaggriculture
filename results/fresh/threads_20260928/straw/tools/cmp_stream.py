"""compare two arms' streams + money on a world. usage: cmp_stream.py ARM_A ARM_B ep"""
import json, sys
R = 'C:/Users/xyygl/Documents/kaggriculture/results/fresh/'
a, b, ep = sys.argv[1], sys.argv[2], sys.argv[3]
sa = json.load(open(R + f'day12_viz/{a.lower()}_streams/{ep}.json'))
sb = json.load(open(R + f'day12_viz/{b.lower()}_streams/{ep}.json'))
A, B = sa['actions'], sb['actions']
lo, hi = sa.get('first_step', 264), sa.get('last_step', 719)
diff = [t for t in range(min(len(A), len(B))) if A[t] != B[t]]
print('len', len(A), len(B), 'steps', lo, hi, 'differing steps', len(diff), 'first', diff[:5])
ma = json.load(open(R + f'sector_20260925/multi/{a}/{ep}.json'))['money']
mb = json.load(open(R + f'sector_20260925/multi/{b}/{ep}.json'))['money']
print('money30', ma['30'], mb['30'], 'daily money identical', ma == mb)
