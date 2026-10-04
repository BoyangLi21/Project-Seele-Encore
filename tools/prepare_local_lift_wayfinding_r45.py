"""Supplement only the three commissioned landings outside the HQ graph.

Arrival concourse, surface gateway and surface transit stay separate physical
walking components; neither a train ride nor an elevator is a walking edge.
"""
from pathlib import Path
import nbtlib
import argparse,gzip,json,math,hashlib
import numpy as np
from audit_transport_facilities_r45 import same_floor_table,sha,OUT,WORLD
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry


def bound_interfaces(world,path):
    """Non-default saves require their own UUID/seed/region/full-device capture."""
    from query_blocks import iter_block_entities
    data=json.loads(path.read_text('utf8'))
    if world.resolve()==WORLD.resolve() and isinstance(data,list):return data
    if not isinstance(data,dict)or data.get('schema')!='projectseele.transport-interface-snapshot-r45.v1':
        raise ValueError('Candidate interface snapshot schema required')
    if Path(data['world']).resolve()!=world.resolve():raise ValueError('Interface world path mismatch')
    actual_id=str(nbtlib.load(world/'dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat')['data']['WorldUUID'])
    actual_seed=int(nbtlib.load(world/'level.dat')['Data']['WorldGenSettings']['seed'])
    if data['world_uuid']!=actual_id or data['seed']!=actual_seed:raise ValueError('Interface UUID/seed mismatch')
    if not data.get('region_preconditions')or not data.get('input_sources'):raise ValueError('Unbound interface provenance')
    for row in data['region_preconditions']:
        p=Path(row['path']).resolve()
        if not p.is_relative_to(world.resolve())or sha(p)!=row['sha256']:raise ValueError('Interface region mismatch')
    for row in data['input_sources']:
        if sha(Path(row['path']))!=row['sha256']:raise ValueError('Device source epoch mismatch')
    shape=world/'native_collision_shapes.json'
    if sha(shape)!=data['native_shapes_sha256']:raise ValueError('Interface native shape epoch mismatch')
    lifts=data['interfaces'];points={tuple(s['controller']) for lift in lifts for s in lift['landings']}
    if len(lifts)!=7 or len(points)!=24:raise ValueError('Original7lift/24stop identity incomplete')
    lo=tuple(min(q[i]for q in points)for i in range(3));hi=tuple(max(q[i]for q in points)for i in range(3))
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi,selected_chunks={(q[0]//16,q[2]//16)for q in points}))
    for lift in lifts:
        for stop in lift['landings']:
            q=tuple(stop['controller']);tag=tags.get(q)
            if tag is None or tag!=nbtlib.parse_nbt(stop['actual_controller_nbt']):raise ValueError('Full controller NBT changed')
    return lifts


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,default=WORLD)
    ap.add_argument('--out',type=Path,default=OUT/'local_ports_v1')
    ap.add_argument('--interfaces',type=Path);a=ap.parse_args();assert not a.out.exists()
    if a.world.resolve()!=WORLD.resolve() and a.interfaces is None:ap.error('Non-default world requires explicit bound --interfaces')
    interfaces=a.interfaces or OUT/'facility_landings/lifts.json'
    lifts=bound_interfaces(a.world,interfaces)
    root_specs=[s for l in lifts for s in l['landings'] if tuple(s['controller']) in
                {(-368,-466,750),(-368,81,750),(130,75,269)}]
    assert len(root_specs)==3
    # Explicit fixed-floor lobbies measured by the complete current interface
    # audit. Surface-transit approach is the authored R40 route, including its
    # street stair; its exact mask replaces a guessed rectangular walk region.
    corridors=json.loads((a.world/'surface_lift_access_r40.json').read_text('utf8'))['walk_nodes'][0]['path']
    scopes=[]
    for s in root_specs:
        q=s['handoff'];key='gateway/arrival' if q[1]<0 else 'gateway/surface' if q[0]<0 else 'surface_transit/entrance'
        cells=set()
        for x in range(q[0]-12,q[0]+13):
            for z in range(q[2]-12,q[2]+13):cells.add((x,q[1],z))
        if q[0]>0:
            for start,finish in zip(corridors,corridors[1:]):
                for t in np.linspace(0,1,max(2,int(np.linalg.norm(np.array(finish)-start)*3)+1)):
                    x,y,z=np.floor(np.array(start)*(1-t)+np.array(finish)*t).astype(int)
                    cells.update((int(x+dx),int(y+dy),int(z+dz)) for dx in range(-2,3) for dz in range(-2,3) for dy in (-1,0,1))
        scopes.append((key,s,cells))
    coords=np.array(sorted(set.union(*(cells for _,_,cells in scopes))),dtype=int)
    keys={q:key for key,_,cells in scopes for q in cells};floor_keys=[keys[tuple(q)]for q in coords]
    w=MeasuredWorld(a.world)
    for q in coords:w.box(tuple(q-[0,1,0]),tuple(q+[0,1,0]))
    w.load();g=Geometry(w);status=[g.standing(tuple(q))['status']for q in coords]
    valid=np.array([s in ('STATIC_STANDING','SHAPED_STAIR_INTERFACE')for s in status])
    index={tuple(q):i for i,q in enumerate(coords)};stairs=[]
    for i,q in enumerate(coords):
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            for dy in (-1,1):
                p=tuple(q+[dx,dy,dz]);j=index.get(p)
                if j is None or not valid[i]or not valid[j]:continue
                if not any('stairs[' in (w.get(v[0],v[1]-1,v[2])or'')for v in (q,p)):continue
                # The native floor parser's shared-boundary footprint check.
                # Stair motion is still explicitly unverified in native play.
                clear=True
                for v,direction in ((q,(dx,dz)),(p,(-dx,-dz))):
                    axis=0 if direction[0]else 2;tangent=2 if direction[0]else 0;positive=sum(direction)>0
                    for h,height,minimum in ((0,1.79,.6),(1,.79,.01)):
                        boxes=g.boxes(w.get(v[0],v[1]+h,v[2]))
                        if boxes is None or any(b[tangent]<.795 and b[tangent+3]>.205
                            and (b[axis+3]>.795 if positive else b[axis]<.205)
                            and b[4]>minimum and b[1]<height for b in boxes):clear=False
                if clear:stairs.append((i,j,math.sqrt(2)))
    landings=[s['handoff']for s in root_specs]
    table,edges=same_floor_table(coords,valid,g.edge_clear,landings,floor_keys,stairs)
    retained=[i for i,r in enumerate(table)if r is not None]
    exported_index={tuple(coords[i]):j for j,i in enumerate(retained)}
    graph=dict(version=2,dimension=w.dimension,goals=[dict(id='local_lift',name='本处电梯入口')],
        nodes=[coords[i].tolist()+[exported_index[tuple(table[i]['next'])]]for i in retained],
        source='Three actual commissioned local landing masks; no inter-facility walking or teleport link')
    a.out.mkdir(parents=True)
    def save(name,data):
        p=a.out/name
        with gzip.GzipFile(filename=str(p),mode='wb',mtime=0)as f:f.write(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf8'))
        return p
    gp=save('local_lift_routes_r45.json.gz',graph)
    tp=save('local_nearest_lift_paths_r45.json.gz',dict(graph_sha256=sha(gp),same_floor=True,same_floor_schema=2,
        node_floor_keys=[floor_keys[i]for i in retained],nodes=[table[i]for i in retained],landing_interfaces=root_specs,native_verified=False))
    plans=[]
    from query_blocks import dimension_dir
    preconditions=[dict(path=str(p.resolve()),sha256=sha(p))for p in sorted({
        dimension_dir(a.world,w.dimension)/'region'/f'r.{cx//32}.{cz//32}.mca'for cx,cz in w.selected})]
    for p in (gp,tp):
        target=a.world/p.name;assert not target.exists()
        plans.append(dict(target=str(target.resolve()),expected_absent=True,expected_sha256=None,
            after_file=str(p.resolve()),after_sha256=sha(p),inverse_file=None,region_preconditions=preconditions,
            rollback='Delete only when installed bytes still match after_sha256'))
    report=dict(world=str(a.world.resolve()),interfaces_source=str(interfaces.resolve()),interfaces_sha256=sha(interfaces),nodes=len(coords),reachable=sum(r is not None for r in table),
        missing=sum(r is None for r in table),unknown_shapes=sorted(g.unknown),root_landings=landings,
        coverage=[dict(floor=key,root=s['handoff'],nodes=sum(k==key for k in floor_keys),
            reachable=sum(k==key and r is not None for k,r in zip(floor_keys,table)))for key,s,_ in scopes],
        proposals=plans,world_written=False,native_verified=False,visual_reviewed=False)
    (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print({k:v for k,v in report.items()if k!='proposals'})


if __name__=='__main__':main()
