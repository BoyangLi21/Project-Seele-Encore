"""Uncover a paved pad buried by later terrain; by default the NERV airport (x350..1350, z-177..86, pavement top y72) from the hill laid over it.

The pavement runs complete under the hill: a later terrain pass covered its north quarter
(about 61,000 columns, up to y118) and left sheer cut faces round the rest. Everything natural
above the pavement goes; outside it the hill is cut back to a slope of about 1 in 1.5 with a
three-block verge, rounded at the crest, and replanted. Built columns stay as they are.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr

PAVEMENT = {'minecraft:gray_concrete', 'minecraft:black_concrete', 'minecraft:white_concrete', 'minecraft:yellow_concrete',
            'minecraft:light_gray_concrete'}
APRON_Y = 72


def noise(shape, sigma, rng):
    f = ndimage.gaussian_filter(rng.standard_normal(shape), sigma)
    return f / (f.std() + 1e-9)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--slope', type=float, default=.68)
    p.add_argument('--verge', type=float, default=3)
    p.add_argument('--box', type=int, nargs=4, default=[180, 1530, -350, 250], help='x0 x1 z0 z1 of the area read and regraded')
    p.add_argument('--apron-y', type=int, default=APRON_Y, help='top of the pavement')
    p.add_argument('--rectangle', action='store_true', help='treat the bounding rectangle of the pavement as apron (buildings set into it included)')
    p.add_argument('--keep', type=Path, help='JSON list of [x0, z0, x1, z1] boxes another task owns; they and 8 columns round them stay as they are')
    a = p.parse_args()
    globals()["APRON_Y"] = a.apron_y
    a.out.mkdir(parents=True, exist_ok=True)
    box = tr.Box(a.world, a.box[0], a.box[1], APRON_Y - 17, 215, a.box[2], a.box[3])
    x0, y0, z0 = box.origin
    k = box.kind_grid()
    names = np.array([s.split('[')[0] for s in box.palette])
    pave = np.isin(names, list(PAVEMENT))
    foot = pave[box.ids[APRON_Y - y0]] | pave[box.ids[APRON_Y - 1 - y0]]
    lab, n = ndimage.label(foot)
    foot = ndimage.binary_fill_holes(lab == np.argmax(np.bincount(lab.ravel())[1:]) + 1)
    if a.rectangle:
        # The terminal strip has floors instead of pavement and would read as a notch of outside terrain.
        zz, xx = np.nonzero(foot)
        foot = np.zeros(foot.shape, bool)
        foot[zz.min():zz.max() + 1, xx.min():xx.max() + 1] = True
    ground = tr.top_of(k == tr.SOIL, y0)
    built = (k == tr.BUILT) | (k == tr.FLUID)
    # Outside the apron every built column and its neighbours stay; buildings on the apron freeze only
    # their own columns, so soil heaped against their walls and windows goes.
    outside_built = built.copy()
    outside_built[:, foot] = False
    frozen = ndimage.binary_dilation(outside_built.any(0), iterations=4) | ~box.loaded
    yy = np.arange(k.shape[0])[:, None, None] + y0
    edge_built = built & foot[None] & (yy > APRON_Y)
    frozen |= ndimage.binary_dilation(edge_built.any(0), iterations=4) & ~foot
    if a.keep:
        for bx0, bz0, bx1, bz1 in json.loads(a.keep.read_text('utf8')):
            frozen[max(0, bz0 - 8 - z0):max(0, bz1 + 9 - z0), max(0, bx0 - 8 - x0):max(0, bx1 + 9 - x0)] = True
    rng = np.random.default_rng(11)
    dist = ndimage.distance_transform_edt(~foot)
    s = a.slope * (1 + .12 * noise(foot.shape, 18, rng))
    cap = APRON_Y + np.maximum(0, dist - a.verge) * s + 1.2 * noise(foot.shape, 6, rng) * np.clip((dist - a.verge) / 8, 0, 1)
    cut = tr.softmin(ground.astype(float), cap, 2.5)
    fill = np.maximum(ground, APRON_Y - .9 * np.maximum(0, dist - 1.5))
    target = np.where(ground > APRON_Y, cut, fill)
    # Next to a kept column the new ground climbs back to the old one instead of leaving a step.
    dfroz = ndimage.distance_transform_edt(~frozen)
    target = np.maximum(target, ground - a.slope * 1.3 * dfroz)
    target = np.where(foot, np.minimum(ground, APRON_Y), target)
    target = np.where(frozen & ~foot, ground, target)
    on_apron_built = (built & (yy > APRON_Y)).any(0) & foot
    target = np.where(on_apron_built, ground, target)
    frozen_all = frozen & ~foot | on_apron_built
    plant = (dist >= a.verge + 2) & ~ndimage.binary_dilation(frozen, iterations=3)
    keepout = ndimage.binary_dilation(foot, iterations=2) | frozen
    # Density as the hill stood (pavement not counted); near the apron fewer conifers, so the first rows
    # do not stand as one dark wall.
    con, broad = tr.local_tree_chances(box, 24, counts=~foot)
    front = np.clip((dist - a.verge) / 25, 0, 1)
    share = con / 25 / np.maximum(con / 25 + broad / 49, 1e-6)
    cap = np.where(share > .4, .4 / np.maximum(share, 1e-6), 1)
    con2 = con * (front + (1 - front) * cap)
    broad2 = broad + (con - con2) * 49 / 25
    chance = (np.clip(con2, 0, .9), np.clip(broad2, 0, .9))
    new_ids, change = tr.apply_heights(box, ground, target, frozen_all, plant=plant, plant_keepout=keepout, chance=chance)
    # Earth left on a roof by the hill: everything natural above a building's highest block goes.
    air = box.state_id(tr.AIR_STATE)
    nk = box.kinds[new_ids]
    # soil, trees and wild plants only: potted or planted decoration on a roof is part of the building
    wild = np.array([(kd == tr.SOIL) or n.split('[')[0].endswith(('_leaves', '_log')) or n.split('[')[0] in ('minecraft:grass', 'minecraft:tall_grass', 'minecraft:fern', 'minecraft:large_fern')
                     for n, kd in zip(box.palette, box.kinds)])
    top_built = tr.top_of((nk == tr.BUILT) & (yy > APRON_Y), y0)
    for z, x in zip(*np.nonzero(on_apron_built)):
        above = np.arange(top_built[z, x] + 1 - y0, new_ids.shape[0])
        nat = wild[new_ids[above, z, x]]
        new_ids[above[nat], z, x] = air
    # Hill poured into buildings standing on the apron (the two hangars were full of it up to y88):
    # natural blocks above the pavement joined to the open hill are cleared under roofs too; a
    # planter shut inside walls is its own piece and stays.
    zz, xx = np.nonzero(foot)
    zs = slice(max(0, zz.min() - 10), zz.max() + 11)
    xs = slice(max(0, xx.min() - 10), xx.max() + 11)
    ys = slice(APRON_Y + 1 - y0, None)
    orig = wild[box.ids[ys, zs, xs]]
    lab, n = ndimage.label(orig)
    open_cols = ~(foot & on_apron_built)[zs, xs]
    hill = np.unique(lab[:, open_cols][lab[:, open_cols] > 0])
    joined = np.isin(lab, hill) & foot[zs, xs][None] & on_apron_built[zs, xs][None]
    sub = new_ids[ys, zs, xs]
    interior_cleared = int((joined & (sub != air)).sum())
    sub[joined] = air
    rows = tr.rows_between(box, new_ids)
    tr.write_rows(a.out / 'rows.json', rows)
    after_ground = tr.top_of(box.kinds[new_ids] == tr.SOIL, y0)
    np.savez_compressed(a.out / 'heights.npz', origin=np.array(box.origin), foot=foot, frozen=frozen_all, before=ground, after=after_ground, target=target)
    still = (foot & wild[new_ids[APRON_Y - y0 + 1:]].any(0))
    from collections import Counter
    report = dict(cells=len(rows), columns_changed=int(change.sum()), footprint_columns=int(foot.sum()),
                  footprint_x=[int(np.nonzero(foot.any(0))[0].min() + x0), int(np.nonzero(foot.any(0))[0].max() + x0)],
                  footprint_z=[int(np.nonzero(foot.any(1))[0].min() + z0), int(np.nonzero(foot.any(1))[0].max() + z0)],
                  apron_columns_still_covered=int(still.sum()), cleared_inside_buildings=interior_cleared, frozen_columns=int(frozen_all.sum()),
                  after_states=Counter(r[4].split('[')[0] for r in rows).most_common(12),
                  before_states=Counter(r[3].split('[')[0] for r in rows).most_common(12),
                  max_cut=int((ground - after_ground)[change].max()), max_fill=int((after_ground - ground)[change].max()))
    (a.out / 'report.json').write_text(json.dumps(report, indent=1), 'utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
