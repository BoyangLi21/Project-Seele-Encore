"""Lay back stream and pond banks that stand as vertical walls over the water.

Inside --area, natural ground within --reach blocks of water is cut down to a bank that rises from the water edge:
water surface + 1 at the edge, then one block per --run blocks away (default 1.5, a 1:1.5 slope). Only cuts, never
fills, so the channel widens into a natural bank and nothing is raised. Regrading is terrain_regrade.apply_heights
(grass on top, trees on cut columns replanted at local density, ground cover). The new edge gets reeds (sugar cane),
ferns, tall grass and the odd bank stone (andesite, mossy cobblestone).

Columns within 2 of anything built, other sessions' pending columns and unloaded chunks are kept, and the bank climbs
back to them at a slope of one.

    plan_stream_banks.py --world W --mosaic DIR --area x0 x1 z0 z1 --out DIR [--run 1.5] [--reach 10] [--keep-file F]
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
    p.add_argument('--run', type=float, default=1.5)
    p.add_argument('--reach', type=int, default=10)
    p.add_argument('--max-cut', type=int, default=1000, help='deepest cut per column')
    p.add_argument('--one-side', action='store_true', help='lay back only one bank of each channel (east or south)')
    p.add_argument('--keep-file', type=Path)
    p.add_argument('--seed', type=int, default=41)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    x0, x1, z0, z1 = a.area
    m = a.reach + 6
    ox, oz = (int(v) for v in np.load(a.mosaic / 'origin.npy'))
    g = np.array(np.load(a.mosaic / 'ground.npy', mmap_mode='r')[z0 - m - oz:z1 + m - oz + 1, x0 - m - ox:x1 + m - ox + 1])
    g = g[g > -30000]
    box = tr.Box(a.world, x0 - m, x1 + m, int(g.min()) - 8, int(g.max()) + 40, z0 - m, z1 + m)
    bx, by, bz = box.origin
    k = box.kind_grid()
    ground = tr.top_of(k == tr.SOIL, by)
    fluid_top = tr.top_of(k == tr.FLUID, by)
    wet = fluid_top >= ground
    yy = np.arange(k.shape[0])[:, None, None] + by
    built = ((k == tr.BUILT) & (yy >= ground[None] - 3)).any(0)
    kept = np.zeros(ground.shape, bool)
    if a.keep_file and a.keep_file.exists():
        for px, pz in json.loads(a.keep_file.read_text('utf8')):
            if bx <= px < bx + ground.shape[1] and bz <= pz < bz + ground.shape[0]:
                kept[pz - bz, px - bx] = True
    frozen = ndimage.binary_dilation(built, iterations=2) | kept | ~box.loaded | wet
    inside = np.zeros(ground.shape, bool)
    inside[z0 - bz:z1 - bz + 1, x0 - bx:x1 - bx + 1] = True
    dist, (iz, ix) = ndimage.distance_transform_edt(~wet, return_indices=True)
    level = fluid_top[iz, ix]
    bank = level + 1 + np.floor((dist - 1) / a.run)
    side = np.ones(ground.shape, bool)
    if a.one_side:
        # lay back only the bank on the east or south of each channel; the other side keeps its edge
        zz_, xx_ = np.mgrid[0:ground.shape[0], 0:ground.shape[1]]
        side = ((xx_ - ix) + (zz_ - iz)) > 0
    target = np.where(inside & ~frozen & side & (dist <= a.reach), np.minimum(ground, bank), ground).astype(float)
    hard = frozen & ~wet
    if hard.any():
        dh, (hz, hx) = ndimage.distance_transform_edt(~hard, return_indices=True)
        target = np.maximum(target, ground[hz, hx] - dh)
    target = np.minimum(target, ground)
    # where laying back would take more than --max-cut, leave the column: no new step is carved into the hill behind
    target = np.where(ground - target > a.max_cut, ground, target)
    target = np.where(frozen, ground, target)
    names = np.array([q.split('[')[0] for q in box.palette]).astype(str)
    wooded = ndimage.binary_dilation(np.char.endswith(names, '_leaves')[box.ids].any(0), iterations=2) & ~built
    chance = tr.local_tree_chances(box, 20, counts=wooded)
    keepout = ndimage.binary_dilation(built, iterations=3) | ndimage.binary_dilation(wet, iterations=2) | kept
    new_ids, change = tr.apply_heights(box, ground, target, frozen, rng_seed=a.seed, plant=inside & ~frozen, plant_keepout=keepout, chance=chance)
    # the water edge: reeds, ferns, tall grass, bank stones
    t = np.round(target).astype(int)
    edge = inside & ~frozen & (dist <= 1.5) & (t <= level + 1)
    rng = np.random.default_rng(a.seed)
    air = box.state_id(tr.AIR_STATE)
    grass_ids = {box.state_id(tr.GRASS), box.state_id(tr.DIRT)}
    cane = box.state_id('minecraft:sugar_cane[age=0]')
    fern = box.state_id('minecraft:fern')
    tall = (box.state_id('minecraft:tall_grass[half=lower]'), box.state_id('minecraft:tall_grass[half=upper]'))
    stones = [box.state_id('minecraft:andesite'), box.state_id('minecraft:mossy_cobblestone')]
    n_reed = n_stone = 0
    for z, x in zip(*np.nonzero(edge)):
        j = int(t[z, x]) - by
        if not (0 <= j and j + 3 < new_ids.shape[0] and new_ids[j, z, x] in grass_ids and new_ids[j + 1, z, x] == air):
            continue
        r = rng.random()
        if r < .22 and dist[z, x] == 1:
            h = 1 + int(rng.random() < .6)
            for d in range(1, h + 1):
                if new_ids[j + d, z, x] == air:
                    new_ids[j + d, z, x] = cane
            n_reed += 1
        elif r < .34 and new_ids[j + 2, z, x] == air:
            new_ids[j + 1, z, x], new_ids[j + 2, z, x] = tall
        elif r < .44:
            new_ids[j + 1, z, x] = fern
        elif r < .48:  # bank stones: half as many as the first pilot
            new_ids[j, z, x] = stones[int(rng.random() < .4)]
            n_stone += 1
    rows = tr.rows_between(box, new_ids)
    tr.write_rows(a.out / 'rows.json', rows)
    rep = dict(cells=len(rows), cut_columns=int((change & (t < ground)).sum()), max_cut=int((ground - t)[change].max()) if change.any() else 0,
               reeds=n_reed, bank_stones=n_stone, area=a.area, run=a.run)
    (a.out / 'report.json').write_text(json.dumps(rep, indent=1), 'utf8')
    print(json.dumps(rep))


if __name__ == '__main__':
    main()
