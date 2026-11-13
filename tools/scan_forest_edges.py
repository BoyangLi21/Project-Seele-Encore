"""Find hard forest edges in a scan mosaic (scan_mosaic.py): dense canopy that stops dead against bare land.

Works on 4 x 4 block cells. A cell's canopy share is the share of its land columns (not water, not built,
not unscanned) whose top block is a leaf or a log above the ground. Forest is a lightly smoothed share of
at least --forest, bare at most --bare. For every forest cell on the forest's rim the distance to the nearest
bare cell measures the edge: a few cells means dense woods stop on a line, a wide band means they thin out.

Outputs in --out:
- cells.npz: per-cell share, land share, forest, bare, built-near and rim width arrays (for the planner);
- edges.json: hard edge pieces (connected rim cells of width <= --hard) with box, length, straightness,
  axis alignment and how much of the bare side is open land;
- profile.json: canopy share against distance from the forest rim, measured on the gradual edges;
- edges.png: overview (forest green, bare tan, built grey, water blue, hard edges red, gradual edges yellow).
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

NONE = -32768
CELL = 4


def cell_sum(a, c=CELL):
    h, w = a.shape[0] // c * c, a.shape[1] // c * c
    return a[:h, :w].reshape(h // c, c, w // c, c).sum(axis=(1, 3), dtype=np.int32)


def load(mosaic):
    pal = [str(s) for s in np.load(mosaic / 'palette.npy')]
    tree_ids = np.array([s.split('[')[0].endswith(('_leaves', '_log', '_wood')) for s in pal])
    ground = np.load(mosaic / 'ground.npy', mmap_mode='r')
    solid = np.load(mosaic / 'solid.npy', mmap_mode='r')
    top = np.load(mosaic / 'top.npy', mmap_mode='r')
    water = np.load(mosaic / 'water.npy', mmap_mode='r')
    top_id = np.load(mosaic / 'top_id.npy', mmap_mode='r')
    origin = np.load(mosaic / 'origin.npy')
    return pal, tree_ids, ground, solid, top, water, top_id, origin


def column_layers(mosaic, band=1024):
    """Per-cell sums computed in bands of rows so the full-size boolean layers never sit in memory at once."""
    pal, tree_ids, ground, solid, top, water, top_id, origin = load(mosaic)
    h, w = ground.shape
    out = {k: [] for k in ('land', 'canopy', 'built', 'water', 'valid', 'height')}
    for z in range(0, h, band):
        g = np.asarray(ground[z:z + band]).astype(np.int32)
        valid = g != NONE
        wet = (np.asarray(water[z:z + band]) != NONE) & (np.asarray(water[z:z + band]) >= g) & valid
        built = (np.asarray(solid[z:z + band]).astype(np.int32) > g) & valid & ~wet
        canopy = tree_ids[np.asarray(top_id[z:z + band])] & (np.asarray(top[z:z + band]).astype(np.int32) > g) & valid & ~built & ~wet
        land = valid & ~wet & ~built
        out['land'].append(cell_sum(land))
        out['canopy'].append(cell_sum(canopy))
        out['built'].append(cell_sum(built))
        out['water'].append(cell_sum(wet))
        out['valid'].append(cell_sum(valid))
        out['height'].append(cell_sum(np.where(valid, g, 0)))
    return {k: np.concatenate(v) for k, v in out.items()}, origin


def pieces(mask, width, origin, extra):
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        zz, xx = np.nonzero(lab[sl] == i)
        if len(zz) < 4:
            continue
        zz = zz + sl[0].start
        xx = xx + sl[1].start
        pts = np.stack([xx, zz], 1).astype(float)
        c = pts - pts.mean(0)
        ev, evec = np.linalg.eigh(np.cov(c.T) if len(pts) > 2 else np.eye(2))
        major = evec[:, 1]
        ang = float(np.degrees(np.arctan2(major[1], major[0])) % 180)
        axis_off = min(ang % 90, 90 - ang % 90)
        straight = float(np.sqrt(ev[1] / max(ev[0], 1e-6)))
        bx = origin[0] + CELL * np.array([xx.min(), xx.max() + 1])
        bz = origin[1] + CELL * np.array([zz.min(), zz.max() + 1])
        out.append(dict(id=len(out) + 1, cells=int(len(zz)), length=int(CELL * np.ptp(c @ major) + CELL), x=[int(bx[0]), int(bx[1])],
                        z=[int(bz[0]), int(bz[1])], direction=round(ang, 1), axis_offset=round(axis_off, 1), straightness=round(straight, 1),
                        mean_width=round(float(CELL * width[zz, xx].mean()), 1), **{k: round(float(v[zz, xx].mean()), 3) for k, v in extra.items()}))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mosaic', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--forest', type=float, default=.45)
    p.add_argument('--bare', type=float, default=.03)
    p.add_argument('--hard', type=int, default=4, help='rim width in cells (4 blocks) at or under which an edge is hard')
    p.add_argument('--soft', type=int, default=8, help='rim width in cells at or over which an edge counts as gradual')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    s, origin = column_layers(a.mosaic)
    n = CELL * CELL
    land_share = s['land'] / n
    share = np.where(s['land'] > 0, s['canopy'] / np.maximum(s['land'], 1), 0)
    # light smoothing over land only, so one tree or one gap does not decide
    wsum = ndimage.gaussian_filter(s['land'].astype(np.float32), 1)
    smooth = ndimage.gaussian_filter(s['canopy'].astype(np.float32), 1) / np.maximum(wsum, 1e-3)
    open_land = land_share >= .75
    forest = (smooth >= a.forest) & (land_share >= .5)
    bare = (smooth <= a.bare) & open_land
    built_near = ndimage.binary_dilation(s['built'] > 0, iterations=2)
    water_near = ndimage.binary_dilation(s['water'] > n // 2, iterations=1)
    nodata_near = ndimage.binary_dilation(s['valid'] < n, iterations=4)
    # bare land that is a road, a yard or the rim of the scan is not where the forest should go on
    bare_open = bare & ~built_near & ~nodata_near
    rim = forest & ndimage.binary_dilation(~forest, iterations=1)
    width = ndimage.distance_transform_edt(~bare_open)
    hard = rim & (width <= a.hard)
    soft = rim & (width >= a.soft) & ~nodata_near
    # how open the bare side is: share of bare cells within 6 cells of the rim
    near_bare = ndimage.uniform_filter(bare_open.astype(np.float32), 13)
    height = s['height'] / np.maximum(s['valid'], 1)
    gy, gx = np.gradient(ndimage.gaussian_filter(height, 1.5))
    slope = np.hypot(gx, gy) / CELL
    edges = pieces(hard, width, origin, dict(bare_side_open=near_bare, slope=slope))
    edges.sort(key=lambda e: -e['length'])
    for i, e in enumerate(edges, 1):
        e['id'] = i
    # density profile out from the rim of gradual edges: canopy share at each distance from forest
    dist_out = ndimage.distance_transform_edt(~forest)
    soft_zone = ndimage.binary_dilation(soft, iterations=12) & ~forest & open_land & ~built_near & ~nodata_near
    prof = []
    for d in range(1, 25):
        m = soft_zone & (np.round(dist_out) == d)
        prof.append(dict(blocks=d * CELL, cells=int(m.sum()), share=round(float(share[m].mean()), 3) if m.any() else None))
    hard_zone = ndimage.binary_dilation(hard, iterations=12) & ~forest & open_land & ~built_near & ~nodata_near
    prof_hard = []
    for d in range(1, 25):
        m = hard_zone & (np.round(dist_out) == d)
        prof_hard.append(dict(blocks=d * CELL, cells=int(m.sum()), share=round(float(share[m].mean()), 3) if m.any() else None))
    np.savez_compressed(a.out / 'cells.npz', origin=origin, share=share.astype(np.float32), smooth=smooth.astype(np.float32), land=land_share.astype(np.float32),
                        forest=forest, bare=bare_open, built=s['built'] > 0, water=s['water'] > n // 2, hard=hard, soft=soft, width=width.astype(np.float32),
                        height=height.astype(np.float32))
    (a.out / 'edges.json').write_text(json.dumps(edges, indent=0), 'utf8')
    (a.out / 'profile.json').write_text(json.dumps(dict(gradual=prof, hard=prof_hard), indent=1), 'utf8')
    rgb = np.zeros(share.shape + (3,), np.uint8)
    rgb[:] = (205, 190, 140)
    rgb[s['valid'] < n // 2] = (30, 30, 30)
    g = np.clip(share * 255, 0, 255).astype(np.uint8)
    tree = share > .05
    rgb[tree] = np.stack([60 - g[tree] // 6, 150 - g[tree] // 3, 50 - g[tree] // 8], 1)
    rgb[s['built'] > n // 4] = (130, 130, 130)
    rgb[s['water'] > n // 2] = (60, 100, 200)
    rgb[ndimage.binary_dilation(soft, iterations=1)] = (240, 210, 40)
    rgb[ndimage.binary_dilation(hard, iterations=1)] = (230, 30, 30)
    Image.fromarray(rgb).save(a.out / 'edges.png')
    total = sum(e['length'] for e in edges)
    print(json.dumps(dict(forest_cells=int(forest.sum()), bare_cells=int(bare_open.sum()), hard_rim_cells=int(hard.sum()), soft_rim_cells=int(soft.sum()),
                          hard_pieces=len(edges), hard_length_blocks=total,
                          long_pieces=sum(1 for e in edges if e['length'] >= 64), straight_axis_pieces=sum(1 for e in edges if e['length'] >= 32 and e['straightness'] >= 6 and e['axis_offset'] <= 8))))
    print('gradual profile', [(q['blocks'], q['share']) for q in prof[:12]])
    print('hard profile   ', [(q['blocks'], q['share']) for q in prof_hard[:12]])


if __name__ == '__main__':
    main()
