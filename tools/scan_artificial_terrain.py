"""Survey what still reads as artificial in natural terrain, from a scan mosaic, ranked by visibility from roads and
buildings (the vis layer of scan_bare_faces.py).

    cliff    straight axis-aligned steps: runs of >= 16 columns along x or z where the ground steps by >= 3 at the same
             line; the share falling on chunk borders (x or z multiple of 16) is reported separately
    flat     natural land that is perfectly flat (no height change) over a 33x33 window, raised above its surroundings
             (plateau) or not (flat lowland)
    border   straight borders between natural top blocks (grass, sand, gravel, dirt, podzol, stone...): runs of >= 24
             columns along x or z where the block type changes on the same line
    shore    columns standing >= 3 above the water next to them (from scan_bare_faces.py)

Each kind is pooled into 64-block cells, scored by amount x visibility, and the top cells are listed.

    scan_artificial_terrain.py --mosaic DIR --faces DIR --out DIR
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

NATURAL = ('grass_block', 'dirt', 'coarse_dirt', 'podzol', 'rooted_dirt', 'gravel', 'stone', 'andesite', 'diorite',
           'granite', 'tuff', 'moss_block', 'sand', 'clay', 'mud', 'calcite', 'mycelium', 'snow_block', 'red_sand')


def runs_along(mask, axis, min_len):
    """Columns belonging to runs of True of at least min_len along axis."""
    m = mask if axis == 1 else mask.T
    out = np.zeros_like(m)
    for i in range(m.shape[0]):
        row = m[i]
        if not row.any():
            continue
        d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        for s, e in zip(starts, ends):
            if e - s >= min_len:
                out[i, s:e] = True
    return out if axis == 1 else out.T


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mosaic', type=Path, required=True)
    p.add_argument('--faces', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cell', type=int, default=64)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    M = a.mosaic
    pal = np.load(M / 'palette.npy', allow_pickle=True)
    names = np.array([q.split('[')[0].split(':')[-1] for q in pal])
    ox, oz = (int(v) for v in np.load(M / 'origin.npy'))
    ground = np.load(M / 'ground.npy')
    solid = np.load(M / 'solid.npy')
    water = np.load(M / 'water.npy')
    have = ground > -30000
    wet = water > -30000
    gtype = np.load(M / 'ground_id.npy')
    nat_ids = np.nonzero(np.isin(names, NATURAL))[0]
    natural = have & ~wet & (solid <= ground) & np.isin(gtype, nat_ids)
    del solid
    f = np.load(a.faces / 'faces.npz')
    vis = f['vis'].astype(np.float32)
    shore = f['shore'] >= 3
    res = {}

    # straight steps: the step between column i and i+1 along each axis
    g = ground.astype(np.int16)
    step_x = np.zeros(g.shape, bool)
    step_x[:, :-1] = (np.abs(np.diff(g, axis=1)) >= 3) & natural[:, :-1] & natural[:, 1:]
    step_z = np.zeros(g.shape, bool)
    step_z[:-1] = (np.abs(np.diff(g, axis=0)) >= 3) & natural[:-1] & natural[1:]
    # a step at fixed x running along z is a straight line north-south
    cliff_ns = runs_along(step_x, 0, 16)
    cliff_ew = runs_along(step_z, 1, 16)
    xs = np.arange(g.shape[1]) + ox
    zs = np.arange(g.shape[0]) + oz
    on_chunk_x = ((xs + 1) % 16 == 0)[None, :]
    on_chunk_z = ((zs + 1) % 16 == 0)[:, None]
    straight = cliff_ns | cliff_ew
    chunk_aligned = (cliff_ns & on_chunk_x) | (cliff_ew & on_chunk_z)
    res['cliff'] = dict(columns=int(straight.sum()), on_chunk_border=int(chunk_aligned.sum()),
                        chunk_border_share=round(float(chunk_aligned.sum() / max(straight.sum(), 1)), 3), chance_share=round(1 / 16, 3))
    del step_x, step_z

    # perfectly flat natural land
    k = 33
    gf = g.astype(np.float32)
    mx = ndimage.maximum_filter(np.where(natural, gf, -1e4), k)
    mn = ndimage.minimum_filter(np.where(natural, gf, 1e4), k)
    flat = natural & (mx == mn)
    surround = ndimage.uniform_filter(np.where(have, gf, gf[have].mean()), 129)
    plateau = flat & (gf > surround + 4)
    res['flat'] = dict(columns=int(flat.sum()), plateau_columns=int(plateau.sum()))
    del mx, mn, surround

    # straight borders between natural block types
    t = gtype
    bx = np.zeros(g.shape, bool)
    bx[:, :-1] = (t[:, :-1] != t[:, 1:]) & natural[:, :-1] & natural[:, 1:]
    bz = np.zeros(g.shape, bool)
    bz[:-1] = (t[:-1] != t[1:]) & natural[:-1] & natural[1:]
    border = runs_along(bx, 0, 24) | runs_along(bz, 1, 24)
    res['border'] = dict(columns=int(border.sum()))
    del bx, bz
    res['shore'] = dict(columns=int(shore.sum()))

    c = a.cell
    H, W = g.shape[0] // c, g.shape[1] // c

    def pool(arr):
        return arr[:H * c, :W * c].reshape(H, c, W, c).sum((1, 3))
    v = pool(vis) / (c * c)
    layers = dict(cliff=straight, flat=plateau, flat_lowland=flat & ~plateau, border=border, shore=shore)
    tops = {}
    for name, arr in layers.items():
        amount = pool(arr.astype(np.int32))
        score = amount * v
        order = np.argsort(score.ravel())[::-1]
        lst = []
        for i in order[:30]:
            r, q = divmod(int(i), W)
            if score[r, q] <= 0:
                break
            lst.append(dict(x=ox + q * c + c // 2, z=oz + r * c + c // 2, columns=int(amount[r, q]), visibility=round(float(v[r, q]), 2), score=round(float(score[r, q]))))
        tops[name] = lst
    (a.out / 'artificial.json').write_text(json.dumps(dict(total=res, top=tops), indent=1), 'utf8')
    np.savez_compressed(a.out / 'artificial.npz', cliff=straight, chunk=chunk_aligned, flat=flat, plateau=plateau, border=border, origin=np.array([ox, oz]))
    print(json.dumps(res))
    for name, lst in tops.items():
        print(name, lst[:8])


if __name__ == '__main__':
    main()
