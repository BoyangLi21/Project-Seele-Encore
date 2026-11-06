"""Root-only finite pockets and real ceiling-supported wet seal bearings."""
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
from r52_spatial_plan import BASE

ROOT = Path(__file__).resolve().parents[1]
OUT = BASE / 'continuous_upright/final_0262_wet_front_seals/v5_true_pit_exit'
SURVEY = OUT / 'CURRENT_NATIVE_POCKET_SURVEY.json'
HANGERS = OUT.parent / 'v2_true_l_shape/ROOT_FINITE_VERTICAL_BEARING_Z308_PROPOSAL.json'
STAGE = 'exact_dry_recesses_and_six_supported_side_bearings'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--support-proof', type=Path)
    args = parser.parse_args()
    assert not list((OUT / STAGE).glob('applied_*')), 'Already applied'
    survey = json.loads(SURVEY.read_text(encoding='utf8'))
    support = json.loads(HANGERS.read_text(encoding='utf8'))
    assert not survey['block_entity_hits']
    assert len(survey['bearings']) == 21
    bearing_cells = {tuple(r['at']) for r in survey['bearings']}
    wet = {tuple(r['position']): r['before'] for r in survey['current_solid_cells'] if r['original_wet_floor']}
    assert len(wet) == 42
    changes = {tuple(r['position']): (r['before'], 'minecraft:air')
               for r in survey['current_solid_cells']
               if not r['original_wet_floor'] and tuple(r['position']) not in bearing_cells}
    assert len(changes) == 666 and all(p[1] < -679 for p in changes)
    for row in support['added_hangers']:
        p = tuple(row['position'])
        assert p not in changes and row['before'] == 'minecraft:air'
        changes[p] = row['before'], row['after']
    assert len(changes) == 696
    caps = {tuple(r['position']): r['state'] for r in support['existing_cap_faces']}
    assert len(caps) == 6 and not set(caps) & set(changes)
    with np.load(OUT / 'CURRENT_NATIVE_POCKET_CONTEXT.npz', allow_pickle=False) as z:
        observed = {tuple(map(int, p)): str(s) for p, s in zip(z['positions'], z['states'], strict=True)}
    points = set(observed) | set(changes) | set(caps) | {(x, -678, z) for x, y, z in wet}
    actual, selected = read_points(points)
    assert all(actual[p] == s for p, s in observed.items())
    assert all(actual[p] == a for p, (a, b) in changes.items())
    assert all(actual[p] == s for p, s in caps.items())
    assert all(actual[p] == s for p, s in wet.items())
    low = tuple(min(p[i] for p in points) for i in range(3))
    high = tuple(max(p[i] for p in points) for i in range(3))
    tags = dict(iter_block_entities(WORLD, 'projectseele:geofront', low, high, selected_chunks=selected))
    assert not set(tags) & set(changes)
    # All six columns terminate on the underside of the actual retained cap.
    for x, y, z in caps:
        assert y == -679 and all((x, yy, z) in changes for yy in range(-684, -679))
    source_locks = survey['source_inputs'] | {str(SURVEY): sha(SURVEY), str(HANGERS): sha(HANGERS)}
    for p, digest in source_locks.items():
        assert sha(p) == digest, ('Actual selected mechanical source changed', p)
    painter = vox.Painter(vertical_bounds=(-960, 320))
    for p, (a, b) in sorted(changes.items()):
        painter.exact((*p, *p), a, b, 'R52_actual_wet_seal_native_interface')
    painter.meta.update(root_author=True, source_locks=source_locks, wet_floor_preserved=list(map(list, wet)),
                        retained_cap_faces=support['existing_cap_faces'])
    vox.WORLD, vox.OUT, vox.DIM = WORLD, OUT, 'projectseele:geofront'
    folder = painter.save_plan(STAGE)
    result = dict(schema='projectseele.r52.actual-wet-seal-native-civil.v1', world_written=False,
                  dry_recess_cells=666, ceiling_supported_column_cells=30, original_closed_floor_cells=42,
                  original_lcl_cells_changed=0, original_native_bearings_retained=15,
                  before_materials=dict(Counter(a for a, b in changes.values())), source_locks=source_locks,
                  native_motion_passed=False, body_and_lower_frame_support_proof=None)
    if args.apply:
        assert args.support_proof, 'Actual complete machinery and body support check required'
        proof = json.loads(args.support_proof.read_text(encoding='utf8'))
        assert proof['root_civil_supports_clear'] is True
        assert proof['proposal_sha256'] == sha(HANGERS)
        assert proof['native_support_cells'] == 30
        for key in ('actual_pit_complete_motion_report', 'actual_lower_fixed_columns_whole_carrier_report'):
            item = proof[key]
            assert item['hits'] == 0 and sha(item['path']) == item['sha256']
            detail = json.loads(Path(item['path']).read_text(encoding='utf8'))
            assert not detail.get('hits') and not detail.get('pairs')
        for item in proof['source_locks']:
            assert sha(item['path']) == item['sha256']
        for path, digest in proof['geometry_source_java_sha256'].items():
            assert sha(ROOT / path) == digest
        result['body_and_lower_frame_support_proof'] = dict(path=str(args.support_proof), sha256=sha(args.support_proof))
        lock = acquire_world_lock()
        try:
            now, _ = read_points(points)
            assert now == actual
            assert all(sha(p) == h for p, h in source_locks.items())
            result.update(world_written=True, receipt=painter.apply(STAGE, session_lock=lock))
        finally:
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            lock.close()
    (folder / 'PLAN.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('source_locks', 'receipt')}), flush=True)


if __name__ == '__main__':
    main()
