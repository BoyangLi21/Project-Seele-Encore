"""Darken a pale gravel beach into a mixed cobble shore and plant a coastal black-pine belt behind it.

Beach: columns whose top is gravel or sand next to the sea (within --beach of sea water). Their top two layers become
gravel, andesite, tuff and cobblestone in patches (value noise), with sand along the waterline.
Dune edge: grass columns within 3 blocks inland of the beach get grass and tall grass.
Pine belt: grass columns --belt-from to --belt-to blocks inland of the beach get black pines (spruce trunk, sometimes
leaning, flat umbrella crown of spruce leaves in one to three layers, the odd side branch) about one per --spacing
squared, and ferns and grass under them. Nothing within 3 blocks of roads or buildings, no other session's pending
columns, unloaded chunks left alone.

    plan_beach_pilot.py --world W --mosaic DIR --area x0 x1 z0 z1 --out DIR [--keep-file F]
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr
from plan_bare_faces import hash01, vnoise

LEAF = 'minecraft:spruce_leaves[distance=1,persistent=true,waterlogged=false]'


def pine(ids, j, z, x, rng, S, air):
    """Grow one black pine from ground cell (j, z, x); returns the cells set, or [] if it does not fit."""
    H, Z, X = ids.shape
    h = int(rng.integers(7, 11))
    lean = (0, 0)
    if rng.random() < .45:
        lean = [(1, 0), (-1, 0), (0, 1), (0, -1)][int(rng.integers(4))]
    cells = []
    cz, cx = z, x
    for d in range(1, h + 1):
        if d == h // 2 + 1 and lean != (0, 0):
            cz, cx = cz + lean[0], cx + lean[1]
        cells.append((j + d, cz, cx, S('minecraft:spruce_log[axis=y]')))
    top = j + h
    layers = [(0, 2.6), (1, 1.8)] + ([(2, 1.0)] if rng.random() < .5 else [])
    if rng.random() < .55:
        layers.append((-3, 1.6))
    for dy, r in layers:
        oz, ox = (cz, cx) if dy >= 0 else (cz + int(rng.integers(-2, 3)), cx + int(rng.integers(-2, 3)))
        ri = int(np.ceil(r))
        for dz in range(-ri, ri + 1):
            for dx in range(-ri, ri + 1):
                if dz * dz + dx * dx <= r * r + rng.random() * .8:
                    cells.append((top + dy, oz + dz, ox + dx, S(LEAF)))
    out = []
    for y, zz, xx, s in cells:
        if not (0 <= y < H and 0 <= zz < Z and 0 <= xx < X):
            return []
        if ids[y, zz, xx] != air and not (s != S(LEAF) and False):
            if ids[y, zz, xx] == S(LEAF):
                continue
            return []
        out.append((y, zz, xx, s))
    for y, zz, xx, s in out:
        if ids[y, zz, xx] == air or s != S(LEAF):
            ids[y, zz, xx] = s
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--mosaic', type=Path, required=True)
    p.add_argument('--area', type=int, nargs=4, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--beach', type=int, default=40)
    p.add_argument('--belt-from', type=int, default=3)
    p.add_argument('--belt-to', type=int, default=40)
    p.add_argument('--spacing', type=float, default=6)
    p.add_argument('--keep-file', type=Path)
    p.add_argument('--seed', type=int, default=81)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    x0, x1, z0, z1 = a.area
    m = 8
    ox, oz = (int(v) for v in np.load(a.mosaic / 'origin.npy'))
    g = np.array(np.load(a.mosaic / 'ground.npy', mmap_mode='r')[z0 - m - oz:z1 + m - oz + 1, x0 - m - ox:x1 + m - ox + 1])
    g = g[g > -30000]
    box = tr.Box(a.world, x0 - m, x1 + m, int(g.min()) - 4, int(g.max()) + 24, z0 - m, z1 + m)
    bx, by, bz = box.origin
    k = box.kind_grid()
    names = np.array([q.split('[')[0] for q in box.palette]).astype(str)
    ground = tr.top_of(k == tr.SOIL, by)
    fluid_top = tr.top_of(k == tr.FLUID, by)
    wet = fluid_top >= ground
    yy = np.arange(k.shape[0])[:, None, None] + by
    built = ((k == tr.BUILT) & (yy >= ground[None] - 2)).any(0)
    kept = np.zeros(ground.shape, bool)
    if a.keep_file and a.keep_file.exists():
        for px, pz in json.loads(a.keep_file.read_text('utf8')):
            if bx <= px < bx + ground.shape[1] and bz <= pz < bz + ground.shape[0]:
                kept[pz - bz, px - bx] = True
    j_top = np.clip(ground - by, 1, k.shape[0] - 2)
    top_name = names[np.take_along_axis(box.ids, j_top[None], 0)[0]]
    above_k = np.take_along_axis(k, (j_top + 1)[None], 0)[0]
    open_sky = above_k == tr.AIRK
    inside = np.zeros(ground.shape, bool)
    inside[z0 - bz:z1 - bz + 1, x0 - bx:x1 - bx + 1] = True
    # the sea: the large water body, not ditches
    lab, n = ndimage.label(wet)
    sizes = ndimage.sum(wet, lab, range(1, n + 1))
    sea = np.isin(lab, 1 + np.nonzero(sizes > 3000)[0]) if n else wet
    d_sea = ndimage.distance_transform_edt(~sea)
    keep = ndimage.binary_dilation(built, iterations=3) | kept | ~box.loaded
    shore = inside & ~keep & ~wet & np.isin(top_name, ['minecraft:gravel', 'minecraft:sand']) & (d_sea <= a.beach)
    lab_b, _ = ndimage.label(shore)
    beach = shore & np.isin(lab_b, np.unique(lab_b[shore & (d_sea <= 2)]))
    d_beach = ndimage.distance_transform_edt(~beach)
    ids = box.ids.copy()
    sid = {}

    def S(s):
        if s not in sid:
            sid[s] = box.state_id(s)
        return sid[s]
    air = S(tr.AIR_STATE)
    zz, xx = np.mgrid[0:ground.shape[0], 0:ground.shape[1]]
    wx, wz = xx + bx, zz + bz
    # coarse at the water, finer inland; three scales of noise and a per-block roll so no pattern repeats
    nmix = vnoise(wx, wz, 9, a.seed) * .45 + vnoise(wx, wz, 3, a.seed + 6) * .3 + hash01(wx, wz, a.seed + 1) * .25
    sand_patch = vnoise(wx, wz, 14, a.seed + 7)
    counts = dict(beach_columns=int(beach.sum()), pines=0, dune_plants=0, under_plants=0)
    zones = [(4, [('minecraft:cobblestone', .3), ('minecraft:andesite', .14), ('minecraft:stone', .16), ('minecraft:tuff', .16), ('minecraft:gravel', .19), ('minecraft:sand', .05)]),
             (12, [('minecraft:gravel', .32), ('minecraft:cobblestone', .2), ('minecraft:tuff', .18), ('minecraft:andesite', .1), ('minecraft:stone', .12), ('minecraft:sand', .08)]),
             (999, [('minecraft:gravel', .36), ('minecraft:tuff', .2), ('minecraft:cobblestone', .16), ('minecraft:sand', .08), ('minecraft:coarse_dirt', .08), ('minecraft:andesite', .12)])]
    for z, x in zip(*np.nonzero(beach)):
        j = int(ground[z, x]) - by
        mix = next(m_ for d_, m_ in zones if d_sea[z, x] <= d_)
        for d in (0, 1):
            if names[box.ids[j - d, z, x]] not in ('minecraft:gravel', 'minecraft:sand'):
                continue
            if sand_patch[z, x] > .88 and d_sea[z, x] > 2:
                s_ = 'minecraft:sand'
            else:
                u = (nmix[z, x] + .37 * d) % 1
                acc = 0
                for state, w in mix:
                    acc += w
                    if u < acc:
                        s_ = state
                        break
            ids[j - d, z, x] = S(s_)
    grassy = inside & ~keep & ~wet & (top_name == 'minecraft:grass_block') & open_sky
    dune = grassy & (d_beach <= 3)
    belt = grassy & (d_beach > a.belt_from)
    rng = np.random.default_rng(a.seed)
    for z, x in zip(*np.nonzero(dune)):
        j = int(ground[z, x]) - by
        u = rng.random()
        if u < .3 and ids[j + 2, z, x] == air:
            ids[j + 1, z, x], ids[j + 2, z, x] = S('minecraft:tall_grass[half=lower]'), S('minecraft:tall_grass[half=upper]')
            counts['dune_plants'] += 1
        elif u < .65:
            ids[j + 1, z, x] = S('minecraft:grass')
            counts['dune_plants'] += 1
    # pines scattered 4-6 apart in a belt whose depth wanders between 6 and 22 blocks (two to four trees deep)
    depth = 6 + 16 * vnoise(wx, wz, 30, a.seed + 8)
    belt &= d_beach <= depth
    taken = np.zeros(ground.shape, bool)
    cand = list(zip(*np.nonzero(belt)))
    rng.shuffle(cand)
    for z, x in cand:
        r = 2 + int(rng.random() * 2)
        if taken[max(0, z - r):z + r + 1, max(0, x - r):x + r + 1].any() or rng.random() > .55:
            continue
        j = int(ground[z, x]) - by
        if pine(ids, j, z, x, rng, S, air):
            taken[z, x] = True
            counts['pines'] += 1
    for z, x in zip(*np.nonzero(belt & ~taken)):
        j = int(ground[z, x]) - by
        if ids[j + 1, z, x] != air:
            continue
        u = rng.random()
        if u < .12:
            ids[j + 1, z, x] = S('minecraft:fern')
            counts['under_plants'] += 1
        elif u < .3:
            ids[j + 1, z, x] = S('minecraft:grass')
            counts['under_plants'] += 1
    rows = [r for r in tr.rows_between(box, ids) if x0 <= r[0] <= x1 and z0 <= r[2] <= z1]
    tr.write_rows(a.out / 'rows.json', rows)
    counts.update(cells=len(rows), area=a.area)
    (a.out / 'report.json').write_text(json.dumps(counts, indent=1), 'utf8')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
