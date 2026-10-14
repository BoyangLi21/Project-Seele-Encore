"""Read actual18 continuous/Legacy rail bearings and nine receivers.

Produces explicit typed requirements/resources in a candidate directory only.
Side and top anchors use the same9point/.0002m native shape face check as the
production upright provider. Source geometry/gate sweeps remain separate proof.
"""
import argparse, copy, gzip, hashlib, json, math, uuid, zipfile
from collections import defaultdict, Counter
from pathlib import Path
from query_blocks import iter_selected_sections
from root_bundle_authority_r53 import arguments as authority_arguments, validate as world_authority, candidate as candidate_path
from prepare_ground_space_r52 import need, sha, read, point
from wet_front_seal_manifest_r52 import validate_seal_phase_tables, phase_rows
from build_immutable_r52_candidate import frozen_build_class_pins
ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'src/main/resources/assets/projectseele'

SELECTED_RESOURCES=('mesh/tv_shoulder_shells_r44.json',
                    'mesh/tv_facilities_r16.json',
                    'mesh/cage_lower_telescopes_r52.json',
                    'mesh/legacy_floor_recesses_r52.json',
                    'mesh/legacy_service_bypass_r52.json',
                    'mesh/legacy_compact_level_r52.json',
                    'mesh/legacy_deep_frame_r53.json',
                    'mesh/outer_head_transfer_r53.json',
                    'mesh/upright_outer_captured_r52.json',
                    'mesh/legacy_running_heads_r52.json',
                    'mesh/foot_guide_rig_r52.json',
                    'eva/full_assembly_geometry_r52_sources.json')

def selected_sources(args):
    # The immutable build selects overlays; src raw bytes are not authority.
    # Verify the actual frozen build/Jar first, then hash its exact resources.
    pins=frozen_build_class_pins(args.selected_build_receipt,args.selected_jar)
    with zipfile.ZipFile(args.selected_jar) as archive:
        need(len(archive.namelist())==len(set(archive.namelist())),'Ambiguous duplicate selected Jar entry')
        hashes={name:hashlib.sha256(archive.read('assets/projectseele/'+name)).hexdigest() for name in SELECTED_RESOURCES}
        cage_receipt=json.loads(archive.read('assets/projectseele/eva/cage_collision_r52_sources.json'))
        need(cage_receipt.get('resource')=='mesh/tv_shoulder_shells_r44.json' and cage_receipt.get('sha256')==hashes[cage_receipt['resource']],'Actual selected Jar cage receipt differs')
    return hashes,dict(jar=str(args.selected_jar.resolve()),jar_sha256=sha(args.selected_jar),
        build_receipt=str(args.selected_build_receipt.resolve()),build_receipt_sha256=sha(args.selected_build_receipt),
        selected_resources=hashes,verified_delivery_class_count=len(pins),
        local_raw_resource_shas={name:sha(ASSET/name) for name in SELECTED_RESOURCES},
        cage_collision_receipt=cage_receipt)

def face_points(anchor):
    n=point(anchor['normal']);p=point(anchor['bearing']);at=anchor['at']
    need(sum(c*c for c in n)==1 and sum(abs(c) for c in n)==1,'Actual axis unit native face normal required')
    axis=next(i for i in range(3) if n[i]);u=[0,1,0] if axis==0 else [1,0,0]
    v=[n[1]*u[2]-n[2]*u[1],n[2]*u[0]-n[0]*u[2],n[0]*u[1]-n[1]*u[0]]
    half=float(anchor.get('contact_half_width_m',.05));need(math.isfinite(half) and 0<half<=.5,'Actual finite native face half-width required')
    return n,axis,[[p[i]+a*u[i]+b*v[i] for i in range(3)] for a in (-half,0,half) for b in (-half,0,half)]

def face_backing_cells(anchor):
    n,axis,points=face_points(anchor)
    return {tuple(math.floor(q[i]-n[i]*1e-5) for i in range(3)) for q in points}

def face_bears(anchor,shapes):
    n,axis,points=face_points(anchor);at=anchor['at']
    boxes=[[local[i]+at[i%3] for i in range(6)] for local in shapes]
    # A real finite plate can straddle two adjacent native cells. Every probe
    # still needs an actual coplanar collision face; no width is reduced.
    return all(any(abs(q[axis]-(box[axis+3] if n[axis]>0 else box[axis]))<=.0002 and all(box[i]-.0002<=q[i]<=box[i+3]+.0002 for i in range(3)) for box in boxes) for q in points)

def face_native_union(anchor,states,shapes):
    at=anchor['at'];result=[]
    for cell in face_backing_cells(anchor):
        state=states.get(cell)
        for box in shapes.get(state,[]):result.append([box[i]+cell[i%3]-at[i%3] for i in range(6)])
    return result

def declared_gate_anchor(cell):
    need('normal' in cell and set(cell.get('source_contact',{}))=={'x','y','z'} and 'contact_half_width_m' in cell,'Complete actual gate face contact and finite half-width provenance required')
    half=float(cell['contact_half_width_m']);need(math.isfinite(half) and 0<half<=.5 and cell.get('half_width_m',half)==half,'Actual gate finite face half-width differs')
    return dict(at=cell['position'],normal=cell['normal'],bearing=[cell['source_contact'][k] for k in ('x','y','z')],contact_half_width_m=half)

def prepare(args):
    selected_hashes,selection=selected_sources(args)
    authority=world_authority(args)
    need(args.guide_source.stat().st_size<=256_000_000,'Actual upright source exceeds its explicit256MB component bound')
    need(sha(args.design)==args.design_sha256 and sha(args.guide_source)==args.guide_source_sha256,'Explicit design/actual guide source SHA differs')
    design,ground,unitsdoc,gatesdoc,staffdoc=[read(p) for p in (args.design,args.ground,args.units,args.gates,args.staff)]
    world_authority(args,directory=design)
    seals=validate_seal_phase_tables(gatesdoc['gates'],lambda g:phase_rows(g,args.gates.parent))
    guide=read(args.guide_source)
    for key in ('units','nodes','routes','ports'):need(ground[key]==design[key],'Actual ground/design topology differs: '+key)
    need([{k:v for k,v in l.items() if k!='occupancy'} for l in ground['legs']]==[{k:v for k,v in l.items() if k!='occupancy'} for l in design['legs']],'Actual ground/design curves differ')
    need(len(ground['legs'])==36 and len(ground['routes'])==18 and all(r.get('motion_profile',{}).get('type')=='continuous_upright' for r in ground['routes']),'Actual36leg continuous design required; retired42rail/Dock rejected')
    need(guide.get('schema')=='projectseele.r52.upright-captured-paths.v1' and guide.get('model_source_sha256')==selected_hashes['mesh/upright_outer_captured_r52.json'] and guide.get('head_transfer_source_sha256')==selected_hashes['mesh/outer_head_transfer_r53.json'] and guide.get('supports_complete') is True and guide.get('anchors') and guide.get('pieces'),'Final actual selected Jar guideway and complete supports declaration required')
    units={u['variant']:u for u in unitsdoc['units']};gates=gatesdoc['gates'];gate_index={g['resource']:g for g in gates};legs={l['id']:l for l in ground['legs']};nodes={n['id']:n for n in ground['nodes']}
    need(set(units)=={0,1,2} and len(gates)==len(gate_index) and gates,'Actual three original units and unique explicitly declared gates required')
    aliases={}
    for r in ground['resources']:
        if r['id'] in aliases:r['id']=aliases[r['id']];r['component']=aliases.get(r['component'],r['component'])
    for leg in ground['legs']:leg['doors']=[aliases.get(k,k) for k in leg['doors']]
    need({r['id'] for r in ground['resources'] if r['kind']=='DOOR'}==set(gate_index),'Ground requires the exact complete physical gate identity set; supply fresh air grid ground')
    need(not staffdoc.get('issues') and len({s['original_uuid'] for s in staffdoc['staff']})==len(staffdoc['staff']),'Actual original staff readback contains issues/duplicate identities')
    path_index={p['leg']:p for p in guide['paths']};wanted_curves={l['id'] for r in ground['routes'] if not r.get('reverse_of') for l in [legs[k] for k in r['legs']] if 'centre_curve'in l}
    need(set(path_index)==wanted_curves and len(wanted_curves)==9,'Actual nine unique forward guideway paths required')
    steel={p['name']:p for p in guide['pieces']};anchors=defaultdict(list)
    for a in guide['anchors']:
        need(a['leg'] in path_index and a['seat_piece'] in steel and steel[a['seat_piece']]['component']=='native_seat' and steel[a['seat_piece']]['leg']==a['leg'],'Actual native seat/leg identity differs')
        anchors[a['leg']].append(a)
    requirements=[]
    for resource in (r for r in ground['resources'] if r['kind']=='RAIL'):
        uses=[l for l in ground['legs'] if resource['id'] in l['rails']];forward=[l for l in uses if not l['id'].endswith('/reverse')]
        need(len(uses)==2 and len(forward)==1 and forward[0]['id']+'/reverse' in {l['id'] for l in uses},'Actual unique forward/reverse rail pair required')
        leg=forward[0];variants={r['variant'] for r in ground['routes'] if leg['id'] in r['legs']};need(len(variants)==1,'Actual unique original rail variant required');variant=next(iter(variants))
        if 'centre_curve'in leg:
            path=path_index[leg['id']]
            canonical=lambda curve:[s['controls'] for s in curve['segments']]
            need(path['reverse_leg']==leg['id']+'/reverse' and path['variant']==variant and path['from']==nodes[leg['from']]['foot_frame'] and path['to']==nodes[leg['to']]['foot_frame'] and canonical(path['centre_curve'])==canonical(leg['centre_curve']) and anchors[leg['id']],'Actual source path/Root geometry differs')
            cells={tuple(a['at']):a['state'] for a in anchors[leg['id']]}
            for a in anchors[leg['id']]:need(cells[tuple(a['at'])]==a['state'],'Actual anchors disagree on native state')
            spec=dict(kind='UPRIGHT_CAPTURED_GUIDEWAY',leg=leg['id'],source_sha256=args.guide_source_sha256,guide_source_sha256=guide['model_source_sha256'],controller_uuid=None,foundation_top_m=None)
        else:
            need(leg['motion'] in ('ORIGINAL_UPRIGHT_TRANSFER','TRACKED_BANK_TRANSFER'),'Retired mechanical rail family rejected')
            unit=units[variant];cells={tuple(c['position']):c['state'] for c in unit['gantry']['supports']+unit['carrier_support']}
            spec=dict(kind='LEGACY_RUNNING_HEAD',leg=leg['id'],source_sha256=selected_hashes['mesh/legacy_running_heads_r52.json'],floor_overlay_sha256=selected_hashes['mesh/legacy_floor_recesses_r52.json'],service_overlay_sha256=selected_hashes['mesh/legacy_service_bypass_r52.json'],level_overlay_sha256=selected_hashes['mesh/legacy_compact_level_r52.json'],deep_frame_sha256=selected_hashes['mesh/legacy_deep_frame_r53.json'],guide_source_sha256=selected_hashes['mesh/foot_guide_rig_r52.json'],controller_uuid=unit['gantry']['id'])
        requirements.append(dict(resource=resource['id'],mechanical_rail=spec,cells=[dict(position=list(p),state=s) for p,s in sorted(cells.items())]))
    need(len(requirements)==18 and Counter(r['mechanical_rail']['kind'] for r in requirements)=={'UPRIGHT_CAPTURED_GUIDEWAY':9,'LEGACY_RUNNING_HEAD':9},'Exact9upright/9Legacy typed rails required')
    wanted={tuple(c['position']) for r in requirements for c in r['cells']}|{tuple(c['position']) for g in gates for c in g['supports']}|{tuple(c['position']) for s in staffdoc['staff'] for c in s['support']};selected=defaultdict(set);sections=defaultdict(set);states={}
    finite_gate_faces=[declared_gate_anchor(c) for g in gates for c in g['supports'] if 'normal' in c or 'source_contact' in c]
    finite_seal_faces=[a for seal in seals.values() for a in seal['wall_bearings']]
    face_cells=set().union(*(face_backing_cells(a) for a in finite_gate_faces+finite_seal_faces))
    wanted|=face_cells
    for x,y,z in wanted:selected[x//16,z//16].add(y//16);sections[x//16,z//16,y//16].add((x,y,z))
    for cx,cz,sy,palette,ix in iter_selected_sections(args.world,'projectseele:geofront',selected):
        a=ix.reshape(16,16,16)
        for x,y,z in sections[cx,cz,sy]:states[x,y,z]=palette[int(a[y%16,z%16,x%16])]
    need(len(states)==len(wanted),'Actual native required sections absent; do not invent missing cell states')
    shapes=read(args.world/'native_collision_shapes.json');resources={};pending=[];face_count=0
    declared_gate_face_count=0
    for role,rows in [('gate',gates),('staff',staffdoc['staff'])]:
        for row in rows:
            for c in row['supports' if role=='gate' else 'support']:
                if states[tuple(c['position'])]!=c['state']:pending.append(dict(role=role,id=row.get('resource',row.get('id')),position=c['position'],expected=c['state'],actual=states[tuple(c['position'])]))
                if role=='gate' and ('normal' in c or 'source_contact' in c):
                    declared_gate_face_count+=1;a=declared_gate_anchor(c)
                    if not face_bears(a,face_native_union(a,states,shapes)):pending.append(dict(role='declared_gate_face',id=row['resource'],anchor=a,actual=states[tuple(c['position'])],reason='Actual declared gate native face does not bear all nine points'))
    seal_face_count=0
    for seal in seals.values():
        for a in seal['wall_bearings']:
            seal_face_count+=1
            if not face_bears(a,face_native_union(a,states,shapes)):pending.append(dict(role='wet_seal_wall_bearing',id=a['resource'],anchor=a,actual=states[tuple(a['at'])],reason='Actual .20m wall plate nine-point face does not bear'))
    for r in requirements:
        spec=r['mechanical_rail'];missing=[]
        for c in r['cells']:
            p=tuple(c['position']);actual=states[p]
            if actual!=c['state']:missing.append(dict(position=list(p),actual=actual,expected=c['state']));continue
            if spec['kind']=='LEGACY_RUNNING_HEAD' and not any(b[1]<=0 and b[4]>=1 and b[0]<=0 and b[2]<=0 and b[3]>=1 and b[5]>=1 for b in shapes.get(actual,[])):missing.append(dict(position=list(p),actual=actual,reason='Actual full upper support face missing'))
        if spec['kind']=='UPRIGHT_CAPTURED_GUIDEWAY':
            for anchor in anchors[spec['leg']]:
                face_count+=1
                if not face_bears(anchor,shapes.get(states[tuple(anchor['at'])],[])):missing.append(dict(anchor=anchor,reason='Actual native9point declared face does not bear'))
        if missing:pending.append(dict(leg=spec['leg'],missing=missing))
        else:
            resources[r['resource']]=r['cells']
            for l in legs.values():
                if r['resource'] in l['rails']:resources[l['support']]=r['cells']
    receivers=[]
    for port in ground['ports']:
        variant=int(next(iter(port['reverse_routes'])));unit=units[variant];route=next(r for r in ground['routes'] if r['id']==port['reverse_routes'][str(variant)]);gate=gate_index[f"bank_{route['bank']}_surface_lane_{route['lane']}"]
        position=nodes[port['node']]['foot_frame']['translation'].copy();position[2]+=unit['bay_frame']['position'][2]-nodes[f'unit{variant}/bay']['foot_frame']['translation'][2]
        supports=gate['supports']
        for c in supports:need(states[tuple(c['position'])]==c['state'],'Actual receiver support state changed')
        table=gate['collision_steps'];file=(args.gates.parent/table['cells_file']).resolve();need(file.is_relative_to(args.gates.parent.resolve()) and sha(file)==table['sha256'],'Actual receiver phase table bytes differ')
        collision=json.loads(gzip.decompress(file.read_bytes()));levels={c['position'][1] for step in collision for c in step}
        need(len(levels)==1 and all(c['closed']=='minecraft:barrier' and c['open']=='minecraft:air' for step in collision for c in step),'Actual receiver hatch collision states required')
        low=next(iter(levels));need(abs(gate['frame']['position'][1]-(low+.02))<1e-8,'Actual receiver hatch frame differs')
        receivers.append(dict(port=port['id'],region=port['region'],domain=[position[0]-15.5,low-1,position[2]-15.5,position[0]+15.5,position[1]+8,position[2]+15.5],stopped_frame=dict(position=position,quaternion=[0.,1.,0.,0.]),supports=supports,gates=[gate['resource']],carrier_ticks=unit['carrier_raise_ticks']))
    need(len(receivers)==9,'Actual nine receivers required')
    args.out.mkdir(parents=True,exist_ok=True)
    def write(name,doc):
        p=args.out/name;p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n','utf8');return p
    inputs={str(p.resolve()):sha(p) for p in (args.design,args.ground,args.guide_source,args.units,args.gates,args.staff,args.world/'native_collision_shapes.json',Path(__file__),ROOT/'tools/wet_front_seal_manifest_r52.py',args.selected_jar,args.selected_build_receipt,args.selected_build_receipt.parent/'SOURCE_BEFORE.json',args.baseline,args.root_plan)}
    for g in gates:
        if isinstance(g['collision_steps'],dict):
            p=(args.gates.parent/g['collision_steps']['cells_file']).resolve();inputs[str(p)]=sha(p)
    outputs=[write('MECHANICAL_RAIL_REQUIREMENTS.json',dict(directory_geometry_sha256=args.design_sha256,model_source_sha256=guide['model_source_sha256'],path_source_sha256=args.guide_source_sha256,mechanical_rail_requirements=requirements)),write('ROOT_MECHANICAL_RESOURCES.json',dict(resources=resources)),write('ROOT_RECEIVERS.json',dict(receivers=receivers))]
    report=dict(world_written=False,native_verified=False,actual_world_root=args.world.as_posix(),root_world_authority=authority,feature_scope="124",ready_rail_and_support_pairs=len(resources)//2,typed_rail_count=len(requirements),actual_native_face_count=face_count,actual_declared_gate_face_count=declared_gate_face_count,wet_floor_seal_count=len(seals),wet_floor_phase_cell_count=sum(len(s['cells']) for s in seals.values()),actual_wet_seal_wall_face_count=seal_face_count,measured_cells=len(states),receivers=len(receivers),pending=pending,selected_source_manifest=selection,source_inputs=inputs,outputs={str(p.resolve()):sha(p) for p in outputs})
    report['actual_declared_gate_face_half_width_counts']={str(k):v for k,v in Counter(a['contact_half_width_m'] for a in finite_gate_faces).items()}
    report['actual_gate_face_backing_cells']=[dict(position=list(p),state=states[p],native_boxes=shapes.get(states[p],[])) for p in sorted(face_cells)]
    report['gate_face_validation']='All nine full-half-width world probes use measured coplanar collision faces, including adjacent backing cells; no support expansion or half-width reduction'
    report_file=write('ACTUAL_MECHANICAL_BINDINGS_READBACK.json',report)
    if not pending:
        # Every table stays relative to this new candidate; never import an old
        # QA/World or retain withdrawn station support/resource declarations.
        def table(ref,parent,group):
            if not isinstance(ref,dict):return copy.deepcopy(ref)
            relative=Path(ref['cells_file']);need(not relative.is_absolute() and '..' not in relative.parts and ':' not in str(relative),'Bounded same-source table required')
            source=(parent/relative).resolve();need(source.is_relative_to(parent.resolve()) and sha(source)==ref['sha256'],'Actual table authority differs')
            dest=args.out/'tables'/group/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(source.read_bytes())
            return dict(cells_file=dest.relative_to(args.out).as_posix(),sha256=sha(dest))
        owner_units=copy.deepcopy(unitsdoc['units']);owner_gates=copy.deepcopy(gates)
        full_sha=selected_hashes['eva/full_assembly_geometry_r52_sources.json']
        for u in owner_units:
            for key in ('bridge_states','lcl'):u[key]=table(u[key],args.units.parent,'units')
            raw=bytearray(hashlib.md5(f"projectseele:r52:original-carrier:{ground['epoch']}:{u['eva']}".encode()).digest());raw[6]=(raw[6]&15)|48;raw[8]=(raw[8]&63)|128
            actual=dict(id=str(uuid.UUID(bytes=bytes(raw))),source_sha256=full_sha)
            need('carrier_controller' not in u or u['carrier_controller']==actual,'Original proposed controller identity differs')
            u['carrier_controller']=actual
        for g in owner_gates:g['collision_steps']=table(g['collision_steps'],args.gates.parent,'gates')
        mechanism_sources={name:selected_hashes[name] for name in ('mesh/tv_shoulder_shells_r44.json','mesh/legacy_floor_recesses_r52.json','mesh/legacy_service_bypass_r52.json','mesh/legacy_compact_level_r52.json','mesh/legacy_deep_frame_r53.json','mesh/outer_head_transfer_r53.json')}
        need(all(value==selection['selected_resources'][name] for name,value in mechanism_sources.items()),'Every owner mechanism source must equal the actual selected Jar bytes')
        owner=dict(schema='projectseele.r52.mechanical-owner.v1',map_author='root',status='design',epoch=ground['epoch'],directory_fingerprint='0'*64,commissioning_receipt_sha256=sha(report_file),mechanism_sources=mechanism_sources,ground_guides=dict(mode='continuous_upright',source_sha256=guide['model_source_sha256'],paths_sha256=args.guide_source_sha256),units=owner_units,gates=owner_gates,resources=resources,receivers=receivers,staff=staffdoc['staff'])
        bindings={aliases.get(b['resource'],b['resource']):b for b in ground['runtime']['bindings']}
        by_resource={r['id']:r for r in ground['resources']}
        for r in requirements:bindings[r['resource']]=dict(resource=r['resource'],component=by_resource[r['resource']]['component'],mechanical_rail=r['mechanical_rail'],cells=r['cells'])
        for key,cells in resources.items():
            if by_resource[key]['kind']=='SUPPORT':bindings[key]=dict(resource=key,component=by_resource[key]['component'],cells=cells)
        for key,g in gate_index.items():bindings[key]=dict(resource=key,component=by_resource[key]['component'],entity_uuid=g['visual'],expected_type='projectseele:nerv_hangar_door' if g['kind']=='HANGAR' else 'projectseele:nerv_silo_door',required_open=1)
        ground['runtime']['bindings']=list(bindings.values())
        owner_file=write('ROOT_CONTINUOUS_OWNER_DESIGN.json',owner);native_file=write('NATIVE_CONTINUOUS_DIRECTORY_DESIGN.json',ground)
        write('OWNER_DIRECTORY_PREPARATION.json',dict(world_written=False,native_verified=False,commissioned=False,directory_geometry_sha256=args.design_sha256,readback_sha256=sha(report_file),outputs={str(p.resolve()):sha(p) for p in (owner_file,native_file)},pending=['Real production parser/commissioning requires final source and bundle fingerprint binding']))
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ground','design','guide-source','units','gates','staff','out','selected-jar','selected-build-receipt'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('design-sha256','guide-source-sha256'):p.add_argument('--'+name,required=True)
    authority_arguments(p)
    args=p.parse_args()
    args.out=candidate_path(args.out,args.world,True)
    need(not args.out.exists() or not any(args.out.iterdir()),'Fresh candidate output required; historical receipts must remain immutable')
    for parent in (args.out.resolve(),*args.out.resolve().parents):need(not (parent/'level.dat').exists() and not (parent/'session.lock').exists(),'Candidate output must remain outside actual Worlds')
    report=prepare(args);print(json.dumps({k:v for k,v in report.items() if k not in ('source_inputs','outputs')}),flush=True)
if __name__=='__main__':main()
