"""Refine installed rail bearing against complete native engine samples.

Rebase on a fresh world capture. Only failing bearing/clearance columns and
their displaced tunnel walls are changed; native service data is untouched.
"""
import argparse,json,math,os,shutil
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from map_pipeline.rail_civil_geometry import columns,vertical_bounds,block_top
from map_pipeline.launch_protection import load,check_candidate
from hakone_earthworks import road_blocks
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import SOIL,PLANTS
from install_r53_carrier_trays import stopped_world
from repair_hakone_rail_civil import PASSIVE,STONE


def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')


def refine(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world'])
    if cap['unavailable_chunks'] or cap['actors']:raise ValueError('Requires a complete actor-free capture')
    x,z,X,Z=cap['bounds_xz'];curves=json.loads((a.authority/'native-curves.json').read_text('utf8'))['trains']
    designs=[json.loads((p/'plan/rail-civil-design.json').read_text('utf8')) for p in a.installed]
    geometry=[json.loads((p/'rail-civil-geometry.json').read_text('utf8')) for p in a.installed]
    indices=sorted(set(i for d in designs for i in d['curve_indices']));env=columns(curves,indices)
    if any(not(x+3<=px<=X-3 and z+3<=pz<=Z-3) for px,pz in env):raise ValueError('Clipped civil envelope')
    a.out.mkdir(exist_ok=False)
    for name in ('source','delta','plan'):(a.out/name).mkdir()
    for f in (a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    for name in ('native-curves.json','catalog.json'):shutil.copy2(a.authority/name,a.out/'plan'/name)
    with np.load(a.authority/'network.npz') as f:g={k:f[k] for k in f.files}
    gx,gz,_,_=map(int,g['bounds']);area=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    d={k:(v[area].copy() if k!='bounds' else np.array([x,z,X,Z])) for k,v in g.items()};del g
    d['old_ground']=d['ground'].copy();np.savez_compressed(a.out/'plan/network.npz',**d)
    stations={r['id']:r for p in a.installed for r in json.loads((p/'plan/buildings.json').read_text('utf8'))}
    save(a.out/'plan/buildings.json',list(stations.values()));save(a.out/'plan/footways.json',[])
    save(a.out/'plan/rail-civil-design.json',dict(curve_indices=indices,installed_sources=list(map(str,a.installed)),bearing_refinement_only=True))
    tags={}
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native')
        for pos,tag in iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z)):tags[pos]=tag
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(tags.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    launch=load(world);e=Editor(a.out);floor,_=road_blocks(d['grade2']);edits=[];issues=[]
    rooms={}
    for r in json.loads((a.authority/'catalog.json').read_text('utf8')):
        b=r['occupied_bounds']
        if b[0]>X or b[3]<x or b[2]>Z or b[5]<z:continue
        for cx in range(b[0]//16,b[3]//16+1):
            for cz in range(b[2]//16,b[5]//16+1):rooms.setdefault((cx,cz),[]).append(b)
    def put(p,state,kind):
        old=e.state(*p)
        if old==state:return
        px,Y,pz=p;j,i=pz-z,px-x;reason=None
        if p in tags:reason='device'
        if launch.chunk_mask(px//16,pz//16)[Y+128,pz%16,px%16]:reason='mechanism'
        if any(all(b[k]<=p[k]<=b[k+3] for k in range(3)) for b in rooms.get((px//16,pz//16),[])):reason='occupied room'
        if d['walk'][j,i] and floor[j,i]-2<=Y<=floor[j,i]+4:reason='retained public passage'
        if old.split('[')[0] not in PASSIVE:reason='foreign structure'
        if reason:issues.append([reason,*p,old,state]);return
        e.put(*p,state);edits.append(dict(pos=list(p),before=old,after=state,kind=kind))
    empty=AIR|PLANTS|{'minecraft:light','minecraft:water','minecraft:lava'}
    failed=[];displaced=set()
    covered=set(tuple(q) for g in geometry for q in g['covered_columns'])
    for (px,pz),r in env.items():
        faces=[];blocked=False
        for Y in range(math.floor(r['low'])-3,math.ceil(r['high']+4.5)):
            s=e.state(px,Y,pz)
            if s.split('[')[0] in empty:continue
            top=block_top(Y,s)
            if top<=r['low']+1e-7:faces.append(top)
            elif Y<r['high']+4.5-1e-7:blocked=True
        if faces and r['high']-max(faces)<=.8 and not blocked:continue
        failed.append([px,pz]);Y,state,top,roof=vertical_bounds(r)
        if r['high']-top>.8:raise ValueError(('Native vertical spread needs explicit geometry review',px,pz))
        old_roof=e.state(px,roof,pz)
        if (px,pz) not in covered and old_roof==STONE and any((px+dx,pz+dz) in covered for dx,dz in ((1,0),(-1,0),(0,1),(0,-1))):
            displaced.add((px,pz));covered.add((px,pz))
        if e.state(px,Y-1,pz).split('[')[0] in empty:put((px,Y-1,pz),STONE,'seam deck continuity')
        put((px,Y,pz),state,'native sampled bearing refinement')
        for yy in range(Y+1,roof):put((px,yy,pz),'minecraft:air','native sampled clearance refinement')
    piers=[r for g in geometry for r in g['pier_columns']];new_walls=[]
    for px,pz in sorted(displaced):
        Y,_,_,roof=vertical_bounds(env[px,pz])
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            Q,R=px+dx,pz+dz
            if (Q,R) in env:continue
            foot=None
            for yy in range(Y-2,max(-128,Y-48)-1,-1):
                if e.state(Q,yy,R).split('[')[0] in SOIL:foot=yy;break
            if foot is None:issues.append(['displaced tunnel wall lacks soil',Q,R]);continue
            for yy in range(foot+1,roof+1):put((Q,yy,R),STONE,'native sampled tunnel sidewall')
            piers.append(dict(top=[Q,roof,R],footing=[Q,foot,R],kind='refined tunnel wall footing'))
            new_walls.append(dict(x=Q,z=R,footing=foot,roof=roof))
    patches=e.save();e.regions.clear()
    data=dict(curves=indices,columns=[dict(x=q[0],z=q[1],**{k:(sorted(v) if k=='curves' else v) for k,v in r.items()}) for q,r in env.items()],
        covered_columns=[list(q) for q in sorted(covered)],tunnels=[r for g in geometry for r in g['tunnels']],pier_columns=piers,
        canopies=[r for g in geometry for r in g['canopies']],station_access_columns=[r for g in geometry for r in g.get('station_access_columns',[])],
        refined_columns=failed,refined_tunnel_walls=new_walls)
    save(a.out/'rail-civil-geometry.json',data);save(a.out/'civil-edits.json',edits);save(a.out/'civil-conflicts.json',issues)
    save(a.out/'manifest.json',dict(world=str(world),bounds_xz=[x,z,X,Z],regions=patches,cells=sum(r['cells'] for r in patches),world_written=False,preserve_native_members=True))
    save(a.out/'functional-check.json',dict(errors=issues,native_curves_unchanged=True,refined_columns=len(failed),civil_edits=len(edits)))
    save(a.out/'launch-protection.json',check_candidate(launch,a.out))
    print('Native bearing refinement',len(failed),'columns',len(edits),'edits',len(issues),'conflicts',flush=True)
    if issues:raise ValueError(issues[:10])


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','authority','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--installed',type=Path,action='append',required=True)
    refine(p.parse_args())
