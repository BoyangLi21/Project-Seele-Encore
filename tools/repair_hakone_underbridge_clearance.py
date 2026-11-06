"""Remove a measured surplus soffit layer while retaining two supported layers.

This does not lower streets, move rails, widen holes in mountains, or treat
unknown space as empty. Existing unrelated road defects remain reported.
"""
import argparse,json,os,shutil
from pathlib import Path
from collections import deque,Counter
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import SOIL
from verify_hakone_network_candidate import PAVEMENT
from install_r53_carrier_trays import stopped_world
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.rail_civil_geometry import columns

CONCRETE='minecraft:light_gray_concrete'
EMPTY=AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern'}
FRAME={CONCRETE,'minecraft:stone_bricks','minecraft:polished_andesite','minecraft:iron_block'}
DIRECTIONS=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))


def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')


def health(e,p,floor,slab,road,original=False):
    x,z=p;s=e.state(x,floor,z,original)
    paved=s.split('[')[0] in PAVEMENT|{'projectseele:period_station_floor'} and ('type=bottom' in s)==bool(slab)
    clear=all(e.state(x,Y,z,original).split('[')[0] in EMPTY for Y in range(floor+1,floor+(5 if road else 3)))
    return paved,clear


def earth_paths(e,bounds,return_nodes=False):
    """Independent six-face paths through actual full-block civil members."""
    x,z,X,Z=bounds;nodes=set()
    for path in (e.folder/'source').glob('*.npz'):
        rx,rz=map(int,path.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        structural=np.array([s.split('[')[0] in FRAME for s in r['names']])
        for (cx,cz),v in zip(r['coords'],r['after']):
            yy,zz,xx=np.nonzero(structural[v]);nodes.update(zip((xx+int(cx)*16).tolist(),(yy-128).tolist(),(zz+int(cz)*16).tolist()))
    distance={};queue=deque()
    for p in nodes:
        for dx,dy,dz in DIRECTIONS:
            q=p[0]+dx,p[1]+dy,p[2]+dz
            if q in nodes or not(x<=q[0]<=X and z<=q[2]<=Z and -128<=q[1]<320):continue
            s=e.state(*q)
            if s.split('[')[0] in SOIL and 'type=bottom' not in s:
                distance[p]=1;queue.append(p);break
    while queue:
        p=queue.popleft()
        for dx,dy,dz in DIRECTIONS:
            q=p[0]+dx,p[1]+dy,p[2]+dz
            if q in nodes and q not in distance:distance[q]=distance[p]+1;queue.append(q)
    return distance,nodes if return_nodes else len(nodes)


def build(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);x,z,X,Z=cap['bounds_xz']
    if cap['actors'] or cap['unavailable_chunks']:raise ValueError('Requires a current FULL actor-free capture')
    a.out.mkdir(exist_ok=False)
    for name in ('source','delta','plan'):(a.out/name).mkdir()
    for f in (a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    for name in ('catalog.json','native-curves.json'):shutil.copy2(a.authority/name,a.out/'plan'/name)
    for name in ('buildings.json','footways.json'):save(a.out/'plan'/name,[])
    with np.load(a.authority/'network.npz') as f:g={k:f[k] for k in f.files}
    gx,gz,_,_=map(int,g['bounds']);area=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    d={k:(v[area].copy() if k!='bounds' else np.array([x,z,X,Z])) for k,v in g.items()};del g
    d['old_ground']=d['ground'].copy();np.savez_compressed(a.out/'plan/network.npz',**d)
    catalog=json.loads((a.authority/'catalog.json').read_text('utf8'));curves=json.loads((a.authority/'native-curves.json').read_text('utf8'))['trains']
    indices=[i for i,r in enumerate(curves) if any(x-5<=p[0]<=X+5 and z-5<=p[2]<=Z+5 and -110<p[1]<310 for p in r['points'])]
    envelopes={i:columns(curves,[i],3.5,4.,max_vertical_spread=None) for i in indices}
    transport=json.loads((a.authority/'native-curves.json').read_text('utf8'));secondary=[]
    for kind,below,above,width in [('ropeway',10,1,3),('boats',1,6,5),('boat',1,6,5)]:
        rows=transport.get(kind,[]);inds=[i for i,r in enumerate(rows) if any(x-6<=p[0]<=X+6 and z-6<=p[2]<=Z+6 for p in r['points'])]
        if inds:secondary.append((columns(rows,inds,width,width,max_vertical_spread=None),below,above))
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native')
        devices=dict(iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z)))
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(devices.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    e=Editor(a.out);launch=load(world);edits=[];deferred=[]
    for raw in json.loads(a.survey.read_text('utf8')):
        px,Y,pz=map(int,raw);p=(px,Y,pz);j,i=pz-z,px-x;floor,slab=road_blocks(d['grade2'][j,i]);floor=int(floor)
        if not d['walk'][j,i] or not d['road'][j,i] or Y!=floor+4:raise ValueError(('Survey is not a four-metre road soffit',p))
        if e.state(*p)!=CONCRETE or any(e.state(px,yy,pz)!=CONCRETE for yy in (Y+1,Y+2)):raise ValueError(('Current three-layer bridge differs from survey',p))
        if health(e,(px,pz),floor,slab,True)!=(True,False):raise ValueError(('Current road no longer matches surveyed problem',p))
        if any(e.state(px,yy,pz).split('[')[0] not in EMPTY for yy in range(floor+1,Y)):raise ValueError(('More than one clearance layer needs reconstruction',p))
        reason=None
        if p in devices:reason='native device'
        if launch.chunk_mask(px//16,pz//16)[Y+128,pz%16,px%16]:reason='mechanical volume'
        if any(all(b[k]<=p[k]<=b[k+3] for k in range(3)) for b in (r['occupied_bounds'] for r in catalog)):reason='occupied parcel'
        tracks=[n for n,env in envelopes.items() if (px,pz) in env and abs(env[px,pz]['low']-(Y+3))<=.8]
        if not tracks:reason='not a measured native rail bearing deck'
        if reason:deferred.append(dict(pos=list(p),reason=reason));continue
        e.put(*p,'minecraft:air');edits.append(dict(pos=list(p),before=CONCRETE,after='minecraft:air',native_curves=tracks))
    if not edits:raise ValueError('No fully verified under-bridge cells')
    piers=json.loads(a.pier_plan.read_text('utf8')) if a.pier_plan else []
    if len(piers)>96:raise ValueError('Pier plan exceeds finite review scope')
    for row in piers:
        px,top,pz=row['top'];foot=int(row['footing']);j,i=pz-z,px-x
        if d['walk'][j,i] or not(0<top-foot<=48) or e.state(px,top,pz)!=CONCRETE:raise ValueError('Pier lacks a retained beam outside public pavement')
        if e.state(px,foot,pz)!=row['soil_state'] or row['soil_state'].split('[')[0] not in SOIL:raise ValueError('Pier lacks its measured earth footing')
        for Y in range(foot+1,top):
            pos=(px,Y,pz);state=e.state(*pos)
            if state not in FRAME and state.split('[')[0] not in AIR:raise ValueError(('Pier meets another structure',pos,state))
            if pos in devices or launch.chunk_mask(px//16,pz//16)[Y+128,pz%16,px%16]:raise ValueError(('Protected pier cell',pos))
            if any(all(b[k]<=pos[k]<=b[k+3] for k in range(3)) for b in (r['occupied_bounds'] for r in catalog)):raise ValueError(('Pier meets occupied parcel',pos))
            if any((px,pz) in env and Y+1>env[px,pz]['low'] and Y<env[px,pz]['high']+4.5 for env in envelopes.values()):raise ValueError(('Pier meets native running track',pos))
            if any((px,pz) in env and Y+1>env[px,pz]['low']-below and Y<env[px,pz]['high']+above for env,below,above in secondary):raise ValueError(('Pier meets another transport reserve',pos))
            if state.split('[')[0] in AIR:e.put(*pos,CONCRETE)
    patches=e.save();e.regions.clear()
    save(a.out/'pier-plan.json',piers)
    save(a.out/'soffit-edits.json',edits);save(a.out/'deferred-soffits.json',deferred)
    save(a.out/'manifest.json',dict(world=str(world),bounds_xz=[x,z,X,Z],regions=patches,cells=sum(r['cells'] for r in patches),world_written=False,preserve_native_members=True))
    save(a.out/'functional-check.json',dict(errors=[],removed_surplus_soffit_cells=len(edits),deferred=deferred,road_geometry_unchanged=True,native_geometry_unchanged=True))
    save(a.out/'launch-protection.json',check_candidate(launch,a.out))
    # Read the persisted candidate independently. Detect all regressions in
    # the surrounding declared streets, including roads outside the work list.
    e=Editor(a.out);errors=[];before=Counter();after=Counter();checked=0
    for j,i in np.argwhere(d['walk']):
        p=(int(i+x),int(j+z));floor,slab=road_blocks(d['grade2'][j,i]);floor=int(floor);road=bool(d['road'][j,i]);checked+=1
        old=health(e,p,floor,slab,road,True);new=health(e,p,floor,slab,road)
        for k,name in enumerate(('floor','headroom')):
            before[name]+=not old[k];after[name]+=not new[k]
            if old[k] and not new[k]:errors.append(['new public regression',name,*p])
    distance,nodes=earth_paths(e,[x,z,X,Z]);max_path=0
    for row in edits:
        px,Y,pz=row['pos']
        if e.state(px,Y,pz)!='minecraft:air':errors.append(['uncleared soffit',px,Y,pz])
        for yy in (Y+1,Y+2):
            p=(px,yy,pz)
            if e.state(*p)!=CONCRETE or e.state(*p,original=True)!=CONCRETE:errors.append(['two-layer deck not retained',*p])
            if p not in distance:errors.append(['retained deck lacks a captured earth load path',*p])
            else:max_path=max(max_path,distance[p])
    for row in piers:
        px,top,pz=row['top'];foot=row['footing']
        if any(e.state(px,Y,pz) not in FRAME for Y in range(foot+1,top+1)):errors.append(['pier is discontinuous',px,pz])
        if e.state(px,foot,pz).split('[')[0] not in SOIL:errors.append(['pier lost soil contact',px,pz])
    for pos in devices:
        if e.state(*pos)!=e.state(*pos,original=True):errors.append(['device changed',*pos])
    if before['headroom']-after['headroom']!=len(edits):errors.append(['public clearance reduction differs from finite work'])
    report=dict(errors=errors,declared_columns_checked=checked,road_defects_before=dict(before),road_defects_after=dict(after),removed_surplus_soffit_cells=len(edits),retained_deck_layers=2,
        structural_nodes_checked=nodes,maximum_earth_load_path=max_path,added_pier_columns=len(piers),devices_unchanged=len(devices),deferred_columns=len(deferred),whole_map_complete=False)
    if a.pier_plan and max_path>24:errors.append(['retained deck still lacks nearby pier',max_path])
    save(a.out/'independent-check.json',report);print(json.dumps(report),flush=True)
    if errors:raise ValueError('Under-bridge geometry or preservation check failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','authority','survey','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--pier-plan',type=Path)
    build(p.parse_args())
