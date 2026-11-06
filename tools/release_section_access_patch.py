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
import subprocess
import sys
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


def validate_offline(args, recompute_routes=True):
    """Validate actual saved evidence and source cells without opening the world."""
    candidate = Path(args.candidate); spec = read(args.config)
    require(spec.get('schema') == 'section-access-patch-release-v1', 'Unknown section release configuration')
    require(re.fullmatch(r'[a-z0-9][a-z0-9_-]*', spec['id']) is not None, 'Invalid patch identifier')
    require(0 < spec['maximum_step'] <= .5, 'Half-step route bound must be retained')
    package_file(candidate, spec['changes_file']); package_file(candidate, spec['functional_report'])
    checked = validate_delta(candidate, spec['changes_file'], spec['section_source'])
    manifest = checked['manifest']; changes = checked['changes']
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
    require(review_report.get('errors') == [] and review_report['stations'] == report['stations'], 'Independent station proof differs')
    fields = spec['evidence_fields']; phases = {p['phase']:p for p in report[fields['phases']]}
    require(set(phases) == {'before','after'} and len(report[fields['phases']]) == 2, 'Exact before/after phase proof is required')
    goals = {g['key']:g for g in phases['after']['goals']}
    before = {g['key']:g for g in phases['before']['goals']}
    require(len(goals) == len(phases['after']['goals']) and set(goals) == set(before)
            and set(spec['required_goals']) == set(goals), 'Required route scope differs')
    from repair_declared_platform_guards import make_walker, touching, sweep
    from review_underground_station_evidence import strict_walk
    shapes = read(package_file(candidate, spec['collision_shapes']))
    walker = make_walker(Path(spec['section_source']), shapes, {p:q['after'] for p,q in changes.items()})
    routes = []
    for key, route in goals.items():
        require(route.get('reachable') is True and route.get('strict_pass') is True and route.get('path')
                and route['path'] == before[key]['path'], 'Original route was moved or became unreachable')
        routes.append(dict(key=key, path=route['path'], forward=route['forward'], reverse=route['reverse']))
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
        require(hit.get('kind') == 'body_obstruction' and tuple(hit['pos']) in changes
                and walker.reader.state(*hit['pos']) == hit['state'], 'Measured guard is absent')
        actual = sweep(walker, guard['feet'], (normal[0],normal[2]))
        require(all(actual[k] == guard[k] for k in ('hit','at','position')), 'Guard collision proof is stale')
    negatives = report[fields['negative_cases']]
    require(len(negatives) >= spec['minimum_negative_cases'] and all(q.get('rejected') is True for q in negatives),
            'Negative fault rejection evidence failed')
    for key, value in spec.get('required_report_values', {}).items():
        require(report.get(key) == value, 'Required functional evidence differs: '+key)
    for name, state_key, old_key in ((spec['forward_patch'],'after','before'), (spec['inverse_patch'],'before','after')):
        rows = read(package_file(candidate, name))
        actual = {tuple(r['pos']):(r['state'],r['expected']) for r in rows}
        require(len(rows) == len(actual) == len(changes) and actual ==
                {p:(r[state_key],r[old_key]) for p,r in changes.items()}, 'Forward/inverse exact scope differs')
    metadata_scope(candidate)
    checked.update(spec=spec, report=report, routes=routes, public_cells=public,
                   guard_probes=len(guards), negative_cases=len(negatives), original_blocks_modified=len(old),
                   captured_devices=len(devices), captured_actors=report['preserved_actors'])
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
    require(not args.production_log.exists() and not args.installation.parent.exists(), 'Preparation requires fresh replay/install paths')
    require(not (args.candidate/CONTROL).exists() and not (args.candidate/FREEZE).exists(), 'Section release is already prepared')
    check_package(argparse.Namespace(candidate=args.candidate, checks=Path(spec['checks']),
        review=Path(spec['review_directory']), authority=args.authority, models=args.candidate))
    require(not args.native_snapshot.resolve().is_relative_to(args.world.resolve()), 'Native baseline must be an offline snapshot')
    baseline = inventory(args.native_snapshot)
    require(len(baseline) == args.expected_native_members, 'Native baseline count differs')
    with stopped_world(args.world):
        assert_preserved(args.world, baseline)
        # Preserve the genuine author report as the legacy installer's adapter;
        # do not invent success fields or reinterpret whole-capture counts.
        shutil.copy2(args.candidate/spec['functional_report'], args.candidate/'functional-check.json')
        manifest = checked['manifest']; manifest['section_source'] = spec['section_source']; manifest['preserve_native_members'] = True
        write(args.candidate/'manifest.json', manifest)
        recipe = prepare_recipes(args.world,args.candidate,spec['changes_file'])
        shutil.copytree(args.native_snapshot,args.candidate/'preserved-native')
        identity = capture_identity(args.world,args.candidate,args.prior_client)
    files = freeze_files(args, save=True)
    result = dict(schema='section-access-preparation-v1', errors=[], replay_scope=replay_scope(args),
        changed_cells=len(checked['changes']), native_additions=0, actor_changes=0, device_changes=0,
        captured_devices_broad_scope=checked['captured_devices'], captured_actors_broad_scope=checked['captured_actors'],
        target_scope=recipe, verified_bidirectional_routes=len(checked['routes']),
        preserved_public_cells=checked['public_cells'], attachment_supported_cells=len(checked['changes']),
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
    subprocess.run([sys.executable,str(Path(__file__).with_name('install_hakone_array_patch.py')),
        '--world',str(args.world),'--candidate',str(args.candidate),'--backup',str(args.installation.parent),'--workers','2'],check=True)
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
    write(overlay,dict(schema='installed-section-guard-overlay-v1',previous=str(args.authority),
        candidate=str(args.candidate),installation=str(args.installation),batch=args.batch,
        changes=checked['rows'],attachment_supports=checked['report'][checked['spec']['evidence_fields']['attachment_supports']],
        verified_bidirectional_routes=checked['routes'],guard_probes=checked['guard_probes'],
        retained_public_cells=checked['public_cells'],all_previous_authority_files_exact=True,
        scalar_network_preserved=True,existing_3d_nodes_and_routes_preserved=True,new_station_count=0,
        static_guard_geometry_only=True,live_acceptance_complete=False,through_service_complete=False,
        existing_station_final_review_complete=False,stage_two_complete=False,world_written=True))
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
        rechecked_bidirectional_routes=len(checked['routes']),guard_probes_passed=checked['guard_probes'],
        attachment_supported_cells=cells,negative_cases_passed=checked['negative_cases'],
        original_public_cells_preserved=checked['public_cells'],
        high_edges_before=checked['spec']['expected_high_edges_before'],high_edges_after=checked['spec']['expected_high_edges_after'],
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
