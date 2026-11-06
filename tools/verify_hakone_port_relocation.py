"""Independent saved-block, original payload and 3-D port-access checks."""
import argparse,copy,json,math
from pathlib import Path
from collections import deque,Counter
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.install.entity_moves import translated
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL
from verify_hakone_network_candidate import PAVEMENT


def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')


def verify(a):
    e=Editor(a.candidate);errors=[];counts=Counter()
    edits={tuple(r['pos']):r for r in json.loads((a.candidate/'port-civil-refinement.json').read_text('utf8'))}
    civil=PAVEMENT|{'projectseele:nerv_hazard_paving','projectseele:nerv_edge_rail'}
    with np.load(a.candidate/'current-payload.npz')as f:
        points,states,palette,delta=(f[k]for k in ('coordinates','states','palette','delta'))
    for p,k in zip(points,states):
        q=tuple(map(int,p+delta));expected=str(palette[k]);actual=e.state(*q)
        if actual!=expected:
            change=edits.get(q)
            if change is None or actual!=change['after'] or expected.split('[')[0]not in civil:
                errors.append(['current payload differs',list(q),expected,actual])
            else:counts['explicit_civil_paving_refinements']+=1
        counts['current_payload_cells_checked']+=1
    for p in json.loads((a.candidate/'dry-hull-interiors.json').read_text('utf8')):
        if e.state(*p).split('[')[0]not in AIR:errors.append(['sealed hull interior not dry',p,e.state(*p)])
        counts['dry_hull_cells_checked']+=1
    originals={tuple(map(int,r['Entity']['UUID'])):r['Entity']for r in nbtlib.load(a.components/'entities.nbt')['Records']}
    packets=nbtlib.load(a.candidate/'entity-moves.dat')['Moves'];seen=set()
    for row in packets:
        uid=tuple(map(int,row['Before']['UUID']));seen.add(uid)
        if uid not in originals or originals[uid]!=row['Before']or row['After']!=translated(originals[uid],delta):errors.append(['actor content or translation',list(uid)])
        tag=row['After'];name=str(tag['id']);px,py,pz=map(float,tag['Pos']);x,y,z=math.floor(px),math.floor(py),math.floor(pz)
        if name.startswith('superbwarfare:'):
            state=e.state(x,y-1,z).split('[')[0]
            if name.endswith('speedboat'):
                if state!='minecraft:water':errors.append(['boat is not afloat',x,y,z,state])
            elif state in AIR|{'minecraft:water'}:errors.append(['vehicle has no retained footing',name,x,y,z,state])
        counts['original_actors_checked']+=1
    if seen!=set(originals):errors.append(['original actor set changed'])
    original_devices={tuple(int(t[k])for k in ('x','y','z')):t for t in nbtlib.load(a.components/'block-entities.nbt')['BlockEntities']}
    changes=nbtlib.load(a.candidate/'block-entities.dat')['Changes'];moved={}
    for r in changes:
        if 'Before'in r:
            t=r['Before'];p=tuple(int(t[k])for k in ('x','y','z'));moved[p]=t
            if original_devices.get(p)!=t:errors.append(['original device changed',list(p)])
        if 'After'in r:
            t=r['After'];q=tuple(int(t[k])for k in ('x','y','z'));p=tuple(int(v-d)for v,d in zip(q,delta));expected=copy.deepcopy(original_devices[p])
            for k,v in zip(('x','y','z'),q):expected[k]=nbtlib.Int(v)
            if expected!=t or e.state(*q)!=e.state(*p,original=True):errors.append(['translated full device',list(q)])
            counts['full_devices_checked']+=1
    for p,t in original_devices.items():
        if p not in moved:
            if e.state(*p)!=e.state(*p,original=True):errors.append(['retained station device block changed',list(p)])
            counts['retained_station_devices_checked']+=1
    corridors=[]
    with np.load(a.candidate/'plan/port-access.npz')as f:final={k:f[k]for k in f.files}
    for path in sorted((a.candidate/'earthworks').glob('*.npz')):
        with np.load(path)as f:d={k:f[k]for k in f.files}
        x,z,X,Z=map(int,d['bounds'])
        fx,fz,fX,fZ=map(int,final['bounds']);l,t,R,B=max(x,fx),max(z,fz),min(X,fX),min(Z,fZ)
        if l<=R and t<=B:
            dst=np.s_[t-z:B-z+1,l-x:R-x+1];src=np.s_[t-fz:B-fz+1,l-fx:R-fx+1]
            mask=d['walk'][dst]&final['walk'][src]
            d['grade2'][dst][mask]=final['grade2'][src][mask]
        floor,slab=road_blocks(d['grade2']);observed=np.zeros(d['walk'].shape,np.int16)
        for j,i in np.argwhere(d['walk']):
            px,py,pz=x+int(i),int(floor[j,i]),z+int(j);s=e.state(px,py,pz)
            if s.split('[')[0]not in PAVEMENT or ('type=bottom'in s)!=bool(slab[j,i]):errors.append(['corridor floor',path.stem,px,py,pz,s])
            observed[j,i]=2*py+(1 if 'type=bottom'in s else 2)
            for yy in range(py+1,py+int(d.get('clearance',5))+1):
                if e.state(px,yy,pz).split('[')[0]not in AIR|{'minecraft:light'}:errors.append(['corridor headroom',path.stem,px,yy,pz])
            for yy in range(min(int(d['old'][j,i]),py)-1,py):
                if e.state(px,yy,pz).split('[')[0]in AIR|{'minecraft:water'}:errors.append(['corridor bearing',path.stem,px,yy,pz])
        for dz,dx in ((1,0),(0,1)):
            bad=d['walk']&np.roll(d['walk'],(-dz,-dx),(0,1))&(abs(observed-np.roll(observed,(-dz,-dx),(0,1)))>1)
            for j,i in np.argwhere(bad):errors.append(['full-width step',path.stem,x+int(i),z+int(j)])
        corridors.append(dict(id=path.stem,columns=int(d['walk'].sum())))
    # Two-block standing volumes and half-block surface heights form a 3-D
    # graph. A plan-view overlap alone cannot connect a quay to a higher yard.
    nodes={};lo,hi=-96,-50
    for rx in range(3040//512,3359//512+1):
        for rz in range(944//512,1247//512+1):
            r=e.region(rx*512,rz*512);names=r['names'];bare=[s.split('[')[0]for s in names]
            empty=np.array([s in AIR|{'minecraft:light'}for s in bare]);floor_ok=np.array([s in PAVEMENT|SOIL or s.endswith('_slab')or s.endswith('_stairs')for s in bare])
            half=np.array(['type=bottom'in s for s in names]);stair=np.array([s.endswith('_stairs')for s in bare])
            for(cx,cz),v in zip(r['coords'],r['after']):
                px,pz=int(cx)*16,int(cz)*16
                if not(3040<=px<=3359 and 944<=pz<=1247):continue
                f=v[lo+128:hi+129];ok=floor_ok[f]&empty[v[lo+129:hi+130]]&empty[v[lo+130:hi+131]]
                for iy,iz,ix in zip(*np.nonzero(ok)):
                    state=f[iy,iz,ix];height=2*(int(iy)+lo)+(1 if half[state]else 2);nodes[(px+int(ix),height,pz+int(iz))]=bool(stair[state])
    start=(3064,-150,1070)
    if start not in nodes:errors.append(['port graph seed absent'])
    seen={start}if start in nodes else set();queue=deque(seen)
    while queue:
        x,h,z=queue.popleft()
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            for dh in (-2,-1,0,1,2):
                p=x+dx,h+dh,z+dz
                if p in seen or p not in nodes or(abs(dh)==2 and not(nodes[p]or nodes[x,h,z])):continue
                seen.add(p);queue.append(p)
    goals=[('warehouse',3100,-150,1034),('customs',3092,-150,1130),('support-building',3180,-150,1162),('helipad',3130,-150,1186),('quay',3234,-158,1170),('first-ship',3258,-150,1060),('second-ship',3308,-150,1060)]
    reached=[]
    for name,x,h,z in goals:
        choices=[p for p in seen if abs(p[0]-x)<=3 and abs(p[2]-z)<=3 and abs(p[1]-h)<=2]
        reached.append(dict(id=name,reachable=bool(choices),target=[x,h/2,z],contacts=len(choices)))
        if not choices:errors.append(['destination disconnected in 3D',name,x,h,z])
    result=dict(errors=errors,counts=dict(counts),corridors=corridors,public_nodes=len(nodes),reachable_public_nodes=len(seen),destinations=reached,visual_verified=False,world_written=False)
    write(a.candidate/'port-independent-check.json',result)
    print(json.dumps(dict(errors=len(errors),first_errors=errors[:16],counts=dict(counts),destinations=reached),ensure_ascii=False),flush=True)
    if errors:raise ValueError('Independent port acceptance failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('candidate','components'):p.add_argument('--'+name,type=Path,required=True)
    verify(p.parse_args())
