"""Render the markdown tables of the tape-library structure study from its JSON outputs.

Reads results/fresh/newphase_20260923/library_structure/*.json (written by library_structure_analysis.py and
library_resource_probe.py) and fills the {{TABLE:name}} placeholders of summary_template.md into summary.md, so
every number in the tables is copied from the JSON, never retyped. Without a template it writes tables.md only.

Usage: .venv/Scripts/python.exe scripts/library_structure_report.py
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/newphase_20260923/library_structure'


def J(name):
    p = OUT / f'{name}.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None


def f(x, nd=0):
    if x is None:
        return 'n/a'
    if isinstance(x, (int,)) or (isinstance(x, float) and nd == 0):
        return f'{x:,.0f}'
    return f'{x:,.{nd}f}'


def pct(x, nd=1):
    return 'n/a' if x is None else f'{100 * x:.{nd}f}%'


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join('---' for _ in head) + '|']
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out)


def t_probe(rp):
    rows = []
    for r in rp['rows']:
        rows.append([f(r['N']), f(r['file_bytes'] / 1e6, 2), f(r['json_bytes'] / 1e6, 1), f(r['load_s'], 2),
                     f(r['decode_json_s'], 2), f(r['rss_growth_mb']), f(r['router_call_ms']['mean'], 2),
                     f(r['router_call_ms']['max'], 2), f(r['router_call_ms']['per_game_total_ms']),
                     f(r['router_ignore_path_ms']['mean'], 2)])
    return table(['tapes N', 'file MB', 'decoded JSON MB', 'module load s (first act)', 'of which json.loads s',
                  'RSS growth MB', 'router call mean ms', 'router call max ms', 'router total per game ms',
                  'router call, overlay-ignore path, mean ms'], rows)


def t_capacity(rp, enc):
    fit = rp['linear_fit']
    cap = enc['capacity_estimate_100MiB']
    rows = [
        ['submission file (100 MiB), current JSON+zlib+b85 encoding', f(cap['current_encoding_b85_per_tape']) + ' B/tape',
         f(cap['tapes_current_encoding'])],
        ['submission file, token stream + lzma, b85 inside the .py', f(cap['better_encoding_b85_per_tape']) + ' B/tape',
         f(cap['tapes_better_encoding_b85_in_py'])],
        ['submission file, token stream + lzma, binary side file', f(cap['better_encoding_binary_per_tape']) + ' B/tape',
         f(cap['tapes_better_encoding_binary'])],
    ]
    for key, c in rp['capacity'].items():
        s = key.replace('slowdown_x', '')
        rows.append([f'router call under 0.5 s (local speed x{s})', f(fit['router_max_ms']['per_tape'] * 1000 * float(s), 1) + ' us/tape (max call)',
                     f(c['router_call_under_0_5s'])])
        rows.append([f'module load under 30 s of the 60 s overage bank (x{s})', f(fit['load_s']['per_tape'] * 1000 * float(s), 2) + ' ms/tape',
                     f(c['load_under_30s_of_overage'])])
    rows.append(['resident memory under 4 GiB (of 6.5 GiB), current in-memory layout',
                 f(fit['rss_growth_mb']['per_tape'] * 1024, 0) + ' KB/tape', f(rp['capacity']['slowdown_x1']['memory_under_4GiB'])])
    return table(['constraint', 'measured marginal cost', 'max tapes (linear extrapolation)'], rows)


def t_prefix(ar):
    rows = []
    for r in ar['prefix_by_day']:
        if r['day'] in (1, 3, 4, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 30):
            rows.append([r['day'], r['steps'], r['shops_visible_on_last_day'], r['distinct_ordered_shop_prefixes'],
                         r['distinct_prefixes'], r['largest_group'], r['tapes_sharing_prefix']])
    return table(['through day', 'steps', 'shops visible on its last day', 'distinct ordered shop prefixes',
                  'distinct action prefixes', 'largest identical group', 'tapes sharing their prefix with another'], rows)


def t_diverge(ar):
    rows = []
    for r in ar['divergence_vs_first_shop_difference']:
        p = r['first_differing_shop']
        rows.append([p, f(r['pairs']), '-' if p == 'none' else f'day {3 * p}', pct(r['diverge_before_shop_visible']),
                     pct(r['diverge_on_reveal_day']), f(r['median_divergence_day'], 1), f(r['max_divergence_day'], 1)])
    t1 = table(['first differing shop', 'tape pairs', 'visible from', 'actions already differ before it is visible',
                'first action difference on the reveal day', 'median divergence day', 'latest divergence day'], rows)
    rows = []
    for r in ar['pairs_with_same_first_k_shops']:
        rows.append([r['k'], f(r['pairs']), pct(r['identical_until_this_reveal']), pct(r['identical_until_next_reveal']),
                     f(r['median_divergence_day'], 1)])
    t2 = table(['same first k shops', 'pairs', 'actions identical until shop k is revealed (day 3k)',
                'identical until shop k+1 is revealed', 'median divergence day'], rows)
    return t1 + '\n\n' + t2


def t_enc(enc):
    fl = enc['full_library']
    sh = enc['shipped']
    rows = [
        ['shipped: JSON (dedup action dicts) + zlib 9, base85 in the .py', f(sh['blob_json_bytes']), f(sh['blob_zlib_bytes']), f(sh['blob_b85_chars'])],
    ]
    if 'current_json_lzma' in fl:
        rows.append(['same JSON + lzma 9', f(fl['current_json_lzma']['raw_json']), f(fl['current_json_lzma']['bytes']), f(fl['current_json_lzma']['b85_chars'])])
    rows.append(['factorised token stream (unit/market vocab) + label boards, zlib 9', f(fl['token_stream_boards_zlib9']['raw']),
                 f(fl['token_stream_boards_zlib9']['bytes']), f(fl['token_stream_boards_zlib9']['bytes'] * 1.25)])
    rows.append(['same, lzma 9', f(fl['token_stream_boards_lzma']['raw']), f(fl['token_stream_boards_lzma']['bytes']), f(fl['token_stream_boards_lzma']['b85_chars'])])
    rows.append(['same with day-delta boards, lzma 9', f(fl['token_stream_board_deltas_lzma']['raw']), f(fl['token_stream_board_deltas_lzma']['bytes']),
                 f(fl['token_stream_board_deltas_lzma']['b85_chars'])])
    tr = fl['day_trie_boardtable_lzma']
    rows.append([f"explicit day-trie ({tr['trie_nodes']:,} nodes) + unique-board table ({tr['unique_boards']:,} of {tr['board_slots']:,}), lzma 9",
                 f(tr['raw']), f(tr['bytes']), f(tr['b85_chars'])])
    t1 = table(['encoding of the same 584 tapes', 'raw bytes', 'compressed bytes', 'in a .py (base85 chars)'], rows)
    parts = enc['shipped_json_parts']
    rows = [[k, f(v['raw']), f(v['zlib9'])] for k, v in parts.items()]
    t2 = table(['shipped JSON part', 'raw bytes', 'zlib 9 alone'], rows)
    pl = fl['parts_lzma']
    rows = [[k, f(v)] for k, v in pl.items()]
    t3 = table(['token encoding part', 'lzma bytes alone'], rows)
    rows = [[r['N'], r['draw'], f(r['unique_actions']), f(r['current_json_zlib9']), f(r['token_board_deltas_lzma'])] for r in enc['subsets']]
    fit = enc['marginal_fit_N146_584']
    rows.append(['fit N>=146', 'slope', f(fit['unique_actions']['per_tape'], 1) + '/tape', f(fit['current_json_zlib9']['per_tape']) + ' B/tape',
                 f(fit['token_board_deltas_lzma']['per_tape']) + ' B/tape'])
    t4 = table(['subset N', 'draw', 'unique action dicts', 'shipped encoding bytes (zlib)', 'token+delta lzma bytes'], rows)
    return t1 + '\n\n' + t2 + '\n\n' + t3 + '\n\n' + t4


def t_boards(bc):
    rows = []
    for d, r in bc.items():
        c = r['compatible_other_tapes']
        rows.append([d, r['shops_known'], f(r['distinct_boards']), f(c['median']), f(c['p10']), f(c['p90']), f(r['compatible_other_tapes']['isolated']),
                     f(r['single_linkage_components']), f(r['largest_component']), f(r['greedy_radius8_clusters']), f(r['largest_greedy_cluster']),
                     f(r['greedy_clusters_for_50pct']), f(r['greedy_clusters_for_90pct']), f(r['median_pairwise_hamming'])])
    return table(['day', 'shops known', 'distinct boards (router labels)', 'other tapes within 8: median', 'p10', 'p90',
                  'tapes with none', 'single-linkage components', 'largest component', 'greedy radius-8 clusters',
                  'largest cluster', 'clusters holding 50% of tapes', 'clusters holding 90%', 'median pairwise Hamming'], rows)


def t_late(lc):
    rows = []
    for d in ('12', '15', '18'):
        r = lc[d]
        lw, nb, fd = r['library_wide'], r['neighbourhood_per_tape'], r['full_hindsight_distance']
        rows.append([d, r['shops_known'], f"{r['suffix_composition_space']} / {r['checkpoint_class_space']} / {r['ordered_suffix_space']}",
                     f"{lw['suffix_compositions']} ({pct(lw['suffix_composition_mass'])})",
                     f"{lw['checkpoint_classes']} ({pct(lw['checkpoint_class_mass'])})",
                     f(nb['compatible_tapes_incl_self_median']),
                     f"{f(nb['suffix_compositions_median'])} ({pct(nb['suffix_composition_mass_mean'])} mean mass)",
                     f"{f(nb['checkpoint_classes_median'])} ({pct(nb['checkpoint_class_mass_mean'])})",
                     f(nb['expected_own_tape_late_distance_mean'], 2), f(nb['expected_best_late_distance_mean'], 2),
                     f(lw['expected_best_late_distance'], 2),
                     f"{f(fd['own_tape'], 1)} / {f(fd['best_compatible'], 1)} / {f(fd['best_in_library'], 1)}"])
    return table(['day', 'shops known', 'late space: compositions / checkpoint classes / ordered', 'library carries: compositions (prob. mass)',
                  'library: checkpoint classes (mass)', 'compatible tapes incl. own (median)', 'compatible: compositions (median)',
                  'compatible: checkpoint classes (median, mean mass)', 'E[late distance] own tape', 'E[late distance] best compatible',
                  'E[late distance] best in library', 'full-hindsight distance own / compatible / library'], rows)


def t_clusters(lc_all, day, n=12):
    rows = []
    for r in sorted(lc_all[day], key=lambda r: -r['size'])[:n]:
        rows.append([r['cluster'], r['center_ep'], r['size'], r['distinct_prefix_compositions'],
                     f"{r['distinct_ordered_shops5_8']} / {r['distinct_compositions_shops5_8']} ({pct(r['composition_mass_shops5_8'])})",
                     f"{r['suffix_compositions']}/{r['suffix_compositions_total']} ({pct(r['suffix_composition_mass'])})",
                     f"{r['checkpoint_classes']}/{r['checkpoint_classes_total']} ({pct(r['checkpoint_class_mass'])})",
                     f(r['members_with_same_prefix_composition_mean'], 2)])
    return table(['cluster', 'centre episode', 'tapes', 'distinct prefix compositions',
                  'shops 5-8: ordered / compositions (mass of 330)', 'unknown late shops: compositions covered (mass)',
                  'checkpoint classes covered (mass)', 'members sharing a member\'s prefix composition (mean)'], rows)


def t_cluster_summary(lc):
    rows = []
    for d in ('12', '15', '18'):
        g = lc[d]['greedy_clusters']
        rows.append([d, g['count'], g['clusters_size_ge2'], f(g['mean_suffix_compositions'], 2),
                     pct(g['size_weighted_mean_suffix_composition_mass']), pct(g['size_weighted_mean_checkpoint_class_mass']),
                     pct(g.get('size_weighted_mean_shops5_8_composition_mass')), f(g.get('clusters_ge2_median_distinct_shops5_8'), 1),
                     g.get('clusters_ge2_all_shops5_8_distinct'), pct(g['max_suffix_composition_mass'])])
    return table(['day', 'greedy clusters', 'with >=2 tapes', 'mean late compositions per cluster',
                  'late composition mass covered (tape-weighted mean)', 'checkpoint-class mass (tape-weighted)',
                  'shops 5-8 composition mass (tape-weighted)', 'multi-tape clusters: median distinct shops 5-8',
                  'multi-tape clusters where every tape has its own shops 5-8', 'best cluster: late composition mass'], rows)


def t_partial(pt):
    out = []
    for d in ('12', '15'):
        r = pt[d]
        e, m = r['expected_late_distance'], r['suffix_composition_mass']
        Ks = sorted(int(k) for k in e['designed'])
        rows = []
        for K in Ks:
            k = str(K)
            rows.append([K, f(e['designed'][k], 2), f"{f(e['natural_random_mean'][k], 2)} +/- {f(e['natural_random_sd'][k], 2)}",
                         pct(m['designed'].get(k)) if k in m['designed'] else 'n/a',
                         pct(m['natural_random_expected'].get(k)) if k in m['natural_random_expected'] else 'n/a'])
        head = (f"Day {d}: largest greedy cluster centre ep {r['center_ep']}; {r['farms_in_center_ball']} tapes' farms within 8 of it "
                f"(median {f(r['existing_compatible_tapes_median'])} compatible tapes each). Late space {r['late_class_space']} checkpoint classes, "
                f"{r['suffix_composition_space']} compositions. Own tape only: E[late distance] {f(e['own_tape_only'], 2)}; library-wide "
                f"(ignoring boards) {f(e['library_wide_no_compat'], 2)}; designed additions reach 0 at K = {r['designed_K_reaching_zero']}.")
        out.append(head + '\n\n' + table(['K extra tapes on the cluster board', 'E[late distance] designed late shops',
                                           'E[late distance] natural (random) late shops, mean +/- sd over 10 draws',
                                           'late composition mass, designed', 'late composition mass, natural (exact expectation)'], rows))
    s = pt['storage']
    out.append(table(['storage quantity', 'bytes'], [
        ['average lzma bytes of one day-12..30 segment (actions + board deltas) in this corpus', f(s['late_segment_bytes_avg_lzma'])],
        ['one day-12 cluster x all late checkpoint classes', f(s['one_cluster_all_late_classes_bytes'])],
        ['all day-12 greedy clusters x all late checkpoint classes', f(s['all_day12_clusters_all_late_classes_bytes'])],
        ['all day-12 greedy clusters x all late compositions', f(s['all_day12_clusters_all_suffix_compositions_bytes'])],
        ['submission limit', f(s['limit_bytes'])]]))
    return '\n\n'.join(out)


def t_pruning(pr, lc):
    rows = [['tapes with identical demand vectors at all 5 checkpoints as another tape', pr['identical_checkpoint_demand_duplicates']],
            ['... that also have boards within 8 of it on days 12, 15 and 18 (removable without losing any routing option)',
             pr['removable_same_demand_and_boards_within8_d12_15_18']],
            ['same prefix composition + same late composition + boards within 8 on days 12/15/18',
             pr['removable_same_prefix_and_late_composition_boards_within8']]]
    t1 = table(['near-duplicate criterion', 'tapes'], rows)
    comp = lc['day12_compatible_by_late_demand']
    rows = []
    for r in pr['late_yarn_stores_day12']:
        y = str(r['yarn_in_shops_5_8'])
        rows.append([r['yarn_in_shops_5_8'], pct(r['world_prob']), f"{r['library_tapes']} ({pct(r['library_share'])})",
                     f(comp['by_late_yarn'][y]['expected_best_compatible_late_distance'], 2),
                     f(r['expected_best_late_distance_library_wide'], 2)])
    t2 = table(['Yarn Stores among shops 5-8', 'world probability', 'library tapes (share)', 'E[best compatible late distance], day 12',
                'E[best late distance], whole library'], rows)
    rows = []
    for r in pr['late_strawberry_shops_day12']:
        s = str(r['strawberry_shops_in_5_8'])
        rows.append([r['strawberry_shops_in_5_8'], pct(r['world_prob']),
                     f(comp['by_late_strawberry_shops'][s]['expected_best_compatible_late_distance'], 2),
                     f(r['expected_best_late_distance_library_wide'], 2)])
    t3 = table(['strawberry-demanding shops among shops 5-8', 'world probability', 'E[best compatible late distance], day 12',
                'E[best late distance], whole library'], rows)
    return t1 + '\n\n' + t2 + '\n\n' + t3


def main():
    ar, enc, bc, lc, pt, pr, rp = (J(x) for x in ('action_redundancy', 'encodings', 'board_clusters', 'late_coverage',
                                                   'partial_tapes', 'pruning', 'resource_probe'))
    lc_all = J('late_coverage_all_clusters')
    tables = {
        'probe': t_probe(rp) if rp else '(resource probe not run)',
        'capacity': t_capacity(rp, enc) if rp else '(resource probe not run)',
        'prefix': t_prefix(ar), 'diverge': t_diverge(ar), 'encodings': t_enc(enc), 'boards': t_boards(bc),
        'late': t_late(lc), 'cluster_summary': t_cluster_summary(lc), 'clusters12': t_clusters(lc_all, '12'),
        'clusters15': t_clusters(lc_all, '15'), 'partial': t_partial(pt), 'pruning': t_pruning(pr, lc),
    }
    tpl = OUT / 'summary_template.md'
    (OUT / 'tables.md').write_text('\n\n'.join(f'## {k}\n\n{v}' for k, v in tables.items()) + '\n', encoding='utf-8')
    if tpl.exists():
        text = tpl.read_text(encoding='utf-8')
        text = re.sub(r'\{\{TABLE:(\w+)\}\}', lambda m: tables[m.group(1)], text)
        (OUT / 'summary.md').write_text(text, encoding='utf-8')
        print('wrote summary.md')
    print('wrote tables.md')


if __name__ == '__main__':
    main()
