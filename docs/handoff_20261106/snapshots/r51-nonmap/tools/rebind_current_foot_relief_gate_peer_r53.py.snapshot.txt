"""Associate only three fixed pit relief changes to their unchanged peer cycle."""
import argparse
import gzip
import json
import struct
from pathlib import Path
from upright_native_anchor_selection_r53 import sha, read


def mesh(path):
    data = memoryview(gzip.decompress(path.read_bytes())); position = 0
    count = struct.unpack_from('>i', data, position)[0]; position += 4; result = {}
    for _ in range(count):
        size = struct.unpack_from('>H', data, position)[0]; position += 2
        name = bytes(data[position:position+size]).decode(); position += size
        moving = bool(data[position]); position += 1
        size = struct.unpack_from('>i', data, position)[0]; position += 4
        result[name] = (moving, bytes(data[position:position+size*8])); position += size*8
    assert position == len(data); return result


def ref(p): return dict(path=str(p.resolve()), sha256=sha(p))
def write(p, value): p.write_text(json.dumps(value, indent=2)+'\n', encoding='utf8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'current', 'foot-proof', 'applied'): p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); oi = read(a.previous/'CURRENT_TYPED_GATE_INTERFACE.json'); ni = read(a.current/'CURRENT_TYPED_GATE_INTERFACE.json')
    old = {row['resource']: row for row in oi['gates']}; new = {row['resource']: row for row in ni['gates']}
    source = read(a.foot_proof); changed = []; rows = []
    for key, gate in new.items():
        previous = old[key]; op, np = oi['profiles'][previous['profile']], ni['profiles'][gate['profile']]
        assert all(previous[field] == gate[field] for field in ('visual', 'world_root', 'bearing_contacts', 'complete_mesh_motion_broadphase_bounds', 'moving_mesh_motion_broadphase_bounds'))
        assert op['phases'] == np['phases'] and op['continuous_sweeps'] == np['continuous_sweeps']
        if op['mesh_sha256'] == np['mesh_sha256']:
            rows.append(dict(resource=key, exact_profile_mesh_reused=True)); continue
        changed.append(key); assert key.endswith('_service_pit')
        old_mesh, new_mesh = mesh(a.previous/op['mesh_file']), mesh(a.current/np['mesh_file'])
        assert old_mesh.keys() == new_mesh.keys()
        changed_parts = []
        for name in old_mesh:
            moving, vertices = old_mesh[name]; new_moving, new_vertices = new_mesh[name]
            assert moving == new_moving
            if vertices != new_vertices:
                assert not moving and name.split('/',1)[1] in ('frame', 'cassette/-1', 'cassette/1')
                changed_parts.append(name)
        assert len(changed_parts) == 3
        variant = gate['variant']; contacts = [row for row in source['rows'] if row['variant'] == variant]
        assert len(contacts) == 4 and all(not row['candidate_full_cube_conflicts'] for row in contacts)
        zones = [[row['cell'][0]-.004, row['cell'][1]-.004, row['cell'][2]-.004,
                  row['cell'][0]+1+.004, row['cell'][1]+1+.004, row['cell'][2]+1+.004] for row in contacts]
        separated = []
        for peer_name, peer in new.items():
            if peer_name == key: continue
            box = peer['complete_mesh_motion_broadphase_bounds']
            assert all(any(zone[i]-.006 >= box[i+3] or box[i]-.006 >= zone[i+3] for i in range(3)) for zone in zones), (key, peer_name)
            separated.append(peer_name)
        rows.append(dict(resource=key, changed_fixed_parts=changed_parts,
            all_leaf_and_bearing_beam_rgb_doubles_exactly_identical=True,
            changed_volume_only_actual_named_native_floor_cubes_plus_4mm=zones,
            all40_peer_complete_motion_bounds_disjoint_from_changed_volume=separated))
    assert changed == ['bay_0_service_pit','bay_1_service_pit','bay_2_service_pit']
    old_gates, new_gates = read(a.previous/'ROOT_TYPED_GATES_CANDIDATE.json'), read(a.current/'ROOT_TYPED_GATES_CANDIDATE.json')
    old_index = {row['resource']: row for row in old_gates['gates']}
    for row in new_gates['gates']:
        previous = old_index[row['resource']]
        assert row['supports'] == previous['supports']
        arows = json.loads(gzip.decompress((a.previous/previous['collision_steps']['cells_file']).read_bytes()))
        brows = json.loads(gzip.decompress((a.current/row['collision_steps']['cells_file']).read_bytes()))
        assert arows == brows
    peer = read(a.previous/'CURRENT_GATE_PEER_CYCLE.json')
    assert peer['passed'] and not peer['hits']
    peer['source_interface'] = str((a.current/'CURRENT_TYPED_GATE_INTERFACE.json').resolve())
    peer['source_interface_sha256'] = sha(a.current/'CURRENT_TYPED_GATE_INTERFACE.json')
    peer['permanent_native_pad_fixed_relief_association'] = dict(previous_peer=ref(a.previous/'CURRENT_GATE_PEER_CYCLE.json'),
        previous_interface=ref(a.previous/'CURRENT_TYPED_GATE_INTERFACE.json'), source_foot_proof=ref(a.foot_proof),
        actual_root_12_native_floor_cells_applied=ref(a.applied),
        all38_other_gate_meshes_byte_identical=True, all41_leaf_phases_motion_bounds_proxy_states_and_support_contacts_exactly_identical=True,
        changed_fixed_volume_peer_disjoint_proofs=rows)
    write(a.current/'CURRENT_GATE_PEER_CYCLE.json', peer)
    result = dict(world_written=False, game_started=False, changed_fixed_profiles=changed, unchanged_other_profiles=38,
        actual_selected_pad_source_and_leaf_and_column_geometry_unchanged=True,
        files={key: ref(a.current/name) for key,name in [('gates','ROOT_TYPED_GATES_CANDIDATE.json'),('gate_interface','CURRENT_TYPED_GATE_INTERFACE.json'),('gate_peer','CURRENT_GATE_PEER_CYCLE.json')]},
        exact_source_association=rows)
    write(a.current/'CURRENT_FIXED_NATIVE_FOOT_RELIEF_SOURCE_RECEIPT.json', result)
    write(a.current/'CURRENT_FIXED_NATIVE_FOOT_RELIEF_INPUTS.json', {key:value for key,value in result.items() if key!='exact_source_association'})
    print(json.dumps({key:value for key,value in result.items() if key!='exact_source_association'}, indent=2))


if __name__ == '__main__': main()
