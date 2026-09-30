"""Tape coverage under limited resources: structure of the embedded UMG tape library (offline, no games).

Reads the library exactly as shipped in agents/mgt_m1.py (the zlib+base85 `_MGT_LIB` blob, read-only) and measures:

  A  action-space redundancy: tapes byte-identical through day d, day-trie size, when and why tapes diverge
     (first differing shop vs other causes)
  B  bytes: what the blob is made of and what better encodings (token streams, lzma, board deltas, day-trie) cost,
     measured on the 584 tapes and on random subsets (marginal bytes per tape)
  C  board-space redundancy at days 6..24: the router's own label comparison (2-char labels, weeds as empty,
     Hamming <= 8): exact distinct boards, per-tape compatible counts, single-linkage components, greedy radius-8 cover
  D  late-shop coverage per board cluster / per compatible neighbourhood: exact counts and probability mass of the
     unknown late shop space, and expected best demand distance (router metric) under uniform shop draws
  E  partial-tape thought experiment on the largest day-12 (and day-15) cluster: K extra tapes sharing its board
     trajectory with designed or natural (random) late shops
  F  pruning / under-covered demand diagnostics

Shop draws are uniform with replacement over the 8 shop types (engine: rng.choice(sorted(SHOPS))), so every
probability below is exact under that model. Nothing here runs the engine.

Usage: .venv/Scripts/python.exe scripts/library_structure_analysis.py [--quick]
Writes results/fresh/newphase_20260923/library_structure/{action_redundancy,encodings,board_clusters,
late_coverage,partial_tapes,pruning}.json
"""
import base64, hashlib, heapq, json, lzma, math, re, sys, time, zlib
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'agents/mgt_m1.py'
OUT = ROOT / 'results/fresh/newphase_20260923/library_structure'

DEMAND = {'BAKERY': {'EGG': 1, 'WHEAT': 1}, 'PIZZA_SHOP': {'MILK': 1, 'TOMATO': 1, 'WHEAT': 1},
          'BRUNCH_SPOT': {'EGG': 1, 'WHEAT': 1, 'STRAWBERRY': 1}, 'YARN_STORE': {'WOOL': 2},
          'ICE_CREAM_SHOP': {'STRAWBERRY': 1, 'MILK': 1, 'WHEAT': 1}, 'PET_CAFE': {'CARROT': 2},
          'SMOOTHIE_SHOP': {'STRAWBERRY': 1, 'MILK': 1},
          'FARMERS_MARKET': {'WHEAT': 1, 'CARROT': 1, 'TOMATO': 1, 'STRAWBERRY': 1}}
SHOPS = sorted(DEMAND)                                     # engine draws rng.choice(sorted(SHOPS))
PRODUCTS = ('STRAWBERRY', 'TOMATO', 'WOOL', 'CARROT', 'MILK', 'EGG', 'WHEAT')
W = np.array([3.0, 2.0, 2.0, 1.5, 1.5, 1.0, 0.5])          # _MGT_WEIGHT in router order
CHECKPOINTS = (2, 4, 5, 6, 8)
MAX_H = 8                                                  # _MGT_CFG['max_hamming']
SHOP_VEC = np.array([[DEMAND[s].get(p, 0) for p in PRODUCTS] for s in SHOPS], float)   # (8, 7)
DAYS = (6, 9, 12, 15, 18, 21, 24)
LIMIT_BYTES = 100 * 1024 * 1024                            # competition overview: 100 MiB submission


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ----------------------------------------------------------------------------------------------------- loading
def load_library(path=AGENT):
    src = path.read_text(encoding='utf-8')
    m = re.search(r"_mgt_b64\.b85decode\('([^']*)'\)", src)
    blob = m.group(1)
    z = base64.b85decode(blob)
    raw = zlib.decompress(z)
    lib = json.loads(raw)
    fb = len(src.encode('utf-8'))
    meta = dict(agent=str(path.relative_to(ROOT)), agent_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                file_bytes=fb, blob_b85_chars=len(blob), blob_zlib_bytes=len(z), blob_json_bytes=len(raw),
                code_bytes=fb - len(blob), tapes=len(lib['tapes']), unique_actions=len(lib['actions']))
    return lib, meta


def router_labels(board):
    """_mgt_labels with relaxed_compat off (m1 config): 2-char labels, weeds (' w') compared as empty."""
    out = [board[i:i + 2] for i in range(0, len(board), 2)]
    return [' .' if x == ' w' else x for x in out]


def comp_prob(counts):
    """probability of an unordered multiset of m i.i.d. uniform shop draws (counts over the 8 shops)."""
    m = sum(counts)
    return math.factorial(m) / np.prod([math.factorial(c) for c in counts]) / 8 ** m


def comp_of(seq):
    c = [0] * 8
    for s in seq:
        c[s] += 1
    return tuple(c)


def cum_vecs(seq_idx):
    """(9, 7) cumulative demand after 0..8 reveals."""
    out = np.zeros((9, 7))
    cur = np.zeros(7)
    for j, s in enumerate(seq_idx[:8]):
        cur = cur + SHOP_VEC[s]
        out[j + 1] = cur
    for j in range(len(seq_idx[:8]) + 1, 9):
        out[j] = cur
    return out


# ------------------------------------------------------------------------------------------ A: action redundancy
def action_redundancy(T, S):
    n = len(T)
    ids = np.array([t['ids'] for t in T], dtype=np.int32)          # (n, 719)
    steps = ids.shape[1]
    res = {'tapes': n, 'steps_per_tape': steps}
    rows = []
    trie_nodes = 0
    for d in range(1, 31):
        L = min(24 * d, steps)
        c = Counter(ids[i, :L].tobytes() for i in range(n))
        sizes = sorted(c.values(), reverse=True)
        k = min(8, (d - 1) // 3)      # shops visible during day d-1, the last day of this prefix
        shop_pref = len({tuple(S[i, :k]) for i in range(n)}) if k else 1
        rows.append(dict(day=d, steps=L, distinct_prefixes=len(c), largest_group=sizes[0],
                         tapes_sharing_prefix=int(sum(s for s in sizes if s > 1)),
                         shops_visible_on_last_day=k, distinct_ordered_shop_prefixes=shop_pref))
        trie_nodes += len(c)
    res['prefix_by_day'] = rows
    segs = set()
    for i in range(n):
        for d in range(1, 31):
            segs.add(ids[i, 24 * (d - 1):min(24 * d, steps)].tobytes())
    res['day_trie_nodes'] = trie_nodes
    res['day_segments_total'] = n * 30
    res['day_segments_unique'] = len(segs)
    # pairwise longest common action prefix (steps)
    lcp = np.zeros((n, n), dtype=np.int32)
    for i in range(n):
        neq = ids != ids[i]
        anyd = neq.any(axis=1)
        lcp[i] = np.where(anyd, neq.argmax(axis=1), steps)
    np.fill_diagonal(lcp, -1)
    near = lcp.max(axis=1)                                           # steps shared with the closest other tape
    res['nearest_tape_shared_days'] = dict(
        hist={int(d): int(c) for d, c in sorted(Counter((near // 24).tolist()).items())},
        median_day=float(np.median(near / 24.0)), mean_day=float(np.mean(near / 24.0)),
        tapes_unique_before_day3=int((near < 72).sum()), tapes_shared_through_day6=int((near >= 144).sum()),
        tapes_shared_through_day9=int((near >= 216).sum()), tapes_shared_through_day12=int((near >= 288).sum()))
    # why do two tapes diverge? first differing shop position p (1..8, 9 = same 8 shops); it is visible from
    # step 72*p (day 3p, hour 0). Divergence before that step has a non-shop cause (weeds, prices, opponent).
    iu = np.triu_indices(n, 1)
    L = lcp[iu]
    diff = S[:, None, :] != S[None, :, :]
    anyd = diff.any(axis=2)
    firstp = np.where(anyd, diff.argmax(axis=2) + 1, 9)[iu]
    by_p = []
    for p in range(1, 10):
        sel = firstp == p
        if not sel.any():
            continue
        Lp = L[sel]
        vis = 72 * p if p <= 8 else 10 ** 9
        by_p.append(dict(first_differing_shop=p if p <= 8 else 'none', pairs=int(sel.sum()),
                         diverge_before_shop_visible=float((Lp < vis).mean()) if p <= 8 else 1.0,
                         diverge_on_reveal_day=float(((Lp >= vis) & (Lp < vis + 24)).mean()) if p <= 8 else 0.0,
                         median_divergence_day=float(np.median(Lp / 24.0)),
                         max_divergence_day=float(Lp.max() / 24.0)))
    res['divergence_vs_first_shop_difference'] = by_p
    # pairs with the same first k shops: share their actions until the next reveal?
    same_k = []
    for k in range(1, 8):
        eq = (~diff[:, :, :k]).all(axis=2)[iu]
        if eq.sum() == 0:
            continue
        Lk = L[eq]
        same_k.append(dict(k=k, pairs=int(eq.sum()),
                           identical_until_next_reveal=float((Lk >= 72 * (k + 1)).mean()),
                           identical_until_this_reveal=float((Lk >= 72 * k).mean()),
                           median_divergence_day=float(np.median(Lk / 24.0))))
    res['pairs_with_same_first_k_shops'] = same_k
    return res, ids, lcp


# --------------------------------------------------------------------------------------------------- B: encodings
def jdump(x):
    return json.dumps(x, separators=(',', ':')).encode('utf-8')


def zsize(b):
    return len(zlib.compress(b, 9))


def xsize(b):
    return len(lzma.compress(b, preset=9))


def b85len(nbytes):
    return int(math.ceil(nbytes / 4.0) * 5)


def sub_library(lib, idx):
    """library restricted to tapes idx with the action table rebuilt (the builder's dedup)."""
    A = lib['actions']
    used = sorted({j for i in idx for j in lib['tapes'][i]['ids']})
    remap = {j: r for r, j in enumerate(used)}
    tapes = []
    for i in idx:
        t = dict(lib['tapes'][i])
        t['ids'] = [remap[j] for j in t['ids']]
        tapes.append(t)
    return dict(actions=[A[j] for j in used], tapes=tapes)


class TokenCodec:
    """Factorised step encoding: farmer token, hand count, hand tokens, market count, market tokens (uint16)."""

    def __init__(self):
        self.unit, self.mkt = {}, {}

    def tok(self, table, x):
        k = json.dumps(x, separators=(',', ':'))
        if k not in table:
            table[k] = len(table)
        return table[k]

    def step(self, a):
        out = [self.tok(self.unit, a.get('farmer') or ['PASS'])]
        h = a.get('hands') or []
        out.append(len(h))
        out += [self.tok(self.unit, x) for x in h]
        m = a.get('market') or []
        out.append(len(m))
        out += [self.tok(self.mkt, x) for x in m]
        return out

    def vocab_bytes(self):
        return jdump([list(self.unit), list(self.mkt)])


def label_codes(T):
    voc = {}
    B = np.zeros((len(T), 30, 100), np.uint8)
    for i, t in enumerate(T):
        for d, b in enumerate(t['boards']):
            for j, x in enumerate(router_labels(b)):
                if x not in voc:
                    voc[x] = len(voc)
                B[i, d, j] = voc[x]
    return B, voc


def encode_variants(lib, want=('current', 'current_lzma', 'tok', 'trie')):
    A, T = lib['actions'], lib['tapes']
    out = {}
    if 'current' in want or 'current_lzma' in want:
        js = jdump(lib)
        if 'current' in want:
            z = zsize(js)
            out['current_json_zlib9'] = dict(bytes=z, b85_chars=b85len(z), raw_json=len(js))
        if 'current_lzma' in want:
            x = xsize(js)
            out['current_json_lzma'] = dict(bytes=x, b85_chars=b85len(x), raw_json=len(js))
    codec = TokenCodec()
    streams = []
    for t in T:
        s = []
        for j in t['ids']:
            s += codec.step(A[j])
        streams.append(np.array(s, dtype=np.uint16))
    assert len(codec.unit) < 65536 and len(codec.mkt) < 65536
    B, voc = label_codes(T)
    shops = np.array([[SHOPS.index(s) for s in t['shops']] for t in T], np.uint8)
    eps = np.array([int(t['ep']) for t in T], np.uint32)
    lens = np.array([len(s) for s in streams], np.uint32)
    header = codec.vocab_bytes() + jdump(sorted(voc, key=voc.get))
    tok_bytes = b''.join(s.tobytes() for s in streams)
    # boards as day deltas: code where the tile changed since the previous morning, 255 elsewhere
    Bd = B.copy()
    Bd[:, 1:, :] = np.where(B[:, 1:, :] != B[:, :-1, :], B[:, 1:, :], 255)
    body_plain = header + lens.tobytes() + tok_bytes + B.tobytes() + shops.tobytes() + eps.tobytes()
    body_delta = header + lens.tobytes() + tok_bytes + Bd.tobytes() + shops.tobytes() + eps.tobytes()
    if 'tok_min' in want:
        xd = xsize(body_delta)
        out['token_stream_board_deltas_lzma'] = dict(bytes=xd, b85_chars=b85len(xd), raw=len(body_delta))
    if 'tok' in want:
        out['token_stream_boards_zlib9'] = dict(bytes=zsize(body_plain), raw=len(body_plain))
        xb = xsize(body_plain)
        out['token_stream_boards_lzma'] = dict(bytes=xb, b85_chars=b85len(xb), raw=len(body_plain))
        xd = xsize(body_delta)
        out['token_stream_board_deltas_lzma'] = dict(bytes=xd, b85_chars=b85len(xd), raw=len(body_delta))
        out['parts_lzma'] = dict(vocab=xsize(header), action_tokens=xsize(tok_bytes),
                                 boards_plain=xsize(B.tobytes()), boards_delta=xsize(Bd.tobytes()),
                                 shops_eps=xsize(shops.tobytes() + eps.tobytes()))
        out['vocab'] = dict(unit_actions=len(codec.unit), market_orders=len(codec.mkt), board_labels=len(voc),
                            tokens_total=int(sum(len(s) for s in streams)))
    if 'trie' in want:
        # explicit day-trie over action ids: node = distinct prefix through day d; store parent + day segment tokens
        ids = [t['ids'] for t in T]
        node_of, nodes = {}, []
        leaf = []
        for i, t in enumerate(T):
            parent = -1
            for d in range(1, 31):
                key = (parent, tuple(ids[i][24 * (d - 1):min(24 * d, 719)]))
                if key not in node_of:
                    node_of[key] = len(nodes)
                    seg = []
                    for j in key[1]:
                        seg += codec.step(A[j])
                    nodes.append((parent, np.array(seg, np.uint16)))
                parent = node_of[key]
            leaf.append(parent)
        par = np.array([p for p, _ in nodes], np.int32)
        seglen = np.array([len(s) for _, s in nodes], np.uint16)
        segs = b''.join(s.tobytes() for _, s in nodes)
        # boards deduplicated globally: table of unique (label-normalised) boards + 30 ids per tape
        bt = {}
        bid = np.zeros((len(T), 30), np.uint32)
        for i in range(len(T)):
            for d in range(30):
                k = B[i, d].tobytes()
                if k not in bt:
                    bt[k] = len(bt)
                bid[i, d] = bt[k]
        btab = b''.join(bt)
        body = (codec.vocab_bytes() + par.tobytes() + seglen.tobytes() + segs + np.array(leaf, np.uint32).tobytes()
                + btab + bid.tobytes() + shops.tobytes() + eps.tobytes())
        xt = xsize(body)
        out['day_trie_boardtable_lzma'] = dict(bytes=xt, b85_chars=b85len(xt), raw=len(body), trie_nodes=len(nodes),
                                               unique_boards=len(bt), board_slots=len(T) * 30)
    return out, streams, B, voc


def late_segment_bytes(lib, streams_from_step=288, board_from_day=12):
    """lzma bytes of the late part only (actions from step 288, boards from day 12) for the whole library."""
    A, T = lib['actions'], lib['tapes']
    codec = TokenCodec()
    ss = []
    for t in T:
        s = []
        for j in t['ids'][streams_from_step:]:
            s += codec.step(A[j])
        ss.append(np.array(s, np.uint16))
    B, voc = label_codes(T)
    Bd = B.copy()
    Bd[:, 1:, :] = np.where(B[:, 1:, :] != B[:, :-1, :], B[:, 1:, :], 255)
    body = codec.vocab_bytes() + b''.join(s.tobytes() for s in ss) + Bd[:, board_from_day:, :].tobytes()
    return xsize(body)


def encodings(lib, meta, quick=False):
    log('B: encodings on the full library')
    full, streams, B, voc = encode_variants(lib, want=('current', 'tok', 'trie') if quick else
                                            ('current', 'current_lzma', 'tok', 'trie'))
    res = {'full_library': full, 'shipped': meta}
    # composition of the shipped JSON (each part compressed on its own with zlib 9)
    T = lib['tapes']
    parts = dict(actions_table=jdump(lib['actions']), tape_ids=jdump([t['ids'] for t in T]),
                 tape_boards=jdump([t['boards'] for t in T]),
                 tape_shops_ep_modal=jdump([[t['shops'], t['ep'], t.get('modal')] for t in T]))
    res['shipped_json_parts'] = {k: dict(raw=len(v), zlib9=zsize(v)) for k, v in parts.items()}
    log('B: marginal bytes per tape from random subsets')
    rng = np.random.default_rng(20260923)
    sizes = (73, 146, 292, 438, 584) if not quick else (146, 584)
    draws = 2 if not quick else 1
    rows = []
    for N in sizes:
        for r in range(draws if N < len(T) else 1):
            idx = sorted(rng.choice(len(T), size=N, replace=False).tolist())
            sub = sub_library(lib, idx)
            e, _, _, _ = encode_variants(sub, want=('current', 'tok_min'))
            rows.append(dict(N=N, draw=r, unique_actions=len(sub['actions']),
                             current_json_zlib9=e['current_json_zlib9']['bytes'],
                             token_board_deltas_lzma=e['token_stream_board_deltas_lzma']['bytes']))
            log('   N', N, rows[-1])
    res['subsets'] = rows
    fits = {}
    for key in ('current_json_zlib9', 'token_board_deltas_lzma', 'unique_actions'):
        xs = np.array([r['N'] for r in rows if r['N'] >= 146], float)
        ys = np.array([r[key] for r in rows if r['N'] >= 146], float)
        slope, icpt = np.polyfit(xs, ys, 1)
        fits[key] = dict(per_tape=float(slope), intercept=float(icpt))
    res['marginal_fit_N146_584'] = fits
    code = meta['code_bytes']
    cur_b85 = fits['current_json_zlib9']['per_tape'] * 1.25
    best_b85 = fits['token_board_deltas_lzma']['per_tape'] * 1.25
    best_bin = fits['token_board_deltas_lzma']['per_tape']
    res['capacity_estimate_100MiB'] = dict(
        limit_bytes=LIMIT_BYTES, code_bytes=code,
        current_encoding_b85_per_tape=cur_b85,
        tapes_current_encoding=int((LIMIT_BYTES - code - fits['current_json_zlib9']['intercept'] * 1.25) / cur_b85),
        better_encoding_b85_per_tape=best_b85,
        tapes_better_encoding_b85_in_py=int((LIMIT_BYTES - code - fits['token_board_deltas_lzma']['intercept'] * 1.25) / best_b85),
        better_encoding_binary_per_tape=best_bin,
        tapes_better_encoding_binary=int((LIMIT_BYTES - code - fits['token_board_deltas_lzma']['intercept']) / best_bin),
        note='linear extrapolation of the marginal bytes of tapes drawn from THIS corpus; new tapes from other worlds '
             'or policies may share less (larger marginal cost).')
    log('B: late-segment bytes')
    late = late_segment_bytes(lib)
    res['late_segment_day12_on_lzma'] = dict(bytes_total=late, bytes_per_tape_avg=late / len(T))
    return res, B, voc


# ----------------------------------------------------------------------------------------------- C: board clusters
def hamming_matrix(Bd):
    n = Bd.shape[0]
    H = np.zeros((n, n), np.int16)
    for a in range(0, n, 128):
        H[a:a + 128] = (Bd[a:a + 128, None, :] != Bd[None, :, :]).sum(axis=2)
    return H


def components(adj):
    n = adj.shape[0]
    comp = -np.ones(n, int)
    c = 0
    for s in range(n):
        if comp[s] >= 0:
            continue
        stack = [s]
        comp[s] = c
        while stack:
            u = stack.pop()
            for v in np.nonzero(adj[u] & (comp < 0))[0]:
                comp[v] = c
                stack.append(v)
        c += 1
    return comp


def greedy_cover(adj):
    """repeatedly take the tape whose radius-8 ball holds the most uncovered tapes; members go to the first ball."""
    n = adj.shape[0]
    unc = np.ones(n, bool)
    centers, assign = [], -np.ones(n, int)
    while unc.any():
        gain = (adj & unc[None, :]).sum(axis=1)
        c = int(np.argmax(gain))
        mem = adj[c] & unc
        assign[mem] = len(centers)
        centers.append(c)
        unc &= ~mem
    return centers, assign


def board_clusters(B, S):
    n = B.shape[0]
    res = {}
    Hs, adjs, clus = {}, {}, {}
    for D in DAYS:
        Bd = B[:, D, :]
        H = hamming_matrix(Bd)
        adj = H <= MAX_H
        Hs[D], adjs[D] = H, adj
        deg = adj.sum(axis=1) - 1
        comp = components(adj)
        cs = Counter(comp.tolist())
        centers, assign = greedy_cover(adj)
        sizes = sorted(Counter(assign.tolist()).values(), reverse=True)
        cum = np.cumsum(sizes) / n
        clus[D] = (centers, assign)
        # exact distinct boards
        distinct = len({Bd[i].tobytes() for i in range(n)})
        res[D] = dict(day=D, shops_known=D // 3, distinct_boards=distinct,
                      compatible_other_tapes=dict(median=float(np.median(deg)), mean=float(deg.mean()),
                                                  p10=float(np.percentile(deg, 10)), p90=float(np.percentile(deg, 90)),
                                                  isolated=int((deg == 0).sum())),
                      single_linkage_components=len(cs), largest_component=max(cs.values()),
                      singleton_components=sum(1 for v in cs.values() if v == 1),
                      greedy_radius8_clusters=len(centers), largest_greedy_cluster=sizes[0],
                      greedy_clusters_for_50pct=int(np.searchsorted(cum, 0.5) + 1),
                      greedy_clusters_for_90pct=int(np.searchsorted(cum, 0.9) + 1),
                      greedy_singletons=sum(1 for s in sizes if s == 1),
                      greedy_cluster_sizes_top10=sizes[:10],
                      median_pairwise_hamming=float(np.median(H[np.triu_indices(n, 1)])))
    return res, Hs, adjs, clus


# ------------------------------------------------------------------------------------ D: late-shop space & coverage
def suffix_classes(k):
    """the checkpoint-relevant classes of the unknown shops k+1..8: vectors S(j) = demand of shops k+1..j for
    checkpoints j > k. Returns class matrix (U, J, 7), probability (U,), dict ordered-suffix -> class id."""
    m = 8 - k
    J = [j for j in CHECKPOINTS if j > k]
    cls, prob, of = {}, [], {}
    mats = []
    for seq in product(range(8), repeat=m):
        cur = np.zeros(7)
        vs = []
        for pos, s in enumerate(seq):
            cur = cur + SHOP_VEC[s]
            if k + pos + 1 in J:
                vs.append(cur.copy())
        key = tuple(np.concatenate(vs).astype(int).tolist())
        if key not in cls:
            cls[key] = len(cls)
            prob.append(0.0)
            mats.append(np.array(vs))
        prob[cls[key]] += 1.0 / 8 ** m
        of[seq] = cls[key]
    return np.array(mats), np.array(prob), of, J


def late_distance_matrix(M):
    """weighted L1 between classes, summed over the late checkpoints: (U, U)."""
    U = M.shape[0]
    D = np.zeros((U, U))
    for a in range(0, U, 256):
        D[a:a + 256] = (np.abs(M[a:a + 256, None, :, :] - M[None, :, :, :]) * W).sum(axis=(2, 3))
    return D


def compositions(m):
    out = []

    def rec(prefix, left, pos):
        if pos == 7:
            out.append(tuple(prefix + [left]))
            return
        for c in range(left, -1, -1):
            rec(prefix + [c], left - c, pos + 1)
    rec([], m, 0)
    return out


def late_coverage(S, adjs, clus, V):
    """per day: late (unknown) shop space vs what each greedy cluster / compatible neighbourhood carries."""
    n = S.shape[0]
    res = {}
    cache = {}
    for D in (12, 15, 18):
        k = D // 3
        m = 8 - k
        M, p, of, J = suffix_classes(k)
        Dl = late_distance_matrix(M)
        comps = compositions(m)
        cprob = {c: comp_prob(c) for c in comps}
        tcls = np.array([of[tuple(S[i, k:8].tolist())] for i in range(n)])
        tcomp = [comp_of(S[i, k:8].tolist()) for i in range(n)]
        pref_comp = [comp_of(S[i, :k].tolist()) for i in range(n)]
        cache[D] = (M, p, of, J, Dl, tcls, tcomp, cprob)
        adj = adjs[D]
        centers, assign = clus[D]
        # ---- per greedy cluster
        crow = []
        for g, c in enumerate(centers):
            mem = np.nonzero(assign == g)[0]
            cc = {tcomp[i] for i in mem}
            kc = set(tcls[mem].tolist())
            # conditional: for each member, other members with the same (unordered) prefix composition
            same_pref = [sum(1 for j in mem if j != i and pref_comp[j] == pref_comp[i]) for i in mem]
            crow.append(dict(cluster=g, center_ep=None, size=int(len(mem)),
                             distinct_prefix_compositions=len({pref_comp[i] for i in mem}),
                             distinct_ordered_shops5_8=len({tuple(S[i, 4:8]) for i in mem}),
                             distinct_compositions_shops5_8=len({comp_of(S[i, 4:8].tolist()) for i in mem}),
                             composition_mass_shops5_8=float(sum(comp_prob(x) for x in {comp_of(S[i, 4:8].tolist()) for i in mem})),
                             distinct_ordered_suffixes=len({tuple(S[i, k:8]) for i in mem}),
                             suffix_compositions=len(cc), suffix_compositions_total=len(comps),
                             suffix_composition_mass=float(sum(cprob[x] for x in cc)),
                             checkpoint_classes=len(kc), checkpoint_classes_total=int(len(p)),
                             checkpoint_class_mass=float(p[list(kc)].sum()),
                             members_with_same_prefix_composition_mean=float(np.mean(same_pref))))
        sizes = np.array([r['size'] for r in crow])
        big = [r for r in crow if r['size'] >= 2]
        # ---- per tape neighbourhood (what a farm on tape i's board can switch to)
        nb = []
        for i in range(n):
            C = np.nonzero(adj[i])[0]
            cc = {tcomp[j] for j in C}
            kc = sorted(set(tcls[C].tolist()))
            best_late = Dl[:, kc].min(axis=1)
            own_late = Dl[:, tcls[i]]
            nb.append((len(C), len(cc), sum(cprob[x] for x in cc), len(kc), float(p[kc].sum()),
                       float(p @ best_late), float(p @ own_late)))
        nb = np.array(nb)
        lib_best = float(p @ Dl[:, sorted(set(tcls.tolist()))].min(axis=1))
        lib_comp = {tcomp[j] for j in range(n)}
        res[D] = dict(
            day=D, shops_known=k, unknown_shops=m, ordered_suffix_space=8 ** m, suffix_composition_space=len(comps),
            checkpoint_class_space=int(len(p)), late_checkpoints=J,
            library_wide=dict(suffix_compositions=len(lib_comp), suffix_composition_mass=float(sum(cprob[x] for x in lib_comp)),
                              checkpoint_classes=len(set(tcls.tolist())),
                              checkpoint_class_mass=float(p[sorted(set(tcls.tolist()))].sum()),
                              expected_best_late_distance=lib_best),
            greedy_clusters=dict(
                count=len(crow), clusters_size_ge2=len(big),
                mean_suffix_compositions=float(np.mean([r['suffix_compositions'] for r in crow])),
                size_weighted_mean_suffix_composition_mass=float(np.average([r['suffix_composition_mass'] for r in crow], weights=sizes)),
                size_weighted_mean_checkpoint_class_mass=float(np.average([r['checkpoint_class_mass'] for r in crow], weights=sizes)),
                size_weighted_mean_shops5_8_composition_mass=float(np.average([r['composition_mass_shops5_8'] for r in crow], weights=sizes)),
                clusters_ge2_median_distinct_shops5_8=float(np.median([r['distinct_ordered_shops5_8'] for r in big])) if big else None,
                clusters_ge2_all_shops5_8_distinct=int(sum(1 for r in big if r['distinct_ordered_shops5_8'] == r['size'])),
                max_suffix_composition_mass=float(max(r['suffix_composition_mass'] for r in crow)),
                top10=sorted(crow, key=lambda r: -r['size'])[:10]),
            neighbourhood_per_tape=dict(
                compatible_tapes_incl_self_median=float(np.median(nb[:, 0])),
                suffix_compositions_median=float(np.median(nb[:, 1])),
                suffix_composition_mass_mean=float(nb[:, 2].mean()), suffix_composition_mass_median=float(np.median(nb[:, 2])),
                checkpoint_classes_median=float(np.median(nb[:, 3])), checkpoint_class_mass_mean=float(nb[:, 4].mean()),
                expected_best_late_distance_mean=float(nb[:, 5].mean()),
                expected_own_tape_late_distance_mean=float(nb[:, 6].mean())),
            _clusters_all=crow)
    return res, cache


def full_distance_neighbourhoods(S, V, adjs, cache):
    """expected best FULL-hindsight router distance (all 5 checkpoints) for a farm on tape i's board whose world
    has tape i's revealed shops and uniformly random later shops: own tape / compatible tapes / whole library."""
    n = S.shape[0]
    out = {}
    for D in (12, 15, 18):
        k = D // 3
        M, p, of, J, Dl, tcls, tcomp, cprob = cache[D]
        Jpre = [j for j in CHECKPOINTS if j <= k]
        Vpre = V[:, Jpre, :]                                     # (n, Jp, 7)
        Dpre = np.zeros((n, n))
        for a in range(0, n, 128):
            Dpre[a:a + 128] = (np.abs(Vpre[a:a + 128, None] - Vpre[None]) * W).sum(axis=(2, 3))
        Vlate = V[:, J, :]                                       # (n, J, 7)
        P = V[:, k, :]
        groups = defaultdict(list)
        for i in range(n):
            groups[tuple(P[i].astype(int))].append(i)
        own, nbh, lib = np.zeros(n), np.zeros(n), np.zeros(n)
        for key, members in groups.items():
            Wv = np.array(key, float)[None, None, :] + M          # (U, J, 7) world late vectors
            E = np.zeros((M.shape[0], n))
            for a in range(0, n, 64):
                E[:, a:a + 64] = (np.abs(Wv[:, None] - Vlate[None, a:a + 64]) * W).sum(axis=(2, 3))
            for i in members:
                Mi = E + Dpre[i][None, :]
                own[i] = p @ Mi[:, i]
                nbh[i] = p @ Mi[:, adj_idx(adjs[D], i)].min(axis=1)
                lib[i] = p @ Mi.min(axis=1)
        out[D] = dict(own_tape=float(own.mean()), best_compatible=float(nbh.mean()), best_in_library=float(lib.mean()),
                      note='tape-to-tape analogue of docs/gap_ceilings.md columns (those are for real worlds)')
    return out


def adj_idx(adj, i):
    return np.nonzero(adj[i])[0]


# -------------------------------------------------------------------------------------- E: partial-tape experiment
def lazy_greedy(cur, p, Dl, K_max, cand=None):
    """choose late classes to add (for every farm) minimising mean_i sum_u p_u min(cur_i(u), Dl[u, s])."""
    F, U = cur.shape
    cand = np.arange(Dl.shape[1]) if cand is None else cand

    def gain(best, s):
        return float((np.maximum(0.0, best - Dl[None, :, s]) * p[None, :]).sum() / F)
    best = cur.copy()
    heap = [(-gain(best, s), int(s)) for s in cand]
    heapq.heapify(heap)
    chosen, curve = [], [float((best * p).sum() / F)]
    while heap and len(chosen) < K_max:
        g, s = heapq.heappop(heap)
        g_new = gain(best, s)
        if heap and g_new < -heap[0][0] - 1e-12:
            heapq.heappush(heap, (-g_new, s))
            continue
        chosen.append(s)
        best = np.minimum(best, Dl[None, :, s])
        curve.append(float((best * p).sum() / F))
    return chosen, curve


def partial_experiment(S, adjs, clus, cache, B_ep, day=12, R=10, seed=11):
    """K extra tapes with the board trajectory of the largest greedy day-D cluster's centre (so compatible with
    every farm in that centre's radius-8 ball) and designed or natural late shops."""
    M, p, of, J, Dl, tcls, tcomp, cprob = cache[day]
    k = day // 3
    adj = adjs[day]
    centers, assign = clus[day]
    c = centers[0]
    farms = np.nonzero(adj[c])[0]
    F, U = len(farms), len(p)
    cur = np.zeros((F, U))
    covered = []
    for a, i in enumerate(farms):
        C = np.nonzero(adj[i])[0]
        cur[a] = Dl[:, sorted(set(tcls[C].tolist()))].min(axis=1)
        covered.append({tcomp[j] for j in C})
    comps = list(cprob)
    cp = np.array([cprob[x] for x in comps])
    cov = np.array([[x in covered[a] for x in comps] for a in range(F)], bool)          # (F, ncomp)
    Ks = [0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, U]
    Ks = sorted({x for x in Ks if x <= U})
    Kmax = max(Ks)
    chosen, curve = lazy_greedy(cur, p, Dl, Kmax)
    designed = {K: curve[min(K, len(curve) - 1)] for K in Ks}
    # random natural late shops: the new tapes' suffix classes are drawn like real worlds (probability p)
    rng = np.random.default_rng(seed)
    rand = {K: [] for K in Ks}
    for r in range(R):
        draw = rng.choice(U, size=Kmax, p=p)
        best = cur.copy()
        prev = 0
        for K in Ks:
            for s in draw[prev:K]:
                best = np.minimum(best, Dl[None, :, s])
            prev = K
            rand[K].append(float((best * p).sum() / F))
    # composition mass: designed = add the uncovered compositions of largest mean uncovered mass first;
    # random = exact expectation sum_c p_c [covered or 1-(1-p_c)^K]
    base_mass = float((cov * cp).sum(axis=1).mean())
    unc_w = ((~cov) * cp).mean(axis=0)
    order = np.argsort(-unc_w)
    comp_designed, comp_random = {}, {}
    for K in Ks:
        add = np.zeros(len(comps), bool)
        add[order[:K]] = True
        comp_designed[K] = float(((cov | add[None, :]) * cp).sum(axis=1).mean())
        comp_random[K] = float((np.where(cov, cp, cp * (1 - (1 - cp) ** K))).sum(axis=1).mean())
    comp_Ks = sorted(set(Ks) | {len(comps)})
    for K in comp_Ks:
        if K not in comp_designed:
            add = np.zeros(len(comps), bool)
            add[order[:K]] = True
            comp_designed[K] = float(((cov | add[None, :]) * cp).sum(axis=1).mean())
            comp_random[K] = float((np.where(cov, cp, cp * (1 - (1 - cp) ** K))).sum(axis=1).mean())
    # the own-tape only and library-wide references for the same farms
    own = float(np.mean([p @ Dl[:, tcls[i]] for i in farms]))
    libbest = float(p @ Dl[:, sorted(set(tcls.tolist()))].min(axis=1))
    return dict(day=day, shops_known=k, center_ep=B_ep[c], farms_in_center_ball=int(F),
                existing_compatible_tapes_median=float(np.median(adj[farms].sum(axis=1))),
                late_class_space=int(U), suffix_composition_space=len(comps),
                expected_late_distance=dict(
                    own_tape_only=own, current_compatible=designed[0], library_wide_no_compat=libbest,
                    designed={int(K): v for K, v in designed.items()},
                    natural_random_mean={int(K): float(np.mean(v)) for K, v in rand.items()},
                    natural_random_sd={int(K): float(np.std(v)) for K, v in rand.items()}),
                suffix_composition_mass=dict(
                    current=base_mass, designed={int(K): v for K, v in sorted(comp_designed.items())},
                    natural_random_expected={int(K): v for K, v in sorted(comp_random.items())}),
                designed_K_reaching_zero=next((K for K, v in enumerate(curve) if v < 1e-9), None))


# ---------------------------------------------------------------------------------------- F: pruning & reweighting
def pruning(S, V, Hs, cache):
    """near-duplicate tapes for routing: same checkpoint demand vectors at every checkpoint AND boards within 8 at
    days 12, 15 and 18 (the router can never tell them apart by demand, and the boards are interchangeable)."""
    n = S.shape[0]
    key = [tuple(V[i, list(CHECKPOINTS)].astype(int).ravel()) for i in range(n)]
    same_vec = Counter(key)
    dup_vec = sum(v - 1 for v in same_vec.values() if v > 1)
    groups = defaultdict(list)
    for i, kk in enumerate(key):
        groups[kk].append(i)
    removable = 0
    for mem in groups.values():
        if len(mem) < 2:
            continue
        keep = []
        for i in mem:
            if any(all(Hs[D][i, j] <= MAX_H for D in (12, 15, 18)) for j in keep):
                removable += 1
            else:
                keep.append(i)
    # a looser criterion: same 4-shop prefix composition + same late composition + boards within 8 at 12/15/18
    key2 = [(comp_of(S[i, :4].tolist()), comp_of(S[i, 4:].tolist())) for i in range(n)]
    groups2 = defaultdict(list)
    for i, kk in enumerate(key2):
        groups2[kk].append(i)
    removable2 = 0
    for mem in groups2.values():
        keep = []
        for i in mem:
            if any(all(Hs[D][i, j] <= MAX_H for D in (12, 15, 18)) for j in keep):
                removable2 += 1
            else:
                keep.append(i)
    # under-covered late demand at day 12: expected best late distance among compatible tapes, split by the
    # world's late shops (how many Yarn Stores / strawberry shops among shops 5-8)
    M, p, of, J, Dl, tcls, tcomp, cprob = cache[12]
    yarn = SHOPS.index('YARN_STORE')
    straw = [SHOPS.index(s) for s in SHOPS if 'STRAWBERRY' in DEMAND[s]]
    by_y, by_s = defaultdict(lambda: [0.0, 0.0]), defaultdict(lambda: [0.0, 0.0])
    # class -> distribution of (#yarn, #straw); classes fix s5,s6 and {s7,s8}, so counts are class-determined
    ny = {}
    ns = {}
    for seq, u in of.items():
        ny[u] = sum(1 for s in seq if s == yarn)
        ns[u] = sum(1 for s in seq if s in straw)
    # library-wide best per class (no compatibility) and mean over tapes of best compatible per class
    libbest = Dl[:, sorted(set(tcls.tolist()))].min(axis=1)
    lib_ny = Counter(sum(1 for s in S[i, 4:] if s == yarn) for i in range(n))
    for u in range(len(p)):
        by_y[ny[u]][0] += p[u]
        by_y[ny[u]][1] += p[u] * libbest[u]
        by_s[ns[u]][0] += p[u]
        by_s[ns[u]][1] += p[u] * libbest[u]
    return dict(
        identical_checkpoint_demand_duplicates=int(dup_vec),
        removable_same_demand_and_boards_within8_d12_15_18=int(removable),
        removable_same_prefix_and_late_composition_boards_within8=int(removable2),
        late_yarn_stores_day12=[dict(yarn_in_shops_5_8=int(y), world_prob=v[0], library_tapes=int(lib_ny.get(y, 0)),
                                     library_share=lib_ny.get(y, 0) / n,
                                     expected_best_late_distance_library_wide=v[1] / v[0]) for y, v in sorted(by_y.items())],
        late_strawberry_shops_day12=[dict(strawberry_shops_in_5_8=int(s), world_prob=v[0],
                                          expected_best_late_distance_library_wide=v[1] / v[0]) for s, v in sorted(by_s.items())])


def compat_stratified(S, adjs, cache):
    """day 12: expected best late distance among COMPATIBLE tapes, by the world's late Yarn Stores / strawberry shops."""
    M, p, of, J, Dl, tcls, tcomp, cprob = cache[12]
    n = S.shape[0]
    yarn = SHOPS.index('YARN_STORE')
    straw = {SHOPS.index(s) for s in SHOPS if 'STRAWBERRY' in DEMAND[s]}
    ny, ns = {}, {}
    for seq, u in of.items():
        ny[u] = sum(1 for s in seq if s == yarn)
        ns[u] = sum(1 for s in seq if s in straw)
    acc = np.zeros(len(p))
    for i in range(n):
        C = np.nonzero(adjs[12][i])[0]
        acc += Dl[:, sorted(set(tcls[C].tolist()))].min(axis=1)
    acc /= n
    out = {'by_late_yarn': {}, 'by_late_strawberry_shops': {}}
    for name, f in (('by_late_yarn', ny), ('by_late_strawberry_shops', ns)):
        agg = defaultdict(lambda: [0.0, 0.0])
        for u in range(len(p)):
            agg[f[u]][0] += p[u]
            agg[f[u]][1] += p[u] * acc[u]
        out[name] = {int(x): dict(world_prob=v[0], expected_best_compatible_late_distance=v[1] / v[0]) for x, v in sorted(agg.items())}
    out['overall'] = float(p @ acc)
    return out


# ------------------------------------------------------------------------------------------------------------ main
def main():
    quick = '--quick' in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log('loading library from', AGENT)
    lib, meta = load_library()
    T = lib['tapes']
    S = np.array([[SHOPS.index(s) for s in t['shops']] for t in T], np.int8)
    V = np.array([cum_vecs(S[i].tolist()) for i in range(len(T))])
    eps = [t['ep'] for t in T]
    # A
    log('A: action redundancy')
    red, ids, lcp = action_redundancy(T, S)
    red['meta'] = meta
    (OUT / 'action_redundancy.json').write_text(json.dumps(red, indent=1), encoding='utf-8')
    # B
    enc, B, voc = encodings(lib, meta, quick=quick)
    enc['board_label_vocabulary'] = sorted(voc, key=voc.get)
    (OUT / 'encodings.json').write_text(json.dumps(enc, indent=1), encoding='utf-8')
    # C
    log('C: board clusters')
    bc, Hs, adjs, clus = board_clusters(B, S)
    for D in DAYS:
        bc[D]['greedy_centers_ep_top10'] = [eps[c] for c in clus[D][0][:10]]
    (OUT / 'board_clusters.json').write_text(json.dumps({str(k): v for k, v in bc.items()}, indent=1), encoding='utf-8')
    # D
    log('D: late-shop coverage')
    lc, cache = late_coverage(S, adjs, clus, V)
    for D in lc:
        for r in lc[D]['_clusters_all']:
            r['center_ep'] = eps[clus[D][0][r['cluster']]]
        lc[D]['greedy_clusters']['top10'] = sorted(lc[D]['_clusters_all'], key=lambda r: -r['size'])[:10]
    log('D: full-hindsight distances (tape-to-tape)')
    fd = full_distance_neighbourhoods(S, V, adjs, cache)
    strat = compat_stratified(S, adjs, cache)
    lc_out = {str(D): {k: v for k, v in lc[D].items() if k != '_clusters_all'} for D in lc}
    for D in lc:
        lc_out[str(D)]['full_hindsight_distance'] = fd[D]
    lc_out['day12_compatible_by_late_demand'] = strat
    (OUT / 'late_coverage.json').write_text(json.dumps(lc_out, indent=1), encoding='utf-8')
    (OUT / 'late_coverage_all_clusters.json').write_text(
        json.dumps({str(D): lc[D]['_clusters_all'] for D in lc}, indent=0), encoding='utf-8')
    # E
    log('E: partial-tape thought experiment')
    pe = {str(D): partial_experiment(S, adjs, clus, cache, eps, day=D) for D in (12, 15)}
    late_b = enc['late_segment_day12_on_lzma']['bytes_per_tape_avg']
    n12 = bc[12]['greedy_radius8_clusters']
    U12 = pe['12']['late_class_space']
    pe['storage'] = dict(
        late_segment_bytes_avg_lzma=late_b,
        one_cluster_all_late_classes_bytes=late_b * U12,
        all_day12_clusters_all_late_classes_bytes=late_b * U12 * n12,
        all_day12_clusters_all_suffix_compositions_bytes=late_b * pe['12']['suffix_composition_space'] * n12,
        limit_bytes=LIMIT_BYTES,
        note='average lzma bytes of a day-12..30 action segment + board deltas in this corpus; a synthetic segment '
             'library would need a generator (UMG\'s policy is not available; her new tapes do not replay).')
    (OUT / 'partial_tapes.json').write_text(json.dumps(pe, indent=1), encoding='utf-8')
    # F
    log('F: pruning')
    pr = pruning(S, V, Hs, cache)
    (OUT / 'pruning.json').write_text(json.dumps(pr, indent=1), encoding='utf-8')
    log('done in %.0f s' % (time.time() - t0))


if __name__ == '__main__':
    main()
