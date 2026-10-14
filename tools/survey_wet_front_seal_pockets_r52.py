"""Read actual native cells for the two orthogonal strokes of the wet seal.

The full L-shaped travel is not replaced by a rectangular excavation. This
file proposes no edits and never removes the closed wet-floor cells.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from fit_original_outer_guide_slots_r52 import read_points, WORLD, REPORT
from project_upright_gate_collisions_r52 import rigid
from query_blocks import iter_block_entities
from r52_spatial_plan import BASE

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / '.Codex/r52_continuous_route_migration_20261012'
SOURCE = P / '0262_BOTTOM_SEAL_V2_TRUE_L_SHAPE_RIG_MOTION_AND_PRIMITIVES.json'
OUT = BASE / 'continuous_upright/final_0262_wet_front_seals/v2_true_l_shape'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    global SOURCE, OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    SOURCE, OUT = args.source.resolve(), args.out.resolve()
    assert OUT.is_relative_to(BASE.resolve()) and not (OUT/'CURRENT_NATIVE_POCKET_SURVEY.json').exists()
    source = json.loads(SOURCE.read_text(encoding='utf8'))
    assert source['pairs'] == [] and source['actual_ramp_poses'] == 2493
    model = ROOT / 'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json'
    assert source['model_source_sha256'] == sha(model)
    original = json.loads(REPORT.read_text(encoding='utf8'))
    wet = {tuple(row['position']) for row in original['floor_material_requires_personnel_interface_review']}
    legacy = {tuple(row['position']) for row in original['static_candidates']} - wet
    requested, details, bearings = set(), [], []
    for gate in source['gates']:
        phases = {row['progress']: row for row in gate['actual_81_phases']}
        limits = {}
        for progress in (0, .25, 1):
            current = {}
            for item in phases[progress]['parts']:
                name = item['part']
                if not name.startswith('bottom_seal/'):
                    continue
                vertices = np.asarray(gate['actual_templates_rgb'][name], dtype=float).reshape(-1, 6)[:, :3]
                translation, rotation = rigid(item['world_frame'])
                points = vertices @ rotation.T + translation
                lo, hi = points.min(0), points.max(0)
                # Every actual new factory component is a cuboid, including
                # each individual wall of the telescoping hollow tube.
                corners = np.unique(np.round(points, 8), axis=0)
                assert len(corners) == 8 and all(np.all(np.isclose(p, lo, atol=1e-7) | np.isclose(p, hi, atol=1e-7)) for p in corners)
                current[name] = (lo, hi)
            limits[progress] = current
        assert set(limits[0]) == set(limits[.25]) == set(limits[1])
        for name in limits[0]:
            for start, end, axis in ((0, .25, 1), (.25, 1, 2)):
                a, b = limits[start][name], limits[end][name]
                unchanged = [i for i in range(3) if i != axis]
                assert np.allclose(a[0][unchanged], b[0][unchanged], atol=1e-7)
                assert np.allclose(a[1][unchanged], b[1][unchanged], atol=1e-7)
                lo, hi = np.minimum(a[0], b[0]), np.maximum(a[1], b[1])
                low, high = np.floor(lo + 1e-7).astype(int), np.ceil(hi - 1e-7).astype(int) - 1
                cells = {tuple(map(int, p)) for p in itertools.product(*(range(low[i], high[i] + 1) for i in range(3)))}
                requested.update(cells)
                details.append(dict(resource=gate['resource'], part=name, progress=[start, end],
                                    axis=axis, actual_swept_bounds=[lo.tolist(), hi.tolist()],
                                    cells=[list(p) for p in sorted(cells)]))
        for row in gate['native_wall_bearing_requests']:
            position = np.array([row['bearing'][k] for k in 'xyz'])
            normal = np.array([row['normal'][k] for k in 'xyz'])
            at = tuple(map(int, np.floor(position - normal * .01)))
            requested.add(at)
            bearings.append(dict(resource=gate['resource'], bearing=position.tolist(), normal=normal.tolist(), at=list(at)))
    # A one-cell shell read identifies whether a finite recess would open into
    # an unmeasured cavity. It is context, not permission to fill that shell.
    neighbours = requested | {tuple(p[i] + offset[i] for i in range(3)) for p in requested
                              for offset in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))}
    actual, selected = read_points(neighbours)
    low = tuple(min(p[i] for p in neighbours) for i in range(3))
    high = tuple(max(p[i] for p in neighbours) for i in range(3))
    tags = dict(iter_block_entities(WORLD, 'projectseele:geofront', low, high, selected_chunks=selected))
    for b in bearings:
        b['actual_state'] = actual[tuple(b['at'])]
    solids = [dict(position=list(p), before=actual[p], original_wet_floor=p in wet,
                   original_outer_slot_candidate=p in legacy, block_entity=p in tags)
              for p in sorted(requested) if actual[p] not in ('minecraft:air','minecraft:cave_air','minecraft:void_air')]
    report = dict(schema='projectseele.r52.wet-front-pocket-survey.v1', world=str(WORLD), world_written=False,
                  source_inputs={str(p): sha(p) for p in (SOURCE, REPORT, model,
                      ROOT/'src/main/java/com/projectseele/world/NervWetFloorSealR52.java',
                      ROOT/'src/main/java/com/projectseele/world/NervHangarGateGeometryR52.java')},
                  requested_cells=len(requested), current_solid_cells=solids, actual_two_stroke_sweeps=details,
                  bearings=bearings, block_entity_hits=[list(p) for p in tags if p in requested],
                  closed_wet_floor_cells_preserved=42, moving_boxes_are_actual_factory_cuboids=True,
                  native_motion_passed=False, root_civil_review_required=True)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'CURRENT_NATIVE_POCKET_SURVEY.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    coords=np.asarray(sorted(actual),np.int32)
    np.savez_compressed(OUT/'CURRENT_NATIVE_POCKET_CONTEXT.npz', positions=coords,
                        states=np.asarray([actual[tuple(p)] for p in coords]))
    print(json.dumps(dict(requested_cells=len(requested), context_cells=len(actual), solids=len(solids),
                          materials=dict(Counter(r['before'] for r in solids)),
                          wet_in_sweep=sum(r['original_wet_floor']for r in solids),
                          bearings=bearings, block_entity_hits=report['block_entity_hits'])),flush=True)


if __name__ == '__main__':
    main()
