"""Export the measured R52 graph and walking-only nearest-lift routes.

This installs derived files only. Door permission and real rides remain native
acceptance tasks; a TRAIN edge never represents NPC walking or teleportation.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse,gzip,hashlib,heapq,json,msvcrt
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import dijkstra
from r52_spatial_plan import BASE
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace


def sha(raw):return hashlib.sha256(raw).hexdigest()


def floor_key(point):
    x,y,z=map(int,point)
    if y>0:return 'surface/'+str(75 if 70<=y<=81 else y)
    if z<100 and -480<=y<=-420:return 'original_laboratory/'+str(min((-468,-442),key=lambda a:abs(a-y)))
    if y<-790:return 'terminal/'+str(-846 if abs(y+846)<=3 else y)
    if y<-577:
        floor=min((-704,-630,-603),key=lambda a:abs(a-y))
        return 'hangar/'+str(floor if abs(floor-y)<=3 else y)
    floors=(-559,-554,-541,-535,-527,-516,-513,-512,-502,-499,-485,-481,-471,-457,-433)
    floor=min(floors,key=lambda a:abs(a-y))
    return 'headquarters/'+str(floor if abs(floor-y)<=2 else y)


def encode(document):return gzip.compress(json.dumps(document,ensure_ascii=False,separators=(',',':')).encode('utf8'),mtime=0)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--revision',default='export');args=ap.parse_args()
    assert args.revision.replace('_','').replace('-','').isalnum(), 'Simple revision directory required'
    folder=BASE/'navigation_rebuild/combined';out=BASE/'navigation_rebuild'/args.revision;out.mkdir(exist_ok=True)
    assert not(out/'APPLIED.json').exists(),'Do not replay an installed derived migration'
    review=json.loads((folder/'REVIEW.json').read_text('utf8'));saved=np.load(folder/'CURRENT_GRAPH.npz')
    assert not review['issues']and not review['missing_shapes']and np.asarray(review['goal_reachability']).all()
    raw=saved['coords'];keep=saved['kept'];coords=raw[keep];size=len(coords);assert 0<size<=500000
    remap=np.full(len(raw),-1,np.int32);remap[keep]=np.arange(size)
    walking=sparse.csr_matrix((saved['walking_weights'],saved['walking_indices'],saved['walking_indptr']),shape=(len(raw),len(raw)))[keep][:,keep].tocsr()
    graph=sparse.csr_matrix((saved['graph_weights'],saved['graph_indices'],saved['graph_indptr']),shape=(len(raw),len(raw)))[keep][:,keep].tocsr()
    goals=[dict(g,node=int(remap[g['node']]))for g in review['goals']];assert all(g['node']>=0 for g in goals)
    # Search the reversed directed graph so every predecessor is the actual
    # next step towards a goal, including explicitly directional transit.
    distances,parents=dijkstra(graph.T.tocsr(),directed=True,indices=[g['node']for g in goals],return_predecessors=True)
    assert np.isfinite(distances).all()
    for i,g in enumerate(goals):parents[i,g['node']]=g['node']
    assert (parents>=0).all()
    for i in range(len(goals)):
        moving=np.flatnonzero(parents[i]!=np.arange(size));target=parents[i,moving]
        assert np.all(graph[moving,target].A1>0)and np.all(distances[i,target]<distances[i,moving])
    lifts=[dict(e,a=int(remap[e['a']]),b=int(remap[e['b']]))for e in review['lift_edges']]
    landings=[dict(e,node=int(remap[e['node']]))for e in review['lift_landings']]
    assert len(landings)==27 and all(e['node']>=0 for e in landings)
    transport=[dict(e,**{'from':int(remap[e['from']]),'to':int(remap[e['to']])})for e in review['transport_edges']]
    names={'station':'总部入口层','pyramid_station':'NERV 总部站 · U2','launch_station':'原试验区车站 · U2'}
    goals=[dict(g,name=names.get(g['id'],g['name']))for g in goals]
    payload=dict(version=2,dimension='projectseele:geofront',r52_navigation=True,goals=goals,
        nodes=np.column_stack((coords,parents.T)).tolist(),lift_edges=lifts,lift_landings=[coords[e['node']].tolist()for e in landings],
        named_lift_landings=landings,transport_edges=transport,
        source='Current measured R52 floors, complete native collision shapes, actual 7 lifts/27 landings and preserved U2 train service.',
        native_verified=False,permission_policy='Declared reader apertures require actual credentials; no access grant is encoded.')
    graph_raw=encode(payload)
    keys=np.asarray([floor_key(q)for q in coords]);coo=walking.tocoo();same=keys[coo.row]==keys[coo.col]
    same_floor=sparse.coo_matrix((coo.data[same],(coo.row[same],coo.col[same])),shape=walking.shape).tocsr()
    lift_ids=np.unique([e['node']for e in landings])
    costs,pred,sources=dijkstra(same_floor.T.tocsr(),directed=True,indices=lift_ids,min_only=True,return_predecessors=True)
    metres=np.full(size,np.inf);metres[lift_ids]=0.;pred[lift_ids]=lift_ids
    for i in np.argsort(costs):
        if not np.isfinite(costs[i]):break
        if pred[i]!=i:metres[i]=metres[pred[i]]+float(np.linalg.norm(coords[i]-coords[pred[i]]))
    fixed=np.isfinite(costs);transfer=np.zeros(size,bool);queue=[(float(costs[i]),int(i))for i in np.flatnonzero(fixed)];heapq.heapify(queue)
    backwards=walking.T.tocsr()
    # Keep same-floor solutions fixed. A stair fallback attaches to an already
    # routed walking tree, which cannot cycle back through a different lift.
    while queue:
        distance,i=heapq.heappop(queue)
        if distance!=costs[i]:continue
        for at in range(backwards.indptr[i],backwards.indptr[i+1]):
            j=int(backwards.indices[at]);candidate=distance+backwards.data[at]
            if fixed[j]or candidate>=costs[j]:continue
            costs[j]=candidate;pred[j]=i;sources[j]=sources[i];metres[j]=metres[i]+float(np.linalg.norm(coords[i]-coords[j]))
            transfer[j]=transfer[i]or keys[j]!=keys[i]or keys[j]!=keys[sources[j]];heapq.heappush(queue,(float(candidate),j))
    table=[];unresolved=[]
    for i in range(size):
        if not np.isfinite(costs[i]):table.append(None);unresolved.append(coords[i].tolist());continue
        j=int(pred[i]);landing=int(sources[i]);assert j>=0 and landing in lift_ids
        assert j==i or(walking[i,j]>0 and abs(int(coords[i,1])-int(coords[j,1]))<=1)
        assert transfer[i]or keys[i]==keys[j]==keys[landing]
        table.append(dict(next=coords[j].tolist(),nearest_landing=coords[landing].tolist(),walking_metres=float(metres[i]),
            floor_key=str(keys[i]),requires_floor_transfer=bool(transfer[i])))
    nearest=dict(graph_sha256=sha(graph_raw),same_floor=True,same_floor_schema=3,node_floor_keys=keys.tolist(),nodes=table,
        unresolved_coordinates=unresolved,native_verified=False,source='Actual walking edges only; same-floor landing preferred; stairs explicitly labelled; no lift or train hop.')
    encoded={'nerv_routes_r24.json.gz':graph_raw,'nearest_lift_paths_r44.json.gz':encode(nearest)}
    for name,body in encoded.items():(out/name).write_bytes(body)
    report=dict(world_written=False,native_verified=False,nodes=size,goals=len(goals),lift_landings=len(landings),
        actual_train_links=len(transport),nearest_lift_unresolved=len(unresolved),walking_stair_transfer_rows=int(transfer.sum()),
        files={name:sha(body)for name,body in encoded.items()},source_graph_sha256=sha((folder/'CURRENT_GRAPH.npz').read_bytes()))
    if args.apply:
        lock=acquire_world_lock();before={};written=[];world=BASE/'WORLD_R52'
        try:
            for name in encoded:before[name]=(world/name).read_bytes();(out/('before_'+name)).write_bytes(before[name])
            for name,body in encoded.items():atomic_replace(world/name,body);written.append(name);assert(world/name).read_bytes()==body
        except BaseException:
            for name in reversed(written):atomic_replace(world/name,before[name])
            raise
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
        report['world_written']=True
    (out/('APPLIED.json'if args.apply else'PLAN.json')).write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
