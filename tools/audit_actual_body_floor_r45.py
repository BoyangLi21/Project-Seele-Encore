"""Measure actual submitted surfaces against an explicitly declared flat fixture.

This is not a world collision audit: floor height is supplied by the native
fixture, and every reconstruction must match the renderer's world samples.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np


def audit(path, floor_y):
    static = {}
    palette = None
    rows = []
    for line in path.open(encoding='utf8'):
        record = json.loads(line)
        kind = record['kind']
        if kind == 'actual_static_part_geometry':
            static[record['resource_part']] = record
        elif kind == 'final_named_palette':
            palette = record
        elif kind == 'actual_cpu_submitted_part':
            assert palette is not None and palette['frame'] == record['frame']
            vertices = np.array(static[record['resource_part']]['original_part_xyz']).reshape(-1, 3)
            original = vertices.copy()
            changes = np.array(record['submitted_position_changes_index_xyz']).reshape(-1, 4)
            vertices[changes[:, 0].astype(int)] = changes[:, 1:]
            vertices = (vertices + record['part_pivot_authored']) * [-1, 1, 1] / 16
            matrix = np.array(record['mesh_to_world_column_major']).reshape(4, 4).T
            original = (original + record['part_pivot_authored']) * [-1, 1, 1] / 16
            original = original @ matrix[:3, :3].T + matrix[:3, 3]
            vertices = vertices @ matrix[:3, :3].T + matrix[:3, 3]
            indices = record['actual_world_sample_vertex_indices']
            expected = np.array(record['actual_world_sample_xyz']).reshape(-1, 3)
            error = float(np.abs(vertices[indices] - expected).max())
            assert error < .01, (record['bone'], error)
            distance = vertices[:, 1] - floor_y
            rows.append(dict(tick=record['tick'], frame=record['frame'],
                             bone=record['bone'], stance=palette['stance'],
                             minimum_floor_distance_m=float(distance.min()),
                             rigid_before_cpu_skin_minimum_m=float(original[:, 1].min() - floor_y),
                             maximum_floor_distance_m=float(distance.max()),
                             vertices_below_5cm=int((distance < -.05).sum()),
                             vertex_count=len(vertices), reconstruction_error_m=error))
    assert rows
    summaries = {}
    for bone in sorted(set(r['bone'] for r in rows)):
        samples = [r for r in rows if r['bone'] == bone]
        summaries[bone] = dict(samples=len(samples),
                               worst_below_plane_m=min(r['minimum_floor_distance_m'] for r in samples),
                               largest_minimum_gap_m=max(r['minimum_floor_distance_m'] for r in samples),
                               frames_with_vertices_below_5cm=sum(r['vertices_below_5cm'] > 0 for r in samples))
    return dict(scope='Actual CPU submitted surfaces on declared flat native fixture only',
                input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), floor_y=floor_y,
                summary=summaries, rows=rows, visual_accepted=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--witness', type=Path, required=True)
    p.add_argument('--floor-y', type=float, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    assert not args.out.exists()
    result = audit(args.witness, args.floor_y)
    args.out.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result['summary'], indent=2))
