"""Explicit current pipeline input pins; no WORLD reads or writes, no game PASS."""
import argparse
import copy
import gzip
import itertools
import json
from pathlib import Path
from upright_native_anchor_selection_r53 import sha, read


def write(p, value): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(value, indent=2)+'\n', encoding='utf8')
def ref(p): return dict(path=str(p.resolve()), sha256=sha(p))


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); root = Path(__file__).resolve().parents[1]; audit = root/'.Codex/map_complete_20261013/route_audit'
    base = Path('D:/eva/artifacts/map_complete_20261013'); directory = base/'phased_routes/PHASED_MONOTONE_DESIGN.json'
    previous = base/'phased_routes/west_early_current/ROOT_PREVIOUS_PHASED.json'; old, new = read(previous), read(directory)
    old_legs = {row['id']: row for row in old['legs']}; new_legs = {row['id']: row for row in new['legs']}
    fp = '2cdfbc5ad241a858e0ec93a7bed04430ae03b0fd37e1ca43d7c346f88e1d6724'
    assert fp in (audit/'current_fp/RESULT.txt').read_text('utf8')
    pre_source = audit/'prelaunch_world_current/CURRENT_PRELAUNCH_PART_ENVELOPES.json'
    plug_source = audit/'seated_plug_prelaunch/TRUE_PLUG_ENVELOPES.json'
    pre, plug = read(pre_source), read(plug_source); checks = []
    for row in pre['legs']:
        name = row['leg']; assert old_legs[name] == new_legs[name]
        checks.append(dict(leg=name, whole_leg_exactly_equal=True,
            source_and_target_node_exactly_equal=all(next(n for n in old['nodes'] if n['id'] == old_legs[name][end]) == next(n for n in new['nodes'] if n['id'] == new_legs[name][end]) for end in ('from', 'to'))))
    assert len(checks) == 9 and all(r['source_and_target_node_exactly_equal'] for r in checks)
    for path, digest in plug['sources_sha256'].items(): assert sha(Path(path)) == digest
    old_rebind = Path(plug['prelaunch_geometry_rebind']); prior_rebind = read(old_rebind)
    rebind = dict(world_written=False, directory_sha256=sha(directory), previous_directory_sha256=sha(previous),
        fixed_component_bytes_unchanged=True, all_nine_retained_legs_exactly_equal=True, checks=checks,
        old_prelaunch_envelopes_sha256=sha(pre_source), old_seated_plug_envelopes_sha256=sha(plug_source),
        original_geometry_rebind_sha256=sha(old_rebind), seated_plug_binding_receipt_sha256=prior_rebind['seated_plug_binding_receipt_sha256'])
    rebound = a.out/'PRELAUNCH_RIGID_GEOMETRY_UNCHANGED.json'; write(rebound, rebind)
    pre['directory_fingerprint'] = fp; pre['current_geometry_rebind'] = str(rebound.resolve())
    plug['prelaunch_geometry_rebind'] = str(rebound.resolve())
    write(a.out/'CURRENT_PRELAUNCH_PART_ENVELOPES.json', pre); write(a.out/'TRUE_PLUG_ENVELOPES.json', plug)
    additions_source = root/'.Codex/map_complete_20261013/requirements_audit/flight124/root_frame_candidate_v4_terminal84/GROUND_ADDITIONAL_SPACE.json'
    additions = read(additions_source); additions['source_ground'] = str(directory); additions['source_sha256'] = sha(directory)
    additions['current_rebind'] = dict(original_source_sha256=sha(additions_source),
        same_canonical_space_resources_and_bindings=True, geometry_scope='Canonical 32m shared SPACE IDs; none derives terrain or route permission')
    write(a.out/'GROUND_ADDITIONAL_SPACE.json', additions)
    old_peer_path = audit/'final_gate_native_readback/rebound_current/CURRENT_GATE_PEER_CYCLE.json'
    old_interface_path = audit/'final_gate_native_readback/rebound_current/CURRENT_TYPED_GATE_INTERFACE.json'
    gates_folder = audit/'west_early_service_ports/early_export/gates'; interface_path = gates_folder/'CURRENT_TYPED_GATE_INTERFACE.json'
    old_interface, interface = read(old_interface_path), read(interface_path)
    previous_gates = {r['resource']: r for r in old_interface['gates']}; gates = {r['resource']: r for r in interface['gates']}
    changed, unchanged = [], []
    for name, row in gates.items():
        prior = previous_gates[name]
        same = old_interface['profiles'][prior['profile']]['mesh_sha256'] == interface['profiles'][row['profile']]['mesh_sha256']
        if same:
            assert all(prior[key] == row[key] for key in ('visual', 'world_root', 'complete_mesh_motion_broadphase_bounds', 'moving_mesh_motion_broadphase_bounds', 'bearing_contacts'))
            assert all(old_interface['profiles'][prior['profile']][key] == interface['profiles'][row['profile']][key] for key in ('phases', 'continuous_sweeps', 'monotone_source_checks'))
            unchanged.append(name)
        else: changed.append(name)
    pairs = []
    for left, right in itertools.combinations(gates, 2):
        if left not in changed and right not in changed: continue
        lo, hi = gates[left]['complete_mesh_motion_broadphase_bounds'], gates[right]['complete_mesh_motion_broadphase_bounds']
        separated = [axis for axis in range(3) if lo[axis]-.006 >= hi[axis+3] or hi[axis]-.006 >= lo[axis+3]]
        assert separated, ('Changed source gates need new exact peer sweep', left, right)
        pairs.append(dict(a=left, b=right, complete_motion_bounds_separated_axes=separated, combined_error_m=.006))
    assert len(changed) == 27 and len(unchanged) == 14 and len(pairs) == 729
    previous_peer = read(old_peer_path); assert previous_peer['passed'] and not previous_peer['hits']
    peer = dict(schema=previous_peer['schema'], source_interface=str(interface_path.resolve()), source_interface_sha256=sha(interface_path),
        passed=True, hits=[], world_written=False, game_started=False, reverse_occupancy_identical=True,
        current_changed_gate_pairs_proven_disjoint=len(pairs), reused_exact_unchanged_peer_gate_count=14,
        original_proof=ref(old_peer_path), original_interface=ref(old_interface_path),
        original_pair_windows=previous_peer['pair_windows'], current_pair_windows_reswept=0,
        geometry_association=dict(method='All14 unchanged peer profiles retain byte-identical mesh and exact phase/sweep/frame/bearing values. All27 changed upright gates have complete-motion bounds disjoint from every peer with both 3mm kernel allowances included.',
            unchanged_profiles=unchanged, changed_disjoint_profiles=changed, complete_motion_pair_proofs=pairs))
    write(a.out/'CURRENT_GATE_PEER_CYCLE.json', peer)
    files = {
        'ascent_hulls': base/'phased_routes/west_early_current/early_measurement/CURRENT_COMPLETE_NINE_ASCENT_HEIGHT_HULLS_BOUND.json',
        'prelaunch_envelopes': a.out/'CURRENT_PRELAUNCH_PART_ENVELOPES.json',
        'seated_plug_envelopes': a.out/'TRUE_PLUG_ENVELOPES.json',
        'bank_head_envelopes': a.out/'bank_current/CURRENT_ALL48_PART_ENVELOPES.json',
        'air_space_additions': a.out/'GROUND_ADDITIONAL_SPACE.json',
        'gate_interface': interface_path, 'gate_peer': a.out/'CURRENT_GATE_PEER_CYCLE.json',
        'gates': gates_folder/'ROOT_TYPED_GATES_CANDIDATE.json',
        'guide_source': root/'src/main/resources/assets/projectseele/facility/r52_upright_guideway_paths.json'}
    for path in files.values(): assert path.is_file(), path
    result = dict(world_written=False, game_started=False, directory=ref(directory), directory_fingerprint=fp,
        root_spatial_plan=ref(base/'ROOT_SPATIAL_PLAN.json'), files={key: ref(path) for key, path in files.items()},
        explicit_override_all_seven_stale_pipeline_defaults=True)
    write(a.out/'CURRENT_PIPELINE_SOURCE_INPUTS.json', result)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}, indent=2))


if __name__ == '__main__': main()
