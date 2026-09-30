"""Paired, descriptive output changes around late shop reveals, 30 UMG games."""
import json
from pathlib import Path
from statistics import mean, median

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/production_continuation'
PRODUCTS=['WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','EGG','MILK','WOOL','FERTILIZER']
SHOP_PRODUCTS={
 'BAKERY':['WHEAT','EGG'],
 'PIZZA_SHOP':['WHEAT','TOMATO','MILK'],
 'BRUNCH_SPOT':['WHEAT','STRAWBERRY','EGG'],
 'YARN_STORE':['WOOL'],
 'ICE_CREAM_SHOP':['WHEAT','STRAWBERRY','MILK'],
 'PET_CAFE':['CARROT'],
 'SMOOTHIE_SHOP':['STRAWBERRY','MILK'],
 'FARMERS_MARKET':['WHEAT','CARROT','TOMATO','STRAWBERRY'],
}
DAYS=[15,18,21,24]


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def summary(v):
    return dict(n=len(v),min=min(v),max=max(v),median=median(v),mean=mean(v)) if v else dict(n=0,min=None,max=None,median=None,mean=None)
def label(s):return s.replace('_',' ').title()
def signed(x):return f'{x:+g}'
def cell(r):
    if not r['n']:return '— (n=0)'
    bounds=signed(r['min']) if r['min']==r['max'] else signed(r['min'])+'…'+signed(r['max'])
    return f"{bounds}; median {signed(r['median'])}; n={r['n']}"


def main():
    games=[read(p) for p in sorted((BASE/'three_day_periods').glob('game-*.json'))]
    assert len(games)==30 and all(g['submission']==56266758 for g in games)
    events=[]
    for g in games:
        audit=read(ROOT/f"results/fresh/leader_segments/segments-{g['episode']}.json")
        for day in DAYS:
            s=day//3
            before_shops=audit['shops_by_segment'][str(s-1)]
            after_shops=audit['shops_by_segment'][str(s)]
            assert after_shops[:-1]==before_shops and len(after_shops)==s
            new=after_shops[-1]
            prior=g['segments'][s-1]['conventional_three_day_output']
            after=g['segments'][s]['conventional_three_day_output']
            prev_aligned=g['segments'][s-1]['output'];post_aligned=g['segments'][s]['output']
            assert all(prior.get(p,0)==audit['seats'][g['seat']]['segments'][s-1]['physical'].get('produced:'+p,0) for p in PRODUCTS)
            assert all(after.get(p,0)==audit['seats'][g['seat']]['segments'][s]['physical'].get('produced:'+p,0) for p in PRODUCTS)
            events.append(dict(episode=g['episode'],day=day,shop=new,previous_shops=before_shops,
                before={p:prior.get(p,0) for p in PRODUCTS},after={p:after.get(p,0) for p in PRODUCTS},
                delta={p:after.get(p,0)-prior.get(p,0) for p in PRODUCTS},
                pre_reveal_aligned_delta={p:post_aligned.get(p,0)-prev_aligned.get(p,0) for p in PRODUCTS}))
    groups=[]
    for shop in SHOP_PRODUCTS:
        for day in DAYS:
            rows=[e for e in events if e['shop']==shop and e['day']==day]
            other=[e for e in events if e['shop']!=shop and e['day']==day]
            products={}
            for p in PRODUCTS:
                changes=summary([e['delta'][p] for e in rows])
                control=summary([e['delta'][p] for e in other])
                no_new_demand=summary([e['delta'][p] for e in events if e['day']==day and p not in SHOP_PRODUCTS[e['shop']]])
                products[p]=dict(**changes,before=summary([e['before'][p] for e in rows]),after=summary([e['after'][p] for e in rows]),
                    other_shop_changes=control,non_demanding_shop_changes=no_new_demand,
                    mean_difference_from_other_shops=changes['mean']-control['mean'] if rows and other else None,
                    positive=sum(e['delta'][p]>0 for e in rows),negative=sum(e['delta'][p]<0 for e in rows),
                    zero=sum(e['delta'][p]==0 for e in rows),
                    snapshot_alignment_disagreements=sum(e['delta'][p]!=e['pre_reveal_aligned_delta'][p] for e in rows))
            groups.append(dict(shop=shop,day=day,n=len(rows),products=products,episodes=[e['episode'] for e in rows]))
    result=dict(submission=56266758,games=30,events=events,groups=groups,products=PRODUCTS,shop_products=SHOP_PRODUCTS,days=DAYS,
        measure='Harvested/collected units after minus before within the same game; full calendar three-day windows.',
        notes=['Observed min–max ranges, not confidence intervals or causal shop effects.',
               'Cash does not remove crop maturation delays or labor/land commitments.',
               'Other-shop reference is descriptive; prior demand, board and opponents are not matched.',
               'Zero-sample groups have no estimate. One-sample groups are single observations.'])
    (BASE/'shop_output_changes.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# UMG: movement in three-day output after a new shop','',
        '**30 games of UMG submission 56266758; 120 reveal events.** These are observed within-game changes, not a causal estimate of what the shop alone changes.','',
        'For a reveal on day D: output during D…D+2 minus output during D−3…D−1. Example: a day-18 reveal compares days 18–20 with 15–17. Output means actual harvested/collected units, excluding purchases and sales. Here the periods are full calendar windows (72 actions), rather than the one-tick-earlier snapshot windows in the preceding report. Both are retained in the data.','',
        'Each cell below is **observed minimum…maximum; median; n**. Zero means an observed zero change; — means no example. n=1 is one observation, not an established interval. Product changes within each group come from the same games.','',
        '## Products directly demanded by the new shop','',
        '| New shop | Product | Day 15 | Day 18 | Day 21 | Day 24 |','|---|---|---|---|---|---|']
    for shop,ps in SHOP_PRODUCTS.items():
        for p in ps:
            gs=[next(g for g in groups if g['shop']==shop and g['day']==day) for day in DAYS]
            lines.append('| '+label(shop)+' | '+label(p)+' | '+' | '.join(cell(g['products'][p]) for g in gs)+' |')
    lines.extend(['','## All-product changes and reference movements','',
        'The reference is the mean change in games revealing another shop at the same date. It helps expose seasonal maturation but is not a matched causal control.',''])
    for g in groups:
        lines.extend([f"### {label(g['shop'])}, day {g['day']} (n={g['n']})",'',
            '| Product | Before mean | After mean | Change range | Median change | Other-shop mean change |','|---|---:|---:|---|---:|---:|'])
        for p,r in g['products'].items():
            fmt=lambda x:'—' if x is None else f'{x:.1f}'
            bounds='—' if not r['n'] else signed(r['min'])+'…'+signed(r['max'])
            lines.append('| '+label(p)+' | '+fmt(r['before']['mean'])+' | '+fmt(r['after']['mean'])+' | '+bounds+' | '+fmt(r['median'])+' | '+fmt(r['other_shop_changes']['mean'])+' |')
        lines.append('')
    lines.extend(['## Interpretation for production plans','',
        'A positive immediate harvest change can be caused by existing crop ages, harvest timing, feeding/care or fertilizer. New tomatoes cannot supply their first crop until age 8, and new strawberries until age 10. A new shop is therefore better related to both immediate servicing decisions and later planting/output targets. Existing cohorts, labor capacity and financing remain constraints even when cash is abundant.','',
        'All groups are small (30 games divided over eight possible shop types at each date), and the marginal ranges combine different starting farms. Use these as observed response envelopes, not numerical rules such as “Farmers Market causes +X strawberries.”','',
        'Sources: `results/fresh/production_continuation/three_day_periods/`, original verified `results/fresh/leader_segments/segments-*.json`. Reproduce with `scripts/analyze_umg_shop_output_changes.py`.'])
    (ROOT/'docs/umg_shop_output_changes.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('events',len(events),'groups',len(groups),'sample_counts',[(g['shop'],g['day'],g['n']) for g in groups])
    print('Farmers day18 strawberry',next(g for g in groups if g['shop']=='FARMERS_MARKET' and g['day']==18)['products']['STRAWBERRY'])
    template=ROOT/'scripts/fragments/umg_shop_changes.html'
    if template.exists():
        target=Path('C:/Users/xyygl/.codex/visualizations/2026/09/15/01a0a5c7-18b1-7141-a48f-45f175aa1a3c/umg-shop-output-changes.html')
        target.write_text(template.read_text(encoding='utf-8').replace('__DATA__',json.dumps(result,separators=(',',':'))),encoding='utf-8')
        assert target.stat().st_size<1000000
        print(target)


if __name__=='__main__':main()
