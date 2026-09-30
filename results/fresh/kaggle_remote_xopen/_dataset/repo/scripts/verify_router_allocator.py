"""Resource and hiring constraints for cross-worker chain allocation."""
from copy import deepcopy
from evaluate_boards import ROOT,module_at

m=module_at('allocator_checks',ROOT/'agents/router_allocator.py')


def fixture(inventories):
    return {'step':224,'player':0,'farms':[{'farmer':[0,0],'hands':[[9,9]]}],
            'private':{'inventories':inventories}}


def check():
    orders={'0':[{'step':224,'target':[9,9],'action':['WATER']}],
            '1':[{'step':224,'target':[0,0],'action':['WATER']}]}
    route=[{'market':[]} for _ in range(720)]
    a=m.Scheduler();a.start=224
    a.allocate(fixture([{},{}]),orders,route)
    assert a.assignment==[1,0] and a.stats['chain_swaps']==1
    # Different carried resources forbid this otherwise attractive swap.
    a=m.Scheduler();a.start=224
    a.allocate(fixture([{'WHEAT':1},{}]),orders,route)
    assert a.assignment==[0,1] and a.stats['chain_swaps']==0
    # Future hires freeze identity even with interchangeable inventories.
    route[225]={'market':[['HIRE']]}
    a=m.Scheduler();a.start=224
    a.allocate(fixture([{},{}]),orders,route)
    assert a.assignment==[0,1]
    # Completed tasks remain completed under role swaps, preventing repeats.
    route[225]={'market':[]}
    a=m.Scheduler();a.start=224;a.completed={(0,224,False),(1,224,False)}
    a.allocate(fixture([{},{}]),orders,route)
    assert a.assignment==[0,1]
    # An impossible job at/after midnight counts as unfinished, independently
    # of accumulated lateness; normal actions each consume one turn.
    assert m.schedule_cost([{'step':239,'target':[0,0],'action':['WATER']},
                            {'step':239,'target':[0,0],'action':['HARVEST']}],[0,0],239)==(1,1)
    print('Passed inventory, hiring, completed-task and deadline checks.')


if __name__=='__main__':check()
