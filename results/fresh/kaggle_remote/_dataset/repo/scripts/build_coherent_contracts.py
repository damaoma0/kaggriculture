"""Build compact deterministic daily execution contracts for coherent switch routing."""
from __future__ import annotations
import collections, gzip, hashlib, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/coherent_switch_20260924_01a0'
SOURCE=ROOT/'results/fresh/coherent_opening_20260924_01a0'
VENDOR=ROOT/'results/fresh/tape_margin_20260924_01a0/payload/vendor'
sys.path.insert(0,str(VENDOR));sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'));sys.path.insert(0,str(ROOT/'scripts'))
from coherent_opening_v5 import SemanticInputPolicy


def sha256_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def sha256_file(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def trace_path_index():
 paths={}
 full=SOURCE/'extraction/full'
 for row in json.loads((full/'index.json').read_text(encoding='utf-8')):
  paths[(int(row['episode']),int(row['seat']))]=full/row['path']
 extra=SOURCE/'new_sources/traces'
 for row in json.loads((extra/'index.json').read_text(encoding='utf-8')):
  paths[(int(row['episode']),int(row['seat']))]=extra/row['trace']
 return paths

KEEP={'kind','label','crop','animal','planted_day','placed_day','yield_units','watered_today','consecutive_unwatered','fertilized_until_day','max_lifespan_step','consecutive_unfed','fed_today','cared_today','fertilizer_available','pending_care_bonus','fertilized_until_day'}
def daily_tiles(farm):
 tiles=[]
 for y,row in enumerate(farm.get('tiles',[])):
  for x,t in enumerate(row):
   if t is None:continue
   if isinstance(t,str):tiles.append({'pos':[x,y],'label':t});continue
   if isinstance(t,dict):
    item={'pos':[x,y]}
    # Keep only fields needed to compare board labels, crop stages/condition, and animal state.
    item.update((k,t[k]) for k in KEEP if k in t)
    if 'kind' not in item:item['label']=str(t.get('label','UNKNOWN'))
    if len(item)>1:tiles.append(item)
   else:tiles.append({'pos':[x,y],'label':str(t)})
 return tiles

def daily_contract(trace,day):
 d=trace['daily'][day]; farm=d['farm']; private=d['private']
 return {'day':day,'cash':d['cash'],'seeds':private.get('seeds',{}),'shed':private.get('shed',{}),
         'farmer':farm.get('farmer'),'hands':farm.get('hands',[]),'tiles':daily_tiles(farm)}

def job_counts(trace,day):
 # Job rows are only successful engine-committed physical events.
 counts=collections.Counter(); jobs=collections.Counter()
 for j in trace.get('jobs',[]):
  if int(j.get('day',-1))!=day:continue
  cmd=j.get('command') or []
  if cmd:counts[str(cmd[0])]+=1
  jobs[str(j.get('job','UNKNOWN'))]+=1
 return {'successful_physical_op_counts':dict(sorted(counts.items())),
         'successful_physical_job_counts':dict(sorted(jobs.items()))}

MOVES={'NORTH','SOUTH','EAST','WEST','PASS'}
def scheduled_ops(trace,day):
 # Contract the next 24 source transitions in the day's action tape. Move and
 # pass commands are omitted; pickup and all physical work opcodes remain.
 start=day*24;stop=min(start+24,len(trace['actions']))
 counts=collections.Counter()
 for action in trace['actions'][start:stop]:
  commands=[action.get('farmer') or ['PASS'],*(action.get('hands') or [])]
  for cmd in commands:
   if cmd and cmd[0] not in MOVES:counts[str(cmd[0])]+=1
 return {'action_index_window':[start,stop],'scheduled_physical_op_counts':dict(sorted(counts.items()))}

def first_two_hire_counts(trace,day):
 fills=trace['market_success_by_order'];start=day*24
 out=[]
 for t in (start,start+1):
  hires=sum(1 for order in (fills[t] if t<len(fills) else []) if order and order[0]=='HIRE')
  out.append({'transition':t,'successful_hires':hires})
 return out

def main():
 policy=SemanticInputPolicy(bank=True)
 refs=policy.references
 assert len(refs)==144 and sorted(refs)==list(range(144)),(len(refs),min(refs),max(refs))
 pathmap=trace_path_index();contracts=[];seen=set()
 for route in range(144):
  trace=refs[route];ep=int(trace['episode']);seat=int(trace['seat']);key=(ep,seat)
  assert trace.get('team')=='DSM',key
  assert key in pathmap,key
  assert trace.get('source_sha256'),key
  assert len(trace['actions'])==719 and len(trace['market_success_by_order'])==719,key
  assert len(trace['daily'])>=31 and [int(d['day']) for d in trace['daily'][:30]]==list(range(30)),key
  srcpath=pathmap[key];trace_hash=sha256_file(srcpath)
  daily=[]
  for day in range(30):
   item=daily_contract(trace,day)
   item.update(scheduled_ops(trace,day))
   item.update(job_counts(trace,day))
   item['first_two_turn_successful_hires']=first_two_hire_counts(trace,day)
   daily.append(item)
  contracts.append({'route':route,'episode':ep,'source_seat':seat,'team':'DSM','source_kind':trace.get('source'),
                    'source_sha256':trace['source_sha256'],'trace_sha256':trace_hash,'daily':daily})
  seen.add(key)
 assert len(contracts)==144 and len(seen)==144
 # Validate every day and all expected job/hire summary fields before output.
 for c in contracts:
  assert len(c['daily'])==30 and [d['day'] for d in c['daily']]==list(range(30))
  for d in c['daily']:
   assert 'cash' in d and 'seeds' in d and 'shed' in d and 'tiles' in d
   assert 'successful_physical_op_counts' in d and len(d['first_two_turn_successful_hires'])==2
 payload={'schema_version':1,'description':'Compact route-indexed source execution contracts. Daily snapshots preserve source cash, private seeds/shed, and sparse farm tile state. Job and hire counts are successful recorded source outcomes.','route_count':len(contracts),'contracts':contracts}
 OUT.mkdir(parents=True,exist_ok=True)
 out=OUT/'contracts.json.gz'
 with out.open('wb') as raw:
  with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=9) as gz:
   gz.write(json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode('utf-8'))
 manifest={'schema_version':1,'artifact':'contracts.json.gz','artifact_sha256':sha256_file(out),'artifact_bytes':out.stat().st_size,
           'policy_reference':'scripts/coherent_opening_v5.py::SemanticInputPolicy(bank=True)','route_count':144,'routes_contiguous':True,
           'unique_episode_seat_sources':len(seen),'days_per_route':30,'validated_transition_actions_per_source':719,
           'source_hashes':{f'{c["episode"]}:{c["source_seat"]}':{'source_sha256':c['source_sha256'],'trace_sha256':c['trace_sha256'],'route':c['route']} for c in contracts},
           'validation':{'route_range':[0,143],'all_targets_team_dsm':True,'all_sources_have_30_days':True,'all_sources_have_719_actions':True,'all_sources_have_719_market_success_rows':True,'successful_physical_job_counts_from_extracted_jobs':True,'hire_counts_from_actual_successful_market_fills':True},
           'field_semantics':{'daily_snapshots':'trace.daily day 0 through 29','tiles':'sparse non-empty state; retains label/kind, crop planted day/yield/watering/fertilizer and animal placement/yield/feed/care/pasture-related fields','scheduled_physical_op_counts':'counts command opcodes other than movement/PASS from the next 24 source actions at indices day*24 through day*24+23; shorter at season end','successful_physical_op_counts':'counts of committed jobs by command opcode for source jobs with matching day','first_two_turn_successful_hires':'actual successful HIRE market fills at transition indices day*24 and day*24+1'}}
 (OUT/'contracts_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print(json.dumps({'route_count':len(contracts),'days':sum(len(c['daily']) for c in contracts),'unique_sources':len(seen),'artifact':str(out),'artifact_sha256':manifest['artifact_sha256'],'bytes':manifest['artifact_bytes'],'source_kinds':dict(collections.Counter(c['source_kind'] for c in contracts))},indent=2))
if __name__=='__main__':main()
