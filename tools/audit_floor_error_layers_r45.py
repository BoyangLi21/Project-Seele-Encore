"""Locate rigid limb floor errors across actually recorded pose stages.

Uses the original rigid surface at each stage. Seam-skinned final surfaces
are a separate witness; this audit does not pretend to replay skin per stage.
"""
from pathlib import Path
import argparse
import json
import numpy as np


def matrix(values):
    return np.array(values).reshape(4, 4).T


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--native', type=Path, required=True)
    p.add_argument('--floor-y', type=float, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    assert not a.out.exists()
    layers_path = next((a.native / 'native/native_media').rglob('body_layers_r40.json'))
    layers = json.loads(layers_path.read_text('utf8'))['samples']
    by_tick = {}
    for row in layers:
        by_tick.setdefault(row['tick'], []).append(row)
    static = {}
    palette = None
    rows = []
    for line in (a.native / 'hand_vertices.jsonl').open(encoding='utf8'):
        r = json.loads(line)
        if r['kind'] == 'actual_static_part_geometry':
            static[r['resource_part']] = r
        elif r['kind'] == 'final_named_palette':
            palette = r
        elif r['kind'] == 'actual_cpu_submitted_part' and r['bone'] in ('forearm_l', 'forearm_r', 'shin_l', 'shin_r'):
            assert palette['frame'] == r['frame']
            candidates = by_tick.get(r['tick'], [])
            if not candidates:
                continue
            layer = min(candidates, key=lambda x: abs(x['partial'] - palette['partial']))
            # A nearby tick is not evidence of the same sampled pose.
            if abs(layer['partial'] - palette['partial']) > .0001:
                continue
            vertices = np.array(static[r['resource_part']]['original_part_xyz']).reshape(-1, 3)
            vertices = (vertices + r['part_pivot_authored']) * [-1, 1, 1] / 16
            world = matrix(palette['model_to_world_column_major'])
            actual = matrix(r['mesh_to_world_column_major'])
            observations = []
            for stage, bones in layer['layers'].items():
                if r['bone'] not in bones:
                    continue
                transform = world @ matrix(bones[r['bone']]['matrix'])
                points = vertices @ transform[:3, :3].T + transform[:3, 3]
                observations.append(dict(stage=stage, rigid_surface_minimum_y_m=float(points[:, 1].min() - a.floor_y),
                                         matrix_max_difference_from_actual_draw=float(np.abs(transform - actual).max())))
            rows.append(dict(tick=r['tick'], review_tick=layer['review_tick'], bone=r['bone'],
                             same_partial=palette['partial'], stages=observations,
                             actual_rigid_minimum_y_m=float((vertices @ actual[:3, :3].T + actual[:3, 3])[:, 1].min() - a.floor_y)))
    assert rows, 'No exact same-tick/partial pose stage witness'
    result = dict(scope='Exact same-tick and partial pose matrices, original rigid limb surfaces; CPU seam skin not re-evaluated per stage',
                  floor_y=a.floor_y, rows=rows, native_art_accepted=False)
    a.out.write_text(json.dumps(result, indent=2), encoding='utf8')
    for bone in ('forearm_l', 'forearm_r', 'shin_l', 'shin_r'):
        row = min((r for r in rows if r['bone'] == bone), key=lambda r: r['actual_rigid_minimum_y_m'])
        print(bone, row['review_tick'], [(s['stage'], round(s['rigid_surface_minimum_y_m'], 4)) for s in row['stages']])


if __name__ == '__main__':
    main()
