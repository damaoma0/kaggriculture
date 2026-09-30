"""Export exact engine replays of the frozen milk-to-wool diagnostic pair."""
import base64
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys

from experiment_tape_variants import ROOT, OUT, BASE, CANDIDATE, CASE, digest, read, write


def export(arm):
    from research_labour_profit import Simulator, engine, economic
    E=engine()
    from kaggle_environments.agent import get_last_callable
    design=read(OUT/'design.json')
    source=OUT/'sources'/f'{arm}.py'
    assert digest(source.read_bytes())==design['source_hashes'][arm]
    expected=read(OUT/'historical'/f'{arm}-{CASE}.json')
    with gzip.open(ROOT/f'data/ladder_panel/56395605/{CASE}.json.gz','rt',encoding='utf8') as f:
        game=json.load(f)
    entry=get_last_callable(source.read_text(encoding='utf8'),path=str(source))
    assert entry.__name__=='mgt_kaggle_entry'
    seat=game['seat'];actions=[None,None]
    actions[seat],actions[1-seat]=game['our_actions'],game['opp_actions']
    tile_table=[];tile_lookup={};frames=[];changed=[]
    harvested=[Counter(),Counter()];sold=[Counter(),Counter()]
    revenue=[Counter(),Counter()];spend=[Counter(),Counter()]
    cursor_work=cursor_events=0

    def tile_id(tile):
        key=json.dumps(tile,sort_keys=True,separators=(',',':'))
        if key not in tile_lookup:
            tile_lookup[key]=len(tile_table)
            tile_table.append(deepcopy(tile))
        return tile_lookup[key]

    with Simulator(game) as sim:
        def capture(state,next_actions):
            nonlocal cursor_work,cursor_events
            for w in sim.work[cursor_work:]:
                if w['cmd'][0]=='HARVEST':
                    harvested[w['seat']].update({k:v for k,v in w['delta'].items() if v>0})
            for _,s,op,item,price in sim.events[cursor_events:]:
                if op=='SELL':
                    sold[s][item]+=1;revenue[s][item]+=price
                else:
                    spend[s][op+(':'+item if item else '')]+=price
            cursor_work=len(sim.work);cursor_events=len(sim.events)
            obs=state[seat]['observation']
            farms=[]
            # Engine mutations update dictionary keys. Struct attribute caches
            # can still hold the opening value, so read live state via keys.
            for s,farm in enumerate(obs['farms']):
                farms.append(dict(money=farm['money'],units=deepcopy([farm['farmer'],*farm['hands']]),
                    board=[tile_id(t) for row in farm['tiles'] for t in row],
                    private=deepcopy(dict(state[s]['observation']['private'])),
                    action=deepcopy(next_actions[s]),harvested=dict(harvested[s]),
                    sold=dict(sold[s]),revenue=dict(revenue[s]),spend=dict(spend[s])))
            frames.append(dict(step=int(obs['step']),farms=farms,prices=deepcopy(obs['market']['prices']),
                               shops=list(obs['town']['unlocked_shops'])))

        interpreter=E.interpreter
        def live(state,env):
            action=entry(deepcopy(state[seat].observation),None)
            if action!=game['our_actions'][sim.t]:changed.append(sim.t)
            state[seat].action=action
            capture(state,[state[s].action for s in range(2)])
            return interpreter(state,env)
        E.interpreter=live
        try:
            result=sim.run(sim.initial,0,719,actions,capture=True)
        finally:
            E.interpreter=interpreter
        capture(result['state'],[None,None])
        assert len(frames)==720 and [f['step'] for f in frames]==list(range(720))
        assert result['money'][seat]==expected['cash']
        assert result['money'][1-seat]==expected['opponent_cash']
        assert [f['money'] for f in frames[-1]['farms']]==result['money']
        assert changed==expected['changed_steps']
        assert dict(harvested[seat])==expected['harvested']
        for s,econ in zip((seat,1-seat),expected['economics']):
            assert economic(result['events'],s)==econ
            assert 3000+sum(revenue[s].values())-sum(spend[s].values())==result['money'][s]
        if arm==BASE:
            assert not changed and result['money']==game['rewards']
        pack=dict(tiles=tile_table,frames=frames)
        body=json.dumps(pack,separators=(',',':')).encode()
        compressed=gzip.compress(body,mtime=0)
        label='Before · original mgt_m1' if arm==BASE else 'After · milk-to-wool care revision'
        meta=dict(id=0 if arm==BASE else 1,label=label,arm=arm,episode=CASE,seed=game['seed'],
            names=[label if s==seat else game['names'][s] for s in range(2)],seat=seat,
            rewards=result['money'],source_sha256=design['source_hashes'][arm],
            changed_steps=changed,decisions=entry.__globals__.get('_TV_REPORT',{}).get('decisions',[]),
            verified=True,packed=base64.b64encode(compressed).decode())
        destination=OUT/'replays'/('before.replay.json.gz' if arm==BASE else 'after.replay.json.gz')
        destination.parent.mkdir(parents=True,exist_ok=True)
        with gzip.open(destination,'wt',encoding='utf8') as f:
            json.dump(dict({k:v for k,v in meta.items() if k!='packed'},**pack),f,separators=(',',':'))
        return meta


def main():
    with ProcessPoolExecutor(max_workers=2,max_tasks_per_child=1) as pool:
        games=list(pool.map(export,[BASE,CANDIDATE]))
    data=dict(games=games,episode=CASE,variant='109740300-milk-care-to-wool-v1',
              method='Official engine reconstruction · identical recorded opponent commands and shop schedule · both cash ledgers verified',
              changed_days=[17,19,21],first_edit=409)
    template=(ROOT/'scripts/fragments/tape_variant_replays.html').read_text(encoding='utf8')
    payload=json.dumps(data,separators=(',',':')).replace('<','\\u003c')
    destination=ROOT/'viz/tape-109740300-before-after.html'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(template.replace('__DATA__',payload),encoding='utf8')
    write(OUT/'replays/verification.json',dict(episode=CASE,frames_each=720,
        states_before_action=True,source_hashes={g['arm']:g['source_sha256'] for g in games},
        cash={g['arm']:g['rewards'] for g in games},changed_steps=games[1]['changed_steps'],
        original_actions_exact=True,prior_experiment_reproduced=True,both_ledgers_verified=True,
        output=str(destination.relative_to(ROOT))))
    print(json.dumps(dict(path=str(destination),bytes=destination.stat().st_size,
                         rewards=[g['rewards'] for g in games],frames_each=720)))


if __name__=='__main__':
    main()
