"""Choose finite roadside piers for measured bridge members, offline only."""
import argparse,json
from pathlib import Path
from collections import deque
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from repair_hakone_underbridge_clearance import earth_paths,CONCRETE,FRAME,DIRECTIONS,save
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL
from map_pipeline.launch_protection import load
from map_pipeline.rail_civil_geometry import columns


def plan(a):
    C=a.candidate;e=Editor(C)
    cap=json.loads((C/'capture.json').read_text('utf8'));x,z,X,Z=cap['bounds_xz'];world=Path(cap['world'])
    with np.load(C/'plan/network.npz') as f:d={k:f[k] for k in f.files}
    devices={tuple(int(t[k]) for k in ('x','y','z')) for t in nbtlib.load(C/'captured-devices.dat')['Devices']}
    catalog=json.loads((C/'plan/catalog.json').read_text('utf8'));launch=load(world)
    curves=json.loads((C/'plan/native-curves.json').read_text('utf8'));trains=curves['trains']
    indexes=[i for i,r in enumerate(trains) if any(x-5<=p[0]<=X+5 and z-5<=p[2]<=Z+5 and -110<p[1]<310 for p in r['points'])]
    env=columns(trains,indexes,3.5,4.,max_vertical_spread=None)
    secondary=[]
    for kind,below,above,width in [('ropeway',10,1,3),('boats',1,6,5),('boat',1,6,5)]:
        rows=curves.get(kind,[])
        inds=[i for i,r in enumerate(rows) if any(x-6<=p[0]<=X+6 and z-6<=p[2]<=Z+6 for p in r['points'])]
        if inds:secondary.append((columns(rows,inds,width,width,max_vertical_spread=None),below,above))
    distance,nodes=earth_paths(e,[x,z,X,Z],return_nodes=True)
    targets={(r['pos'][0],r['pos'][1]+k,r['pos'][2]) for r in json.loads((C/'soffit-edits.json').read_text('utf8')) for k in (1,2)}
    initial=max(distance.get(p,1000000) for p in targets);piers=[];tried={}
    def footing(p):
        if p in tried:return tried[p]
        px,Y,pz=p;j,i=pz-z,px-x;result=None
        if d['walk'][j,i] or e.state(*p)!=CONCRETE:tried[p]=None;return None
        for yy in range(Y-1,max(-128,Y-48)-1,-1):
            q=px,yy,pz;s=e.state(*q)
            if s.split('[')[0] in SOIL:
                result=dict(top=list(p),footing=yy,soil_state=s);break
            if s.split('[')[0] not in AIR and s not in FRAME:break
            if q in devices or launch.chunk_mask(px//16,pz//16)[yy+128,pz%16,px%16]:break
            if any(all(b[k]<=q[k]<=b[k+3] for k in range(3)) for b in (r['occupied_bounds'] for r in catalog)):break
            r=env.get((px,pz))
            if r and yy+1>r['low'] and yy<r['high']+4.5:break
            if any((px,pz) in other and yy+1>other[px,pz]['low']-below and yy<other[px,pz]['high']+above for other,below,above in secondary):break
        tried[p]=result;return result
    while max(distance.get(p,1000000) for p in targets)>24:
        worst=max(sorted(targets),key=lambda p:distance.get(p,1000000));near={worst:0};queue=deque([worst]);choices=[]
        while queue:
            p=queue.popleft();steps=near[p]
            if abs(p[1]-worst[1])<=3:
                row=footing(p)
                if row:
                    cost=steps+p[1]-row['footing']
                    if cost<=24:choices.append((cost,steps,p,row))
            if steps>=20:continue
            for dx,dy,dz in DIRECTIONS:
                q=p[0]+dx,p[1]+dy,p[2]+dz
                if q in nodes and q not in near:near[q]=steps+1;queue.append(q)
        if not choices:raise ValueError(('No protected roadside pier within bounded span',worst,distance.get(worst)))
        _,_,p,row=min(choices,key=lambda r:r[:3]);px,Y,pz=p;piers.append(row)
        if len(piers)>96:raise ValueError('Too many piers; requires corridor redesign')
        queue=deque()
        for yy in range(row['footing']+1,Y+1):
            q=px,yy,pz;nodes.add(q)
            if e.state(*q).split('[')[0] in AIR:e.put(*q,CONCRETE)
            value=yy-row['footing']
            if value<distance.get(q,1000000):distance[q]=value;queue.append(q)
        while queue:
            p=queue.popleft()
            for dx,dy,dz in DIRECTIONS:
                q=p[0]+dx,p[1]+dy,p[2]+dz
                if q in nodes and distance[p]+1<distance.get(q,1000000):distance[q]=distance[p]+1;queue.append(q)
    save(a.out,piers)
    print('Planned',len(piers),'roadside piers; measured earth path',initial,'->',max(distance[p] for p in targets),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    plan(p.parse_args())
