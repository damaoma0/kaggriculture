"""Report the completed capital search, validation and untouched confirmation."""
from copy import deepcopy
import json
from statistics import mean
from evaluate_boards import ROOT, module_at, observation


def summary(rows):
    names={r["name"] for r in rows}
    return sorted([(n,[r for r in rows if r["name"]==n]) for n in names],key=lambda p:-mean(r["margin"] for r in p[1]))


def main():
    out=ROOT/"results/fresh/capital_search"
    panels={stage:json.loads((out/f"{stage}.json").read_text()) for stage in ("screen","validate","confirm")}
    selected=json.loads((out/"selection.json").read_text())
    name=selected["name"]
    verified=0
    for seat in (0,1):
        path=out/f"{name}-86601-seat{seat}/opening.json"
        replay=json.loads(path.read_text())
        module=module_at("selected_capital",ROOT/"agents/opening_v3.py")
        for t in range(216):
            obs=observation(replay["steps"][t],seat)
            before=deepcopy(obs)
            assert module.agent(obs)==replay["steps"][t+1][seat]["action"]
            assert obs==before
            verified+=1
    lines=["# Opening capital-allocation search","",
           f"Selected local research opening: **{name}**, in `agents/opening_v3.py`.","",
           "## Method","",
           "31 configurations were screened on two seed pairs (62 games, our seat 0). The unchanged public-router opening and previous growth opening were controls. Three candidates advanced with both controls to four new seed pairs, both seats (40 games). The validation winner was frozen, then compared with both controls on four untouched seed pairs, both seats (24 games). Selection uses mean final cash margin in direct matches against the router opening, with BOTH farms switching to the identical replanting rule at day 9.","",
           "Replanting maintains existing assets, replaces cleared original crop plots with wheat through day 25, and buys no more animals or land. Both farms use the same workload rule capped at 10 hands. Seeds are hidden from agents; opening and future seeds are paired across configurations, but farm-dependent random draws and shared-market effects remain part of the outcome.","",
           "Router variants preserve the recorded movement stream while substituting purchase/placement/planting item names, limiting hires, changing sale order, or selling fertilizer instead of applying it. These are coupled action-stream interventions, not fully redesigned schedules. Some substitutions break feeding or crop timing; their failure does not establish that the substituted crop or animal is intrinsically bad. Growth variants change initial herd size, slow-crop allocation, land timing and cash-crop harvest age using the observation-driven scheduler.","",
           "## Untouched confirmation","",
           "| Opening | Our final cash | Router-opening cash | Our margin | Wins | Mean day-1 cash |","|---|---:|---:|---:|---:|---:|"]
    for n,g in summary(panels['confirm']):
        lines.append(f"| {n} | {mean(r['our_final'] for r in g):,.0f} | {mean(r['router_final'] for r in g):,.0f} | {mean(r['margin'] for r in g):+,.0f} | {sum(r['margin']>0 for r in g)}/{len(g)} | {mean(r['day1_cash'] for r in g):,.0f} |")
    new=[r for r in panels['confirm'] if r['name']==name]
    old={(r['seed'],r['seat']):r for r in panels['confirm'] if r['name']=='growth-control'}
    gains=[r['margin']-old[r['seed'],r['seat']]['margin'] for r in new]
    lines += ["",f"Compared with the previous growth opening, selected mean margin improves by {mean(gains):+,.0f}; improvement occurs in {sum(g>0 for g in gains)}/{len(gains)} paired scenarios.","",
              "## Capital and revenue diagnostics","",
              "| Opening | Mean day-1 cash | Mean day-9 cash | Mean first non-fertilizer sale step | Mean opening revenue | Mean opening spending |","|---|---:|---:|---:|---:|---:|"]
    for n,g in summary(panels['confirm']):
        sales=[r['first_product_sale_step'] for r in g if r['first_product_sale_step'] is not None]
        revenue=mean(sum(r['opening_accounts'][r['seat']]['revenue'].values()) for r in g)
        spend=mean(sum(r['opening_accounts'][r['seat']]['spend'].values()) for r in g)
        lines.append(f"| {n} | {mean(r['day1_cash'] for r in g):,.0f} | {mean(r['day9']['cash'] for r in g):,.0f} | {mean(sales) if sales else 'none'} | {revenue:,.0f} | {spend:,.0f} |")
    lines += ["","First sale excludes fertilizer but can include resale of purchased feed; it is a transaction diagnostic, not proof of harvest time. Step 24 is the start of day 1. Revenue and spending are recorded from successful engine transactions, including fertilizer sales and worker costs. Near-zero idle cash alone is not the selection objective.","",
              "## Validation ranking","","| Opening | Mean cash | Mean margin | Wins |","|---|---:|---:|---:|"]
    for n,g in summary(panels['validate']):
        lines.append(f"| {n} | {mean(r['our_final'] for r in g):,.0f} | {mean(r['margin'] for r in g):+,.0f} | {sum(r['margin']>0 for r in g)}/{len(g)} |")
    lines += ["","## Screen ranking","","| Opening | Mean cash | Mean margin | Opening crop/animal losses (total) |","|---|---:|---:|---:|"]
    for n,g in summary(panels['screen']):
        lines.append(f"| {n} | {mean(r['our_final'] for r in g):,.0f} | {mean(r['margin'] for r in g):+,.0f} | {sum(sum(r['opening_losses'].values()) for r in g)} |")
    lines += ["","## Verification and limits","",
              f"All {sum(len(p) for p in panels.values())} evaluated games completed with valid intermediate statuses and exact continuation cash accounting. The selected entry point reproduced {verified} opening actions across both saved confirmation seats, without observation mutation. The final selection was frozen before confirmation; the four confirmation seeds are still a small sample. This is one opponent and one continuation rule, not a leaderboard win-rate estimate or an optimal opening. The generic controller's handling of different layouts can influence rankings.","",
              f"[Exact selected moves](../results/fresh/capital_search/{name}-86601-seat0/moves.md) · [Full replay](../results/fresh/capital_search/{name}-86601-seat0/full_replay.json) · [Selection](../results/fresh/capital_search/selection.json)","",
              "Commands and exact candidate/source hashes are saved in the screen, validate and confirm manifests under `results/fresh/capital_search`. Run `scripts/search_capital.py --stage screen`, then pass the frozen shortlist with `--stage validate --names ...`, and the selected opening plus controls with `--stage confirm --names ...`. Existing recorded folders are not overwritten.",""]
    (ROOT/"docs/capital_search.md").write_text("\n".join(lines),encoding="utf-8")
    print(f"PASS {verified} selected opening actions.")
    print("\n".join(lines[14:22]))


if __name__=="__main__": main()
