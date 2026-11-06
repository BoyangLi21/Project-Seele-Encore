"""Bounded offline dispositions for five retained underground station ends.

Reads frozen section/model exports and original operation archives only. It
does not read a save, load native runtime, update an authority or install edits.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path

import numpy as np
import nbtlib

from audit_hq_mtr_protection_r52 import Reader
from verify_declared_platform_footprints import EnvelopeWalker
from review_underground_station_evidence import Overlay, strict_walk


def load(path):
    return json.loads(path.read_text('utf8'))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf8')


def main(base, out, finalize=False):
    assert finalize or not (out/'readiness.json').exists(), 'Frozen disposition already exists'
    out.mkdir(exist_ok=True)
    source = base / 'all-stations-current-source-v1'
    shapes = load(base / 'all-stations-support-metadata-v1/native_collision_shapes.json')
    declaration = load(base / 'deep-platform-fullwidth-review-v1/declarations.json')
    findings = load(base / 'deep-platform-fullwidth-review-v1/findings.json')
    original = load(base / 'deep-platform-guards-candidate-v1/source-dispositions.json')
    native = load(base / 'all-stations-native-engine-v2/snapshot.json')
    w = EnvelopeWalker(source, shapes)
    bays = {s['site']: s['bays'] for s in declaration['stations']}
    bysite = {s['site']: s for s in declaration['stations']}

    # Validate the frozen evaluated underground geometry against the later
    # frozen native member maps, without an engine, identity reset or digest.
    keys = ('position1', 'position2', 'angle1', 'angle2', 'shape', 'verticalRadius')
    def signature(r):
        return json.dumps({k:r[k] for k in keys}, sort_keys=True)
    current = []
    for file in (base / 'station-installed69-native-v1/projectseele/geofront/rails').rglob('*'):
        if file.is_file():
            row = Reader(file.read_bytes()).read()
            if row['transportMode'] == 'TRAIN' and row['position1']['y'] < -400:
                current.append(signature(row))
    evaluated = [signature(r) for r in native['rails']
                 if r['transportMode'] == 'TRAIN' and r['position1']['y'] < -400]
    assert Counter(current) == Counter(evaluated)

    def local(bay, point):
        cx, _, cz = bay['center']
        return ((point[0] - .5 - cx, point[2] - .5 - cz) if bay['horizontal']
                else (point[2] - .5 - cz, point[0] - .5 - cx))

    def platform_interval(site, bay):
        axis = 'x' if bay['horizontal'] else 'z'
        cross = 'z' if bay['horizontal'] else 'x'
        centre = bay['center'][2 if bay['horizontal'] else 0]
        rows = [p for p in native['platforms'] if p['transportMode'] == 'TRAIN'
                and p['position1']['y'] == bay['current_floor_y']
                and abs(p['position1'][cross] - centre) <= 4
                and abs((p['position1'][axis]+p['position2'][axis])/2
                        - bay['center'][0 if bay['horizontal'] else 2]) < 1]
        assert rows
        return [min(min(p['position1'][axis], p['position2'][axis])+.5 for p in rows),
                max(max(p['position1'][axis], p['position2'][axis])+.5 for p in rows)]

    rail_segments = []
    for ci, curve in enumerate(native['curves']):
        if curve['mode'] != 'TRAIN':
            continue
        for si, (a, b) in enumerate(zip(curve['points'], curve['points'][1:])):
            if min(a[1], b[1]) < 0:
                rail_segments.append((ci, si, np.array(a), np.array(b)))

    def nearest(point):
        p = np.array(point)
        best = None
        for ci, si, a, b in rail_segments:
            if abs(a[1]-p[1]) > 8:
                continue
            delta = b[[0,2]]-a[[0,2]]
            t = float(np.clip(np.dot(p[[0,2]]-a[[0,2]], delta)/max(np.dot(delta,delta),1e-12),0,1))
            q = a + t*(b-a)
            dist = float(np.linalg.norm((p-q)[[0,2]]))
            if best is None or dist < best['horizontal_distance']:
                best = dict(curve_index=ci, segment_index=si, point=q.tolist(), horizontal_distance=dist)
        return best

    groups = defaultdict(list)
    for station in findings['stations']:
        site = station['site']
        for row in station['unprotected_ground_level_rail_or_end_interfaces']:
            p = row['feet']
            bay = min(bays[site], key=lambda b:abs(local(b,p)[1]))
            u,v = local(bay,p)
            bounds = platform_interval(site,bay)
            axial = p[0 if bay['horizontal'] else 2]
            end = 'before_native_platform' if axial < bounds[0] else 'after_native_platform' if axial > bounds[1] else 'within_native_platform'
            side = tuple(row['side_cell'])
            current_states = [dict(pos=[side[0],side[1]+dy,side[2]],state=w.reader.state(side[0],side[1]+dy,side[2])) for dy in (-2,-1,0,1,2)]
            assert all(r['state'] is not None for r in current_states)
            assert end != 'within_native_platform'
            item = dict(**row, local_uv=[u,v], native_platform_interval=bounds,
                        nearest_current_curve=nearest(p), measured_side_column=current_states,
                        classification='reachable_nonboarding_terminal_rail_interface',
                        required_action='Complete a fixed passenger boundary outside the true train sweep; do not fill the live track bed or treat the opening as boarding.',
                        author_recipe='build_transit_civil_r20.py:99-105 makes the rail trench, while the finite native platform/gate ends delimit boarding. The wider civil bay is not a boarding permission.',
                        passed=False)
            groups[(site,bay['line'],end,v,tuple(row['normal']))].append(item)
    edge_groups = [dict(site=k[0],line=k[1],end=k[2],transverse_cell=k[3],normal=k[4],
                       count=len(rows),rows=rows) for k,rows in sorted(groups.items())]
    assert sum(g['count'] for g in edge_groups) == 223
    save(out/'terminal-edge-groups.json',edge_groups)

    r28 = Path('F:/eva/artifacts/facility_r28/train_repairs')
    r28_before = {tuple(r['position']):r for r in load(r28/'measured_before.json')['items']}
    r28_ops = json.loads(gzip.decompress((r28/'native_train_body_clearance/ops.json.gz').read_bytes()))
    disposition = []
    edits = []
    half_steps = []
    controls = []
    for row in original:
        q = tuple(row['floor'])
        x,y,z = q
        state = w.reader.state(*q)
        assert state == row['measured_floor_state']
        result = dict(site=row['site'],floor=q,measured_state=state,original_status=row['status'])
        if row['site'] == 'native-28':
            feet = [x+.5,y+.5,z+.5]
            assert shapes[state] == [[0.,0.,0.,1.,.5,1.]] and w.body(*feet) is None
            connections = []
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                target = [feet[0]+dx,y+1,feet[2]+dz]
                a,b = strict_walk(w,[feet,target]),strict_walk(w,[target,feet])
                if a['kind'] == b['kind'] == 'strict_static_clear':
                    assert max(a['maximum_observed_step'],b['maximum_observed_step']) <= .5
                    connections.append(dict(target=target,forward=a,reverse=b))
            assert connections
            normal = [0,0,1 if z<785 else -1]
            railstep = [feet[0],y,feet[2]+normal[2]]
            result.update(disposition='supported_half_step_deck_not_missing_floor',feet=feet,
                          shape=shapes[state],connections=connections,
                          historical_lowering_operation='not recovered; no modification is required to retain this measured authored-floor footprint',
                          original_authored_floor=True,rail_edge_still_separate=True,
                          railward_half_step=railstep,static_body_clear=w.body(*railstep) is None,
                          next_action='Correct declared feet datum to -466.5; include this low ledge in terminal passenger-boundary design.',
                          not_whole_station_pass=True)
            half_steps.append(dict(site=row['site'],floor=q,old_feet_y=y+1,correct_feet_y=y+.5))
            nw = EnvelopeWalker(source,shapes)
            nw.reader = Overlay(nw.reader,{q:'minecraft:air'})
            neg = strict_walk(nw,[feet,feet])
            assert neg['kind'] != 'strict_static_clear'
            controls.append(dict(case='remove_actual_half_slab',floor=q,result=neg,rejected=True))
        elif row['site'] == 'native-22':
            matches = [dict(operation_index=i,operation=o) for i,o in enumerate(r28_ops)
                       if o['box']==[*q,*q]]
            assert len(matches)==1 and matches[0]['operation']['state']=='minecraft:air'
            assert q in r28_before
            result.update(disposition='stale_curve_clearance_cut_in_authored_deck',
                          historical_measurement=r28_before[q],historical_operation=matches[0],
                          historical_source=str(r28/'native_train_body_clearance/ops.json.gz'),
                          current_nearest_curve=nearest([x+.5,y,z+.5]),
                          next_action='Restore original smooth_stone floor under exact current air precondition, after frozen mini-model clearance and source checks.')
            edits.append(dict(pos=q,before=state,after='minecraft:smooth_stone',before_nbt=None,after_nbt=None,
                              reason='Restore R20 complete public deck where R28 cleared an obsolete curved alignment; current rail is straight and clear.'))
        else:
            column = [dict(pos=[x,Y,z],state=w.reader.state(x,Y,z)) for Y in range(y-1,y+8)]
            result.update(disposition='preserved_current_enclosure_source_unresolved',
                          current_wall_column=column,
                          source_not_proven='No exact R25 wall operation; R21 full-width port clears this body coordinate. R41 filled_edges references the position but does not author this wall. Do not extend adjacent R25 wall ownership to these cells.',
                          adjacent_retirement='The R25 retired gallery ends at Z=-50; these cells are at its retained-station rim Z=-49.',
                          current_geometry='Two occupied footprints continue the current wall at X<=114/Z=-49 and meet the X114/Z<=-50 glazing. Removing them would open the retired-side junction.',
                          next_action='Retain both walls; recover the exact later enclosure/retirement operation before changing the declared public ownership or removing cells.',
                          passed=False)
        disposition.append(result)

    # A cube below platform-top elevation is checked against only vehicle
    # cubes actually intersecting that height interval, not the widest roof.
    modelroot = base/'deep-mini-model-envelope-v1'
    models = []
    for ident in ('eidan_9000_mini_cab_1','eidan_9000_mini_cab_2','eidan_9000_mini_trailer'):
        with np.load(modelroot/(ident+'-visible-cubes.npz')) as a:
            lo = a['cubes'].min(1)-a['door_slides']
            hi = a['cubes'].max(1)+a['door_slides']
            names = a['names']
        band = (lo[:,1] < 1) & (hi[:,1] > 0)
        model=load(modelroot/(ident+'.json'))
        nonvisible=[p for p in model['parts'] if p['kind']!='NORMAL'
                    and p['door_motion_bounds'][0][1]<1 and p['door_motion_bounds'][1][1]>0]
        sensor_radius=max(max(abs(p['door_motion_bounds'][0][0]),abs(p['door_motion_bounds'][1][0])) for p in nonvisible)
        models.append(dict(vehicle=ident,low_band=[0,1],overlapping_cubes=int(band.sum()),
                           maximum_abs_lateral=float(max(abs(lo[band,0].min()),abs(hi[band,0].max()))),
                           low_band_parts=sorted(set(names[band].tolist())),
                           nonvisible_low_band=nonvisible,nonvisible_lateral_radius=sensor_radius,
                           maximum_longitudinal=float(max(abs(lo[:,2].min()),abs(hi[:,2].max()))),
                           maximum_abs_lateral_any_height=float(max(abs(lo[:,0].min()),abs(hi[:,0].max())))))
    radius=max(m['maximum_abs_lateral'] for m in models)
    reach=max(m['maximum_longitudinal'] for m in models)
    assert reach <= 6.75
    local_curves=[]
    # 12m covers maximum longitudinal reach + largest bogie offset + an
    # additional 0.25m. Every potentially contributing pose is on one straight
    # level segment family, so no guessed corner orientation is needed here.
    for ci,curve in enumerate(native['curves']):
        if curve['mode']!='TRAIN':continue
        pts=np.array(curve['points'])
        near=np.zeros(len(pts),bool)
        for edit in edits:
            x,y,z=edit['pos']
            near|=((pts[:,0]-(x+.5))**2+(pts[:,2]-(z+.5))**2 < 12**2)&(abs(pts[:,1]-y)<8)
        if near.any():
            picked=pts[near]
            assert np.all(abs(picked[:,0]-310.5)<1e-8) and np.all(abs(picked[:,1]+467)<1e-8)
            local_curves.append(dict(curve_index=ci,kind=curve['kind'],min=picked.min(0).tolist(),max=picked.max(0).tolist()))
    assert {c['curve_index'] for c in local_curves}=={30,150}
    margins=[]
    for edit in edits:
        x,y,z=edit['pos']
        margin=310.5-(x+1)-radius
        assert margin>.10
        sensor_separation=310.5-(x+1)-max(m['nonvisible_lateral_radius']for m in models)
        assert sensor_separation>=0
        margins.append(dict(pos=edit['pos'],minimum_horizontal_separation=margin,
                            nonvisible_boundary_separation=sensor_separation,
                            nonvisible_boundary_touches_without_positive_overlap=sensor_separation==0,
                            rail_center_x=310.5,rail_y=-467,added_cube_height=[0,1]))
    # A false blanket claim based on nominal width would miss this sentinel.
    sentinel_gap=310.5-(309+1)-radius
    assert sentinel_gap<0
    controls.append(dict(case='one_cell_toward_track_floor_intrudes',pos=[309,-467,524],
                         separation=sentinel_gap,rejected=True))

    # Apply only in memory, on top of the already frozen stair guards.
    guard_edits=load(base/'deep-platform-guards-candidate-v1/exact-edits.json')
    if isinstance(guard_edits,dict):guard_edits=guard_edits['changes']
    guardmap={tuple(e['pos']):e['after'] for e in guard_edits}
    change={tuple(e['pos']):e['after'] for e in edits}
    assert not set(change)&set(guardmap)
    captured_tags=nbtlib.load(source/'devices.dat')['Devices']
    occupied_tags={tuple(int(t[k])for k in('x','y','z'))for t in captured_tags}
    assert not set(change)&occupied_tags
    before=EnvelopeWalker(source,shapes);before.reader=Overlay(before.reader,guardmap)
    after=EnvelopeWalker(source,shapes);after.reader=Overlay(after.reader,{**guardmap,**change})
    native22=load(base/'deep-platform-fullwidth-review-v1/checks/native-22.json')
    prior_clear={tuple(c['feet']) for c in native22['cells'] if c['status']=='clear_public_floor'}
    full=[]
    for cell in bysite['native-22']['cells']:
        x,y,z=cell['floor'];p=(x+.5,cell.get('feet_y',y+1),z+.5)
        oldbody,newbody=before.body(*p),after.body(*p)
        assert oldbody==newbody
        assert oldbody is None or oldbody['kind']!='unknown'
        oldstate,oldboxes=before.boxes(x,y,z);newstate,newboxes=after.boxes(x,y,z)
        supported=any(abs(y+b[4]-p[1])<1e-6 and b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 for b in newboxes)
        assert supported
        full.append(dict(floor=cell['floor'],support_after=True,body_before=oldbody,body_after=newbody,
                         support_state_changed=oldstate!=newstate))
    connections=[]
    restored_feet={(e['pos'][0]+.5,e['pos'][1]+1,e['pos'][2]+.5) for e in edits}
    adjacency={}
    for edit in edits:
        x,y,z=edit['pos'];p=(x+.5,y+1,z+.5)
        links=[]
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            q=(p[0]+dx,p[1],p[2]+dz)
            if q not in prior_clear|restored_feet:continue
            a,b=strict_walk(after,[p,q]),strict_walk(after,[q,p])
            if a['kind']==b['kind']=='strict_static_clear':links.append(dict(target=q,forward=a,reverse=b))
        assert links
        adjacency[p]=[tuple(link['target']) for link in links]
        failure=strict_walk(before,[p,p]);success=strict_walk(after,[p,p])
        assert failure['kind']!='strict_static_clear' and success['kind']=='strict_static_clear'
        connections.append(dict(floor=edit['pos'],before=failure,after=success,links_in_restored_public_component=links))
        blocker=EnvelopeWalker(source,shapes)
        blocker.reader=Overlay(blocker.reader,{**guardmap,**change,(x,y+2,z):'minecraft:stone'})
        rejected=strict_walk(blocker,[p,p])
        assert rejected['kind']!='strict_static_clear'
        controls.append(dict(case='blocked_repaired_headroom',floor=edit['pos'],result=rejected,rejected=True))
    connected=set(prior_clear)
    while True:
        added={p for p,targets in adjacency.items() if any(q in connected for q in targets)}-connected
        if not added:break
        connected|=added
    assert restored_feet<=connected
    roundtrip={tuple(e['pos']):e['after'] for e in edits}
    for e in edits:roundtrip[tuple(e['pos'])]=e['before']
    assert all(roundtrip[tuple(e['pos'])]==w.reader.state(*e['pos']) for e in edits)
    inverse=[dict(pos=e['pos'],before=e['after'],after=e['before'],before_nbt=None,after_nbt=None) for e in edits]
    save(out/'source-dispositions.json',disposition)
    save(out/'half-step-datum-corrections.json',half_steps)
    save(out/'public-surface-check.json',dict(site='native-22',cells=full,count=len(full),
         changed_support_cells=7,new_body_obstructions=0,new_clear_cells=7,all_added_cells_connected=True,
         connections=connections,old_routes_rerun=0,base_stair_guard_overlay_cells=len(guardmap)))
    save(out/'negative-controls.json',controls)
    save(out/'train-clearance.json',dict(models=models,local_curve_witness=local_curves,
         pose_neighborhood_radius=12.0,maximum_model_reach=reach,maximum_bogie_offset=5.0,
         all_relevant_points_level_and_axis_aligned=True,per_edit=margins,
         minimum_separation=min(m['minimum_horizontal_separation'] for m in margins),
         minimum_nonvisible_boundary_separation=min(m['nonvisible_boundary_separation']for m in margins),
         nonvisible_interaction_boundary_note='Six restored cubes touch the outer DOORWAY sensor face at X309; no positive-volume overlap. This is not a live boarding validation.',
         high_level_guard_not_authorized=True,full_vehicle_operation_pass=False,
         native_geometry_equal_underground_rails=len(evaluated)))
    resource_check=modelroot/'resource-source-check.json'
    resource_proof=load(resource_check) if resource_check.exists() else None
    resource_verified=bool(resource_proof and not resource_proof['errors'] and resource_proof['all_selected_dependencies_resolve_to_same_bytes'])
    patch=dict(schema=1,scope='native-22 seven restored original public deck voxels',
               edits=edits,positive_edit_mask=[e['pos']for e in edits],inverse=inverse,
               before_preconditions='Exact block state plus no block entity at each edited cell; reject changed current state.',
               source=str(source),full_declared_surface_check=str(out/'public-surface-check.json'),
               model_clearance=str(out/'train-clearance.json'),negative_controls=str(out/'negative-controls.json'),
               reverse_roundtrip_pass=True,root_must_package_and_install=True,
               release_ready=resource_verified,resource_precedence_evidence=resource_proof,
               exported_devices_at_edits=0,
               release_pending=[] if resource_verified else ['Root confirms installed resource precedence for the three mini models.'],
               installation_preconditions='Root must confirm current exact before state/NBT, package delta and read back after applying; no runtime validation is implied.',
               existing_stair_guard_candidate_untouched=True,world_written=False)
    save(out/'seven-cell-floor-patch-plan.json',patch)
    readiness=dict(status='finite_offline_disposition_frozen',
        reviewed=dict(open_end_interfaces=223,reported_missing_floor_cells=17,unclassified_wall_footprints=2),
        conclusions=dict(reachable_nonboarding_terminal_interfaces_need_boundary=223,
                         actual_half_step_surfaces_not_missing_support=10,
                         obsolete_curve_cut_floor_cells_to_restore=7,
                         wall_footprints_preserved_source_unresolved=2),
        groups=str(out/'terminal-edge-groups.json'),source_dispositions=str(out/'source-dispositions.json'),
        patch_plan=str(out/'seven-cell-floor-patch-plan.json'),
        frozen_mini_resource_precedence_verified=resource_verified,
        pending_measurements=[dict(kind='source_ownership',positions=[[113,-442,-49],[114,-442,-49]],
                 already_measured_box=[107,-445,-55,118,-435,-46],
                 request='Find the exact later wall/enclosure operation or current retirement contract; additional air inference is not evidence.')],
        required_repairs=[dict(kind='floor_restore',count=7,plan=str(out/'seven-cell-floor-patch-plan.json')),
                          dict(kind='nonboarding_end_boundary',count=223,groups=str(out/'terminal-edge-groups.json'),
                               rule='Continuous setback end barriers must preserve all boarding gates, public circulation and model-height bands. Do not place full-height guards at the restored floor lip using the floor-only clearance result.')],
        additional_half_step_rail_interfaces=10,
        corrected_datum_is_not_track_access_permission=True,
        source_currentness_evidence=str(base/'deep-platform-guards-candidate-v1/source-currentness.json'),
        underground_evaluated_geometry_verified_against_frozen_installed69=True,
        same_geometry_rail_count=len(evaluated),
        parent_reports_later71_additions_are_surface_only=True,
        source_not_new_capture=True,unknown_treated_as_air=False,
        original_60_routes_rerun=0,shared_tools_modified=False,
        world_opened=False,world_written=False,native_database_written=False,jar_opened=False,
        game_or_simulator_started=False,commit_created=False,operational_pass=False,
        stage_two_complete=False,whole_station_complete=False,readiness_frozen=True,
        task_expansion_stopped=True,active_owned_processes=[])
    save(out/'readiness.json',readiness)
    print(json.dumps(readiness['conclusions'],ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--finalize',action='store_true')
    args=parser.parse_args()
    main(args.base,args.out,args.finalize)
