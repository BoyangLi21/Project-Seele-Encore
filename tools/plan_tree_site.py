"""Thicken the trees over one site so it reads as part of the woods around it (for example the lawns round
the weapon silos beside Tokyo-3, which the owner found too bare).

Inside --site the target is the trunk density and conifer share of the woods within 48 blocks (sampled on
wooded columns only), eased down near anything built: a quarter of it at --clear blocks from a building,
road or hatch, full strength from --clear + 24 on. The ground shapes it as in plan_forest_transitions.py
(hollows and stream banks more, ridges and steep faces fewer, groves from a low-frequency noise), less the
trees already standing. Shrubs are scattered on the open ground left between.

Never within --clear blocks of anything built at the surface, on water, on unscanned chunks, in columns other
sessions' pending lists touch (--keep-rows), or within 2 blocks of the boxes in --avoid (pieces another
session is about to fix). Only air and loose plants are replaced.
"""
import argparse
import json
import random
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr
from plan_forest_transitions import keep_columns, plant_shrubs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--site', type=int, nargs=4, required=True, help='x0 x1 z0 z1')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--clear', type=int, default=3, help='blocks kept free round anything built')
    p.add_argument('--strength', type=float, default=.85, help='share of the nearby woods\' density aimed at')
    p.add_argument('--avoid', type=Path, help='json list of [x0, y0, z0, x1, y1, z1] boxes (or pieces with a bbox) left alone')
    p.add_argument('--keep-rows', nargs='*', default=[])
    p.add_argument('--keep-days', type=float, default=4)
    p.add_argument('--ease', type=float, default=24, help='blocks over which the cover rises from a quarter to full away from buildings')
    p.add_argument('--clump', type=float, default=1.0, help='strength of the grove noise')
    p.add_argument('--seed', type=int, default=21)
    p.add_argument('--debug', action='store_true', help='also save the planning layers to debug.npz')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    sx0, sx1, sz0, sz1 = a.site
    m = 56
    x0, x1, z0, z1 = sx0 - m, sx1 + m, sz0 - m, sz1 + m
    box = tr.Box(a.world, x0, x1, -64, 300, z0, z1)
    by = box.origin[1]
    k = box.kind_grid()
    ground = tr.top_of(k == tr.SOIL, by)
    yy = np.arange(k.shape[0])[:, None, None] + by
    built = ((k == tr.BUILT) & (yy >= ground[None] - 8)).any(0)
    wet = ((k == tr.FLUID) & (yy >= ground[None])).any(0)
    names = np.array([q.split('[')[0] for q in box.palette]).astype(str)
    canopy = np.char.endswith(names, '_leaves')[box.ids].any(0)
    avoid = np.zeros(ground.shape, bool)
    if a.avoid:
        for piece in json.loads(a.avoid.read_text('utf8')):
            b = piece['bbox'] if isinstance(piece, dict) else piece
            avoid[max(0, b[2] - 2 - z0):max(0, b[5] + 3 - z0), max(0, b[0] - 2 - x0):max(0, b[3] + 3 - x0)] = True
    kept = np.zeros(ground.shape, bool)
    for (px, pz) in keep_columns(a.keep_rows, a.keep_days, a.world):
        if x0 <= px <= x1 and z0 <= pz <= z1:
            kept[pz - z0, px - x0] = True
    keepout = ndimage.binary_dilation(built, iterations=a.clear) | ndimage.binary_dilation(wet | kept, iterations=1) | avoid | ~box.loaded
    site = np.zeros(ground.shape, bool)
    site[sz0 - z0:sz1 - z0 + 1, sx0 - x0:sx1 - x0 + 1] = True
    d_built = ndimage.distance_transform_edt(~built)
    ease = np.clip((d_built - a.clear) / a.ease, 0, 1)
    rel = a.strength * (.25 + .75 * ease * ease * (3 - 2 * ease))
    # soften the site's own edge so the thicker cover fades into what is round it
    d_edge = ndimage.distance_transform_edt(site)
    rel = rel * np.clip(d_edge / 16, 0, 1)
    rng_np = np.random.default_rng(a.seed)
    g = ndimage.gaussian_filter(ground.astype(float), 2)
    lap = ndimage.gaussian_laplace(g, 8)
    lap_n = np.clip(lap / (np.std(lap) + 1e-9), -2, 2)
    gy, gx = np.gradient(g)
    steep = np.hypot(gx, gy)
    near_water = np.exp(-ndimage.distance_transform_edt(~wet) / 16) if wet.any() else 0
    clump = ndimage.gaussian_filter(rng_np.standard_normal(ground.shape), 9)
    clump /= clump.std() + 1e-9
    mod = np.exp(.35 * lap_n + a.clump * clump) * (1 + .6 * near_water) * np.where(steep > 1.3, .55, 1)
    zone = site & ~canopy & ~keepout
    if zone.any():
        mod = mod / max(float(np.median(mod[zone])), 1e-6)
    wooded = ndimage.binary_dilation(canopy, iterations=2) & ~built
    trunks_c, trunks_b = tr.local_tree_chances(box, 48, counts=wooded)
    d_forest = trunks_c / 25 + trunks_b / 49
    share_c = np.where(d_forest > 0, (trunks_c / 25) / np.maximum(d_forest, 1e-9), .5)
    existing = ndimage.uniform_filter(canopy.astype(float), 13)
    wood_share = max(float(existing[wooded].mean()) if wooded.any() else .6, .3)
    want = np.clip(rel * mod - existing / wood_share, 0, 1)
    chance = (np.clip(25 * d_forest * share_c * want, 0, .9), np.clip(49 * d_forest * (1 - share_c) * want, 0, .9))
    if a.debug:
        np.savez_compressed(a.out / 'debug.npz', origin=np.array([x0, z0]), ground=ground, built=built, wet=wet, canopy=canopy, keepout=keepout,
                            zone=zone, rel=rel, mod=mod, existing=existing, want=want, chance_c=chance[0], chance_b=chance[1])
    ids = box.ids.copy()
    tr.replant(box, ids, ground, zone, keepout, random.Random(a.seed), chance=chance)
    leaf = np.char.endswith(np.array([q.split('[')[0] for q in box.palette]).astype(str), '_leaves')
    shrub_where = zone & ~ndimage.binary_dilation(leaf[ids].any(0), iterations=1)
    shrubs = plant_shrubs(box, ids, shrub_where, .03 * np.clip(rel / a.strength, 0, 1) * mod, np.random.default_rng(a.seed + 1))
    rows = tr.rows_between(box, ids)
    tr.write_rows(a.out / 'rows.json', rows)
    bases = {(q[0], q[2]) for q in rows if q[4].split('[')[0].endswith('_log')}
    after_canopy = leaf[ids].any(0)
    rep = dict(cells=len(rows), trees=len(bases), shrubs=shrubs, site=a.site,
               canopy_share_in_site_before=round(float(canopy[site & ~built].mean()), 3), canopy_share_in_site_after=round(float(after_canopy[site & ~built].mean()), 3),
               woods_share_nearby=round(wood_share, 3), avoided_columns=int(avoid.sum()))
    (a.out / 'report.json').write_text(json.dumps(rep, indent=1), 'utf8')
    print(json.dumps(rep))


if __name__ == '__main__':
    main()
