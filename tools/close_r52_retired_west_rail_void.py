"""Finish the retired 105m railway scar without changing the live railway.

Known original grass surfaces remain exact. The 90 original engineering-cap
columns have no retained natural surface; Root blends only those small columns
from their nearest retained natural neighbours, explicitly as new landscaping.
"""
import argparse
from collections import Counter
import json
import msvcrt
from pathlib import Path

import numpy as np
import regional_voxels as vox
from extend_world_depth_r52 import acquire_world_lock
from fit_original_outer_guide_slots_r52 import read_points, WORLD, sha
from query_blocks import iter_block_entities
from restore_r52_west_recorded_mountain import vertical_runs, SOIL, PROOF, INPUT, TEMPLATE, OUT

TOPS = PROOF / 'R20_PRIMARY_WEST_TRUE_REMOVED_GRASS_TOPS.npz'
STAGE = 'retire_105m_void_and_blend_missing_engineering_caps'
AIR = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    assert not list((OUT / STAGE).glob('applied_*'))
    clear = {tuple(p) for p in json.loads(TEMPLATE.read_text(encoding='utf8'))['union_clear_cells']}
    with np.load(TOPS, allow_pickle=False) as data:
        known = {(int(x), int(z)): int(h) for x, z, h in data['columns'] if h > -1000}
        unknown = [tuple(map(int, row)) for row in data['unknown_columns']]
    assert len(known) == 2262 and len(unknown) == 90
    blended = {}
    for x, z in unknown:
        neighbours = sorted((float(np.hypot(x-X, z-Z)), h, X, Z) for (X, Z), h in known.items()
                            if abs(x-X) <= 8 and abs(z-Z) <= 8)[:8]
        assert len(neighbours) >= 3
        h = round(sum(h/(d*d) for d, h, X, Z in neighbours) / sum(1/(d*d) for d, h, X, Z in neighbours))
        blended[x, z] = dict(height=h, measured_neighbours=neighbours)
    desired = {}
    for (x, z), h in known.items():
        for y in range(102, min(112, h) + 1):
            desired[x, y, z] = 'minecraft:grass_block[snowy=false]' if y == h else 'minecraft:dirt' if y >= h-3 else 'minecraft:stone'
    for (x, z), row in blended.items():
        h = row['height']
        for y in range(min(90, h-3), 133):
            desired[x, y, z] = 'minecraft:air' if y > h else 'minecraft:grass_block[snowy=false]' if y == h else 'minecraft:dirt' if y >= h-3 else 'minecraft:stone'
    # Retired R20 concrete/ballast that has already been removed may be
    # restored to its recorded natural before state, never to its old railway.
    with np.load(INPUT, allow_pickle=False) as data:
        palette = data['palette']
        removed_formation = {tuple(map(int, p)): str(palette[b])
                             for p, b, a, c in zip(data['positions'], data['before'], data['after'], data['current_at_audit'], strict=True)
                             if str(palette[b]) in SOIL and str(palette[a]) in ('minecraft:light_gray_concrete', 'minecraft:gravel')
                             and str(palette[c]) in AIR}
    for p, state in removed_formation.items():
        desired.setdefault(p, state)
    actual, selected = read_points(set(desired))
    changes = {p: (actual[p], s) for p, s in desired.items()
               if actual[p] in SOIL | AIR and p not in clear and actual[p] != s}
    assert changes
    low = tuple(min(p[i] for p in desired) for i in range(3))
    high = tuple(max(p[i] for p in desired) for i in range(3))
    tags = dict(iter_block_entities(WORLD, 'projectseele:geofront', low, high, selected_chunks=selected))
    assert not set(tags) & set(changes)
    mtr = {str(p): sha(p) for p in WORLD.rglob('*') if p.is_file() and '/mtr/' in p.as_posix()}
    assert mtr
    painter = vox.Painter(vertical_bounds=(-960, 320))
    for box, a, b in vertical_runs(changes):
        painter.exact(box, a, b, 'R52_retired_105m_rail_natural_closure')
    painter.meta.update(root_author=True, original_known_grass_columns=2262,
                        new_small_cap_blends=[dict(xz=p, **r) for p, r in sorted(blended.items())],
                        original_surface_claimed_for_blends=False, current_native_mtr_clearance_preserved=True)
    vox.WORLD, vox.OUT, vox.DIM = WORLD, OUT, 'projectseele:geofront'
    folder = painter.save_plan(STAGE)
    coords = np.asarray(sorted(changes), np.int32)
    np.savez_compressed(folder / 'EXACT_CHANGES.npz', positions=coords,
                        before=np.asarray([changes[tuple(p)][0] for p in coords]), after=np.asarray([changes[tuple(p)][1] for p in coords]))
    locks = {str(p): sha(p) for p in (TOPS, INPUT, TEMPLATE)}
    report = dict(schema='projectseele.r52.retired-west-rail-scar-closure.v1', world_written=False,
                  changed_cells=len(changes), new_blended_cap_columns=90, blended_height_range=[min(r['height'] for r in blended.values()), max(r['height'] for r in blended.values())],
                  exact_original_surface_claimed_for_blends=False, source_locks=locks, original_railway_rebuilt=False,
                  actual_rail_data_sha256=mtr, live_train_clearance_overlap=len(set(changes) & clear),
                  after_materials=dict(Counter(b for a, b in changes.values())), root_native_art_passed=False)
    if args.apply:
        lock = acquire_world_lock()
        try:
            now, _ = read_points(set(desired))
            assert now == actual and all(sha(p) == h for p, h in (locks | mtr).items())
            report.update(world_written=True, receipt=painter.apply(STAGE, session_lock=lock))
            assert all(sha(p) == h for p, h in mtr.items())
        finally:
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            lock.close()
    (folder/'PLAN.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('receipt','source_locks','actual_rail_data_sha256')}), flush=True)


if __name__ == '__main__':
    main()
