"""Prepare continuous upright SPACE/ticket extents from explicit actual sources.

Candidate JSON only. Bezier control hulls enclose every translation; actual
runner vertices are bounded about their ball joint for every orientation.
Reservation extents never replace native clearance/bearing/commissioning.
Retired84-leg/Dock inputs are rejected. No World/install mode exists.
"""
import argparse, copy, hashlib, json, math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'src/main/resources/assets/projectseele'

def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def need(condition, reason):
    if not condition: raise ValueError(reason)
def point(p, n=3):
    need(len(p)==n and all(type(v) in (int,float) and math.isfinite(v) for v in p), 'Actual finite point required')
    return list(p)

def split(controls):
    rows=[controls]
    while len(rows[-1])>1: rows.append([[(a[i]+b[i])/2 for i in range(3)] for a,b in zip(rows[-1],rows[-1][1:])])
    return [r[0] for r in rows], [r[-1] for r in reversed(rows)]
def curve_intervals(controls, depth=0):
    bound=sum(math.dist(a,b) for a,b in zip(controls,controls[1:]))
    if bound<=16: return [(controls,bound)]
    need(depth<24,'Finite curve subdivision budget exceeded')
    a,b=split(controls)
    return curve_intervals(a,depth+1)+curve_intervals(b,depth+1)
def ramp_height(profile,h,t):
    before,run,blend=[profile[k] for k in ('flat_before','slope_run','blend')]
    need(0<=before and 0<blend<=run/2 and before+run<=h+1e-8,'Actual original ramp geometry required')
    d=max(0,min(run,h*t-before));effective=run-blend
    rounded=lambda v:v/2-blend/(2*math.pi)*math.sin(math.pi*v/blend)
    return (rounded(d) if d<blend else effective-rounded(run-d) if d>run-blend else d-blend/2)/effective
def leg_intervals(leg,nodes):
    a=point(nodes[leg['from']]['foot_frame']['translation']);b=point(nodes[leg['to']]['foot_frame']['translation'])
    if 'centre_curve' in leg:
        segments=leg['centre_curve']['segments'];result=[];previous=a
        need(segments and segments[-1]['controls'][-1]==b,'Actual curve/node endpoints differ')
        for segment in segments:
            controls=[point(p) for p in segment['controls']]
            need(len(controls) in (2,6) and controls[0]==previous,'Actual continuous LINE/QUINTIC_BEZIER controls required')
            previous=controls[-1];result.extend(curve_intervals(controls))
        return result
    profile=leg.get('ramp_profile');delta=[b[i]-a[i] for i in range(3)];h=math.hypot(delta[0],delta[2])
    # Ramp coordinates are monotone. Endpoint boxes contain all points;
    # maximum derivative bounds actual arc length, rather than only chords.
    bound=math.dist(a,b) if profile is None else math.hypot(h,abs(delta[1])*h/(profile['slope_run']-profile['blend']))
    count=max(1,math.ceil(bound/16))
    def at(t):
        p=[a[i]+delta[i]*t for i in range(3)]
        if profile is not None:p[1]=a[1]+delta[1]*ramp_height(profile,h,t)
        return p
    return [([at(i/count),at((i+1)/count)],bound/count) for i in range(count)]

def local_sources(hulls,model):
    variants={r['variant']:r for r in hulls['variants']};need(set(variants)=={0,1,2},'Three actual full assembly hull variants required')
    nominal=read(ASSET/'mesh/foot_guide_rig_r52.json')['nominal_sole_bindings'];radii={}
    mounts=[point(p) for p in model['mounts_root_local']]
    origin=point(model['runner_origin_from_ball_local'])
    need(len(mounts)==2 and mounts[0][0]<0<mounts[1][0] and origin[0]==0 and origin[2]==0,
         'Actual two selected ball mounts and runner origin required')
    for p in model['parts']:
        if p['frame']=='ROOT':continue
        need(p['frame'] in ('RUNNER_NEG','RUNNER_POS'),'Actual selected runner frame required')
        a=p['triangles_rgb'];need(a and len(a)%18==0,'Actual runner triangle stride6 required')
        # headFrame uses the selected asset's exact runner-origin offset;
        # orthonormal rotation preserves vertex distance about its real ball.
        radius=max(math.sqrt(sum((a[i+k]+origin[k])**2 for k in range(3))) for i in range(0,len(a),6))
        radii[p['frame']]=max(radii.get(p['frame'],0),radius)
    need(set(radii)=={'RUNNER_NEG','RUNNER_POS'},'Both actual captured runners required')
    result={}
    for v,row in variants.items():
        need(row['reference_foot_midpoint_m']==[0,0,0] and row['stance_quaternion_xyzw']==[0,1,0,0],'Actual fixed180degree source reference required')
        bands=row['height_slices_1m'];need(bands,'Complete actual height hulls required');boxes=[]
        for band in bands:
            low,high=band['height_band_m'];polygon=band['actual_clipped_XZ_convex_hull_m']
            # A highest triangle edge can clip to two points exactly on the
            # next slab boundary. It is still actual geometry and stays in bounds.
            need(high>low and polygon,'Actual nonempty clipped height hull required')
            for p in polygon:point(p,2)
            boxes.append([min(p[0] for p in polygon),low,min(p[1] for p in polygon),max(p[0] for p in polygon),high,max(p[1] for p in polygon)])
        sole=[(nominal[str(v)]['l'][i]+nominal[str(v)]['r'][i])/2 for i in range(3)];spheres=[];root_boxes=[]
        for part in model['parts']:
            if part['frame']!='ROOT':continue
            a=part['triangles_rgb'];need(a and len(a)%18==0,'Actual static outer triangle stride6 required')
            vertices=[[-a[i]+sole[0],a[i+1]-sole[1],-a[i+2]+sole[2]] for i in range(0,len(a),6)]
            box=[min(p[k] for p in vertices) for k in range(3)]+[max(p[k] for p in vertices) for k in range(3)]
            boxes.append(box);root_boxes.append(dict(part=part['name'],bounds_foot_local_m=box))
        for pin,side,frame in [(mounts[0],-1,'RUNNER_NEG'),(mounts[1],1,'RUNNER_POS')]:
            centre=[-pin[0]+sole[0],pin[1]-sole[1],-pin[2]+sole[2]];radius=radii[frame]
            box=[n-radius for n in centre]+[n+radius for n in centre];boxes.append(box)
            spheres.append(dict(side=side,actual_ball_root_local_m=pin,actual_runner_origin_from_ball_local_m=origin,
                                centre_foot_local_m=centre,actual_vertex_radius_m=radius,bounds_m=box))
        legacy=read(ASSET/'mesh/legacy_running_heads_r52.json');legacy_boxes=[]
        # Match the actual partsAtR52 transform constants, fail on source drift.
        helper=(ROOT/'src/main/java/com/projectseele/world/NervLegacyCarrierRideR52.java').read_text('utf8')
        need('MAX_DROP=5.40' in helper and '-1.895-.18-k*(j.drop()+.01)/31' in helper and 'double x=side*6,z=row*10' in helper,'Actual Legacy transform changed; refresh reservation producer')
        for side in (-1,1):
            for row_ in (-1,1):
                for member in legacy['members']:
                    if member['role']!='moving_bogie_template':continue
                    name=member['part'];a=legacy['parts'][name];xyz=[a[i:i+3] for i in range(0,len(a),6)]
                    if name.startswith('ride_telescope_'):
                        k=int(name.rsplit('_',1)[1]);lo=-1.895-.18-k*(5.40+.01)/31;hi=-1.895-.18-k*.01/31
                        box=[-side*6-max(p[0] for p in xyz)+sole[0],lo+min(p[1] for p in xyz)-sole[1],-row_*10-max(p[2] for p in xyz)+sole[2],-side*6-min(p[0] for p in xyz)+sole[0],hi+max(p[1] for p in xyz)-sole[1],-row_*10-min(p[2] for p in xyz)+sole[2]]
                    elif name in ('ride_top_bearing','ride_roof_connector'):
                        box=[-side*6-max(p[0] for p in xyz)+sole[0],-1.895+min(p[1] for p in xyz)-sole[1],-row_*10-max(p[2] for p in xyz)+sole[2],-side*6-min(p[0] for p in xyz)+sole[0],-1.895+max(p[1] for p in xyz)-sole[1],-row_*10-min(p[2] for p in xyz)+sole[2]]
                    else:
                        radius=max(math.sqrt(sum(c*c for c in p)) for p in xyz);centre=[-side*6+sole[0],-2.12-sole[1],-row_*10+sole[2]]
                        box=[centre[0]-radius,centre[1]-5.40-radius,centre[2]-radius,centre[0]+radius,centre[1]+radius,centre[2]+radius]
                    legacy_boxes.append(box)
        need(len(legacy_boxes)==148,'Actual four Legacy joints and37pieces each required')
        boxes.extend(legacy_boxes)
        bounds=[min(b[i] for b in boxes) for i in range(3)]+[max(b[i+3] for b in boxes) for i in range(3)]
        result[v]=dict(bounds_m=bounds,height_slices_1m=bands,continuous_runner_ball_bounds=spheres,
                       continuous_outer_root_part_bounds=root_boxes,continuous_legacy_joint_bounds=legacy_boxes)
    return result

def prepare(args):
    need(sha(args.ground)==args.ground_sha256 and sha(args.hulls)==args.hulls_sha256,'Explicit actual ground/hull SHA differs')
    ground,hulls=read(args.ground),read(args.hulls);before=copy.deepcopy(ground)
    need(hulls['schema']=='projectseele.r52.actual-outer-upright-height-hulls.v1' and hulls['root_design_sha256']==args.ground_sha256,'Fresh actual outer-capture hull/design pair required')
    need(len(ground['legs'])==36 and len(ground['routes'])==18 and all(r.get('motion_profile',{}).get('type')=='continuous_upright' for r in ground['routes']),'Actual36leg/18route continuous design required; retired Dock rejected')
    model_path=ASSET/'mesh/upright_outer_captured_r52.json';model=read(model_path)
    need(hulls['model_source_sha256']==sha(model_path) and model['original_full_source_sha256']==sha(ASSET/'eva/full_assembly_geometry_r52_sources.json') and model['original_running_source_sha256']==sha(ASSET/'mesh/legacy_running_heads_r52.json'),'Actual complete selected model/full/Legacy sources differ')
    for v,expected in enumerate(hulls['body_snapshot_sha256']):
        snapshot=args.hulls.parent/f'INNER_RAIL_ACTUAL_FULL_PROBE.json.variant{v}.actual_mesh.bin.gz'
        need(snapshot.is_file() and sha(snapshot)==expected,'Actual full triangle snapshot authority differs')
    nodes={n['id']:n for n in ground['nodes']}
    need(all(n['foot_frame']['quaternion_xyzw']==[0,0,0,1] for n in nodes.values()),'Fixed foot/deck frame required')
    need(all(l['motion']!='FOOT_BEARING_TURN' and l['eva_from_xyzw']==[0,1,0,0] and l['eva_to_xyzw']==[0,1,0,0] for l in ground['legs']),'Constant actual prepared EVA stance required')
    locals_=local_sources(hulls,model);resources={r['id']:r for r in ground['resources']};bindings={r['resource']:r for r in ground['runtime']['bindings']}
    need(len(resources)==len(ground['resources']) and len(bindings)==len(ground['runtime']['bindings']),'Duplicate actual resource/native binding')
    added,rows,tickets=set(),[],set()
    def reserve(leg,box):
        point(box,6);need(all(box[i+3]>box[i] for i in range(3)),'Actual finite assembly extent required');cells=[]
        for x in range(math.floor((box[0]-.005)/32),math.floor((box[3]+.005)/32)+1):
            for y in range(math.floor((box[1]-.005)/32),math.floor((box[4]+.005)/32)+1):
                for z in range(math.floor((box[2]-.005)/32),math.floor((box[5]+.005)/32)+1):
                    name=f'space/c{x}_{y}_{z}';cells.append(name);r=dict(id=name,kind='SPACE',component=name)
                    b=dict(resource=name,component=name,spaces=[[x*32,y*32,z*32,(x+1)*32,(y+1)*32,(z+1)*32]])
                    need(name not in resources or resources[name]==r,'Existing SPACE identity differs');need(name not in bindings or bindings[name]==b,'Existing SPACE native grid differs')
                    if name not in resources:added.add(name)
                    resources[name]=r;bindings[name]=b
        leg['occupancy']=sorted(set(leg['occupancy'])|set(cells))
    for leg in ground['legs']:
        variants={r['variant'] for r in ground['routes'] if leg['id'] in r['legs']};need(len(variants)==1,'Actual unique route variant per leg required')
        v=next(iter(variants));local=locals_[v]['bounds_m'];intervals=leg_intervals(leg,nodes);boxes=[];chunks=set()
        for controls,bound in intervals:
            box=[min(p[i] for p in controls)+local[i]-.005 for i in range(3)]+[max(p[i] for p in controls)+local[i+3]+.005 for i in range(3)]
            reserve(leg,box);boxes.append(box)
            for x in range(math.floor(box[0]/16),math.floor(box[3]/16)+1):
                for z in range(math.floor(box[2]/16),math.floor(box[5]/16)+1):chunks.add((x,z))
        tickets.update(chunks)
        rows.append(dict(leg=leg['id'],variant=v,source_curve_intervals=len(intervals),maximum_foot_interval_m=max(b for _,b in intervals),reservation_boxes=boxes,foot_curve_control_hulls=[p for p,_ in intervals],preload_chunks=[list(p) for p in sorted(chunks)]))
    pending=[];loading_rows=[]
    if args.outer_loading_report:
        need(args.outer_loading_sha256 and sha(args.outer_loading_report)==args.outer_loading_sha256,'Explicit actual added-part loading report SHA differs')
        loading=read(args.outer_loading_report)
        need(loading['model_source_sha256']==sha(model_path) and loading['ground_sha256']==args.ground_sha256 and
             loading['world_written'] is False and loading['native_admission'] is False,'Actual selected model/ground bounds-only report required')
        need(loading.get('floor_overlay_sha256')==sha(ASSET/'mesh/legacy_floor_recesses_r52.json') and loading.get('original_running_source_sha256')==sha(ASSET/'mesh/legacy_running_heads_r52.json'),'Fresh loading/Legacy bounds must be exported from exact base plus independent floor overlay provider')
        lift=loading['original_lift_and_six_supports'];retained=loading['retained_original_legacy_legs']
        need(len(lift)==3 and {r['variant'] for r in lift}=={0,1,2} and len(retained)==9,'Actual three loading states/nine Legacy legs required')
        legs={l['id']:l for l in ground['legs']}
        def actual_box(b):
            box=point([b[k] for k in ('minX','minY','minZ','maxX','maxY','maxZ')],6)
            need(all(box[k]<=box[k+3] for k in range(3)),'Actual added-part bounds inverted');return box
        def reserve_actual(leg,box):
            reserve(leg,box)
            for x in range(math.floor(box[0]/16),math.floor(box[3]/16)+1):
                for z in range(math.floor(box[2]/16),math.floor(box[5]/16)+1):tickets.add((x,z))
        for row in lift:
            v=row['variant'];stroke=row['actual_original_lift_stroke_m'];need(stroke==64,'Actual original lift stroke changed')
            need(row['actual_rise0_outer_parts'],'Actual loading added parts missing')
            boxes_=[actual_box(p['world_bounds']) for p in row['actual_rise0_outer_parts']]
            box=[min(b[k] for b in boxes_) for k in range(3)]+[max(b[k+3] for b in boxes_) for k in range(3)]
            # Report uses actual rise0 Root. Original lift is pure +Y64m;
            # reserve its entire translation, never only the upper bay state.
            box[4]+=stroke;box=[q-.005 if k<3 else q+.005 for k,q in enumerate(box)]
            root=row['actual_bay_root'];q=[root[k] for k in ('qx','qy','qz','qw')]
            need(q==[0,1,0,0],'Actual immutable loading Root stance differs')
            p=root['translation'];sole_bindings=read(ASSET/'mesh/foot_guide_rig_r52.json')['nominal_sole_bindings'][str(v)]
            sole=[(sole_bindings['l'][k]+sole_bindings['r'][k])/2 for k in range(3)]
            foot=[p['x']-sole[0],p['y']-stroke+sole[1],p['z']-sole[2]];local=locals_[v]['bounds_m']
            full=[foot[k]+local[k]-.005 for k in range(3)]+[foot[k]+local[k+3]+.005 for k in range(3)]
            full[4]+=stroke
            box=[min(box[k],full[k]) for k in range(3)]+[max(box[k+3],full[k+3]) for k in range(3)]
            for name in (f'unit{v}/original_incline',f'unit{v}/original_incline/reverse'):reserve_actual(legs[name],box)
            loading_rows.append(dict(variant=v,phase='actual_original_lift_rise0_to64',reservation_box=box,
                includes_selected_outer_template=True,includes_original_eva_plug_carrier_and_legacy=True,
                actual_rise0_foot_reference=foot,whole_selected_assembly_control_bound=full,native_admission=False))
        for row in retained:
            name=row['leg'];need(name in legs and row['actual_distance_samples']>1,'Actual retained added-part leg missing')
            boxes_=[actual_box(b) for b in row['actual_added_parts_world_bounds'].values()];need(boxes_,'Actual retained added parts missing')
            box=[min(b[k] for b in boxes_) for k in range(3)]+[max(b[k+3] for b in boxes_) for k in range(3)]
            for key in (name,name+'/reverse'):reserve_actual(legs[key],box)
            loading_rows.append(dict(leg=name,phase='actual_added_part_sample_bounds',reservation_box=box,
                continuous_padding_authority='Selected-model all-orientation ball/control hull bounds already cover all route intervals',native_admission=False))
        pending.append('Selected0262 wet/Legacy native floor/collision admission remains separate from consumed added-part reservation bounds')
    else:pending.append('Fresh selected-model outer loading/Legacy added-part bounds not consumed; old Legacy lead alone excludes the new Outer template')
    if args.lead_report:
        lead=read(args.lead_report)
        need(lead['source']==sha(ASSET/'mesh/legacy_running_heads_r52.json') and lead['full_source']==model['original_full_source_sha256'] and lead['legacy_helper_java_sha256']==sha(ROOT/'src/main/java/com/projectseele/world/NervLegacyCarrierRideR52.java'),'Fresh actual Legacy lead producer required')
        need(lead.get('floor_overlay_sha256')==lead.get('actual_floor_overlay_bytes_sha256')==sha(ASSET/'mesh/legacy_floor_recesses_r52.json'),'Fresh actual Legacy provider must lock independent floor overlay; original63fa remains unchanged')
        need(len(lead['rows'])==3 and {r['variant'] for r in lead['rows']}=={0,1,2},'Actual three Legacy actuator bounds required');legs={l['id']:l for l in ground['legs']}
        for row in lead['rows']:
            for name in (f"unit{row['variant']}/original_incline",f"unit{row['variant']}/original_incline/reverse"):reserve(legs[name],row['source_bounds'])
            box=row['source_bounds']
            for x in range(math.floor(box[0]/16),math.floor(box[3]/16)+1):
                for z in range(math.floor(box[2]/16),math.floor(box[5]/16)+1):tickets.add((x,z))
    else:pending.append('Fresh actual Legacy bay actuator bounds must be supplied before final bundle')
    if args.guide_source:
        need(args.guide_source.is_file(),'Explicit final guide source file is absent')
        need(args.guide_source.stat().st_size<=256_000_000,'Actual upright source exceeds its explicit256MB component bound')
        guide=read(args.guide_source)
        need(guide.get('schema')=='projectseele.r52.upright-captured-paths.v1' and guide.get('model_source_sha256')==sha(model_path) and guide.get('anchors') and guide.get('paths') and guide.get('pieces'),'Actual complete anchored guide source required')
    guide_sha=sha(args.guide_source) if args.guide_source else None
    if guide_sha is None:pending.append('Final anchored guideway source bytes/typed native bearings absent; candidate cannot install')
    ground['resources']=list(resources.values());ground['runtime']['bindings']=list(bindings.values())
    ground['space_domains']=[dict(id=name,dimension='projectseele:geofront',bounds=box,grid_metres=32,max_step_cells=8192) for name,box in [('r52/surface_field_air',[-4288,-192,-8384,8384,1216,4288]),('r52/geofront_field_air',[-4288,-736,-4288,4288,160,4288])]]
    ground['status']='design';ground['root_construction_note']='Unchanged actual continuous Root routes with fresh full source SPACE; native clearance, gates, bearings and commissioning remain separately required.'
    need(all(ground[k]==before[k] for k in ('units','nodes','routes','ports')) and all({k:v for k,v in a.items() if k!='occupancy'}=={k:v for k,v in b.items() if k!='occupancy'} for a,b in zip(ground['legs'],before['legs'])),'Prepared directory changed actual Root geometry')
    inputs={str(p.resolve()):sha(p) for p in (args.ground,args.hulls,model_path,ASSET/'mesh/foot_guide_rig_r52.json',ASSET/'mesh/legacy_running_heads_r52.json',ASSET/'mesh/legacy_floor_recesses_r52.json',ASSET/'eva/full_assembly_geometry_r52_sources.json',ROOT/'src/main/java/com/projectseele/world/NervLegacyCarrierRideR52.java',Path(__file__))}
    for p in (args.lead_report,args.guide_source,args.outer_loading_report):
        if p and p.is_file():inputs[str(p.resolve())]=sha(p)
    env=dict(schema='projectseele.r52.continuous-source-reservation-envelopes.v1',world_written=False,native_acceptance=False,directory_matches=True,directory_geometry_sha256=args.ground_sha256,full_source_sha256=model['original_full_source_sha256'],model_source_sha256=sha(model_path),path_source_sha256=guide_sha,actual_height_hulls_sha256=args.hulls_sha256,continuous_bound='Bezier convex control hulls; monotone cosine-ramp bounds; actual runner vertex ball radii for every intermediate orientation. Reservation/tickets only; no native collision/bearing PASS.',local_height_footprints=[dict(variant=v,**data) for v,data in sorted(locals_.items())],root_legs=rows,added_outer_loading_and_legacy_reservations=loading_rows,legacy_lead_scope='Unchanged Legacy bay actuators only; does not include selected Outer template',preload_chunks=[list(p) for p in sorted(tickets)],pending=pending,source_inputs=inputs)
    env['legacy_floor_overlay_sha256']=sha(ASSET/'mesh/legacy_floor_recesses_r52.json')
    args.out.mkdir(parents=True,exist_ok=True)
    def write(name,doc):
        p=args.out/name;p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return p
    files=[write('GROUND_SOURCE_SPACES.json',ground),write('CONTINUOUS_SOURCE_RESERVATION_ENVELOPES.json',env)]
    receipt=dict(prepared_only=True,world_written=False,native_verified=False,source_inputs=inputs,source_directory_sha256=args.ground_sha256,leg_count=len(rows),new_grid_resources=len(added),body_preload_chunk_count=len(tickets),pending=pending,unchanged_geometry_routes_ports_units=True,outputs={str(p.resolve()):sha(p) for p in files})
    write('GROUND_SPACE_RECEIPT.json',receipt);return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true',required=True)
    p.add_argument('--ground',type=Path,required=True);p.add_argument('--ground-sha256',required=True);p.add_argument('--hulls',type=Path,required=True);p.add_argument('--hulls-sha256',required=True)
    p.add_argument('--guide-source',type=Path);p.add_argument('--lead-report',type=Path)
    p.add_argument('--outer-loading-report',type=Path);p.add_argument('--outer-loading-sha256')
    p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    for parent in (args.out.resolve(),*args.out.resolve().parents):need(not (parent/'level.dat').exists() and not (parent/'session.lock').exists(),'Candidate output must remain outside every actual World')
    print(json.dumps(prepare(args)),flush=True)
if __name__=='__main__':main()
