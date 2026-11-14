"""Round off blocky lattice terrain (straight, right-angled 1-block steps laid out on a grid) inside one area.

The natural ground moves toward a Gaussian-smoothed copy of itself (normalised over natural columns, so buildings and
water do not drag it). The move fades in over --blend blocks from the area edge, and near anything kept (buildings,
water, other sessions' pending columns, unloaded chunks) the new ground climbs back to the kept height at a slope of
one. Cut and filled columns are regraded by terrain_regrade.apply_heights: grass on top, dirt below, trees standing on
changed columns replanted at the density of the woods around them, ground cover on the new slopes.

    plan_area_smoothing.py --world W --mosaic DIR --area x0 x1 z0 z1 --out DIR [--sigma 5] [--blend 24] [--keep-file F]
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--mosaic', type=Path, required=True)
    p.add_argument('--area', type=int, nargs=4, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--sigma', type=float, default=5)
    p.add_argument('--blend', type=float, default=24)
    p.add_argument('--keep-file', type=Path)
    p.add_argument('--seed', type=int, default=31)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    x0, x1, z0, z1 = a.area
    m = int(3 * a.sigma) + 4
    ox, oz = (int(v) for v in np.load(a.mosaic / 'origin.npy'))
    g = np.load(a.mosaic / 'ground.npy', mmap_mode='r')[z0 - m - oz:z1 + m - oz + 1, x0 - m - ox:x1 + m - ox + 1]
    g = np.array(g)[np.array(g) > -30000]
    box = tr.Box(a.world, x0 - m, x1 + m, int(g.min()) - 12, int(g.max()) + 40, z0 - m, z1 + m)
    bx, by, bz = box.origin
    k = box.kind_grid()
    ground = tr.top_of(k == tr.SOIL, by)
    yy = np.arange(k.shape[0])[:, None, None] + by
    built = ((k == tr.BUILT) & (yy >= ground[None] - 3)).any(0)
    wet = (tr.top_of(k == tr.FLUID, by) >= ground)
    kept = np.zeros(ground.shape, bool)
    if a.keep_file and a.keep_file.exists():
        for px, pz in json.loads(a.keep_file.read_text('utf8')):
            if bx <= px < bx + ground.shape[1] and bz <= pz < bz + ground.shape[0]:
                kept[pz - bz, px - bx] = True
    frozen = ndimage.binary_dilation(built, iterations=2) | ndimage.binary_dilation(wet | kept, iterations=1) | ~box.loaded
    w = (~frozen).astype(float)
    gf = ground.astype(float)
    smooth = ndimage.gaussian_filter(gf * w, a.sigma) / np.maximum(ndimage.gaussian_filter(w, a.sigma), 1e-6)
    inside = np.zeros(ground.shape, bool)
    inside[z0 - bz:z1 - bz + 1, x0 - bx:x1 - bx + 1] = True
    fade = np.clip(ndimage.distance_transform_edt(inside) / a.blend, 0, 1)
    target = gf + fade * (smooth - gf)
    # climb back to anything kept at a slope of one
    if frozen.any():
        d = ndimage.distance_transform_edt(~frozen, return_indices=True)
        dist, (iz, ix) = d
        anchor = gf[iz, ix]
        target = np.clip(target, anchor - dist, anchor + dist)
    target = np.where(frozen | ~inside, gf, target)
    names = np.array([q.split('[')[0] for q in box.palette]).astype(str)
    wooded = ndimage.binary_dilation(np.char.endswith(names, '_leaves')[box.ids].any(0), iterations=2) & ~built
    chance = tr.local_tree_chances(box, 20, counts=wooded)
    keepout = ndimage.binary_dilation(built, iterations=3) | wet | kept
    new_ids, change = tr.apply_heights(box, ground, target, frozen, rng_seed=a.seed, plant=inside & ~frozen, plant_keepout=keepout, chance=chance)
    rows = tr.rows_between(box, new_ids)
    tr.write_rows(a.out / 'rows.json', rows)
    t = np.round(target).astype(int)
    rep = dict(cells=len(rows), changed_columns=int(change.sum()), cut_columns=int((change & (t < ground)).sum()), fill_columns=int((change & (t > ground)).sum()),
               max_cut=int((ground - t)[change].max()) if change.any() else 0, max_fill=int((t - ground)[change].max()) if change.any() else 0, area=a.area, sigma=a.sigma)
    (a.out / 'report.json').write_text(json.dumps(rep, indent=1), 'utf8')
    print(json.dumps(rep))


if __name__ == '__main__':
    main()
