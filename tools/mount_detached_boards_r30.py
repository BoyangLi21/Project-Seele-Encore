"""Provide real mounts for custom wayfinding boards omitted by vanilla-sign surveys."""
from pathlib import Path
import argparse,json,math
import numpy as np
from scipy.spatial import cKDTree
import regional_voxels as v
from query_blocks import read_box,AIR
from install_facility_lighting_r30 import static_ceiling

ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_FIELD_R30_REVIEW';BASE=ROOT/'run/saves/SEELE_R30_WORLD';OUT=ROOT/'artifacts/facility_r30/board_mounts'
VECTORS={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}
def main(apply):
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();groups=json.loads((OUT.parent/'global_scan/components/contact_classification.json').read_text())['groups']
    rail=np.asarray([q for c in json.loads((BASE/'native_transit_r26.json').read_text())['curves'] if c['mode']=='TRAIN' for q in c['points']]);rails=cKDTree(rail[:,[0,2]])
    points=[]
    for c in json.loads((BASE/'quality_walk_cases.json').read_text()):
        pts=c.get('path') or [c.get('start'),c.get('end')]
        if not all(q is not None for q in pts):continue
        for a,b in zip(pts,pts[1:]):
            a,b=np.asarray(a),np.asarray(b);points.extend(np.linspace(a,b,max(2,math.ceil(np.linalg.norm(b-a)/.7)+1)))
    walk=cKDTree(np.asarray(points));shapes=json.loads((WORLD/'native_collision_shapes.json').read_text());decisions=[];held=[];planned={}
    for g in groups:
        if g['kind']!='isolated_structure' or not any('station_departure_board' in s for s in g['states']):continue
        lo,hi=g['lo'],g['hi'];b=read_box(WORLD,v.DIM,(lo[0]-3,lo[1]-5,lo[2]-3),(hi[0]+3,hi[1]+24,hi[2]+3))
        q=next(q for q,s in b.items() if 'station_departure_board' in s);x,y,z=q;state=b[q];facing=state.split('facing=')[1].split(',')[0].split(']')[0];dx,dz=VECTORS[facing]
        roof=next((Y for Y in range(y+2,y+25) if static_ceiling(b.get((x,Y,z),'UNKNOWN')) and 'ceiling_light' not in b.get((x,Y,z),'')),None)
        if roof is not None and all(b.get((x,Y,z)) in AIR or b.get((x,Y,z),'').startswith('minecraft:chain') for Y in range(y+1,roof)):
            for Y in range(y+1,roof):planned[x,Y,z]=(b[x,Y,z],'minecraft:chain[axis=y,waterlogged=false]')
            decisions.append({'board':q,'kind':'suspended','roof':roof});continue
        candidates=[(x-dx,z-dz,facing),(x-dz*2,z+dx*2,('south' if dx<0 else 'north') if dx else ('west' if dz<0 else 'east')),(x+dz*2,z-dx*2,('north' if dx<0 else 'south') if dx else ('east' if dz<0 else 'west'))]
        chosen=None
        for X,Z,direction in candidates:
            floor=y-3;s=b.get((X,floor,Z),'UNKNOWN');boxes=shapes.get(s,[])
            # A gap in historical walking samples does not make the native
            # train boarding apron a valid column site.
            if 'station_tactile_' in s:continue
            if any(b.get((X+dx2,floor,Z+dz2),'').startswith('mtr:platform[') for dx2,dz2 in ((1,0),(-1,0),(0,1),(0,-1))):continue
            if not any(a[0]<=.3 and a[3]>=.7 and a[2]<=.3 and a[5]>=.7 and a[4]>=.999 for a in boxes):continue
            if any(b.get((X,Y,Z)) not in AIR for Y in range(floor+1,y+1)):continue
            if walk.query([X+.5,floor+1,Z+.5])[0]<.75:continue
            # Native rail audit uses a 3m-wide swept corridor; the .25m post
            # stays at least .875m beyond it with this additional setback.
            near=rails.query_ball_point([X+.5,Z+.5],2.4)
            if any(floor+1<=rail[i,1]+6 and y+1>=rail[i,1]-.5 for i in near):continue
            chosen=(X,Z,direction);break
        if chosen is None:held.append({'board':q,'reason':'No measured free mount outside walking/rail envelope'});continue
        X,Z,direction=chosen
        for Y in range(y-2,y+1):planned[X,Y,Z]=(b[X,Y,Z],f'projectseele:nerv_sign_post[arm={str(Y==y).lower()},facing={direction}]')
        decisions.append({'board':q,'kind':'stanchion','post':[X,y-2,Z],'bracket_facing':direction})
    for q,(old,new) in planned.items():
        if old!=new:p.match((*q,*q),old,new,'r30/physical_wayfinding_mount')
    p.meta.update(mounts=decisions,held=held,existing_board_positions_and_NBT_preserved=True);p.save_plan('custom_board_mounts');print('Mounted',len(decisions),'held',len(held),held,flush=True)
    if apply:p.apply('custom_board_mounts')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
