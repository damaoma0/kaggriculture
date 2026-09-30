"""Render the frozen prefix study; no fitting or model selection occurs here."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/shop_prefix_predictability'


def main():
    data = json.loads((OUT / 'ordered_metrics.json').read_text())
    coverage = json.loads((OUT / 'coverage.json').read_text())
    corpora = [('UMG56266758_native', 'UMG · 105 games', '#2465AC'),
               ('own_m1_56395605', 'Our m1 · 86 games', '#DA7734')]
    x = np.arange(1, 9)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold', 'axes.labelcolor': '#344454',
                         'text.color': '#203246', 'axes.edgecolor': '#ACB6C0',
                         'savefig.facecolor': '#FFFFFF'})
    fig, (ax, cov) = plt.subplots(2, 1, figsize=(11, 11.5),
                                  gridspec_kw={'height_ratios': [1.25, 1]})
    fig.subplots_adjust(top=.83, bottom=.20, left=.10, right=.96, hspace=.48)
    fig.suptitle('How much can the first shops tell us?', x=.10, y=.968,
                 ha='left', fontsize=23, weight='bold')
    fig.text(.10, .925, 'Fixed target: total physical production over the full 30-day season.', fontsize=12)
    fig.text(.10, .898, 'Each point uses only shops revealed so far; all predictions are out of sample.', fontsize=11)
    ax.set_title('A. Predictable variation in final production', loc='left', pad=15)
    for name, label, color in corpora:
        rows = [m for m in data['metrics'] if m['corpus'] == name]
        y = np.array([r['overall_variance_weighted_skill'] for r in rows]) * 100
        ci = np.array([r['bootstrap_95_ci']['overall_variance_weighted_skill_95_ci'] for r in rows]) * 100
        ax.fill_between(x, ci[:, 0], ci[:, 1], alpha=.12, color=color, linewidth=0)
        ax.plot(x, y, 'o-', color=color, linewidth=2.5, markersize=6, label=label)
        for index in [0, 3, 5, 7]:
            ax.annotate(f'{y[index]:.0f}%', (x[index], y[index]), xytext=(0, 11 if name.startswith('UMG') else -19),
                        textcoords='offset points', ha='center', color=color, fontsize=11, weight='bold')
    ax.set_ylim(0, 103)
    ax.set_yticks(range(0, 101, 20), [f'{i}%' for i in range(0, 101, 20)])
    ax.set_xticks(x, [f'{i}\nDay {3*i}' for i in x])
    ax.set_ylabel('Held-out prediction skill')
    ax.grid(axis='y', color='#E3E8ED')
    ax.set_axisbelow(True)
    ax.axvline(4, ls=':', color='#9CA9B5', lw=1, zorder=0)
    ax.legend(loc='upper left', ncol=2, frameon=False, fontsize=10)
    cov.set_title('B. UMG tape coverage of our 86 historical worlds', loc='left', pad=15)
    for key, label, color, style in [
        ('ordered_by_x', 'Exact shop order', '#9A4C88', 'o-'),
        ('unordered_by_x', 'Same shop counts, any order', '#289489', 's--')]:
        y = [coverage['observed_rates'][key][str(i)] * 100 for i in x]
        cov.plot(x, y, style, color=color, linewidth=2.4, markersize=6, label=label)
        for index in [3, 5, 7]:
            cov.annotate(f'{y[index]:.0f}%', (x[index], y[index]), xytext=(0, 10),
                         textcoords='offset points', ha='center', color=color, weight='bold')
    cov.set_ylim(-5, 115)
    cov.set_yticks(range(0, 101, 20), [f'{i}%' for i in range(0, 101, 20)])
    cov.set_xticks(x, [f'{i}\nDay {3*i}' for i in x])
    cov.set_ylabel('Worlds with a matching prefix')
    cov.set_xlabel('Number of revealed shops', labelpad=8)
    cov.grid(axis='y', color='#E3E8ED')
    cov.set_axisbelow(True)
    cov.axvline(4, ls=':', color='#9CA9B5', lw=1, zorder=0)
    cov.legend(loc='upper right', frameon=False, fontsize=10)
    fig.text(.10, .035,
             'A: Reduction in squared prediction error vs a training-mean baseline, weighted by product variance.\n'
             'Shading: 95% episode bootstrap, conditional on the fixed grouped CV split. Later declines can reflect\n'
             'limited data and model estimation. B: Prefix presence in 584 UMG tapes; executable state matching is stricter.',
             fontsize=9, color='#586A7A', linespacing=1.5)
    fig.savefig(OUT / 'shop_prefix_predictability.png', dpi=180)
    fig.savefig(OUT / 'shop_prefix_predictability.svg')
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(14, 7), sharey=True)
    fig.subplots_adjust(left=.11, right=.90, top=.80, bottom=.24, wspace=.10)
    fig.suptitle('Which products are predictable from the first shops?', x=.11, y=.955,
                 ha='left', fontsize=21, weight='bold')
    fig.text(.11, .901, 'Held-out prediction skill (%) for whole-season production; the same fixed method for each product.', fontsize=11)
    for ax, (name, label, _) in zip(axes, corpora):
        rows = [m for m in data['metrics'] if m['corpus'] == name]
        values = np.array([[r['products'][p]['skill'] for r in rows] for p in data['products']]) * 100
        im = ax.imshow(values, cmap='RdBu', norm=TwoSlopeNorm(vmin=-100, vcenter=0, vmax=100), aspect='auto')
        ax.set_title(label, pad=13)
        ax.set_xticks(range(8), range(1, 9))
        ax.set_yticks(range(9), [p.title() for p in data['products']])
        ax.set_xlabel('Number of revealed shops')
        for i in range(9):
            for j in range(8):
                ax.text(j, i, f'{values[i,j]:.0f}', va='center', ha='center', fontsize=10,
                        color='white' if abs(values[i,j]) > 62 else '#223344')
    cb_ax = fig.add_axes([.925, .27, .014, .50])
    fig.colorbar(im, cax=cb_ax, ticks=[-100, -50, 0, 50, 100])
    fig.text(.11, .065,
             '0%: no gain over the training-mean baseline. Negative: worse held-out prediction.\n'
             'Prediction skill describes association, not the share of output units caused by shops or imitation accuracy.',
             color='#586A7A', fontsize=10, linespacing=1.5)
    fig.savefig(OUT / 'shop_prefix_products.png', dpi=180)
    plt.close(fig)
    summary = []
    for m in data['metrics']:
        total = sum(p['baseline_sse'] for p in m['products'].values())
        summary.append({k: m[k] for k in ['corpus', 'prefix_shops', 'n_episodes',
                       'first4_unordered_groups', 'overall_variance_weighted_skill', 'macro_product_skill']} |
                       {'ci95': m['bootstrap_95_ci']['overall_variance_weighted_skill_95_ci'],
                        'product_weights': {p: a['baseline_sse'] / total for p, a in m['products'].items()}})
    (OUT / 'chart_summary.json').write_text(json.dumps(summary, indent=2))
    print('Created shop_prefix_predictability.png, .svg, shop_prefix_products.png, chart_summary.json')


if __name__ == '__main__':
    main()
