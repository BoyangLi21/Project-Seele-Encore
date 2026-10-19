"""Join guards on the twelve authored R04/R06 pyramid stair flights.

Only the existing iron guards are replaced. The three-wide treads, stair
landings and structural stringers below stay intact.
"""
import argparse,gzip,json
from pathlib import Path
from query_blocks import read_box,iter_block_entities
from repair_r53_reported_landings import apply,DIM

def plan(world,out,all_floors=False):
    rows=[]
    for floor in (range(-541,-457,14) if all_floors else (-541,)):
        for centre,z0,start,step,face in ((64,364,floor,-1,'north'),(69,357,floor+7,1,'south')):
            cells=read_box(world,DIM,(centre-2,start,z0-7),(centre+2,start+9,z0+7))
            tags=dict(iter_block_entities(world,DIM,(centre-2,start,z0-7),(centre+2,start+9,z0+7)))
            for i in range(7):
                z=z0+step*i;y=start+i
                for x in range(centre-1,centre+2):
                    assert cells[x,y,z].startswith('minecraft:polished_andesite_stairs['),('Original tread changed',(x,y,z),cells[x,y,z])
                for x in (centre-2,centre+2):
                    side=('right' if x<centre else 'left') if face=='north' else ('left' if x<centre else 'right')
                    for q,expected,after in (
                        ((x,y+1,z),'minecraft:iron_bars[',f'mtr:escalator_side[facing={face},orientation=slope,side={side}]'),):
                        before=cells[q]
                        if before==after or before=='projectseele:nerv_floor_panel':continue
                        assert before==expected or expected.endswith('[') and before.startswith(expected),('Original R06 guard changed',q,before)
                        assert q not in tags,('Existing device',q)
                        rows.append(dict(pos=q,before=before,after=after,before_nbt=None,after_nbt=None,reason='continuous_guard_on_authored_stair_stringer'))
    out.mkdir(parents=True,exist_ok=True)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    (out/'PLAN.json').write_text(json.dumps(dict(world=str(world),changed_cells=len(rows),stair_width_preserved=3,source='R04 flights / R06 existing stringer caps and guards',all_floors=all_floors),indent=2),'utf8')
    print('Planned',len(rows),'exact guard cells')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--all-floors',action='store_true');p.add_argument('--apply',action='store_true');a=p.parse_args()
    apply(a.world,a.output) if a.apply else plan(a.world,a.output,a.all_floors)
