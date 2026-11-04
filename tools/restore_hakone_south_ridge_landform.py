"""Restore measured hillside gaps below retained South Ward streets and station.

Only terrain/empty cells change; native volumes and all architectural payloads
remain exact. Complete affected trees are translated onto the finished soil.
"""
import argparse,json,os,shutil,itertools
from pathlib import Path
from collections import Counter
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import SOIL,PLANTS
from hakone_earthworks import road_blocks
from repair_hakone_underbridge_clearance import health,save
from repair_hakone_fixture_bearings import reserves,conflict
from map_pipeline.launch_protection import load,check_candidate
from install_r53_carrier_trays import stopped_world


def build(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);bounds=cap['bounds_xz'];x,z,X,Z=bounds
    if bounds!=[112,656,351,943]or cap['actors']or cap['unavailable_chunks']:raise ValueError('Full current South ridge capture required')
    with np.load(a.authority/'network.npz')as f:g={k:f[k]for k in f.files}
    gx,gz,_,_=map(int,g['bounds']);ar=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1];d={k:(v[ar].copy()if k!='bounds'else np.array(bounds))for k,v in g.items()};del g
    with np.load(a.design)as f:plan={k:f[k]for k in f.files}
    with np.load(a.source/'measured.npz')as f:soil=f['top']
    if not np.array_equal(plan['bounds'],bounds)or not np.array_equal(plan['current'],d['ground'])or not np.array_equal(plan['soil'],soil):raise ValueError('Current ground differs from finite survey')
    target=plan['target'];change=target>d['ground']
    if np.any(target<d['ground'])or np.any(change&~plan['mask']):raise ValueError('This landform pass is fill-only within its exact extent')
    if change[[0,-1],:].any()or change[:,[0,-1]].any():raise ValueError('No changes at capture boundary')
    if int(change.sum())!=4839 or int((target-d['ground']).max())!=93:raise ValueError('Finite landform extent changed')
    # No new cliff is allowed: raised surfaces meet their neighbors within one
    # voxel, or reduce an already present difference at retained foundations.
    for axis in(0,1):
        old=np.abs(np.diff(d['ground'].astype(int),axis=axis));new=np.abs(np.diff(target.astype(int),axis=axis))
        if np.any(new>np.maximum(old,1)):raise ValueError('New terrain height discontinuity')
    catalog=json.loads((a.authority/'catalog.json').read_text('utf8'));volumes=json.loads((a.authority/'station-volumes.json').read_text('utf8'))+[r['occupied_bounds']for r in catalog]
    volumes=[b for b in volumes if b[0]<=X and b[3]>=x and b[2]<=Z and b[5]>=z]
    a.out.mkdir(exist_ok=False)
    for name in('source','delta','plan'):(a.out/name).mkdir()
    for f in(a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json');shutil.copy2(a.design,a.out/'landform-design.npz')
    for name in('native-curves.json','catalog.json'):shutil.copy2(a.authority/name,a.out/'plan'/name)
    for name in('buildings.json','footways.json'):save(a.out/'plan'/name,[])
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');devices=dict(iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z)))
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(devices.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    e=Editor(a.out);env=reserves(a.authority,bounds);guard=load(world);vegetation={}
    for f in(a.out/'source').glob('*.npz'):
        rx,rz=map(int,f.stem.split('.')[1:]);r=e.region(rx*512,rz*512);tree=np.array([s.split('[')[0].endswith(('_log','_leaves'))for s in r['names']])
        for(cx,cz),b in zip(r['coords'],r['before']):
            yy,zz,xx=np.nonzero(tree[b])
            for px,y,pz in zip(xx+cx*16,yy-128,zz+cz*16):vegetation[(int(px),int(y),int(pz))]=e.state(int(px),int(y),int(pz))
    todo=set(vegetation);groups=[];neighbors=[q for q in itertools.product((-1,0,1),repeat=3)if q!=(0,0,0)]
    while todo:
        seed=todo.pop();group={seed};stack=[seed]
        while stack:
            p=stack.pop()
            for off in neighbors:
                q=tuple(p[k]+off[k]for k in range(3))
                if q in todo:todo.remove(q);group.add(q);stack.append(q)
        if any(change[p[2]-z,p[0]-x]and p[1]<=target[p[2]-z,p[0]-x]for p in group):groups.append(group)
    moving=set().union(*groups)if groups else set();moves=[];destinations={}
    launch_masks={}
    def protected(p):
        px,y,pz=p
        chunk=px//16,pz//16
        if chunk not in launch_masks:launch_masks[chunk]=guard.chunk_mask(*chunk)
        if p in devices or launch_masks[chunk][y+128,pz%16,px%16]:return 'native device or launch volume'
        if any(all(b[k]<=p[k]<=b[k+3]for k in range(3))for b in volumes):return 'retained occupied volume'
        if conflict(p,env):return 'native clearance'
        j,i=pz-z,px-x
        if d['walk'][j,i]:
            h,_=road_blocks(d['grade2'][j,i]);h=int(h)
            if h<=y<=h+(4 if d['road'][j,i]else 3):return 'public floor or body'
        return None
    for group in sorted(groups,key=lambda r:min(r)):
        logs=[p for p in group if vegetation[p].split('[')[0].endswith('_log')];feet={}
        if not logs:raise ValueError('Affected leaf component has no complete trunk')
        for px,y,pz in logs:feet[px,pz]=min(feet.get((px,pz),y),y)
        shift=max(int(max(target[pz-z,px-x],soil[pz-z,px-x]))+1-y for(px,pz),y in feet.items())
        if shift<=0:raise ValueError('Tree canopy intersects hillside despite retained roots; explicit replanting needed')
        for(px,pz),y in feet.items():
            if y+shift!=max(int(target[pz-z,px-x]),int(soil[pz-z,px-x]))+1:raise ValueError('Joined tree group needs different footing heights')
        row=dict(translation=[0,shift,0],cells=[],footings=[])
        for p in sorted(group):
            q=(p[0],p[1]+shift,p[2])
            if q[1]>=319 or protected(p)or protected(q):raise ValueError(('Tree intersects retained geometry',p,q,protected(q)))
            if q in destinations or(q not in moving and e.state(*q).split('[')[0]not in AIR|PLANTS):raise ValueError(('Tree destination occupied',q,e.state(*q)))
            destinations[q]=vegetation[p];row['cells'].append(dict(pos=list(p),state=vegetation[p]))
        row['footings']=[[px,y+shift-1,pz]for(px,pz),y in feet.items()];moves.append(row)
    for p in moving:e.put(*p,'minecraft:air')
    additions=0;retained=Counter();raised_soil_columns=0
    for j,i in np.argwhere(change&(target>soil)):
        px,pz=int(i+x),int(j+z);top=int(target[j,i]);lo=int(soil[j,i]);raised_soil_columns+=1
        for y in range(lo,top+1):
            p=px,y,pz;state=e.state(*p);mat=state.split('[')[0]
            if mat not in AIR|SOIL|PLANTS:
                retained[mat]+=1;continue
            if protected(p):raise ValueError(('Proposed earth enters retained space',p,protected(p)))
            new='minecraft:grass_block[snowy=false]'if y==top else'minecraft:dirt'if y>=top-2 else'minecraft:stone'
            if state!=new:e.put(*p,new);additions+=1
    for p,state in destinations.items():
        if e.state(*p).split('[')[0]not in AIR|PLANTS:raise ValueError(('Tree buried by new terrain',p))
        e.put(*p,state)
    patches=e.save();e.regions.clear();e=Editor(a.out);errors=[];before=Counter();after=Counter()
    for j,i in np.argwhere(d['walk']):
        h,s=road_blocks(d['grade2'][j,i]);p=int(x+i),int(z+j);v=health(e,p,int(h),s,bool(d['road'][j,i]),True);w=health(e,p,int(h),s,bool(d['road'][j,i]))
        for k,name in enumerate(('floor','headroom')):
            before[name]+=not v[k];after[name]+=not w[k]
            if v[k]and not w[k]:errors.append(['new public defect',name,*p])
    for p in devices:
        if e.state(*p)!=e.state(*p,original=True):errors.append(['device altered',*p])
    for row in moves:
        for cell in row['cells']:
            q=tuple(cell['pos'][k]+row['translation'][k]for k in range(3))
            if e.state(*q)!=cell['state']:errors.append(['tree payload changed',*q])
        for p in row['footings']:
            if e.state(*p).split('[')[0]not in SOIL:errors.append(['tree lacks soil footing',*p])
    changed_columns=set();original_structures=0;total=0
    for f in(a.out/'delta').glob('*.npz'):
        with np.load(f)as q:v={k:q[k]for k in q.files}
        for n,(cx,cz)in enumerate(v['coordinates']):
            lo,hi=v['ranges'][n:n+2]
            for at,b,c in zip(v['indices'][lo:hi],v['before'][lo:hi],v['after'][lo:hi]):
                p=int(cx*16+at%16),int(at//256)-128,int(cz*16+at//16%16);old=str(v['palette'][b]);new=str(v['palette'][c]);total+=1;changed_columns.add((p[0],p[2]))
                if p not in moving and old.split('[')[0]not in AIR|SOIL|PLANTS:errors.append(['existing structure changed',*p,old]);original_structures+=1
                if protected(p):errors.append(['changed retained envelope',*p])
                if p not in moving and p not in destinations:
                    if not change[p[2]-z,p[0]-x]or not int(soil[p[2]-z,p[0]-x])<=p[1]<=int(target[p[2]-z,p[0]-x]):errors.append(['earth edit outside finite volume',*p])
    # A contiguous natural fill is required, except for retained civil blocks.
    for j,i in np.argwhere(change&(target>soil)):
        px,pz=int(x+i),int(z+j)
        for y in range(int(soil[j,i])+1,int(target[j,i])+1):
            if e.state(px,y,pz).split('[')[0]in AIR:errors.append(['remaining void in filled hillside',px,y,pz])
    d['old_ground']=d['ground'].copy();d['ground']=target.copy();np.savez_compressed(a.out/'plan/network.npz',**d)
    np.savez_compressed(a.out/'finite-landform-authority.npz',bounds=bounds,editable=change,before_ground=plan['current'])
    report=dict(errors=errors,cells=total,terrain_columns=int(change.sum()),raised_soil_columns=raised_soil_columns,earth_cells=additions,trees_replanted=len(moves),tree_cells_moved=len(moving),devices_preserved=len(devices),retained_public_before=dict(before),retained_public_after=dict(after),retained_civil_cells_in_fill=dict(retained),original_structures_modified=original_structures,native_geometry_unchanged=True,maximum_ground_raise=int((target-plan['current']).max()),new_height_discontinuities=0,whole_map_complete=False)
    for name,data in[('functional-check.json',report),('independent-check.json',report),('tree-moves.json',moves),('manifest.json',dict(world=str(world),bounds_xz=bounds,regions=patches,cells=total,world_written=False,preserve_native_members=True)),('launch-protection.json',check_candidate(guard,a.out))]:save(a.out/name,data)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if errors:raise ValueError('Independent landform verification failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','authority','design','out'):p.add_argument('--'+n,type=Path,required=True)
    build(p.parse_args())
