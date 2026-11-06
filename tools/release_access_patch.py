"""Release a bounded access patch using JSON scope and shared delivery checks.

All three publishing modes require an explicit --world. Importing this module
or calling validate_offline does not open a world. Native transport and client
changes are forbidden. Walking routes retain their exact three-dimensional
coordinates; scalar ground access is changed only by an explicit column list.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import nbtlib
import numpy as np

from author_hakone_lakefront import Editor
from install_r53_carrier_trays import stopped_world
from native_transit_additions import inventory, assert_preserved
from prepare_hakone_network_recipes import parallel_recipes
from map_pipeline.delivery_check import read, write, capture_identity, verify_delivery
from map_pipeline.station_release_checks import verify as check_package
from map_pipeline.verify_corridors import write_replay_expected


SURFACES = Path('dimensions/projectseele/geofront/data/city_rigid_generation_r45/surface')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def package_file(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    require(path.is_relative_to(root) and path.is_file(), 'Missing or escaping package file: ' + name)
    return path


def require_world(args):
    require(getattr(args, 'world', None) is not None, 'An explicit --world is required for publishing modes')


def metadata_scope(candidate):
    files = []
    for path in (candidate / 'after').rglob('*'):
        if path.is_file():
            rel = path.relative_to(candidate / 'after')
            require(rel.parent == SURFACES and rel.suffix == '.dat',
                    'Access patches may publish only surface recipes, never native/client files')
            files.append(path)
    return files


def ground_replacements(candidate, authority, spec, editor, nodes):
    """Validate exact old/new column declarations against current saved voxels."""
    if spec['ground_network']['mode']!='explicit_replacements':return None
    patch=read(package_file(candidate,spec['ground_network']['replacements_file']))
    require(patch.get('schema')=='access-ground-replacements-v1'
            and Path(patch['source_authority']).resolve()==authority.resolve()
            and patch['expected_previous_batch']==spec['previous_batch']
            and patch.get('preserve_all_other_fields')is True,'Ground replacement authority differs')
    rows=patch['columns'];require(len(rows)==patch['unique_columns']>0,'Ground replacement scope differs')
    with np.load(authority/'network.npz')as f:network={k:f[k]for k in f.files}
    x0,z0,x1,z1=map(int,network['bounds']);seen=set();changed=0
    for row in rows:
        x,z=row['column'];require(type(x)is int and type(z)is int,'Ground replacement coordinates must be integers')
        require((x,z)not in seen and x0<=x<=x1 and z0<=z<=z1,'Repeated or outside ground replacement');seen.add((x,z))
        before,after=row['before'],row['after']
        for state in(before,after):
            require(set(state)=={'walk','road','grade2'}and type(state['walk'])is bool
                    and type(state['road'])is bool and type(state['grade2'])is int,'Invalid ground replacement state')
        actual={k:bool(network[k][z-z0,x-x0])if k!='grade2'else int(network[k][z-z0,x-x0])for k in before}
        require(actual==before,'Ground replacement precondition changed')
        require(after['road']==before['road']and(not before['road']or after==before),'Access replacement may not change existing roads')
        require(row['changed']==(before!=after),'Ground replacement change count is inconsistent')
        changed+=before!=after
        if after['walk']:
            require((x,after['grade2'],z)in nodes and {g for px,g,pz in nodes if(px,pz)==(x,z)}=={after['grade2']},
                    'Ground replacement lacks a unique measured public surface')
        elif before['walk']:
            require((x,before['grade2'],z)not in nodes,'Ground retirement would hide a retained public route')
        require(row.get('source_witnesses'),'Ground replacement has no measured voxel evidence')
        for witness in row['source_witnesses']:
            pos=witness['pos'];require(pos[0]==x and pos[2]==z,'Ground witness belongs to another column')
            require(editor.state(*pos,True)==witness['source_state']and editor.state(*pos)==witness['candidate_state'],
                    'Ground replacement witness differs from exact source/candidate')
    require(changed==patch['changed_columns'],'Ground replacement count differs')
    return patch


def validate_offline(args):
    """Read saved candidate files and evidence only; return exact route overlay."""
    candidate = Path(args.candidate)
    spec = read(args.config)
    require(spec.get('schema') == 'access-patch-release-v1', 'Unknown access release configuration')
    require(re.fullmatch(r'[a-z0-9][a-z0-9_-]*', spec['id']) is not None, 'Invalid access patch identifier')
    require(0 < spec['maximum_step'] <= .5, 'Access validation must retain the half-step bound')
    manifest = read(candidate / 'manifest.json')
    if getattr(args, 'world', None) is not None:
        require(Path(manifest['world']).resolve() == args.world.resolve(), 'Candidate belongs to another world')
    require(not manifest.get('native_additions') and not manifest.get('native_changes')
            and not manifest.get('native_members') and not manifest.get('native_geometry_patch')
            and not manifest.get('native_geometry_migrations') and not manifest.get('actor_changes')
            and not manifest.get('entity_moves') and not manifest.get('json_metadata'),
            'Access patches do not authorize native or actor changes')
    changes = read(package_file(candidate, spec['changes_file']))
    expected = {tuple(row['pos']): row for row in changes}
    require(len(expected) == len(changes) == manifest['cells'] == spec['expected_changed_cells'],
            'Access patch change counts disagree')
    approved_old = {tuple(row['pos']): row for row in spec['approved_existing_changes']}
    require(len(approved_old) == len(spec['approved_existing_changes']), 'Repeated existing-cell authorization')
    devices = nbtlib.load(candidate / 'captured-devices.dat')['Devices']
    protected = {tuple(int(tag[k]) for k in ('x', 'y', 'z')) for tag in devices}
    payloads = nbtlib.load(candidate / 'block-entities.dat')['Changes']
    require(len(payloads) == spec['expected_device_changes'] == manifest.get('device_changes', 0) == 0,
            'Access patch device payload changes are not authorized')
    require(not protected.intersection(expected), 'Access patch changes an original device cell')
    editor = Editor(candidate)
    actual = set()
    for file in sorted((candidate / 'source').glob('*.npz')):
        rx, rz = map(int, file.stem.split('.')[1:])
        region = editor.region(rx*512, rz*512)
        for (cx, cz), before, after in zip(region['coords'], region['before'], region['after']):
            actual.update((int(cx)*16+int(ix), int(iy)-128, int(cz)*16+int(iz))
                          for iy, iz, ix in np.argwhere(before != after))
    require(actual == set(expected), 'Saved voxel delta differs from declared access changes')
    old = {}
    for pos, row in expected.items():
        require(editor.state(*pos, True) == row['before'] and editor.state(*pos) == row['after'],
                'Access change before/after state differs from saved cells')
        if row['before'] != 'minecraft:air':
            old[pos] = dict(pos=list(pos), before=row['before'], after=row['after'])
    require(old == approved_old, 'Original-block edits differ from explicit access authorization')
    report = read(package_file(candidate, spec['functional_report']))
    require(report.get('errors') == [] and report.get('changed_cells') == len(expected)
            and report.get('vehicle_intrusions') == [] and report.get('dynamic_gate_bypass') is False,
            'Access functional or vehicle evidence failed')
    require(report.get('preserved_devices') == len(devices)
            and report.get('preserved_actors') == len(read(candidate / 'capture.json').get('actors', [])),
            'Captured device/actor evidence disagrees')
    fields = spec['evidence_fields']
    supports, guards, negatives = (report[fields[k]] for k in ('supports', 'guards', 'negative_cases'))
    require(len(supports) == spec['expected_support_columns'] and len(guards) == spec['expected_guard_probes'],
            'Support or guard evidence count disagrees')
    for column in supports:
        x, z = column['x'], column['z']
        require(editor.state(x, column['base_y'], z) == column['base_state'], 'Support bearing differs')
        ys = column[spec['support_y_field']]
        require(ys == list(range(column['base_y']+1, column['top_y'])), 'Support contains a vertical gap')
        require(all(editor.state(x, y, z) in spec['support_materials'] for y in ys), 'Support material differs')
    for guard in guards:
        hit = guard.get('hit') or {}
        require(hit.get('kind') == 'body_obstruction' and editor.state(*hit['pos']) == hit['state'],
                'Measured side guard is missing')
    require(len(negatives) >= spec['minimum_negative_cases'] and all(q.get('rejected') is True for q in negatives),
            'Access fault rejection evidence failed')
    phases = {phase['phase']: phase for phase in report[fields['phases']]}
    require('before' in phases and 'after' in phases, 'Before/after path evidence is missing')
    after = {goal['key']: goal for goal in phases['after']['goals']}
    keys = spec['required_goals']
    require(keys and len(keys) == len(set(keys)) and set(keys).issubset(after), 'Required access goals are missing')
    routes = []
    nodes = set()
    for key in keys:
        route = after[key]
        require(route.get('reachable') is True and route.get('strict_pass') is True and route.get('path'),
                'Required access goal is unreachable: ' + key)
        for direction in ('forward', 'reverse'):
            check = route[direction]
            require(check.get('kind') == 'strict_static_clear'
                    and 0 <= check.get('maximum_observed_step', math.inf) <= spec['maximum_step'],
                    'Access route lacks bounded bidirectional clearance: ' + key)
        for point in route['path']:
            require(len(point) == 3 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in point),
                    'Access route has an invalid three-dimensional point')
            require(abs(point[1]*2-round(point[1]*2)) < 1e-6, 'Access route is not measured on half-step heights')
            nodes.add((math.floor(point[0]), round((point[1]-1)*2), math.floor(point[2])))
        routes.append(route)
    ground = spec['ground_network']
    require(ground['mode'] in ('preserve', 'explicit_additions','explicit_replacements'), 'Unknown scalar ground update mode')
    columns = ground.get('columns', [])
    require(all(len(row) == 3 and all(isinstance(v, int) and not isinstance(v, bool) for v in row) for row in columns),
            'Explicit ground columns require integer x,z,grade2 values')
    require(ground['mode'] != 'preserve' or not columns, 'Preserve mode cannot change ground columns')
    require(len({(x, z) for x, z, g in columns}) == len(columns), 'Ground columns contain several grades')
    for x, z, grade in columns:
        require((x, grade, z) in nodes and {g for px, g, pz in nodes if (px, pz) == (x, z)} == {grade},
                'Ground update is absent from routes or would flatten a layered route')
    require(ground['mode']!='explicit_replacements'or not columns,'Replacement and addition modes cannot be mixed')
    replacements=ground_replacements(candidate,Path(args.authority),spec,editor,nodes)if ground['mode']=='explicit_replacements'else None
    for view in spec['candidate_views']:
        package_file(candidate, view)
    metadata_scope(candidate)
    return dict(spec=spec, manifest=manifest, report=report, device_count=len(payloads),
                routes=routes, nodes=sorted(nodes), ground_columns=columns, ground_replacements=replacements,
                changed_cells=len(expected), original_blocks_modified=len(old),
                support_columns=len(supports), guard_probes=len(guards), negative_cases=len(negatives),
                frozen_scope=dict(configuration=spec, changes=changes, functional_report=report,
                                  **({'ground_replacements':replacements}if replacements is not None else{})))


def current_state(args, spec):
    require(spec.get('views_reviewed_by_root') is True, 'Root review of the configured exact candidate views is pending')
    state = read(args.continuation)
    require(state['latest_installed_batch'] == spec['previous_batch'] == args.batch-1,
            'Access patch batch is not the next continuation batch')
    require(Path(state['planning_authority']).resolve() == args.authority.resolve()
            == Path(spec['source_authority']).resolve(), 'Access patch authority is stale')
    require(not args.next_authority.exists() and not args.delivery.exists(), 'Never overwrite a published access release')
    require(args.next_authority.resolve() != args.authority.resolve(), 'New authority must have a distinct path')
    return state


def prepared_scope(args, checked):
    prepared = read(args.candidate / 'access-release-check.json')
    require(prepared.get('frozen_scope') == checked['frozen_scope']
            and prepared.get('exact_voxel_views_reviewed') is True,
            'Access scope changed after preparation or was never reviewed')
    require(checked['manifest'].get('preserve_native_members') is True,
            'Installer native preservation guard is not enabled')
    return prepared


def prepare(args):
    require_world(args)
    checked = validate_offline(args)
    spec = checked['spec']
    current_state(args, spec)
    # The shared package checker enforces the root's recorded visual review.
    package_args = argparse.Namespace(**vars(args))
    package_args.checks = args.config
    package_args.review = Path(spec['review_directory'])
    package_args.models = args.candidate
    check_package(package_args)
    source = Path(spec['native_snapshot'])
    require(not source.resolve().is_relative_to(args.world.resolve()), 'Use the offline native snapshot as preparation input')
    baseline = inventory(source)
    require(len(baseline) == spec['expected_native_members'], 'Offline native snapshot count differs')
    require(not (args.candidate / 'preserved-native').exists(), 'Access release was already prepared')
    with stopped_world(args.world):
        assert_preserved(args.world, baseline)
        shutil.copytree(source, args.candidate / 'preserved-native')
        # This enables the installer's exact preservation check with zero new
        # native members; it does not authorize writing any native object.
        checked['manifest']['preserve_native_members'] = True
        write(args.candidate / 'manifest.json', checked['manifest'])
        parallel_recipes(argparse.Namespace(candidate=args.candidate, world=args.world, regions=None, workers=2))
        identity = capture_identity(args.world, args.candidate, args.prior_client)
    metadata_scope(args.candidate)
    write_replay_expected(args.candidate)
    # Recipe preparation appends measured recipe/device counts to the report.
    # Freeze the final prepared evidence rather than its pre-recipe version.
    checked = validate_offline(args)
    write(args.candidate / 'access-release-check.json', dict(
        schema='access-patch-preparation-v1', config=str(args.config.resolve()),
        changed_cells=checked['changed_cells'], device_changes=checked['device_count'], native_additions=0,
        verified_destinations=len(checked['routes']), native_members_preserved=len(baseline),
        identity_files=len(identity), exact_voxel_views_reviewed=True,
        frozen_scope=checked['frozen_scope'], production_recipe_replay_passed=False, world_written=False))
    print('Prepared bounded access patch:', checked['changed_cells'], 'cells;', len(checked['routes']), 'destinations.')


def install(args):
    require_world(args)
    checked = validate_offline(args)
    current_state(args, checked['spec'])
    prepared = prepared_scope(args, checked)
    log = args.production_log.read_text('utf-8-sig')
    matches = re.findall(r'Production surface replay: (\d+) chunks, ([\d,]+) changed cells', log)
    require('BUILD SUCCESSFUL' in log and len(matches) == 1, 'Production replay is incomplete or ambiguous')
    chunks, cells = (int(v.replace(',', '')) for v in matches[0])
    require(cells == checked['changed_cells'] and chunks == len(metadata_scope(args.candidate)),
            'Production replay differs from prepared access scope')
    subprocess.run([sys.executable, str(Path(__file__).with_name('install_hakone_array_patch.py')),
                    '--world', str(args.world), '--candidate', str(args.candidate),
                    '--backup', str(args.installation.parent), '--workers', '2'], check=True)
    prepared['production_recipe_replay_passed'] = True
    prepared['installed_delivery_check_passed'] = False
    write(args.candidate / 'access-release-check.json', prepared)


def publish_overlay(args, checked):
    """Publish metadata only; caller has already verified the installed receipt."""
    columns = checked['ground_columns']
    network = None
    replacement=checked.get('ground_replacements')
    if replacement is not None:
        with np.load(args.authority/'network.npz')as data:network={k:data[k]for k in data.files}
        ax,az,_,_=map(int,network['bounds'])
        for row in replacement['columns']:
            x,z=row['column']
            for field in('walk','grade2'):network[field][z-az,x-ax]=row['after'][field]
    if columns:
        with np.load(args.authority / 'network.npz') as data:
            network = {k: data[k] for k in data.files}
        ax, az, bx, bz = map(int, network['bounds'])
        for x, z, grade in columns:
            require(ax <= x <= bx and az <= z <= bz, 'Explicit ground addition lies outside authority')
            j, i = z-az, x-ax
            if network['walk'][j, i] or network['road'][j, i]:
                require(int(network['grade2'][j, i]) == grade, 'Explicit ground addition changes an existing grade')
            else:
                network['walk'][j, i] = True
                network['grade2'][j, i] = grade
    overlay_name = checked['spec']['id'] + '-multilevel-overlay.json'
    require(not (args.authority / overlay_name).exists(), 'Access overlay identity already exists')
    shutil.copytree(args.authority, args.next_authority)
    if network is not None:
        np.savez_compressed(args.next_authority / 'network.npz', **network)
    else:
        require((args.next_authority / 'network.npz').read_bytes() == (args.authority / 'network.npz').read_bytes(),
                'Preserved scalar network differs')
    overlay = args.next_authority / overlay_name
    require(not overlay.exists(), 'Access overlay identity already exists')
    write(overlay, dict(schema='installed-access-routes-v1', previous=str(args.authority),
        candidate=str(args.candidate), installation=str(args.installation),
        verified_routes=checked['routes'], path_format=['x_world', 'feet_y', 'z_world'],
        station_multi_level_nodes=checked['nodes'], station_multi_level_node_format=['x', 'grade2', 'z'],
        ground_access_columns=columns, ground_access_format=['x', 'z', 'grade2'],
        scalar_network_preserved=not columns and replacement is None,
        ground_replacement_evidence=replacement,maximum_verified_step=checked['spec']['maximum_step'],
        static_access_geometry_only=True, live_acceptance_complete=False, through_service_complete=False,
        existing_station_final_review_complete=False, world_written=True))
    return overlay


def record(args):
    require_world(args)
    checked = validate_offline(args)
    before_state = args.continuation.read_bytes()
    state = current_state(args, checked['spec'])
    require(json.loads(before_state) == state, 'Continuation changed before record validation')
    prepared = prepared_scope(args, checked)
    receipt = read(args.installation)
    require(any(Path(p).resolve() == args.candidate.resolve() for p in receipt.get('candidates', [])),
            'Installation receipt does not refer to this access candidate')
    with stopped_world(args.world):
        installed = verify_delivery(args.world, args.candidate, args.installation, args.production_log)
    require(installed['new_native_members_exact'] == 0 and installed['device_payloads'] == checked['device_count']
            and installed['old_native_members_exact'] == checked['spec']['expected_native_members'],
            'Installed preservation scope differs')
    write(args.candidate / 'delivery-check.json', installed)
    prepared['installed_delivery_check_passed'] = True
    write(args.candidate / 'access-release-check.json', prepared)
    require(args.continuation.read_bytes() == before_state, 'Continuation changed during installed verification')
    overlay = publish_overlay(args, checked)
    report = dict(batch=args.batch, station=checked['spec']['label'], candidate=str(args.candidate),
        installation=str(args.installation), authority=str(args.next_authority), terrain_field=str(args.terrain),
        multilevel_overlay=str(overlay), changed_cells=installed['changed_cells'], recipe_chunks=installed['recipe_chunks'],
        safe_destinations_reachable=len(checked['routes']), maximum_step=checked['spec']['maximum_step'],
        guard_probes_passed=checked['guard_probes'], continuous_support_columns=checked['support_columns'],
        negative_cases_passed=checked['negative_cases'], original_blocks_modified=checked['original_blocks_modified'],
        new_native_members=0, old_native_members_exact=installed['old_native_members_exact'],
        device_payloads=installed['device_payloads'], identity_files_exact=installed['identity_files_exact'],
        whole_client_jar_exact=installed['whole_client_jar_exact'],
        old_road_network_exact=not checked['ground_columns']and checked.get('ground_replacements')is None,
        production_replay_passed=True, world_written=True, client_jar_written=False,
        current_collision_and_open_door_runtime_pending=True, through_service_complete=False,
        existing_station_final_review_complete=False, stage_two_complete=False)
    write(args.delivery, report)
    state.update(latest_installed_batch=args.batch, planning_authority=str(args.next_authority),
                 current_work=checked['spec']['continuation_work'])
    pending = state.setdefault('pending_map_cache_releases', [])
    if str(args.installation.parent) not in pending:
        pending.append(str(args.installation.parent))
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf8', dir=args.continuation.parent,
                                     prefix='.access-progress-', suffix='.json', delete=False) as output:
        json.dump(state, output, ensure_ascii=False, indent=2)
        temporary = Path(output.name)
    try:
        require(args.continuation.read_bytes() == before_state, 'Continuation changed before access publication')
        os.replace(temporary, args.continuation)
    finally:
        if temporary.exists():
            temporary.unlink()
    print('Recorded access patch batch', args.batch, ':', installed['changed_cells'], 'cells; final/live review remains pending.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('mode', choices=('prepare', 'install', 'record'))
    parser.add_argument('--batch', type=int, required=True)
    for key in ('config', 'candidate', 'world', 'authority', 'next-authority', 'installation',
                'production-log', 'delivery', 'continuation', 'terrain', 'prior-client'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    globals()[args.mode](args)
