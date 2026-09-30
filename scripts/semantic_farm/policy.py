"""Integrated daily replanning agent, with no action-tape dependency."""
from collections import Counter
from copy import deepcopy
import time
from .common import E, PASS, asset_counts, physical_key, species, tiles, hired_cost
from .model import DecisionModel
from .layout import assign,vacant_count
from .care import existing_jobs,establishment_jobs
from .economics import reserve_plan,quantity_value,market_scenarios,input_needs,sell_orders,tile_profile
from .execution import batch,advance,idle_to_dawn


class SemanticFarm:
    def __init__(self,model_path=None,*,care=True,layout=True,planning_seconds=2.,max_workers=13):
        self.model=DecisionModel() if model_path is None else DecisionModel(model_path)
        self.care=care;self.layout=layout;self.planning_seconds=planning_seconds;self.max_workers=max_workers
        self.actions=[];self.checkpoints=[];self.at=0;self.day=-1
        self.history=[];self.stats=Counter();self.pending=None;self.next_replan=-1

    def _workers(self,obs,jobs):
        farm=obs['farms'][obs['player']]
        # A lower bound only. Test ascending headcounts in the real scheduler;
        # wages are Fibonacci, so adding the last worker is not a linear cost.
        base=max(1,len(farm['hands'])+1)
        estimated=max(base,min(self.max_workers,2+(len(jobs)+9)//10))
        return list(range(estimated,self.max_workers+1))

    def _compile(self,obs,proposal,deadline):
        original=deepcopy(obs);projected=deepcopy(obs)
        actions=[];checkpoints=[];reports=[];done=0
        quantities={s:n for s,n in proposal['quantities'].items() if n>0}
        def append(result):
            nonlocal projected,done
            actions.extend(result['actions']);checkpoints.extend(result['checkpoints']);projected=result['end']
            done+=result.get('completed',0)
        early=proposal.get('early_wheat',0)
        if obs['day']<=5 and quantities.get('STRAWBERRY',0):
            early=max(early,min(asset_counts(obs)['WHEAT'],quantities['STRAWBERRY']))
        # Releases and income are deliberately separate from establishment. They
        # cannot use seeds bought after the physical phase of the same turn.
        current_jobs,_=existing_jobs(projected,optimize=self.care,opening=obs['day']<6,early_wheat=early)
        seeds,stock=input_needs(current_jobs)
        buy_cost=sum(max(0,n-projected['private']['shed'].get(p,0))*obs['market']['prices'].get(p,0)
                     for p,n in stock.items())
        capital=sum(n*(E.CROPS[s]['seed'] if s in E.CROPS else E.ANIMALS[s]['cost']) for s,n in quantities.items())
        needs_income=projected['farms'][obs['player']]['money']<buy_cost+capital+40
        if needs_income:
            collection,_=existing_jobs(projected,optimize=self.care,opening=obs['day']<6,
                                       early_wheat=0,collect_only=True)
            # Cash bridge uses nearby animal income. Early wheat conversion is
            # kept in the same chain as planting, avoiding a second farm tour.
            if obs['day']<6:
                collection=[j for j in collection if j['cmd'][0]=='COLLECT_FERTILIZER']
                expected=sum(obs['market']['prices']['FERTILIZER'] for j in collection)
                if early and projected['farms'][obs['player']]['money']+expected<buy_cost+capital+40:
                    from .care import job_chain
                    wheat=[(pos,tile) for pos,tile in tiles(projected) if species(tile)=='WHEAT'
                        and obs['day']-tile['planted_day']>=2]
                    wheat.sort(key=lambda p:(abs(p[0][0]-4.5)+abs(p[0][1]-4.5),p[0]))
                    for pos,tile in wheat[:early]:
                        cmds=([] if tile.get('watered_today') else [['WATER']])+[['HARVEST']]
                        collection.extend(job_chain(pos,cmds,tile))
            if collection:
                success=None
                best_collection_score=float('inf')
                failures=[]
                for workers in self._workers(projected,collection):
                    result=batch(projected,collection,workers,collect=True,deadline=deadline)
                    if result['ok']:
                        score=len(result['actions'])+.2*hired_cost(0,workers-1)
                        if score<best_collection_score:success=result;best_collection_score=score
                        continue
                    failures.append(dict(workers=workers,reason=result['reason']))
                if success is None:return dict(ok=False,reason='collection_unreachable',last=result,attempts=failures)
                append(success);reports.append(dict(phase='collection',jobs=len(collection)))
        if projected['day']!=obs['day']:
            return dict(ok=False,reason='collection_consumed_day')
        # Capital reserves explicitly include current service and tomorrow's
        # wages. A failed land proposal is rejected, not silently amputated.
        current_land=len(projected['farms'][obs['player']]['unlocked_quadrants'])
        missing_space=max(0,sum(quantities.values())-vacant_count(projected)-early)
        required_land=min(4,current_land+(missing_space+24)//25)
        desired=min(proposal.get('desired_land',current_land),required_land)
        while desired>len(projected['farms'][obs['player']]['unlocked_quadrants']):
            index=len(projected['farms'][obs['player']]['unlocked_quadrants'])-1
            reserve=reserve_plan(projected,8)['reserve']
            if projected['farms'][obs['player']]['money']<E.LAND_PRICES[index]+reserve+capital+buy_cost:
                return dict(ok=False,reason='land_cash_path')
            checkpoints.append(physical_key(projected));action=dict(PASS,market=[['BUY_LAND']])
            projected,report=advance(projected,action);actions.append(action)
            if report['failures']:return dict(ok=False,reason='land_failed')
        layout_obs=deepcopy(projected);release={}
        if early:
            available=[(pos,tile) for pos,tile in tiles(projected)
                if species(tile)=='WHEAT' and obs['day']-tile['planted_day']>=2]
            available.sort(key=lambda p:(abs(p[0][0]-4.5)+abs(p[0][1]-4.5),p[0]))
            for pos,tile in available[:early]:
                release[pos]=tile
                layout_obs['farms'][obs['player']]['tiles'][pos[1]][pos[0]]=None
        try:assigned=assign(layout_obs,quantities,'service' if self.layout else 'uniform')
        except ValueError:return dict(ok=False,reason='land_capacity')
        jobs,skips=existing_jobs(projected,optimize=self.care,opening=obs['day']<6)
        for pos,tile in release.items():
            jobs=[j for j in jobs if tuple(j['tile'])!=pos]
            from .care import job_chain
            jobs.extend(job_chain(pos,[['HARVEST']],tile))
        # Establishment chains own vacated/weed cells exclusively, avoiding a
        # duplicate DIG for a spent crop selected for replacement.
        establish_positions={tuple(a['tile']) for a in assigned}
        jobs=[j for j in jobs if tuple(j['tile']) not in establish_positions]
        new,omissions=establishment_jobs(layout_obs,assigned,optimize=self.care,opening=obs['day']<6)
        for pos in establish_positions & release.keys():
            from .care import job_chain
            new=job_chain(pos,[['HARVEST']],release[pos])+new
        jobs+=new;skips+=omissions
        failures=[];success=None
        for workers in self._workers(projected,jobs):
            cash=reserve_plan(projected,workers)
            # Young opening capital is funded by the explicit collection stage;
            # retain next dawn wages rather than demand all later feed in cash.
            reserve=cash['wage_floor'] if obs['day']<6 else cash['reserve']
            result=batch(projected,jobs,workers,reserve=reserve,deadline=deadline)
            if result['ok']:success=result;break
            failures.append(dict(workers=workers,reason=result['reason']))
        if success is None:return dict(ok=False,reason='main_unreachable',attempts=failures,last=result)
        append(success)
        if projected['day']==obs['day'] and projected['hour']<(23 if obs['day']==29 else 24):
            append(idle_to_dawn(projected))
        return dict(ok=True,actions=actions,checkpoints=checkpoints,end=projected,completed=done,
                    quantities=quantities,assignments=assigned,skips=skips,workers=workers,
                    reserve=cash,reports=reports,name=proposal['name'])

    def plan(self,obs):
        started=time.perf_counter();deadline=started+self.planning_seconds
        retain=dict(name='retain_assets',quantities={},early_wheat=0,
                    desired_land=len(obs['farms'][obs['player']]['unlocked_quadrants']))
        # Compute a viable incumbent before spending the remaining time on new
        # investments. Repeated failed searches must not starve existing assets.
        incumbent=self._compile(obs,retain,min(deadline,started+.6)) if obs['day']>=6 else None
        proposals=self.model.proposals(obs,limit=3)
        counts=asset_counts(obs)
        if obs['day']>=6:
            # A bounded generative neighbor is important when the donor's
            # counts are already matched. Its profitability is explicitly tested.
            paths=market_scenarios(obs)
            free=vacant_count(obs)
            scores=[]
            for s in E.CROPS:
                if obs['day']+E.CROPS[s]['first_yield_day']>29:continue
                n=min(4,free)
                if n:
                    q={s:n};v=quantity_value(obs,q,paths)
                    if v['low']>0:scores.append((v['objective'],q))
            for _,q in sorted(scores,reverse=True,key=lambda r:r[0])[:1]:
                proposals.append(dict(name='generated_cohort',quantities=q,early_wheat=0,
                    desired_land=len(obs['farms'][obs['player']]['unlocked_quadrants'])))
            for p in proposals:p['value']=quantity_value(obs,p['quantities'],paths)
            proposals.sort(key=lambda p:-p['value']['objective'])
            proposals=[p for p in proposals if p['value']['objective']>0]
        # Finite proposal list with explicit quantity backoffs. A failed large
        # plan does not consume real capital. The fallback retains actual assets.
        options=[]
        for p in proposals:
            options.append(p)
            if obs['day']>=1:
                smaller=dict(p,quantities={s:n//2 for s,n in p['quantities'].items()},
                             name=p['name']+'-half')
                options.append(smaller)
        if obs['day']<6:options.append(retain)
        rejected=[];selected=None
        for p in options:
            if time.perf_counter()>deadline:break
            if obs['day']>=6 and sum(counts.values())+sum(p['quantities'].values())>40:
                rejected.append(dict(name=p['name'],reason='asset_capacity_guard'))
                continue
            trial=self._compile(obs,p,deadline)
            if trial['ok']:
                # New cohorts create obligations after the establishment day.
                # Check all remaining actual service days and a season-wide
                # workload envelope before admitting irreversible spending.
                if p['quantities'] and obs['day']>=6:
                    future=self.future_service(trial['end'],deadline)
                    if not future['ok']:
                        rejected.append(dict(name=p['name'],reason='future_obligations',details=future))
                        continue
                selected=trial;break
            rejected.append(dict(name=p['name'],reason=trial['reason'],details=trial.get('attempts',[]),
                                 last=trial.get('last',{}).get('reason')))
        if selected is None:
            # Immediate state-based emergency job scheduling, without returning
            # to any old tape. Try smaller service sets and cheaper crews.
            selected=incumbent if incumbent and incumbent['ok'] else self.recovery(
                obs,deadline=max(deadline,time.perf_counter()+.25))
        self.stats['plans']+=1;self.stats['rejections']+=len(rejected)
        self.stats['jobs']+=selected.get('completed',0)
        self.actions=selected['actions'];self.checkpoints=selected['checkpoints'];self.at=0
        self.day=obs['day'];self.next_replan=obs['step']+len(self.actions)
        self.history.append(dict(day=obs['day'],hour=obs['hour'],name=selected.get('name','recovery'),
            quantities=selected.get('quantities',{}),workers=selected.get('workers'),
            assignments=selected.get('assignments',[]),skips=selected.get('skips',[]),
            reserve=selected.get('reserve'),rejected=rejected,seconds=time.perf_counter()-started,
            actions=len(self.actions),cash=obs['farms'][obs['player']]['money']))

    def future_service(self,obs,deadline):
        if obs['day']>=30:return dict(ok=True)
        from collections import defaultdict
        load=Counter();visits=Counter()
        for _,tile in tiles(obs):
            if not species(tile):continue
            pr=tile_profile(tile,obs['day'])
            for day,work in pr['work'].items():
                load[day]+=sum(work.values());visits[day]+=bool(work)
        # Leave travel/logistics headroom. This conservative bound cannot prove
        # route feasibility; it filters implausible future peaks cheaply.
        if max((load[d]+5*visits[d] for d in load),default=0)>self.max_workers*18:
            return dict(ok=False,reason='future_labor_peak')
        projected=obs
        # Replay the entire remaining service commitment, including terminal
        # delivery. A two-day probe missed synchronized harvests much later.
        for _ in range(30-obs['day']):
            if time.perf_counter()>deadline:return dict(ok=False,reason='future_probe_budget')
            retained=dict(name='future_retained',quantities={},early_wheat=0,
                desired_land=len(projected['farms'][projected['player']]['unlocked_quadrants']))
            result=self._compile(projected,retained,deadline)
            if not result['ok']:return dict(ok=False,reason=result['reason'],day=projected['day'])
            projected=result['end']
        return dict(ok=True,checked_through_day=projected['day'])

    def recovery(self,obs,deadline):
        self.stats['recoveries']+=1
        jobs,_=existing_jobs(obs,optimize=True,opening=obs['day']<6)
        # Protect survival first, then production. Optional bonus losses are
        # recorded as recovery, never silently called the full-care plan.
        survival=[j for j in jobs if j['cmd'][0] in ('WATER','FEED','HARVEST','COLLECT_FERTILIZER')]
        for work in (jobs,survival):
            for workers in self._workers(obs,work):
                result=batch(obs,work,workers,deadline=deadline)
                if result['ok']:
                    if result['end']['day']==obs['day']:
                        tail=idle_to_dawn(result['end']);result['actions']+=tail['actions'];result['checkpoints']+=tail['checkpoints']
                        result['end']=tail['end']
                    result['name']='recovery_service';return result
        # Existing workers greedily service the most threatened reachable asset;
        # replan next hour. This is an explicit failure, not proof of feasibility.
        self.stats['unplanned_hours']+=1
        commands=[];farm=obs['farms'][obs['player']]
        positions=[farm['farmer'],*farm['hands']];reserved=set()
        for u,pos in enumerate(positions):
            candidates=[]
            for j in survival:
                key=tuple(j['tile']),j['cmd'][0]
                if key in reserved:continue
                distance=abs(pos[0]-j['tile'][0])+abs(pos[1]-j['tile'][1])
                priority=0 if j['cmd'][0] in ('FEED','WATER') else 1
                if j['cmd'][0]=='FEED' and obs['private']['inventories'][u].get('WHEAT',0)==0:continue
                candidates.append((priority,distance,j))
            if not candidates:commands.append(['PASS']);continue
            _,d,j=min(candidates,key=lambda r:r[:2]);reserved.add((tuple(j['tile']),j['cmd'][0]))
            if d:
                dx=j['tile'][0]-pos[0];dy=j['tile'][1]-pos[1]
                commands.append(['EAST' if dx>0 else 'WEST'] if dx else ['SOUTH' if dy>0 else 'NORTH'])
            else:commands.append(j['cmd'])
        action=dict(farmer=commands[0],hands=commands[1:],market=sell_orders(obs)[:10])
        return dict(actions=[action],checkpoints=[physical_key(obs)],name='emergency_hour',completed=0)

    def __call__(self,obs):
        mismatch=(self.at<len(self.checkpoints) and physical_key(obs)!=self.checkpoints[self.at])
        if mismatch:self.stats['state_repairs']+=1
        if obs['day']!=self.day or self.at>=len(self.actions) or mismatch:
            self.plan(obs)
        action=deepcopy(self.actions[self.at]);self.at+=1
        self.stats['calls']+=1
        return action
