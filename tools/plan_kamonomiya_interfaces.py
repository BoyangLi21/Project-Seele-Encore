"""Retain measured rail/water interfaces around an offline Kamonomiya station.

Outputs reservations for stage three, never excavation or native-service edits.
Targets must lie on the connected cached JR corridor and at least 180m beyond
the corresponding platform end. A separate unbuilt siding stays explicit.
"""
import argparse,collections,gzip,heapq,json,math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Point,LineString,box,shape,mapping
from shapely.ops import unary_union

def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')

def run(candidate,features,out):
    features=json.loads(gzip.decompress((features/'features.world.geojson.gz').read_bytes()))['features']
    rails=[(i,f,shape(f['geometry']))for i,f in enumerate(features)if f['properties'].get('source_layer')=='RailCL']
    main=[(i,f,g)for i,f,g in rails if f['properties'].get('vt_rtcode')=='JR']
    points=[];edges=[];records={i:(f,g)for i,f,g in rails}
    for i,f,g in main:
        seq=list(g.coords);start=len(points);points.extend(seq)
        edges.extend((start+j,start+j+1,i)for j in range(len(seq)-1))
    points=np.asarray(points);parent=list(range(len(points)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,j in cKDTree(points).query_pairs(.25):
        ii,jj=find(i),find(j)
        if ii!=jj:parent[jj]=ii
    members=collections.defaultdict(list)
    for i,p in enumerate(points):members[find(i)].append(p)
    centres={k:np.mean(v,axis=0)for k,v in members.items()};graph=collections.defaultdict(list)
    for i,j,feature in edges:
        I,J=find(i),find(j)
        if I==J:continue
        distance=float(np.linalg.norm(centres[I]-centres[J]));graph[I].append((J,distance,feature));graph[J].append((I,distance,feature))
    ref=np.asarray([3904.541,-38.342]);root=min(graph,key=lambda k:float(np.linalg.norm(centres[k]-ref)))
    queue=[(0,root)];cost={root:0};previous={root:None};via={}
    while queue:
        distance,node=heapq.heappop(queue)
        if distance!=cost[node]:continue
        for nxt,length,feature in graph[node]:
            d=distance+length
            if d<cost.get(nxt,float('inf')):cost[nxt]=d;previous[nxt]=node;via[nxt]=feature;heapq.heappush(queue,(d,nxt))
    transitions=[]
    for side,port,direction in(('west',np.asarray([3840.5,-38.5]),-1),('east',np.asarray([3968.5,-38.5]),1)):
        candidates=[k for k in cost if (centres[k][0]-port[0])*direction>=180 and np.linalg.norm(centres[k]-port)>=180]
        if not candidates:raise ValueError('No connected cached '+side+' target at least 180m beyond the station')
        target=min(candidates,key=lambda k:cost[k]);p=centres[target];ids=[];path=[];q=target
        while q is not None:
            path.append(centres[q].tolist())
            if q in via:ids.append(via[q])
            q=previous[q]
        path.reverse();ids.reverse()
        corridor=LineString([port,p]).buffer(14,cap_style=2).union(LineString(path).buffer(14,cap_style=2))
        transitions.append(dict(side=side,station_centreline_port_xz=port.tolist(),native_track_ports=[[int(port[0]-.5),-78,z]for z in(-46,-32)],native_outward_tangent='W'if direction<0 else'E',minimum_design_transition_length=180,
            reference_target_xz=p.tolist(),horizontal_distance=float(np.linalg.norm(p-port)),longitudinal_distance=float((p[0]-port[0])*direction),reference_graph_distance_from_station_node=cost[target],reference_connected_path_xz=path,
            reference_feature_indices=list(dict.fromkeys(ids)),source_join_tolerance=.25,reserved_horizontal_corridor=mapping(corridor),
            vertical_profile_verified=False,native_transition_geometry_verified=False,full_vehicle_sweep_verified=False,world_terrain_capture_complete=False,construction_allowed=False,stage=3))
    sidings=[];platform_box=box(3840.5,-47,3968.5,-30)
    for i,f,g in rails:
        if f['properties'].get('vt_rtcode')!='側線' or g.distance(Point(3840.5,-38.5))>100:continue
        overlaps=g.intersects(platform_box.buffer(2))
        sidings.append(dict(source_feature_index=i,properties=f['properties'],reference_geometry=mapping(g),reference_length=g.length,overlaps_adapted_platform_corridor=overlaps,
            source_is_unbuilt_reference_not_existing_native_rail=True,reference_must_not_be_dropped=True,
            requires_station_adaptation_reconnect=overlaps,retain_reference_geometry_without_station_relocation=not overlaps,
            proposed_turnout_zone_xz=[3784,-61,3820,-18]if overlaps else None,proposed_turnout_centre_xz=[3812.5,-31.5]if overlaps else None,minimum_distance_outside_west_platform=20,
            relocated_siding_geometry_verified=False,operational_purpose_and_capacity_pending=True,construction_allowed=False,stage=3,
            rule='Retain all reference fragments. Only the fragment overlapping the adapted station requires a relocated connection; do not shift the rest of the yard. Any new turnout must remain west of X3820, at least 20.5m outside the platform. Do not invent a depot or service before the stage-three review.'))
    # Exact changed columns, not the station bounding rectangle, determine
    # whether the prepared candidate enters a current cached water reserve.
    columns=set();changed_rows=[]
    for file in(candidate/'delta').glob('*.npz'):
        with np.load(file)as q:
            for i,(cx,cz)in enumerate(q['coordinates']):
                for j in range(int(q['ranges'][i]),int(q['ranges'][i+1])):
                    v=int(q['indices'][j]);px=int(cx)*16+v%16;pz=int(cz)*16+(v%256)//16;columns.add((px,pz))
    bounds=unary_union([box(px,pz,px+1,pz+1)for px,pz in columns]).bounds;search=box(*bounds).buffer(3)
    water=[(i,f,shape(f['geometry']))for i,f in enumerate(features)if f['properties'].get('source_layer')in('WA','RvrCL','WStrL')]
    nearby=[(i,f,g)for i,f,g in water if g.intersects(search)]
    wet=unary_union([g for i,f,g in nearby]);buffer=wet.buffer(3)
    bad=[[px,pz]for px,pz in sorted(columns)if box(px,pz,px+1,pz+1).intersects(buffer)]
    if bad:raise ValueError('Prepared cells enter the three-block water reserve: '+str(bad[:20]))
    result=dict(candidate=str(candidate),source='cached GSI world vectors; no network access',transition_interfaces=transitions,retained_siding_interfaces=sidings,
        source_water_features=[dict(feature_index=i,properties=f['properties'],geometry=mapping(g.intersection(search)))for i,f,g in nearby],
        changed_column_count=len(columns),three_block_water_buffer_intersections=bad,water_buffer_preserved=True,
        turnout_forbidden_in_platform_span=[3840.5,3968.5],stage_three_connections_complete=False,world_written=False)
    out.parent.mkdir(exist_ok=True,parents=True);dump(out,result)
    print('Interfaces:',[(r['side'],round(r['horizontal_distance'],2),r['reference_target_xz'])for r in transitions],'; retained sidings',len(sidings),'; water buffer intersections',len(bad),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('candidate','features','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(a.candidate,a.features,a.out)
