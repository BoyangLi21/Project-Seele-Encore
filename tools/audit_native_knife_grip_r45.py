"""Check actual submitted hand/knife surfaces, including stance and attack frames.

This verifies geometry, not a rendered artistic judgement. Coordinates come
from the native draw submissions; no authoring pose is substituted.
"""
from pathlib import Path
import argparse
import json
import sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri


def crossing(first, second):
    for tri, other in ((first, second), (second, first)):
        for i in range(3):
            start = tri[i]
            direction = tri[(i + 1) % 3] - start
            length2 = direction.length_squared
            if length2 < 1e-16:
                continue
            hit = intersect_ray_tri(*other, direction, start, True)
            if hit is not None and 1e-5 < (hit - start).dot(direction) / length2 < 1 - 1e-5:
                return True
    return False


def surface(row, geometry, origin):
    points = np.asarray(geometry[row['resource_part']]['original_part_xyz']).reshape(-1, 3).copy()
    changes = np.asarray(row['submitted_position_changes_index_xyz']).reshape(-1, 4)
    points[changes[:, 0].astype(int)] = changes[:, 1:]
    points = (points + row['part_pivot_authored']) * [-1, 1, 1] / 16
    matrix = np.asarray(row['mesh_to_world_column_major']).reshape(4, 4).T
    world = points @ matrix[:3, :3].T + matrix[:3, 3]
    indices = np.asarray(row['actual_world_sample_vertex_indices'], int)
    error = float(np.abs(world[indices] - np.asarray(row['actual_world_sample_xyz']).reshape(-1, 3)).max())
    assert error < .01, 'Native geometry reconstruction differs from draw readback'
    return world - origin, error


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--witness', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--against', default='hand_r')
    p.add_argument('--weapon', choices=['knife','cannon'], default='knife')
    args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
    geometry, frames = {}, {}
    for line in args.witness.open(encoding='utf8'):
        row = json.loads(line)
        kind = row['kind']
        if kind == 'actual_static_part_geometry':
            geometry[row['resource_part']] = row
        elif kind == 'final_named_palette':
            frames[row['tick']] = dict(palette=row, parts={})
        elif kind == 'actual_cpu_submitted_part' and row['bone'] in (args.against, args.weapon):
            frames[row['tick']]['parts'][row['bone']] = row
    report = []
    for tick, frame in frames.items():
        if args.weapon not in frame['parts'] or args.against not in frame['parts']:
            continue
        palette = frame['palette']
        origin = np.asarray(palette['model_to_world_column_major']).reshape(4, 4).T[:3, 3]
        hand, errh = surface(frame['parts'][args.against], geometry, origin)
        knife, errk = surface(frame['parts'][args.weapon], geometry, origin)
        hv, kv = [Vector(v) for v in hand], [Vector(v) for v in knife]
        hf, kf = np.arange(len(hand)).reshape(-1, 3), np.arange(len(knife)).reshape(-1, 3)
        ht = BVHTree.FromPolygons(hv, hf.tolist(), all_triangles=True)
        kt = BVHTree.FromPolygons(kv, kf.tolist(), all_triangles=True)
        hits = [(h, k) for h, k in ht.overlap(kt)
                if crossing([hv[i] for i in hf[h]], [kv[i] for i in kf[k]])]
        report.append(dict(tick=tick, stance=palette['stance'],
                           inputs=palette['actual_owner_inputs'], triangle_crossings=len(hits),
                           max_world_readback_error=max(errh, errk), examples=hits[:12]))
        print(tick, len(hits), flush=True)
    assert report, 'No actual '+args.weapon+' submissions'
    args.out.write_text(json.dumps(dict(weapon=args.weapon,against=args.against,samples=len(report), frames=report,
        geometric_clear=all(r['triangle_crossings'] == 0 for r in report), visual_accepted=False), indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
