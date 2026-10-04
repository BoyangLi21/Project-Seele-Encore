"""Read frozen7/24 lift hardware and the exact legacy skin-owned floor error."""
from __future__ import annotations
import argparse,collections,gzip,json,sys,ast
from pathlib import Path
sys.dont_write_bytecode=True
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha,jsonl,gzread
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR
from prepare_school_hakone_native_r45 import ActualGeometry

INTERFACES=ROOT/'artifacts/rebuild_r45/candidate_transport_acceptance_sol_v1/candidate_interfaces_bound.json'
LOG=ROOT/'artifacts/rebuild_r45/city_atomic_integration_r45/qa_checkpoint_revision_v1/native_city_checkpoint_run_v6/native.log'
SKIN=ROOT/'artifacts/rebuild_r44/facility_transit_r44/tv_hangar_envelope_v3/whole_three_line_tv_skin'
def main(args):
    out=args.out.resolve();assert not out.exists() and not out.is_relative_to(WORLD)
    expected={r['relative']:r['sha256']for r in read(BASELINE)['files']};assert len(expected)==1736
    def inventory():
        names={p.relative_to(WORLD).as_posix()for p in WORLD.rglob('*')if p.is_file()};assert names==set(expected)
        actual={k:sha(WORLD/k)for k in sorted(names)};assert actual==expected;return actual
    before=inventory();interfaces=read(INTERFACES)['interfaces'];assert len(interfaces)==7 and sum(len(l['landings'])for l in interfaces)==24
    m=MeasuredWorld(WORLD)
    for lift in interfaces:
        for stop in lift['landings']:m.around(stop['cabin_centre'],14)
    m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-390,-590,-300),(160,100,780),selected_chunks=set(m.selected)))
    def full(q):
        q=tuple(q);tag=tags.get(q);return dict(pos=list(q),state=m.block(q),full_nbt=None if tag is None else tag.snbt())
    geometry=ActualGeometry(m);normal={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}
    allgroups=[];allstops=[];foreign=[]
    for lift in interfaces:
        key=tuple(lift['landings'][0]['controller'][i]for i in(0,2));gateway=key==(-368,750);surface=key==(130,269)
        radius=7 if gateway else 3 if surface else 2;roof_height=7 if gateway else 4
        floor_types={'minecraft:smooth_stone'}if gateway else{'minecraft:polished_deepslate','projectseele:nerv_structural_panel'}
        roof_type='minecraft:polished_deepslate'if gateway else'minecraft:smooth_quartz'
        cars=[];stops=[]
        for stop in lift['landings']:
            x,y,z=stop['cabin_centre'];floor=[full((x+dx,y-1,z+dz))for dx in range(-radius,radius+1)for dz in range(-radius,radius+1)]
            roof=[full((x+dx,y+roof_height,z+dz))for dx in range(-radius,radius+1)for dz in range(-radius,radius+1)]
            floor_count=collections.Counter(r['state']for r in floor);roof_complete=all(r['state']==roof_type for r in roof)
            selectors=[]
            for q,tag in tags.items():
                if not(x-radius<=q[0]<=x+radius and y<=q[1]<=y+roof_height and z-radius<=q[2]<=z+radius):continue
                if m.block(q)!='movingelevators:button_block' or m.block((q[0],q[1]+1,q[2]))!='movingelevators:display_block':continue
                data=tag.get('data',{});linked=int(data.get('controllerX',999999))==key[0]and int(data.get('controllerZ',999999))==key[1]and int(data.get('controllerY',999999))in{s['controller'][1]for s in lift['landings']}
                selectors.append(dict(input=full(q),display=full((q[0],q[1]+1,q[2])),linked_to_exact_current_group=linked))
            # The large gateway exposes the native fixed controller menu
            # directly, with showButtons=1. It never had a saving in-car
            # button/display pair; requiring a fabricated selector loses it.
            gateway_controller=tags.get(tuple(stop['controller']))
            gateway_menu=bool(gateway and gateway_controller is not None and str(gateway_controller.get('id',''))=='movingelevators:elevator_tile'
                and int(gateway_controller.get('data',{}).get('showButtons',0))==1)
            identified=roof_complete and (any(s['linked_to_exact_current_group']for s in selectors)or gateway_menu and all(r['state']in floor_types for r in floor))
            bad=[r for r in floor if r['state']not in floor_types]
            dx,dz=normal[stop['exit']];lx,lz=-dz,dx;plane=stop['door_plane'];half=3 if gateway else 2;height=5 if gateway else 3
            aperture=[full((plane[0]+across*lx,plane[1]+dy,plane[2]+across*lz))for across in range(-half,half+1)for dy in range(height)]
            aperture_precondition=all(r['full_nbt']is None and r['state']in AIR|{'minecraft:barrier','minecraft:gray_stained_glass','minecraft:light_gray_stained_glass','projectseele:clear_glass'}for r in aperture)
            handoff=stop['handoff'];handoff_point=[handoff[0]+.5,handoff[1],handoff[2]+.5]
            route_checks=[]
            path=stop.get('outside_call_path')or[]
            for p in path:route_checks.append(dict(pos=p,status=geometry.standing([p[0]+.5,p[1],p[2]+.5]),full=[full((p[0],Y,p[2]))for Y in(p[1]-1,p[1],p[1]+1)]))
            row=dict(lift=lift['id'],controller=full(stop['controller']),expected_original_controller_nbt=stop['controller_nbt'],
                cabin_centre=[x,y,z],exit=stop['exit'],approach_y=stop.get('approach_y',y),radius=radius,complete_floor=floor,complete_roof=roof,
                floor_counts=dict(floor_count),roof_complete=roof_complete,actual_native_selectors=selectors,gateway_actual_fixed_native_menu=gateway_menu,independently_identified_current_parked_car=identified,
                non_cabin_floor_cells=bad if identified else[],outside_call=full(stop['outside_call']),declared_handoff=full(stop['handoff']),
                actual_registered_input_path=stop.get('outside_call_path'),native_function_pass=False,body_or_shaft_rebuild_proposed=False)
            row.update(complete_fixed_layer_aperture=aperture,complete_layer_aperture_source_precondition=aperture_precondition,
                handoff_actual_nine_point_status=geometry.standing(handoff_point),complete_actual_input_path=route_checks,
                all_width_lane_native_door_use_entry_and_exit_pass=False)
            stops.append(row);allstops.append(row)
            if identified:
                cars.append(row);foreign.extend(dict(lift=lift['id'],**r)for r in bad)
        assert len(cars)==1,('Current original car is ambiguous',lift['id'],len(cars))
        allgroups.append(dict(id=lift['id'],landings=len(stops),identified_car_centre=cars[0]['cabin_centre'],car_bad_floor_cells=len(cars[0]['non_cabin_floor_cells']),
            physical_floor_footprints_and_roofs_only=True,all_actual_controller_and_input_NBT_retained=True,native_pass=False))
    assert len(foreign)==1 and foreign[0]['pos']==[95,-395,-54]and foreign[0]['state']=='projectseele:nerv_machine_panel'
    q=tuple(foreign[0]['pos']);ops=gzread(SKIN/'ops.json.gz');owner=[r for r in ops if all(r['box'][i]<=q[i]<=r['box'][i+3]for i in range(3))]
    assert len(owner)==1 and owner[0]['extra']==['minecraft:polished_deepslate']and owner[0]['state']=='projectseele:nerv_machine_panel'
    receipt=read(SKIN/'applied_20260930_175054_732221/receipt.json');assert receipt['verified'] is True
    assert full(q)['full_nbt']is None
    forward=[dict(pos=list(q),before=foreign[0]['state'],after=owner[0]['extra'][0],before_nbt=None,after_nbt=None,
        owner='r45/restore_exact_original_identified_compact_car_floor_corner',original_wrong_owner=owner[0]['owner'],
        reason='Undo exactly one verified old transfer-skin repaint of the identified original floor; no material whitelist relaxation or shaft/body rebuild')]
    inverse=[dict(forward[0],before=forward[0]['after'],after=forward[0]['before'])]
    lines=LOG.read_text('utf8',errors='replace').splitlines();failed=[dict(line=i+1,text=line)for i,line in enumerate(lines)if'Native lift s20-compact-cage-x93-z204-v4 held for an ambiguous/unsafe damaged cabin'in line]
    assert failed and failed[0]['line']==684
    after=inventory();assert before==after
    out.mkdir(parents=True)
    write(out/'all7_car_identity_summary.json',allgroups);write(out/'all24_full_cabins_inputs_controllers_NBT.json',allstops)
    write(out/'exact1_original_wrong_skin_owner.json',dict(operation=owner[0],applied_receipt=str((SKIN/'applied_20260930_175054_732221/receipt.json').resolve()),log=str(LOG),log_sha256=sha(LOG),failure_lines=failed))
    jsonl(out/'forward.jsonl.gz',forward);jsonl(out/'inverse.jsonl.gz',inverse);jsonl(out/'positive_edit_mask.jsonl.gz',[list(q)])
    report=dict(source_world=str(WORLD),complete1736_before_after_SHA_equal=True,groups=7,landings=24,independently_identified_original_cars=7,
        damaged_cars=1,actual_foreign_floor_cells=1,repair_cells=1,candidate_restores_original_complete_floor_to_persisted_material=True,
        precise_perimeter_corner_not_generic_one_interior_hole=True,original_skin_source_guard_now_preserves_whole_native_lift=True,
        actual_old_applied_recipe_conflicts_with_current_whole_lift_guard=True,source_body_selector_roof_hardware_and_shaft_not_changed=True,
        world_written=False,Java_Gradle_MC_started=False,native90_or_any_lift_lifecycle_pass=False,
        forward_sha256=sha(out/'forward.jsonl.gz'),inverse_sha256=sha(out/'inverse.jsonl.gz'),
        remaining='Root stopped explicit QA target old complete state/NBT check, exact single original repair, new checkpoint/lease, live original car/door/input/90pairs and all reload/occupied cases')
    write(out/'report.json',report);print(json.dumps(report),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args())
