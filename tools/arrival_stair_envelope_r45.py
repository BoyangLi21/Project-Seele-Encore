"""Retain complete measured stair flights and the supported landings they join."""
from collections import deque
from math import floor
from measure_world_r40 import properties
from prepare_school_hakone_native_r45 import ActualGeometry
from prepare_b2_stair_component_r45 import full_body_status

NORMAL={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}

def retained_stair_contract(world, seeds):
    geometry=ActualGeometry(world); found={}; queue=deque(tuple(r['position']) for r in seeds)
    while queue:
        q=queue.popleft()
        if q in found: continue
        state=world.block(q); p=properties(state or '')
        if not (state and state.partition('[')[0].endswith('_stairs') and p.get('half')=='bottom' and p.get('shape')=='straight'):
            raise RuntimeError(('Retained stair must have measured straight native geometry',q,state))
        dx,dz=NORMAL[p['facing']]; found[q]=state
        for d in ((dz,0,-dx),(-dz,0,dx),(dx,1,dz),(-dx,-1,-dz)):
            n=tuple(q[k]+d[k] for k in range(3))
            if world.block(n)==state: queue.append(n)
    groups={}
    for q,state in found.items():
        face=properties(state)['facing'];dx,dz=NORMAL[face]
        groups.setdefault((face,q[1]-dx*q[0]-dz*q[2],dz*q[0]-dx*q[2]),[]).append(q)
    body=set();bearing=set();lanes=[]
    for (face,_,_),qs in sorted(groups.items()):
        dx,dz=NORMAL[face];qs.sort(key=lambda q:dx*q[0]+dz*q[2])
        assert all(b==tuple(a[k]+(dx,1,dz)[k]for k in range(3))for a,b in zip(qs,qs[1:])),('Disconnected retained lane',qs)
        first,last=qs[0],qs[-1]
        lower=[first[0]+.5-1.1*dx,first[1],first[2]+.5-1.1*dz]
        upper=[[last[0]+.5+d*dx,last[1]+1,last[2]+.5+d*dz]for d in(1,2)]
        points=[lower]
        for x,y,z in qs:
            points.extend([[x+.5-.4*dx,y+.5,z+.5-.4*dz],[x+.5+.1*dx,y+1,z+.5+.1*dz]])
        points.extend(upper)
        for p in [lower,*upper]:
            for ox in(-.25,0,.25):
                for oz in(-.25,0,.25):
                    px,pz=p[0]+ox,p[2]+oz;q=(floor(px),floor(p[1]-.01),floor(pz));boxes=geometry.boxes(q)
                    if boxes is None or not any(q[0]+b[0]<=px<=q[0]+b[3] and q[2]+b[2]<=pz<=q[2]+b[5] and abs(q[1]+b[4]-p[1])<.001 for b in boxes):
                        raise RuntimeError(('Retained original stair landing has no measured full-datum bearing',p,q,world.block(q)))
                    bearing.add(q)
        for a,b in [(p,p)for p in points]+list(zip(points,points[1:])):
            y=max(a[1],b[1]);lo=[min(a[0],b[0])-.3,y+1e-6,min(a[2],b[2])-.3];hi=[max(a[0],b[0])+.3,y+1.8,max(a[2],b[2])+.3]
            body.update((x,y,z)for x in range(floor(lo[0]),floor(hi[0])+1)for y in range(floor(lo[1]),floor(hi[1])+1)for z in range(floor(lo[2]),floor(hi[2])+1))
        lanes.append(dict(facing=face,treads=qs,points=points,landings=[lower,*upper]))
    if geometry.unknown:raise RuntimeError(('Unknown retained stair producer shapes',sorted(geometry.unknown)))
    return dict(treads=found,body=body,bearing=bearing,lanes=lanes)

def verify_retained_stair_contract(image, contract):
    geometry=ActualGeometry(image)
    for q,state in contract['treads'].items():
        if image.block(q)!=state:raise RuntimeError(('Retained original tread changed',q,state,image.block(q)))
    for lane in contract['lanes']:
        points=lane['points']
        for p in points:
            if full_body_status(geometry,p)!='CLEAR':raise RuntimeError(('Complete retained stair body obstructed',p))
        for a,b in zip(points,points[1:]):
            if full_body_status(geometry,a,b)!='CLEAR':raise RuntimeError(('Complete retained stair sweep obstructed',a,b))
        for p in lane['landings']:
            if geometry.standing(p)!='STATIC_STANDING':raise RuntimeError(('Retained landing body/bearing failed',p))
    if geometry.unknown:raise RuntimeError(('Unknown retained stair final native shapes',sorted(geometry.unknown)))
    return dict(complete_lanes=len(contract['lanes']),original_treads=len(contract['treads']),body_cells=len(contract['body']),bearing_cells=len(contract['bearing']),native_walk=False)
