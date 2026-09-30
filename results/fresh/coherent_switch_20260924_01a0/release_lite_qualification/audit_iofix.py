import ast
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import types

ROOT=Path(__file__).resolve().parents[4]
AUDIT=ROOT/'results/fresh/coherent_switch_20260924_01a0/release_lite_qualification'
OLD=AUDIT/'package'
NEW=ROOT/'submissions/2026-09-24-v9lite-iofix-01a0/pkg'

def digest(p): return sha256(Path(p).read_bytes()).hexdigest()
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec); sys.modules[name]=m; spec.loader.exec_module(m); return m
def plain(x):
    if isinstance(x,dict): return {str(k):plain(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [plain(v) for v in x]
    if hasattr(x,'__dict__') and not isinstance(x,(str,int,float,bool,type(None))): return plain(vars(x))
    return x
def dump(x): return json.dumps(plain(x),sort_keys=True,separators=(',',':'),default=str)

def normalize(node):
    node=ast.fix_missing_locations(node)
    class StripRedirect(ast.NodeTransformer):
        def visit_With(self,n):
            self.generic_visit(n)
            names=[]
            for item in n.items:
                call=item.context_expr
                names.append(call.func.id if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) else None)
            if names and all(name in {'nullcontext','redirect_stdout','redirect_stderr'} for name in names):
                return n.body
            return n
    node=StripRedirect().visit(node)
    ast.fix_missing_locations(node)
    return ast.dump(node,include_attributes=False)

oldp=OLD/'scripts/research_labour_profit.py'
newp=NEW/'scripts/research_labour_profit.py'
oldsrc=oldp.read_text(encoding='utf-8'); newsrc=newp.read_text(encoding='utf-8')
oldtree=ast.parse(oldsrc); newtree=ast.parse(newsrc)
oldfunc={n.name:n for n in oldtree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
newfunc={n.name:n for n in newtree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
oldcls=next(n for n in oldtree.body if isinstance(n,ast.ClassDef) and n.name=='Simulator')
newcls=next(n for n in newtree.body if isinstance(n,ast.ClassDef) and n.name=='Simulator')
oldinit=next(n for n in oldcls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
newinit=next(n for n in newcls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
assert normalize(oldfunc['engine'])==normalize(newfunc['engine'])
assert normalize(oldinit)==normalize(newinit)
old_without=[n for n in oldtree.body if not (isinstance(n,ast.ImportFrom) and n.module=='contextlib')]
new_without=[n for n in newtree.body if not (isinstance(n,ast.ImportFrom) and n.module=='contextlib')]
assert normalize(ast.Module(body=old_without,type_ignores=[]))==normalize(ast.Module(body=new_without,type_ignores=[]))
assert newsrc.count('with nullcontext():')==2 and 'redirect_stdout' not in newsrc and 'redirect_stderr' not in newsrc

old_manifest=json.loads((OLD.parent/'manifest.json').read_text(encoding='utf-8'))
new_manifest=json.loads((NEW.parent/'MANIFEST.json').read_text(encoding='utf-8'))
archive=NEW.parent/'submission.tar.gz'
archive_sha=digest(archive)
expected_archive='372237589610a204abd156db65f865a41f9c0535744ff2cfe251e94438961c9e'
assert archive_sha==expected_archive
old_file_hashes=old_manifest['package_files']
new_files=new_manifest.get('files',new_manifest.get('package_files',{}))
changed=[]
for rel in sorted(set(old_file_hashes)|set(new_files)):
    if rel not in old_file_hashes or rel not in new_files or old_file_hashes[rel]!=new_files[rel]:
        changed.append(rel)
assert changed==['scripts/research_labour_profit.py'],changed
assert new_files.get('scripts/research_labour_profit.py')==digest(newp)

# Load both exact helper modules with the same pinned framework imports.
old_scripts=str(OLD/'scripts'); new_scripts=str(NEW/'scripts')
sys.path.insert(0,old_scripts); sys.path.insert(0,new_scripts)
Rold=load(oldp,'rlp_old_audit'); Rnew=load(newp,'rlp_new_audit')
design=json.loads((AUDIT/'design.json').read_text(encoding='utf-8'))
env_manifest=json.loads((AUDIT/'environment_manifest.json').read_text(encoding='utf-8'))
sys.path.insert(0,str(Path(env_manifest['environment']['framework_root']).parent))
sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
cases=[]
for world in (design['worlds'][0],design['worlds'][17]):
    game=dict(seed=world['seed'],seat=0,episode=0,shops=[world['shops'][:min(8,d//3)] for d in range(31)])
    a=Rold.Simulator(game); b=Rnew.Simulator(game)
    init_equal=dump(a.initial)==dump(b.initial)
    config_equal=dump(a.env.configuration)==dump(b.env.configuration)
    info_equal=dump(a.env.info)==dump(b.env.info)
    assert init_equal and config_equal and info_equal
    assert a.game==b.game
    cases.append(dict(seed=world['seed'],shops=world['shops'],initial_equal=init_equal,
        configuration_equal=config_equal,info_equal=info_equal,game_equal=True))

report=dict(passed=True,scope='non-game constructor equivalence and source/AST audit; no policy calls or full game runs',
    old_archive_sha256=old_manifest['archive_sha256'],derived_archive_sha256=archive_sha,
    changed_members=changed,old_research_helper_sha256=digest(oldp),new_research_helper_sha256=digest(newp),
    ast_engine_body_equal_after_redirect_wrapper_removal=True,
    ast_Simulator_init_equal_after_redirect_wrapper_removal=True,
    other_module_AST_equal=True,derived_helper_redirect_sites=0,
    constructor_cases=cases,
    qualification_inheritance=dict(games=384,arm='old immutable archive',paired_stats_remain_valid_for_old_archive=True,
        derived_archive_has_no_full_game_qualification=True,
        evidence='The changed RLP import/reset wrapper preserves AST bodies and exact simulator/projection state for tested cases; official loader check must validate thread/stdio behavior.'),
    limitations=['Two constructor seeds only; no full-season rollout or official threaded loader test executed here.'])
(AUDIT/'io_fix_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
md=['# Derived archive I/O fix audit','',
    f"- Derived archive SHA-256: {archive_sha}; original archive SHA-256: {old_manifest['archive_sha256']}.",
    '- Manifest/member comparison: only scripts/research_labour_profit.py changed.',
    '- AST proof: engine() and Simulator.__init__ bodies are unchanged after removing the old redirect wrapper / new nullcontext wrapper; all other module AST is equal.',
    '- Direct constructors: two qualification seeds produced identical initial state, configuration, info, and game settings.',
    '- Public-observation project_input code path is unchanged by AST/module comparison; no rollout or projection call was run in this bounded audit.',
    '- This is equivalence evidence, not a full game qualification. The 384-game results in final_audit.* apply to the original archive; the derived archive still needs the official loader/runtime checks.',
    '- No policy entrypoint was called and no full game was run.']
(AUDIT/'io_fix_audit.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('passed','changed_members','constructor_cases','derived_archive_sha256')},indent=2))
