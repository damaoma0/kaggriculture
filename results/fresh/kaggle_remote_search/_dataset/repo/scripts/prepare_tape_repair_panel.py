"""Freeze the repair policy and adapt the previously audited full-game harness."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import random
import secrets

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'results/fresh/value_tape_wide_20260923_01a0'
BASE = ROOT / 'results/fresh/tape_repair_20260924_01a0'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default='r1')
    ap.add_argument('--policy', default='value_tape_repair_r1')
    ap.add_argument('--all-v56', action='store_true')
    ap.add_argument('--all-recordings', action='store_true')
    ap.add_argument('--fresh-worlds', type=int, default=0)
    args = ap.parse_args()
    assert sum((args.all_v56, args.all_recordings, bool(args.fresh_worlds))) <= 1
    out = BASE / args.version
    assert not out.exists(), 'Never overwrite a frozen policy experiment'
    payload = out / 'payload'
    manifest = json.loads((OLD / 'source_manifest.json').read_text())
    for rel, digest in manifest['sha256'].items():
        source = OLD / 'payload' / rel
        assert sha256(source.read_bytes()).hexdigest() == digest
        target = payload / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for module in sorted({'value_tape_repair_r1', 'value_tape_repair_r2', args.policy}):
        rel = f'scripts/{module}.py'
        shutil.copyfile(ROOT / rel, payload / rel)
        manifest['sha256'][rel] = sha256((payload / rel).read_bytes()).hexdigest()
    rel = f'scripts/{args.policy}.py'
    (out / 'source_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    text = (OLD / 'run_panel.py').read_text()
    text = text[:text.index('\ndef worker(')]
    def replace(old, new):
        nonlocal text
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    replace("PAYLOAD = OUT / 'payload'", "PAYLOAD = OUT / 'payload'\nREFERENCE = Path(" + repr(str(OLD)) + ")")
    replace("N = importlib.import_module('value_tape_search_v9')",
            f"N = importlib.import_module({args.policy!r} if arm=='candidate' else 'value_tape_search_v9')")
    replace("assert set(N.B.M.M.DEMAND)==set(E.SHOPS)",
            "assert set(importlib.import_module('rival_trajectory_model_v3').M.DEMAND)==set(E.SHOPS)")
    replace("gzip.open(OUT/'recordings'/", "gzip.open(REFERENCE/'recordings'/")
    replace("reference=json.loads((OUT/'arms'/f'{spec[\"id\"]}-recording.json').read_text())",
            "reference=json.loads((REFERENCE/'arms'/f'{spec[\"id\"]}-recording.json').read_text())")
    replace("ours = None if arm=='recording' else V.fresh_agent()",
            "ours = None if arm=='recording' else V.fresh_agent()\n    if arm=='candidate': N.install(ours)")
    replace("decisions=[]; actions=[[],[]]; prefix=[]; daily=[]; timings=[]",
            "decisions=[]; actions=[[],[]]; prefix=[]; daily=[]; timings=[]; repair_execution=[]")
    replace("searched=arm=='candidate' and t in (288,360,432)",
            "searched=arm in ('candidate','v9') and t in (288,360,432)\n                if arm=='candidate':\n                    repair=N.install(ours)\n                    if repair.targets and t==repair.until:\n                        repair_execution.append(dict(until=t,assets=list(repair.targets.values()),stats=dict(repair.stats)))")
    replace("if selected is not None:\n                        def committed",
            "if arm=='candidate':\n                        N.commit(ours,selected,decision['until'],router)\n                    elif selected is not None:\n                        def committed")
    replace("write(OUT/'decisions'/f'{spec[\"id\"]}-d{t//24}.json',decisions[-1])",
            "write(OUT/'decisions'/f'{spec[\"id\"]}-{arm}-d{t//24}.json',decisions[-1])")
    replace("economics=economics,physical=[dict(p) for p in physical],physical_daily=physical_daily,",
            "economics=economics,physical=[dict(p) for p in physical],physical_daily=physical_daily,\n        repair_execution=repair_execution,native_telemetry=V.canonical(ours.__globals__['_SHP_REPORT']) if ours else {},")
    start, end = text.index('\ndef specs():'), text.index('\ndef physical_key(')
    text = text[:start] + "\ndef specs():\n    return json.loads((OUT/'design.json').read_text())['specs']\n\n" + text[end:]
    text += '''
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--case',required=True)
    ap.add_argument('--arm',choices=['baseline','candidate','v9'],required=True)
    args=ap.parse_args()
    spec=next(s for s in specs() if s['id']==args.case)
    started=time.perf_counter()
    try: result=run_game(spec,args.arm)
    except Exception: result=dict(spec=spec,arm=args.arm,completed=False,error=traceback.format_exc())
    result['seconds']=time.perf_counter()-started
    write(OUT/'arms'/f'{args.case}-{args.arm}.json',result)
    print('ARM '+json.dumps({k:result.get(k) for k in ('spec','arm','completed','margin','selected','seconds','remaining_overage_seconds','error')}),flush=True)
    raise SystemExit(0 if result['completed'] else 1)

if __name__=='__main__':main()
'''
    compile(text, str(out / 'run_panel.py'), 'exec')
    (out / 'run_panel.py').write_text(text, encoding='utf-8')
    pairs = [json.loads(p.read_text()) for p in (OLD / 'pairs').glob('*.json')]
    losers = sorted((p for p in pairs if p['spec']['kind']=='live'
                     and p['spec']['opponent']=='v56' and not p['intervened']),
                    key=lambda p:p['baseline_margin'])[:4]
    if args.all_v56:
        losers = sorted((p for p in pairs if p['spec']['kind']=='live' and p['spec']['opponent']=='v56'),
                        key=lambda p:p['spec']['id'])
    records = [p for p in pairs if p['spec'].get('anchored') and p['spec']['episode'] in (112109339,112543358)]
    design = dict(protocol='Development: four largest unchanged live V56 losses plus Snorlax and Evil Mango exact native recordings. Previously inspected outcomes; not a holdout.',
                  specs=[p['spec'] for p in records+losers], policy_sha256=manifest['sha256'][rel],
                  harness_sha256=sha256((out/'run_panel.py').read_bytes()).hexdigest())
    if args.all_v56:
        design['protocol']='Development: all 32 previously evaluated live V56 worlds plus Snorlax and Evil Mango exact native recordings. Not a new holdout; unchanged original sources and outcomes retained.'
    if args.all_recordings:
        design.update(protocol='Frozen R3 extension on all 42 previously fetched recordings: 32 rated-opponent records plus 10 original-m1 anchors. Earlier V9 results were inspected; this is not a new holdout. Reuse exact source reconstructions and baseline/V9 controls by hash. Exclude broken opponent-action counterfactuals from competitive claims, retaining all outcomes in the report.',
                      specs=[p['spec'] for p in sorted(pairs,key=lambda p:p['spec']['id']) if p['spec']['kind']=='replay'],
                      arms=['candidate'],decisions=[12,15,18])
    if args.fresh_worlds:
        seed = secrets.randbits(128)
        rng = random.Random(seed)
        used = {p['spec']['seed'] for p in pairs if p['spec']['kind']=='live'}
        shops = sorted(['BAKERY','PIZZA_SHOP','BRUNCH_SPOT','YARN_STORE','ICE_CREAM_SHOP',
                        'PET_CAFE','SMOOTHIE_SHOP','FARMERS_MARKET'])
        specs = []
        for world in range(args.fresh_worlds):
            while True:
                game_seed = rng.randrange(2**32)
                if game_seed not in used and not 93021000 <= game_seed <= 93023999:break
            used.add(game_seed)
            draw = [rng.choice(shops) for _ in range(8)]
            for rival in ('v56','original_m1'):
                specs.append(dict(id=f'fresh-{world:02d}-{rival}',world=world,seed=game_seed,
                                  seat=world%2,shops=draw,kind='live',opponent=rival))
        design.update(protocol='Frozen fresh qualification: IID uniform eight-shop worlds, each crossed with live V56 and original m1, alternating own seat. Every matchup runs original m1, V9, and repair candidate from day zero with the same shops. Report world-clustered uncertainty. No policy tuning or outcome-based exclusions.',
                      master_seed=seed,independent_worlds=args.fresh_worlds,specs=specs,
                      arms=['baseline','v9','candidate'],decisions=[12,15,18])
    (out / 'design.json').write_text(json.dumps(design,indent=2),encoding='utf-8')
    print(json.dumps(dict(out=str(out),**design),indent=2))


if __name__ == '__main__':
    main()
