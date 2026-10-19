"""Retire the four R43 under-stair pockets at their original gallery mouths."""
import argparse,copy,gzip,json,math
from pathlib import Path
from collections import Counter
import nbtlib
from query_blocks import read_box,iter_block_entities,AIR
from measure_world_r40 import properties
from station_sign_readers_r44 import NORMAL
from repair_r53_reported_landings import apply

DIM='projectseele:geofront';LEVELS=(-527,-513,-499,-485)
STRUCT='projectseele:nerv_structural_panel'

def plan(world,out):
    rows=[];reports=[]
    for y in LEVELS:
        lo=(60,y-14,330);hi=(78,y+13,370)
        cells=read_box(world,DIM,lo,hi);tags=dict(iter_block_entities(world,DIM,lo,hi));protected=set()
        # Preserve both flights, every lane, and their actual standing-body
        # volume, including the descent arriving from the floor below.
        for q,state in cells.items():
            prop=properties(state)
            if not(state.partition('[')[0].endswith('_stairs') and prop.get('half')=='bottom'):continue
            dx,dz=NORMAL[prop['facing']]
            for d,h in ((-.4,.5),(.2,1)):
                p=(q[0]+.5+d*dx,q[1]+h,q[2]+.5+d*dz)
                for X in range(math.floor(p[0]-.3),math.floor(p[0]+.3)+1):
                    for Y in range(math.floor(p[1]+.001),math.floor(p[1]+1.8)+1):
                        for Z in range(math.floor(p[2]-.3),math.floor(p[2]+.3)+1):protected.add((X,Y,Z))
            protected.add(q)
        changes=[]
        for x in range(62,73):
            for z in range(350,363):
                for Y in range(y,y+4):
                    q=(x,Y,z);s=cells[q]
                    if q in protected:continue
                    oldtag=tags.get(q)
                    if oldtag is not None:
                        assert q==(71,y+3,355) and str(oldtag['id'])=='projectseele:station_departure_board' and bool(oldtag.get('Wayfinding',False)),('Retained device',q)
                    # The pocket is retired at the gallery junction. Its
                    # underlying slab also bears the real switchback; leave
                    # that original stair-core fabric and internal void intact.
                    if x<72 and oldtag is None:continue
                    after=cells[72,Y,330] if x==72 else 'minecraft:air'
                    if s==after and oldtag is None:continue
                    assert s in AIR or s.partition('[')[0] in {STRUCT,'projectseele:nerv_floor_panel','projectseele:nerv_wall_panel','projectseele:nerv_wall_datum','projectseele:nerv_machine_edge','projectseele:clear_glass','projectseele:nerv_direction_panel'},(q,s)
                    changes.append(dict(pos=q,before=s,after=after,before_nbt=None if oldtag is None else oldtag.snbt(),after_nbt=None,reason='retire_r43_understair_pocket_from_gallery_junction'))
        rows+=changes;reports.append(dict(feet_y=y,owned_bounds=[[62,y,350],[72,y+3,362]],changed=len(changes),protected_stair_body_cells=len(protected),gallery_x73_and_both_flights_preserved=True))
    # Native review showed the new SEELE header touched the low ceiling. The
    # fixed right jamb is clear of both the access reader and elevator calls.
    old=(28,-454,316);new=(30,-455,316)
    cells=read_box(world,DIM,(27,-456,315),(31,-453,317));tags=dict(iter_block_entities(world,DIM,(27,-456,315),(31,-453,317)))
    assert str(tags[old]['id'])=='minecraft:sign' and cells[new] in AIR and new not in tags
    assert cells[30,-455,315]=='minecraft:black_concrete'
    tag=copy.deepcopy(tags[old])
    for k,v in zip(('x','y','z'),new):tag[k]=nbtlib.Int(v)
    rows+=[dict(pos=old,before=cells[old],after='minecraft:air',before_nbt=tags[old].snbt(),after_nbt=None,reason='seele_label_clear_of_low_ceiling'),dict(pos=new,before=cells[new],after=cells[old],before_nbt=None,after_nbt=tag.snbt(),reason='seele_label_fixed_side_jamb')]
    out.mkdir(parents=True,exist_ok=True)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode(),mtime=0))
    record=dict(world=str(world),source='R04 stair_core and R43 explicitly authored under-stair service vestibules; current native views vestibule-west712 and vestibule-east712',changed_cells=len(rows),pockets=reports,world_written=False)
    (out/'PLAN.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(record,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args();(apply if a.apply else plan)(a.world,a.output)
