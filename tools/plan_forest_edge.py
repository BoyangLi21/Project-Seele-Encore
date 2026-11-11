"""Feather a straight forest edge found by scan_terrain_seams.py (kind trees).

The forest on one side of an axis line stops dead and the other side is bare grass, the mark
of a planting area's border rather than of the land. Trees are planted on the bare side with a
chance that falls from 0.85 at the line to nothing at --depth columns, plus a low-frequency
noise so the new edge wanders. Only on grass, clear of anything built, water and the columns
around them, with the forest tool's trees.
"""
import argparse
import json
from pathlib import Path
import random

import numpy as np
from scipy import ndimage

import terrain_regrade as tr


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--seams', type=Path, required=True)
    p.add_argument('--ids', type=int, nargs='+', required=True)
    p.add_argument('--depth', type=int, default=56)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    seams = {s['id']: s for s in json.loads(a.seams.read_text('utf8'))['seams']}
    rows, report = [], []
    for n, sid in enumerate(a.ids):
        s = seams[sid]
        along_x = s['direction'] < 45 or s['direction'] > 135
        m = a.depth + 12
        x0, x1 = s['x'][0] - (12 if along_x else m), s['x'][1] + (12 if along_x else m)
        z0, z1 = s['z'][0] - (m if along_x else 12), s['z'][1] + (m if along_x else 12)
        box = tr.Box(a.world, x0, x1, -64, 250, z0, z1)
        by = box.origin[1]
        k = box.kind_grid()
        ground = tr.top_of(k == tr.SOIL, by)
        names = np.array([q.split('[')[0] for q in box.palette])
        trees = np.isin(k, (tr.SOFT,)) & np.char.endswith(names.astype(str), ('_leaves'))[box.ids]
        canopy = trees.any(0)
        built = ((k == tr.BUILT) | (k == tr.FLUID)).any(0)
        keepout = ndimage.binary_dilation(built, iterations=4) | ~box.loaded
        line = (s['z'][0] + s['z'][1]) // 2 - z0 if along_x else (s['x'][0] + s['x'][1]) // 2 - x0
        coord = np.arange(ground.shape[0])[:, None] if along_x else np.arange(ground.shape[1])[None, :]
        coord = np.broadcast_to(coord, ground.shape)
        before_side, after_side = coord < line, coord > line
        bare = after_side if canopy[before_side].mean() > canopy[after_side].mean() else before_side
        dist = np.abs(coord - line).astype(float)
        rng = np.random.default_rng(300 + sid)
        wobble = ndimage.gaussian_filter(rng.standard_normal(ground.shape), 9)
        wobble /= wobble.std() + 1e-9
        reach = a.depth * (1 + .35 * wobble)
        chance = np.clip(.85 * np.maximum(0, 1 - dist / np.maximum(reach, 1)) ** 1.3, 0, .85)
        span = np.zeros(ground.shape, bool)
        if along_x:
            span[:, s['x'][0] - x0:s['x'][1] - x0 + 1] = True
        else:
            span[s['z'][0] - z0:s['z'][1] - z0 + 1, :] = True
        span = ndimage.binary_dilation(span, iterations=8)
        where = bare & span & ~keepout & (chance > 0)
        ids = box.ids.copy()
        tr.replant(box, ids, ground, where, keepout, random.Random(400 + sid), chance=chance)
        r = tr.rows_between(box, ids)
        rows += r
        report.append(dict(seam=sid, line='z=%d' % (line + z0) if along_x else 'x=%d' % (line + x0), box=[x0, z0, x1, z1], cells=len(r),
                           log_cells=sum(1 for q in r if q[4].split('[')[0].endswith('_log'))))
        print(json.dumps(report[-1]), flush=True)
    seen = set()
    for row in rows:
        if tuple(row[:3]) in seen:
            raise SystemExit(f'{row[:3]} planned twice')
        seen.add(tuple(row[:3]))
    tr.write_rows(a.out / 'rows.json', rows)
    (a.out / 'report.json').write_text(json.dumps(dict(cells=len(rows), seams=report), indent=1), 'utf8')


if __name__ == '__main__':
    main()
