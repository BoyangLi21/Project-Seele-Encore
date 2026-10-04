"""Separate legacy nominal nodes, current fixed access and conditional equipment."""
from __future__ import annotations
import argparse,json,math,collections,sys
from pathlib import Path
from collections import deque
sys.dont_write_bytecode=True
import nbtlib,numpy as np
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha,jsonl
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import iter_block_entities,AIR
from prepare_school_hakone_native_r45 import ActualGeometry
from verify_main_r20 import entities

META=WORLD/'r44_tv_personnel_platforms.json'
MODEL=ROOT/'src/main/resources/assets/projectseele/mesh/tv_shoulder_shells_r44.json'
OLDNAV=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1/frozen_audit_v7/all527_actual_classification.json'
def main(args):
    out=args.out.resolve();assert not out.exists() and not out.is_relative_to(WORLD)
    expected={r['relative']:r['sha256']for r in read(BASELINE)['files']};assert len(expected)==1736
    def inventory():
        assert {p.relative_to(WORLD).as_posix()for p in WORLD.rglob('*')if p.is_file()}==set(expected)
        value={k:sha(WORLD/k)for k in sorted(expected)};assert value==expected;return value
    before=inventory();metadata=read(META);mesh_before=sha(MODEL);mesh=read(MODEL)
    null=[r['pos']for r in read(OLDNAV)if r['pos'][1]==-394];assert len(null)==417
    floor=metadata['owner_provenance']['floor_cells'];ops=metadata['owner_provenance']['installed_owned_operations']
    assert len(floor)==202 and len(ops)==427 and len(metadata['entry_gate_pairs'])==6
    owned={tuple(r['position']):r for r in ops};floorxz={tuple((r['position'][0],r['position'][2]))for r in floor}
    m=MeasuredWorld(WORLD);m.box((-46,-405,-298),(114,-385,-42));m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-46,-405,-298),(114,-385,-42),selected_chunks=set(m.selected)))
    def full(q):
        q=tuple(q);tag=tags.get(q);return dict(pos=list(q),state=m.block(q),full_nbt=None if tag is None else tag.snbt())
    mismatches=[]
    for q,op in owned.items():
        actual=m.block(q);wanted=op['after'];equivalent=actual==wanted
        if wanted.startswith('projectseele:city_personnel_door['):equivalent=actual is not None and actual.replace('open=true','open=false').replace('powered=true','powered=false')==wanted.replace('open=true','open=false').replace('powered=true','powered=false')
        if not equivalent or q in tags:mismatches.append(dict(pos=list(q),actual=full(q),expected=op))
    assert not mismatches,'Current complete fixed staff installation differs from427-owner recipe'
    fleet=nbtlib.load(WORLD/'data/projectseele_eva_fleet.dat')['data']['Fleet'];saved_entities=entities(WORLD);saved=[]
    for entry in fleet:
        unit=saved_entities[tuple(map(int,entry['Canonical']))];plug=saved_entities.get(tuple(map(int,entry['EntryPlug'])))
        assert plug is not None
        saved.append(dict(variant=int(entry['Variant']),full_fleet_nbt=entry.snbt(),phase=str(entry['Phase']),ticks=int(entry['Ticks']),
            canonical_uuid=list(map(int,entry['Canonical'])),canonical_full_nbt=unit.snbt(),canonical_pos=list(map(float,unit['Pos'])),
            entry_plug_uuid=list(map(int,entry['EntryPlug'])),entry_plug_full_nbt=plug.snbt(),entry_plug_pos=list(map(float,plug['Pos'])),
            actual_no_save_gantry_presence='UNVERIFIED_COLD_SAVE_CANNOT_CERTIFY_RUNTIME_RECONCILIATION'))
    # Inspect the exact current declared fixed apron slabs. Their geometry
    # depends on a real runtime gantry/provider flag; projection is explicitly
    # not treated as a saving block floor or a completed native access proof.
    platform=[]
    for variant,cx in enumerate((-11.5,30.5,72.5)):
        for side in(-1,1):
            part='platform_2_r'if variant==2 and side==1 else'platform_l'if side<0 else'platform_r'
            boxes=np.asarray(mesh['collision_parts'][part],float)+[cx,-443,-239.5]
            slabs=boxes[(boxes[:,1,0]-boxes[:,0,0]>3)&(boxes[:,1,2]-boxes[:,0,2]<=.126)]
            assert len(slabs)>0
            platform.append(dict(variant=variant,side=side,part=part,slabs=slabs,world_declared_bounds=[slabs[:,0,:].min(0).tolist(),slabs[:,1,:].max(0).tolist()]))
    classified=[]
    for q in null:
        x,y,z=q;body=full(q);exact=owned.get(tuple(q));related=[]
        for p in platform:
            b=p['slabs'];overlap=(b[:,0,0]<=x+.5)&(b[:,1,0]>=x+.5)&(b[:,0,2]<=z+.5)&(b[:,1,2]>=z+.5)
            if np.any(overlap):related.append(dict(variant=p['variant'],side=p['side'],part=p['part'],declared_actual_slab_tops=sorted(set(float(n)for n in b[overlap,1,1])),
                motion='fixed',private_equipment=True,runtime_flag_and_actual_gantry_required=True,native_present_and_walkable_pass=False))
        if exact and body['state'].startswith('projectseele:tv_personnel_guard_r44['):kind='CURRENT_OWNED_FIXED_BOUNDARY_GUARD_NOT_STANDING_NODE'
        elif related:kind='OLD_NOMINAL_DATUM_BELOW_PRIVATE_FIXED_INSPECTION_APRON; ACTUAL_RUNTIME_UNVERIFIED'
        elif -263<=z<=-261:kind='OLD_FULL_WIDTH_FRONT_SHELF_NOW_INNER_CLEAR_SPACE; CURRENT_ACCESS_IS_THE_SEPARATE_REGISTERED_BRIDGE'
        else:kind='OLD_INTERNAL_SERVICE_OR_PLUG_WELL_FRAME_NOW_CLEAR; NO_CURRENT_PUBLIC_FLOOR_OR_ENTRY_HERE'
        classified.append(dict(legacy_pos=q,current_classification=kind,complete_current_vertical_column=[full((x,Y,z))for Y in range(-401,-385)],
            actual_fixed_floor202_XZ_match=(x,z)in floorxz,current427_owner=exact,declared_private_apron_surfaces=related,
            saved_bay_phase=saved[min(range(3),key=lambda v:abs(x-(-12+42*v)))]['phase'],
            public_floor_permission=False,device_normal_or_native_pass=False,construction_permitted=False))
    g=ActualGeometry(m)
    def public_point(x,z):
        q=(x,-395,z);boxes=g.boxes(q)
        if boxes is not None:
            for top in sorted({b[4]for b in boxes},reverse=True):
                if .01<=top<=1 and all(any(b[0]<=a<=b[3]and b[2]<=c<=b[5]and abs(b[4]-top)<.001 for b in boxes)for a in(.25,.5,.75)for c in(.25,.5,.75)):return[x+.5,-395+top,z+.5]
        return[x+.5,-394,z+.5]
    points={}
    for x in range(-43,111):
        for z in range(-293,-44):
            p=public_point(x,z)
            if g.standing(p)=='STATIC_STANDING':points[x,z]=p
    def route(a,b):
        if a not in points or b not in points:return None
        todo=deque([a]);parent={a:None}
        while todo:
            q=todo.popleft()
            if q==b:
                path=[]
                while q is not None:path.append(points[q]);q=parent[q]
                return path[::-1]
            for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                n=q[0]+dx,q[1]+dz
                if n not in points or n in parent:continue
                p,t=points[q],points[n];h=max(p[1],t[1])
                if abs(p[1]-t[1])<=.0625 and g.clear([p[0],h,p[2]],target=[t[0],h,t[2]])=='CLEAR':parent[n]=q;todo.append(n)
        return None
    gates=[]
    for gate in metadata['entry_gate_pairs']:
        approach=gate['public_approach'];positions=gate['lower_positions'];paths={}
        for name,start in [('real_west_lift',(-29,-285)),('real_compact_lift',(93,-45))]:
            path=route(start,(math.floor(approach[0]),math.floor(approach[2])));paths[name]=path
        assert all(paths.values()),('Current actual public entry is disconnected',gate)
        lower_upper=[full((q[0],Y,q[2]))for q in positions for Y in(q[1],q[1]+1)]
        gates.append(dict(contract=gate,complete_actual_door_pairs=lower_upper,actual_full_width_supported_public_approach=g.standing(approach),
            complete_existing_same_floor_public_paths=paths,native_door_use_and_all202_grating_or_private_apron_actual_return_pass=False,
            compact_lift_known_foreign_floor_corner_installed_repair=False))
    saved_people=[]
    for uid,e in saved_entities.items():
        if 'Pos'not in e or not str(e.get('id','')).startswith('projectseele:'):continue
        p=list(map(float,e['Pos']))
        if -33<=p[0]<=93 and -399<=p[1]<=-387 and -267<=p[2]<=-244:
            saved_people.append(dict(uuid=list(uid),id=str(e['id']),actual_saved_position=p,actual_fixed_world_standing=g.standing(p),
                complete_saved_nbt=e.snbt(),legacy417_same_nominal_node=[math.floor(p[0]),round(p[1]),math.floor(p[2])]in null,
                native_current_AI_or_device_access_pass=False,relocation_proposed=False))
    decks=[]
    for row in floor:
        q=tuple(row['position']);boxes=g.boxes(q);assert boxes is not None and boxes
        # Report actual collider strips over the whole .6m body footprint.
        # Fine grating's deliberate ray-sized holes must not be converted to
        # air or certified through a solid-nine-ray rule.
        overlaps=[b for b in boxes if b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2]
        height=q[1]+max(b[4]for b in overlaps);probe=[q[0]+.5,height,q[2]+.5]
        decks.append(dict(owner=row,actual=full(q),native_boxes=boxes,full_0p6m_footprint_intersects_native_grating=bool(overlaps),
            actual_highest_intersecting_slab_y=height,actual_fixed_world_body_probe=probe,fixed_world_full_body_clearance=g.clear(probe),
            native_actual_full_width_ramp_movement_required=True,native_pass=False))
    # A scoped operator extension keeps current fractional deck datums and
    # gate ownership. The old integer public graph cannot represent this
    # by filling/reclassifying its417 legacy inner coordinates.
    import gzip
    with gzip.open(WORLD/'nerv_routes_r24.json.gz','rt',encoding='utf8')as f:old_graph=json.load(f)
    old_nodes={tuple(r[:3])for r in old_graph['nodes']};exact_height_matches=0
    for row in decks:
        x,_,z=row['actual']['pos'];height=row['actual_highest_intersecting_slab_y']
        row['old_integer_graph_has_this_actual_fixed_datum']=(x,height,z)in old_nodes
        exact_height_matches+=int(row['old_integer_graph_has_this_actual_fixed_datum'])
    operator_cases=[]
    for gate_row in gates:
        gate=gate_row['contract'];variant,side=gate['variant'],gate['side'];ident=f'tv_operator/{variant}/{side}/entry'
        current=next(r for r in metadata['crew_exit_routes']if r['id']==ident)
        route_cells=[d for d in decks if d['owner']['variant']==variant and d['owner']['side']==side]
        cell_map={(d['actual']['pos'][0],d['actual']['pos'][2]):d for d in route_cells};links=[]
        for coord,d in cell_map.items():
            a=d['actual_fixed_world_body_probe']
            for dx,dz in((1,0),(0,1)):
                n=coord[0]+dx,coord[1]+dz
                if n not in cell_map:continue
                b=cell_map[n]['actual_fixed_world_body_probe'];h=max(a[1],b[1])
                sweep=g.clear([a[0],h,a[2]],target=[b[0],h,b[2]])
                links.append(dict(a=d['actual']['pos'],b=cell_map[n]['actual']['pos'],a_actual_feet=a,b_actual_feet=b,
                    actual_end_datum_difference=abs(a[1]-b[1]),complete_fixed_world_sweep_at_higher_real_datum=sweep,
                    ramp_quarter_steps_and_0p6m_footprint_native_actual_movement_required=True,native_pass=False))
        operator_cases.append(dict(id=f'r45/boarding/{variant}/{side}/fixed_operator_complete_return',
            real_same_floor_lift_public_paths=gate_row['complete_existing_same_floor_public_paths'],actual_pair_use=gate['lower_positions'],
            current202_exact_native_floor_subset=route_cells,existing_expected_route_for_native_refinement=current,
            all_current_adjacent_fixed_floor_edge_proposals=links,
            expected_y_is_not_teleport_or_native_move_proof=True,native_execution_and_live_stationary_owner_required=True,
            native_actual_both_width_lanes_clearance_and_return_pass=False))
    assert sha(MODEL)==mesh_before,'Root model changed during readonly projection; use a fresh explicit epoch'
    after=inventory();assert before==after
    out.mkdir(parents=True)
    write(out/'all417_current_semantics_and_full_columns.json',classified);write(out/'all427_current_owned_installation_readback.json',[dict(expected=r,actual=full(r['position']))for r in ops])
    write(out/'all202_actual_fixed_native_grating_and_height.json',decks);write(out/'all6_gate_pairs_and_real_same_floor_lift_paths.json',gates);write(out/'saved3_actual_fleet_and_canonical_plug_full_NBT.json',saved)
    write(out/'saved_current_staff_and_training_pilot_full_NBT_and_bearing.json',saved_people)
    write(out/'scoped_operator_graph_extension_UNBOUND.json',dict(schema='projectseele.r45-scoped-current-operator-layout.v1',bound=False,world=str(WORLD),
        ordinary_public_floor=False,permission='Real registered personnel gate + actual stationary owned-machine interlock; no inherited public-air permission',
        cases=operator_cases,source_metadata_sha256=sha(META),native_collision_sha256=sha(WORLD/'native_collision_shapes.json'),
        producer_issue='Legacy nav enumerates frozen143080 integer nodes and its generic floor_key, so current fractional202 operator floors need explicit permission/height-aware scope; do not rewrite private machinery or417 void coordinates as general routes',
        installed=False,native_pass=False))
    write(out/'operator_scope_reversible_proposal.json',dict(target=str(WORLD/'operator_lift_routes_r45.json'),expected_absent=not(WORLD/'operator_lift_routes_r45.json').exists(),
        candidate_file=str((out/'scoped_operator_graph_extension_UNBOUND.json').resolve()),candidate_sha256=sha(out/'scoped_operator_graph_extension_UNBOUND.json'),
        installed=False,derived_only=True,old_global143080_graph_not_replaced=True,positive_static_world_mask=[],
        requires_actual_root_native_current_phase_provider_flags_gate_and_height_refinement=True,
        rollback='If newly installed by root, remove only matching candidate bytes; never delete old graph/geometry/progress or remove permission gate'))
    write(out/'private_fixed_apron_declared_geometry_runtime_preconditions.json',[{k:v for k,v in p.items()if k!='slabs'}for p in platform])
    report=dict(source_world=str(WORLD),complete1736_inventory_SHA_before_after_equal=True,legacy_null_nodes=417,
        classifications=dict(collections.Counter(r['current_classification']for r in classified)),
        fixed_current_floor202_XZ_overlap_with417=sum(r['actual_fixed_floor202_XZ_match']for r in classified),
        all427_installed_complete_states_NBT_match=True,all202_fixed_native_grating_colliders_read=True,
        actual_saved3_phases=[r['phase']for r in saved],all6_registered_gate_current_public_paths_to_both_real_same_floor_lifts=True,
        actual_fixed_public_body_nodes=len(points),old_integer_graph_not_adequate_for_202_fractional_grating_or_private_equipment=True,
        exact_current202_fixed_datum_present_in_old_integer_graph=exact_height_matches,actual_saved_people_in_current_band=len(saved_people),
        all202_fixed_world_body_clearance_status=dict(collections.Counter(r['fixed_world_full_body_clearance']for r in decks)),
        saved_people_on_legacy417_nominal_nodes=sum(r['legacy417_same_nominal_node']for r in saved_people),
        scoped_private_operator_extension_bound=False,scoped_private_operator_extension_installed=False,
        source_model_readonly_sha256=mesh_before,source_metadata_sha256=sha(META),
        world_written=False,Java_Gradle_MC_started=False,policy_Java_or_model_or_motion_changed=False,
        installed1cell=False,installed6cell=False,installed18buttons=False,native_private_apron_grating_gates_or_devices_normal_pass=False,
        construction_proposed=False,
        remaining='Actual flag/current gantry and saved-motion reconciliation, native full two-lane grating ramps, all gates/occupied states and private aprons require root; derived scoped operator graph must retain permission and actual height instead of filling417 legacy coordinates')
    write(out/'report.json',report);print(json.dumps(report),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args())
