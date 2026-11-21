"""Correct only twelve stale floor proxies at original service-column ports.

Read-only WORLD candidate; Root applies its exact twelve-cell patch separately.
"""
import argparse
import copy
import gzip
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path
from query_blocks import iter_selected_sections, iter_block_entities


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text('utf8'))
def write(p, value): p.write_text(json.dumps(value, indent=2)+'\n', encoding='utf8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'gates', 'previous-gates', 'directory', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); assert not a.output.exists(); shutil.copytree(a.gates, a.output)
    interface = read(a.output/'CURRENT_TYPED_GATE_INTERFACE.json')
    prior = read(a.previous_gates/'CURRENT_TYPED_GATE_INTERFACE.json')
    candidate = read(a.output/'ROOT_TYPED_GATES_CANDIDATE.json')
    old_rows = {g['resource']: g for g in prior['gates']}
    current = {g['resource']: g for g in interface['gates']}
    gates = {g['resource']: g for g in candidate['gates']}
    wanted = {}; proof = []
    for variant, x in enumerate((72.5, 30.5, -11.5)):
        name = f'bay_{variant}_service_pit'; gate = gates[name]
        assert gate['silo_hatch']['service_column_ports'] and not gate['silo_hatch']['upright_guide_ports']
        profile = current[name]['profile']; assert old_rows[name]['profile'] == profile
        assert prior['profiles'][profile]['mesh_sha256'] == interface['profiles'][profile]['mesh_sha256']
        holes = {(int(x-16.5), -1063, z) for z in (322, 334)} | {(int(x+15.5), -1063, z) for z in (322, 334)}
        ref = gate['collision_steps']; path = a.output/ref['cells_file']; assert sha(path) == ref['sha256']
        rows = json.loads(gzip.decompress(path.read_bytes()))
        actual_path = a.output/'collision_tables'/f'{name}__actual_closed_leaf.json.gz'
        actual = {tuple(c['position']) for row in json.loads(gzip.decompress(actual_path.read_bytes())) for c in row}
        selected = {tuple(c['position']): c for row in rows for c in row}
        assert selected.keys()-actual == holes and len(selected) == 1154 and len(actual) == 1151
        shared = actual-selected.keys(); assert shared == {(int(x+12.5), -1063, 311)}
        assert all(selected[q]['closed'] == 'projectseele:nerv_floor_panel' for q in holes)
        fixed = [[c for c in row if tuple(c['position']) not in holes] for row in rows]
        path.write_bytes(gzip.compress(json.dumps(fixed, separators=(',', ':')).encode(), mtime=0))
        ref['sha256'] = sha(path); current[name]['collision_steps'] = copy.deepcopy(ref)
        current[name]['selected_proxy_cell_count'] = 1150
        current[name]['source_proxy_preserved'] = False
        current[name]['service_column_port_proxy_correction'] = sorted(holes)
        wanted.update({q: name for q in holes})
        proof.append(dict(resource=name, original_selected=1154, corrected_selected=1150,
            actual_closed_leaf=1151, shared_front_owned=list(shared)[0], removed_original_column_ports=sorted(holes),
            unchanged_actual_profile_sha256=interface['profiles'][profile]['mesh_sha256'],
            previous_actual_leaf_count=old_rows[name]['actual_closed_leaf_cell_count']))
    selected = defaultdict(set); states = {}
    for x, y, z in wanted: selected[x//16, z//16].add(y//16)
    for cx, cz, sy, palette, indices in iter_selected_sections(a.base/'WORLD', 'projectseele:geofront', selected):
        for q in wanted:
            x, y, z = q
            if (x//16, z//16, y//16) == (cx, cz, sy): states[q] = palette[int(indices[(y%16)*256+(z%16)*16+x%16])]
    assert len(states) == 12 and set(states.values()) == {'projectseele:nerv_floor_panel'}
    assert not [q for q, nbt in iter_block_entities(a.base/'WORLD', 'projectseele:geofront', (-28, -1063, 322), (88, -1063, 334), selected_chunks=selected) if q in wanted]
    candidate['directory_sha256'] = sha(a.directory)
    candidate['service_column_port_correction'] = proof
    write(a.output/'ROOT_TYPED_GATES_CANDIDATE.json', candidate)
    interface['directory_sha256'] = sha(a.directory)
    interface['root_gate_candidate']['sha256'] = sha(a.output/'ROOT_TYPED_GATES_CANDIDATE.json')
    for issue in interface['actual_current_source_proxy_differences']:
        if 'service_pit' in issue['resource']: issue['retained_root_table_cells_without_actual_closed_leaf'] = []
    interface['source_unchanged_column_ports_corrected'] = proof
    write(a.output/'CURRENT_TYPED_GATE_INTERFACE.json', interface)
    changes = [dict(position=list(q), before=states[q], after='minecraft:air', before_nbt_snbt=None,
        after_nbt_snbt=None, resource=wanted[q], reason='actual original fixed column port already absent from moving service leaf') for q in sorted(wanted)]
    receipt = dict(world_written=False, root_review_pending=True, actual_source_mesh_unchanged=True,
        directory_sha256=sha(a.directory), root_spatial_plan_sha256=sha(a.base/'ROOT_SPATIAL_PLAN.json'),
        source_interface_sha256=sha(a.gates/'CURRENT_TYPED_GATE_INTERFACE.json'),
        source_previous_interface_sha256=sha(a.previous_gates/'CURRENT_TYPED_GATE_INTERFACE.json'),
        candidate_sha256=sha(a.output/'ROOT_TYPED_GATES_CANDIDATE.json'), interface_sha256=sha(a.output/'CURRENT_TYPED_GATE_INTERFACE.json'),
        positiveEditMask=[c['position'] for c in changes], changes=changes,
        inversePatch=[dict(position=c['position'], before=c['after'], after=c['before'], before_nbt_snbt=None, after_nbt_snbt=None) for c in changes],
        profiles=proof)
    write(a.output/'SERVICE_COLUMN_PORT_CORRECTION.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('candidate_sha256', 'interface_sha256', 'world_written')}, indent=2))


if __name__ == '__main__': main()
