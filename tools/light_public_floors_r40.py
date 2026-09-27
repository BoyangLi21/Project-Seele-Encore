"""Visible fixtures on measured room/corridor ceilings, outside machinery sweeps."""
import argparse,json,math
from pathlib import Path
import numpy as np
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,WORLD,ROOT
from query_blocks import AIR

OUT=ROOT/'artifacts/world_combat_r40/lighting'
NAV=ROOT/'artifacts/world_combat_r40/navigation'
LAMP='projectseele:nerv_ceiling_light[hanging=true,lit=true]'
FLOORS={'projectseele:nerv_floor_panel','projectseele:period_station_floor','minecraft:smooth_stone','minecraft:polished_andesite'}
BACKING={'projectseele:nerv_structural_panel','projectseele:nerv_wall_panel','projectseele:nerv_machine_panel','projectseele:nerv_floor_panel','minecraft:smooth_stone','minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:white_concrete','minecraft:smooth_quartz','minecraft:polished_deepslate'}

def main(apply=False):
    OUT.mkdir(parents=True,exist_ok=True);v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();placed=[];held=[]
    for area,levels in [('pyramid',[-461,-448,-434,-420,-406,-392,-378,-364]),('hangars',[-442,-394,-370,-367]),('arrival',[-466])]:
        d=np.load(NAV/area/'measured.npz');a=d['blocks'];pal=d['palette'];lo=d['lo'];hi=d['hi'];walk=d['walk'];free=d['free'];changes={}
        def get(q):
            if any(q[i]<lo[i] or q[i]>hi[i] for i in range(3)):return 'UNKNOWN'
            return changes.get(q,str(pal[a[q[1]-lo[1],q[2]-lo[2],q[0]-lo[0]]]))
        lights=np.array([('lit=false' not in s and ('nerv_strip_light' in s or 'nerv_ceiling_light' in s or s.partition('[')[0] in ('minecraft:sea_lantern','minecraft:glowstone','minecraft:shroomlight'))) for s in pal])
        points=(np.argwhere(lights[a])[:,[2,0,1]]+lo).astype(float)
        new=[]
        for Y in levels:
            yi=Y-lo[1]
            for zz,xx in np.argwhere(walk[yi]):
                x,z=int(xx+lo[0]),int(zz+lo[2]);q=x,Y,z
                if x%3 or z%3:continue
                if get((x,Y-1,z)).partition('[')[0] not in FLOORS:continue
                if area=='pyramid' and 6<=x<=53 and 262<=z<=365 and -445<=Y<=-388:continue
                if (8<=x<=16 and 249<=z<=258) or (62<=x<=70 and 298<=z<=308):continue
                if area=='hangars' and -35<=x<=95 and -294<=z<=-18 and not (Y==-367 and -224<=z<=-201):continue
                # Existing visible lamps must have a direct unobstructed path
                # to this occupied space, rather than lighting through walls.
                lit=False
                for pt in points[np.abs(points-np.array([x,Y+1,z])).sum(1)<=8]:
                    ray=np.linspace(np.array([x,Y+1,z])+.5,pt+.5,max(3,int(np.linalg.norm(pt-[x,Y+1,z])*2)))
                    if all(get(tuple(np.floor(s).astype(int))).partition('[')[0] in AIR|{'minecraft:light','projectseele:clear_glass','projectseele:nerv_ceiling_light','projectseele:nerv_strip_light','minecraft:sea_lantern'} for s in ray[1:-1]):lit=True;break
                if lit or any(abs(x-px)+abs(z-pz)+abs(Y+1-py)<=8 for px,py,pz in new):continue
                ceiling=None
                for yy in range(Y+3,min(Y+11,int(hi[1]))):
                    state=get((x,yy,z)).partition('[')[0]
                    if state in BACKING:ceiling=yy;break
                    if state not in AIR|{'minecraft:light'}:break
                if ceiling is None:held.append(dict(area=area,pos=q,reason='No supported ceiling in room height'));continue
                at=x,ceiling-1,z
                if get(at).partition('[')[0] not in AIR|{'minecraft:light'}:continue
                changes[at]=LAMP;new.append(at);placed.append(dict(area=area,floor=Y,position=at,ceiling=[x,ceiling,z]))
        # Read the latest exact states again: a previous stage may have added
        # station signs or doors since the survey. Do not overwrite them.
        w=MeasuredWorld()
        for q in changes:w.around(q,0)
        w.load()
        for q,after in changes.items():
            old=w.block(q)
            if old and old.partition('[')[0] in AIR|{'minecraft:light'}:p.match((*q,*q),old,after,'r40/visible_public_ceiling_fixture')
            else:held.append(dict(area=area,pos=q,reason='Changed since survey',actual=old))
    p.meta.update(placed=placed,held=held,command_room_switch_preserved=True,method='Exact occupied floor and ceiling; physical fixture, measured approach, bounded shadow ray')
    p.save_plan('visible_ceiling_lights')
    if apply:p.apply('visible_ceiling_lights')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Visible lights',len(p.ops),'held',len(held))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
