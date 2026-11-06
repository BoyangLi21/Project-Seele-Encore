"""Restore the exact natural material removed by the inactive R20 height field.

Root-owned finite repair. Current MTR clear space, newer edits, old railway
formation, and cells without a retained before record are not overwritten.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import msvcrt
from pathlib import Path

import numpy as np
import regional_voxels as vox
from extend_world_depth_r52 import acquire_world_lock
from fit_original_outer_guide_slots_r52 import read_points, WORLD
from query_blocks import iter_block_entities
from r52_spatial_plan import BASE

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / '.codex/r52_global_height_ownership_readonly'
INPUT = PROOF / 'R20_PRIMARY_WEST_BEFORE_AFTER_CURRENT_CHANGED_CELLS.npz'
TEMPLATE = PROOF / 'MTR405_NATIVE_TWO_RAIL_EXACT_TEMPLATE.json'
OUT = BASE / 'final_map_audit/west_recorded_mountain'
STAGE = 'restore_true_natural_before_preserve_live_rail'
SOIL = {'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block[snowy=false]'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def vertical_runs(changes):
    columns = defaultdict(list)
    for (x, y, z), (before, after) in changes.items():
        columns[x, z, before, after].append(y)
    for (x, z, before, after), ys in sorted(columns.items()):
        ys.sort()
        first = previous = ys[0]
        for y in ys[1:] + [ys[-1] + 2]:
            if y == previous + 1:
                previous = y
                continue
            yield (x, first, z, x, previous, z), before, after
            first = previous = y


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    assert not list((OUT / STAGE).glob('applied_*')), 'Do not replay this repair'
    assert sha(INPUT) == 'eea53a20024837186606b48ed8002769a238a043b93d2512825c68909269fc7f'
    assert sha(TEMPLATE) == '7033262b39fc4b58bcfc22737fd4e2e7f63f34624325734efa29217753d06991'
    template = json.loads(TEMPLATE.read_text(encoding='utf8'))
    clear = {tuple(p) for p in template['union_clear_cells']}
    with np.load(INPUT, allow_pickle=False) as data:
        palette = data['palette']
        source = {tuple(map(int, p)): (str(palette[b]), str(palette[a]))
                  for p, b, a in zip(data['positions'], data['before'], data['after'], strict=True)}
    actual, selected = read_points(set(source))
    changes, reasons = {}, Counter()
    for pos, (original, old_after) in source.items():
        if original not in SOIL:
            reasons['old_rail_formation_air_or_other_not_restored'] += 1
        elif pos in clear:
            reasons['current_native_train_clearance_preserved'] += 1
        elif actual[pos] != old_after:
            reasons['later_real_world_edit_preserved'] += 1
        elif actual[pos] != original:
            changes[pos] = (actual[pos], original)
    assert changes
    low = tuple(min(p[i] for p in changes) for i in range(3))
    high = tuple(max(p[i] for p in changes) for i in range(3))
    tags = dict(iter_block_entities(WORLD, 'projectseele:geofront', low, high, selected_chunks=selected))
    assert not set(tags) & set(changes)
    # The actual railway state directory is read-only and must retain every byte.
    mtr_paths = sorted(p for p in WORLD.rglob('*') if p.is_file() and '/mtr/' in p.as_posix())
    mtr_hashes = {str(p): sha(p) for p in mtr_paths}
    assert mtr_hashes, 'Actual existing MTR identity data must be available'
    painter = vox.Painter(vertical_bounds=(-960, 320))
    for box, before, after in vertical_runs(changes):
        painter.exact(box, before, after, 'R52_restore_recorded_natural_mountain')
    locks = {str(p): sha(p) for p in (INPUT, TEMPLATE)}
    painter.meta.update(root_author=True, source_locks=locks,
                        current_rail_clearance_preserved=True,
                        assumed_unknown_surface_columns=0,
                        retired_105m_railway_restored=False)
    vox.WORLD, vox.OUT, vox.DIM = WORLD, OUT, 'projectseele:geofront'
    folder = painter.save_plan(STAGE)
    coords = np.asarray(sorted(changes), np.int32)
    np.savez_compressed(folder / 'EXACT_CHANGES.npz', positions=coords,
                        before=np.asarray([changes[tuple(p)][0] for p in coords]),
                        after=np.asarray([changes[tuple(p)][1] for p in coords]))
    result = dict(schema='projectseele.r52.restore-recorded-natural-west-mountain.v1',
                  world_written=False, changed_cells=len(changes), columns=len({(p[0], p[2]) for p in changes}),
                  exact_vertical_runs=len(painter.ops), excluded=dict(reasons),
                  after_materials=dict(Counter(b for a, b in changes.values())),
                  source_locks=locks, actual_mtr_members=mtr_hashes, block_entities_changed=0,
                  rail_clearance_overlap=len(set(changes) & clear),
                  root_native_art_review=False, restored_unknown_original_surface=False)
    if args.apply:
        lock = acquire_world_lock()
        try:
            now, _ = read_points(set(source))
            assert now == actual, 'Actual western terrain changed since the read'
            assert all(sha(p) == h for p, h in locks.items())
            assert all(sha(p) == h for p, h in mtr_hashes.items())
            result.update(world_written=True, receipt=painter.apply(STAGE, session_lock=lock))
            assert all(sha(p) == h for p, h in mtr_hashes.items())
        finally:
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            lock.close()
    (folder / 'PLAN.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('actual_mtr_members', 'receipt')}), flush=True)


if __name__ == '__main__':
    main()
