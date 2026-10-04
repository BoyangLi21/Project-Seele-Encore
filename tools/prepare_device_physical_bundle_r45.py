"""Combine the exact18+6+1 physical fixes on one immutable source, offline only."""
from __future__ import annotations
import argparse,ast,copy,gzip,hashlib,json,math,sys
from pathlib import Path
sys.dont_write_bytecode=True
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from prepare_school_hakone_native_r45 import ActualGeometry

LIFE=ROOT/'artifacts/rebuild_r45/lifts_doors_lifecycle_sol_v2'
PYRAMID=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1'
PARTS=[('command18',LIFE/'command_controls_v3',18),('MTR6',PYRAMID/'frozen_audit_v7',6),('compact1',LIFE/'small_lift_complete_v3',1)]
INTERFACE=ROOT/'artifacts/rebuild_r45/candidate_transport_acceptance_sol_v1/candidate_interfaces_bound.json'
CONSUMER_INTERFACE=INTERFACE.with_name('candidate_lifts_for_existing_consumer.json')
TRIPS=ROOT/'artifacts/rebuild_r45/candidate_transport_acceptance_sol_v1/all90_candidate_lift_trip_cases.UNBOUND.json'
SCHEMA='projectseele.device-physical-bundle-r45.v1'

def rows(p):return [json.loads(x)for x in gzip.open(p,'rt',encoding='utf8')]
def jsonl(p,data):
    encoded=''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n'for r in data).encode('utf8');p.write_bytes(gzip.compress(encoded,mtime=0))

def main(args):
    out=args.out.resolve();assert not out.exists() and not out.is_relative_to(WORLD) and 'saves'not in{p.lower()for p in out.parts}
    base=read(BASELINE);expected={r['relative']:r['sha256']for r in base['files']};assert len(expected)==1736
    def inventory():
        assert {p.relative_to(WORLD).as_posix()for p in WORLD.rglob('*')if p.is_file()}==set(expected)
        values={k:sha(WORLD/k)for k in sorted(expected)};assert values==expected;return values
    before=inventory();merged={};parts=[]
    for name,path,count in PARTS:
        fwd,inv=rows(path/'forward.jsonl.gz'),rows(path/'inverse.jsonl.gz');assert len(fwd)==len(inv)==count
        for a,b in zip(fwd,inv):
            q=tuple(a['pos']);assert q not in merged,'Independent proposals overlap; do not choose one silently'
            assert a['before_nbt']is None and a['after_nbt']is None
            assert a['pos']==b['pos'] and all(a[k]==b[v]for k,v in [('before','after'),('after','before'),('before_nbt','after_nbt'),('after_nbt','before_nbt')])
            merged[q]=dict(a,component=name)
        parts.append(dict(name=name,count=count,forward=dict(path=str(path/'forward.jsonl.gz'),sha256=sha(path/'forward.jsonl.gz')),inverse=dict(path=str(path/'inverse.jsonl.gz'),sha256=sha(path/'inverse.jsonl.gz'))))
    forward=[merged[q]for q in sorted(merged)];inverse=[dict(r,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt'])for r in forward];assert len(forward)==25
    command=read(LIFE/'command_controls_v3/proposal.json');marker=command['marker_file_proposal'];relative=marker['relative']
    marker_before=(LIFE/'command_controls_v3/command_marker.before.json').read_bytes();marker_after=(LIFE/'command_controls_v3/command_marker.after.json').read_bytes()
    assert (WORLD/relative).read_bytes()==marker_before and hashlib.sha256(marker_after).hexdigest()==marker['after_sha256']
    old,new=json.loads(marker_before),json.loads(marker_after);a,b=copy.deepcopy(old),copy.deepcopy(new)
    assert {r['id']for r in a['doors']}=={r['id']for r in b['doors']}==set(range(19))-{5,14}
    old_by={r['id']:r for r in a['doors']}
    for door in b['doors']:
        door.pop('fixedInputContractsR45');door['buttons']=old_by[door['id']]['buttons'];assert door==old_by[door['id']]
    assert a==b,'The control marker may not alter original device/layout/retirement fields'
    interfaces=read(INTERFACE);hardware=read(LIFE/'small_lift_complete_v3/all24_full_cabins_inputs_controllers_NBT.json')
    assert len(interfaces['interfaces'])==7 and len(hardware)==24
    m=MeasuredWorld(WORLD)
    for r in forward:m.around(r['pos'],4)
    for r in hardware:m.around(r['cabin_centre'],14)
    m.box((89,-371,-224),(110,-363,-204));m.box((8,-569,249),(16,-562,263));m.load();assert all(v=='full'for v in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-390,-672,-310),(170,319,790),selected_chunks=set(m.selected)))
    def full(q):
        q=tuple(q);t=tags.get(q);return dict(pos=list(q),state=m.block(q),full_nbt=None if t is None else t.snbt())
    for r in forward:assert full(r['pos'])==dict(pos=r['pos'],state=r['before'],full_nbt=r['before_nbt'])
    preserve={}
    def retain(q):
        q=tuple(q)
        if q not in merged:preserve[q]=full(q)
    # Full cabin hardware, all fixed apertures and every input path are read
    # from the same source, not inferred from a previous run's screenshots.
    for r in hardware:
        for key in('controller','outside_call','declared_handoff'):assert full(r[key]['pos'])==r[key];retain(r[key]['pos'])
        for key in('complete_floor','complete_roof','complete_fixed_layer_aperture'):
            for cell in r[key]:assert full(cell['pos'])==cell;retain(cell['pos'])
        for s in r['actual_native_selectors']:
            for key in('input','display'):assert full(s[key]['pos'])==s[key];retain(s[key]['pos'])
        for p in r['actual_registered_input_path']or[]:
            for y in range(p[1]-1,p[1]+2):retain((p[0],y,p[2]))
    for d in new['doors']:
        for q in d['aperture']:retain(q)
        for c in d['fixedInputContractsR45']:assert full(c['fixed_support']['pos'])==c['fixed_support'];retain(c['fixed_support']['pos'])
    for x in range(95,103):
        for z in range(-216,-210):
            for y in range(-369,-363):retain((x,y,z))
    deep_columns=[full((x,y,z))for x in range(10,15)for z in range(251,261)for y in range(-568,-562)]
    geometry=ActualGeometry(m);reported=geometry.standing([14.5,-566,256.5]);raw_reported=geometry.standing([14,-566,256]);assert reported=='STATIC_STANDING' and raw_reported=='NO_FULL_DATUM_BEARING'
    assert all(m.block((x,-567,z))!='minecraft:air'for x in range(10,15)for z in range(256,261))
    rear=[r for r in hardware if r['lift'].endswith('/9/253')];assert next(r for r in rear if r['independently_identified_current_parked_car'])['cabin_centre']==[12,-448,253]
    assert next(r for r in rear if r['cabin_centre'][1]==-566)['floor_counts']=={'minecraft:air':25}
    # Proof of writer semantics without making even a disposable region/world.
    from regional_voxels import Painter
    painter=Painter()
    for r in forward:painter.match((*r['pos'],*r['pos']),r['before'],r['after'],r['owner'])
    assert len(painter.ops)==25 and not painter.block_entities and not painter.entity_updates
    touched_chunks={(q[0]//16,q[2]//16)for q in merged};be_in_changed_chunks=[dict(pos=list(q),full_nbt=t.snbt())for q,t in tags.items()if(q[0]//16,q[2]//16)in touched_chunks]
    assert all(tuple(r['pos'])not in merged for r in be_in_changed_chunks)
    image={q:(r['after'],r['after_nbt'])for q,r in merged.items()}
    for r in inverse:image[tuple(r['pos'])]=r['after'],r['after_nbt']
    assert all(image[q]==(r['before'],r['before_nbt'])for q,r in merged.items())
    # Current generators are frozen; report real recurrence status rather than
    # claiming the runtime guard rewrote the original authoring generator.
    generator={}
    for name in('plan_hangar_upper_enclosure_r44.py','plan_factory_r20.py','plan_tv_hangar_envelope_r44.py','prepare_command_control_repairs_r45.py'):
        p=ROOT/'tools'/name;ast.parse(p.read_text('utf8'));generator[name]=dict(path=str(p),sha256=sha(p))
    assert 'native_public_bearing'in(ROOT/'tools/plan_hangar_upper_enclosure_r44.py').read_text('utf8')
    assert 'native_public_bearing'in(ROOT/'tools/plan_factory_r20.py').read_text('utf8')
    assert '89<=q[0]<=99 and -446<=q[1]<=-364 and -56<=q[2]<=-48'in(ROOT/'tools/plan_tv_hangar_envelope_r44.py').read_text('utf8')
    recurrence=dict(MTR6='Current source public-surface/native .9375 bearing guard already present in both upper enclosure and factory producers; no initial generator executed',
        compact1='Current whole-native-lift skin guard already includes the exact corner; legacy installed recipe conflicts with it; no whitelist/runtime air-hole relaxation',
        command18='Finite measured-frame repair producer and frozen Director strict marker/6-cell/actual-support guards present. Original initial placement generator is NOT rewritten; do not claim fresh rebuild convergence until root changes it.')
    after=inventory();assert before==after
    out.mkdir(parents=True);jsonl(out/'forward.jsonl.gz',forward);jsonl(out/'inverse.jsonl.gz',inverse);jsonl(out/'positive_edit_mask.jsonl.gz',[r['pos']for r in forward])
    (out/'command_marker.before.json').write_bytes(marker_before);(out/'command_marker.after.json').write_bytes(marker_after)
    jsonl(out/'all_retained_related_complete_states_NBT.jsonl.gz',[preserve[q]for q in sorted(preserve)])
    write(out/'full_changed_chunk_BE_inventory.json',be_in_changed_chunks);write(out/'all24_actual_hardware_complete_source.json',hardware)
    write(out/'deep_14_-566_256_complete_columns_and_empty_shaft.json',dict(reported_raw_feet=[14,-566,256],raw_source_nine_point_status=raw_reported,block_centre_point=[14.5,-566,256.5],block_centre_source_status=reported,all5_width_fixed_threshold_blocks_supported=True,current_car=[12,-448,253],empty_deep_shaft_not_repair_permission=True,columns=deep_columns,native_actual_pass=False))
    jsonl(out/'complete1736_source_before_after_SHA.jsonl.gz',[dict(relative=k,before_sha256=before[k],after_sha256=after[k])for k in sorted(before)])
    write(out/'generator_recurrence_status.json',dict(current_sources=generator,status=recurrence,source_modified_by_this_task=False))
    native=read(TRIPS);assert len(native['cases'])==90
    def priority(c):
        if c['group'].endswith('/9/253')and -566 in(c['from_cabin'][1],c['to_cabin'][1]):return 0
        if c['group'].endswith('/96/-52'):return 1
        return 2
    indexed=[dict(c,original_case_index=i,physical_bundle_required=True)for i,c in enumerate(native['cases'])];indexed.sort(key=lambda c:(priority(c),c['original_case_index']))
    actual_array=read(CONSUMER_INTERFACE);assert isinstance(actual_array,list) and actual_array==interfaces['interfaces']
    native.update(bound=False,cases=indexed,reason='Same90 cases prioritized for reported deep loss and real compact floor refusal; bind only after actual25 install/new checkpoint/lease',interfaces_file=str(CONSUMER_INTERFACE),interfaces_sha256=sha(CONSUMER_INTERFACE))
    write(out/'all90_physical_bundle_priority_cases.UNBOUND.json',native)
    landing_cases=[]
    for group in interfaces['interfaces']:
        for s in group['landings']:
            h=next(r for r in hardware if r['controller']['pos']==s['controller']);width=7 if h['radius']==7 else 3
            landing_cases.append(dict(id=f"{group['id']}/{s['controller'][1]}/complete_call_entry_exit",group=group['id'],controller=s['controller'],controller_full_nbt=h['controller']['full_nbt'],
                actual_outside_call=s['outside_call'],actual_call_state_NBT=h['outside_call'],actual_outside_call_path=s.get('outside_call_path'),real_handoff=s['handoff'],real_cabin=s['cabin_centre'],real_exit=s['exit'],
                actual_cabin_port_walk_width=width,layer_owned_aperture_mask_width=7 if width==7 else 5,complete_aperture=h['complete_fixed_layer_aperture'],selectors=h['actual_native_selectors'],gateway_fixed_controller_menu=h['gateway_actual_fixed_native_menu'],
                required=['actual grounded approach and native ray/outline/use','real outside call','wait original car and complete floor/roof/menu','all full-width lanes actual entry and exit with real car','actual menu select','departure closes full layer doors','occupied leaf refuses closure/motion','arrive grounded no drops or forced re-seat','return','same-JVM and cold reload','two clients'],native_pass=False))
    write(out/'all24_landing_actual_call_and_all_exit_inputs.UNBOUND.json',landing_cases)
    normals={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)};lane_cases=[]
    for group in interfaces['interfaces']:
        for s in group['landings']:
            h=next(r for r in hardware if r['controller']['pos']==s['controller']);dx,dz=normals[s['exit']];lx,lz=-dz,dx;plane=s['door_plane'];half=3 if h['radius']==7 else 2
            for across in range(-half,half+1):
                outside=[plane[0]+across*lx+2*dx+.5,float(h['approach_y']),plane[2]+across*lz+2*dz+.5]
                inside=[s['cabin_centre'][0]+across*lx+dx*(h['radius']-1)+.5,float(s['cabin_centre'][1]),s['cabin_centre'][2]+across*lz+dz*(h['radius']-1)+.5]
                route=[];distance=round(abs(outside[0]-inside[0])+abs(outside[2]-inside[2]));assert distance>=1
                for n in range(distance+1):
                    t=n/distance;p=[outside[0]+(inside[0]-outside[0])*t,inside[1],outside[2]+(inside[2]-outside[2])*t];x,y,z=map(math.floor,p)
                    route.append(dict(actual_candidate_feet=p,cold_source_proxy=geometry.standing(p),complete_floor_body_head_column=[full((x,Y,z))for Y in range(y-1,y+3)]))
                walk_lane=h['radius']==7 or abs(across)<=1
                lane_cases.append(dict(id=f'{group["id"]}/{s["controller"][1]}/width/{across}',controller=s['controller'],outside_call=s['outside_call'],outside_candidate_feet=outside,
                    outside_cold_source_proxy=geometry.standing(outside),inside_actual_car_candidate_feet=inside,complete_registered_plane=s['door_plane'],source_lane_columns=route,
                    actual_cabin_walk_lane=walk_lane,lane_purpose='ACTUAL_CABIN_PORT_WALK_LANE'if walk_lane else'WIDER_LAYER_APERTURE_EDGE_AND_FIXED_FRAME_CENSUS_NOT_STRAIGHT_CAR_ENTRY',
                    native_required='Original car must actually arrive and complete gate open; actual3-wide car (7 gateway) walk and grounded exit. Wider5 layer mask/floor footprint does not authorize removing car sidewall/call backing. Cold absent car/closed device is not an air-fill permit. Stairs require native height/step refinement, never teleport.',
                    implemented_by_frozen90_centre_path_consumer=False,native_pass=False))
    assert len(lane_cases)==124 and sum(r['actual_cabin_walk_lane']for r in lane_cases)==80
    write(out/'all124_full_width_landing_lane_requests.UNBOUND.json',lane_cases)
    write(out/'all80_actual_cabin_port_walk_lane_requests.UNBOUND.json',[r for r in lane_cases if r['actual_cabin_walk_lane']])
    write(out/'width_and_stair_proxy_semantics.json',dict(source_definitions=dict(S20PhysicalElevatorDirector=dict(path=str(ROOT/'src/main/java/com/projectseele/world/S20PhysicalElevatorDirector.java'),sha256=sha(ROOT/'src/main/java/com/projectseele/world/S20PhysicalElevatorDirector.java'),cabin_door_half_width=1,landing_door_half_width=2),RegionalGatewayDirector=dict(path=str(ROOT/'src/main/java/com/projectseele/world/RegionalGatewayDirector.java'),sha256=sha(ROOT/'src/main/java/com/projectseele/world/RegionalGatewayDirector.java'),actual_both_door_width=7)),
        aperture_census=124,actual_car_walk_lanes=80,wide_layer_edge_frame_census=44,
        observed12_outer_lane_body_obstructions_are_frame_call_backing_or_view_glass_not_removed=True,
        compact_upper_3_proxy_no_full_flat_datum='Actual saved smooth_quartz_stairs[facing=north,half=bottom,shape=straight,waterlogged=false] at Y-370; nonplanar native stair height/step must be measured, not filled',
        native_all_actual80_walk_or44_edge_safety_pass=False))
    requests=read(LIFE/'command_controls_v3/native_fixed_input_requests.json');assert len(requests)==37
    write(out/'all37_command_actual_fixed_input_requests.UNBOUND.json',requests)
    write(out/'priority_failures_and_MTR_native_inputs.UNBOUND.json',dict(bound=False,native_pass=False,
        deep=dict(reported_raw_feet=[14,-566,256],reported_raw_cold_full_bearing=raw_reported,block_centre=[14.5,-566,256.5],side_frame_collision_refusal_probe=[14.5,-566,255.5],safe_inner_edge_after_real_arrival=[13.5,-566,254.5],from_controller=[9,-566,253],outside_call=[9,-565,258],reader=[10,-566,258],car_wait=[12,-566,253],car_current_source=[12,-448,253],
            required=['no-card deep exit actual call, preserve entry authorization','wait actual car before crossing shaft','reported raw14 fringe occupancy during actual call/arrival must refuse unsafe clip or retain grounded actor; no force place/seat','observe full5 landing threshold and preserve sideframes; actual3-wide car entry/exit','full ascent/descent at valid centre and inner-edge positions no detach/drop/clip/forced seat','return and same-JVM/cold reload']),
        compact=dict(group='projectseele:geofront/lift/96/-52',before_foreign_corner=[95,-395,-54],before='projectseele:nerv_machine_panel',after='minecraft:polished_deepslate',
            before_native_refusal_log='city_atomic_integration_r45/qa_checkpoint_revision_v1/native_city_checkpoint_run_v6/native.log:684',required=['retain actual held-before negative; do not clear shaft','after exactrepair original unique car identified','both directions all3 stops actual call/menu/full-width entry/exit','guard negative foreign/corrupt cabin remains refusal, not new whitelist']),
        MTR=dict(source_cells=[r['pos']for r in forward if r['component']=='MTR6'],lanes=[98.5,99.5],actual_feet_y=-367.0625,port_z=-212.5,
            required=['actual grounded .9375 moving tread','both directions all2 lanes through restored3-high opening','header/frame/floor/BE retained','body and head no snag/fall','cold reload']),
        QA_navigation_install_or_model_activation=False))
    logs=[]
    for p in(ROOT/'artifacts/rebuild_r45/city_atomic_integration_r45/qa_checkpoint_revision_v1/native_city_checkpoint_run_v6/native.log',ROOT/'artifacts/rebuild_r45/city_atomic_integration_r45/qa_settled_endpoint_revision_v1/native_lazy_fold_retract_run_v1/native.log'):
        if p.exists():
            matches=[dict(line=i+1,text=l)for i,l in enumerate(p.read_text('utf8',errors='replace').splitlines())if's20-compact-cage-x93-z204-v4 held'in l]
            if matches:logs.append(dict(path=str(p),sha256=sha(p),actual_failure_lines=matches))
    write(out/'actual_compact_native_refusal_dependencies.json',logs)
    writer=ROOT/'tools/regional_voxels.py'
    write(out/'writer_NBT_safety_audit.json',dict(writer=str(writer),writer_sha256=sha(writer),changed_voxels_generically_retire_BE=True,
        this_bundle_all25_before_after_NBT_are_null=True,edited_positions_intersect_real_BE=False,complete_BE_inventory_retained=len(be_in_changed_chunks),
        staged_Painter_operations=25,staged_BE_additions_or_updates=0,no_writer_executed=True,
        required_root_wrapper='Strict before/after full cell+NBT, all target original BE records and all non-region/marker world files checked; rollback backups only with unchanged full post-write epoch'))
    bundle=dict(schema=SCHEMA,source_world=str(WORLD),source_baseline=dict(path=str(BASELINE),sha256=sha(BASELINE)),source_world_id=base['world_id'],source_seed=base['world_seed'],components=parts,
        forward=dict(path=str(out/'forward.jsonl.gz'),sha256=sha(out/'forward.jsonl.gz')),inverse=dict(path=str(out/'inverse.jsonl.gz'),sha256=sha(out/'inverse.jsonl.gz')),
        mask=dict(path=str(out/'positive_edit_mask.jsonl.gz'),sha256=sha(out/'positive_edit_mask.jsonl.gz')),cells=25,
        marker=dict(relative=relative,before_path=str(out/'command_marker.before.json'),before_sha256=hashlib.sha256(marker_before).hexdigest(),after_path=str(out/'command_marker.after.json'),after_sha256=hashlib.sha256(marker_after).hexdigest()),
        installed=False,world_written=False,native_pass=False,root_only_writer=True,navigation_or_model_install_included=False,
        source_writer=dict(path=str(writer),sha256=sha(writer)),required_runtime_target='Explicit stopped QA copy with new full target cold inventory; reject immutable source and hot/consumed admission',
        report=dict(source1736_unchanged=True,coordinates_disjoint=True,full_NBT_preimages=True,heap_inverse_exact=True,retained_related_cells=len(preserve),all24_landings=24,trip_pairs=90,command_inputs=37,
            native_consumer_interface_is_expected_JSON_array=True,departure_board_not_in_mask=True,car_whitelist_not_relaxed=True,initial_command_generation_not_patched=True))
    write(out/'bundle.json',bundle);print(json.dumps(bundle['report']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args())
