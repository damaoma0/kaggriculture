"""Optional count-only early labor ablation; never changes production quantities."""
from copy import deepcopy

import semantic_strategy_policy_20260928 as P


def apply_early_hands_bonus(proposals, config, current_cash=None):
    """Adjust only hands, after the baseline forecast is already constructed.

    D6--10, at most one extra hand, and no higher than the existing 14-hand cap.
    Extra wages are exposed rather than assumed funded. Future quantities retain
    the baseline forecast; actual cash is observed again at each daily replan.
    """
    result=deepcopy(proposals)
    requested=min(1,max(0,int(config.get('early_hands_bonus',0))))
    cap=min(14,int(config.get('max_hands',14)))
    adjustments=[]
    for proposal in result:
        day=int(proposal['day']);before=int(proposal['hands'])
        extra=min(requested,max(0,cap-before)) if 6<=day<=10 else 0
        after=before+extra;proposal['hands']=after
        wage_before=P._hire_cost(before);wage_after=P._hire_cost(after)
        adjustments.append(dict(day=day,before=before,after=after,bonus=extra,
                                baseline_wages=wage_before,total_wages=wage_after,
                                incremental_wages=wage_after-wage_before))
    diag=dict(enabled=bool(requested),hard_window=[6,10],hard_bonus_cap=1,hand_cap=cap,
              adjustments=adjustments,forecast_quantity_fields_unchanged=True,
              future_wages_not_reprojected_into_quantity_admission=True)
    if result:
        capital=float(result[0].get('estimated_capital_cost',0))
        diag['today']=dict(adjustments[0],estimated_capital_cost=capital,observed_cash=current_cash,
            funding_basis='cash versus capital plus wages only; excludes feed and prospective sales')
        if current_cash is not None:
            diag['today'].update(cash_covers_added_wage_only=float(current_cash)>=adjustments[0]['incremental_wages'],
                cash_gap_for_capital_and_wages=max(0.,capital+adjustments[0]['total_wages']-float(current_cash)))
    return result,diag
