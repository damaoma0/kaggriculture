"""Read-only AST/config audit of KB115LT2; no engine or gameplay calls."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'results/fresh/semantic_strategy_20260928'
CANONICAL=dict(sd_collect_at_floor=1,sd_polish=3000,sd_polish_final=1,sd_polish_xch=.2,
               sd_polish_water_c=20,sd_tier_dawn_shape='learned2',sd_tier_anim_harv_frac=.3)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(node):return ast.dump(node,include_attributes=False)
def load(p,name):
    spec=importlib.util.spec_from_file_location(name,p);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

def main():
    paths=[STUDY/'runtime/agents/mgt_lead_kb115lt.py',ROOT/'agents/mgt_lead_kb115lt2.py']
    trees=[ast.parse(p.read_text(encoding='utf-8')) for p in paths]
    defs=[{n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))} for tree in trees]
    old,new=defs;changed=sorted(k for k in old.keys()&new.keys() if dump(old[k])!=dump(new[k]))
    added=sorted(new.keys()-old.keys())
    modules=[load(p,'compatibility_kb_'+str(i)) for i,p in enumerate(paths)]
    cfg0,cfg1=[dict(m.CFG) for m in modules]
    unchanged=['_market','_sd_build','_sd_eval','_sd_eval1','_sd_pre','_sd_act','_sd_step',
               '_tier_override','_exact_retire','_own_retire','_dawn_shape','TilePlanView']
    signature_equal={name:dump(old[name].args)==dump(new[name].args)
                     for name in old.keys()&new.keys() if isinstance(old[name],ast.FunctionDef)}
    # The only _tier_cmd difference is a guarded idle-work call after its old body.
    assert all(dump(a)==dump(b) for a,b in zip(old['_tier_cmd'].body[:-1],new['_tier_cmd'].body[:-2]))
    assert dump(old['_tier_cmd'].body[-1])==dump(new['_tier_cmd'].body[-1])
    assert len(new['_tier_cmd'].body)==len(old['_tier_cmd'].body)+1
    retire=[]
    for module_defs in defs:
        blocks=[n for n in ast.walk(module_defs['_tier_pre']) if isinstance(n,ast.If)
                and 'S.get(\'_xretire\')' in ast.unparse(n.test)
                and 'sd_exact_retire' in ast.unparse(n.test)]
        assert len(blocks)==1
        retire.append(blocks[0])
    clean_new={name:dict(
        forbidden_source_names=sorted({n.id for n in ast.walk(new[name]) if isinstance(n,ast.Name)
                                       and n.id in ('_T','_TGT_EP','_DSM_DATA','_dsm_data','open','Path')}),
        calls=sorted({n.func.id for n in ast.walk(new[name]) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}))
        for name in added}
    # The canonical learned2 branch must not consult the per-episode source loader.
    current=modules[1];current.CFG.update(CANONICAL);source_calls=[]
    def denied(kind):source_calls.append(kind);raise AssertionError('Hidden source call')
    current._dsm_data=denied
    tiles=[[None for _ in range(10)] for _ in range(10)]
    for tile in (33,34,35,43,44,45,53,54):
        tiles[tile//10][tile%10]=dict(kind='PASTURE',animal='SHEEP',placed_day=0,yield_units=4)
    dawn=current._dawn_shape(18,tiles)
    assert not source_calls and dawn
    payload=dict(scope='STATIC_SOURCE_AND_PURE_FUNCTION_COMPATIBILITY_NO_GAME',
        source_files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in paths],
        changed_existing_definitions=changed,added_definitions=added,removed_definitions=sorted(old.keys()-new.keys()),
        unchanged_relevant={n:dump(old[n])==dump(new[n]) for n in unchanged},
        signatures_equal=all(signature_equal.values()),changed_signatures=[k for k,v in signature_equal.items() if not v],
        config_changes={k:dict(old=cfg0.get(k,'MISSING'),new=cfg1.get(k,'MISSING'))
                        for k in sorted(cfg0.keys()|cfg1.keys()) if cfg0.get(k,'MISSING')!=cfg1.get(k,'MISSING')},
        canonical_overrides=CANONICAL,new_function_source_audit=clean_new,
        exact_retirement_filter_ast_identical=dump(retire[0])==dump(retire[1]),
        tier_pickup_execution_prefix_ast_identical=True,learned2_poison_source_calls=source_calls,
        learned2_pure_current_board_result=dawn,
        conclusions=dict(rolling_wheat_stall_fixed=False,tier_partial_pickup_fixed=False,
                         clean_interface_new_source_read_found=False,new_retirement_bypass_found=False),
        scope_limit='Static and pure-function evidence. Enabled polish may change allocations and runtime; frozen V8 gameplay and leak counters remain necessary.',
        script_sha256=sha(Path(__file__)))
    candidates=STUDY/'candidates'
    before=candidates/'strategy_v7_blocks100_readiness';after=candidates/'strategy_v8_kb115lt2_readiness'
    if (after/'manifest.json').exists():
        m0=json.loads((before/'manifest.json').read_text());m1=json.loads((after/'manifest.json').read_text())
        changes={k:dict(old=m0['files'].get(k),new=m1['files'].get(k)) for k in sorted(m0['files'].keys()|m1['files'].keys())
                 if m0['files'].get(k)!=m1['files'].get(k)}
        recipe='results/fresh/semantic_strategy_20260928/executor_recipe_online.json'
        executor='results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py'
        config='results/fresh/semantic_strategy_20260928/candidate_config.json'
        recipes=[json.loads((p/'project'/recipe).read_text()) for p in (before,after)]
        recipe_changes={k:recipes[1].get(k) for k in recipes[0].keys()|recipes[1].keys() if recipes[0].get(k)!=recipes[1].get(k)}
        protocol=json.loads((STUDY/'protocol.json').read_text())
        holdouts={str(row['episode']) for row in protocol['development']['recorded']+protocol['qualification']['recorded']+protocol['recorded_reserve']}
        checks=dict(project_files_match=all(sha(after/'project'/p)==h for p,h in m1['files'].items()),
            harness_files_match=all(sha(after/'harness'/p)==h for p,h in m1['harness_files'].items()),
            only_executor_and_recipe_changed=set(changes)=={recipe,executor},canonical_recipe_changes=recipe_changes==CANONICAL,
            executor_is_selected_source=sha(after/'project'/executor)==sha(paths[1]),
            harness_unchanged=m0['harness_files']==m1['harness_files'],config_unchanged=sha(before/'project'/config)==sha(after/'project'/config),
            entry_unchanged=m0['entry']==m1['entry'],training_episodes_unchanged=m0['training_episodes']==m1['training_episodes'],
            model_provenance_unchanged=m0['model_training_provenance']==m1['model_training_provenance'],
            prior_manifest_link_correct=m1['derived_from']['manifest_sha256']==sha(before/'manifest.json'),
            protocol_hash_correct=m1['protocol_sha256']==sha(STUDY/'protocol.json'),
            no_reserved_training_episode_overlap=not(set(m1['training_episodes'])&holdouts))
        assert all(checks.values()),checks
        payload['frozen_candidate_audit']=dict(candidate=m1['candidate_id'],manifest_sha256=sha(after/'manifest.json'),
            prior_manifest_sha256=sha(before/'manifest.json'),checks=checks,changed_files=changes,
            recipe_changes=recipe_changes,training_episodes=len(m1['training_episodes']),reserved_episodes=len(holdouts),
            reserved_training_overlap=sorted(set(m1['training_episodes'])&holdouts),result='PASS')
    out=STUDY/'kb115lt2_compatibility_audit.json'
    out.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:payload[k] for k in ('changed_existing_definitions','added_definitions','unchanged_relevant',
        'exact_retirement_filter_ast_identical','tier_pickup_execution_prefix_ast_identical','conclusions')},indent=2))
    print(out)

if __name__=='__main__':main()
