"""Bind the reviewed 1872 requests to current native faces and source lineage.

Only unchanged-route source-clear anchors may be reused, after native reread.
"""
import argparse
import copy
import json
import shutil
from pathlib import Path
import numpy as np
from upright_native_anchor_selection_r53 import sha, read, MeasuredWorld, finite_face


def write(p, value): p.write_text(json.dumps(value, indent=2)+'\n', encoding='utf8')
def key(row): return row['leg'], row['side'], tuple(np.array(row['actual_rail_weld_triangle']).ravel())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'directory', 'measurement', 'gates', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); root = Path(__file__).resolve().parents[1]
    folder = root/'.Codex/map_complete_20261013/requirements_audit/anchor_tool/reverse_diagonal'
    assert not a.output.exists(); a.output.mkdir(parents=True)
    steel = folder/'WEST_EARLY_REVIEW_STEEL.json'; sockets = steel.with_suffix('.SOCKETS.json')
    requests = read(sockets); assert len(requests['sockets']) == 1872 and requests['directory_geometry_sha256'] == sha(a.directory)
    current = a.output/'source'; current.mkdir()
    old_source = folder/'current_source'; export = read(old_source/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json')
    dependencies = {}
    for name in ['ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz', *[f'ACTUAL_FIXED_ASSEMBLY.variant{v}.bin.gz' for v in range(3)]]:
        source = old_source/name; target = current/name; shutil.copy2(source, target)
        assert sha(source) == sha(target); dependencies[str(target.resolve())] = sha(target)
    export['root_design_sha256'] = sha(a.directory)
    export['directory_fingerprint'] = '2cdfbc5ad241a858e0ec93a7bed04430ae03b0fd37e1ca43d7c346f88e1d6724'
    export['sources_sha256'] = dependencies
    export['current_curve_rebind_receipt'] = dict(previous_export_sha256=sha(old_source/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json'),
        unchanged_original_body_and_head_binary_bytes=True, no_original_body_export_or_remesh=True,
        new_directory_sha256=sha(a.directory), production_fp_result_sha256=sha(root/'.Codex/map_complete_20261013/route_audit/current_fp/RESULT.txt'))
    write(current/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json', export)
    cones = read(old_source/'CURRENT_HEAD_CONTINUOUS_TANGENT_CONES.json'); rebound = []
    for row in cones['cones']:
        r = copy.deepcopy(row)
        if '/exit3/' in r['leg']:
            if r['segment'] in (1, 2, 3): continue
            if r['segment'] >= 4: r['segment'] -= 1
        rebound.append(r)
    rebound.extend(read(a.measurement/'ADDED_EARLY_HEAD_TANGENT_CONES.json')['cones'])
    cones.update(root_design_sha256=sha(a.directory), cones=rebound, exact_original_far_direction_rows_reused=True)
    write(current/'CURRENT_HEAD_CONTINUOUS_TANGENT_CONES.json', cones)
    old_requests = {r['socket_id']: r for r in read(folder/'REVERSE68_UNANCHORED_STEEL.SOCKETS.json')['sockets']}
    old_seats = read(folder/'REVERSE68_NATIVE_SEATS_537_FIXED.json')
    proof = read(folder/'REVERSE481_COMPLETE_SOURCE_REVIEW.json')
    clear = {r['socket_id'] for r in proof['results'] if r['continuous_complete_source_clear']}
    clear.add(read(folder/'REVERSE537_SOURCE_NATIVE_RECEIPT.json')['socket_id'])
    new_by_geometry = {key(r): r for r in requests['sockets']}
    preserved, mapping_rows = [], []
    for seat in old_seats['seats']:
        ident = seat['socket_id']
        if ident not in clear: continue
        old_request = old_requests[ident]
        if '/exit3/' in old_request['leg']: continue
        candidate = new_by_geometry.get(key(old_request))
        if candidate is None: continue
        assert old_request['rail_bearing'] == candidate['rail_bearing'] and old_request['normal'] == candidate['normal']
        bound = copy.deepcopy(seat); bound['socket_id'] = candidate['socket_id']
        bound['current_exact_unchanged_source_reuse'] = dict(previous_socket_id=ident,
            previous_full_triangle_proof_sha256=sha(folder/'REVERSE481_COMPLETE_SOURCE_REVIEW.json'),
            unchanged_full_leg=True, actual_weld_triangle_exact=True)
        preserved.append(bound); mapping_rows.append(dict(previous_socket=ident, current_socket=candidate['socket_id']))
    shapes_path = a.base/'WORLD/native_collision_shapes.json'; shapes = read(shapes_path)
    world = MeasuredWorld(a.base/'WORLD', 'projectseele:geofront')
    for row in preserved:
        world.box(tuple(row['at']), tuple(row['at']))
        if row.get('secondary_native_seat'): world.box(tuple(row['secondary_native_seat']['at']), tuple(row['secondary_native_seat']['at']))
    world.load(); valid, invalid = [], []
    for row in preserved:
        good = True
        for seat in (row, row.get('secondary_native_seat')):
            if seat is None: continue
            state = world.block(tuple(seat['at'])); boxes = [np.array(b)+np.tile(seat['at'], 2) for b in shapes.get(state, [])]
            good &= state == seat['state'] and finite_face(boxes, seat['bearing'], seat['normal'])
        (valid if good else invalid).append(row)
    terminal = dict(model_source_sha256=requests['model_source_sha256'], directory_geometry_sha256=sha(a.directory),
        head_transfer_source_sha256=requests['head_transfer_source_sha256'], seats=[], status='NO_OLD_TERMINAL_ADMISSION_ALL_TERMINALS_CURRENT_RESELECT')
    terminal_path = a.output/'EMPTY_TERMINALS.json'; write(terminal_path, terminal)
    lining = a.base/'phased_routes/final68_ascent_civil/CIVIL_CANDIDATE.npz'
    result = dict(schema=old_seats['schema'], status='CURRENT_UNCHANGED_LEG_NATIVE_REBOUND_SEED',
        world=str((a.base/'WORLD').resolve()), model_source_sha256=requests['model_source_sha256'],
        directory_geometry_sha256=sha(a.directory), head_transfer_source_sha256=requests['head_transfer_source_sha256'],
        socket_requests_sha256=sha(sockets), lining_npz_sha256=sha(lining), terminal_seats_sha256=sha(terminal_path),
        native_shapes_sha256=sha(shapes_path), gate_candidate_sha256=sha(a.gates/'ROOT_TYPED_GATES_CANDIDATE.json'),
        gate_interface_sha256=sha(a.gates/'CURRENT_TYPED_GATE_INTERFACE.json'), seats=valid,
        pending=[r for r in requests['sockets'] if r['socket_id'] not in {s['socket_id'] for s in valid}],
        world_written=False, production_enable=False, current_root_combined_applied_sha256=sha(a.base/'phased_routes/west_early_current/combined_civil/APPLIED.json'))
    write(a.output/'CURRENT_NATIVE_SEED.json', result)
    write(a.output/'EXACT_UNCHANGED_LEG_REBIND_RECEIPT.json', dict(world_written=False, socket_requests=1872,
        previous_source_clear=474, preserved_current_native=len(valid), prior_native_face_changed=len(invalid),
        actual_weld_geometry_remapping=mapping_rows, no_original_body_retest=True))
    print(json.dumps(dict(socket_requests=1872, preserved_current_native=len(valid), pending=len(result['pending']), source=str(current)), indent=2))


if __name__ == '__main__': main()
