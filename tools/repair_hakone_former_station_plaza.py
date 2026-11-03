"""Support the retained P1 public plaza and join it to the present street.

P1 is retired as a railway. This repairs its later public use without recreating
old tracks, platforms, signs or transit identities. Original deck material and
the vehicle west of the plaza stay in place.
"""
import argparse,collections,json,os,shutil
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import binary_dilation
from author_hakone_lakefront import Editor
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import NATURAL,SOIL,PLANTS
from repair_hakone_funicular_civil import CIVIL
from hakone_earthworks import road_blocks
from install_r53_carrier_trays import stopped_world
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.launch_earthworks import ground
from verify_hakone_network_candidate import PAVEMENT

def run(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);x,z,X,Z=cap['bounds_xz']
    a.out.mkdir(parents=True,exist_ok=False)
    for n in ('source','delta','plan'):(a.out/n).mkdir()
    for f in (a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    with np.load(a.source/'measured.npz')as f:old=f['top']
    e=Editor(a.out);launch=load(world);masks={};owned=set()
    curves=json.loads(a.curves.read_text('utf8'));pts=np.concatenate([r['points']for r in curves['trains']]);tree=cKDTree(pts[:,[0,2]])
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');devices={p for p,t in iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z))}
    walk=np.zeros(old.shape,bool);stairs=walk.copy();grade=np.zeros(old.shape,np.int16)
    def rect(l,t,r,b,h,stair=False):
        ar=np.s_[t-z:b-z+1,l-x:r-x+1];walk[ar]=True;grade[ar]=round(h*2)
        if stair:stairs[ar]=True
    rect(471,455,553,489,80)
    rect(452,499,457,501,95.5,True)
    for px in range(458,472):rect(px,499,px,501,95.5-.5*(px-457),True)
    rect(472,497,476,501,88.5,True)
    for pz in range(496,479,-1):rect(474,pz,476,pz,88.5-.5*(497-pz),True)
    grade[499-z,452-x]=192 # existing full-block end of the street parapet
    banks=walk&~stairs&(old>=81)
    walk[banks]=False
    stairs_zone=binary_dilation(stairs)
    def put(px,py,pz,state):
        before=e.state(px,py,pz)
        if before==state:return
        existing_guard=before.split('[')[0]=='projectseele:nerv_edge_rail'
        stair_mouth=bool(stairs_zone[pz-z,px-x])
        if existing_guard and not stair_mouth and state.startswith('minecraft:iron_bars'):return
        key=px//16,pz//16
        if key not in masks:masks[key]=launch.chunk_mask(*key)
        if (px,py,pz)in devices or masks[key][py+128,pz%16,px%16]:raise ValueError(('Native device contact',px,py,pz))
        dist,idx=tree.query([px+.5,pz+.5])
        if dist<=6 and pts[idx,1]-5<=py<=pts[idx,1]+9:raise ValueError(('Native train contact',px,py,pz))
        for actor in cap['actors']:
            q=actor['pos']
            if abs(px-q[0])<6 and abs(pz-q[2])<6 and q[1]-3<=py<=q[1]+7:raise ValueError(('Original vehicle envelope',px,py,pz))
        if (px,py,pz)not in owned and not(existing_guard and stair_mouth)and before.split('[')[0]not in (CIVIL|SOIL|AIR|PLANTS|{'minecraft:light'}):raise ValueError(('Unclassified plaza contact',px,py,pz,before))
        e.put(px,py,pz,state);owned.add((px,py,pz))
    piers=[];beams=[]
    def fill(l,y,t,r,Y,b,state):
        for px in range(l,r+1):
            for pz in range(t,b+1):
                for py in range(y,Y+1):put(px,py,pz,state)
    # The old P1 track pier west of the public deck has no successor load.
    # Its full original R07 bounds are separate from the four station piers
    # that still carry this deck. Restore terrain where that obsolete pier
    # had prevented the later landscape fill.
    retired_pier=0
    for px in range(455,458):
        for pz in range(470,475):
            h=round((int(old[pz-z,454-x])+int(old[pz-z,458-x]))/2)
            for py in range(32,77):
                if e.state(px,py,pz)!='minecraft:polished_andesite':raise ValueError(('Original P1 pier source changed',px,py,pz))
                put(px,py,pz,'minecraft:air'if py>h else'minecraft:grass_block[snowy=false]'if py==h else'minecraft:dirt'if py>=h-3 else'minecraft:stone');retired_pier+=1
    for px in (475,501,527,551):
        for pz in (458,472,486):
            # Find a complete dry 3x3 footing under the corresponding beam bay.
            choices=sorted(((dx,dz)for dx in range(-3,4)for dz in range(-3,4)),key=lambda q:q[0]**2+q[1]**2);chosen=None
            for dx,dz in choices:
                Q,R=px+dx,pz+dz
                if not(472<=Q<=552 and 456<=R<=488):continue
                if all(e.state(u,y,v).split('[')[0]in CIVIL|SOIL|AIR|PLANTS for u in range(Q-1,Q+2)for v in range(R-1,R+2)for y in range(int(old[v-z,u-x])-2,78)):
                    chosen=(Q,R);break
            if chosen is None:raise ValueError(('No complete dry bearing',px,pz))
            Q,R=chosen;bottom=min(int(old[v-z,u-x])-2 for u in range(Q-1,Q+2)for v in range(R-1,R+2))
            fill(Q-1,bottom,R-1,Q+1,77,R+1,'minecraft:polished_andesite');piers.append([Q-1,bottom,R-1,Q+1,77,R+1])
            # Shifted footing remains under a full cap connected to the bay.
            fill(min(Q,px)-1,75,min(R,pz)-1,max(Q,px)+1,77,max(R,pz)+1,'minecraft:gray_concrete')
    for pz in (458,472,486):beams.append([472,75,pz-1,552,77,pz+1])
    for px in (475,501,527,551):beams.append([px-1,75,456,px+1,77,488])
    for q in beams:fill(*q,'minecraft:gray_concrete')
    for iz,ix in zip(*np.nonzero(stairs)):
        px,pz=x+int(ix),z+int(iz);f,slab=road_blocks(grade[iz,ix]);f=int(f)
        if px==452:
            # Preserve the real full/slab road level; open its guard only at
            # the new three-block pedestrian mouth.
            for py in range(f+1,f+4):put(px,py,pz,'minecraft:air')
            continue
        bottom=81 if 470<=px<=554 and 454<=pz<=490 else min(int(old[iz,ix])-1,f-2)
        for py in range(bottom,f):put(px,py,pz,'minecraft:stone_bricks')
        put(px,f,pz,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'if slab else'minecraft:smooth_stone')
        for py in range(f+1,max(f+3,int(old[iz,ix])+1)+1):put(px,py,pz,'minecraft:air')
    # Retain the original edge geometry and give the large public deck a clear
    # planted perimeter; furniture stands on the existing slab, never in air.
    bank_edge=banks&binary_dilation(walk)
    for iz,ix in zip(*np.nonzero(bank_edge)):
        for py in range(80,int(old[iz,ix])):put(x+int(ix),py,z+int(iz),'minecraft:stone_bricks')
    furniture=[]
    for cx,cz in ((488,458),(512,458),(540,458),(512,486),(540,486)):
        for px in range(cx-2,cx+3):
            for pz in range(cz-1,cz+2):
                walk[pz-z,px-x]=False
                put(px,81,pz,'minecraft:stone_bricks'if abs(px-cx)==2 or abs(pz-cz)==1 else'minecraft:dirt')
                if abs(px-cx)<2 and pz==cz:put(px,82,pz,'minecraft:oak_leaves[distance=1,persistent=true,waterlogged=false]')
        furniture.append([cx,cz])
    for cx,cz,face in ((499,457,'south'),(525,457,'south'),(525,487,'north')):
        for px in range(cx-1,cx+2):
            walk[cz-z,px-x]=False;put(px,81,cz,f'minecraft:oak_stairs[facing={face},half=bottom,shape=straight,waterlogged=false]')
    edges=binary_dilation(walk)&~walk
    for iz,ix in zip(*np.nonzero(edges)):
        px,pz=x+int(ix),z+int(iz)
        outer=(px in(470,554)and 454<=pz<=490)or(pz in(454,490)and 470<=px<=554)
        stair_edge=any(stairs[j,i]for j,i in ((iz-1,ix),(iz+1,ix),(iz,ix-1),(iz,ix+1))if 0<=j<walk.shape[0]and 0<=i<walk.shape[1])
        if not(outer or stair_edge)or px<=453:continue
        levels=[int(grade[j,i])for j,i in ((iz-1,ix),(iz+1,ix),(iz,ix-1),(iz,ix+1))if 0<=j<walk.shape[0]and 0<=i<walk.shape[1]and walk[j,i]]
        h=max(levels)//2
        # At a stair/deck intersection, do not fence off the deck mouth.
        if any(abs(int(g)-2*h)>2 for g in levels):continue
        base=80 if 470<=px<=554 and 454<=pz<=490 else min(h,int(old[iz,ix]))
        for py in range(base,h+1):put(px,py,pz,'minecraft:stone_bricks')
        along_x=walk[max(0,iz-1),ix]or walk[min(walk.shape[0]-1,iz+1),ix]
        put(px,h+1,pz,'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]'if along_x else'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]')
    regions=e.save();check=Editor(a.out);errors=[];seen={(452-x,500-z)};queue=collections.deque(seen)
    while queue:
        ix,iz=queue.popleft()
        for i,j in ((ix-1,iz),(ix+1,iz),(ix,iz-1),(ix,iz+1)):
            if 0<=i<walk.shape[1]and 0<=j<walk.shape[0]and walk[j,i]and(i,j)not in seen and abs(int(grade[j,i])-int(grade[iz,ix]))<=1:seen.add((i,j));queue.append((i,j))
    if len(seen)!=int(walk.sum()):errors.append(['disconnected-public-columns',int(walk.sum())-len(seen)])
    for iz,ix in zip(*np.nonzero(walk)):
        px,pz=x+int(ix),z+int(iz);f,slab=road_blocks(grade[iz,ix]);f=int(f)
        if check.state(px,f,pz).split('[')[0]not in PAVEMENT:errors.append(['missing-public-floor',px,f,pz])
        for py in range(f+1,f+4):
            if check.state(px,py,pz).split('[')[0]not in AIR:errors.append(['public-headroom',px,py,pz])
    for q in piers+beams:
        if any(check.state(px,py,pz).split('[')[0]in AIR for px in range(q[0],q[3]+1)for py in range(q[1],q[4]+1)for pz in range(q[2],q[5]+1)):errors.append(['incomplete-load-path',q])
    actual=ground(Editor(a.out),cap['bounds_xz']);empty=np.zeros(old.shape,bool)
    np.savez_compressed(a.out/'plan/network.npz',bounds=cap['bounds_xz'],ground=actual,old_ground=old,walk=walk,road=empty,grade2=grade,tunnel=empty,marking=empty)
    report=dict(errors=errors,public_columns=int(walk.sum()),reachable_columns=len(seen),door_and_street_contacts=[[452,500],[500,472]],public_space_id='former-P1-supported-public-plaza',retained_bank_columns=int(banks.sum()),piers=piers,beams=beams,planters=furniture,retired_disconnected_track_pier_cells=retired_pier,retired_station_recreated=False,actors_changed=0,visual_verified=False)
    for name,value in [('manifest.json',dict(world=str(world),bounds_xz=cap['bounds_xz'],regions=regions,cells=sum(r['cells']for r in regions),world_written=False,progress_files_written=[])),('functional-check.json',report),('launch-protection.json',check_candidate(launch,a.out))]:(a.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k not in ('piers','beams')}),flush=True)
    if errors:raise ValueError('Plaza verification failed')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','out','curves'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
