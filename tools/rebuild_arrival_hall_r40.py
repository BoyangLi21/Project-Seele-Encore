"""Rebuild the measured main-lift arrival concourse; keep the native shaft.

The user authorised rebuilding its dark, fragmented underground landing.
Door apertures, the fifteen-metre moving cage and existing MTR steps survive.
"""
import argparse,json,nbtlib
from collections import Counter
from pathlib import Path
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,WORLD,ROOT
from query_blocks import iter_block_entities,AIR

OUT=ROOT/'artifacts/world_combat_r40/arrival_hall'
STRUCT='projectseele:nerv_structural_panel';FLOOR='projectseele:nerv_floor_panel'
WALL='projectseele:nerv_wall_panel';GLASS='projectseele:clear_glass';LIGHT='projectseele:nerv_strip_light'

def main(apply=False):
    if (WORLD/'eva_facility_r29.json').is_file():
        raise RuntimeError('The partial R40 arrival shell is retired for this delivered layout; use rebuild_arrival_hall_r44.plan with an explicit revision output')
    v.WORLD=WORLD;v.OUT=OUT;w=MeasuredWorld();w.box((-389,-470,716),(-327,-455,746));w.load();p=v.Painter();targets={};held=[]
    bes={q:t for q,t in iter_block_entities(WORLD,v.DIM,(-389,-470,716),(-327,-455,746))}
    def put(x,y,z,state,owner):
        q=x,y,z;old=w.block(q)
        if old is None:raise RuntimeError(('Unknown',q))
        if old.startswith(('mtr:','movingelevators:')) or q in bes:
            if old!=state:held.append(dict(pos=q,state=old,reason='existing transport/device'))
            return
        if any((w.get(x,y-d,z) or '').startswith('mtr:escalator_step') for d in range(1,5)):
            state='minecraft:air'
        targets[q]=(state,owner)
    mask={(x,z) for x in range(-375,-340) for z in range(718,742)}
    mask|={(x,z) for x in range(-341,-330) for z in range(730,740)}
    ports={(x,718) for x in range(-364,-355)}|{(-331,z) for z in range(732,738)}
    ports|={(x,z) for x in range(-338,-331) for z in (730,739)}
    ports|={(x,741) for x in range(-363,-356)}
    for x,z in sorted(mask):
        rim=any((x+dx,z+dz) not in mask for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)))
        put(x,-468,z,STRUCT,'arrival/foundation');put(x,-467,z,FLOOR,'arrival/floor')
        put(x,-459,z,STRUCT,'arrival/ceiling')
        for y in range(-466,-459):
            if z==741 and -363<=x<=-357 and y<=-462:continue
            state='minecraft:air'
            if rim and (x,z) not in ports:
                state=STRUCT if y==-466 else WALL
                if -464<=y<=-462 and (x+z)%9 not in (0,1):state=GLASS
            put(x,y,z,state,'arrival/wall' if rim else 'arrival/clearance')
        if not rim and x%7 in (0,1) and z%8 in (2,3,4):put(x,-460,z,LIGHT,'arrival/fluorescent')
    # The call button's backing is a fixed jamb, five metres from the axis.
    put(-355,-465,741,'minecraft:black_concrete','arrival/call_jamb')
    put(-355,-465,740,'minecraft:polished_blackstone_button[face=wall,facing=north,powered=false]','arrival/call_button')
    # The obsolete one-cell-wide ledge terminates in the cavern west of the
    # lift. Its old top is not an additional public route.
    for x in range(-387,-375):
        for z in range(741,744):
            for y in range(-468,-459):
                q=x,y,z;old=w.block(q)
                if old.partition('[')[0] in {FLOOR,STRUCT,WALL,'minecraft:smooth_stone','minecraft:light_gray_concrete','minecraft:iron_bars','minecraft:sea_lantern'}:
                    put(*q,'minecraft:air','arrival/retire_blind_ledge')
    boards=[((-354,-463,740),'north','地下都市 · 入构厅',['大直梯 ↑ 地面 NERV 入口','← 车站 · 地下铁路','← 总部／机库 · 乘车']),
            ((-334,-463,738),'north','NERV GEOFRONT',['大直梯 · 地面入口 →','↑ 车站 · 地下铁路','请沿东侧主廊进入候车区'])]
    for q,face,title,rows in boards:
        # Compact one-cell panels sit against actual fixed walls; they do
        # not extend across a door opening or escalator landing.
        backing=(q[0],q[1],q[2]+1)
        put(*backing,WALL,'arrival/sign_backing')
        state=f'projectseele:nerv_direction_panel[facing={face},wayfinding=true]';put(*q,state,'arrival/sign')
        tag=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Wayfinding':nbtlib.Byte(1),'Station':nbtlib.String(title),'Route':nbtlib.String('GEOFRONT'),'PlatformCentre':nbtlib.Long(0)})
        for i,row in enumerate(rows):tag['Row'+str(i)]=nbtlib.String(row)
        p.block_entities[q]=tag
    for q,(after,owner) in sorted(targets.items()):
        old=w.block(q)
        if old!=after:p.match((*q,*q),old,after,'r40/'+owner)
    for q,tag in list(p.block_entities.items()):
        if q in bes:p.update_block_entity(q,w.block(q),bes[q],tag,'r40/arrival/sign_text')
    walks=[dict(id='r40/arrival/station',path=[[-360.5,-466,739.5],[-360.5,-466,735.5],[-332.5,-466,735.5],[-335.5,-466,752.5],[-335.5,-466,771.5]]),
           dict(id='r40/arrival/call',path=[[-360.5,-466,735.5],[-355.5,-466,739.5]])]
    p.meta.update(reason='Measured missing call control, unlit arrival and blind legacy ledge',walk_nodes=walks,protected_devices=held,boards=[dict(position=q,facing=f,title=t,rows=r) for q,f,t,r in boards])
    p.save_plan('concourse')
    if apply:p.apply('concourse')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8')
    print('Changes',len(p.ops),'protected mechanisms',len(held),dict(Counter(o.owner for o in p.ops)))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
