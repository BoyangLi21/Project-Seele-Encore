"""Replace the hanging outdoor stair tail by complete flights and landings."""
import argparse,collections,json,os,shutil
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import binary_dilation
from author_hakone_lakefront import Editor
from repair_hakone_funicular_civil import CIVIL
from hakone_earthworks import road_blocks
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import NATURAL
from install_r53_carrier_trays import stopped_world
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.launch_earthworks import ground
from verify_hakone_network_candidate import PAVEMENT

def run(a):
    capture=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(capture['world']);x,z,X,Z=capture['bounds_xz']
    a.out.mkdir(parents=True,exist_ok=False)
    for name in ('source','delta','plan'):(a.out/name).mkdir()
    for p in (a.source/'source').glob('*.npz'):os.link(p,a.out/'source'/p.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    with np.load(a.source/'measured.npz')as f:old=f['top']
    walk=np.zeros(old.shape,bool);grade=np.zeros(old.shape,np.int16)
    def rect(l,t,r,b,h):
        area=np.s_[t-z:b-z+1,l-x:r-x+1]
        if np.any(walk[area]&(grade[area]!=round(h*2))):raise ValueError(('Conflicting landing',l,t,r,b,h))
        walk[area]=True;grade[area]=round(h*2)
    rect(670,776,673,778,110)
    for px in range(674,686):rect(px,776,px,778,110-.5*(px-673))
    rect(686,775,690,779,104)
    for pz in range(780,796):rect(687,pz,689,pz,104-.5*(pz-779))
    rect(687,796,691,798,96);rect(690,794,704,796,96);rect(703,789,705,793,96)
    rect(687,770,689,774,104);rect(674,769,686,771,104);rect(673,763,675,768,104);rect(670,762,672,764,104)
    e=Editor(a.out);launch=load(world);masks={}
    curves=json.loads(a.curves.read_text('utf8'));pts=np.concatenate([r['points']for r in curves['trains']if r['id'].startswith('HC')]);tree=cKDTree(pts[:,[0,2]])
    spec=json.loads(a.prior_design.read_text('utf8'));contacts=[b for b in spec['protected_volumes']if b[0]==b[3]and b[2]==b[5]and 697<=b[0]<=704 and 778<=b[2]<=789]
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');devices={p for p,t in iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z))}
    def put(px,py,pz,state,reason):
        before=e.state(px,py,pz)
        if before==state:return
        # Keep actual native thresholds, their foundations and the original
        # street surface exact. The independent walk check still requires the
        # retained floor and headroom to meet the new landing at its real level.
        if px<=670:return
        if any(q[0]<=px<=q[3]and q[1]<=py<=q[4]and q[2]<=pz<=q[5]for q in contacts):return
        key=px//16,pz//16
        if key not in masks:masks[key]=launch.chunk_mask(*key)
        if (px,py,pz)in devices or masks[key][py+128,pz%16,px%16]:raise ValueError(('Changed original device',px,py,pz))
        dist,index=tree.query([px+.5,pz+.5])
        if dist<=2.8 and pts[index,1]-1<=py<=pts[index,1]+5:raise ValueError(('Stair enters native train clearance',px,py,pz))
        if before.split('[')[0]not in (CIVIL|NATURAL|{'minecraft:light'})-{'minecraft:water'}:raise ValueError(('Unclassified stair contact',px,py,pz,before,reason))
        e.put(px,py,pz,state)
    retired=0
    for px in range(671,704):
        for pz in range(764,800):
            g=int(old[pz-z,px-x])
            for py in range(max(95,g-2),112):
                if any(q[0]<=px<=q[3]and q[1]<=py<=q[4]and q[2]<=pz<=q[5]for q in contacts):continue
                mat=e.state(px,py,pz).split('[')[0]
                if mat not in CIVIL:continue
                if px==671 and py>=110:continue # original doorway threshold and lintel
                put(px,py,pz,'minecraft:air'if py>g else'minecraft:grass_block[snowy=false]'if py==g else'minecraft:dirt','retired-hanging-stair-and-old-road');retired+=1
    for iz,ix in zip(*np.nonzero(walk)):
        px,pz=x+int(ix),z+int(iz);floor,slab=road_blocks(grade[iz,ix]);floor=int(floor);g=int(old[iz,ix])
        for py in range(min(g-1,floor-2),floor):put(px,py,pz,'minecraft:stone_bricks','continuous-stair-bearing')
        put(px,floor,pz,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'if slab else'minecraft:smooth_stone','half-step-tread')
        for py in range(floor+1,max(floor+3,g+1)+1):put(px,py,pz,'minecraft:air','public-headroom')
    # Fit a guard beside exposed edges; all three door/street mouths stay open.
    edges=binary_dilation(walk)&~walk;rails=[]
    for iz,ix in zip(*np.nonzero(edges)):
        px,pz=x+int(ix),z+int(iz)
        if px<=671 or any(abs(px-Q)+abs(pz-R)<4 for Q,R in [(670,777),(670,763),(704,789)]):continue
        neighbours=[int(grade[j,i])for j,i in [(iz-1,ix),(iz+1,ix),(iz,ix-1),(iz,ix+1)]if 0<=j<walk.shape[0]and 0<=i<walk.shape[1]and walk[j,i]]
        if not neighbours:continue
        h=min(neighbours)//2
        if h-int(old[iz,ix])<3:continue
        for py in range(int(old[iz,ix]),h+1):put(px,py,pz,'minecraft:stone_bricks','guard-bearing')
        put(px,h+1,pz,'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]'if walk[max(0,iz-1),ix]or walk[min(walk.shape[0]-1,iz+1),ix]else'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]','guardrail');rails.append([px,h+1,pz])
    regions=e.save();errors=[];goals=[(670,777),(670,763),(704,789)];seed=(goals[0][0]-x,goals[0][1]-z);seen={seed};queue=collections.deque([seed])
    while queue:
        ix,iz=queue.popleft()
        for i,j in ((ix-1,iz),(ix+1,iz),(ix,iz-1),(ix,iz+1)):
            if 0<=i<walk.shape[1]and 0<=j<walk.shape[0]and walk[j,i]and (i,j)not in seen and abs(int(grade[j,i])-int(grade[iz,ix]))<=1:seen.add((i,j));queue.append((i,j))
    if len(seen)!=int(walk.sum()):errors.append(['disconnected-stair-columns',int(walk.sum())-len(seen)])
    check=Editor(a.out)
    for iz,ix in zip(*np.nonzero(walk)):
        px,pz=x+int(ix),z+int(iz);floor,slab=road_blocks(grade[iz,ix]);floor=int(floor)
        if check.state(px,floor,pz).split('[')[0]not in PAVEMENT:errors.append(['missing-tread',px,floor,pz])
        for py in range(floor+1,floor+4):
            if check.state(px,py,pz).split('[')[0]not in AIR:errors.append(['blocked-stair-headroom',px,py,pz])
        if px>670:
            for py in range(min(int(old[iz,ix]),floor-1),floor):
                if check.state(px,py,pz).split('[')[0]in AIR:errors.append(['unsupported-stair',px,py,pz]);break
    actual=ground(Editor(a.out),capture['bounds_xz'])
    np.savez_compressed(a.out/'plan/network.npz',bounds=capture['bounds_xz'],ground=actual,old_ground=old,walk=walk,road=np.zeros(walk.shape,bool),grade2=grade,tunnel=np.zeros(walk.shape,bool),marking=np.zeros(walk.shape,bool))
    report=dict(errors=errors,public_columns=int(walk.sum()),reachable_columns=len(seen),door_and_street_contacts=goals,retired_civil_cells=retired,guardrails=len(rails),launch=check_candidate(launch,a.out),visual_verified=False)
    for name,value in [('manifest.json',dict(world=str(world),bounds_xz=capture['bounds_xz'],regions=regions,cells=sum(r['cells']for r in regions),world_written=False,progress_files_written=[])),('functional-check.json',report)]:
        (a.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k!='launch'}),flush=True)
    if errors:raise ValueError('Stair verification failed')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','out','curves','prior-design'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
