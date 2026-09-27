"""Permanent street access outside the retractable battlefield, with the same lift/card gate."""
import argparse,json,nbtlib,shutil
from pathlib import Path
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,WORLD,ROOT
from query_blocks import iter_block_entities,AIR

OUT=ROOT/'artifacts/world_combat_r40/surface_lift'
FLOOR='projectseele:nerv_floor_panel';STRUCT='projectseele:nerv_structural_panel';WALL='projectseele:nerv_wall_panel';GLASS='projectseele:clear_glass'

def main(apply=False):
    OUT.mkdir(parents=True,exist_ok=True);v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();w=MeasuredWorld();w.box((107,71,267),(235,88,309));w.load();targets={}
    tags=dict(iter_block_entities(WORLD,v.DIM,(107,71,267),(235,88,309)))
    def put(x,y,z,s,why):
        q=x,y,z;old=w.block(q)
        if old is None:raise RuntimeError(('Unknown',q))
        if old.startswith('movingelevators:') or q in tags:raise RuntimeError(('Existing device',q,old))
        if old.startswith('mtr:') and not old.startswith(('mtr:escalator_step','mtr:escalator_side')):raise RuntimeError(('Transit conflict',q,old))
        targets[q]=(v.canonical_state(s),why)
    # Flat vestibule avoids the old security door occupying a stair tread.
    # Only fixed civil space west of x=126 is authored; native cage/landing is
    # preserved at x=127..133 / z=270..276.
    mask={(x,z) for x in range(110,126) for z in range(269,278)}
    mask|={(x,z) for x in range(110,120) for z in range(274,288)}
    mask|={(x,z) for x in range(110,233) for z in range(281,288)}
    mask|={(x,z) for x in range(220,233) for z in range(282,291)}
    ports={(125,z) for z in range(271,276)}|{(x,290) for x in range(223,230)}
    for x,z in sorted(mask):
        rim=any((x+dx,z+dz) not in mask for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)))
        put(x,73,z,STRUCT,'foundation');put(x,74,z,FLOOR,'floor');put(x,80,z,STRUCT,'roof_below_street')
        for y in range(75,80):put(x,y,z,WALL if rim and (x,z) not in ports else 'minecraft:air','envelope')
        if not rim and x%7==0 and z in (273,284):put(x,79,z,'projectseele:nerv_ceiling_light[hanging=true,lit=true]','light')
    # Full-length two-way moving walks: two cells each, with clear approaches
    # at both ends and no handrails on flat sections.
    for x in range(122,215):
        for z0,forward in [(282,True),(285,False)]:
            for dz in (0,1):put(x,74,z0+dz,f'mtr:escalator_step[direction={str(forward).lower()},facing=east,orientation=flat,side={"left" if dz==0 else "right"},status=true]','two_way_moving_walk')
    # Six-metre rise on a short wide stair, away from the road. The covered
    # portal is on the paved plot east of the combat square, not in a lane.
    for z in range(289,306):
        floor=74+max(0,min(6,z-288))
        for x in range(220,233):
            for y in range(73,floor+1):put(x,y,z,STRUCT,'stair_foundation')
            for y in range(floor+1,floor+5):put(x,y,z,WALL if x in (220,232) else 'minecraft:air','stair_clearance')
            put(x,floor+5,z,STRUCT,'stair_canopy')
            if 289<=z<=294 and 223<=x<=229:put(x,floor,z,'minecraft:smooth_quartz_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]','stair')
            elif x not in (220,232):put(x,floor,z,FLOOR,'landing')
            if x in (221,231) and z<=294:
                for y in (floor+1,floor+2):put(x,y,z,GLASS,'stair_edge')
            if x in (220,232) and z>=295:
                for y in (floor+2,floor+3):put(x,y,z,GLASS,'portal_glazing')
        if z%4==0:put(226,floor+4,z,'projectseele:nerv_ceiling_light[hanging=true,lit=true]','stair_light')
    # Public landing meets the existing paved plaza flush at Y=81.
    for x in range(220,233):
        for z in range(306,309):put(x,80,z,FLOOR,'plaza_handoff')
    # Retire the old rising railings and the old covered slit, permanently.
    for x in range(109,120):
        for z in range(269,280):
            for y in range(81,85):
                old=w.get(x,y,z)
                if old and (old.partition('[')[0] in AIR|{WALL,STRUCT,'minecraft:iron_bars','minecraft:black_concrete','minecraft:red_concrete','minecraft:gray_stained_glass'}):put(x,y,z,'minecraft:air','retire_old_surface_slit')
    # One card gate, now on the flat vestibule. Its existing visual identity
    # and destination permissions are reused by S20SurfaceAccessGate.
    for z in range(271,276):
        for y in range(75,79):put(120,y,z,'minecraft:barrier','security_aperture')
    for x,face in [(119,'west'),(121,'east')]:
        put(120,76,270,'minecraft:black_concrete','reader_backing')
        put(x,76,270,f'minecraft:polished_blackstone_button[face=wall,facing={face},powered=false]','reader')
    boards=[((226,83,304),'south','NERV · 地下联络入口',['↑ 地下交通层 · 金字塔','职员通道 / 刷卡进入','战时入口保持开放']),
            ((113,77,277),'east','NERV · 地面联络厅',['直梯 → 地下交通层','← 地面出口 · 东侧广场','请在门旁刷职员证']),
            ((124,77,280),'south','地面出口',['→ 东侧广场','双向自动步道','地面出口在战斗区外'])]
    for q,face,title,rows in boards:
        nx,nz={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}[face]
        put(q[0]-nx,q[1],q[2]-nz,WALL,'board_backing');put(*q,f'projectseele:nerv_direction_panel[facing={face},wayfinding=true]','board')
        tag=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Wayfinding':nbtlib.Byte(1),'Station':nbtlib.String(title),'Route':nbtlib.String('NERV'),'PlatformCentre':nbtlib.Long(0)})
        for i,t in enumerate(rows):tag['Row'+str(i)]=nbtlib.String(t)
        p.block_entities[q]=tag
    for q,(after,why) in sorted(targets.items()):
        old=w.block(q)
        if old!=after:p.match((*q,*q),old,after,'r40/surface_lift/'+why)
    plan=json.loads((WORLD/'battlefield_r21.json').read_text());retired=[];keep=[]
    for c in plan['cells']:
        (retired if 108<=c[0]<=125 and 268<=c[2]<=280 and 74<=c[1]<=90 else keep).append(c)
    plan['cells']=keep
    p.meta.update(entry=[226,81,306],lift_unchanged=[130,75,273],card_gate_x=120,retired_battlefield_cells=len(retired),street_plaza_measured_empty=True,
        walk_nodes=[dict(id='r40/surface_lift/entry',path=[[226.5,81,306.5],[226.5,81,295.5],[226.5,75,289.5],[226.5,75,284.5],[115.5,75,284.5],[115.5,75,273.5],[123.5,75,273.5]])])
    p.save_plan('permanent_access')
    if apply:
        shutil.copy2(WORLD/'battlefield_r21.json',OUT/'battlefield_before.json')
        p.apply('permanent_access')
        (WORLD/'battlefield_r21.json').write_text(json.dumps(plan,separators=(',',':')),encoding='utf8')
        (WORLD/'surface_lift_access_r40.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Access changes',len(p.ops),'retired emergency-cover cells',len(retired))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
