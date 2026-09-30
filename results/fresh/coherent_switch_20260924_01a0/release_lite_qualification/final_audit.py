import hashlib, json, statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parent
games=ROOT/'games'
design=json.loads((ROOT/'design.json').read_text())
manifest=json.loads((ROOT/'manifest.json').read_text())
env=json.loads((ROOT/'environment_manifest.json').read_text())
specs={s['id']:s for s in design['specs']}
rows={}
errors=[]
for p in games.glob('*.json'):
    d=json.loads(p.read_text())
    key=(d.get('spec',{}).get('id'),d.get('arm'))
    if key in rows: errors.append(f'duplicate {key}')
    rows[key]=d
    if not d.get('completed'): errors.append(f'incomplete {p.name}: {d.get("error")}')
    if d.get('ledger_verified') != [True,True]: errors.append(f'ledger flag {p.name}')
    if len(d.get('cash',[]))!=2 or len(d.get('ledgers',[]))!=2: errors.append(f'ledger cardinality {p.name}'); continue
    for seat in (0,1):
        led=d['ledgers'][seat]
        net=3000+sum(led['revenue'].values())-sum(led['spend'].values())
        if net != d['cash'][seat]: errors.append(f'ledger arithmetic {p.name} seat{seat}: {net} != {d["cash"][seat]}')
    if len(d.get('daily',[]))!=30: errors.append(f'daily cardinality {p.name}')
    if len(d.get('timings',[]))!=719: errors.append(f'timing cardinality {p.name}')
    if d.get('bank_remaining',-1)<0: errors.append(f'negative bank {p.name}')
    if d.get('arm')=='v9lite' and Path(d.get('package_root','')).resolve()!= (ROOT/'package').resolve(): errors.append(f'package root mismatch {p.name}')
    sid,arm=key
    if sid not in specs: errors.append(f'unknown spec {key}')
    elif d.get('spec')!=specs[sid]: errors.append(f'spec mismatch {p.name}')
    if not d.get('action_sha256') or not d.get('prefix_sha256'): errors.append(f'hash missing {p.name}')
expected={(s,a) for s in specs for a in ('baseline','y3','v9lite')}
if set(rows)!=expected: errors.append(f'game set mismatch missing={len(expected-set(rows))} extra={len(set(rows)-expected)}')
if len(design['worlds'])!=64 or len(specs)!=128: errors.append('design cardinality mismatch')
shop_counts={shop:sum(w['first_shop']==shop for w in design['worlds']) for shop in sorted({w['first_shop'] for w in design['worlds']})}
opponent_counts={opp:sum(s['opponent']==opp for s in specs.values()) for opp in sorted({s['opponent'] for s in specs.values()})}
seat_counts={seat:sum(s['seat']==seat for s in specs.values()) for seat in (0,1)}
if len(shop_counts)!=8 or sum(shop_counts.values())!=64: errors.append(f'first shop coverage: {shop_counts}')
if len(opponent_counts)!=2 or set(opponent_counts.values())!={64}: errors.append(f'opponent balance: {opponent_counts}')
if seat_counts!={0:64,1:64}: errors.append(f'seat balance: {seat_counts}')
pkg=ROOT/'package'
for rel,want in manifest['package_files'].items():
    p=pkg/rel
    if not p.exists(): errors.append(f'missing package member {rel}'); continue
    got=hashlib.sha256(p.read_bytes()).hexdigest()
    if got!=want: errors.append(f'package hash mismatch {rel}')
arc=ROOT/'submission.tar.gz'
if hashlib.sha256(arc.read_bytes()).hexdigest()!=manifest['archive_sha256']: errors.append('archive sha mismatch')
eroot=Path(env['environment']['framework_root'])
for rel,want in env['environment']['files'].items():
    p=eroot/rel
    if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=want: errors.append(f'environment hash mismatch {rel}')
prefix_equal=[]; noswitch=[]
for sid in specs:
    b=rows.get((sid,'baseline')); y=rows.get((sid,'y3')); v=rows.get((sid,'v9lite'))
    if not (b and y and v): continue
    if len({b['prefix_sha256'],y['prefix_sha256'],v['prefix_sha256']})==1: prefix_equal.append(sid)
    if y['action_sha256']==v['action_sha256']: noswitch.append(sid)
def margin(r): return r['cash'][r['spec']['seat']]-r['cash'][1-r['spec']['seat']]
summary={}
for arm in ('baseline','y3','v9lite'):
    rr=[rows[(sid,arm)] for sid in specs if (sid,arm) in rows]
    summary[arm]=dict(n=len(rr),mean_own_cash=statistics.mean(r['cash'][r['spec']['seat']] for r in rr),
        mean_opp_cash=statistics.mean(r['cash'][1-r['spec']['seat']] for r in rr),
        mean_margin=statistics.mean(margin(r) for r in rr),
        actual_wins=sum(r['cash'][r['spec']['seat']]>r['cash'][1-r['spec']['seat']] for r in rr),
        ties=sum(r['cash'][r['spec']['seat']]==r['cash'][1-r['spec']['seat']] for r in rr),
        actual_losses=sum(r['cash'][r['spec']['seat']]<r['cash'][1-r['spec']['seat']] for r in rr),
        max_action_seconds=max(max(r['timings']) for r in rr),
        min_bank_remaining=min(r['bank_remaining'] for r in rr),
        errors=sum(r.get('report',{}).get('errors',0) for r in rr))
paired={}
for arm in ('y3','v9lite'):
    diffs=[];cashdiff=[]
    for sid in specs:
        a,b=rows[(sid,arm)],rows[(sid,'baseline')]
        diffs.append(margin(a)-margin(b))
        cashdiff.append(a['cash'][a['spec']['seat']]-b['cash'][b['spec']['seat']])
    paired[arm]=dict(n=len(diffs),mean_margin_delta=statistics.mean(diffs),median_margin_delta=statistics.median(diffs),
        positive_margin_pairs=sum(x>0 for x in diffs),zero_margin_pairs=sum(x==0 for x in diffs),
        mean_own_cash_delta=statistics.mean(cashdiff),positive_own_cash_pairs=sum(x>0 for x in cashdiff),
        margin_deltas=diffs,own_cash_deltas=cashdiff)
vs_y3=[]
cash_vs_y3=[]
for sid in specs:
    a,y=rows[(sid,'v9lite')],rows[(sid,'y3')]
    vs_y3.append(margin(a)-margin(y))
    cash_vs_y3.append(a['cash'][a['spec']['seat']]-y['cash'][y['spec']['seat']])
paired['v9lite_vs_y3']=dict(n=len(vs_y3),mean_margin_delta=statistics.mean(vs_y3),
    median_margin_delta=statistics.median(vs_y3),positive_margin_pairs=sum(x>0 for x in vs_y3),
    zero_margin_pairs=sum(x==0 for x in vs_y3),mean_own_cash_delta=statistics.mean(cash_vs_y3),
    positive_own_cash_pairs=sum(x>0 for x in cash_vs_y3),margin_deltas=vs_y3,own_cash_deltas=cash_vs_y3)
byopp={}
for opp in sorted({s['opponent'] for s in specs.values()}):
    ids=[sid for sid,s in specs.items() if s['opponent']==opp]
    byopp[opp]={}
    for arm in ('baseline','y3','v9lite'):
        byopp[opp][arm]=dict(n=len(ids),mean_margin=statistics.mean(margin(rows[(sid,arm)]) for sid in ids),
            wins=sum(rows[(sid,arm)]['cash'][specs[sid]['seat']]>rows[(sid,arm)]['cash'][1-specs[sid]['seat']] for sid in ids))
decisions=[]
for sid in specs:
    r=rows[(sid,'v9lite')]; seat=specs[sid]['seat']; y=rows[(sid,'y3')]; b=rows[(sid,'baseline')]
    decisions.append(dict(spec=sid,opponent=specs[sid]['opponent'],seat=seat,first_shop=specs[sid]['world']['first_shop'],
       v9lite_cash=r['cash'],v9lite_margin=margin(r),y3_margin=margin(y),baseline_margin=margin(b),
       v9lite_action_sha256=r['action_sha256'],y3_action_sha256=y['action_sha256'],baseline_action_sha256=b['action_sha256'],
       v9lite_prefix_sha256=r['prefix_sha256'],y3_prefix_sha256=y['prefix_sha256'],baseline_prefix_sha256=b['prefix_sha256'],
       v9lite_bank_remaining=r['bank_remaining'],v9lite_max_action_seconds=max(r['timings']),v9lite_failed_hires=len(r['failed_hires'])))
report=dict(audit_scope='independent raw-record integrity, cash/ledger, package/environment hashes, pairing and descriptive paired outcomes; no new games',
    design_worlds=len(design['worlds']),design_specs=len(specs),expected_games=len(expected),actual_games=len(rows),
    game_records_valid=not errors,errors=errors,ledger_reconciliations=2*len(rows),prefix_equal_all_arms=len(prefix_equal),
    prefix_equal_specs=prefix_equal,noswitch_y3_v9lite=len(noswitch),noswitch_specs=noswitch,
    arm_summary=summary,paired_vs_baseline=paired,by_opponent=byopp,decisions=decisions,
    design_balance=dict(first_shop_world_counts=shop_counts,opponent_spec_counts=opponent_counts,seat_spec_counts=seat_counts),
    package_archive_sha256=manifest['archive_sha256'],
    frozen_source_hashes={k:v for k,v in manifest['package_files'].items() if k in ('main.py','agents/mgt_m1.py','agents/mgt_y3.py')})
(ROOT/'final_audit.json').write_text(json.dumps(report,indent=2))
md=['# Independent release qualification audit','',f"- Games: {len(rows)} / {len(expected)}; records and ledgers valid: **{not errors}**.",f"- Cash reconciliations: {2*len(rows)} seats; spec cross-checks: {len(specs)}.",f"- All-arm opening prefix equal: {len(prefix_equal)}/{len(specs)}; Y3 and v9lite full action hashes equal: {len(noswitch)}/{len(specs)}.",'','## Outcomes recomputed from raw records','','| Arm | Mean own cash | Mean opponent cash | Mean margin | Wins / ties / losses | Max action s | Minimum bank s |','|---|---:|---:|---:|---:|---:|---:|']
for arm,s in summary.items(): md.append(f"| {arm} | {s['mean_own_cash']:.2f} | {s['mean_opp_cash']:.2f} | {s['mean_margin']:.2f} | {s['actual_wins']} / {s['ties']} / {s['actual_losses']} | {s['max_action_seconds']:.6f} | {s['min_bank_remaining']:.3f} |")
md+=['','## Paired comparisons','','| Comparison | Mean paired margin delta | Median | Positive pairs | Mean own-cash delta | Positive cash pairs |','|---|---:|---:|---:|---:|---:|']
for arm,s in paired.items():
    label={'y3':'y3 vs baseline','v9lite':'v9lite vs baseline','v9lite_vs_y3':'v9lite vs y3'}[arm]
    md.append(f"| {label} | {s['mean_margin_delta']:.2f} | {s['median_margin_delta']:.2f} | {s['positive_margin_pairs']}/{s['n']} | {s['mean_own_cash_delta']:.2f} | {s['positive_own_cash_pairs']}/{s['n']} |")
md+=['','## Audit errors','',*(errors if errors else ['None.']), '', 'No games were launched during this audit. See final_audit.json for per-spec hashes, values, and paired deltas.']
(ROOT/'final_audit.md').write_text('\n'.join(md)+'\n')
print(json.dumps({k:report[k] for k in ('actual_games','game_records_valid','errors','prefix_equal_all_arms','noswitch_y3_v9lite','arm_summary','paired_vs_baseline')},indent=2))
