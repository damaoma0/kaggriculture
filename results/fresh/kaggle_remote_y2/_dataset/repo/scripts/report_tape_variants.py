"""Update the per-tape revision register and its human-readable experiment log."""
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

from experiment_tape_variants import BASE, CANDIDATE, CASE, OUT, REGISTRY, ROOT, TAPE, digest, read, write


def report():
    design=read(OUT/'design.json')
    pairs=[]
    for episode in design['diagnostic_episodes']:
        b=read(OUT/'historical'/f'{BASE}-{episode}.json')
        a=read(OUT/'historical'/f'{CANDIDATE}-{episode}.json')
        for arm,row in ((BASE,b),(CANDIDATE,a)):
            assert row['completed'] and row['ledger_verified']
            assert row['source_sha256']==design['source_hashes'][arm]
            assert not row['actions_over_1s']
            assert not row['overlay'].get('errors',0) and not row['router'].get('router_errors',0)
            assert not any(row['chassis'].values())
        assert b['action_changes']==0
        econ_delta={}
        for key in ('revenue','spend','units'):
            x,y=a['economics'][0][key],b['economics'][0][key]
            econ_delta[key]={p:x.get(p,0)-y.get(p,0) for p in sorted(set(x)|set(y)) if x.get(p,0)!=y.get(p,0)}
        pairs.append(dict(episode=episode,own_cash_delta=a['cash']-b['cash'],
            opponent_cash_delta=a['opponent_cash']-b['opponent_cash'],
            margin_delta=a['margin']-b['margin'],before_margin=b['margin'],after_margin=a['margin'],
            economy_delta=econ_delta,harvest_delta={p:a['harvested'].get(p,0)-b['harvested'].get(p,0)
                for p in sorted(set(a['harvested'])|set(b['harvested'])) if a['harvested'].get(p,0)!=b['harvested'].get(p,0)},
            decisions=a['variant_report']['decisions'],changed_action_steps=a['action_changes']))
    result=next(p for p in pairs if p['episode']==CASE)
    inactive=[p for p in pairs if p['episode']!=CASE]
    assert all(p['changed_action_steps']==0 for p in inactive)
    status='diagnostic_improvement' if result['margin_delta']>0 and result['own_cash_delta']>0 else 'diagnostic_failed'
    mark_path=REGISTRY/f'{design["variant_id"]}.json'
    mark=read(mark_path)
    mark['status']=status
    mark['evidence']=[dict(kind='fixed_recorded_opponent_full_game',tuned_case=True,
        baseline_source_sha256=design['source_hashes'][BASE],candidate_source_sha256=design['source_hashes'][CANDIDATE],
        result=result,scope_controls=inactive,total_engine_executions=len(pairs)*2)]
    mark['promotion']='Not promoted. Applicable responsive-opponent validation remains outstanding.'
    write(mark_path,mark)
    write(OUT/'summary.json',dict(status=status,pairs=pairs,engine_executions=len(pairs)*2,
        limitations=['The edited case was selected after failure analysis and is not independent confirmation.',
                     'The three other-donor controls show inactivity, not general effectiveness.',
                     'Fixed opponent commands do not adapt; both opponents still receive changed market prices.']))

    # Every original tape has an explicit entry. Absence of a flagged loss is
    # missing evidence, never an assertion that a tape is good or optimal.
    audit=read(ROOT/'results/fresh/all_umg_m1/summary.json')
    by_donor=defaultdict(list)
    for loss in audit['losses']:
        donor=loss.get('plan',{}).get('donor',{}).get('episode')
        if donor:
            by_donor[donor].append(loss)
    entries=[]
    for path in sorted((ROOT/'data/mg_tapes').glob('*/*.json.gz')):
        with gzip.open(path,'rt',encoding='utf8') as f:
            tape=json.load(f)
        episode=tape['episode']
        associated=by_donor[episode]
        evidence=[]
        for loss in associated:
            products={p['product']:p for p in loss['products']}
            glut=[p for p,v in products.items() if p not in ('WHEAT','FERTILIZER')
                  and v['ours']['low_harvest']>=20 and v['ours']['low_harvest']>=v['ours']['produced']/2]
            short=[p for p,v in products.items() if p not in ('WHEAT','FERTILIZER')
                   and v['opponent']['produced']-v['ours']['produced']>=11
                   and v['quantity_component']<-1000
                   and max(v['ours']['avg_price'] or 0,v['opponent']['avg_price'] or 0)>=v['base']]
            wool_gap=products['WOOL']['opponent']['produced']-products['WOOL']['ours']['produced']
            evidence.append(dict(episode=loss['episode'],opponent=loss['opponent'],rating=loss['rating'],
                under2500=loss['under2500'],loss_margin=loss['margin'],
                low_quote_harvest_flags=glut,high_price_shortfall_flags=short,
                milk_to_wool_review=('MILK' in glut and wool_gap>=11 and products['WOOL']['direct_cash_gap']<-1000),
                wool_harvest_gap=wool_gap,
                caveat='Associated final donor; the game may have used earlier tapes. Product gaps are screens, not attributable recoverable profit.'))
        entries.append(dict(base_tape_episode=episode,source=str(path.relative_to(ROOT)),
            source_sha256=digest(path.read_bytes()),
            status=status if episode==TAPE else 'unmodified',
            variants=[mark['id']] if episode==TAPE else [],
            audited_loss_associations=evidence))
    assert len(entries)==584 and len({e['base_tape_episode'] for e in entries})==584
    index=dict(schema_version=1,tapes=entries,counts=dict(tapes=len(entries),revised=1,
        with_associated_losses=sum(bool(e['audited_loss_associations']) for e in entries),
        milk_to_wool_review=sum(any(x['milk_to_wool_review'] for x in e['audited_loss_associations']) for e in entries)),
        semantics='Original tapes remain unchanged. Variants are separate revisions with observable scenario conditions and evidence status. This inventory does not claim all tapes have been optimized.')
    write(REGISTRY/'index.json',index)

    lines=['# Marked per-tape sequence variants','',
        'Watch the [before → after replay](../viz/tape-109740300-before-after.html): the full original game plays first, then the revised game. The replay selector preserves the current hour for direct comparison; shortcuts highlight D17, D19, D21 and the D23 retirement guard. Both exported 720-state replays reproduce the frozen experiment\'s actions, cash ledgers and harvest totals. Build with `scripts/build_tape_variant_replays.py`; browser checks are in `scripts/check_tape_variant_replays.cjs`.','',
        'Start with a small revision to one existing sequence and keep its identity, applicability and measured outcome. The original UMG tapes and mgt_m1 remain unchanged. The register includes all 584 original tapes; one has an experimental revision. Every other tape is explicitly marked unmodified.','',
        '## First revision: 109740300-milk-care-to-wool-v1','',
        'This donor came from a world with no Yarn Store. In the diagnosed m1 loss 111678108, the actual world revealed two; m1 harvested 90 wool versus 155 for its opponent. It harvested 69 of its 116 milk while the milk quote was at most 40 (59 milk units were actually sold at those low prices). This is a scenario mismatch, not a claim that the original tape is intrinsically poor.','',
        'The revision moves one worker’s existing PICKUP, COLLECT_FERTILIZER and WEST commands one hour earlier, then performs CARE on the adjacent sheep instead of the cow. Four commands change on an active day. At hour 5 the worker rejoins the original sequence; all later positions and commands match. Hires, travel, purchases and non-care work are unchanged in the compiled sequence.','',
        'It applies only to donor 109740300 with a revealed Yarn Store, milk quote ≤40 and wool quote at least 20 higher, the expected cow and sheep cohort, room in the sheep’s care bank, and a wool harvest before the donor’s D26 pasture conversion. Days are zero-based, as in the engine. The actual replay applied it on D17, D19 and D21. It rejected D15 on prices and D23 because the next harvest would conflict with retirement.','',
        '| Measurement, complete recorded-game replay | Original m1 | Revised tape | Change |',
        '|---|---:|---:|---:|',
        '| Own final cash | 87,878 | 88,192 | +314 |',
        '| Opponent final cash | 98,302 | 98,528 | +226 |',
        '| Cash margin | −10,424 | −10,336 | +88 |',
        '| Wool harvested and sold | 90 | 91 | +1 |',
        '| Milk harvested and sold | 116 | 113 | −3 |',
        '| Total spending | Same | Same | 0 |','',
        'Own wool revenue rose 230 and own milk revenue rose 84 despite lower volume: reducing supply improved later milk prices. The opponent also benefited, so own-cash improvement overstates the competitive gain. Two of the three redirected cares replaced care that the existing overlay would otherwise supply; only one was additional care overall. All other harvested product totals were unchanged. The final action stream changed at 38 steps because subsequent overlay work and sales responded to the 12 edited tape commands.','',
        '**Mark: diagnostic improvement; broader validation pending.** This is the discovery case with recorded opponent commands and recorded shops. It demonstrates a small feasible improvement in this scenario, not a general win-rate or rating improvement. Three other-donor full-game controls reproduced identical actions and cash. All eight baseline/candidate executions completed with reconciled cash ledgers, no policy fallbacks and no own action over one second. The prior wool-forecast change was not combined into this experiment.','',
        '## Register and next revisions','',
        f"The register links {index['counts']['with_associated_losses']} tapes to final-donor associations from the 89 audited losses. {index['counts']['milk_to_wool_review']} tapes have a milk-glut/wool-shortage review flag. These are candidates for inspection: they are not automatically marked bad, and missing flags do not imply a good tape.",'',
        'Each revision records its base tape and hashes, production change, exact command edits, observable activation conditions, retirement boundary, paired cash/output changes, scope controls and evidence status. Failed revisions and regressions should stay in the register. Promotion requires applicable tests with a responsive opponent; inactive controls cannot establish effectiveness.','',
        'Artifacts: [all-tape register](../data/tape_variants/index.json), [marked revision](../data/tape_variants/109740300-milk-care-to-wool-v1.json), [candidate](../agents/mgt_tape_care_v1.py), [paired results](../results/fresh/tape_variants_20260922/summary.json), [frozen design](../results/fresh/tape_variants_20260922/design.json).','',
        'Reproduce with scripts/experiment_tape_variants.py freeze, then historical --workers 3, then scripts/report_tape_variants.py. The project’s bundled Python fallback uses the existing engine 1.32.7; no dependencies changed.','']
    (ROOT/'docs/tape_sequence_variants.md').write_text('\n'.join(lines),encoding='utf8')
    print(json.dumps(dict(counts=index['counts'],status=status,results=pairs),indent=2))


if __name__=='__main__':
    report()
