"""Independently inspect saved bearing, headroom, supports and retained passages."""
import argparse,json,math
from collections import deque
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from map_pipeline.rail_civil_geometry import columns,block_top
from hakone_earthworks import road_blocks
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL,PLANTS
from verify_hakone_station_connection import verify as station_verify


def verify(candidate):
    spec=json.loads((candidate/'plan/rail-civil-design.json').read_text('utf8'))
    curves=json.loads((candidate/'plan/native-curves.json').read_text('utf8'))['trains']
    env=columns(curves,spec['curve_indices']);e=Editor(candidate);errors=[];bearings={};structure={}
    base=Editor(Path(spec['base_public_candidate'])) if spec.get('base_public_candidate') else None
    base_public_columns=0
    if base is not None:
        path=Path(spec['base_public_candidate'])
        if json.loads((path/'independent-check.json').read_text('utf8'))['errors']:raise ValueError('Base public works are not verified')
        with np.load(path/'plan/network.npz') as f:public={k:f[k] for k in ('bounds','walk','grade2')}
        bx,bz,_,_=map(int,public['bounds']);by,_=road_blocks(public['grade2'])
        for j,i in np.argwhere(public['walk']):
            px,pz=int(i+bx),int(j+bz);h=int(by[j,i])
            for Y in range(h-2,h+5):
                if e.state(px,Y,pz)!=base.state(px,Y,pz):errors.append(['verified public works changed by rail civil',px,Y,pz])
            base_public_columns+=1
    empty=AIR|PLANTS|{'minecraft:light','minecraft:water','minecraft:lava'}
    low_gaps=[];clearance=0
    for (x,z),row in env.items():
        # Find the highest saved solid upper face below the rail, rather than
        # accepting the author's expected state or integer floor calculation.
        faces=[]
        for y in range(math.floor(row['low'])-3,math.ceil(row['high']+4.5)):
            s=e.state(x,y,z)
            if s.split('[')[0] in empty:continue
            top=block_top(y,s)
            if top<=row['low']+1e-7:faces.append((top,y,s))
            elif y<row['high']+4.5-1e-7:errors.append(['rail reserve blocked',x,y,z,s,row['low'],row['high']])
        if not faces:errors.append(['missing bearing',x,z]);continue
        top,y,state=max(faces)
        if row['high']-top>.8:errors.append(['bearing too far below rail',x,y,z,row['high']-top])
        low_gaps.append(row['low']-top);bearings[x,y,z]=state;clearance+=1
        for Y in range(y-1,y+1):
            s=e.state(x,Y,z)
            if s.split('[')[0] not in empty:structure[x,Y,z]=s
    data=json.loads((candidate/'rail-civil-geometry.json').read_text('utf8'))
    station_access_cells=set()
    for row in data.get('station_access_columns',[]):
        px,pz,h,footing=(row[k] for k in ('x','z','floor','footing'))
        if e.state(px,footing,pz).split('[')[0] not in SOIL:errors.append(['station footway lacks earth bearing',px,footing,pz])
        for Y in range(footing+1,h+4):
            state=e.state(px,Y,pz)
            if (Y<=h and state!='minecraft:stone_bricks') or (Y>h and state.split('[')[0] not in AIR):errors.append(['station footway surface or clearance',px,Y,pz,state])
            station_access_cells.add((px,Y,pz))
    exterior_footings=set()
    for row in data['pier_columns']:
        x,y,z=row['top'];bottom=row['footing'][1]
        for Y in range(bottom+1,y+1):
            s=e.state(x,Y,z)
            if s.split('[')[0] in empty:errors.append(['pier gap',x,Y,z])
            else:structure[x,Y,z]=s
            if row['kind']=='measured exterior fragment footing':exterior_footings.add((x,Y,z))
        if e.state(x,bottom,z).split('[')[0] not in SOIL:errors.append(['pier lacks measured earth bearing',x,bottom,z])
    # Solid contacts must have actual overlapping vertical faces: touching
    # half-slabs at a voxel corner is not a structural connection.
    def touches(p,q):
        if p[1]==q[1]:return min(block_top(p[1],structure[p]),block_top(q[1],structure[q]))>p[1]
        low,high=(p,q) if p[1]<q[1] else (q,p)
        return abs(block_top(low[1],structure[low])-high[1])<1e-7
    seeds=set()
    directions=[(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]
    for p,s in structure.items():
        for dx,dy,dz in directions:
            q=p[0]+dx,p[1]+dy,p[2]+dz
            if q in structure:continue
            try:other=e.state(*q)
            except (KeyError,FileNotFoundError):continue
            if other.split('[')[0] not in SOIL:continue
            if dy==1 and block_top(p[1],s)<q[1]:continue
            seeds.add(p);break
    distance={p:0 for p in seeds};queue=deque(seeds)
    while queue:
        p=queue.popleft()
        for dx,dy,dz in directions:
            q=p[0]+dx,p[1]+dy,p[2]+dz
            if q in structure and q not in distance and touches(p,q):distance[q]=distance[p]+1;queue.append(q)
    missing=[p for p in bearings if p not in distance]
    for p in missing:errors.append(['rail deck has no continuous earth load path',*p])
    # Exact existing devices, occupied rooms and current road-floor structures
    # remain intact; removing an old overhead fragment is a recorded exception.
    with np.load(candidate/'plan/network.npz') as f:d={k:f[k] for k in ('bounds','walk','grade2')}
    x,z,X,Z=map(int,d['bounds']);floor,_=road_blocks(d['grade2']);passage_changed=0
    tags={tuple(int(t[k]) for k in ('x','y','z')):t for t in nbtlib.load(candidate/'captured-devices.dat')['Devices']}
    buildings=json.loads((candidate/'plan/catalog.json').read_text('utf8'));room_index={}
    for row in buildings:
        b=row['occupied_bounds']
        if b[0]>X or b[3]<x or b[2]>Z or b[5]<z:continue
        for cx in range(b[0]//16,b[3]//16+1):
            for cz in range(b[2]//16,b[5]//16+1):room_index.setdefault((cx,cz),[]).append((row['id'],b))
    for p in tags:
        if e.state(*p)!=e.state(*p,original=True):errors.append(['device block changed',*p])
    for patch in (candidate/'delta').glob('*.npz'):
        with np.load(patch) as f:coords,ranges,at,before,after,palette=(f[k] for k in ('coordinates','ranges','indices','before','after','palette'))
        for k,(cx,cz) in enumerate(coords):
            lo,hi=ranges[k:k+2]
            yy,zz,xx=np.unravel_index(at[lo:hi],(448,16,16));yy-=128;xx+=cx*16;zz+=cz*16
            for px,py,pz,old,new in zip(xx,yy,zz,before[lo:hi],after[lo:hi]):
                j,i=pz-z,px-x
                for name,b in room_index.get((int(cx),int(cz)),[]):
                    if b[0]<=px<=b[3] and b[1]<=py<=b[4] and b[2]<=pz<=b[5]:errors.append(['retained occupied room changed',name,int(px),int(py),int(pz)])
                if d['walk'][j,i] and floor[j,i]-2<=py<=floor[j,i]+4:
                    if (int(px),int(py),int(pz)) in station_access_cells:continue
                    if (int(px),int(py),int(pz)) in exterior_footings and py<floor[j,i] and str(palette[old]).split('[')[0] in AIR|PLANTS|{'minecraft:light'}:continue
                    if base is not None and base.state(int(px),int(py),int(pz))==str(palette[new]):continue
                    if str(palette[new]).split('[')[0] not in AIR or py<=floor[j,i]:errors.append(['retained public passage changed',int(px),int(py),int(pz)])
                    else:passage_changed+=1
    stations=station_verify(candidate)
    errors.extend(stations['errors'])
    report=dict(errors=errors,track_columns=len(env),bearing_positions_checked=len(bearings),maximum_bearing_gap_below_lowest_native_rail=max(low_gaps,default=0),
        continuous_earth_load_paths=len(bearings)-len(missing),maximum_load_path_blocks=max((distance.get(p,0) for p in bearings),default=0),
        station_access=stations['stations'],devices_unchanged=len(tags),retained_public_headroom_fragments_removed=passage_changed,
        verified_base_public_columns_unchanged=base_public_columns,world_written=False,rendered_train_collision_checked=False)
    (candidate/'independent-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print({k:v for k,v in report.items() if k not in ('errors','station_access')},'errors',len(errors),errors[:8],flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True)
    if verify(p.parse_args().candidate)['errors']:raise SystemExit(1)
