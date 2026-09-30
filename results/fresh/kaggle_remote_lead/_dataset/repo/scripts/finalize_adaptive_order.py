"""Apply the recorded confirmation gates and preserve the tested candidate."""
from hashlib import sha256
import json
from research_adaptive_order import OUT,ROOT,BASE
from report_opponent_sales import compare


def main():
    total=0
    for phase in ('discovery','shops','discovery_available','shops_available','confirmation'):
        manifest=json.loads((OUT/(phase+'_manifest.json')).read_text())
        rows=json.loads((OUT/(phase+'_results.json')).read_text())
        expected={(s,i,o,m) for s in manifest['seeds'] for i in (0,1) for o in manifest['opponents'] for m in manifest['modes']}
        assert len(rows)==len(expected) and {(r['seed'],r['seat'],r['opponent'],r['mode']) for r in rows}==expected
        for path,digest in manifest['sources'].items():assert sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
        assert sum(r['constraint_checks'] for r in rows)==len(rows)*719
        total+=len(rows)
    rows=json.loads((OUT/'confirmation_results.json').read_text())
    mode=json.loads((OUT/'selection.json').read_text())['mode']
    overall=compare(rows,mode,'fixed');direct=compare(rows,mode,'fixed','priority')
    extra=compare(rows,mode,'available') if mode!='available' else None
    gates={'positive_mean_margin':overall['margin_delta']>0,'no_fewer_wins':overall['wins']>=overall['baseline_wins'],
      'direct_wins_exceed_losses':direct['wins']>direct['losses'],'beats_availability_margin':extra is None or extra['margin_delta']>0}
    package=json.loads((OUT/'package.json').read_text())
    source=ROOT/'agents/adaptive_order_candidate.py'
    assert sha256(source.read_bytes()).hexdigest()==package['sha256']
    parity=sum(r.get('packaged_parity_actions',0) for r in rows)
    assert parity==overall['n']*719
    promoted=all(gates.values())
    selected=BASE
    if promoted:
        name='market_impact_selected.py' if mode=='static' else 'market_available_selected.py' if mode=='available' else 'adaptive_order_selected.py'
        selected=ROOT/'agents'/name
        assert not selected.exists() or selected.read_bytes()==source.read_bytes(),'Refusing to replace unrelated candidate'
        selected.write_bytes(source.read_bytes())
    summary=(f"Keep {selected.relative_to(ROOT).as_posix()} as the locally preferred candidate. "
      f"The confirmed {mode} ordering policy produced {overall['wins']} wins, {overall['ties']} ties and {overall['losses']} losses in {overall['n']} matches, "
      f"versus {overall['baseline_wins']} wins, {overall['baseline_ties']} ties and {overall['baseline_losses']} losses for fixed priority on the same panel. "
      f"Mean cash changed by {overall['cash_delta']:+.1f} and match margin by {overall['margin_delta']:+.1f}. "
      +(f"Its additional margin improvement over availability-only ordering was {extra['margin_delta']:+.1f}. " if extra else '')+
      "The selected price-impact rule uses current prices and available lot sizes; it does not use opponent forecasts. The previous selected files are preserved. No Kaggle submission was made.") if promoted else (
      f"Retain {BASE.relative_to(ROOT).as_posix()}. The {mode} candidate did not pass all confirmation gates: {gates}. No Kaggle submission was made.")
    decision={'selected':selected.relative_to(ROOT).as_posix(),'promoted':promoted,'mode':mode,'gates':gates,'summary':summary,
      'sha256':sha256(selected.read_bytes()).hexdigest(),'confirmation':overall,'direct_against_fixed':direct,'versus_availability':extra,
      'scored_games':total,'additional_smoke_parity_games':4,'packaged_parity_actions':parity+package['parity_actions']}
    (OUT/'decision.json').write_text(json.dumps(decision,indent=2))
    readme=ROOT/'README.md';text=readme.read_text(encoding='utf-8')
    start=text.index('**Latest competitive candidate (2026-09-16):**');end=text.index('The [market forecast and sales-DP study]',start)
    if promoted:
        block=f'''**Latest competitive candidate (2026-09-16):**
[`{decision['selected']}`]({decision['selected']}), a self-contained six-day router
with the milk/wool sales adapter and ordering based on current price impact and
available lot sizes. It preserves the previous opening through turn 215.
Independent confirmation on eight fresh seeds, both seats and five opponent
behaviors: **{overall['wins']} wins, {overall['ties']} ties, {overall['losses']} losses** versus {overall['baseline_wins']} wins, {overall['baseline_ties']} ties and
{overall['baseline_losses']} losses for fixed priority on the same panel. Mean cash improved by
{overall['cash_delta']:,.0f}; mean match margin improved by {overall['margin_delta']:,.0f}.
The [adaptive market-order study](docs/adaptive_market_order.md) records {total}
evaluation games, all eight first shops, opponent-forecast controls, and a separate
availability-only control for stale sale orders. The price-impact rule beat the
forecast-based alternatives in discovery; opponent forecasts are not used in the
selected policy. These are local results against a limited opponent panel, not
a leaderboard claim. The candidate has not been submitted to Kaggle.

Previous candidates remain available:
[`agents/market_priority_selected.py`](agents/market_priority_selected.py)
([opponent-aware sales study](docs/opponent_sales.md)) and
[`agents/production_selected.py`](agents/production_selected.py)
([production study](docs/production_research.md)).

'''
        readme.write_text(text[:start]+block+text[end:],encoding='utf-8')
    elif 'docs/adaptive_market_order.md' not in text:
        readme.write_text(text[:end]+'The [adaptive market-order study](docs/adaptive_market_order.md) is complete; no candidate passed all confirmation gates.\n\n'+text[end:],encoding='utf-8')
    print(json.dumps(decision,indent=2))


if __name__=='__main__':main()
