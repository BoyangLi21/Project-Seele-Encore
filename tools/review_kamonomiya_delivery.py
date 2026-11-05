"""Package offline evidence for the serial main-agent station publisher."""
import argparse,copy,gzip,json,math,shutil
from pathlib import Path
import numpy as np
import nbtlib
from scipy.ndimage import label
from shapely.geometry import Point,LineString,box,shape,mapping
from shapely.ops import nearest_points,unary_union
from author_hakone_lakefront import Editor
from author_kamonomiya_station import verify,voxel_box,OPEN
from check_kamonomiya_platform_edges import run as edge_review
from render_hakone_voxel_3d import render

def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')

def components(folder,bounds):
    data,palette=voxel_box(Editor(folder),bounds);solids=np.asarray([s.split('[')[0]not in OPEN for s in palette])[data]
    ids,count=label(solids);sizes=np.bincount(ids.ravel());roots=set(map(int,np.unique(ids[0])));floating=[dict(component=i,cells=int(sizes[i]))for i in range(1,count+1)if i not in roots]
    return dict(components=count,ground_rooted_components=len(roots-{0}),unrooted_components=len(floating),unrooted_cells=sum(r['cells']for r in floating),unrooted=floating,known_source_bounds=bounds,method='six-face solid connectivity to the complete captured bottom layer; unknown source chunks are never accepted')

def run(a):
    a.out.mkdir(exist_ok=False);edge_review(a.candidate)
    d=json.loads((a.candidate/'station-design.json').read_text('utf8'));m=json.loads((a.candidate/'manifest.json').read_text('utf8'));native=json.loads((a.candidate/'native-station-plan.json').read_text('utf8'))
    x,z,X,Z=m['bounds_xz'];bounds=[x,-128,z,X,319,Z]
    component_report=dict(before=components(a.source,bounds),after=components(a.candidate,bounds),world_written=False)
    dump(a.out/'components.json',component_report)
    if component_report['after']['unrooted_cells']>component_report['before']['unrooted_cells']:raise ValueError('New unrooted solids')
    changed=[]
    for f in(a.candidate/'delta').glob('*.npz'):
        with np.load(f)as q:changed.extend([dict(chunk_x=int(cx),chunk_z=int(cz),changed_cells=int(q['ranges'][i+1]-q['ranges'][i]))for i,(cx,cz)in enumerate(q['coordinates'])])
    dump(a.out/'changed-chunks.json',dict(chunks=sorted(changed,key=lambda q:(q['chunk_x'],q['chunk_z'])),count=len(changed),cells=sum(q['changed_cells']for q in changed)))
    features=json.loads(gzip.decompress((a.features/'features.world.geojson.gz').read_bytes()))['features'];rails=[(i,f,shape(f['geometry']))for i,f in enumerate(features)if f['properties'].get('source_layer')=='RailCL']
    site=json.loads(a.site.read_text('utf8'));ref=site['reference'];centre=np.asarray(ref['track_centre_xz']);axis=np.asarray(ref['station_track'][-1])-ref['station_track'][0];axis/=np.linalg.norm(axis)
    if axis[0]<0:axis=-axis
    allnative=json.loads((a.authority/'native-curves.json').read_text('utf8'));footprint=box(d['parts'][0]['bounds'][0],d['parts'][0]['bounds'][2],d['parts'][0]['bounds'][3]+1,d['parts'][0]['bounds'][5]+1)
    retained_native=[]
    for mode,rows in allnative.items():
        for q in rows:
            if not q.get('points'):continue
            v=np.asarray(q['points']);line=LineString(v[:,[0,2]])
            if line.buffer(4).intersects(footprint) and float(v[:,1].max())>=-85 and float(v[:,1].min())<=-55:retained_native.append(dict(id=q['id'],mode=mode))
    transition=[]
    for side,endpoint,targetx in(('west',[3840.5,-38.5],3660.5),('east',[3968.5,-38.5],4148.5)):
        predicted=centre+axis*((targetx-centre[0])/axis[0]);jr=[(i,f,g)for i,f,g in rails if f['properties'].get('vt_rtcode')=='JR']
        i,f,g=min(jr,key=lambda r:r[2].distance(Point(predicted)));p=np.asarray(nearest_points(g,Point(predicted))[0].coords[0]);line=LineString([endpoint,p]);reserved=line.buffer(14,cap_style=2)
        transition.append(dict(side=side,station_centreline_port_xz=endpoint,station_rail_y=-78,station_outward_tangent='W'if side=='west'else'E',reference_target_xz=p.tolist(),reference_target_feature_index=i,reference_target_properties=f['properties'],horizontal_distance=float(np.linalg.norm(p-endpoint)),minimum_design_transition_length=180,reserved_horizontal_corridor=mapping(reserved),world_terrain_capture_complete=False,vertical_profile_verified=False,exact_native_transition_curve_verified=False,track_pair_spacing_at_station=14,stage=3,construction_allowed=False,note='Retain both east/west native tangents; taper onto the measured reference corridor only after three-dimensional road, river and vehicle checks. This reservation is not an excavation instruction.'))
    sources=[]
    for i,f,g in rails:
        if g.intersects(footprint.buffer(4)):sources.append(dict(feature_index=i,properties=f['properties'],geometry=mapping(g.intersection(footprint.buffer(4)))))
    water=[]
    for i,f in enumerate(features):
        if f['properties'].get('source_layer')not in('WA','RvrCL','WStrL'):continue
        q=shape(f['geometry'])
        if q.intersects(footprint):water.append(dict(feature_index=i,properties=f['properties'],geometry=mapping(q.intersection(footprint))))
    adaptation=dict(reference_centre=centre.tolist(),native_centre=[3904.5,-38.5],centre_offset=float(np.linalg.norm(centre-[3904.5,-38.5])),reference_axis_degrees=float(math.degrees(math.atan2(axis[1],axis[0]))%180),native_axis_degrees=0,local_axis_adaptation_degrees=abs(float(math.degrees(math.atan2(axis[1],axis[0])))),platform_lengths=[128,128],capacity=120,gap_each_side=.5,reason='Local straight-platform geographic adaptation for a continuous safe boarding edge; not a 1:1 restoration.',reference_rail_features_in_station_area=sources,retained_native_curves_in_station_volume=retained_native,cached_water_features_in_station_area=water,transition_interfaces=transition,through_service_complete=False,world_written=False)
    dump(a.out/'geographic-adaptation-and-interfaces.json',adaptation)
    if retained_native:raise ValueError('Candidate intersects retained native curves')
    # Failures are injected in independent offline copies; live world untouched.
    neg=a.out/'neg';neg.mkdir();tests=[]
    cases=[('floor','public bearing or floor height changed'),('train','rigid vehicle envelope obstructed'),('protected','protected original block changed'),('sign','sign payload/backing verification failed'),('support','new solid component has no measured ground support')]
    for name,expected in cases:
        folder=neg/name;shutil.copytree(a.candidate,folder);e=Editor(folder)
        if name=='floor':
            px,feet,pz=d['goals']['hall'];e.put(px,int(feet)-1,pz,'minecraft:air')
        elif name=='train':e.put(3904,-77,-46,'minecraft:glass')
        elif name=='protected':e.put(3908,-80,1,'minecraft:air')
        elif name=='support':e.put(3972,-68,-10,'minecraft:gray_concrete')
        else:
            tags=nbtlib.load(folder/'block-entities.dat');del tags['Changes'][0]['After'];tags.save(folder/'block-entities.dat',gzipped=True)
        if name!='sign':
            rows=e.save();manifest=json.loads((folder/'manifest.json').read_text('utf8'));manifest['regions']=rows;manifest['cells']=sum(r['cells']for r in rows);dump(folder/'manifest.json',manifest)
        detected=False
        try:verify(folder,a.authority)
        except ValueError:
            proof=json.loads((folder/'offline-verification.json').read_text('utf8'));detected=expected in proof['errors']
        if not detected:raise ValueError('Negative case not detected: '+name)
        tests.append(dict(case=name,expected=expected,detected=True))
    dump(a.out/'negative-cases.json',dict(cases=tests,world_written=False))
    e=Editor(a.candidate)
    render(e,[3826,-83,-54,3982,-62,34],a.out/'overview.png','鴨宮站：128格双线、0.5格连续登车间隙、跨线桥与南侧接入')
    render(e,[3836,-81,-49,3924,-66,6],a.out/'ramp-cut.png','剖切：站台双侧通道、半砖缓坡、楼梯和跨线桥净空')
    positions=[r['pos']for r in d['expected_signs']]
    dump(a.out/'review.json',dict(candidate=str(a.candidate),cells=m['cells'],changed_chunks=len(changed),sign_positions=positions,ground_access_columns=len(d['ground_access_columns']),multi_level_nodes=len(d['station_multi_level_nodes']),negative_cases_passed=len(tests),component_report='components.json',adaptation_report='geographic-adaptation-and-interfaces.json',views=['overview.png','ramp-cut.png'],source=str(a.source),authority=str(a.authority),world_written=False,native_registry_pending=True,production_replay_pending=True,through_service_complete=False))
    print('Final offline evidence ready:',len(changed),'chunks;',len(tests),'negative cases;',len(positions),'signs; world untouched',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('candidate','source','authority','site','features','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
