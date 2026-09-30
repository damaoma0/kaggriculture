"""Contract checks for the experimental crop-replacement guard, without agent imports."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
namespace={}
exec(compile((ROOT/'scripts/fragments/tape_calendar.py').read_text(),'<calendar>','exec'),namespace)
exec(compile((ROOT/'scripts/fragments/mgt_replacement_guard.py').read_text(),'<guard>','exec'),namespace)


def tape():
    t=[{'farmer':['PASS']} for _ in range(72)]
    t[48]={'farmer':['WEST']}
    t[49]={'farmer':['DIG']}
    t[50]={'farmer':['PLANT','WHEAT']}
    return t


def main():
    calendar=namespace['_shp_replacement_calendar']
    t=tape()
    assert calendar({},t,0)=={(3,4):50}
    t[49]={'farmer':['PASS']}
    assert calendar({},t,0)=={}, 'Plant alone is not explicit retirement'
    t=tape();t[24]={'farmer':['WEST']};t[25]={'farmer':['FEED']}
    assert calendar({},t,0)=={}, 'Do not contradict native feed before conversion'
    t=tape();t[50]={'farmer':['PASS']}
    assert calendar({},t,0)=={}, 'Dig alone is not enough'
    t=tape()
    board=[[{} for _ in range(10)] for _ in range(10)]
    board[4][3]={'animal':'SHEEP','yield_units':3}
    obs={'player':0,'farms':[{'tiles':board}],'market':{'prices':{'WOOL':100}}}
    namespace['_SHP_ANIMALS']={'SHEEP':('WOOL',6,3)}
    counts={}
    namespace['_shp_count']=lambda k:counts.update({k:counts.get(k,0)+1})
    original=[(900,(3,4),{'FEED','CARE','HARVEST'}),(200,(6,6),{'FEED'})]
    namespace['_shp_topups_before_replacement']=lambda *args:original
    state={'orphans':[(3,4),(6,6)],'rescue_pinned':[(3,4),(6,6)]}
    result=namespace['_shp_topups'](state,obs,t,0)
    assert result==[(300,(3,4),{'HARVEST'}),(200,(6,6),{'FEED'})]
    assert state['rescue_pinned']==[(6,6)] and state['orphans']==[(6,6)]
    assert original[0][2]=={'FEED','CARE','HARVEST'}, 'No mutation of parent rows'
    board[4][3]['yield_units']=0
    assert namespace['_shp_topups']({},obs,t,0)==[(200,(6,6),{'FEED'})]
    print('PASS: explicit conversion, native-feed veto, final-stock harvest, pin removal, no parent mutation, empty-stock suppression')


if __name__=='__main__':main()
