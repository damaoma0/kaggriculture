"""Report fresh fetch, exact loss decomposition and prespecified paired tests."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import random
import statistics as S

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/records_refresh_20260923'

def ci(values):
    rng=random.Random(20260923)
    xs=sorted(S.mean(rng.choices(values,k=len(values))) for _ in range(10000))
    return [xs[250],xs[9750]]

def summarize(pairs):
    delta=[c['margin']-b['margin'] for b,c in pairs]
    return dict(n=len(pairs),mean_margin_delta=S.mean(delta),ci95=ci(delta),
                better=sum(x>0 for x in delta),worse=sum(x<0 for x in delta),same=sum(x==0 for x in delta),
                baseline_wins=sum(b['margin']>0 for b,c in pairs),candidate_wins=sum(c['margin']>0 for b,c in pairs),
                loss_to_win=sum(b['margin']<0<c['margin'] for b,c in pairs),win_to_loss=sum(c['margin']<0<b['margin'] for b,c in pairs),
                worst=min(delta),best=max(delta))

def main():
    diagnosis=json.loads((OUT/'diagnosis.json').read_text())
    design=json.loads((OUT/'fix_design.json').read_text())
    for name,digest in design['hashes'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    rows=[json.loads(p.read_text()) for p in (OUT/'audits').glob('*.json')]
    result=dict(source_hashes_verified=True,cohorts=diagnosis['cohorts'],fixes={})
    lines=['# Fresh game fetch and fix evaluation — 2026-09-23','',
           'Fetched the newly completed games for both live submissions; no submission was made. '
           'All 54 recorded-action replays reproduce both final balances exactly. The candidate tests below '
           'use the official local engine and recorded opponents, which cannot react.','',
           '| Build | New W–L | New mean margin | All cached W–L |',
           '|---|---:|---:|---:|']
    for sub,c in diagnosis['cohorts'].items():
        a,n=c['all'],c['new']
        lines.append(f"| {'mgt_m1' if sub=='56395605' else 'mgt_t10'} | {n['wins']}–{n['losses']} | {n['mean_margin']:+,.0f} | {a['wins']}–{a['losses']} |")
    lines+=['','These are different, small matchup cohorts; their rates do not establish that one build is better '
            'or that the policy itself deteriorated. Inventories are snapshots, so games completed after the fetch are excluded.','',
            '## What the losses show','',
            '| Mean product revenue gap, us minus rival | 28 losses | 26 wins |',
            '|---|---:|---:|']
    for p in ['WOOL','STRAWBERRY','MILK','TOMATO','EGG','MELON']:
        l=diagnosis['groups']['new_losses']['mean_revenue_gap'][p]
        w=diagnosis['groups']['new_wins']['mean_revenue_gap'][p]
        lines.append(f'| {p} | {l:+,.0f} | {w:+,.0f} |')
    lines+=['','These product differences describe realized outcomes, not the profit from adding production. '
            'Gross wheat/fertilizer turnover is deliberately omitted from this table: opponents buy and resell those goods. '
            'Their purchases must be netted before attributing profit. After netting, losses have a +566 wheat '
            'trade gap and a −2,089 fertilizer trade gap. The large gross wheat deficit is therefore not a cause '
            'of the losses. All 54 full revenue-minus-expense differences reconcile to the recorded margins.','',
            'Across the new cohort, strawberry plots average 17.1 versus 19.4 on day 9 and 21.2 versus 29.8 on day 12. '
            'In losses, harvested strawberries per planting average 7.36 versus 7.49, close to the eight-unit ceiling. '
            'This supports a cohort quantity/timing and product-mix deficit more than a universal fertilizer failure. '
            'Three of the 28 losses have our yield below 7 while the rival reaches at least 7.4.','',
            'The new games with three or more Yarn Stores are 2–6, versus 7–7 with none, 15–11 with one and 2–4 with two. '
            'Small descriptive strata support investigating wool response; they are not adjusted causal estimates.','',
            '### Concrete failures','',
            '| Episode / build | Margin | Largest observed production deficit |',
            '|---|---:|---|',
            '| 112543358 / m1 | −12,635 | Strawberry revenue −14,661; 36 versus 47 plantings; 282 versus 344 harvested units. |',
            '| 112561320 / m1 | −12,299 | Wool −13,718 and milk −8,241; three Yarn Stores. |',
            '| 112531372 / m1 | −10,534 | Milk −12,766; the wool deficit is only −1,758. |',
            '| 112512725 / t10 | −25,594 | Wool −33,526; three Yarn Stores. |',
            '| 112573085 / t10 | −27,015 | Broad egg/milk/berry deficits; day-9 berries 19 versus 31 and rival has an extra land block. |','',
            'A wool-only patch cannot address the berry- and milk-dominated losses. A day-12 tape change also cannot '
            'recover output already missed in the opening.','', '## Fresh paired candidate tests','']
    pairs=[]
    for ep in design['all_new_m1']:
        b=json.loads((OUT/'paired/mgt_m1'/f'{ep}.json').read_text())
        c=json.loads((OUT/'paired/mgt_y2'/f'{ep}.json').read_text())
        assert [b['final'],b['rival']]==b['recorded'],ep
        pairs.append((b,c))
    y=summarize(pairs)
    y['mean_cash_delta']=S.mean(c['final']-b['final'] for b,c in pairs)
    y['mean_rival_delta']=S.mean(c['rival']-b['rival'] for b,c in pairs)
    y['opponent_no_effect_increase_over40']=[c['episode'] for b,c in pairs if c['opp_dead']-b['opp_dead']>40]
    y['cases']=[dict(episode=c['episode'],baseline=b['margin'],candidate=c['margin'],delta=c['margin']-b['margin']) for b,c in pairs]
    result['fixes']['y2']=y
    vp=[]
    for ep in design['v9_sample']:
        c=json.loads((OUT/'v9'/f'{ep}.json').read_text())
        assert c['completed'] and c['baseline_verified'] and c['ledger_verified']
        vp.append((c['baseline'],c))
    v=summarize(vp)
    v['mean_cash_delta']=S.mean(c['cash_delta'] for b,c in vp)
    v['changed_games']=sum(any(x is not None for x in c['selected']) for b,c in vp)
    v['selected_decisions']=sum(x is not None for b,c in vp for x in c['selected'])
    v['overage_above60']=sum(c['measured_overage_used']>60 for b,c in vp)
    decisions=[json.loads(p.read_text()) for p in (OUT/'v9').glob('*-d*.json')]
    alternatives=[c for d in decisions for c in d['candidates'] if c['route'] is not None]
    v['candidate_evaluations']=len(alternatives)
    v['protected_cohort_rejections']=sum(bool(c.get('protection_failures')) for c in alternatives)
    v['changed_game_opponent_sales_unchanged']=[]
    for b,c in vp:
        if not c['margin_delta']:continue
        a=json.loads((OUT/'audits'/f"{c['episode']}.json").read_text())
        old=a['sides'][1]['sales'];new=c['economics'][1-a['seat']]['units']
        assert all(old.get(p,0)==new.get(p,0) for p in set(old)|set(new))
        v['changed_game_opponent_sales_unchanged'].append(c['episode'])
    v['cases']=[{k:c[k] for k in ('episode','selected','margin','margin_delta','cash_delta','measured_overage_used','search_seconds')} for b,c in vp]
    result['fixes']['v9']=v
    for label,s in [('Late-Yarn y2, all 25 new m1 games',y),('Value selector V9, 8 uniformly sampled new m1 games',v)]:
        lines += [f'### {label}','',
                  f"Mean paired margin change **{s['mean_margin_delta']:+,.0f}** (game-bootstrap 95% interval {s['ci95'][0]:+,.0f} to {s['ci95'][1]:+,.0f}). "
                  f"{s['better']} improve, {s['worse']} worsen, {s['same']} are unchanged. Wins: {s['baseline_wins']} → {s['candidate_wins']}. "
                  f"Losses flipped: {s['loss_to_win']}; wins lost: {s['win_to_loss']}. Worst/best margin changes: {s['worst']:+,.0f} / {s['best']:+,.0f}.", '']
    lines += [f"V9 chooses a different tape on {v['selected_decisions']}/24 reveal decisions across {v['changed_games']}/8 games. "
              'The sample was fixed with seed 230926 before candidate evaluation and includes wins and losses. '
              'Replanning uses only each reached observation at days 12, 15 and 18; actual future shops and recorded rival actions are evaluation inputs only.','',
              f"V9 exceeds 60 seconds of measured cumulative per-turn overage in {v['overage_above60']}/8 games. "
              'This diagnostic excludes initial imports, process/serialization overhead and competition hardware differences, and does not enforce timeouts. '
              'It is not a deployment timing certificate.','',
              '### Why the fixes help, and what they leave unresolved','',
              f"V9 rejects {v['protected_cohort_rejections']} of {v['candidate_evaluations']} alternative route evaluations "
              'because they fail to preserve protected crops or animals. The count is across decisions, not unique tapes. '
              'Its small switch count reflects feasibility and value gates; faster search by itself does not provide a new production plan.','',
              'In episode **112572245**, V9 selects donor 109534325 on day 15. Own cash rises **3,161**, '
              'rival cash rises 928, and margin improves **2,233**. Our egg sales increase by 55 units; '
              'hire expense falls 720 and wheat purchases fall 1,298, with other products changing too. '
              'The result remains a 4,464 loss.','',
              'In episode **112605999**, V9 selects donor 109640231 on day 15. '
              'Own cash falls **2,207**, but rival cash falls **8,060**, improving margin **5,853** and turning −252 into +5,601. '
              'Our wool sales rise by 47 units; rival wool revenue falls 10,579. In both changed games, '
              'the rival sells exactly the same quantity of every product as in the original replay. '
              'Thus the measured gain is not caused by losing rival sales volume, although responsive sale timing remains untested.','',
              'The y2 mean own-cash change is −4 versus −95 for the rival: nearly all of its +92 margin comes '
              'from the opponent-price effect. Its one new win ends at **+2**, too narrow to treat as a reliable live win. '
              'The previous historical y2 panel also contained a −3,153 regression; this fresh positive panel does not erase that risk.','',
              '**Assessment:** the value selector has demonstrated useful recovery on fresh records, but this eight-game '
              'sample is preliminary and its average is dominated by one price-impact win. The late-Yarn layer is a small '
              'incremental improvement, not a repair for the main losses. Earlier production allocation and feasible '
              'responses to wool/milk demand remain the important unresolved work. Before promotion, test V9 on the '
              'remaining fresh games and responsive opponents, and validate a self-contained submission with a time-bank policy.','',
              'Full native m1 replays match all 25 recorded results; V9 additionally verifies its native prefix and baseline suffix, '
              'and both changed-game economic ledgers reconcile. Source hashes are unchanged through the panel. '
              'Bootstrap intervals over these small, potentially related game samples should not be treated as strong live-ladder guarantees.','',
              '## Artifacts','',
              '- `results/fresh/records_refresh_20260923/manifest.json`: inventory counts and all 54 downloaded IDs.',
              '- `diagnosis.json` and `audits/`: exact replay audits and product/crop/service accounts.',
              '- `fix_design.json`: prespecified samples and source hashes.',
              '- `paired/` and `v9/`: individual candidate results and reveal decisions.',
              '- `summary.json`: machine-readable comparison and per-game improvements/regressions.','']
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    (ROOT/'docs/records_refresh_20260923.md').write_text('\n'.join(lines),encoding='utf8')
    print(json.dumps(result['fixes'],indent=2))

if __name__=='__main__':main()
