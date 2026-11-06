"""Apply finite reviewed bearing additions and exact rigid vegetation moves.

Native devices, routes and occupied contents stay at their original coordinates.
Every addition is checked in three dimensions against public and native traffic.
"""
import argparse,json,os,shutil
from pathlib import Path
from collections import Counter
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from query_blocks import AIR,iter_block_entities
from hakone_earthworks import road_blocks
from repair_hakone_underbridge_clearance import health,save
from map_pipeline.rail_civil_geometry import columns
from map_pipeline.launch_protection import load,check_candidate
from install_r53_carrier_trays import stopped_world


def reserves(authority,bounds):
    x,z,X,Z=bounds;data=json.loads((authority/'native-curves.json').read_text('utf8'));result=[]
    for key,below,above,width,platform in [('trains',0,4.5,1.75,1.3),('ropeway',10,1,3,3),('boats',1,6,5,5)]:
        rows=data.get(key,[])
        for i,row in enumerate(rows):
            if not any(x-5<=p[0]<=X+5 and z-5<=p[2]<=Z+5 and -128<p[1]<319 for p in row['points']):continue
            result.append((key,i,columns(rows,[i],width,platform,max_vertical_spread=None),below,above))
    return result


def conflict(pos,env):
    x,y,z=pos
    for key,i,c,below,above in env:
        r=c.get((x,z))
        if r and y+1>r['low']-below+1e-6 and y<r['high']+above-1e-6:return key,i
    return None


def build(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);bounds=cap['bounds_xz'];x,z,X,Z=bounds
    if cap['actors'] or cap['unavailable_chunks']:raise ValueError('Requires FULL actor-free current capture')
    plan=json.loads(a.design.read_text('utf8'));a.out.mkdir(exist_ok=False)
    for name in ('source','delta','plan'):(a.out/name).mkdir()
    for f in (a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json');shutil.copy2(a.design,a.out/'bearing-design.json')
    for name in ('native-curves.json','catalog.json'):shutil.copy2(a.authority/name,a.out/'plan'/name)
    for name in ('buildings.json','footways.json'):save(a.out/'plan'/name,[])
    with np.load(a.authority/'network.npz') as f:g={k:f[k] for k in f.files}
    gx,gz,_,_=map(int,g['bounds']);ar=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    d={k:(v[ar].copy() if k!='bounds' else np.array(bounds)) for k,v in g.items()};del g
    d['old_ground']=d['ground'].copy();np.savez_compressed(a.out/'plan/network.npz',**d)
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');devices=dict(iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z)))
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(devices.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    e=Editor(a.out);env=reserves(a.authority,bounds);guard=load(world);edits={};anchors=[]
    def proposed(pos,state,kind,removing=False):
        p=tuple(map(int,pos));px,y,pz=p
        if not(x<=px<=X and z<=pz<=Z and -128<=y<320):raise ValueError(('Outside capture',p))
        old=e.state(*p,original=True)
        if p in devices or guard.chunk_mask(px//16,pz//16)[y+128,pz%16,px%16]:raise ValueError(('Protected cell',p))
        if not removing and conflict(p,env):raise ValueError(('Native clearance',p,conflict(p,env)))
        j,i=pz-z,px-x
        if d['walk'][j,i]:
            floor,_=road_blocks(d['grade2'][j,i]);floor=int(floor)
            if floor<=y<=floor+(4 if d['road'][j,i] else 2):raise ValueError(('Public surface/body',p))
        if p in edits and edits[p]['after']!=state:raise ValueError(('Conflicting finite edits',p))
        edits[p]=dict(pos=list(p),before=old,after=state,kind=kind)
    moves=plan.get('rigid_moves',[]);moving=set()
    for row in moves:
        for c in row['cells']:
            p=tuple(c['pos'])
            if p in moving or e.state(*p)!=c['state'] or not(c['state'].split('[')[0].endswith('_log') or c['state'].split('[')[0].endswith('_leaves')):raise ValueError(('Invalid exact vegetation payload',p))
            moving.add(p)
    final_moves={}
    for row in moves:
        shift=row['translation']
        for c in row['cells']:
            p=tuple(c['pos']);q=tuple(p[i]+shift[i] for i in range(3))
            if q in final_moves:raise ValueError('Overlapping moved vegetation')
            if q not in moving and e.state(*q).split('[')[0] not in AIR:raise ValueError(('Moved vegetation collision',q))
            final_moves[q]=c['state']
        anchors.append(row['footing'])
    for p in moving-final_moves.keys():proposed(p,'minecraft:air','retired original vegetation position',True)
    for p,state in final_moves.items():proposed(p,state,'complete tree lowered to measured soil')
    for row in plan.get('supports',[]):
        for anchor in row['anchors']:anchors.append(anchor)
        for c in row['cells']:
            p=c['pos'];old=e.state(*p)
            if old!=c['before'] or old.split('[')[0] not in AIR:raise ValueError(('Support must use measured empty space',p,old))
            proposed(p,c['after'],row['kind'])
    for a0 in anchors:
        p=tuple(a0['pos'])
        if p in edits or e.state(*p)!=a0['state']:raise ValueError(('Measured anchor changed',p))
    for row in edits.values():e.put(*row['pos'],row['after'])
    patches=e.save();e.regions.clear()
    save(a.out/'bearing-edits.json',list(edits.values()));save(a.out/'manifest.json',dict(world=str(world),bounds_xz=bounds,regions=patches,cells=sum(r['cells'] for r in patches),world_written=False,preserve_native_members=True))
    save(a.out/'launch-protection.json',check_candidate(guard,a.out))
    # Independent readback checks all public columns, device blocks, finite
    # anchors and every retained step's formerly empty headroom in the crop.
    e=Editor(a.out);errors=[];before=Counter();after=Counter();steps=0
    for j,i in np.argwhere(d['walk']):
        h,slab=road_blocks(d['grade2'][j,i]);p=int(i+x),int(j+z);road=bool(d['road'][j,i]);old=health(e,p,int(h),slab,road,True);new=health(e,p,int(h),slab,road)
        for k,name in enumerate(('floor','headroom')):
            before[name]+=not old[k];after[name]+=not new[k]
            if old[k] and not new[k]:errors.append(['new public defect',name,*p])
    for f in (a.out/'source').glob('*.npz'):
        rx,rz=map(int,f.stem.split('.')[1:]);r=e.region(rx*512,rz*512);stairs=np.array(['_stairs[' in s for s in r['names']])
        for (cx,cz),v in zip(r['coords'],r['before']):
            yy,zz,xx=np.nonzero(stairs[v]);steps+=len(xx)
            for px,y,pz in zip(xx+cx*16,yy-128,zz+cz*16):
                for Y in (int(y)+1,int(y)+2):
                    if Y>=320:continue
                    old=e.state(int(px),Y,int(pz),True);new=e.state(int(px),Y,int(pz))
                    if old.split('[')[0] in AIR and new.split('[')[0] not in AIR:errors.append(['stair headroom changed',int(px),Y,int(pz)])
    for p in devices:
        if e.state(*p)!=e.state(*p,original=True):errors.append(['device changed',*p])
    for row in moves:
        for c in row['cells']:
            p=tuple(c['pos'][i]+row['translation'][i] for i in range(3))
            if e.state(*p)!=c['state']:errors.append(['tree payload changed',*p])
    for a0 in anchors:
        if e.state(*a0['pos'])!=a0['state']:errors.append(['anchor changed',a0['pos']])
    actual={}
    for f in (a.out/'delta').glob('*.npz'):
        with np.load(f) as data:q={k:data[k] for k in data.files}
        for n,(cx,cz) in enumerate(q['coordinates']):
            lo,hi=q['ranges'][n:n+2]
            for at,b,v in zip(q['indices'][lo:hi],q['before'][lo:hi],q['after'][lo:hi]):
                p=(int(cx*16+at%16),int(at//256)-128,int(cz*16+(at//16)%16));actual[p]=(str(q['palette'][b]),str(q['palette'][v]))
    expected={p:(v['before'],v['after']) for p,v in edits.items() if v['before']!=v['after']}
    if actual!=expected:errors.append(['persisted delta differs from finite plan'])
    report=dict(errors=errors,cells=len(actual),support_groups=len(plan.get('supports',[])),complete_trees_replanted=len(moves),devices_unchanged=len(devices),stair_blocks_checked=steps,public_before=dict(before),public_after=dict(after),native_geometry_unchanged=True,whole_map_complete=False)
    save(a.out/'functional-check.json',report);save(a.out/'independent-check.json',report);print(json.dumps(report),flush=True)
    if errors:raise ValueError('Fixture bearing verification failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','authority','design','out'):p.add_argument('--'+n,type=Path,required=True)
    build(p.parse_args())
