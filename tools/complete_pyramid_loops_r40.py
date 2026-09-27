"""Two coherent circulation links in authorised internal voids, not exterior appendages."""
import argparse,json,nbtlib
from pathlib import Path
from collections import Counter
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,WORLD,ROOT
from query_blocks import iter_block_entities,AIR
OUT=ROOT/'artifacts/world_combat_r40/pyramid_loops'
FLOOR='projectseele:nerv_floor_panel';FRAME='projectseele:nerv_structural_panel';WALL='projectseele:nerv_wall_panel';GLASS='projectseele:clear_glass'

def main(apply=False):
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();w=MeasuredWorld();w.box((-35,-452,286),(96,-370,407));w.load();tags=dict(iter_block_entities(WORLD,v.DIM,(-35,-452,286),(96,-370,407)));changes={};protected=[]
    def put(q,s,owner):
        old=w.block(q)
        if old is None:raise RuntimeError(('Unknown',q))
        if q in tags or any(k in old for k in ['one_way','elevator','button','lever','mtr:','office_chair','period_fixture']):
            if old!=s:protected.append(dict(pos=q,before=old,desired=s))
            return
        changes[q]=(s,owner)
    definitions=[dict(id='main_rear_ring',feet=-448,boxes=[(-33,399,93,405)],ports=[(-32,399,-27,399),(86,399,92,399)],purpose='Join both retained side corridors on the same main-ring floor above the lower arrival-hall roof'),
        dict(id='optical_room_lift_link',feet=-378,boxes=[(47,292,59,298),(53,292,59,311)],ports=[(47,293,47,296),(54,311,58,311),(59,307,59,310)],purpose='Second exit from the documented optical-monitoring room to the existing east-lift landing')]
    for d in definitions:
        y=d['feet'];mask={(x,z) for x0,z0,x1,z1 in d['boxes'] for x in range(x0,x1+1) for z in range(z0,z1+1)};ports={(x,z) for x0,z0,x1,z1 in d['ports'] for x in range(x0,x1+1) for z in range(z0,z1+1)}
        for x,z in sorted(mask):
            rim=any((x+dx,z+dz) not in mask for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)))
            put((x,y-2,z),FRAME,d['id']+'/bearing');put((x,y-1,z),FLOOR,d['id']+'/floor');put((x,y+5,z),FRAME,d['id']+'/ceiling')
            for Y in range(y,y+5):
                s=WALL if rim and (x,z) not in ports else 'minecraft:air'
                if s==WALL and Y==y+2:s='projectseele:nerv_wall_datum'
                put((x,Y,z),s,d['id']+'/envelope')
            if not rim and (x%8==0 and z==402 or x==56 and z%7==0):put((x,y+4,z),'projectseele:nerv_ceiling_light[hanging=true,lit=true]',d['id']+'/light')
        if d['id']=='main_rear_ring':
            for x in range(-24,83):
                for z0,direction in [(400,True),(403,False)]:
                    for dz in (0,1):put((x,y-1,z0+dz),f'mtr:escalator_step[direction={str(direction).lower()},facing=east,orientation=flat,side={"left" if dz==0 else "right"},status=true]',d['id']+'/two_way_walk')
    # Six primitive stair-block seats stood on one-metre plinths in the east
    # waiting room. They are furniture, not a staircase to another floor.
    chairs=[]
    for z in (288,294):
        for x in range(63,78):
            old=w.get(x,-447,z)
            if not old.startswith('minecraft:polished_blackstone_stairs'):continue
            assert w.get(x,-448,z)=='minecraft:polished_deepslate'
            put((x,-447,z),'minecraft:air','waiting_room/retire_stair_seats')
            put((x,-448,z),'projectseele:nerv_office_chair[facing=north]','waiting_room/chair');chairs.append([x,-448,z])
    # The optical-room label was on the wall being opened. Remount it on
    # the new fixed north wall, with a real full-width backing.
    old_label=(51,-376,294);label=(51,-376,293)
    if old_label in tags:
        changes[old_label]=('minecraft:air','optical_room/retire_old_wall_label')
        changes[label]=('projectseele:station_departure_board[facing=south,wayfinding=true]','optical_room/room_label')
        p.block_entities[label]=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(label[0]),'y':nbtlib.Int(label[1]),'z':nbtlib.Int(label[2]),'Wayfinding':nbtlib.Byte(1),'Station':nbtlib.String('光学监视室'),'Route':nbtlib.String('房间入口'),'PlatformCentre':nbtlib.Long(0),'Row0':nbtlib.String('← 光学监视室'),'Row1':nbtlib.String('本层直梯 →'),'Row2':nbtlib.String('指挥室／车站 · 经直梯 →')})
    for q,(after,owner) in sorted(changes.items()):
        old=w.block(q)
        if old!=after:p.match((*q,*q),old,after,'r40/'+owner)
    walks=[dict(id='r40/rear_ring/west_east',path=[[-29.5,-448,396.5],[-29.5,-448,402.5],[89.5,-448,402.5],[89.5,-448,396.5]]),
           dict(id='r40/optical_room/east_lift',path=[[44.5,-378,294.5],[56.5,-378,294.5],[56.5,-378,309.5],[66.5,-378,309.5]])]
    p.meta.update(circulation=definitions,walk_nodes=walks,chairs=chairs,protected=protected,command_room_layout_unchanged=True,exterior_pyramid_shape_unchanged=True)
    p.save_plan('internal_circulation_loops')
    if apply:p.apply('internal_circulation_loops')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Loop changes',len(p.ops),'chairs',len(chairs),'protected',len(protected),Counter(q['before'] for q in protected))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
