"""Root-only reversible civil delta for the one adopted west-early curve.

Candidate creation only reads WORLD; --apply is reserved for the sole Root.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import argparse
import gzip
import hashlib
import json
import msvcrt
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import iter_selected_sections, iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids, xyz_for


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text('utf8'))
def write(p, value): p.write_text(json.dumps(value, indent=2)+'\n', encoding='utf8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'measurement', 'directory', 'gates', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--apply', action='store_true'); a = p.parse_args()
    assert not (a.output/'APPLIED.json').exists()
    world = a.base/'WORLD'; source = np.load(a.measurement/'MEASURED_SOURCE.npz')
    report = read(a.measurement/'MEASURED_REPORT.json')
    assert report['root_design_sha256'] == sha(a.directory)
    assert report['measured_legs'] == 'ONLY_THREE_CHANGED_EARLY_SEGMENTS_AND_OLD_MAIN_PREFIX'
    assert report['root_spatial_plan_sha256'] == sha(a.base/'ROOT_SPATIAL_PLAN.json')
    names = list(map(str, source['palette'])); codes = {state: j for j, state in enumerate(names)}
    def code(state):
        if state not in codes: codes[state] = len(names); names.append(state)
        return codes[state]
    air, panel = code('minecraft:air'), code('projectseele:nerv_shaft_panel')
    before = source['before']; after = before.copy(); keys = [tuple(map(int, k)) for k in source['section_keys']]
    selected = defaultdict(set)
    for cx, cz, sy in keys: selected[cx, cz].add(sy)
    lo = tuple(map(int, np.min(np.array(keys)[:, [0, 2, 1]]*16, axis=0)))
    hi = tuple(map(int, np.max(np.array(keys)[:, [0, 2, 1]]*16+15, axis=0)))
    devices = {tuple(q) for q, nbt in iter_block_entities(world, 'projectseele:geofront', lo, hi, selected_chunks=selected)}
    slots = defaultdict(list)
    for x, y, z in devices: slots[x//16, z//16, y//16].append((y%16)*256+(z%16)*16+x%16)
    for gate in read(a.gates)['gates']:
        for s in gate['supports']:
            x, y, z = s['position']; slots[x//16, z//16, y//16].append((y%16)*256+(z%16)*16+x%16)
    old_file = a.base/'phased_routes/final68_ascent_civil/CIVIL_CANDIDATE.npz'
    old = np.load(old_file); original_palette = list(map(str, old['palette']))
    mapping = np.array([code(s) for s in original_palette], np.uint16)
    old_index = {tuple(map(int, k)): j for j, k in enumerate(old['section_keys'])}
    frozen_old_before, frozen_old_after = old['before'], old['after']
    old_core_rows, old_shell_rows = source['old_core'], source['old_shell']
    new_core_rows, new_shell_rows = source['new_core'], source['new_shell']
    retained_core_rows, retained_shell_rows = source['retained_core'], source['retained_shell']
    lining = {'projectseele:nerv_shaft_panel', 'projectseele:nerv_machine_edge', 'projectseele:nerv_strip_light[lit=true]'}
    natural = {'minecraft:stone', 'minecraft:deepslate', 'minecraft:deepslate[axis=y]', 'minecraft:bedrock',
        'minecraft:dirt', 'minecraft:grass_block[snowy=false]', 'minecraft:gravel', 'minecraft:sand',
        'minecraft:andesite', 'minecraft:diorite', 'minecraft:granite', 'minecraft:tuff', 'minecraft:coal_ore',
        'minecraft:iron_ore', 'minecraft:copper_ore', 'minecraft:deepslate_coal_ore', 'minecraft:deepslate_iron_ore', 'minecraft:deepslate_copper_ore'}
    air_names = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}
    materials = Counter(); retired = 0; foreign = []; protected = Counter()
    for j, key in enumerate(keys):
        xyz = xyz_for(key); x, y, z = xyz.T; state = before[j]
        old_core, old_shell = old_core_rows[j], old_shell_rows[j]
        new_core = new_core_rows[j] | retained_core_rows[j]
        new_shell = new_shell_rows[j] | retained_shell_rows[j]
        prior = old_index.get(key)
        owned = np.zeros(4096, bool); old_before = None
        if prior is not None:
            old_before, old_after = mapping[frozen_old_before[prior]], mapping[frozen_old_after[prior]]
            owned = (old_before != old_after) & (state == old_after)
        port_keep = np.array([names[int(value)] == 'minecraft:barrier' or names[int(value)] in
            {'projectseele:clear_glass', 'minecraft:light_gray_stained_glass', 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'}
            or names[int(value)].startswith('projectseele:nerv_warning_beacon') for value in state])
        port_keep[slots.get(key, [])] = True
        # Positive original bank-roof ownership inherited from the accepted
        # bank component, rather than a collision-derived permission.
        roof = (y >= -956) & (y <= -930) & (x >= -31) & (x <= 91) & (z >= 9) & (z <= 147)
        authored = np.array([names[int(value)].startswith('projectseele:nerv_') or names[int(value)] in
            {'minecraft:light_gray_concrete', 'minecraft:gray_concrete', 'minecraft:black_concrete', 'minecraft:iron_block',
             'minecraft:polished_basalt[axis=y]', 'minecraft:sea_lantern', 'minecraft:ladder[facing=south,waterlogged=false]'} for value in state])
        valid = np.isin(state, [codes[s] for s in natural | air_names if s in codes]) | (owned & np.isin(state, [codes[s] for s in lining if s in codes])) | (roof & authored)
        active = source['new_shell'][j]
        unknown = active & new_core & ~valid & ~port_keep
        for index in np.flatnonzero(unknown): foreign.append(dict(position=xyz[index].tolist(), state=names[int(state[index])]))
        edit = active & valid & ~port_keep
        after[j][edit & new_core] = air
        after[j][edit & ~new_core] = panel
        # Retire the entire unique old cavity by restoring its frozen source;
        # never fill any still-used route or an unowned/manual changed cell.
        retirement = old_shell & ~new_shell & owned & ~port_keep
        if old_before is not None:
            retirement &= np.isin(old_before, [codes[s] for s in natural | air_names if s in codes])
            after[j][retirement] = old_before[retirement]
            retired += int(np.count_nonzero(retirement & (state != after[j])))
        for value, count in zip(*np.unique(state[active & port_keep], return_counts=True)): protected[names[int(value)]] += int(count)
        for value, count in zip(*np.unique(state[state != after[j]], return_counts=True)): materials[names[int(value)]] += int(count)
    a.output.mkdir(parents=True, exist_ok=True)
    path = a.output/'CIVIL_CANDIDATE.npz'
    np.savez_compressed(path, section_keys=np.array(keys, np.int32), before=before, after=after, palette=names)
    (a.output/'UNCLASSIFIED_CURRENT_CELLS.json.gz').write_bytes(gzip.compress(json.dumps(foreign, separators=(',', ':')).encode(), mtime=0))
    result = dict(world_written=False, root_author=True, world=str(world.resolve()), directory_sha256=sha(a.directory),
        candidate_sha256=sha(path), measurement_sha256=sha(a.measurement/'MEASURED_SOURCE.npz'),
        root_spatial_plan_sha256=sha(a.base/'ROOT_SPATIAL_PLAN.json'), old_lining_sha256=sha(old_file),
        changed_cells=int(np.count_nonzero(before != after)), retired_old_cavity_cells=retired, sections=len(keys),
        foreign_current_cells=len(foreign), changed_materials=materials, protected_current_states=protected,
        original_devices=len(devices), full_body_mesh_not_retested=True, native_admission=False)
    write(a.output/'CANDIDATE.json', result); print(json.dumps(result), flush=True)
    if not a.apply: return
    assert not foreign, 'Unclassified current cells need Root review'
    vox.WORLD = extension.WORLD = world; vox.OUT = a.output; vox.DIM = 'projectseele:geofront'
    painter = vox.Painter(vertical_bounds=(-1344, 320))
    for j, (cx, cz, sy) in enumerate(keys):
        if np.any(before[j] != after[j]):
            cuboids(painter, (cx*16, sy*16, cz*16), before[j].reshape(16, 16, 16), after[j].reshape(16, 16, 16), names, 'root_adopted_west_early_curve_and_complete_retired_cavity')
    painter.meta.update(result); painter.save_plan('west_early_curve_civil_delta')
    lock = extension.acquire_world_lock()
    try:
        receipt = painter.apply('west_early_curve_civil_delta', session_lock=lock)
        index = {k: j for j, k in enumerate(keys)}; checked = 0
        for cx, cz, sy, pal, values in iter_selected_sections(world, vox.DIM, selected):
            actual = np.array([codes[s] for s in pal])[values]
            assert np.array_equal(actual, after[index[cx, cz, sy]])
            checked += 1
        assert checked == len(keys)
        result.update(world_written=True, receipt=receipt, full_selected_sections_read_back=checked)
        write(a.output/'APPLIED.json', result)
    finally:
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1); lock.close()


if __name__ == '__main__': main()
