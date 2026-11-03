"""Author a finite public garden from the current measured Gora terrain.

The cached park label locates a playable adaptation, not surveyed footprints.
Existing public street surfaces, original tags and native transit remain exact.
"""
import argparse,copy,json,os,shutil
from pathlib import Path
import nbtlib
import numpy as np
from scipy.spatial import cKDTree
from author_hakone_lakefront import Editor
from author_hakone_togendai import Station
from detail_hakone_nerv_streets import preservation_mask
from hakone_earthworks import road_blocks
from install_r53_carrier_trays import stopped_world
from map_pipeline.corridors import alignment,fit_ports
from map_pipeline.launch_earthworks import ground
from map_pipeline.launch_protection import load,check_candidate
from plan_ashi_landscape_r54 import SOIL,PLANTS
from prepare_hakone_city_cross import packed
from prepare_hakone_togendai_neighbourhood import save_json
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

EMPTY=AIR|PLANTS|{'minecraft:light'}

def author(a):
    spec=json.loads(a.design.read_text('utf8'));capture=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(capture['world'])
    assert capture['bounds_xz']==spec['bounds'] and not capture['unavailable_chunks']
    a.out.mkdir(parents=True,exist_ok=False)
    for name in ('source','delta','plan','payloads'):(a.out/name).mkdir()
    for file in (a.source/'source').glob('*.npz'):os.link(file,a.out/'source'/file.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json');shutil.copy2(a.survey/'captured-devices.dat',a.out/'captured-devices.dat')
    with stopped_world(world):shutil.copytree(world/'mtr',a.out/'preserved-native')
    with np.load(a.survey/'surface.npz')as f:old=f['old_ground'];bounds=f['bounds']
    x,z,X,Z=map(int,bounds);zz,xx=np.mgrid[z:Z+1,x:X+1];shape=old.shape
    with np.load(a.previous/'plan/network.npz')as f:
        bx,bz,_,_=map(int,f['bounds']);area=np.s_[z-bz:Z-bz+1,x-bx:X-bx+1]
        # The previous candidate may cover less than this new survey. Copy
        # the actual overlap, not an incorrectly sized NumPy slice.
        prior_walk=np.zeros(shape,bool);prior_g=np.zeros(shape,np.int16);prior_road=prior_walk.copy()
        ox,oz,oX,oZ=map(int,f['bounds']);l,t,r,b=max(x,ox),max(z,oz),min(X,oX),min(Z,oZ)
        dst=np.s_[t-z:b-z+1,l-x:r-x+1];src=np.s_[t-oz:b-oz+1,l-ox:r-ox+1]
        prior_walk[dst]=f['walk'][src];prior_g[dst]=f['grade2'][src];prior_road[dst]=f['road'][src]
    retained=prior_walk&np.logical_or.reduce([np.hypot(xx-px,zz-pz)<=6 for px,_,pz in spec['contacts']])
    walk=retained.copy();grade=np.zeros(shape,np.int16);grade[retained]=prior_g[retained]
    for path in spec['paths']:
        curve,s=alignment(path);distance,near=cKDTree(curve[:,[0,2]]).query(np.column_stack([xx.ravel(),zz.ravel()]))
        distance=distance.reshape(shape);near=near.reshape(shape);new=distance<=path['width']/2
        values=np.rint((curve[near,1]-1)*2).astype(np.int16)
        if np.any(new&walk&(abs(values-grade)>2)):raise ValueError(('Inconsistent garden junction',path['id']))
        values[new&walk]=grade[new&walk];grade[new]=values[new];walk|=new
    p=spec['pergola'];l,t,r,b=p['walk_bounds'];walk[t-z:b-z+1,l-x:r-x+1]=True;grade[t-z:b-z+1,l-x:r-x+1]=p['floor']*2
    fixed=retained.copy();fixed[t-z:b-z+1,l-x:r-x+1]=True
    for px,py,pz in spec['benches']:
        for Q in range(px-1,px+4):
            for R in range(pz-1,pz+2):
                if R==pz and px<=Q<=px+2:continue
                if retained[R-z,Q-x]:raise ValueError('Bench apron occupies retained street')
                walk[R-z,Q-x]=True;fixed[R-z,Q-x]=True;grade[R-z,Q-x]=(py-1)*2
    grade=fit_ports(walk&~fixed,grade,fixed,grade)
    d=dict(bounds=bounds,walk=walk,grade2=grade,road=prior_road&retained,marking=np.zeros(shape,bool),tunnel=np.zeros(shape,bool),ground=old.copy(),old_ground=old,retained_walk=retained,plots=np.zeros(shape,bool))
    np.savez_compressed(a.out/'plan/network.npz',**d)
    prior_spec=json.loads((a.previous/'plan/authored-design.json').read_text('utf8'))
    boxes=[]
    for box in prior_spec.get('protected_volumes',[]):
        if box[0]>X or box[3]<x or box[2]>Z or box[5]<z:continue
        boxes.append([max(x,box[0]),box[1],max(z,box[2]),min(X,box[3]),box[4],min(Z,box[5])])
    protected_spec=dict(protected_volumes=boxes,preserve_train_corridors=True,streets=[],retained_ports=[],connectivity_seed=[864,749],park_design=spec)
    save_json(a.out/'plan/authored-design.json',protected_spec)
    shutil.copy2(a.previous/'plan/native-curves.json',a.out/'plan/native-curves.json')
    for name in ('buildings.json','retained-buildings.json','footways.json','new-frontages.json'):save_json(a.out/'plan'/name,[])
    save_json(a.out/'outdoor-apron-corrections.json',[])
    e=Editor(a.out);native=preservation_mask(a.out,protected_spec);launch=load(world);masks={};owned=set()
    devices={tuple(int(t[k])for k in ('x','y','z'))for t in nbtlib.load(a.out/'captured-devices.dat')['Devices']}
    retiring=set();entrance_corrections=[]
    def put(px,py,pz,state):
        pos=(int(px),int(py),int(pz));px,py,pz=pos
        if e.state(*pos)==state:return
        key=px//16,pz//16
        if key not in masks:masks[key]=launch.chunk_mask(*key)
        if native(pos)or masks[key][py+128,pz%16,px%16]or pos in devices:raise ValueError(('Garden enters retained volume',pos))
        if retained[pz-z,px-x]:
            f,_=road_blocks(grade[pz-z,px-x])
            if f-1<=py<=f+3:raise ValueError(('Retained street changed',pos))
        if pos not in owned and pos not in retiring and e.state(*pos).split('[')[0]not in SOIL|EMPTY:
            allowed=any(all(box[k]<=pos[k]<=box[k+3]for k in range(3))for box in spec.get('entrance_earthworks',[]))
            if not allowed or e.state(*pos).split('[')[0]not in PAVEMENT|{'minecraft:iron_bars','minecraft:stone_brick_wall'}:raise ValueError(('Unowned garden cell',pos,e.state(*pos)))
            entrance_corrections.append(dict(pos=list(pos),before=e.state(*pos),after=state))
        e.put(*pos,state);owned.add(pos)
    def pad(box,floor,material='minecraft:stone_bricks'):
        l,t,r,b=box
        for px in range(l,r+1):
            for pz in range(t,b+1):
                bottom=min(int(old[pz-z,px-x]),floor)-1
                for py in range(bottom,floor):put(px,py,pz,'minecraft:stone')
                put(px,floor,pz,material)
                for py in range(floor+1,max(floor+3,int(old[pz-z,px-x])+1)+1):put(px,py,pz,'minecraft:air')
    # Retire complete, previously authored trees whose exact trunks/crowns
    # occupy the garden furniture. No partial canopy or broad forest clearing.
    previous_trees={tuple(t['base']):t for t in json.loads((a.previous/'street-details.json').read_text('utf8'))['trees']}
    retired=[]
    for base in spec.get('retire_tree_bases',[]):
        tree=previous_trees[tuple(base)];px,by,pz=base;h=by-1;height=tree['height'];species=tree['species'];cells={}
        for Y in range(h+1,h+height):cells[px,Y,pz]=f'minecraft:{species}_log[axis=y]'
        for layer in range(4):
            radius=(2 if layer<3 else 1)if species!='spruce'else(2 if layer%2==0 else 1);Y=h+height-3+layer
            for dx in range(-radius,radius+1):
                for dz in range(-radius,radius+1):
                    if abs(dx)+abs(dz)>radius+1 or(dx==0 and dz==0 and Y<h+height):continue
                    cells[px+dx,Y,pz+dz]=f'minecraft:{species}_leaves[distance=1,persistent=true,waterlogged=false]'
        for pos,state in cells.items():
            if e.state(*pos)!=state:raise ValueError(('Tree source differs from full authored crown',pos))
        retiring.update(cells)
        for pos in cells:put(*pos,'minecraft:air')
        retired.append(dict(**tree,cells=len(cells)))
    # Stone terraces fit the slope and keep full soil support underneath.
    pad(p['bounds'],p['floor'])
    for garden in spec['flower_beds']:pad(garden['bounds'],garden['floor'],'minecraft:grass_block[snowy=false]')
    basin=spec['basin'];cx,cz=basin['centre'];water=basin['water_y'];radius=basin['radius']
    pad([cx-radius-1,cz-radius-1,cx+radius+1,cz+radius+1],water-1)
    for px in range(cx-radius,cx+radius+1):
        for pz in range(cz-radius,cz+radius+1):
            if abs(px-cx)==radius or abs(pz-cz)==radius:
                put(px,water,pz,'minecraft:smooth_quartz');put(px,water+1,pz,'minecraft:quartz_slab[type=bottom,waterlogged=false]')
            else:put(px,water,pz,'minecraft:water[level=0]')
    put(cx,water-1,cz,'minecraft:sea_lantern')
    for py in range(water,water+3):put(cx,py,cz,'minecraft:quartz_pillar[axis=y]')
    put(cx,water+3,cz,'minecraft:quartz_slab[type=bottom,waterlogged=false]')
    # Formal flowers retain planting soil; edging stays outside public width.
    for garden in spec['flower_beds']:
        l,t,r,b=garden['bounds'];floor=garden['floor']
        for px in range(l,r+1):
            for pz in range(t,b+1):
                if px in (l,r)or pz in(t,b):put(px,floor+1,pz,'minecraft:stone_brick_slab[type=bottom,waterlogged=false]')
                elif (px+pz)%2==0:put(px,floor+1,pz,'minecraft:red_tulip'if px%3 else'minecraft:white_tulip')
    for j,i in np.argwhere(walk&~retained):
        px,pz=int(i+x),int(j+z);floor,slab=road_blocks(grade[j,i]);floor=int(floor)
        for py in range(min(int(old[j,i]),floor)-1,floor):put(px,py,pz,'minecraft:stone')
        put(px,floor,pz,'minecraft:stone_brick_slab[type=bottom,waterlogged=false]'if slab else'minecraft:stone_bricks')
        for py in range(floor+1,max(floor+3,int(old[j,i])+1)+1):put(px,py,pz,'minecraft:air')
    # Pergola: independent posts and a high open timber lattice, no closed box.
    l,t,r,b=p['bounds'];floor=p['floor']
    for px in (l,r):
        for pz in (t,b):
            for py in range(floor+1,floor+6):put(px,py,pz,'minecraft:dark_oak_log[axis=y]')
    for px in range(l,r+1):
        for pz in range(t,b+1):
            if px in (l,r)or pz in (t,b)or (px-l)%2==0:put(px,floor+6,pz,'minecraft:dark_oak_slab[type=bottom,waterlogged=false]')
    for px,py,pz in spec['benches']:
        for Q in range(px,px+3):
            if walk[pz-z,Q-x]:raise ValueError(('Bench on public path',Q,pz))
        pad([px-1,pz-1,px+3,pz+1],py-1)
        for Q in range(px,px+3):put(Q,py,pz,'minecraft:dark_oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
    for px,py,pz in spec['lights']:
        if walk[pz-z,px-x]:raise ValueError(('Lamp on public path',px,pz))
        pad([px,pz,px,pz],py-1)
        for Y in range(py,py+3):put(px,Y,pz,'minecraft:dark_oak_fence[east=false,north=false,south=false,waterlogged=false,west=false]')
        put(px,py+3,pz,'minecraft:lantern[hanging=false,waterlogged=false]')
    trees=[]
    for index,(px,pz)in enumerate(spec['trees']):
        floor=int(old[pz-z,px-x]);volume=[]
        for Y in range(floor+1,floor+7):
            for Q in range(px-2,px+3):
                for R in range(pz-2,pz+3):
                    if Y<=floor+3 and(Q!=px or R!=pz):continue
                    if Y==floor+6 and abs(Q-px)+abs(R-pz)>2:continue
                    volume.append((Q,Y,R))
        if any(native(pos)or e.state(*pos).split('[')[0]not in EMPTY or walk[pos[2]-z,pos[0]-x]for pos in volume):continue
        for Q,Y,R in volume:put(Q,Y,R,'minecraft:oak_log[axis=y]'if Q==px and R==pz and Y<floor+5 else'minecraft:oak_leaves[distance=1,persistent=true,waterlogged=false]')
        trees.append([px,floor,pz])
    # Keep sign placement inside the same guard, including its small support.
    class GuardedEditor:
        def state(self,*p):return e.state(*p)
        def put(self,*p):put(*p)
        def fill(self,x,y,z,X,Y,Z,state):
            for Q in range(x,X+1):
                for R in range(z,Z+1):
                    for H in range(y,Y+1):put(Q,H,R,state)
    signs=Station(GuardedEditor())
    for row in spec['signs']:signs.sign(*row['pos'],row['lines'],row['facing'])
    for row in signs.devices:row['Pos']=nbtlib.Long(packed(tuple(int(row['After'][k])for k in ('x','y','z'))))
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](signs.devices)}).save(a.out/'block-entities.dat',gzipped=True)
    patches=e.save();e.regions.clear();d['ground']=ground(Editor(a.out),bounds);np.savez_compressed(a.out/'plan/network.npz',**d)
    save_json(a.out/'garden-details.json',dict(design=spec,trees=trees,retired_complete_trees=retired,entrance_corrections=entrance_corrections,retained_public_columns=int(retained.sum()),new_public_columns=int((walk&~retained).sum())))
    save_json(a.out/'manifest.json',dict(world=str(world),bounds_xz=list(map(int,bounds)),regions=patches,cells=sum(r['cells']for r in patches),world_written=False,preserve_native_members=True,neighbourhood_verification=dict(public_columns=int(walk.sum()),parcels=0,devices=0,new_native_fixtures=0)))
    save_json(a.out/'functional-check.json',dict(errors=[],world_written=False))
    save_json(a.out/'launch-protection.json',check_candidate(launch,a.out))
    print('Prepared garden',sum(r['cells']for r in patches),'cells;',int(walk.sum()),'public columns; trees',len(trees),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','survey','previous','design','out'):p.add_argument('--'+name,type=Path,required=True)
    author(p.parse_args())
