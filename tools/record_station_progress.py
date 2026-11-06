"""Advance a station worklist from installed offline evidence, never world IO.

--out is a new directory containing worklist.json. A delivery can describe one
station or a station set; repeat --delivery for several deliveries. The newest
delivery must match continuation's current batch
and planning authority. --native-snapshot is a captured mtr directory, with
projectseele/geofront below it. Existing station reviews and operation claims
are preserved; installing a station does not complete either of those scopes.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import tempfile

from audit_hq_mtr_protection_r52 import Reader


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


def offline_path(path, world):
    path = Path(path).resolve()
    require(not path.is_relative_to(world), 'Only captured offline files are allowed')
    return path


def read_offline(path, world):
    return read(offline_path(path, world))


def native_id(value):
    return int(value) % (1 << 64)


def endpoints(record):
    return frozenset(tuple(record[key][axis] for axis in ('x', 'y', 'z'))
                     for key in ('position1', 'position2'))


def station_set_mapping(names, design, layout, proof, decoded):
    """Bind each declared station to its saved station and platform identities."""
    stations = {s['name']: s for s in decoded['stations']}
    layout_by_name = {s['name']: s for s in layout['stations']}
    designs = {s['name']: s for s in design['stations']}
    planned_stations = {s['name']: s for s in proof['input_plan']['stations']}
    require(len(planned_stations) == len(proof['input_plan']['stations']) == len(names)
            and set(planned_stations) == set(names), 'Native input plan station names disagree')
    require(len(stations) == len(decoded['stations']) == len(names)
            and set(stations) == set(names), 'Native station set names disagree')
    require(proof.get('existing_platform_station_membership_exact') is True
            and proof.get('preserved_source_member_bytes_exact') is True
            and proof.get('delivery_only_new_members') is True, 'Station set native preservation proof is incomplete')
    station_proofs = {native_id(s['station_id']): s for s in proof['stations']}
    require(len(station_proofs) == len(proof['stations']) == len(stations)
            and set(station_proofs) == {native_id(s['id']) for s in stations.values()},
            'Station proof identities do not match saved stations')
    platforms = {native_id(p['id']): p for p in decoded['platforms']}
    require(len(platforms) == len(decoded['platforms']) == len(proof['platforms'])
            and {native_id(p['platform_id']) for p in proof['platforms']} == set(platforms),
            'Platform proof identities do not match saved platforms')
    require(len(decoded['rails']) == len(proof['rails']) == len(proof['input_plan']['rails']),
            'Station set native rail scope disagrees')
    expected_rails = [frozenset((tuple(r['from']), tuple(r['to']))) for r in proof['input_plan']['rails']]
    require(len(set(expected_rails)) == len(expected_rails)
            and set(expected_rails) == {endpoints(r) for r in decoded['rails']},
            'Saved rail endpoints differ from the station set proof')
    mappings = []
    for name in names:
        station, declared = stations[name], layout_by_name[name]
        station_id = native_id(station['id'])
        planned = planned_stations[name]
        require(station_proofs[station_id]['input_station_id'] == planned['id'],
                'Native station identity is assigned to the wrong layout station')
        assigned = [p for p in proof['platforms'] if p['station'] == name]
        require(len(assigned) == len(declared['platform_lengths']) > 0,
                'Station platform count differs from release layout')
        lengths = sorted(p['platform_length'] for p in assigned)
        require(all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in lengths)
                and all(abs(a-b) < 1e-6 for a,b in zip(lengths, sorted(declared['platform_lengths'])))
                and min(lengths) >= declared['planned_consist_length'], 'Station platform lengths disagree')
        owned = []
        for p in assigned:
            require(native_id(p['station_id']) == station_id and p['input_station_id'] == planned['id']
                    and p['input_rail_id'] in {q['rail_id'] for q in planned['platforms']},
                    'Platform proof assigns a saved platform to the wrong station')
            actual = platforms[native_id(p['platform_id'])]
            require(actual['name'] == p['platform_name'], 'Native platform name disagrees')
            wanted = p['native_rail_endpoints']
            expected = frozenset((tuple(wanted['from']), tuple(wanted['to'])))
            require(endpoints(actual) == expected and expected in expected_rails,
                    'Platform proof endpoints differ from saved platform or rail')
            # Current set designs provide the station's platform rail directly.
            # This binds ownership independently of the proof's name labels.
            designed = designs[name]['native_rail']
            require(p['input_rail_id'] == designs[name]['rail_id']
                    and expected == frozenset((tuple(designed['from']), tuple(designed['to']))),
                    'Platform identity is assigned to another station design rail')
            midpoint = [(actual['position1'][k] + actual['position2'][k])/2 for k in ('x', 'y', 'z')]
            require(all(min(station['position1'][k], station['position2'][k]) <= midpoint[i]
                        <= max(station['position1'][k], station['position2'][k]) for i,k in enumerate(('x','y','z'))),
                    'Platform midpoint is outside its saved native station')
            owned.append(str(actual['id']))
        mappings.append(dict(name=name, station_native_id=str(station['id']), platform_native_ids=owned))
    require(sum(len(r['platform_native_ids']) for r in mappings) == len(platforms),
            'Some saved platforms have no station in the delivery')
    return mappings


def installed_station(delivery_path, snapshot, world):
    delivery_path = offline_path(delivery_path, world)
    delivery = read(delivery_path)
    require(delivery.get('world_written') is True, 'Delivery does not describe an installation')
    require(delivery.get('production_replay_passed') is True, 'Delivery has no successful production replay')
    candidate = offline_path(delivery['candidate'], world)
    receipt_path = offline_path(delivery['installation'], world)
    receipt = read(receipt_path)
    require(receipt.get('status') == 'installed' and receipt.get('changed_section_readback') is True
            and receipt.get('existing_native_members_exact') is True, 'Installation readback is incomplete')
    require(any(same_path(candidate, p) for p in receipt.get('candidates', [])),
            'Receipt does not install the delivery candidate')
    manifest = read_offline(candidate / 'manifest.json', world)
    design = read_offline(candidate / 'station-design.json', world)
    is_set = 'stations' in delivery
    layout = None
    if is_set:
        names = delivery['stations']
        require(isinstance(names, list) and names and all(isinstance(n, str) and n for n in names)
                and len(names) == len(set(names)), 'Delivery station set names must be unique')
        layout = read_offline(candidate / 'release-layout.json', world)
        require(layout.get('schema') == 'station-release-layout-v1', 'Unknown station release layout')
        if 'stations' not in design:
            plan=read_offline(candidate/'native-station-plan.json',world)
            station_name=design.get('station',design.get('name'))
            require(len(names)==1 and station_name==names[0] and len(plan['rails'])==1,
                    'A single-station design must bind exactly one declared platform')
            rail=plan['rails'][0]
            design=dict(design,stations=[dict(name=station_name,rail_id=rail['id'],native_rail=rail)])
        require(len(design['stations']) == len(layout['stations']) == len(names)
                and {s['name'] for s in design['stations']} == {s['name'] for s in layout['stations']} == set(names),
                'Delivery, station design and release layout names disagree')
    else:
        require(delivery['station'] == design['station'], 'Delivery and station design names disagree')
        names = [design['station']]
    require(receipt['cells'] == manifest['cells'] == delivery['changed_cells'], 'Installed cell counts disagree')
    require(receipt.get('metadata_readback') == receipt.get('metadata_files')
            and isinstance(receipt.get('metadata_files'), int), 'Metadata readback is incomplete')
    release_path = candidate / 'station-release-check.json'
    release = read_offline(release_path, world)
    for key in ('production_recipe_replay_passed', 'native_station_registration_verified',
                'negative_fault_checks_passed', 'no_new_floating_components', 'current_native_source_exact'):
        require(release.get(key) is True, 'Station release evidence is incomplete: ' + key)
    evidence = [str(delivery_path), str(receipt_path), str(release_path)]
    delivered_check = candidate / 'delivery-check.json'
    require(not is_set or delivered_check.is_file(), 'Station set requires the common installed delivery check')
    if delivered_check.exists():
        checked = read_offline(delivered_check, world)
        require(checked.get('passed') is True and checked.get('production_replay_passed') is True,
                'Independent installed delivery check did not pass')
        require(checked['changed_cells'] == receipt['cells'], 'Independent delivery count disagrees')
        if is_set:
            require(checked.get('old_native_members_exact') == delivery['old_native_members_exact']
                    and checked.get('new_native_members_exact') == receipt['native_additions'] == delivery['new_native_members']
                    and checked.get('identity_files_exact') == delivery['identity_files_exact']
                    and checked.get('whole_client_jar_exact') is True, 'Common delivery preservation evidence disagrees')
        evidence.append(str(delivered_check))

    # Prefer the registered checker; layered station designs also have an
    # independent offline pedestrian proof and the separate native proof below.
    walk_path = candidate / 'station-independent-check.json'
    if is_set:
        walk_path = candidate / 'release-layout-check.json'
        walk = read_offline(walk_path, world)
        total, reachable = walk.get('nodes'), walk.get('reachable_nodes')
        require(total == len(layout['station_multi_level_nodes']) == delivery['public_surfaces']
                and walk.get('ground_columns') == len(layout['ground_access_columns']) == delivery['ground_public_columns'],
                'Station set walking overlay counts disagree')
        functional_path = candidate / 'functional-check.json'
        functional = read_offline(functional_path, world)
        require(functional.get('errors') == [] and functional.get('native_station_registration_verified') is True
                and functional.get('overlay_proof') == 'release-layout-check.json', 'Station set functional evidence is incomplete')
        structural_path = offline_path(functional['evidence'], world)
        structural = read(structural_path)
        if structural.get('schema')=='strict-station-layout-v1':
            underlying_path=offline_path(structural['underlying_structural_evidence'],world)
            require(same_path(underlying_path,candidate/'offline-verification.json'), 'Strict sweep refers to another candidate')
            underlying=read(underlying_path)
            require(structural.get('errors')==[] and structural.get('public_nodes')==structural.get('reachable_nodes')==total
                    and structural.get('strict_sweep_directions',0)>0 and structural.get('maximum_measured_step',1)<=.50001,
                    'Strict all-surface passenger sweep failed')
            require(underlying.get('errors')==[] and underlying.get('cells')==receipt['cells']
                    and underlying.get('public_nodes')==underlying.get('reachable_public_nodes')==total
                    and not underlying.get('new_floating_solids',True)and not underlying.get('newly_detached_retained_cells',True)
                    and not underlying.get('unguarded_public_drop_edges',True)
                    and all(p.get('rejected')is True for p in underlying['negative_cases']),
                    'Generic station structure evidence failed')
            evidence.append(str(underlying_path))
        else:
            require(structural.get('errors') == [] and structural.get('offline_candidate_verified') is True
                    and structural.get('exact_saved_delta_matches') is True and structural.get('cells') == receipt['cells']
                    and not structural.get('new_floating_solids', True)
                    and not structural.get('newly_detached_retained_cells', True), 'Station set structural evidence failed')
            reached = structural.get('reachable_platforms', [])
            require(len(reached) == len(names) and {p['station'] for p in reached} == set(names)
                    and all(p.get('unreachable') == [] and p.get('reachable_platform_cells', 0) > 0 for p in reached),
                    'Station set lacks per-station passenger evidence')
        require(receipt.get('changed_device_nbt_readback') == layout['device_changes']
                and receipt['native_additions'] == layout['native_additions'], 'Station set installation scope disagrees')
        evidence.extend((str(candidate / 'release-layout.json'), str(functional_path), str(structural_path)))
    elif walk_path.exists():
        walk = read_offline(walk_path, world)
        require(walk.get('validation_mode', 'registered') == 'registered'
                and walk.get('native_station_registration_verified') is True,
                'A preflight report is not registered station evidence')
        total, reachable = walk.get('public_columns'), walk.get('reachable_public_columns')
    else:
        walk_path = candidate / 'offline-verification.json'
        walk = read_offline(walk_path, world)
        total = walk.get('nodes', walk.get('public_nodes'))
        reachable = walk.get('reachable_nodes')
    require(walk.get('errors') == [] and isinstance(total, int) and total > 0 and total == reachable,
            'Passenger access geometry is not verified')
    evidence.append(str(walk_path))

    proof_path = candidate / 'native-station/native-station-proof.json'
    proof = read_offline(proof_path, world)
    require(proof.get('existing_loaded_objects_exact') is True, 'Native preservation proof is incomplete')
    members = proof['members']
    require(len(set(members)) == len(members) and set(members) == set(manifest.get('native_additions', [])),
            'Native member lists disagree')
    require(len(members) == receipt['native_additions'] == delivery['new_native_members'],
            'Native addition counts disagree')
    decoded = {'stations': [], 'platforms': [], 'rails': []}
    for name in members:
        member = Path(name)
        require(not member.is_absolute() and '..' not in member.parts
                and len(member.parts) >= 5 and member.parts[:3] == ('mtr', 'projectseele', 'geofront')
                and member.parts[3] in decoded, 'Unexpected station native member path')
        expected = offline_path(candidate / 'after' / member, world)
        captured = offline_path(snapshot / member.relative_to('mtr'), world)
        require(captured.is_file() and expected.read_bytes() == captured.read_bytes(),
                'Native snapshot does not contain the installed station additions')
        decoded[member.parts[3]].append(Reader(captured.read_bytes()).read())
    if is_set:
        mappings = station_set_mapping(names, design, layout, proof, decoded)
    else:
        require(len(decoded['stations']) == 1 and len(decoded['platforms']) >= 1
                and len(decoded['rails']) == len(decoded['platforms']), 'Unexpected station registration scope')
        require(decoded['stations'][0]['name'] == design['station'], 'Native station name disagrees')
        mappings = [dict(name=design['station'], station_native_id=str(decoded['stations'][0]['id']),
                         platform_native_ids=[str(p['id']) for p in decoded['platforms']])]
    evidence.append(str(proof_path))
    return [dict(**mapping, batch=delivery['batch'], delivery=str(delivery_path),
                 candidate=str(candidate), installation=str(receipt_path), authority=delivery['authority'],
                 evidence=evidence, delivery_data=delivery) for mapping in mappings]


def prepare(args):
    original = args.continuation.read_bytes()
    state = json.loads(original.decode('utf8'))
    world = Path(state['world']).resolve()
    for path in (args.continuation, args.prior_worklist, args.out, args.native_snapshot):
        offline_path(path, world)
    require(not args.out.exists(), '--out must be a new worklist version directory')
    require(same_path(args.prior_worklist, state['station_construction_worklist']),
            'Prior worklist is not continuation\'s current station worklist')
    work = read(args.prior_worklist)
    require(work['latest_installed_batch'] <= state['latest_installed_batch'], 'Prior worklist is newer than continuation')
    native_root = offline_path(args.native_snapshot / 'projectseele/geofront', world)
    require(native_root.is_dir(), 'Native snapshot must be an offline mtr root')
    inventory = {}
    for kind in ('stations', 'platforms', 'routes', 'rails'):
        directory = offline_path(native_root / kind, world)
        require(directory.is_dir(), 'Native snapshot is incomplete: ' + kind)
        inventory[kind] = sum(p.is_file() for p in directory.rglob('*'))
    records = [row for path in args.delivery for row in installed_station(path, args.native_snapshot, world)]
    require(len({r['name'] for r in records}) == len(records), 'Supply one delivery per station')
    latest = max(records, key=lambda r: r['batch'])
    require(latest['batch'] == state['latest_installed_batch'], 'Newest delivery does not match current installed batch')
    require(same_path(latest['authority'], state['planning_authority']), 'Newest delivery is not the current authority')
    # The latest captured snapshot must include the complete preserved baseline,
    # not only the handful of new objects used to identify the updated station.
    baseline = offline_path(Path(latest['candidate']) / 'preserved-native', world)
    require(baseline.is_dir(), 'Latest station has no preserved native baseline')
    preserved = {p.relative_to(baseline): p for p in baseline.rglob('*') if p.is_file()}
    additions = read_offline(Path(latest['candidate']) / 'manifest.json', world)['native_additions']
    added = {Path(p).relative_to('mtr') for p in additions}
    captured = {p.relative_to(args.native_snapshot): p for p in args.native_snapshot.rglob('*') if p.is_file()}
    require(not set(preserved) & added and set(captured) == set(preserved) | added,
            'Native snapshot is not the complete current installed member set')
    require(len(preserved) == latest['delivery_data']['old_native_members_exact'],
            'Preserved native count differs from the latest delivery')
    for name, expected in preserved.items():
        require(offline_path(expected, world).read_bytes() == offline_path(captured[name], world).read_bytes(),
                'Current native snapshot changed a preserved member')
    result = copy.deepcopy(work)
    rows = result['geographic_stations']
    for record in records:
        matches = [row for row in rows if row['name'] == record['name']]
        require(len(matches) == 1, 'Station has no unique geographic worklist entry: ' + record['name'])
        row = matches[0]
        if row.get('delivery'):
            prior_delivery = read_offline(row['delivery'], world)
            require(prior_delivery['batch'] <= record['batch'], 'Cannot replace a station with an older delivery')
        row.update(physical_structure_installed=True, native_registration_installed=True,
                   passenger_access_geometry_verified=True, structure_status='installed',
                   status=f"Installed batch {record['batch']}; static structure and access verified; final/live acceptance remains separate",
                   delivery=record['delivery'], candidate=record['candidate'], installation=record['installation'],
                   installed_batch=record['batch'], station_native_id=record['station_native_id'],
                   platform_native_ids=record['platform_native_ids'], progress_evidence=record['evidence'])
        if len(record['platform_native_ids']) == 1:
            row['platform_native_id'] = record['platform_native_ids'][0]
        elif 'platform_native_id' in row:
            del row['platform_native_id']
        row.setdefault('through_service_complete', False)
    installed = sum(all(row.get(k) is True for k in ('physical_structure_installed',
                    'native_registration_installed', 'passenger_access_geometry_verified')) for row in rows)
    claimed_count = latest['delivery_data'].get('new_geographic_stations_installed')
    if claimed_count is not None:
        require(installed == claimed_count, 'Worklist and latest delivery installation totals disagree; supply missing deliveries')
    remaining_reviews = sum(row.get('station_complete') is not True for row in result['existing_stations'])
    result.update(latest_installed_batch=state['latest_installed_batch'], planning_authority=state['planning_authority'],
                  current_native_snapshot=str(args.native_snapshot.resolve()), native_engine_inventory=inventory,
                  new_structures_installed=installed, new_structures_remaining=len(rows)-installed,
                  existing_station_final_reviews_remaining=remaining_reviews,
                  previous_worklist=str(args.prior_worklist.resolve()),
                  station_progress_deliveries=list(dict.fromkeys(r['delivery'] for r in records)),
                  actual_world_modified_by_this_report=False)
    new_state = copy.deepcopy(state)
    new_state['station_construction_worklist'] = str((args.out / 'worklist.json').resolve())
    # Keep the older alias in sync where present, without changing other state.
    if 'station_worklist' in new_state:
        new_state['station_worklist'] = new_state['station_construction_worklist']
    new_state['current_native_snapshot'] = str(args.native_snapshot.resolve())
    summary = dict(batch=state['latest_installed_batch'], updated_stations=[r['name'] for r in records],
                   new_structures_installed=installed, new_structures_remaining=len(rows)-installed,
                   existing_station_final_reviews_remaining=remaining_reviews, native_inventory=inventory,
                   worklist=new_state['station_construction_worklist'], world_written=False,
                   operation_completion_inferred=False)
    return original, result, new_state, summary


def record(args):
    original, work, state, summary = prepare(args)
    require(args.continuation.read_bytes() == original, 'Continuation changed during verification; retry with current inputs')
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'worklist.json').write_text(json.dumps(work, ensure_ascii=False, indent=2), 'utf8')
    (args.out / 'progress-record.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), 'utf8')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf8', prefix='.station-progress-', suffix='.json',
                                         dir=args.continuation.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(state, output, ensure_ascii=False, indent=2)
        require(args.continuation.read_bytes() == original, 'Continuation changed before publication; new worklist was left unlinked')
        os.replace(temporary, args.continuation)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--delivery', type=Path, action='append', required=True, help='Repeat for multiple stations')
    for name in ('prior-worklist', 'out', 'continuation', 'native-snapshot'):
        parser.add_argument('--' + name, type=Path, required=True)
    record(parser.parse_args())
