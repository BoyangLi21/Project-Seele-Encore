"""Sparse whole-authority topology and measured geometry candidates, never a route pass."""
from pathlib import Path
from collections import Counter
import argparse, hashlib, json
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]


def components(coordinates, feet, flags, mode):
    n = len(coordinates)
    packed = coordinates[:,0].astype(np.int64)*4294967296 + (coordinates[:,1].astype(np.int64)&0xffffffff)
    order = np.argsort(packed);ordered = packed[order]
    if mode == 'authored':
        active = np.ones(n, bool)
    elif mode == 'player':
        active = (flags&7)==7
    else:
        active = (flags&27)==27
    if mode != 'authored':active &= (flags&256)==0
    froms, tos = [], []
    for dx,dz in ((1,0),(0,1),(1,1),(1,-1)):
        target = (coordinates[:,0].astype(np.int64)+dx)*4294967296+((coordinates[:,1].astype(np.int64)+dz)&0xffffffff)
        indices = np.searchsorted(ordered,target)
        valid = indices<n
        candidates = np.flatnonzero(valid)
        candidates = candidates[ordered[indices[candidates]]==target[candidates]]
        neighbours = order[indices[candidates]]
        allowed = active[candidates]&active[neighbours]
        if mode != 'authored':allowed &= np.abs(feet[candidates]-feet[neighbours])<=.501
        froms.append(candidates[allowed].astype(np.int32));tos.append(neighbours[allowed].astype(np.int32))
    a,b=np.concatenate(froms),np.concatenate(tos)
    graph=csr_matrix((np.ones(len(a),np.uint8),(a,b)),shape=(n,n))
    _,labels=connected_components(graph,directed=False)
    sizes=Counter(map(int,labels[active]));rank=sorted(sizes,key=lambda q:(-sizes[q],q))
    mapping=np.zeros(n,np.int32)
    for i,label in enumerate(rank,1):mapping[label]=i
    canonical=np.where(active,mapping[labels],0).astype(np.int32)
    rows=[]
    for i,label in enumerate(rank,1):
        indices=np.flatnonzero(canonical==i);points=coordinates[indices]
        rows.append(dict(id=i,columns=len(indices),bounds=[points[:,0].min().item(),points[:,1].min().item(),points[:,0].max().item(),points[:,1].max().item()]))
    return canonical,dict(component_count=len(rows),active_columns=int(active.sum()),held_geometry_columns=int((~active).sum()),components=rows)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('road_audit',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    assert not args.output.exists(),'Keep the earlier topology and use a new epoch'
    audit=json.loads(args.road_audit.read_text('utf8'));profile=Path(audit['exact_measured_column_profiles'])
    assert hashlib.sha256(profile.read_bytes()).hexdigest()==audit['column_profile_sha256']
    arrays=np.load(profile);coordinates,feet,flags=arrays['coordinates'],arrays['actual_feet'],arrays['flags']
    assert len(coordinates)==audit['measured_columns']==audit['full_authority_columns']
    labels={};summaries={}
    for mode in ('authored','player','vehicle'):
        labels[mode],summaries[mode]=components(coordinates,feet,flags,mode)
        print(mode,summaries[mode]['component_count'],'components',summaries[mode]['active_columns'],'active columns',flush=True)
    inherited=json.loads((ROOT/'artifacts/rebuild_r44/surface_network/road_network_connectivity.json').read_text('utf8'))
    zones=[]
    for old in inherited['zones']:
        x0,x1,z0,z1=old['declared_bounds'];inside=(coordinates[:,0]>=x0)&(coordinates[:,0]<=x1)&(coordinates[:,1]>=z0)&(coordinates[:,1]<=z1)
        row=dict(id=old['id'],bounds=[x0,z0,x1,z1],component_columns={})
        for mode in labels:
            row['component_columns'][mode]={str(k):v for k,v in Counter(map(int,labels[mode][inside])).items() if k}
        zones.append(row)
    connections=[]
    city_zones={q['id']:q for q in zones}
    for a,b in [('new_hakone','tokyo_west'),('tokyo_west','harbour_ward'),('harbour_ward','bay_airport'),('new_hakone','hakone_airfield')]:
        principal=[]
        for name in (a,b):
            row=city_zones[name];membership=row['component_columns']['authored'];label=max(membership,key=membership.get) if membership else None
            if label is None:principal.append((None,np.empty((0,2),np.int32)));continue
            x0,z0,x1,z1=row['bounds'];inside=(coordinates[:,0]>=x0)&(coordinates[:,0]<=x1)&(coordinates[:,1]>=z0)&(coordinates[:,1]<=z1)&(labels['authored']==int(label))
            principal.append((int(label),coordinates[inside]))
        (first,points),(second,targets)=principal
        record=dict(cities=[a,b],principal_authored_components=[first,second],native_full_width_route_passed=False)
        if first is None or second is None:record['status']='MISSING_AUTHORED_ZONE_ROAD_ENDPOINT_REQUIRES_OWNER_RECONCILIATION'
        elif first==second:record['status']='SAME_AUTHORED_COMPONENT_FULL_NATIVE_ROUTE_AND_SECTIONS_PENDING'
        else:
            distances,indices=cKDTree(targets).query(points);i=int(np.argmin(distances))
            zone_endpoints=[points[i].tolist(),targets[indices[i]].tolist()]
            whole_first=coordinates[labels['authored']==first];whole_second=coordinates[labels['authored']==second]
            distances,indices=cKDTree(whole_second).query(whole_first);i=int(np.argmin(distances))
            record.update(status='DIFFERENT_AUTHORED_COMPONENTS_SURVEY_CONNECTOR_OR_MISSING_AUTHORITY',
                nearest_zone_authored_endpoints=zone_endpoints,nearest_component_authored_endpoints=[whole_first[i].tolist(),whole_second[indices[i]].tolist()],distance=float(distances[i]))
        connections.append(record)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    npz=args.output.with_suffix('.labels.npz');np.savez_compressed(npz,coordinates=coordinates,actual_feet=feet,flags=flags,**{f'{k}_component':v for k,v in labels.items()})
    report=dict(road_audit=str(args.road_audit),road_audit_sha256=hashlib.sha256(args.road_audit.read_bytes()).hexdigest(),authority_sources=audit['authority_sources'],
        measured_columns=len(coordinates),graphs=summaries,zones=zones,city_connection_surveys=connections,labels=str(npz),world_written=False,
        whole_width_and_bearing_native_passed=False,rail_bridge_port_and_vehicle_native_passed=False,visual_passed=False,
        interpretation='Every authored column participates; measured candidate graphs require exact datum and native clearance and reject height jumps above half a block and 3D virtual rail conflicts. They can still contain narrowed pinch points, pending bridge support, shores or transferred station/airport uses. Connectivity cannot stand in for complete-width walking/driving, foundation, port or client review.')
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(connections,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
