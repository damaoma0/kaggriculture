"""Read-only saved-action prefix replay; no policy calls or changed commands."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/"scripts"))
STUDY=ROOT/"results/fresh/semantic_strategy_20260928"
def read(p):return json.loads(p.read_text(encoding="utf-8"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run():
    import psutil
    assert psutil.virtual_memory().available/2**30>=2.5,"Insufficient replay headroom"
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    from evaluate_boards import Ledger
    paths={"native":STUDY/"controls/recorded-112612822.json",
           "candidate":STUDY/"runs/strategy_v5_blocks100_finance/development/recorded/recorded-112612822.json"}
    output={"scope":"READ_ONLY_SAVED_ACTION_PREFIX_DIAGNOSTIC","through_executed_step":234,"runs":{}}
    for label,path in paths.items():
        row=read(path);case=row["case"];seat=1-case["seat"]
        actions=read(path.with_suffix(".actions.json"))
        game=json.loads(gzip.decompress((STUDY/case["file"]).read_bytes()))
        assert sha(STUDY/case["file"])==case["sha256"]
        env=make("kaggriculture",configuration={"episodeSteps":720,"actTimeout":1},info={"seed":case["seed"]})
        original_end=E._end_of_day
        def fixed_end(state,environment,day):
            original_end(state,environment,day)
            state[0].observation.town.unlocked_shops[:]=game["shops"][min(30,day+1)]
        E._end_of_day=fixed_end
        logs=[];now=-1;dawns=0;started=time.perf_counter()
        try:
            env.reset(2)
            with Ledger(E) as ledger:
                original_commit=E._commit_unit
                def commit(op,item,price,farm,private,market,shed_capacity=100):
                    selected=now==234 and ledger.seats[id(farm)]==seat and op=="BUY_ANIMAL" and item=="COW"
                    before=dict(step=now,money=farm["money"],shed=deepcopy(private["shed"]),
                        shed_units=sum(private["shed"].values()),shed_capacity=shed_capacity,unit_cost=price) if selected else None
                    ok=original_commit(op,item,price,farm,private,market,shed_capacity)
                    if selected:logs.append(dict(before=before,success=ok,after_money=farm["money"],
                        after_shed=deepcopy(private["shed"])))
                    return ok
                E._commit_unit=commit
                try:
                    for now in range(235):
                        if now%24==0:
                            day=now//24
                            for player in (0,1):
                                farm=env.state[0].observation.farms[player]
                                saved=row["diagnostics"][player][day]["current_observation"]
                                assert farm==saved["own_farm"],(label,player,day,"farm")
                                assert env.state[0].observation.market==saved["market"],(label,player,day,"market")
                                assert env.state[0].observation.town==saved["town"],(label,player,day,"town")
                                assert 3000+sum(ledger.data[player]["revenue"].values())-sum(ledger.data[player]["spend"].values())==farm["money"]
                            dawns+=1
                        env.step([deepcopy(actions[player][now]) for player in (0,1)])
                    for player in (0,1):
                        assert 3000+sum(ledger.data[player]["revenue"].values())-sum(ledger.data[player]["spend"].values())==env.state[0].observation.farms[player]["money"]
                finally:E._commit_unit=original_commit
        finally:E._end_of_day=original_end
        assert len(logs)==2,(label,logs)
        output["runs"][label]=dict(source_result_sha256=sha(path),source_actions_sha256=sha(path.with_suffix(".actions.json")),
            dawns_both_farms_markets_towns_equal=dawns,partial_ledgers_verified=True,policy_calls=0,
            original_order=actions[seat][234]["market"],purchase_units=logs,seconds=time.perf_counter()-started)
    destination=Path(__file__).with_suffix(".json")
    destination.write_text(json.dumps(output,indent=2),encoding="utf-8")
    print(json.dumps(output,indent=2))


if __name__=="__main__":run()
