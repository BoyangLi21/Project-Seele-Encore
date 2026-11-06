"""Bind every support proof to the exact current production gate contact.

Metadata candidates only; block position/state, proxies and geometry stay exact.
"""
import argparse
import copy
import json
import shutil
from pathlib import Path
from upright_native_anchor_selection_r53 import sha, read


def write(p, value): p.write_text(json.dumps(value, indent=2)+'\n', encoding='utf8')
def ref(p): return dict(path=str(p.resolve()), sha256=sha(p))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('gates', 'interface', 'peer', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); assert not a.out.exists(); shutil.copytree(a.gates.parent, a.out)
    source, interface, peer = [read(path) for path in (a.gates, a.interface, a.peer)]
    assert interface['root_gate_candidate']['sha256'] == sha(a.gates)
    assert peer['passed'] and not peer['hits'] and peer['source_interface_sha256'] == sha(a.interface)
    frames = {row['resource']: row for row in interface['gates']}; candidate = copy.deepcopy(source); bindings = []
    for gate in candidate['gates']:
        contacts = {tuple(c['candidate_cell']): c for c in frames[gate['resource']]['bearing_contacts']}
        assert len(contacts) == len(frames[gate['resource']]['bearing_contacts'])
        assert set(contacts) == {tuple(s['position']) for s in gate['supports']}, gate['resource']
        for support in gate['supports']:
            contact = contacts[tuple(support['position'])]
            assert contact['nine_points_on_actual_fixed_triangles']
            normal, point, half = contact['normal_world'], contact['point_world'], contact['half_width_m']
            assert len(normal) == len(point) == 3 and sum(v*v for v in normal) == 1 and sum(abs(v) for v in normal) == 1
            assert 0 < half <= .5
            old = copy.deepcopy(support)
            support.update(source_contact=dict(zip(('x', 'y', 'z'), point)), normal=normal,
                half_width_m=half, contact_half_width_m=half,
                source_contact_kind=contact['kind'], source_contact_triangle_witnesses=contact['triangle_witnesses'])
            bindings.append(dict(resource=gate['resource'], position=support['position'], state=support['state'],
                old_support_metadata=old, current_production_contact=contact))
    assert len(bindings) == 370 and len({tuple(row['position']) for row in bindings}) == 354
    for before, after in zip(source['gates'], candidate['gates']):
        arow, brow = copy.deepcopy(before), copy.deepcopy(after)
        arow['supports'] = [dict(position=s['position'], state=s['state']) for s in arow['supports']]
        brow['supports'] = [dict(position=s['position'], state=s['state']) for s in brow['supports']]
        assert arow == brow, 'Only support proof metadata may change'
    gate_file = a.out/'ROOT_TYPED_GATES_CANDIDATE.json'; write(gate_file, candidate)
    interface['root_gate_candidate']['file'] = gate_file.name
    interface['root_gate_candidate']['sha256'] = sha(gate_file)
    interface['current_support_proof_metadata_binding'] = dict(source_interface=ref(a.interface),
        source_gates=ref(a.gates), actual_contacts=370, unique_native_support_cells=354,
        all_contact_geometry_and_motion_exactly_unchanged=True, half_width_m_preserved=True)
    interface_file = a.out/'CURRENT_TYPED_GATE_INTERFACE.json'; write(interface_file, interface)
    peer['source_interface'] = str(interface_file.resolve()); peer['source_interface_sha256'] = sha(interface_file)
    peer['current_support_metadata_association'] = dict(original_peer=ref(a.peer), original_interface=ref(a.interface),
        same_actual_contacts_and_profile_triangle_motion_values=True, changed_only_support_proof_representation=True,
        actual_point_normal_and_half_width_from_current_production_interface=True)
    peer_file = a.out/'CURRENT_GATE_PEER_CYCLE.json'; write(peer_file, peer)
    receipt = dict(world_written=False, game_started=False, original_gates=ref(a.gates), original_interface=ref(a.interface),
        contacts=370, unique_native_support_cells=354, entire_geometry_proxy_and_native_cell_states_unchanged=True,
        half_widths_sorted=sorted({row['current_production_contact']['half_width_m'] for row in bindings}),
        files=dict(gates=ref(gate_file), gate_interface=ref(interface_file), gate_peer=ref(peer_file)), bindings=bindings)
    write(a.out/'CURRENT_NATIVE_CONTACT_BINDING_RECEIPT.json', receipt)
    write(a.out/'CURRENT_NATIVE_CONTACT_INPUTS.json', {key: value for key, value in receipt.items() if key != 'bindings'})
    print(json.dumps({key: value for key, value in receipt.items() if key != 'bindings'}, indent=2))


if __name__ == '__main__': main()
