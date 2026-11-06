"""Publish a zero-native/device/actor sparse section patch from a JSON contract.

prepare/install/record require explicit current world, authority, native snapshot,
replay expected directory, batch, client reference and producer log. Import and
validate_offline are offline. No Editor or fixed-height surface interpretation.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import time

import nbtlib
from install_r53_carrier_trays import stopped_world
from map_pipeline.delivery_check import read, write, capture_identity, verify_delivery
from map_pipeline.install.invariants import require_nbt_equal
from map_pipeline.station_release_checks import verify as check_package
from native_transit_additions import inventory, assert_preserved
from prepare_station_section_recipes import DATA, require, validate_delta, actual_cells, prepare as prepare_recipes

CONTROL = 'section-release-check.json'
FREEZE = 'section-release-freeze'


def package_file(root, name):
    root = Path(root).resolve(); path = (root/name).resolve()
    require(path.is_relative_to(root) and path.is_file(), 'Missing or escaping package file: '+str(name))
    return path


def metadata_scope(candidate):
    files = []
    for path in (Path(candidate)/'after').rglob('*'):
        if not path.is_file(): continue
        rel = path.relative_to(Path(candidate)/'after')
        require(rel.parent == DATA and re.fullmatch(r'-?\d+_-?\d+\.dat', rel.name),
                'Section access patches may publish only exact surface recipes')
        files.append(path)
    return files


def strict_result(result, maximum):
    require(result.get('kind') == 'strict_static_clear'
            and 0 <= result.get('maximum_observed_step', math.inf) <= maximum
            and result.get('samples', 0) > 0, 'Route lacks measured bidirectional half-step clearance')


def source_dependencies(spec):
    """Reconstruct explicitly ordered, exact overlays from cached section data."""
    overlay, dependencies = {}, []
    for item in spec.get('source_overlays', []):
        checked = validate_delta(Path(item['candidate']), item['changes_file'],
                                 spec['section_source'], overlay)
        require(len(checked['changes']) == item['expected_cells'], 'Dependency cell scope differs')
        require(not set(overlay).intersection(checked['changes']), 'Overlapping dependency overlays are not authorized')
        overlay.update({p:r['after'] for p,r in checked['changes'].items()})
        dependencies.append((item, checked))
    return overlay, dependencies


def installed_dependencies(dependencies, world=None):
    """Receipt checks are offline; root additionally verifies FULL actual cells under lock."""
    for item, checked in dependencies:
        candidate = Path(item['candidate'])
        require(item.get('installation') and Path(item['installation']).is_file(), 'Dependency is not installed')
        receipt = read(item['installation']); delivery = read(candidate/'delivery-check.json')
        control = read(candidate/CONTROL)
        require(receipt.get('status') == 'installed' and receipt.get('changed_section_readback') is True
                and receipt.get('cells') == len(checked['changes'])
                and [Path(p).resolve() for p in receipt.get('candidates', [])] == [candidate.resolve()],
                'Dependency installed receipt differs')
        require(Path(receipt['world']).resolve()==Path(checked['manifest']['world']).resolve(),
                'Dependency receipt world differs')
        require(delivery.get('passed') is True and delivery.get('production_replay_passed') is True
                and delivery.get('changed_cells') == len(checked['changes'])
                and control.get('installed_delivery_check_passed') is True
                and control.get('production_recipe_replay_passed') is True, 'Dependency replay/delivery is incomplete')
        if world is not None:
            require(Path(world).resolve()==Path(receipt['world']).resolve(), 'Dependency belongs to another world')
            current, _ = actual_cells(world, checked, after=True)
            require_nbt_equal(nbtlib.load(candidate/'target-devices-before.dat'), current, 'dependency-devices')


def json_value(value):
    return json.loads(json.dumps(value))


def recompute_footprint(declaration, source, shapes, edits):
    import verify_declared_platform_footprints as fw
    from review_underground_station_evidence import Overlay
    original = fw.EnvelopeWalker
    class CandidateWalker(original):
        def __init__(self, src, ss):
            super().__init__(src, ss)
            self.reader = Overlay(self.reader, edits)
    fw.EnvelopeWalker = CandidateWalker
    try:
        return json_value(fw.footprint(declaration, Path(source), shapes))
    finally:
        fw.EnvelopeWalker = original


def verify_footprint(saved, actual):
    for field in ('site', 'declared_floor_cells', 'floor_status', 'cells', 'failures',
                  'clear_cells', 'connected_to_retained_routes', 'disconnected', 'capture_requests'):
        require(saved[field] == actual[field], 'Full-width proof is stale: '+field)
    require(not actual['failures'] and not actual['disconnected'] and not actual['capture_requests'],
            'Public footprint has missing support, obstruction, unknown or disconnected cells')


def validate_retained_failure(row, exception, before, after, changes):
    require(exception and row['path']==exception['path'] and row['before']==exception['results']
            and row['after']==exception['results'], 'Unapproved or changed original route failure')
    witness=exception['obstruction']
    require(witness['kind']=='body_obstruction' and before.body(*exception['witness_feet'])==witness
            and after.body(*exception['witness_feet'])==witness
            and before.reader.state(*witness['pos'])==after.reader.state(*witness['pos'])==witness['state'],
            'Original route failure witness differs')
    # Bound every anchor the extended-cuboid body or bearing query could read
    # along the entire historical path. Ignore Y for a conservative exclusion.
    radius=max(.3,*(abs(v)+.3 for v in before.minimum+before.maximum))+1
    for a,b in zip(row['path'],row['path'][1:]):
        require(not any(min(a[0],b[0])-radius <= p[0] <= max(a[0],b[0])+radius
                        and min(a[2],b[2])-radius <= p[2] <= max(a[2],b[2])+radius for p in changes),
                'Patch intersects unresolved original route query domain')
    return dict(key=row['key'],results=row['before'],obstruction=witness,full_path_query_domain_disjoint=True,
                horizontal_anchor_padding=radius,resolved=False)


def declaration_transition(before, after, exact, changes, expected):
    """Keep the complete denominator; allow only measured occupied/margin cells."""
    bsites = {s['site']:s for s in before['stations']}; asites = {s['site']:s for s in after['stations']}
    require(len(bsites) == len(before['stations']) and bsites.keys() == asites.keys(), 'Declaration station scope differs')
    calculated, margins, occupants, count = [], [], [], 0
    for site, b in bsites.items():
        a = asites[site]
        require({k:v for k,v in b.items() if k != 'cells'} ==
                {k:v for k,v in a.items() if k not in ('cells','nonboarding_margin_semantics')},
                'Original boarding, bay or retained route declaration changed')
        old = {tuple(c['floor']):c for c in b['cells']}; new = {tuple(c['floor']):c for c in a['cells']}
        require(len(old) == len(b['cells']) == len(new) == len(a['cells']) and old.keys() == new.keys(),
                'Complete floor denominator changed')
        count += len(old)
        for p, c in old.items():
            q = new[p]
            if c == q: continue
            calculated.append(dict(site=site, floor=list(p), before=c, after=q))
            require(q.get('public_walkable') is False and q['floor'] == c['floor'] and q['source'] == c['source'],
                    'Declaration change is not a bounded non-walkable cell')
            if q.get('role') == 'guarded_nonboarding_trackside_margin':
                require({k:v for k,v in q.items() if k not in ('role','public_walkable','ownership_change','feet_y')} ==
                        {k:v for k,v in c.items() if k not in ('role','feet_y')} and q.get('ownership_change')
                        and q.get('feet_y',p[1]+1) in (p[1]+.5,p[1]+1),
                        'Margin reclassification changed unrelated fields')
                margins.append((site,p))
            else:
                hit = q.get('new_terminal_barrier_occupant') or {}
                require(hit.get('kind') == 'body_obstruction' and tuple(hit['pos']) in changes
                        and changes[tuple(hit['pos'])]['after'] == hit['state'], 'Declaration occupant is outside exact patch')
                require({k:v for k,v in q.items() if k not in ('public_walkable','allowed_occupants','new_terminal_barrier_occupant')} ==
                        {k:v for k,v in c.items() if k != 'allowed_occupants'}
                        and q['allowed_occupants'][:len(c['allowed_occupants'])] == c['allowed_occupants']
                        and all(hit['state'].startswith(v) for v in q['allowed_occupants'][len(c['allowed_occupants']):]),
                        'Occupied declaration changed unrelated fields')
                occupants.append((site,p))
    key = lambda r: (r['site'], r['floor'])
    require(sorted(calculated,key=key) == sorted(exact,key=key), 'Exact declaration delta differs')
    actual = dict(complete_floor_denominator=count, finite_margin_cells=len(margins),
                  new_barrier_occupied_cells=len(occupants), declaration_changed_cells=len(calculated))
    require(actual == expected, 'Declaration classification scope differs')
    return actual, set(margins)


def scope_evidence(candidate, spec, report, walker, prior, changes, overlay, shapes, recompute):
    """Scope-specific physics, without manufacturing stair-guard report fields."""
    from review_underground_station_evidence import strict_walk
    base = read(spec['original_declarations']); review = Path(spec['review_directory'])
    stations = {s['site']:s for s in base['stations']}
    require(Path(base['source']).resolve() == Path(spec['section_source']).resolve(), 'Declaration source differs')
    retained = []; exceptions={r['key']:r for r in spec.get('retained_route_exceptions',[])}; unresolved=[]
    for site, station in stations.items():
        for i, route in enumerate(station['retained_paths']):
            row = dict(key=site+'/original/'+str(i), path=route['path'])
            if recompute:
                for phase, w in (('before',prior),('after',walker)):
                    proofs = {d:strict_walk(w,route['path'][::sign]) for d,sign in (('forward',1),('reverse',-1))}
                    row[phase] = proofs
                if all(p.get('kind')=='strict_static_clear' for phase in ('before','after') for p in row[phase].values()):
                    for phase in ('before','after'):
                        for proof in row[phase].values(): strict_result(proof,spec['maximum_step'])
                    require(row['key'] not in exceptions, 'Stale original route exception')
                else:
                    unresolved.append(validate_retained_failure(row,exceptions.get(row['key']),prior,walker,changes))
            retained.append(row)
    require(len(retained) == spec['expected_original_routes'], 'Original route denominator differs')
    metrics = dict(scope_kind=spec['scope_kind'], original_routes=len(retained),
                   original_routes_recomputed_before_and_after=recompute, maximum_step=spec['maximum_step'])
    if recompute:
        require({r['key'] for r in unresolved}==set(exceptions), 'Original route exception inventory differs')
        metrics.update(original_routes_passed=len(retained)-len(unresolved),unresolved_original_routes=unresolved)
    edits = {p:q['after'] for p,q in changes.items()}
    affected = {q['site'] for q in changes.values()}
    require(affected == {s['site'] for s in report['stations']}, 'Functional station scope differs')
    if spec['scope_kind'] == 'floor_restore':
        require(len(affected) == 1 and not report['guard_probes'], 'Floor restoration cannot claim terminal guards')
        station = read(package_file(candidate,spec['floor_declaration']))
        require(station == stations[station['site']], 'Floor declaration differs from complete original')
        saved = read(package_file(review,spec['floor_fullwidth']))
        if recompute:
            actual = recompute_footprint(station,spec['section_source'],shapes,{**overlay,**edits})
            verify_footprint(saved,actual)
            before = recompute_footprint(station,spec['section_source'],shapes,overlay)
            missing = {tuple(c['floor']) for c in before['failures'] if c['status'] == 'missing_declared_support'}
            require(missing == set(edits) and len(before['failures']) == len(edits), 'Restored support preconditions differ')
            before_clear = {tuple(c['floor']) for c in before['cells'] if c['status']=='clear_public_floor'}
            after_clear = {tuple(c['floor']) for c in actual['cells'] if c['status']=='clear_public_floor'}
            require(after_clear-before_clear == set(edits) and before_clear <= after_clear, 'Restored public floor scope differs')
        sr = report['stations'][0]
        require((sr['declared_floor_cells'],sr['missing_support_before'],sr['missing_support_after'],sr['new_clear_cells'],sr['connected_public_cells']) ==
                (len(station['cells']),len(edits),0,len(edits),saved['connected_to_retained_routes']), 'Floor functional scope differs')
        train = read(package_file(candidate,spec['vehicle_proof']))
        require(train['all_relevant_points_level_and_axis_aligned'] is True and
                train['pose_neighborhood_radius'] > train['maximum_model_reach']+train['maximum_bogie_offset'], 'Floor local vehicle scope insufficient')
        maximum = max(m['maximum_abs_lateral'] for m in train['models'])
        require({tuple(r['pos']) for r in train['per_edit']} == set(edits), 'Vehicle proof edit scope differs')
        for r in train['per_edit']:
            x,y,z = r['pos']; center = r['rail_center_x']
            separation = max(center-(x+1),x-center)-maximum
            require(abs(separation-r['minimum_horizontal_separation']) < 1e-8 and separation > 0
                    and y == r['rail_y'] and r['added_cube_height']==[0,1]
                    and r['nonvisible_boundary_separation'] >= 0, 'Restored floor intersects vehicle envelope')
        require(train['full_vehicle_operation_pass'] is False, 'Offline floor proof claims runtime acceptance')
        metrics.update(complete_floor_denominator=len(station['cells']), restored_support_cells=len(edits),
                       clear_connected_public_cells=saved['connected_to_retained_routes'], declaration_changed_cells=0)
    else:
        from build_deep_station_end_guards import terminal_free_space, edge_coverage, uv
        from shapely.geometry import Point
        complete = read(package_file(candidate,spec['complete_declarations']))
        exact = read(package_file(candidate,spec['declaration_delta']))
        values, margins = declaration_transition(base,complete,exact,
            {p:dict(after=s) for p,s in edits.items()},spec['expected_declaration_scope'])
        metrics.update(values)
        coverage = read(package_file(review,spec['continuous_coverage']))
        require(coverage['errors']==[] and coverage['unknown_as_air'] is False and
                coverage['partial_floor_support_admitted'] is True and coverage['jump_or_climb_permitted'] is False
                and (coverage['player_width'],coverage['player_height'],coverage['step_height'])==(.6,1.8,.5)
                and coverage['phase']==report['dynamic_gate_phase_scope'], 'Continuous boundary model differs')
        design = read(package_file(candidate,spec['boundary_design']))
        components = design['components']
        require(len(components)==spec['expected_terminal_components'], 'Terminal component count differs')
        requested=set()
        for component in components:
            station=stations[component['site']]
            bay=next(b for b in station['bays'] if b['line']==component['line'])
            lo,hi=component['preserved_boarding_u'];gate=component['fixed_gate_end']
            require(prior.reader.state(*gate['pos'])==walker.reader.state(*gate['pos'])==gate['state'],
                    'Original terminal boarding gate changed')
            for x,y,z in component['requested_cells']:
                u,_=uv(bay,[x,y,z])
                require(u<lo or u>hi, 'Terminal guard enters original boarding interval')
                requested.update((x,y+dy,z) for dy in (0,1))
        require(requested==set(edits), 'Terminal design and exact voxel scope differ')
        all_margin = set(); total_before=total_after=public=0
        for station_result in report['stations']:
            site=station_result['site']; station=stations[site]
            declaration=read(package_file(review,spec['declarations_pattern'].format(site=site)))
            saved=read(package_file(review,spec['fullwidth_pattern'].format(site=site)))
            full=next(s for s in complete['stations'] if s['site']==site)
            reviewed_cells = copy.deepcopy(declaration['cells']+declaration['retained_nonpublic_margin_cells'])
            for cell in reviewed_cells:
                if cell.get('new_terminal_barrier_occupant') or cell.get('role')=='guarded_nonboarding_trackside_margin':
                    cell['public_walkable'] = False
            require(sorted(reviewed_cells,key=lambda c:c['floor']) ==
                    sorted(full['cells'],key=lambda c:c['floor']), 'Published complete declarations differ from verified cells')
            if recompute:
                verify_footprint(saved,recompute_footprint(declaration,spec['section_source'],shapes,{**overlay,**edits}))
            require(not saved['failures'] and not saved['disconnected'] and not saved['capture_requests']
                    and station_result['clear_public']==station_result['connected_public']==saved['connected_to_retained_routes'],
                    'Terminal retained public proof differs')
            public+=saved['connected_to_retained_routes']
            evidence=next(s for s in coverage['stations'] if s['site']==site)
            issues=[r for c in components if c['site']==site for r in c['issues']]
            require(evidence['interfaces']==len(issues)==evidence['protected_after']==evidence['exposed_before']
                    and all(r['protected'] for r in evidence['after']) and not any(r['protected'] for r in evidence['before']),
                    'Original terminal interfaces are not all closed')
            if recompute:
                geometry=dict(station,_source=spec['section_source'])
                seeds=[c for c in saved['cells'] if c['status']=='clear_public_floor']
                after_space=terminal_free_space(walker,geometry,seeds)
                before_space=terminal_free_space(prior,geometry,seeds)
                require(edge_coverage(after_space,issues)==evidence['after'] and
                        edge_coverage(before_space,issues)==evidence['before'], 'Continuous terminal boundary proof is stale')
            for row in evidence['finite_nonboarding_margin']:
                p=tuple(row['floor']);all_margin.add((site,p))
                cell=next(c for c in full['cells'] if tuple(c['floor'])==p)
                require(row['feet']==[p[0]+.5,cell.get('feet_y',p[1]+1),p[2]+.5], 'Margin feet differ from published declaration')
                owner=cell['ownership_change']['component']
                component=next(c for c in components if [c['site'],c['line'],c['end'],c['side']]==owner)
                bay=next(b for b in station['bays'] if b['line']==component['line'])
                u,_=uv(bay,p);lo,hi=component['preserved_boarding_u']
                require(u<lo or u>hi, 'Margin reclassification enters original boarding interval')
                require(row['support'] is True and row['reachable_from_retained_public'] is False, 'Margin is unsupported or publicly reachable')
                if recompute:
                    x,y,z=p;_,boxes=walker.boxes(*p);h=row['feet'][1]
                    supported=boxes is not None and any(abs(y+b[4]-h)<1e-7 and b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 for b in boxes)
                    require(supported and not after_space[h].intersects(Point(x+.5,z+.5))
                            and walker.body(*row['feet'])==row['body'], 'Margin body/support proof is stale')
            total_before+=evidence['exposed_before'];total_after+=sum(not r['protected'] for r in evidence['after'])
        require(all_margin==margins, 'Margin evidence scope differs')
        require((total_before,total_after,public)==(spec['expected_terminal_edges_before'],0,spec['expected_clear_connected_public_cells']),
                'Terminal aggregate scope differs')
        model=read(package_file(review,spec['vehicle_proof']))
        require(model['errors']==[] and model['vehicle_intrusions']==[] and model['runtime_verified'] is False
                and model['padding_covers_observed_sample_motion'] is True
                and model['maximum_observed_adjacent_corner_displacement'] <= model['interval_padding']
                and model['travel_directions']==[-1,1] and len(model['bogie_pose_modes'])==2
                and model['tested_heightband_obbs']>0
                and all(n['rejected'] and n.get('witness') for n in model['negative_controls']), 'Vehicle swept-volume evidence incomplete')
        import numpy as np
        model_source=Path(spec['vehicle_model_directory'])
        require(read(model_source/'resource-source-check.json')['errors']==[], 'Vehicle resource precedence failed')
        for detail in model['model_bands']:
            name=detail['vehicle']
            with np.load(model_source/(name+'-closed-cubes.npz')) as closed, np.load(model_source/(name+'-visible-cubes.npz')) as visible:
                cubes=np.concatenate([closed['cubes'],visible['cubes']+visible['door_slides'][:,None,:]])
            low,high=cubes.min(1),cubes.max(1);bands=[]
            for bottom in np.arange(0,4,.125):
                top=bottom+.125;selected=(high[:,1]>bottom+1e-10)&(low[:,1]<top-1e-10)
                if not selected.any():continue
                a=low[selected].min(0);b=high[selected].max(0)
                a[1]=max(a[1],bottom);b[1]=min(b[1],top)
                corners=a+(b-a)*np.array([[x,y,z] for x in (0,1) for y in (0,1) for z in (0,1)])
                bands.append(dict(min=corners.min(0).tolist(),max=corners.max(0).tolist()))
            require(detail['selected_cubes']==len(cubes) and detail['bands']==bands, 'Vehicle height bands differ from exported complete cubes')
        metrics.update(clear_connected_public_cells=public, terminal_edges_before=total_before,
                       terminal_edges_after=total_after, terminal_components=len(components),
                       vehicle_heightband_tests_recorded=model['tested_heightband_obbs'],vehicle_sweep_recomputed=False)
    return metrics, retained


def validate_offline(args, recompute_routes=True):
    """Validate actual saved evidence and source cells without opening the world."""
    candidate = Path(args.candidate); spec = read(args.config)
    require(spec.get('schema') == 'section-access-patch-release-v1', 'Unknown section release configuration')
    require(re.fullmatch(r'[a-z0-9][a-z0-9_-]*', spec['id']) is not None, 'Invalid patch identifier')
    require(0 < spec['maximum_step'] <= .5, 'Half-step route bound must be retained')
    package_file(candidate, spec['changes_file']); package_file(candidate, spec['functional_report'])
    kind = spec.get('scope_kind', 'stair_guard')
    require(kind in ('stair_guard','floor_restore','terminal_boundary'), 'Unknown section scope_kind')
    overlay, dependencies = source_dependencies(spec)
    if kind != 'stair_guard':
        require([len(c['changes']) for _,c in dependencies] == spec['expected_source_overlay_cells']
                and dependencies, 'Installed source overlay scope differs')
    checked = validate_delta(candidate, spec['changes_file'], spec['section_source'], overlay)
    require(not set(overlay).intersection(checked['changes']), 'Patch overwrites a preserved dependency')
    manifest = checked['manifest']; changes = checked['changes']
    if kind != 'stair_guard':
        require([{k:r[k] for k in ('pos','before','after')} for r in checked['rows']] == spec['exact_transitions'],
                'Exact transition contract changed after vehicle and geometry review')
    require(Path(manifest.get('section_source', manifest['source'])).resolve() == Path(spec['section_source']).resolve(),
            'Configured section source differs from manifest')
    require(not any(manifest.get(k) for k in ('native_additions','native_changes','native_members',
            'native_geometry_patch','native_geometry_migrations','actor_changes','entity_moves','json_metadata',
            'terrain_inputs','preserved_generation_statuses')), 'Section patch authorizes no native/actor/client changes')
    require(manifest.get('device_changes', 0) == spec['expected_device_changes'] == 0
            and len(nbtlib.load(candidate/'block-entities.dat')['Changes']) == 0, 'Device changes are forbidden')
    require(len(changes) == spec['expected_changed_cells'], 'Configured section scope differs')
    require(checked['extents'] == {(spec['delta_y_origin'], spec['delta_height'])}
            and manifest['vertical_extent'] == spec['vertical_extent'], 'Configured extent differs')
    approved = {tuple(q['pos']): q for q in spec.get('approved_existing_changes', [])}
    old = {p:dict(pos=list(p),before=q['before'],after=q['after']) for p,q in changes.items() if q['before'] != 'minecraft:air'}
    require(old == approved, 'Original block edits lack exact authorization')
    devices = nbtlib.load(candidate/'captured-devices.dat')['Devices']
    protected = {tuple(int(tag[k]) for k in ('x','y','z')) for tag in devices}
    require(not protected.intersection(changes), 'Patch touches a captured device host')
    capture = read(candidate/'capture.json'); report = read(candidate/spec['functional_report'])
    require(report.get('errors') == [] and report.get('changed_cells') == len(changes)
            and report.get('vehicle_intrusions') == [] and report.get('dynamic_gate_bypass') is False,
            'Functional or vehicle proof is incomplete')
    require(report.get('preserved_devices') == len(devices) == capture['devices']
            and report.get('preserved_actors') == (len(capture['actors']) if isinstance(capture['actors'], list) else capture['actors']),
            'Whole-capture device/actor evidence differs')
    require(spec['ground_network'] == {'mode':'preserve', 'columns':[]}, 'Section guard patches must preserve scalar network')
    review = Path(spec['review_directory']); review_report = read(package_file(review, spec['review_report']))
    require(review_report.get('errors') == [] and (kind == 'floor_restore' or review_report['stations'] == report['stations']), 'Independent station proof differs')
    fields = spec['evidence_fields']; phases = {p['phase']:p for p in report[fields['phases']]}
    require(set(phases) == {'before','after'} and len(report[fields['phases']]) == 2, 'Exact before/after phase proof is required')
    goals = {g['key']:g for g in phases['after']['goals']}
    before = {g['key']:g for g in phases['before']['goals']}
    require(len(goals) == len(phases['after']['goals']) and set(goals) == set(before)
            and set(spec['required_goals']) == set(goals), 'Required route scope differs')
    from repair_declared_platform_guards import make_walker, touching, sweep
    from review_underground_station_evidence import strict_walk
    shapes = read(package_file(candidate, spec['collision_shapes']))
    walker = make_walker(Path(spec['section_source']), shapes, {**overlay, **{p:q['after'] for p,q in changes.items()}})
    prior = make_walker(Path(spec['section_source']), shapes, overlay)
    routes = []
    for key, route in goals.items():
        require(route.get('reachable') is True and route.get('strict_pass') is True and route.get('path')
                and route['path'] == before[key]['path'], 'Original route was moved or became unreachable')
        routes.append(dict(key=key, path=route['path'], forward=route['forward'], reverse=route['reverse']))
        if kind != 'stair_guard':
            expected_before = kind != 'floor_restore'
            require(before[key].get('reachable') is expected_before and before[key].get('strict_pass') is expected_before,
                    'Scope-specific before route result differs')
            if recompute_routes:
                for direction, points in (('forward',route['path']),('reverse',list(reversed(route['path'])))):
                    actual_before = strict_walk(prior,points)
                    require(actual_before == before[key][direction], 'Saved before route proof is stale: '+key)
                if expected_before:
                    for direction in ('forward','reverse'): strict_result(before[key][direction],spec['maximum_step'])
    scope_metrics = {}; retained = []
    if kind == 'stair_guard':
        public, edges_before, edges_after, site_cells = 0, 0, 0, 0
        sites = set()
        for station in report['stations']:
            site = station['site']; require(site not in sites, 'Duplicate station proof'); sites.add(site)
            require(station['before_status'] == station['after_status']
                    and not station['new_guard_occupied_floors'] and station['new_floating'] == 0,
                    'Existing public floor classifications changed')
            require(station['connected_public_cells'] == station['before_status']['clear_public_floor']
                    and station['complete_eight_direction_probes'] == station['connected_public_cells']*8,
                    'Public floor connection/probe denominator differs')
            require(station['changed_cells'] == sum(q.get('site') == site for q in changes.values()), 'Station cell scope differs')
            public += station['connected_public_cells']; site_cells += station['changed_cells']
            edges_before += station['before_high_edges']; edges_after += station['after_high_edges']
            declaration = read(package_file(review, spec['declarations_pattern'].format(site=site)))
            fullwidth = read(package_file(review, spec['fullwidth_pattern'].format(site=site)))
            require(fullwidth['floor_status'] == station['after_status']
                    and fullwidth['connected_to_retained_routes'] == station['connected_public_cells']
                    and len(fullwidth['cells']) == station['declared_floor_cells']
                    and not fullwidth['disconnected'], 'Full-width public proof differs')
            for phase in ('before','after'):
                edge = read(package_file(review, spec['edges_pattern'].format(site=site, phase=phase)))
                require(not edge['unknown'] and len(edge['unprotected_elevated']) == station[phase+'_high_edges']
                        and edge['probe_count'] == station['complete_eight_direction_probes'], 'Edge proof differs')
            indices = set()
            for result in station['affected_retained_routes_rechecked']:
                i = result['index']; require(i not in indices, 'Repeated affected retained route'); indices.add(i)
                path = declaration['retained_paths'][i]['path']
                routes.append(dict(key=site+'/retained/'+str(i), path=path, forward=result['forward'], reverse=result['reverse']))
            require(station['retained_long_routes'] == len(declaration['retained_paths']) ==
                    len(indices)+station['unchanged_routes_inherited'], 'Retained route accounting differs')
        require((public, edges_before, edges_after, len(routes), site_cells) ==
                (spec['expected_preserved_public_cells'], spec['expected_high_edges_before'],
                 spec['expected_high_edges_after'], spec['expected_rechecked_routes'], len(changes)), 'Aggregate proof scope differs')
    else:
        scope_metrics, retained = scope_evidence(candidate,spec,report,walker,prior,changes,overlay,shapes,recompute_routes)
        public = scope_metrics['clear_connected_public_cells']
        sites = {station['site'] for station in report['stations']}
    for route in routes:
        require(all(len(p) == 3 and all(type(n) in (int,float) and math.isfinite(n) for n in p)
                    for p in route['path']), 'Invalid route coordinates')
        for direction in ('forward','reverse'):
            strict_result(route[direction], spec['maximum_step'])
            if recompute_routes:
                points = route['path'] if direction == 'forward' else list(reversed(route['path']))
                result = strict_walk(walker, points)
                strict_result(result, spec['maximum_step'])
                require(result == route[direction], 'Saved route proof is stale: '+route['key'])
    supports = report[fields['attachment_supports']]; supported = set()
    require({p['site'] for p in supports} == sites, 'Attachment evidence station scope differs')
    for support in supports:
        require(not support['floating'] and support['new_cells'] == support['supported_cells'] ==
                len(support['collision_contact_paths']), 'Floating or unproved guard attachment')
        for proof in support['collision_contact_paths']:
            pos = tuple(proof['pos']); chain = proof['chain']
            require(pos in changes and pos not in supported and chain and tuple(chain[0]['pos']) == pos,
                    'Attachment scope differs')
            require(chain[-1] == proof['foundation'] and tuple(chain[-1]['pos']) not in changes
                    and chain[-1]['pos'][1] == support['foundation_y'], 'Attachment does not reach original foundation')
            boxes = []
            for row in chain:
                p = row['pos']; state, local = walker.boxes(*p)
                require(state == row['state'] and local, 'Attachment contains unknown or stale collision state')
                boxes.append([tuple(p[i%3]+b[i] for i in range(6)) for b in local])
            for i, row in enumerate(chain[:-1]):
                require(sum(abs(a-b) for a,b in zip(row['pos'],chain[i+1]['pos'])) == 1,
                        'Attachment skips a face neighbor')
                actual = [contact for a in boxes[i] for b in boxes[i+1] if (contact := touching(a,b))]
                require(row['contact_to_next'] in actual, 'Attachment lacks recorded positive collision contact')
            supported.add(pos)
    require(supported == set(changes) and report.get('support_columns') == [], 'Sparse attachment support scope differs')
    guards = report[fields['guards']]
    require(len(guards) == spec['expected_guard_probes'], 'Guard probe count differs')
    for guard in guards:
        hit = guard.get('hit') or {}; normal = guard['normal']
        require(hit.get('kind') == 'body_obstruction' and (kind == 'terminal_boundary' or tuple(hit['pos']) in changes)
                and walker.reader.state(*hit['pos']) == hit['state'], 'Measured guard is absent')
        actual = sweep(walker, guard['feet'], (normal[0],normal[2]))
        require(all(actual[k] == guard[k] for k in ('hit','at','position')), 'Guard collision proof is stale')
        if kind == 'terminal_boundary':
            require(guard['first_contact_is_new_guard'] == (tuple(hit['pos']) in changes), 'Guard first-contact attribution differs')
    negatives = report[fields['negative_cases']]
    require(len(negatives) >= spec['minimum_negative_cases'] and all(q.get('rejected') is True for q in negatives),
            'Negative fault rejection evidence failed')
    for key, value in spec.get('required_report_values', {}).items():
        require(report.get(key) == value, 'Required functional evidence differs: '+key)
    for name, state_key, old_key in ((spec['forward_patch'],'after','before'), (spec['inverse_patch'],'before','after')):
        rows = read(package_file(candidate, name))
        if isinstance(rows,dict):
            require(rows.get('requires_exact_before') is True, 'Forward/inverse lacks exact precondition')
            rows = [dict(pos=r['pos'],state=r['after'],expected=r['before']) for r in rows['edits']]
        actual = {tuple(r['pos']):(r['state'],r['expected']) for r in rows}
        require(len(rows) == len(actual) == len(changes) and actual ==
                {p:(r[state_key],r[old_key]) for p,r in changes.items()}, 'Forward/inverse exact scope differs')
    metadata_scope(candidate)
    checked.update(spec=spec, report=report, routes=routes, public_cells=public,
                   guard_probes=len(guards), negative_cases=len(negatives), original_blocks_modified=len(old),
                   captured_devices=len(devices), captured_actors=report['preserved_actors'],
                   scope_kind=kind, scope_metrics=scope_metrics, retained_routes=retained,
                   source_overlay=overlay, dependencies=dependencies)
    return checked


def current_state(args, checked):
    spec = checked['spec']; state = read(args.continuation)
    require(Path(checked['manifest']['world']).resolve() == args.world.resolve(), 'Candidate belongs to another world')
    require(state['latest_installed_batch'] == spec['previous_batch'] == args.batch-1, 'Continuation batch is stale')
    require(Path(state['planning_authority']).resolve() == Path(spec['source_authority']).resolve() == args.authority.resolve(),
            'Current authority differs')
    require(Path(spec['native_snapshot']).resolve() == args.native_snapshot.resolve()
            and spec['expected_native_members'] == args.expected_native_members, 'Native snapshot/count contract differs')
    require(args.expected.resolve() == (args.candidate/'recipe-replay-expected').resolve(), 'Replay expected directory differs')
    require(args.installation.name == 'installation.json', 'Shared installer receipt must be installation.json')
    require(not args.next_authority.exists() and not args.delivery.exists(), 'Never overwrite a published release')
    require(args.next_authority.resolve() != args.authority.resolve(), 'Next authority must be distinct')
    return state


def replay_scope(args):
    return dict(candidate=str(args.candidate.resolve()), world=str(args.world.resolve()), batch=args.batch,
                expected=str(args.expected.resolve()), recipes=str((args.candidate/'after'/DATA).resolve()))


def freeze_files(args, save=False):
    """Freeze complete QC/recipe bytes, not a digest or a selected success flag."""
    candidate = args.candidate; destination = candidate/FREEZE; spec = read(args.config)
    review = Path(spec['review_directory'])
    excluded = {CONTROL, 'delivery-check.json'}
    sources = {'config/config.json':args.config}
    for path in candidate.iterdir():
        if path.is_file() and path.suffix in ('.json','.dat') and path.name not in excluded:
            sources['candidate/'+path.name] = path
    for directory in ('delta','before','after','recipe-replay-expected','preserved-native','identity-before'):
        for path in (candidate/directory).rglob('*'):
            if path.is_file(): sources['candidate/'+path.relative_to(candidate).as_posix()] = path
    for path in review.rglob('*'):
        if path.is_file(): sources['review/'+path.relative_to(review).as_posix()] = path
    # The source reader may visit neighbors beyond the edited cells during
    # collision sweeps; freeze every captured section, not just the 196 cells.
    if spec.get('section_source'):
        source = Path(spec['section_source'])
        for name in ('capture.json','source-check.json'):
            if (source/name).is_file(): sources['source/'+name] = source/name
        for path in (source/'sections').glob('*.npz'):
            sources['source/sections/'+path.name] = path
    if spec.get('checks'):
        sources['config/checks.json'] = Path(spec['checks'])
    for i, path in enumerate(spec.get('external_evidence_files', [])):
        source = Path(path)
        require(source.is_file(), 'External evidence is missing: '+str(source))
        sources[f'external/{i}/{source.name}'] = source
    if spec.get('original_declarations'):
        sources['config/original-declarations.json'] = Path(spec['original_declarations'])
    for i, item in enumerate(spec.get('source_overlays', [])):
        root = Path(item['candidate'])
        for name in ('manifest.json',item['changes_file'],CONTROL,'delivery-check.json','target-devices-before.dat'):
            sources[f'dependency/{i}/'+name] = package_file(root,name)
        for path in (root/'delta').glob('*.npz'):
            sources[f'dependency/{i}/delta/'+path.name] = path
        sources[f'dependency/{i}/installation.json'] = Path(item['installation'])
    if getattr(args,'authority',None):
        for path in args.authority.rglob('*'):
            if path.is_file(): sources['authority/'+path.relative_to(args.authority).as_posix()] = path
    # Keep copies shallow: original recipe/native paths can exceed Windows'
    # legacy path limit when nested below the release directory. The inventory
    # retains every original logical path; comparisons still use exact bytes.
    entries = {rel: f'{i:06d}.bin' for i, rel in enumerate(sorted(sources))}
    inventory = dict(schema='flat-exact-release-freeze-v1', files=entries)
    if save:
        destination.mkdir(exist_ok=False)
        for rel, source in sources.items():
            shutil.copy2(source,destination/entries[rel])
        write(destination/'inventory.json', inventory)
    else:
        require(read(destination/'inventory.json') == inventory, 'Frozen evidence file inventory changed')
        for rel, source in sources.items():
            require(source.read_bytes() == (destination/entries[rel]).read_bytes(), 'Frozen proof or scope changed: '+rel)
    return len(sources)


def prepared_scope(args, checked):
    prepared = read(args.candidate/CONTROL)
    require(prepared.get('schema') == 'section-access-preparation-v1'
            and prepared.get('exact_voxel_views_reviewed') is True
            and prepared.get('replay_scope') == replay_scope(args), 'Missing or stale preparation scope')
    require(checked['manifest'].get('preserve_native_members') is True, 'Native preservation guard is missing')
    freeze_files(args)
    return prepared


def validate_replay(args, checked, prepared):
    require(args.production_log.is_file(), 'Production recipe replay is missing')
    require(args.production_log.stat().st_mtime_ns >= prepared['prepared_time_ns'], 'Production log predates preparation')
    log = args.production_log.read_text('utf-8-sig')
    scope = [json.loads(line[len('SECTION_PATCH_REPLAY_SCOPE '):]) for line in log.splitlines()
             if line.startswith('SECTION_PATCH_REPLAY_SCOPE ')]
    require(scope == [replay_scope(args)], 'Production replay scope is missing or stale')
    matches = re.findall(r'Production surface replay: (\d+) chunks, ([\d,]+) changed cells', log)
    require('BUILD SUCCESSFUL' in log and len(matches) == 1, 'Production replay did not complete unambiguously')
    chunks, cells = (int(v.replace(',','')) for v in matches[0])
    require((chunks,cells) == (len(metadata_scope(args.candidate)),len(checked['changes'])), 'Production replay scope differs')
    return log


def prepare(args):
    checked = validate_offline(args); current_state(args,checked); spec = checked['spec']
    installed_dependencies(checked['dependencies'])
    require(not args.production_log.exists() and not args.installation.parent.exists(), 'Preparation requires fresh replay/install paths')
    require(not (args.candidate/CONTROL).exists() and not (args.candidate/FREEZE).exists(), 'Section release is already prepared')
    check_package(argparse.Namespace(candidate=args.candidate, checks=Path(spec['checks']),
        review=Path(spec['review_directory']), authority=args.authority, models=args.candidate))
    require(not args.native_snapshot.resolve().is_relative_to(args.world.resolve()), 'Native baseline must be an offline snapshot')
    baseline = inventory(args.native_snapshot)
    require(len(baseline) == args.expected_native_members, 'Native baseline count differs')
    with stopped_world(args.world):
        assert_preserved(args.world, baseline)
        installed_dependencies(checked['dependencies'], args.world)
        # Preserve the genuine author report as the legacy installer's adapter;
        # do not invent success fields or reinterpret whole-capture counts.
        shutil.copy2(args.candidate/spec['functional_report'], args.candidate/'functional-check.json')
        manifest = checked['manifest']; manifest['section_source'] = spec['section_source']; manifest['preserve_native_members'] = True
        write(args.candidate/'manifest.json', manifest)
        recipe = prepare_recipes(args.world,args.candidate,spec['changes_file'],checked['source_overlay'])
        shutil.copytree(args.native_snapshot,args.candidate/'preserved-native')
        identity = capture_identity(args.world,args.candidate,args.prior_client)
    write(args.candidate/'publisher-validation.json', dict(scope_kind=checked['scope_kind'],
        scope_metrics=checked['scope_metrics'], scoped_routes=checked['routes'],
        original_routes=checked['retained_routes'], offline_evidence_recomputed=True,
        vehicle_sweep_recomputed=False, runtime_acceptance=False))
    files = freeze_files(args, save=True)
    result = dict(schema='section-access-preparation-v1', errors=[], replay_scope=replay_scope(args),
        changed_cells=len(checked['changes']), native_additions=0, actor_changes=0, device_changes=0,
        captured_devices_broad_scope=checked['captured_devices'], captured_actors_broad_scope=checked['captured_actors'],
        target_scope=recipe, rechecked_bidirectional_routes=len(checked['routes'])+len(checked['retained_routes']),
        verified_bidirectional_routes=len(checked['routes'])+checked['scope_metrics'].get('original_routes_passed',0),
        scope_kind=checked['scope_kind'], scope_metrics=checked['scope_metrics'],
        clear_connected_public_cells_after=checked['public_cells'], attachment_supported_cells=len(checked['changes']),
        guard_probes=checked['guard_probes'], negative_cases=checked['negative_cases'],
        native_members_preserved=len(baseline), identity_files=len(identity), frozen_files=files,
        exact_voxel_views_reviewed=True, prepared_time_ns=time.time_ns(),
        production_recipe_replay_passed=False, installed_delivery_check_passed=False, world_written=False)
    write(args.candidate/CONTROL,result)
    print('Prepared section patch:',result['changed_cells'],'cells;',recipe['updated_recipes'],'recipes.')
    print('SECTION_PATCH_REPLAY_SCOPE '+json.dumps(result['replay_scope'],ensure_ascii=False,separators=(',',':')))


def install(args):
    checked = validate_offline(args, recompute_routes=False); current_state(args,checked)
    prepared = prepared_scope(args,checked); validate_replay(args,checked,prepared)
    require(not prepared['production_recipe_replay_passed'], 'Never install an already consumed preparation')
    from install_hakone_array_patch import install as install_sparse
    with stopped_world(args.world):
        installed_dependencies(checked['dependencies'], args.world)
        install_sparse(argparse.Namespace(world=args.world,candidate=[args.candidate],backup=args.installation.parent,
            workers=2,installed_jar=None,compiled_jar=None,terrain_resource_only=False,terrain_consumer_only=False))
    prepared.update(production_recipe_replay_passed=True, installed_delivery_check_passed=False)
    write(args.candidate/CONTROL,prepared)


def publish_overlay(args, checked):
    """Copy every authority byte, then append one explicitly limited guard overlay."""
    name = checked['spec']['id']+'-guard-overlay.json'
    require(not (args.authority/name).exists(), 'Guard overlay already exists')
    shutil.copytree(args.authority,args.next_authority)
    for path in args.authority.rglob('*'):
        if path.is_file():
            require(path.read_bytes() == (args.next_authority/path.relative_to(args.authority)).read_bytes(),
                    'Authority copy differs: '+str(path))
    overlay = args.next_authority/name
    validation=read(args.candidate/'publisher-validation.json')
    published=dict(schema='installed-section-access-overlay-v2',previous=str(args.authority),
        scope_kind=checked['scope_kind'],scope_metrics=validation['scope_metrics'],
        candidate=str(args.candidate),installation=str(args.installation),batch=args.batch,
        changes=checked['rows'],attachment_supports=checked['report'][checked['spec']['evidence_fields']['attachment_supports']],
        verified_bidirectional_routes=validation['scoped_routes'],original_routes_before_and_after=validation['original_routes'],
        guard_probes=checked['guard_probes'],
        retained_public_cells=checked['public_cells'],all_previous_authority_files_exact=True,
        scalar_network_preserved=True,existing_3d_nodes_and_routes_preserved=True,new_station_count=0,
        static_section_geometry_only=True,live_acceptance_complete=False,through_service_complete=False,
        existing_station_final_review_complete=False,stage_two_complete=False,world_written=True)
    if checked['scope_kind']=='terminal_boundary':
        published['complete_floor_declarations']=read(args.candidate/checked['spec']['complete_declarations'])
        published['exact_floor_declaration_changes']=read(args.candidate/checked['spec']['declaration_delta'])
    write(overlay,published)
    return overlay


def record(args):
    checked = validate_offline(args,recompute_routes=False)
    before_state = args.continuation.read_bytes(); state = current_state(args,checked)
    require(json.loads(before_state) == state, 'Continuation changed before record')
    prepared = prepared_scope(args,checked); validate_replay(args,checked,prepared)
    require(prepared.get('production_recipe_replay_passed') is True and
            prepared.get('installed_delivery_check_passed') is False, 'Installation/replay is not ready for one-time record')
    receipt = read(args.installation)
    require([Path(p).resolve() for p in receipt.get('candidates',[])] == [args.candidate.resolve()], 'Receipt candidate scope differs')
    with stopped_world(args.world):
        installed_dependencies(checked['dependencies'], args.world)
        installed = verify_delivery(args.world,args.candidate,args.installation,args.production_log)
        current_devices, cells = actual_cells(args.world,checked,after=True)
        require_nbt_equal(nbtlib.load(args.candidate/'target-devices-before.dat'),current_devices,'target-devices')
    require(installed['new_native_members_exact'] == installed['device_payloads'] == 0
            and installed['old_native_members_exact'] == args.expected_native_members, 'Installed preservation scope differs')
    require(args.continuation.read_bytes() == before_state, 'Continuation changed during verification')
    installed.update(actual_changed_cells_readback=cells,
        original_target_device_payloads_exact=len(current_devices['Devices']))
    write(args.candidate/'delivery-check.json',installed)
    overlay = publish_overlay(args,checked)
    report = dict(batch=args.batch,station=checked['spec']['label'],candidate=str(args.candidate),
        installation=str(args.installation),authority=str(args.next_authority),terrain_field=str(args.terrain),
        guard_overlay=str(overlay),changed_cells=cells,recipe_chunks=installed['recipe_chunks'],
        rechecked_bidirectional_routes=len(checked['routes'])+len(checked['retained_routes']),
        verified_bidirectional_routes=prepared['verified_bidirectional_routes'],guard_probes_passed=checked['guard_probes'],
        scope_kind=checked['scope_kind'],scope_metrics=prepared['scope_metrics'],
        attachment_supported_cells=cells,negative_cases_passed=checked['negative_cases'],
        clear_connected_public_cells_after=checked['public_cells'],
        high_edges_before=checked['spec'].get('expected_high_edges_before'),high_edges_after=checked['spec'].get('expected_high_edges_after'),
        original_blocks_modified=checked['original_blocks_modified'],new_native_members=0,new_station_count=0,
        old_native_members_exact=installed['old_native_members_exact'],device_payload_changes=0,actor_changes=0,
        original_target_device_payloads_exact=len(current_devices['Devices']),
        broad_capture_device_count=checked['captured_devices'],broad_capture_actor_count=checked['captured_actors'],
        identity_files_exact=installed['identity_files_exact'],whole_client_jar_exact=installed['whole_client_jar_exact'],
        all_previous_authority_files_exact=True,production_replay_passed=True,world_written=True,client_jar_written=False,
        current_collision_and_open_door_runtime_pending=True,through_service_complete=False,
        existing_station_final_review_complete=False,stage_two_complete=False,
        preserved_pending=checked['spec']['preserved_pending'])
    write(args.delivery,report)
    state.update(latest_installed_batch=args.batch,planning_authority=str(args.next_authority),
                 current_work=checked['spec']['continuation_work'])
    pending = state.setdefault('pending_map_cache_releases',[])
    if str(args.installation.parent) not in pending: pending.append(str(args.installation.parent))
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=args.continuation.parent,
                                     prefix='.section-progress-',suffix='.json',delete=False) as output:
        json.dump(state,output,ensure_ascii=False,indent=2); temporary = Path(output.name)
    try:
        require(args.continuation.read_bytes() == before_state, 'Continuation changed before publication')
        os.replace(temporary,args.continuation)
    finally:
        if temporary.exists(): temporary.unlink()
    prepared['installed_delivery_check_passed'] = True; write(args.candidate/CONTROL,prepared)
    print('Recorded section patch batch',args.batch,':',cells,'cells; final/live review remains pending.')


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=('prepare','install','record'))
    parser.add_argument('--batch',type=int,required=True)
    parser.add_argument('--expected-native-members',type=int,required=True)
    for name in ('config','candidate','world','authority','next-authority','native-snapshot','expected',
                 'installation','production-log','delivery','continuation','terrain','prior-client'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args(); globals()[args.mode](args)


if __name__ == '__main__':
    main()
