"""Root's finite original-ramp guide recesses; wet seals stay untouched.

Consumes actual current-mesh triangle evidence, not a bounding-box excavation.
The 42 wet-pool floor cells require a visible operated seal in a separate change.
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
from query_blocks import iter_block_entities, iter_selected_sections
from r52_spatial_plan import BASE

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / '.codex/r52_final_0262_loading_floor_readonly'
REPORT = EVIDENCE / 'FINAL_ORIGINAL9_OUTER_SLOT_CANDIDATES_AND_PROTECTIONS.json'
CELLS = EVIDENCE / 'FINAL_ORIGINAL9_OUTER_STATIC_SLOT_CELLS.npz'
OUT = BASE / 'continuous_upright/final_0262_original_finite_slots'
STAGE = 'nonwet_original_ramp_and_lower_crossbeam_grooves'
WORLD = BASE / 'WORLD_R52'
REPORT_SHA = 'e43ab0f4f880488a8533e63ae6ffd060df53a1f2df2f6f7afd38c035d7a80da5'
CELLS_SHA = 'c1bc3b13af881dab3100905a46b2bb327bc991989be0a636bda72502355a985f'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_points(points):
    selected, grouped = defaultdict(set), defaultdict(set)
    for x, y, z in points:
        selected[x // 16, z // 16].add(y // 16)
        grouped[x // 16, z // 16, y // 16].add((x, y, z))
    actual = {}
    for cx, cz, sy, palette, data in iter_selected_sections(WORLD, 'projectseele:geofront', selected):
        for x, y, z in grouped[cx, cz, sy]:
            actual[x, y, z] = palette[int(data[(y % 16) * 256 + (z % 16) * 16 + x % 16])]
    if set(actual) != set(points):
        raise ValueError('Every finite requested cell must be measured in the actual world')
    return actual, selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--review-receipt', type=Path,
                        help='Independent current-world shell/interface review required to apply')
    args = parser.parse_args()
    assert not list((OUT / STAGE).glob('applied_*')), 'Do not replay an installed patch'
    assert sha(REPORT) == REPORT_SHA and sha(CELLS) == CELLS_SHA
    report = json.loads(REPORT.read_text(encoding='utf8'))
    for path, digest in report['source_locks'].items():
        assert sha(path) == digest, ('Changed actual geometry or original interfaces', path)
    assert not any(report['static_candidates_protected_set_overlap'].values())
    candidates = {tuple(row['position']): row for row in report['static_candidates']}
    with np.load(CELLS, allow_pickle=False) as source:
        cells = {tuple(map(int, pos)): str(state)
                 for pos, state in zip(source['positions'], source['before'], strict=True)}
    assert len(cells) == len(candidates) == 2943
    assert cells == {pos: row['before'] for pos, row in candidates.items()}
    held = {tuple(row['position']) for row in report['floor_material_requires_personnel_interface_review']}
    assert len(held) == 42 and all(p[1] == -679 and cells[p] == 'projectseele:nerv_floor_panel' for p in held)
    dynamic = {tuple(row['position']): row['before'] for row in report['dynamic_gate_candidates']}
    assert len(dynamic) == 6 and not set(dynamic) & set(cells)
    selected_cells = {p: state for p, state in cells.items() if p not in held}
    assert len(selected_cells) == 2901
    actual, selected = read_points(set(cells) | set(dynamic))
    assert all(actual[p] == state for p, state in (cells | dynamic).items()), 'World changed after triangle measurement'
    low = tuple(min(p[i] for p in selected_cells) for i in range(3))
    high = tuple(max(p[i] for p in selected_cells) for i in range(3))
    tags = dict(iter_block_entities(WORLD, 'projectseele:geofront', low, high, selected_chunks=selected))
    assert not set(tags) & set(selected_cells), 'Never excavate a block-entity anchor'

    painter = vox.Painter(vertical_bounds=(-960, 320))
    for pos, state in sorted(selected_cells.items()):
        painter.exact((*pos, *pos), state, 'minecraft:air', 'R52_finite_actual_original_outer_guide_recess')
    painter.meta.update(root_author=True, evidence_sha256=REPORT_SHA, sparse_cells_sha256=CELLS_SHA,
                        source_locks=report['source_locks'], wet_floor_cells_held=sorted(held),
                        dynamic_front_gate_cells_preserved=sorted(dynamic),
                        bounded_only_candidate_count=len(report['ramp_only_bounded_unique_cells']),
                        bounding_box_is_not_an_excavation_mask=True)
    vox.WORLD, vox.OUT, vox.DIM = WORLD, OUT, 'projectseele:geofront'
    folder = painter.save_plan(STAGE)
    result = dict(schema='projectseele.r52.finite-original-guide-slots.v1', world_written=False,
                  cells=len(selected_cells), before_materials=dict(Counter(selected_cells.values())),
                  protected_wet_floor_count=42, original_dynamic_gate_cells_preserved=6,
                  actual_penetration_cells=2865, bounded_only_candidates=36,
                  source_locks=report['source_locks'], evidence_sha256=REPORT_SHA,
                  sparse_cells_sha256=CELLS_SHA, native_game_passed=False)
    if args.apply:
        assert args.review_receipt, 'Current shell and personnel interfaces must be reviewed before applying'
        review = json.loads(args.review_receipt.read_text(encoding='utf8'))
        assert review.get('schema') == 'projectseele.r52.original-guide-slots-interface-review.v1'
        assert review.get('evidence_sha256') == REPORT_SHA
        assert review.get('nonwet_cells') == 2901 and review.get('pending_count') == 0
        assert review.get('independent_interface_clear') is True
        assert review.get('root_apply_allowed') is True
        assert review.get('required_backing_cells') == [], 'Resolve actual backing before this finite-only patch'
        result['interface_review'] = dict(path=str(args.review_receipt), sha256=sha(args.review_receipt))
        lock = acquire_world_lock()
        try:
            for path, digest in review['source_locks'].items():
                assert sha(path) == digest, ('Changed shell/interface review source', path)
            neighbours_path = Path(review['current_states_file'])
            assert sha(neighbours_path) == review['current_states_sha256']
            neighbour_rows = json.loads(neighbours_path.read_text(encoding='utf8'))['positions']
            before_neighbours = {tuple(row['position']): row['state'] for row in neighbour_rows}
            assert len(before_neighbours) == len(neighbour_rows) == review['measured_cell_count']
            now, _ = read_points(set(before_neighbours))
            assert now == before_neighbours, 'Shell or personnel interface changed since independent readback'
            result.update(world_written=True, receipt=painter.apply(STAGE, session_lock=lock))
        finally:
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            lock.close()
    (folder / 'PLAN.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('source_locks', 'receipt')}), flush=True)


if __name__ == '__main__':
    main()
