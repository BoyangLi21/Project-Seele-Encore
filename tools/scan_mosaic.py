"""Stitch the per-region npz files of scan_surface_columns.py into one folder of whole-map .npy layers.

Layers: ground, solid, top, water (int16, -32768 = no data) and ground_id, solid_id, top_id (uint16 indices
into one shared palette.npy). origin.npy holds the block x, z of element [0, 0]; scan_terrain_seams.py
assumes -5120, -8704, which is where the Hakone regions start.
"""
import argparse
import re
from pathlib import Path

import numpy as np

NONE = -32768


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scan', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--origin', type=int, nargs=2, default=[-5120, -8704])
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    files = {}
    for f in a.scan.glob('r.*.npz'):
        m = re.match(r'r\.(-?\d+)\.(-?\d+)\.npz', f.name)
        files[(int(m[1]), int(m[2]))] = f
    rx0, rz0 = a.origin[0] // 512, a.origin[1] // 512
    rx1 = max(r[0] for r in files) + 1
    rz1 = max(r[1] for r in files) + 1
    w, h = (rx1 - rx0) * 512, (rz1 - rz0) * 512
    heights = {k: np.full((h, w), NONE, np.int16) for k in ('ground', 'solid', 'top', 'water')}
    ids = {k: np.zeros((h, w), np.uint16) for k in ('ground_id', 'solid_id', 'top_id')}
    palette, lookup = [], {}
    for (rx, rz), f in sorted(files.items()):
        if rx < rx0 or rz < rz0:
            continue
        d = np.load(f)
        local = [str(s) for s in d['palette']]
        remap = np.array([lookup.setdefault(s, len(lookup)) for s in local] or [0], np.uint16)
        for s in local:
            if len(palette) < len(lookup):
                palette.append(s)
        z, x = (rz - rz0) * 512, (rx - rx0) * 512
        for k in heights:
            heights[k][z:z + 512, x:x + 512] = d[k]
        for k in ids:
            ids[k][z:z + 512, x:x + 512] = remap[d[k]]
    palette = [s for s, _ in sorted(lookup.items(), key=lambda kv: kv[1])]
    for k, v in {**heights, **ids}.items():
        np.save(a.out / f'{k}.npy', v)
    np.save(a.out / 'palette.npy', np.array(palette))
    np.save(a.out / 'origin.npy', np.array(a.origin))
    print(f'{len(files)} regions, {w} x {h} columns, {len(palette)} states')


if __name__ == '__main__':
    main()
