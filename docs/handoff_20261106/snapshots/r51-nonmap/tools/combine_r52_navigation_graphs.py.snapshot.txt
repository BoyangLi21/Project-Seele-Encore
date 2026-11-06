"""Root joins measured floor graphs using actual original lift and train interfaces.

Only candidate artifacts are written. Native use and final installation remain separate.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import gzip,hashlib,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import dijkstra,connected_components
from scipy.spatial import cKDTree
from r52_spatial_plan import BASE
from query_blocks import iter_selected_sections
from prepare_r52_navigation_components import SCOPES


def minimum_edge_graph(rows, cols, weights, size):
    """Overlapping measured scopes describe the same edge, not parallel tolls."""
    if not rows:
        return sparse.csr_matrix((size, size), dtype=float)
    keys=np.asarray(rows,dtype=np.int64)*size+np.asarray(cols,dtype=np.int64)
    order=np.argsort(keys,kind='stable');keys=keys[order]
    first=np.r_[0,np.flatnonzero(keys[1:]!=keys[:-1])+1]
    unique=keys[first];cost=np.minimum.reduceat(np.asarray(weights,dtype=float)[order],first)
    return sparse.coo_matrix((cost,(unique//size,unique%size)),shape=(size,size)).tocsr()


def main():
    world=BASE/'WORLD_R52';out=BASE/'navigation_rebuild/combined';out.mkdir(exist_ok=True)
    components=[];all_coordinates=[]
    for name in SCOPES:
        path=BASE/'navigation_rebuild/components'/name/'walkable_graph.npz';d=np.load(path);coords=d['coords'].astype(np.int32)
        graph=sparse.csr_matrix((d['weights'],d['indices'],d['indptr']),shape=(len(coords),len(coords)))
        components.append((coords,graph));all_coordinates.append(coords)
    migrated=np.load(BASE/'navigation_rebuild/ORIGINAL_NODE_MIGRATION.npz');retained=migrated['current'][migrated['valid_original_indices']].astype(np.int32)
    outside=np.ones(len(retained),bool)
    for low,high in SCOPES.values():outside&=~((retained>=low)&(retained<=high)).all(axis=1)
    retained=retained[outside]
    transit=json.loads((world/'native_transit_r28.json').read_text('utf8'));rail_points=np.concatenate([np.floor(r['points']).astype(np.int32)for r in transit['curves']if r['mode']=='TRAIN'])
    near=cKDTree(rail_points).query_ball_point(retained,6,p=np.inf);safe=np.ones(len(retained),bool)
    for i,ids in enumerate(near):
        if ids:
            delta=retained[i]-rail_points[ids];safe[i]=not((np.abs(delta[:,0])<=2)&(np.abs(delta[:,2])<=2)&(delta[:,1]>=-1)&(delta[:,1]<=5)).any()
    retained=retained[safe];all_coordinates.append(retained)
    coords=np.unique(np.concatenate(all_coordinates),axis=0);lookup={tuple(q):i for i,q in enumerate(coords)};rows=[];cols=[];weights=[]
    for local,graph in components:
        indices=np.asarray([lookup[tuple(p)]for p in local]);coo=graph.tocoo();rows.extend(indices[coo.row]);cols.extend(indices[coo.col]);weights.extend(coo.data)
    # Retained public nodes outside the moved complexes use the same native
    # foot/head boundary rule. No diagonal shortcut is added at a new seam.
    needed={tuple(map(int,p))for p in retained}
    for p in list(needed):
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            for dy in(-1,0,1):
                q=(p[0]+dx,p[1]+dy,p[2]+dz)
                if q in lookup:needed.add(q)
    wanted=set()
    for x,y,z in needed:
        for dy in(-1,0,1):wanted.add((x,y+dy,z))
    selected=defaultdict(set);sections=defaultdict(set);states={}
    for x,y,z in wanted:selected[x//16,z//16].add(y//16);sections[x//16,z//16,y//16].add((x,y,z))
    for cx,cz,sy,pal,ix in iter_selected_sections(world,'projectseele:geofront',selected):
        a=ix.reshape(16,16,16)
        for x,y,z in sections[cx,cz,sy]:states[x,y,z]=pal[int(a[y%16,z%16,x%16])]
    shapes=json.loads((world/'native_collision_shapes.json').read_text('utf8'));missing=set()
    def shape(p):
        state=states.get(p,'UNMEASURED')
        if state not in shapes:missing.add(state);return None
        return shapes[state]
    def blocked(boxes,dx,dz,height):
        if boxes is None:return True
        axis=0 if dx else 2;tangent=2 if dx else 0;positive=dx+dz>0
        return any(b[tangent]<.795 and b[tangent+3]>.205 and(b[axis+3]>.795 if positive else b[axis]<.205)and b[4]>.01 and b[1]<height for b in boxes)
    stitched=0
    for p0 in retained:
        p=tuple(map(int,p0));i=lookup[p]
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            for dy in(-1,0,1):
                q=(p[0]+dx,p[1]+dy,p[2]+dz);j=lookup.get(q)
                if j is None:continue
                if dy and not any('stairs'in states.get((v[0],v[1]-1,v[2]),'')or'escalator_step'in states.get((v[0],v[1]-1,v[2]),'')for v in(p,q)):continue
                if any(blocked(shape((v[0],v[1]+h,v[2])),sx,sz,height)for v,sx,sz in((p,dx,dz),(q,-dx,-dz))for h,height in((0,1),(1,.79))):continue
                rows.extend((i,j));cols.extend((j,i));weights.extend((4. if dy else 1.,)*2);stitched+=1
    walking=minimum_edge_graph(rows,cols,weights,len(coords))
    tree=cKDTree(coords);lift_doc=json.loads((world/'personnel_lifts_r52.json').read_text('utf8'));landings=[];issues=[];lift_edges=[]
    def nearest(point,radius=7,y_tolerance=.1):
        ids=tree.query_ball_point(point,radius);ids=[i for i in ids if abs(coords[i,1]-point[1])<=y_tolerance]
        return None if not ids else min(ids,key=lambda i:float(np.linalg.norm(coords[i]-point)))
    for lift in lift_doc['lifts']:
        stops=[]
        for floor in lift['floors']:
            door=np.asarray([d['pos']for d in floor['landing_doors']]);point=door.mean(axis=0);point[1]=floor['approach_y']
            direction={'north':(0,0,-1),'south':(0,0,1),'east':(1,0,0),'west':(-1,0,0)}[floor['exit']]
            point+=np.asarray(direction);node=nearest(point)
            if node is None:
                issues.append(dict(kind='lift_landing',lift=lift['id'],label=floor['label'],point=point.tolist()));continue
            stops.append(node);landings.append(dict(node=int(node),label=floor['label'],lift_id=lift['id'],requested=point.tolist(),actual=coords[node].tolist()))
        for i in stops:
            for j in stops:
                if i!=j:lift_edges.append(dict(id=lift['id'],a=int(i),b=int(j),weight=4+abs(int(coords[i,1])-int(coords[j,1]))*.12))
    old=json.loads(gzip.decompress((world/'nerv_routes_r24.json.gz').read_bytes()));audit=json.loads((BASE/'navigation_rebuild/SOURCE_AUDIT.json').read_text('utf8'))
    goals=[]
    for g in audit['goals']:
        node=nearest(g['candidate'],8)
        if node is None:issues.append(dict(kind='goal',goal=g['id'],point=g['candidate']))
        else:goals.append(dict(id=g['id'],name=g['name'],node=int(node)))
    # U2 is an actual retained round trip through the original logistics stop.
    # The long graph edge represents riding that service, never walking it.
    service=json.loads((BASE/'derived_transit/ACTUAL_U2_SERVICE.json').read_text('utf8'));transport=[];by_goal={g['id']:g['node']for g in goals}
    hq=service['stops'][0];hangar=next(s for s in service['stops']if s['station_id']==6417785485925618840)
    for a,b,source,dest in(('pyramid_station','launch_station',hq,hangar),('launch_station','pyramid_station',hangar,hq)):
        if a in by_goal and b in by_goal:transport.append(dict(kind='TRAIN',**{'from':by_goal[a],'to':by_goal[b]},line=service['route_number'],destination=dest['station'],source_station_id=str(source['station_id']),destination_station_id=str(dest['station_id']),weight=180))
    coo=walking.tocoo();rr=coo.row.tolist();cc=coo.col.tolist();ww=coo.data.tolist()
    for e in lift_edges:rr.append(e['a']);cc.append(e['b']);ww.append(e['weight'])
    for e in transport:rr.append(e['from']);cc.append(e['to']);ww.append(e['weight'])
    combined=minimum_edge_graph(rr,cc,ww,len(coords));gid=[g['node']for g in goals]
    distance,predecessors=dijkstra(combined,indices=gid,return_predecessors=True)
    connections=np.isfinite(distance[:,gid]);keep=np.flatnonzero(np.isfinite(distance).all(axis=0));report=dict(world_written=False,native_verified=False,raw_nodes=len(coords),walking_edges=walking.nnz,
        retained_nodes_added=len(retained),seam_edges=stitched,missing_shapes=sorted(missing),goals=goals,goal_reachability=connections.tolist(),
        mutually_reachable_nodes=len(keep),lift_landings=landings,lift_edges=lift_edges,transport_edges=transport,issues=issues)
    np.savez_compressed(out/'CURRENT_GRAPH.npz',coords=coords,walking_indptr=walking.indptr,walking_indices=walking.indices,walking_weights=walking.data,
        graph_indptr=combined.indptr,graph_indices=combined.indices,graph_weights=combined.data,goal_distances=distance,goal_predecessors=predecessors,kept=keep)
    (out/'REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k not in('lift_landings','lift_edges','transport_edges')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
