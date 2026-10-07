"""Compose complete finite main-cavern topology from read-only actual voxels.

No world/generator/actor modifications. The connected mask is partitioned into
merged equal row intervals. Every rectangle and shared-edge connector, including
diagonal edge interiors, uses actual stored FULL-chunk Y-410..-237 air. Lower
cargo remains a native compound-geometry test rather than a height-only pass.
"""
from pathlib import Path
import heapq,json,math
import numpy as np
from scipy.ndimage import maximum_filter

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r50/underground_airlift'

def rectangles(mask):
    active={};result=[]
    for z,row in enumerate(mask):
        changes=np.diff(np.r_[False,row,False].astype(np.int8))
        runs=list(zip(np.where(changes==1)[0],np.where(changes==-1)[0]));now={}
        for run in runs:now[run]=active.pop(run,z)
        for (x,x1),z0 in active.items():result.append((int(x),int(z0),int(x1),int(z)))
        active=now
    for (x,x1),z0 in active.items():result.append((int(x),int(z0),int(x1),mask.shape[0]))
    return result

def main():
    raster=np.load(OUT/'cavern_grid/actual_cavern_air_band.npz')
    x0,z0=map(int,raster['origin']);clear=raster['airport_connected'];known=raster['known_full']
    blocked=raster['blocked_any_y_minus410_to_minus237'];ground=raster['highest_soil_in_read_band']
    eligible=clear&(ground>=-510)&(ground<=-411)
    if not np.array_equal(clear,eligible):raise RuntimeError('Connected non-field columns need independent actual pickup classification')
    local=rectangles(eligible);rects=[(a+x0,b+z0,c+x0,d+z0)for a,b,c,d in local]
    src=ROOT/'artifacts/rebuild_r50/underground_airport/flight_geometry_candidate.json'
    meta=json.loads(src.read_text('utf8'));meta['installed']=False;meta['airport_node']='airportLift'
    for node in meta['nodes']:node['role']='stand' if node['id']=='airport' else 'hover' if node['id'].startswith('drop_') else 'cruise'
    for zone in meta['pickup_zones']:
        zone['pickup_node']=f"receiver_{zone['id'].rsplit('_',1)[1]}"if zone['id'].startswith('receiver_pickup_')else'airportLift'
    zone_details=[];centers=[];cover=np.zeros(eligible.shape,np.uint8)
    for i,(a,b,c,d)in enumerate(rects):
        node_id=f'field_{i:03d}';center=[(a+c)/2,-260,(b+d)/2];centers.append(center)
        meta['nodes'].append(dict(id=node_id,pos=center,role='cruise'))
        zz=slice(b-z0,d-z0);xx=slice(a-x0,c-x0);g=ground[zz,xx];low,high=int(g.min()),int(g.max());cover[zz,xx]+=1
        zone=dict(id=f'pickup_{node_id}',bounds=[[a,low-1,b],[c,high+81,d]],pickup_node=node_id,
                  actual_soil_y_range=[low,high],field_floor_observed=True,actual_pose_and_collision_required=True)
        meta['pickup_zones'].append(zone);zone_details.append(zone)
        lo,hi=[a-96,-560,b-96],[c+96,-237,d+96]
        full_z,full_x=slice(b-96-z0,d+96-z0),slice(a-96-x0,c+96-x0)
        if not known[full_z,full_x].all()or blocked[full_z,full_x].any():raise AssertionError('Rectangle is not a fully measured all-yaw air band')
        meta['airspace'].append(dict(id=f'field_volume_{node_id}',bounds=[lo,hi],
            certified_empty_air_band_y=[-410,-237],lower_cargo_space_requires_runtime_geometry=True))
    if not np.array_equal(cover,eligible.astype(np.uint8)):raise AssertionError('Exact field domain partition failed')
    adjacencies=[]
    for i,(x,z,xx,zz)in enumerate(rects):
        for j,(a,b,aa,bb)in enumerate(rects[:i]):
            overlap_lo,overlap_hi=max(x,a),min(xx,aa)
            if(zz==b or bb==z)and overlap_lo<overlap_hi:at=[(overlap_lo+overlap_hi)/2,-260,zz if zz==b else z]
            else:
                overlap_lo,overlap_hi=max(z,b),min(zz,bb)
                if not((xx==a or aa==x)and overlap_lo<overlap_hi):continue
                at=[xx if xx==a else x,-260,(overlap_lo+overlap_hi)/2]
            bridge=f'field_link_{len(adjacencies):03d}';meta['nodes'].append(dict(id=bridge,pos=at,role='cruise'))
            for index in(i,j):meta['edges'].append([f'field_{index:03d}',bridge])
            adjacencies.append(dict(node=bridge,rectangles=[i,j],pos=at,whole_connector_inside_registered_rectangles=True))
    # Physical mainline has separately measured thinner posed volumes. Attach
    # at the exact airport point owned by one proven all-yaw field rectangle.
    hosts=[i for i,(a,b,c,d)in enumerate(rects)if a<=-440<c and b<=-270<d]
    if len(hosts)!=1:raise AssertionError('Airport entry lacks exact field owner')
    meta['edges'].append(['airportLift',f'field_{hosts[0]:03d}'])
    # Keep the exact outer mask while giving long journeys measured interior
    # shortcuts. All chord bounding rectangles, not only the line, must be
    # clear. Thus a chord cannot cut across the headquarters or a deep tower.
    bad=np.pad((~clear).astype(np.int32),((1,0),(1,0))).cumsum(0,dtype=np.int32).cumsum(1,dtype=np.int32)
    def rectangle_clear(u,v):
        a,b=math.floor(min(u[0],v[0]))-x0,math.floor(min(u[2],v[2]))-z0
        c,d=math.floor(max(u[0],v[0]))-x0+1,math.floor(max(u[2],v[2]))-z0+1
        return bad[d,c]-bad[b,c]-bad[d,a]+bad[b,a]==0
    interior=maximum_filter((~clear).astype(np.uint8),size=225,mode='constant',cval=1)==0
    cruise=[('airportLift',[-440,-260,-270])]
    for z in range(-720,1425,224):
        for x in range(-1120,1185,224):
            if not interior[z-z0,x-x0]:continue
            name=f'cruise_field_{len(cruise):02d}';at=[x,-260,z];cruise.append((name,at));meta['nodes'].append(dict(id=name,pos=at,role='cruise'))
    shortcuts=[]
    def chord(a,u,b,v):
        if not rectangle_clear(u,v):raise AssertionError('Shortcut crosses blocked/unknown interior')
        meta['edges'].append([a,b]);lo=[min(u[0],v[0])-96,-560,min(u[2],v[2])-96];hi=[max(u[0],v[0])+96,-237,max(u[2],v[2])+96]
        meta['airspace'].append(dict(id=f'chord_{a}_{b}',bounds=[lo,hi],certified_empty_air_band_y=[-410,-237],lower_cargo_space_requires_runtime_geometry=True))
        shortcuts.append(dict(edge=[a,b],entire_root_rectangle_known_and_clear=True))
    for i,(name,at)in enumerate(cruise):
        for other,there in cruise[:i]:
            if rectangle_clear(at,there):chord(name,at,other,there)
    for i,center in enumerate(centers):
        candidates=sorted((math.dist(center,at),name,at)for name,at in cruise if rectangle_clear(center,at))
        for _,name,at in candidates[:2]:chord(f'field_{i:03d}',center,name,at)
    if len(meta['nodes'])>1024 or len(meta['airspace'])>2048 or len(meta['pickup_zones'])>512:raise AssertionError('Bounded runtime metadata exceeded')
    points={n['id']:n['pos']for n in meta['nodes']};edges={k:[]for k in points}
    for a,b in meta['edges']:
        length=math.dist(points[a],points[b]);edges[a].append((b,length));edges[b].append((a,length))
    def distances(source):
        dist={source:0};todo=[(0,source)]
        while todo:
            cost,node=heapq.heappop(todo)
            if cost!=dist[node]:continue
            for other,weight in edges[node]:
                candidate=cost+weight
                if candidate<dist.get(other,math.inf):dist[other]=candidate;heapq.heappush(todo,(candidate,other))
        return dist
    from_airport=distances('airportLift')
    if len(from_airport)!=len(points):raise AssertionError('Adjacent field graph disconnected')
    to_receiver={v:distances(f'receiver_{v}')for v in range(3)}
    max_leg=max((from_airport[f'field_{i:03d}'],i)for i in range(len(rects)))
    max_trip=max((from_airport[f'field_{i:03d}']+to_receiver[v][f'field_{i:03d}'],i,v)for i in range(len(rects))for v in range(3))
    # Selected aircraft radius sqrt(69^2+58^2)=90.139. Radius90.2+4m/t
    # +.01 inflation fits96m cell padding even across a shared edge.
    def fits(bounds,lo,hi):return all(lo[k]>=bounds[0][k]and hi[k]<=bounds[1][k]for k in range(3))
    samples=0
    for a,b in meta['edges'][9:]:
        start=np.asarray(points[a]);end=np.asarray(points[b]);count=max(2,math.ceil(math.dist(start,end)/4))
        for t in np.linspace(0,1,count+1):
            at=start+(end-start)*t;lo=(at-[94.21,150,94.21]).tolist();hi=(at+[94.21,19.01,94.21]).tolist()
            if not any(fits(box['bounds'],lo,hi)for box in meta['airspace']):raise AssertionError((a,b,t,'whole swept aircraft not in one box'))
            samples+=1
    target=OUT/'nerv_underground_transport_r50.json'
    meta.update(hoist_offset=112,all_yaw_planning_radius=95,terrain_geometry_candidate_final=True,
        pickup_scope='Complete measured airport-connected main GeoFront natural field columns plus commissioned airport/receivers; excludes unregistered rooms, HQ/deep towers, blocked, proto and unknown regions',
        voxel_screen_source=str((OUT/'cavern_grid/actual_cavern_air_band_readback.json').resolve()),
        expanded_field_zones=len(rects),expanded_field_unique_columns=int(eligible.sum()),
        original_physical_geometry_unchanged=True,world_written=False,native_verified=False)
    target.write_text(json.dumps(meta,ensure_ascii=False,indent=2),'utf8')
    report=dict(metadata=str(target.resolve()),graph_nodes=len(points),graph_edges=len(meta['edges']),airspace_cells=len(meta['airspace']),pickup_zones=len(meta['pickup_zones']),
        expanded_field_zones=len(rects),expanded_field_unique_columns=int(eligible.sum()),airport_connected_planning_columns=int(clear.sum()),
        connected_field_columns_outside_expanded_boxes=0,stored_full_columns=int(known.sum()),unknown_or_proto_columns=int((~known).sum()),
        actual_obstructed_flight_columns=int((known&blocked).sum()),field_soil_range=[int(ground[eligible].min()),int(ground[eligible].max())],
        exact_partition_overlap_or_gap_columns=0,field_zones=zone_details,shared_edge_connectors=adjacencies,
        measured_whole_rectangle_cruise_shortcuts=shortcuts,
        original_physical_and_actor_identity_unchanged=True,graph_connectivity_checked=True,
        single_box_whole_aircraft_peak4_step_samples=samples,
        max_airport_to_pickup_cruise_m=max_leg[0],max_airport_to_pickup_field=f'field_{max_leg[1]:03d}',
        max_airport_pickup_to_receiver_cruise_m=max_trip[0],max_round_trip_field=f'field_{max_trip[1]:03d}',max_round_trip_receiver=max_trip[2],
        max_field_center_to_pickup_m=max(math.hypot((c-a)/2,(d-b)/2)for a,b,c,d in rects),
        speed_geometry='Empty aircraft radius90.139 plus4m/t and .01 turn inflation fits96m measured padding. Loaded2.8m/t still uses original full cargo compound GJK and full-AABB domain every frame; no frozen pose assumed by this metadata audit.',
        unregistered='Every proven connected field column is registered. HQ/deep tower/nonair flight-band cells, proto/unstored columns and every other cavern remain rejected. Lower cargo and current actors/blocks require native geometry clearance every frame; soil range alone is not clearance.',
        airport_marker=str((ROOT/'artifacts/rebuild_r50/underground_airport/r50_underground_airport.json').resolve()),
        install_requires_both_receipts=True,quality_acceptance=False,world_written=False,Java_started=False)
    (OUT/'expanded_topology_readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:report[k]for k in('graph_nodes','graph_edges','airspace_cells','pickup_zones','expanded_field_unique_columns','single_box_whole_aircraft_peak4_step_samples','max_airport_to_pickup_cruise_m','max_airport_pickup_to_receiver_cruise_m')}))

if __name__=='__main__':main()
