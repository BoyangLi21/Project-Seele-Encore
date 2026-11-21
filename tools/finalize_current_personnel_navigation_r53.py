"""Walking-only nearest-lift tables and exact derived-file installation intent."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import argparse, collections, gzip, hashlib, heapq, json
import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import dijkstra


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--stage',default='current_personnel_navigation');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=a.out.resolve();folder=out/'combined';report=json.loads((folder/'REVIEW.json').read_text('utf8'))
    assert not report['issues']and not report['unknown_states']and np.asarray(report['goal_reachability']).all()and report['native_lift_landings']==25
    saved=np.load(folder/'CURRENT_GRAPH.npz');coords=saved['coords'];active=saved['active'];n=len(coords)
    walking=sparse.csr_matrix((saved['walking_weights'],saved['walking_indices'],saved['walking_indptr']),shape=(n,n))
    raw=(folder/'nerv_routes_r24.json.gz').read_bytes();graph=json.loads(gzip.decompress(raw))
    names=dict(command='指挥室入口',hangars='深机库登机廊',station='总部车站入口',pyramid_station='金字塔总部站',launch_station='原实验区站',observation='机库观察廊',dogma='终极教条前厅',experiment='LCL 实验层')
    for goal in graph['goals']:goal['name']=names[goal['id']]
    raw=gzip.compress(json.dumps(graph,ensure_ascii=False,separators=(',',':')).encode('utf8'),mtime=0);(folder/'nerv_routes_r24.json.gz').write_bytes(raw)
    def floor_key(q):
        x,y,z=map(int,q)
        if y>=70:return 'original_surface_pavilion/75'
        if y<-1150:return 'terminal/'+str(-1230 if abs(y+1230)<4 else y)
        if y<-970:return 'deep_hangar/'+str(min((-1088,-1014,-987),key=lambda t:abs(t-y)))
        if z<100 and -474<=y<=-432:return 'original_experiment/'+str(min((-468,-442),key=lambda t:abs(t-y)))
        if 442<=z<=546 and -575<=y<=-542:return 'headquarters_station/-559'
        if -577<=y<=-415 and 235<=z<=448:return 'pyramid/'+str(min((-554,-541,-535,-527,-516,-513,-512,-502,-499,-485,-481,-471,-457,-434,-433,-422),key=lambda t:abs(t-y)))
        return 'original_retained/'+str(y)
    keys=np.asarray([floor_key(q)for q in coords]);coo=walking.tocoo();legal=active[coo.row]&active[coo.col];same=legal&(keys[coo.row]==keys[coo.col])
    same_floor=sparse.csr_matrix((coo.data[same],(coo.row[same],coo.col[same])),shape=(n,n));walk=sparse.csr_matrix((coo.data[legal],(coo.row[legal],coo.col[legal])),shape=(n,n))
    landings=np.unique([r['node']for r in graph['named_lift_landings']]);assert len(graph['named_lift_landings'])==25 and active[landings].all()
    costs,pred,source=dijkstra(same_floor.T.tocsr(),directed=True,indices=landings,min_only=True,return_predecessors=True)
    pred[landings]=landings;source[landings]=landings
    fixed=np.isfinite(costs);transfer=np.zeros(n,bool);queue=[(float(costs[i]),int(i))for i in np.flatnonzero(fixed)];heapq.heapify(queue)
    backwards=walk.T.tocsr()
    while queue:
        distance,i=heapq.heappop(queue)
        if distance!=costs[i]:continue
        for k in range(backwards.indptr[i],backwards.indptr[i+1]):
            j=int(backwards.indices[k]);candidate=distance+backwards.data[k]
            if fixed[j]or candidate>=costs[j]:continue
            costs[j]=candidate;pred[j]=i;source[j]=source[i];transfer[j]=transfer[i]or keys[j]!=keys[i]or keys[j]!=keys[source[j]];heapq.heappush(queue,(float(candidate),j))
    table=[];unresolved=[]
    for i in range(n):
        if not active[i]or not np.isfinite(costs[i]):
            table.append(None)
            if active[i]:unresolved.append(coords[i].tolist())
            continue
        j=int(pred[i]);landing=int(source[i]);assert j>=0 and landing in landings and(j==i or walk[i,j]>0 and abs(int(coords[i,1]-coords[j,1]))<=1)
        assert transfer[i]or keys[i]==keys[j]==keys[landing]
        table.append(dict(next=coords[j].tolist(),nearest_landing=coords[landing].tolist(),walking_metres=float(costs[i]),floor_key=str(keys[i]),requires_floor_transfer=bool(transfer[i])))
    nearest=dict(graph_sha256=hashlib.sha256(raw).hexdigest(),same_floor=True,same_floor_schema=3,node_floor_keys=keys.tolist(),nodes=table,unresolved_coordinates=unresolved,native_verified=False,source='Current actual walking boundary edges only; same-floor landing preferred, existing stairs labelled; no native lift journey or TRAIN edge enters this nearest-lift table.')
    nearest_raw=gzip.compress(json.dumps(nearest,ensure_ascii=False,separators=(',',':')).encode('utf8'),mtime=0);(folder/'nearest_lift_paths_r44.json.gz').write_bytes(nearest_raw)
    # The separate NPC graph retains original floor nodes even when a player
    # needs a train to reach another facility. TRAIN is absent from this file.
    npc=dict(schema='projectseele.r53.current-personnel-walking.v1',dimension='projectseele:geofront',nodes=coords.tolist(),walking_edges=[[int(i),int(j),float(v)]for i,j,v in zip(coo.row,coo.col,coo.data)],native_lift_edges=graph['lift_edges'],native_lift_landings=graph['named_lift_landings'],train_edges=[],permission_policy=graph['permission_policy'],native_verified=False)
    npc_raw=gzip.compress(json.dumps(npc,ensure_ascii=False,separators=(',',':')).encode('utf8'),mtime=0);(folder/'r53_personnel_walking_graph.json.gz').write_bytes(npc_raw)
    files=[]
    for name in('nerv_routes_r24.json.gz','nearest_lift_paths_r44.json.gz','r53_personnel_walking_graph.json.gz'):
        target=world/name;before=target.read_bytes()if target.exists()else None;i=len(files)
        if before is not None:(folder/f'{i}.before.bin').write_bytes(before)
        after=(folder/name).read_bytes();(folder/f'{i}.after.bin').write_bytes(after)
        files.append(dict(target=str(target),before_exists=before is not None,before_file=f'{i}.before.bin',after_file=f'{i}.after.bin',before_sha256=None if before is None else hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(after).hexdigest()))
    evidence=dict(native_verified=False,ready_is_derived_installation_intent=True,node_count=n,current_active_player_nodes=int(active.sum()),actual_native_lift_landings=25,walking_only_nearest_table=True,stair_transfer_rows=int(transfer.sum()),active_nearest_lift_unresolved=len(unresolved),unresolved_use_preserved_local_lift_directory_without_train_walk_inference=True,player_train_edges=len(graph['transport_edges']),npc_train_edges=0,other_surface_navigation_files_untouched=True,graph_sha256=hashlib.sha256(raw).hexdigest(),nearest_sha256=hashlib.sha256(nearest_raw).hexdigest(),npc_walking_sha256=hashlib.sha256(npc_raw).hexdigest(),source_role_report=str(folder/'REVIEW.json'))
    plan=dict(schema='projectseele.r53.pyramid-exact-files.v1',stage=a.stage,world=str(world),world_written=False,files=files,unchanged_files=[dict(relative='personnel_lifts_r52.json',sha256=hashlib.sha256((world/'personnel_lifts_r52.json').read_bytes()).hexdigest()),dict(relative='native_transit_r28.json',sha256=hashlib.sha256((world/'native_transit_r28.json').read_bytes()).hexdigest())],evidence=evidence)
    (folder/'PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n','utf8');(folder/'FINAL_DERIVED_REPORT.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n','utf8');print(json.dumps(evidence,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
