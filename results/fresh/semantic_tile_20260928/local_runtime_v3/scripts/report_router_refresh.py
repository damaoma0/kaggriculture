"""Summarize the frozen router refresh and retain benchmark limitations."""
import ast,json
from hashlib import sha256
from statistics import mean
from compare_router_refresh import ROOT,OUT,DATA,PATHS,jobs

def main():
    summary=json.loads((OUT/'summary.json').read_text());manifest=json.loads((OUT/'manifest.json').read_text())
    for name,digest in manifest['sources'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==digest
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text()) for j in jobs()]
    assert len(rows)==192
    original=ROOT/'data/public_candidates/thomastschinkel/extracted/main.py'
    assert ast.dump(ast.parse(original.read_text(encoding='utf-8')))==ast.dump(ast.parse(PATHS['sixday'].read_text(encoding='utf-8')))
    gains={}
    for opponent in ('v45','v44','farmingv5','twocoins','pasture2700'):
        pairs=[]
        for seed in range(133000,133008):
            for seat in (0,1):
                a=next(r for r in rows if (r['panel'],r['seed'],r['seat'],r['policy'],r['opponent'])==('randomshops',seed,seat,'selected',opponent))
                b=next(r for r in rows if (r['panel'],r['seed'],r['seat'],r['policy'],r['opponent'])==('randomshops',seed,seat,'sixday',opponent))
                assert a['shops']==b['shops'];pairs.append(a['margin']-b['margin'])
        gains[opponent]={'mean_margin_change':mean(pairs),'better':sum(x>0 for x in pairs),'worse':sum(x<0 for x in pairs),'same':sum(x==0 for x in pairs)}
    errors=[]
    for r in rows:
        for i,telemetry in enumerate(r['telemetry']):
            for k,v in telemetry.items():
                if 'error' in k.lower() and isinstance(v,(int,float)) and v:errors.append([r['seed'],r['seat'],r['policy'],r['opponent'],i,k,v])
    diagnostics={'paired_changes':gains,'reported_error_counters':errors,'max_action_seconds':max(max(r['max_seconds']) for r in rows),'unchanged_sixday_ast':True}
    (OUT/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2))
    labels={'v45':'V45: First-Turn Wheat Round Trip','v44':'V44: Winning the Same-Turn Sale Race','farmingv5':'Farming Score V5','twocoins':'Two Coins, One Sheep','pasture2700':'Shape the Shop (tetsutani)','sixday':'Original six-day parent'}
    references={n:json.loads((PATHS[n].parent/'kernel-metadata.json').read_text(encoding='utf-8'))['id'] for n in labels}
    lines=['# Why local router wins did not translate to the ladder','',
      '## Findings','',
      '**The older base policy and a narrow benchmark are the main problems supported by these tests.** The latest downloaded six-day notebook has the same executable code as our previously tested parent (identical Python AST; only file formatting differs). The new public-agent panel is substantially stronger. Our sale/liquidation modifications have relatively small effects compared with the gaps to modern agents.','',
      'The prior 80–0 result was a local result against a limited panel, including related route variants and older policies. It was not a calibrated prediction of leaderboard rating. That benchmark should have been refreshed before so much further optimization of the older base. Winning directly against one public router does not establish equivalent or higher ladder strength across other opponents and shop sequences.','',
      'The fetched submission snapshot showed **1532.2 with 14 public wins and 4 losses** after 18 public matches. The downloaded leaderboard snapshot put QQ Farming at 1963.8, Napster Y at 1468.0, bzczz123 at 1765.3 and ruizhichen at 1572.9. These are snapshot team scores, not their exact ratings at match time. The short match history is insufficient to identify our settled rating, but its losses and the fresh benchmarks are real weaknesses.',
      '', '## Fresh direct matches','',
      'Eight fresh seeds (133000–133007), both seats, with uniform independent shop draws shared across all policy comparisons and hidden until revealed. The official engine handles the rest of the game. Each row has 16 games; the effective independent sample is eight seeds, not sixteen seats. No policy tuning was performed.','',
      '| Opponent | Our W/T/L | Our average margin | Parent W/T/L | Parent average margin | Our change vs parent |','|---|---:|---:|---:|---:|---:|']
    for o in ('v45','v44','farmingv5','twocoins','pasture2700'):
        a=summary['randomshops/selected/'+o];b=summary['randomshops/sixday/'+o]
        lines.append(f"| [{labels[o]}](https://www.kaggle.com/code/{references[o]}) | {a['wins']}/{a['ties']}/{a['losses']} | {a['mean_margin']:+,.1f} | {b['wins']}/{b['ties']}/{b['losses']} | {b['mean_margin']:+,.1f} | {gains[o]['mean_margin_change']:+,.1f} |")
    a=summary['randomshops/selected/sixday'];s=summary['firstshops/selected/v45']
    lines+=['',f"Directly against its unmodified six-day parent, our agent scored **{a['wins']}/{a['ties']}/{a['losses']}**, averaging **{a['mean_margin']:+,.1f}** margin. That local improvement is compatible with both policies losing to a newer family.",
      '',f"An additional panel forces each of the eight first shops once, both seats (134000–134007). Against V45, ours scored **{s['wins']}/{s['ties']}/{s['losses']}**, with mean margin **{s['mean_margin']:+,.1f}**. This is a coverage check, not a natural-frequency sample.",
      '', 'The newcomers are not five independent strategy families: several share Shop Router/Two Coins ancestry. This study establishes performance against the downloaded files, not that any agent is globally best or guaranteed a particular rating. The weaker result for the tetsutani notebook also shows why a historical score label is not enough to select a benchmark.',
      '', '## Are our modifications causing the four live losses?','',
      'As a diagnostic, replay each rival’s actual recorded action stream, keep the observed shop sequence, and let our chosen policy respond normally to the evolving state. These are **fixed-stream controls, not matches against the rival’s live decision code**. Opponents cannot adapt their action choices, and changed market conditions can affect the success of their recorded orders.','',
      '| Recorded opponent | Our submitted margin | Unmodified parent margin | V45 diagnostic margin |','|---|---:|---:|---:|']
    for episode in (109609580,109611734,109613921,109617159):
        rs={p:json.loads((OUT/'replay_controls'/f'{episode}-{p}.json').read_text()) for p in ('selected','sixday','v45')}
        lines.append(f"| {rs['selected']['opponent']} | {rs['selected']['margin']:+,.0f} | {rs['sixday']['margin']:+,.0f} | {rs['v45']['margin']:+,.0f} |")
    trace=json.loads((OUT/'trace_v45.json').read_text());u,v=trace['ledger']
    lines+=['','The selected-agent controls reproduce every original state in all four games. The unmodified parent also loses all four recorded streams and loses by more. This argues against our changes being the principal cause of those losses. V45 reverses the margins against the fixed streams; that motivates testing it, but is not proof of four hypothetical live wins.',
      '', '## What the newer code adds','',
      '- A larger route portfolio: Two Coins contains 13 production tapes, compared with five in our six-day base, plus route selection based on observed shop combinations.',
      '- Worker-level recovery when weeds interrupt planting, rather than continuing a broken action suffix.',
      '- Forecasting the agent’s own upcoming pickups and stock needs, reserving inputs and bringing eligible sales forward. These are execution and inventory changes, beyond rearranging existing sell orders.',
      '- Conditional crop/animal substitutions, fourth-quadrant production, feed and fertilizer checks, and terminal collection planning in the newer layered agents.',
      '- V45 additionally uses a 70-unit first-turn wheat round trip. Its author targets rival order placement and opening affordability. This is a larger, interaction-dependent mechanism than our earlier five-unit example; the notebook’s own claimed gains are not used as our benchmark results.',
      '', '### One measured production example','',
      'The detailed trace repeats seed 133000, selected agent in seat 0 against V45. The eight shop draws are Farmers Market, Farmers Market, Pizza Shop, Smoothie Shop, Yarn Store, Farmers Market, Pizza Shop, Yarn Store. This particular world strongly supports tomato demand.',
      '', 'At turn 432 both farms still have the same animal counts, 33 strawberry plants, 25 wheat plants and three land quadrants. By turn 576, V45 has bought a fourth quadrant and planted ten tomatoes; we have no tomatoes. V45 eventually sells **80 tomatoes for 44,196**. Final cash is **139,316 versus our 99,455**, a gap of **39,861**. Telemetry records one production commitment, ten confirmed tomato plants and 80 harvested tomato units.',
      '',f"Across all products in this example, V45 earns {sum(v['revenue'].values())-sum(u['revenue'].values()):,.0f} more revenue and spends {sum(v['spend'].values())-sum(u['spend'].values()):,.0f} more. This is an exact accounting explanation, not an isolated tomato-policy ablation. It shows that similar visible farms can later diverge materially through production investment, not just sale ordering.",
      '', '## Provenance and validation','',
      '- Downloaded six notebooks through the Kaggle API into `data/router_refresh_20260916/`. Notebook setup cells were not executed. Agent sources were extracted as data; embedded hashes, local package files and literal embedded executable helpers were inspected. Original license notices were retained.',
      '- V44 and V45 source bytes match their published embedded digests. Two Coins uses its notebook’s `sale_horizon=2` settings and complete local `policy.py`, `router.py` and `actions.json`, not just its loader.',
      '- The old Indar Karhana pasture benchmark’s packaged entry point simply delegates to the policy file we tested; the audit did not find an entry-point mismatch there. The newly downloaded tetsutani notebook is a different artifact despite its similar title.',
      '- Cached web snippets show conflicting scores and versions (including 2400/2600/2700 claims). Notebook current score, best historical version score, author/team score and the exact downloaded artifact must not be treated as interchangeable. This report makes no claim that every downloaded file is currently rated 2700.',
      f"- All 192 direct games completed 720 valid states and reconciled both cash ledgers. The 12 replay controls also completed and reconciled; selected controls matched all original states. One repeated detailed trace exactly matched its panel result. Total: 205 full-game runs. Maximum observed per-call time in the concurrent comparison was {diagnostics['max_action_seconds']:.3f}s; this is not an isolated competition-host timing certification.",
      f"- Nonzero telemetry fields containing 'error': {len(errors)}. Detailed counters, hashes and paired changes are recorded in `diagnostics.json` and the frozen manifest.",
      '', '## Decision','',
      'Preserve the currently uploaded agent as a control. Use the newer, fully inspectable agents as the next competitive baselines and evaluate changes against multiple modern opponents, with public-source versions and shop panels frozen. Do not infer leaderboard rating from head-to-head wins over one older parent. No agent was promoted or submitted during this comparison.',
      '', '## Reproduction','',
      '`scripts/extract_router_refresh.py` extracts single-file sources; the Two Coins support files were extracted as notebook literals and hash-checked gzip assets. `scripts/compare_router_refresh.py` runs the frozen direct panel. `scripts/router_refresh_replay_controls.py` runs the diagnostic replay controls. `scripts/trace_router_refresh.py` reproduces the detailed V45 game. `scripts/report_router_refresh.py` verifies hashes and regenerates this report.',
      '', 'Results: `results/fresh/router_refresh/`. Source notebook URLs and kernel metadata: `data/router_refresh_20260916/`.']
    (ROOT/'docs/router_refresh.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(diagnostics,indent=2))

if __name__=='__main__':main()
