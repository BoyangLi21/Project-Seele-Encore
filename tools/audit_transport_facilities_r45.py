"""Current installed transport readback and same-floor lift-table proposal.

No apply entry point. Save reads use query_blocks through MeasuredWorld;
controller identity, closed doors, traffic progress and equipment are intact.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import math
from collections import Counter

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra,connected_components
from scipy.spatial import cKDTree

from audit_facility_transit_r44 import Geometry
from measure_world_r40 import MeasuredWorld, properties
from regional_voxels import canonical_state
from query_blocks import dimension_dir

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
OUT = ROOT/'artifacts/rebuild_r45/transport_facilities_sol_high'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def floor_key(q):
    """Commissioned facility floors; local thresholds may differ in height."""
    x,y,z=map(int,q)
    if z < 0:
        for key,lo,hi in [('hangar_observation',-370,-366),('hangar_boarding',-395,-393),('hangar_launch',-443,-441)]:
            if lo<=y<=hi:return key
        return f'hangar_connector/{y}'
    if -5<=x<=70 and 263<=z<=366:
        if -390<=y<=-387:return 'commander_office/lower'
        # The actual highest meeting room joins the reception lift through
        # its retained small stair at X17..28/Z306, not another elevator hop.
        if -342<=y<=-328 and 296<=z<=363:return 'commander_office/upper'
    if ((6<=x<=52 and 263<=z<=365)or(8<=x<=16 and 253<=z<=264))and -430<=y<=-422:
        return 'command/main_dais'
    for datum,name in [(-566,'terminal_dogma'),(-461,'pyramid/B1'),(-448,'pyramid/1F'),(-434,'pyramid/2F'),
                       (-420,'pyramid/3F'),(-406,'pyramid/4F'),(-392,'pyramid/5F'),(-378,'pyramid/6F'),(-364,'pyramid/7F'),
                       (-423,'command/main_dais'),(-409,'command/observation')]:
        if abs(y-datum)<=1:return name
    if y in (-466,-465):return 'hq_station_or_lower_apron'
    return f'hq_connector/{y}'


def same_floor_table(coords, valid, edge_clear, landings, floor_keys=None, stair_edges=(), audit_graph=None):
    """Prefer actual landings in the same authored use floor; no lift hops."""
    floor_keys=floor_keys or [str(q[1]) for q in coords]
    index = {tuple(map(int, q)): i for i, q in enumerate(coords)}
    row, col = [], []
    for i, q in enumerate(coords):
        if not valid[i]:
            continue
        x, y, z = map(int, q)
        for other in ((x+1, y, z), (x, y, z+1)):
            j = index.get(other)
            if j is not None and valid[j] and floor_keys[i]==floor_keys[j] and edge_clear(tuple(q), other):
                row.extend((i, j));col.extend((j, i))
    weights=[1.]*len(row)
    for i,j,weight in stair_edges:
        if valid[i] and valid[j] and floor_keys[i]==floor_keys[j]:
            row.append(i);col.append(j);weights.append(weight)
    graph = coo_matrix((weights, (row, col)), shape=(len(coords), len(coords))).tocsr()
    if audit_graph is not None:audit_graph['graph']=graph
    sources = [index[tuple(q)] for q in landings if tuple(q) in index and valid[index[tuple(q)]]]
    if not sources:
        raise RuntimeError('No measured actual layer-door landing survived')
    cost, prev, origin = dijkstra(graph, indices=sources, directed=False,
                                  min_only=True, return_predecessors=True)
    metres=np.full(len(coords),np.inf);metres[sources]=0.
    for i in np.argsort(cost):
        if not math.isfinite(cost[i]):break
        if prev[i]>=0:
            parent=int(prev[i]);metres[i]=metres[parent]+float(np.linalg.norm(coords[i]-coords[parent]))
    table = []
    for i in range(len(coords)):
        if not valid[i] or origin[i] < 0 or not math.isfinite(cost[i]):
            table.append(None);continue
        target = int(prev[i]) if prev[i] >= 0 else i
        landing = coords[int(origin[i])].tolist()
        assert floor_keys[i]==floor_keys[int(origin[i])]==floor_keys[target]
        table.append(dict(nearest_landing=landing, walking_cost=float(cost[i]),
                          walking_metres=float(metres[i]), next=coords[target].tolist(),floor_key=floor_keys[i]))
    return table, len(row)//2


def walking_fallback(coords,valid,edge_clear,landings,table,stair_edges):
    """Fill only unresolved rows, honestly labelling an existing stair transfer."""
    unrestricted,_=same_floor_table(coords,valid,edge_clear,landings,
                                    ['actual_walking_network']*len(coords),stair_edges)
    replaced=0;index={tuple(q):i for i,q in enumerate(coords)};edge_cost={}
    for i,row in enumerate(table):
        if row is not None:
            row['requires_floor_transfer']=False
        elif unrestricted[i] is not None:
            replacement=unrestricted[i]
            parent=index[tuple(replacement['next'])]
            edge_cost[i]=replacement['walking_cost']-unrestricted[parent]['walking_cost']
            replacement['floor_key']=floor_key(coords[i])
            replacement['requires_floor_transfer']=True
            replacement['landing_floor_key']=floor_key(replacement['nearest_landing'])
            table[i]=replacement;replaced+=1
    # On entering a floor with a nearer local door, its same-floor policy
    # takes precedence. Recompute fallback labels/metres from that real chain,
    # rather than advertising a different global root that will not be used.
    completed={i for i,row in enumerate(table)if row is None or not row['requires_floor_transfer']}
    for seed,row in enumerate(table):
        if seed in completed:continue
        chain=[];seen=set();current=seed
        while current not in completed:
            if current in seen:raise RuntimeError('Mixed nearest-lift policy introduced a cycle')
            seen.add(current);chain.append(current);current=index[tuple(table[current]['next'])]
        for i in reversed(chain):
            parent=index[tuple(table[i]['next'])];p=table[parent]
            assert p is not None
            table[i]['nearest_landing']=p['nearest_landing']
            table[i]['landing_floor_key']=floor_key(p['nearest_landing'])
            table[i]['walking_metres']=p['walking_metres']+float(np.linalg.norm(coords[i]-coords[parent]))
            table[i]['walking_cost']=p['walking_cost']+edge_cost[i]
            completed.add(i)
    return replaced


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,default=WORLD)
    ap.add_argument('--out',type=Path,default=OUT/'same_floor_lift_v7')
    ap.add_argument('--interfaces',type=Path,default=OUT/'facility_landings/lifts.json')
    ap.add_argument('--shape-library',type=Path);ap.add_argument('--shape-inheritance',type=Path);a=ap.parse_args()
    assert not a.out.exists(), 'Keep audit epochs immutable'
    graph_path=a.world/'nerv_routes_r24.json.gz'
    with gzip.open(graph_path,'rt',encoding='utf8') as f:data=json.load(f)
    coords=np.asarray([r[:3] for r in data['nodes']],dtype=int)
    w=MeasuredWorld(a.world)
    for x,y,z in coords:
        w.box((int(x),int(y)-1,int(z)),(int(x),int(y)+1,int(z)))
    w.load();g=Geometry(w);shape_file=a.world/'native_collision_shapes.json'
    if a.shape_library:
        assert a.shape_inheritance,'A measured class-bound inheritance proof is required'
        inherited=json.loads(a.shape_inheritance.read_text('utf8'));base=inherited['base'];derived=inherited['derived_after']
        assert Path(base['path']).resolve()==shape_file.resolve()and sha(shape_file)==base['sha256']
        assert a.shape_library.resolve()==Path(derived['path']).resolve()and sha(a.shape_library)==derived['sha256']
        for row in inherited['classes']:
            assert sha(Path(row['original']['path']))==row['original']['sha256']==row['current']['sha256']==sha(Path(row['current']['path']))
        old=json.loads(shape_file.read_text('utf8'));new=json.loads(a.shape_library.read_text('utf8'))
        added={row['state']for row in inherited['additional_states']}
        assert len(added)==4 and set(new)==set(old)|added and not set(old)&added
        assert all(new[k]==value for k,value in old.items())
        assert all(new[row['state']]==row['after_exact_native_AABBs']for row in inherited['additional_states'])
        shape_file=a.shape_library;g.shapes={canonical_state(k):v for k,v in new.items()}
    gates=json.loads((a.world/'r44_public_station_gates.json').read_text('utf8'))['gates']
    controlled={}
    for gate in gates:
        q=tuple(gate['position']);state=w.block(q)
        if state is not None and state.partition('[')[0]==gate['closed_state'].partition('[')[0] \
                and properties(state).get('facing')==properties(gate['closed_state']).get('facing'):
            controlled[q]=canonical_state(gate['open_state'])
    sliding=a.world/'.projectseele_command_sliding_doors_r01.json'
    operated_doors=[]
    if sliding.exists():
        for door in json.loads(sliding.read_text('utf8')).get('doors',[]):
            observed=[]
            for point in door.get('aperture',[]):
                q=tuple(point);state=w.block(q)
                if state in ('minecraft:barrier','minecraft:air'):
                    controlled[q]='minecraft:air';observed.append(dict(pos=q,state=state))
            if observed:operated_doors.append(dict(id=door['id'],aperture=observed,buttons=door.get('buttons',[]),
                meaning='Actual registered moving door; opening/authorization remains a live equipment condition, never a world deletion'))
    original_get=w.get
    w.get=lambda x,y,z:controlled.get((int(x),int(y),int(z)),original_get(x,y,z))
    standing_cache={};status=[]
    for q in coords:
        key=tuple(w.get(q[0],q[1]+dy,q[2]) for dy in (-1,0,1))
        if key not in standing_cache:standing_cache[key]=g.standing(tuple(q))['status']
        status.append(standing_cache[key])
    # Retain measured stair interfaces only when their source/target complete
    # footprint states match the frozen graph that proved native boundaries.
    frozen=ROOT/'artifacts/repair_r43/world_composition/navigation'
    assert sha(frozen/'nerv_routes_r24.json.gz')==sha(graph_path),'Frozen graph identity differs'
    with np.load(frozen/'walkable_graph.npz') as saved:
        oldcoords=saved['coords'];oldgraph=csr_matrix((saved['weights'],saved['indices'],saved['indptr']),shape=(len(oldcoords),len(oldcoords)))
    distance,original=cKDTree(oldcoords).query(coords);assert not np.any(distance>.01)
    candidate=oldgraph[original][:,original].tocoo();dy=coords[candidate.row,1]-coords[candidate.col,1]
    with np.load(frozen/'measured_public_space.npz') as saved:
        oldblocks=saved['blocks'];oldpal=saved['palette'];oldlo=saved['lo']
    def unchanged(q):
        for dy in (-1,0,1):
            x,y,z=map(int,np.asarray(q)+[0,dy,0]-oldlo)
            if canonical_state(str(oldpal[oldblocks[y,z,x]]))!=w.get(q[0],q[1]+dy,q[2]):return False
        return True
    unchanged_nodes=np.asarray([unchanged(q) for q in coords],dtype=bool)
    valid=np.asarray([s=='STATIC_STANDING' or s=='SHAPED_STAIR_INTERFACE' and unchanged_nodes[i] for i,s in enumerate(status)],dtype=bool)
    stair_edges=[(int(i),int(j),float(weight)) for i,j,weight,d in zip(candidate.row,candidate.col,candidate.data,dy)
                 if abs(d)==1 and unchanged_nodes[i] and unchanged_nodes[j]]
    del oldblocks,oldgraph,candidate
    actual_lifts=json.loads(a.interfaces.read_text('utf8'))
    node_set={tuple(q) for q in coords}
    landing_interfaces=[dict(lift=lift['id'],controller=s['controller'],landing=s['handoff'],
                            outside_call=s['outside_call'],controller_nbt=s['controller_nbt'])
                        for lift in actual_lifts for s in lift['landings'] if tuple(s['handoff']) in node_set]
    landings=[s['landing'] for s in landing_interfaces]
    floor_keys=[floor_key(q) for q in coords]
    graph_audit={}
    table,edges=same_floor_table(coords,valid,g.edge_clear,landings,floor_keys,stair_edges,graph_audit)
    same_use_floor=[r is not None for r in table]
    fallback_rows=walking_fallback(coords,valid,g.edge_clear,landings,table,stair_edges)
    a.out.mkdir(parents=True)
    target=a.world/'nearest_lift_paths_r44.json.gz'
    payload=dict(graph_sha256=sha(graph_path),same_floor=True,same_floor_schema=3,node_floor_keys=floor_keys,nodes=table,
        routing_policy='Prefer reachable current use-floor landing; otherwise explicitly describe actual walking/stair transfer to another real landing',
        scope='Current installed graph; same authored facility use floor includes measured local stairs/thresholds; original unchanged stair boundaries inherited, live fare-gate permission separate',
        landing_interfaces=landing_interfaces,operating_doors=operated_doors,native_verified=False,visual_reviewed=False)
    after=a.out/'nearest_lift_paths_r44.after.json.gz'
    with gzip.GzipFile(filename=str(after),mode='wb',mtime=0) as f:
        f.write(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf8'))
    proposal=dict(target=str(target.resolve()),expected_sha256=sha(target) if target.exists() else None,
        expected_absent=not target.exists(),after_file=str(after.resolve()),after_sha256=sha(after),
        inverse_file=None,rollback='Delete only if installed bytes still match after_sha256' if not target.exists() else 'Restore exact before bytes',
        graph_precondition=dict(path=str(graph_path.resolve()),sha256=sha(graph_path)),
        shape_precondition=dict(path=str(shape_file.resolve()),sha256=sha(shape_file)),
        gate_precondition=dict(path=str((a.world/'r44_public_station_gates.json').resolve()),sha256=sha(a.world/'r44_public_station_gates.json')),
        region_preconditions=[dict(path=str(p.resolve()),sha256=sha(p)) for p in sorted({
            dimension_dir(a.world,w.dimension)/'region'/f'r.{cx//32}.{cz//32}.mca'
            for cx,cz in w.selected})])
    if a.shape_library:
        proposal['shape_base_precondition']=dict(path=str((a.world/'native_collision_shapes.json').resolve()),sha256=sha(a.world/'native_collision_shapes.json'))
        proposal['shape_inheritance']=dict(path=str(a.shape_inheritance.resolve()),sha256=sha(a.shape_inheritance))
    if target.exists():
        before=a.out/'nearest_lift_paths_r44.before.json.gz';before.write_bytes(target.read_bytes());proposal['inverse_file']=str(before.resolve())
    (a.out/'reversible_file_proposal.json').write_text(json.dumps(proposal,indent=2),'utf8')
    report=dict(world=str(a.world.resolve()),nodes=len(coords),same_floor_rows=sum(same_use_floor),fallback_rows=fallback_rows,
        unavailable_nodes=sum(r is None for r in table),measured_horizontal_edges=edges,
        standing_statuses=dict(Counter(status)),unknown_shapes=sorted(g.unknown),
        valid_landings=[q for q in landings if tuple(q) in {tuple(coords[i]) for i,r in enumerate(table) if r is not None}],
        actual_landing_interfaces=landing_interfaces,interfaces_sha256=sha(a.interfaces),
        no_world_writes=True,static_geometry_only=True,native_verified=False,visual_reviewed=False,
        routes_sha256=sha(graph_path),nearest_table_sha256=sha(after),proposal=proposal,
        invalid_coordinates=[coords[i].tolist() for i,s in enumerate(status) if s!='STATIC_STANDING'])
    report['floor_coverage']=[dict(floor=key,nodes=sum(k==key for k in floor_keys),
        reachable=sum(k==key and r is not None for k,r in zip(floor_keys,table)),
        same_use_floor=sum(k==key and same_use_floor[i]for i,k in enumerate(floor_keys)),
        walking_stair_transfer=sum(k==key and r is not None and r['requires_floor_transfer']for k,r in zip(floor_keys,table)),
        missing=sum(k==key and r is None for k,r in zip(floor_keys,table)),
        landing_roots=[r['nearest_landing'] for i,r in enumerate(table) if r is not None and r['next']==coords[i].tolist() and floor_keys[i]==key]) for key in sorted(set(floor_keys))]
    _,labels=connected_components(graph_audit['graph'],directed=False)
    null_components=[]
    for label in np.unique(labels):
        selected=np.flatnonzero(labels==label)
        if table[int(selected[0])] is not None:continue
        points=coords[selected];key=floor_keys[int(selected[0])]
        null_components.append(dict(component=int(label),floor=key,nodes=len(selected),bounds=[points.min(0).tolist(),points.max(0).tolist()],
            standing_statuses=dict(Counter(status[int(i)]for i in selected)),
            reason='NO_REGISTERED_LANDING_ON_THIS_USE_FLOOR'if not any(floor_key(q)==key for q in landings)
                else 'DISCONNECTED_FROM_REAL_LANDING_IN_CURRENT_FLOOR_GEOMETRY',
            examples=[dict(pos=coords[i].tolist(),states=[w.get(coords[i,0],coords[i,1]+dy,coords[i,2])for dy in (-1,0,1)])for i in selected[:8]],
            repair_permitted=False,native_required=True))
    (a.out/'unreached_floor_components.json').write_text(json.dumps(null_components,ensure_ascii=False,indent=2),'utf8')
    (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('proposal','invalid_coordinates','valid_landings','actual_landing_interfaces')}))


if __name__=='__main__':main()
