"""Merge head-edge and adopted early-curve patches, refreshing current states.

Only Root may use --apply. New early topology supersedes obsolete old padding.
"""
import argparse
import gzip
import hashlib
import json
import msvcrt
from collections import defaultdict
from pathlib import Path
import numpy as np
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import iter_selected_sections, iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids, xyz_for


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text('utf8'))
def write(p, v): p.write_text(json.dumps(v, indent=2)+'\n', encoding='utf8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'directory', 'previous', 'head-civil', 'early-civil', 'measurement', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--apply', action='store_true'); a = p.parse_args()
    assert not (a.output/'APPLIED.json').exists()
    head_report, early_report = [read(folder/'CANDIDATE.json') for folder in (a.head_civil, a.early_civil)]
    assert head_report['directory_sha256'] == sha(a.previous)
    assert early_report['directory_sha256'] == sha(a.directory) and early_report['foreign_current_cells'] == 0
    foreign = json.loads(gzip.decompress((a.head_civil/'UNCLASSIFIED_CURRENT_CELLS.json.gz').read_bytes()))
    allowed = {(x, y, -1505) for x in (-1147, -1267, -1387) for y in (169, 170)}
    assert {tuple(row['position']) for row in foreign} <= allowed, 'No other unknown head-edge cells may be inherited'
    names = ['minecraft:air']; codes = {names[0]: 0}
    def code(state):
        if state not in codes: codes[state] = len(names); names.append(state)
        return codes[state]
    measure = np.load(a.measurement/'MEASURED_SOURCE.npz')
    local = {tuple(map(int, key)): j for j, key in enumerate(measure['section_keys'])}
    measured_old_shell = measure['old_shell']; measured_new_shell = measure['new_shell']; measured_retained_shell = measure['retained_shell']
    expectations, desired, masks = {}, {}, {}
    skipped_retired_head_padding = 0
    for role, folder in (('head', a.head_civil), ('early', a.early_civil)):
        d = np.load(folder/'CIVIL_CANDIDATE.npz'); mapping = np.array([code(str(s)) for s in d['palette']], np.uint16)
        section_keys, frozen_before, frozen_after = d['section_keys'], d['before'], d['after']
        for j, raw in enumerate(section_keys):
            key = tuple(map(int, raw)); before, after = mapping[frozen_before[j]], mapping[frozen_after[j]]
            changed = before != after
            if role == 'head':
                xyz = xyz_for(key)
                changed &= ~(np.isin(xyz[:, 0], [-1147, -1267, -1387]) & np.isin(xyz[:, 1], [169, 170]) & (xyz[:, 2] == -1505))
                if key in local:
                    k = local[key]
                    retired = measured_old_shell[k] & ~(measured_new_shell[k] | measured_retained_shell[k])
                    skipped_retired_head_padding += int(np.count_nonzero(changed & retired)); changed &= ~retired
            if not changed.any(): continue
            if key not in desired:
                expectations[key] = before.copy(); desired[key] = before.copy(); masks[key] = np.zeros(4096, bool)
            assert np.all(expectations[key][changed & masks[key]] == before[changed & masks[key]]), 'Candidate old-state conflict'
            expectations[key][changed] = before[changed]; desired[key][changed] = after[changed]; masks[key] |= changed
        print('merged frozen candidate', role, 'sections', len(desired), flush=True)
    selected = defaultdict(set)
    for cx, cz, sy in desired: selected[cx, cz].add(sy)
    rows = []; drift = []
    for cx, cz, sy, pal, indices in iter_selected_sections(a.base/'WORLD', 'projectseele:geofront', selected):
        key = cx, cz, sy; actual = np.array([code(state) for state in pal], np.uint16)[indices]; mask = masks[key]
        for slot in np.flatnonzero(mask & (actual != expectations[key])):
            point = xyz_for(key)[slot].tolist(); drift.append(dict(position=point, expected=names[int(expectations[key][slot])], actual=names[int(actual[slot])]))
        after = actual.copy(); after[mask] = desired[key][mask]
        rows.append((key, actual, after))
    assert len(rows) == len(desired)
    lo = tuple(map(int, np.min(np.array([r[0] for r in rows])[:, [0, 2, 1]]*16, axis=0)))
    hi = tuple(map(int, np.max(np.array([r[0] for r in rows])[:, [0, 2, 1]]*16+15, axis=0)))
    for point, nbt in iter_block_entities(a.base/'WORLD', 'projectseele:geofront', lo, hi, selected_chunks=selected):
        x, y, z = point; key = x//16, z//16, y//16
        assert key not in masks or not masks[key][(y%16)*256+(z%16)*16+x%16], ('Protected complete NBT', point)
    a.output.mkdir(parents=True, exist_ok=True)
    write(a.output/'CURRENT_PRECONDITION_DRIFT.json', drift)
    assert not drift, 'Current edits differ from candidate preconditions; never overwrite them'
    before = np.array([r[1] for r in rows], np.uint16); after = np.array([r[2] for r in rows], np.uint16)
    path = a.output/'CIVIL_CANDIDATE.npz'; keys = [r[0] for r in rows]
    np.savez_compressed(path, section_keys=np.array(keys, np.int32), before=before, after=after, palette=names)
    report = dict(world_written=False, root_author=True, world=str((a.base/'WORLD').resolve()), directory_sha256=sha(a.directory),
        previous_directory_sha256=sha(a.previous), candidate_sha256=sha(path), changed_cells=int(np.count_nonzero(before != after)),
        retired_old_cavity_cells=early_report['retired_old_cavity_cells'], skipped_obsolete_head_padding_cells=skipped_retired_head_padding,
        sections=len(keys), foreign_current_cells=0, current_before_refreshed_through_query_blocks=True,
        source_inputs_sha256={str(folder/'CIVIL_CANDIDATE.npz'): sha(folder/'CIVIL_CANDIDATE.npz') for folder in (a.head_civil, a.early_civil)},
        root_spatial_plan_sha256=sha(a.base/'ROOT_SPATIAL_PLAN.json'), native_admission=False)
    write(a.output/'CANDIDATE.json', report); print(json.dumps(report), flush=True)
    if not a.apply: return
    vox.WORLD = extension.WORLD = a.base/'WORLD'; vox.OUT = a.output; vox.DIM = 'projectseele:geofront'
    painter = vox.Painter(vertical_bounds=(-1344, 320))
    for j, (cx, cz, sy) in enumerate(keys):
        cuboids(painter, (cx*16, sy*16, cz*16), before[j].reshape(16, 16, 16), after[j].reshape(16, 16, 16), names, 'root_current_curve_and_reverse_head_civil')
    painter.meta.update(report); painter.save_plan('current_curve_and_reverse_head_civil')
    lock = extension.acquire_world_lock()
    try:
        receipt = painter.apply('current_curve_and_reverse_head_civil', session_lock=lock)
        index = {key: j for j, key in enumerate(keys)}; checked = 0
        for cx, cz, sy, pal, values in iter_selected_sections(vox.WORLD, vox.DIM, selected):
            actual = np.array([codes[s] for s in pal])[values]
            assert np.array_equal(actual, after[index[cx, cz, sy]]); checked += 1
        assert checked == len(keys)
        report.update(world_written=True, full_selected_sections_read_back=checked, receipt=receipt)
        write(a.output/'APPLIED.json', report)
    finally:
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1); lock.close()


if __name__ == '__main__': main()
