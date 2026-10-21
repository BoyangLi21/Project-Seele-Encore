"""Check supplied carrier surfaces against original EVA meshes and native frames.

Frames must be read from the installed CarrierAssemblyR53 profile. This audit
does not reproduce its actuator implementation. Edge crossings are a diagnostic,
not a substitute for native visual review or route/obstacle checks.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from audit_r53_rifle_chest_intersections import intersections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mesh', type=Path, required=True)
    parser.add_argument('--frames', type=Path, required=True)
    parser.add_argument('--bodies', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    doc = json.loads(args.mesh.read_text('utf8'))
    native = json.loads(args.frames.read_text('utf8'))
    parts = {n: np.asarray(v).reshape(-1, 3, 8)[:, :, :3]
             for n, v in doc['parts'].items()}
    assert {n: len(v) for n, v in parts.items()} == native['triangles']
    rows = []
    for variant in (0, 1, 2):
        body = json.loads((args.bodies / f'unit0{variant}.json').read_text('utf8'))
        source = np.concatenate([np.asarray(v).reshape(-1, 3, 3)
                                 for v in body['parts'].values()])
        # The renderer's established root offset is also checked; collision
        # geometry itself remains in the unshifted physical frame.
        for offset in (0, .05):
            actual = source + [0, offset, 0]
            lo, hi = actual.min(1), actual.max(1)
            for frame in native['frames']:
                assert set(frame['translations']) == set(parts)
                hits = {}
                for name, vertices in parts.items():
                    posed = vertices + frame['translations'][name]
                    near = actual[((hi >= posed.min((0, 1))) &
                                   (lo <= posed.max((0, 1)))).all(1)]
                    count = intersections(posed, near) if len(near) else 0
                    if count:
                        hits[name] = count
                rows.append(dict(variant=variant, render_offset=offset,
                                 rise=frame['rise'], release=frame['release'],
                                 crossings=hits))
    result = dict(selection=native['selection'], samples=len(rows),
                  intersecting_samples=sum(bool(r['crossings']) for r in rows),
                  source_triangles=doc['source_triangles'], rows=rows)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))
    if result['intersecting_samples']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
