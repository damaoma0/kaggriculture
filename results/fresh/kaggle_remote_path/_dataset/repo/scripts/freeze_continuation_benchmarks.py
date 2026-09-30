"""Freeze opponents and outcome-independent panels before candidate qualification."""
from collections import defaultdict
from hashlib import sha256
import gzip
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/tape_gap_plans'
def digest(p):return sha256(Path(p).read_bytes()).hexdigest()

def main():
    dest=OUT/'promotion_protocol.json'
    if dest.exists():raise SystemExit('Protocol already frozen; do not overwrite after viewing results.')
    v56=ROOT/'data/router_refresh_20260922/v56/main.py'
    meta=json.loads((v56.parent/'kernel-metadata.json').read_text(encoding='utf-8'))
    assert meta['id']=='ahmedberatozer/kaggriculture-v56-smarter-seeds-and-fertilizer'
    # Do not use the 105 rich-state donor episodes from the current transfer
    # study as historical qualification worlds. The other compact tapes are
    # still in the old router's library; this is not called a blind corpus.
    donor_ids=set()
    for name in ('dataset_train.json','dataset_test.json'):
        data=json.loads((ROOT/'results/fresh/cumulative_planning'/name).read_text(encoding='utf-8'))
        donor_ids.update(g['episode'] for g in data['games'] if int(g['submission'])==56266758)
    groups=defaultdict(list)
    for sub in ('56266758','56266899'):
        for path in (ROOT/f'data/mg_tapes/{sub}').glob('*.json.gz'):
            with gzip.open(path,'rt',encoding='utf-8') as f:game=json.load(f)
            if game['episode'] in donor_ids:continue
            key=sha256(f"continuation-promotion-20260922:{sub}:{game['episode']}".encode()).hexdigest()
            row=dict(episode=game['episode'],seed=game['seed'],seat=game['seat'],submission=int(sub),
                     compact_path=str(path.relative_to(ROOT)),compact_sha256=digest(path),selection_hash=key)
            groups[(sub,game['seat'])].append(row)
    worlds=[]
    for sub in ('56266758','56266899'):
        for seat in (0,1):
            rows=sorted(groups[(sub,seat)],key=lambda r:r['selection_hash']);assert len(rows)>=16
            worlds.extend(rows[:16])
    obj=dict(schema_version=1,created='2026-09-22',qualification_status='NOT_RUN',candidate_ready=False,
        user_requirement='Reliably beat public V56 and win more than original UMG tapes.',
        opponent=dict(id='v56',source=meta['id'],url='https://www.kaggle.com/code/'+meta['id'],
                      path=str(v56.relative_to(ROOT)),sha256=digest(v56),notebook_title=meta['title']),
        current_baseline=dict(id='mgt_m1',path='agents/mgt_m1.py',sha256=digest(ROOT/'agents/mgt_m1.py')),
        development=dict(seeds=list(range(93021000,93021016)),seats=[0,1],qualifies_for_promotion=False),
        natural_qualification=dict(seeds=list(range(93022000,93022128)),seats=[0,1],games_per_policy=256,
            policies=['candidate','mgt_m1'],opponent='v56',shops='natural engine RNG; equal seeds may produce different shop paths',
            cluster='seed',first_shop_subgroups='Report all eight; do not pool subgroup data as independent seeds.'),
        umg_qualification=dict(worlds=worlds,games_per_policy=64,
            policies=['candidate','umg_raw','umg_opening_repaired'],opponent='v56',
            seat_rule='Every policy takes the recorded UMG seat; 16 worlds per original source version and native seat.',
            environment='Recorded shops and identical recorded own-farm weed opportunities in every paired arm; only currently revealed state enters agents.',
            original_reproduction_required=True,repair_source_and_sha_required=True,cluster='episode',
            limitation='Historical conditional control using known compact tapes, not a blind corpus or a live UMG policy. Source episodes exclude the105 rich-state donors.',
            tape_validity='Report first command/physical divergence; raw-opening failures alone never establish policy improvement.'),
        gates=dict(
            v56=dict(minimum_win_score=.60,win_score_ci95_lower_strictly_above=.50,mean_margin_ci95_lower_strictly_above=0),
            original_umg=dict(minimum_paired_win_score_gain=.05,paired_win_score_gain_ci95_lower_strictly_above=0,
                paired_margin_gain_ci95_lower_strictly_above=0,apply_separately_to=['umg_raw','umg_opening_repaired']),
            current_m1=dict(paired_win_score_gain_ci95_lower_strictly_above=0,paired_margin_gain_ci95_lower_strictly_above=0),
            validity=dict(all_games_required=True,terminal_status='DONE',cash_ledgers_reconcile=True,
                no_candidate_errors_or_timeouts=True,competition_loading_and_time_limits=True,frozen_source_hashes=True)),
        statistics=dict(win_score='win=1,tie=0.5,loss=0',bootstrap_draws=10000,bootstrap_seed=20260922,
            confidence='Two-sided95percent percentile intervals; resample complete world clusters, preserve all paired arms/seats.',
            no_optional_stopping=True,no_tuning_on_qualification_results=True),
        stress=dict(ordered_first_two_shop_pairs=64,seats=[0,1],natural_win_rate_pooling=False,
            report=['late reveals','repeated shops','absent-demand products','first unavailable UMG prefix','farm-state distance','worst-decile loss','compiler job failures']),
        readiness_blockers=['Executable integrated continuation candidate not yet built.',
            'Opening-repaired UMG control implementation and hash must be frozen.',
            'Selected raw UMG worlds require full original reproduction checks and matching weed-opportunity records.',
            'Official timing validation and complete qualification panels have not run.'])
    dest.write_text(json.dumps(obj,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=obj['qualification_status'],v56_sha256=obj['opponent']['sha256'],
        natural_games_per_policy=256,historical_games_per_policy=64,historical_worlds=len(worlds)),indent=2))

if __name__=='__main__':main()
