"""Freeze the confirmed competitive candidate; never submit it automatically."""
from hashlib import sha256
import json,subprocess,sys
from audit_router_advantage import ROOT,OUT
from market_corpus import load
from evaluate_boards import observation

def main():
    summary=json.loads((OUT/'summary.json').read_text());results=summary['confirmation']['adapter']
    assert results['opponents']['sixday']['wins']>=12 and results['opponents']['sixday']['margin_delta']>0
    assert results['opponents']['pasture']['wins']==16
    source=ROOT/'agents/production_candidate.py';dest=ROOT/'agents/production_selected.py'
    frozen=json.loads((OUT/'confirmation_manifest.json').read_text())['candidate_sha256']
    assert sha256(source.read_bytes()).hexdigest()==frozen
    if dest.exists():assert dest.read_bytes()==source.read_bytes(),'Existing selected file differs'
    else:dest.write_bytes(source.read_bytes())
    replay=json.loads((OUT/'audit/replay-110000.json').read_text())
    obs=observation(replay['steps'][0],0);module=load('selected_packaging_check',dest)
    expected=module.agent(obs)
    cli=subprocess.run([sys.executable,str(dest)],input=json.dumps({'observation':obs})+'\n',capture_output=True,text=True,check=True,timeout=10)
    assert json.loads(cli.stdout)==expected
    assert [k for k,v in module.__dict__.items() if callable(v)][-1]=='agent'
    result={'selected':str(dest.relative_to(ROOT)),'sha256':frozen,'basis':'Competitive confirmation: 13/16 versus sixday; 16/16 versus pasture. Eight fresh seeds, both seats. No production-DP changes.',
      'limitations':'Local panel only; mean own cash slightly lower. Candidate improves match margins and results, not absolute-cash maximization.',
      'standalone_cli_verified':True,'research_parity_actions':2876,'submitted':False}
    (OUT/'selected_policy.json').write_text(json.dumps(result,indent=2))
    build=json.loads((OUT/'candidate_build.json').read_text());build['status']='Confirmed and frozen as agents/production_selected.py; not submitted.'
    (OUT/'candidate_build.json').write_text(json.dumps(build,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
