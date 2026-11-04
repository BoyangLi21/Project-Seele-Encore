"""Read back the restored road, native walkways, load paths and floating delta."""
import argparse,json,math
from pathlib import Path
from collections import deque
import numpy as np
from author_hakone_lakefront import Editor
from repair_hakone_underbridge_clearance import earth_paths,FRAME,health
from hakone_earthworks import road_blocks
from query_blocks import AIR
from map_pipeline.native_geometry_patch import expected


def floating(folder):
    report=json.loads((folder/'floating-components.json').read_text('utf8'));data={};result=set();unknown=0
    for f in folder.glob('r.*.*.npz'):
        with np.load(f)as a:data[tuple(map(int,f.stem.split('.')[1:]))]=(a['indices'].astype(np.int64),a['labels'])
    for r in report['components']:
        if r['unknown']:unknown+=1;continue
        for rx,rz,label in r['parts']:
            at,ids=data[rx,rz];q=at[ids==label]
            result.update(zip((q%512+rx*512).tolist(),(q//262144-128).tolist(),((q//512)%512+rz*512).tolist()))
    return result,unknown


def verify(a):
    c=a.candidate;e=Editor(c);design=json.loads((c/'tunnel-design.json').read_text('utf8'));errors=[]
    with np.load(c/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);nodes=set();new_road=set();source=(-1084,310);goal=(-740,315)
    for row in design['roadway']:
        px,pz=row['pos'];j,i=pz-z,px-x;h,slab=road_blocks(d['grade2'][j,i]);state=health(e,(px,pz),int(h),slab,bool(d['road'][j,i]))
        if not all(state):errors.append(['authored surface or clearance',px,pz])
        if row['road']:
            new_road.add((px,pz))
            if not d['road'][j,i]:errors.append(['carriageway not registered',px,pz])
    maximum_crossfall=0
    for px,_,pz in design['centreline']:
        px=int(px);zc=round(pz);values=[]
        for zz in range(zc-4,zc+5):
            if not d['road'][zz-z,px-x]:errors.append(['full-width carriageway gap',px,zz])
            values.append(float(d['grade2'][zz-z,px-x])/2)
        delta=max(values)-min(values);maximum_crossfall=max(maximum_crossfall,delta)
        if delta>.5:errors.append(['excessive carriageway crossfall',px,delta])
    for j,i in np.argwhere(d['road']):
        h,slab=road_blocks(d['grade2'][j,i]);px,pz=int(i+x),int(j+z)
        if all(health(e,(px,pz),int(h),slab,True)):nodes.add((px,pz))
    prev={source:None}if source in nodes else{};queue=deque(prev)
    while queue:
        px,pz=queue.popleft()
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            q=px+dx,pz+dz
            if q in nodes and q not in prev and abs(int(d['grade2'][pz-z,px-x])-int(d['grade2'][q[1]-z,q[0]-x]))<=1:prev[q]=(px,pz);queue.append(q)
    if new_road-set(prev):errors.append(['carriageway isolated cells',len(new_road-set(prev)),sorted(new_road-set(prev))[:12]])
    path=[]
    if goal not in prev:errors.append(['east road unreachable by vehicle cells'])
    else:
        p=goal
        while p is not None:path.append([p[0],float(d['grade2'][p[1]-z,p[0]-x])/2+1,p[1]]);p=prev[p]
        path.reverse()
    native=design['native']
    if len(native)!=348:errors.append(['native walkway count changed'])
    for row in native:
        px,y,pz=row['pos']
        if e.state(px,y,pz)!=row['state']or e.state(px,y,pz)!=e.state(px,y,pz,original=True):errors.append(['native module changed',px,pz])
        if any(e.state(px,h,pz).split('[')[0]not in AIR|{'minecraft:light'}for h in(99,100,101)):errors.append(['native walk headroom',px,pz])
        if e.state(px,97,pz).split('[')[0]not in FRAME:errors.append(['native module lacks bearing',px,pz])
    for px in(-873,-785):
        for pz in(301,302,314,315):
            if e.state(px,98,pz)!='minecraft:smooth_stone'or any(e.state(px,h,pz).split('[')[0]not in AIR for h in(99,100)):errors.append(['native walkway landing',px,pz])
    distance,_=earth_paths(e,[x,z,X,Z]);unsupported=[]
    for p in map(tuple,design['structural']):
        s=e.state(*p).split('[')[0]
        if s=='minecraft:sea_lantern':continue
        if s not in FRAME or p not in distance:unsupported.append(list(p))
    if unsupported:errors.append(['structural member lacks soil load path',len(unsupported),unsupported[:8]])
    old,uo=floating(a.before_components);new,un=floating(a.after_components)
    if new-old or uo!=un:errors.append(['floating regression',len(new-old),uo,un])
    edits=json.loads((c/'tunnel-edits.json').read_text('utf8'))
    for r in edits:
        if e.state(*r['pos'])!=r['after']or e.state(*r['pos'],original=True)!=r['before']:errors.append(['edited block readback',r['pos']])
    _,native_proof=expected(c)
    if not native_proof['existing_native_members_exact']:errors.append(['native service changed'])
    report=dict(errors=errors,edited_cells=len(edits),vehicle_columns=len(new_road),vehicle_connected_columns=len(new_road&set(prev)),vehicle_path=path,native_walkway_modules=len(native),native_landing_pairs=4,maximum_full_width_crossfall=maximum_crossfall,
                structural_cells=len(design['structural']),unsupported_members=len(unsupported),floating_cells_before=len(old),floating_cells_after=len(new),new_floating_cells=len(new-old),unknown_components=un,native_services_unchanged=True,game_ui_verified=False)
    (c/'tunnel-independent-check.json').write_text(json.dumps(report,indent=2),'utf8')
    manifest=json.loads((c/'manifest.json').read_text('utf8'));manifest['finite_tunnel_verification']={'native_walkway_modules':348,'vehicle_columns':len(new_road)}
    (c/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k!='vehicle_path'}),flush=True)
    if errors:raise ValueError('Independent tunnel check failed')


def require_verified(candidate):
    m=json.loads((candidate/'manifest.json').read_text('utf8'))
    if 'finite_tunnel_verification'not in m and not(candidate/'tunnel-design.json').exists():return
    r=json.loads((candidate/'tunnel-independent-check.json').read_text('utf8'))
    if r['errors']or r['new_floating_cells']or r['unsupported_members']or r['native_walkway_modules']!=348 or r['vehicle_columns']!=r['vehicle_connected_columns']or not r['vehicle_path']:raise ValueError('Unverified finite tunnel')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('candidate','before-components','after-components'):p.add_argument('--'+n,type=Path,required=True)
    verify(p.parse_args())
