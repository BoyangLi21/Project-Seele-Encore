"""Soften hard forest edges found by scan_forest_edges.py: thinning bands, scattered trees and shrubs on the
bare side, shaped by the ground.

Where: open grass within --reach blocks (with a wandering noise) of a forest rim that scan_forest_edges.py
marked hard. How dense: the woods' own trunk density (sampled on forest columns within 40 blocks, with their
conifer share) times a profile measured on the map's gradual edges (forest share 0.26 at 4 blocks, 0.11-0.14
from 12 to 48), less the trees already standing there. The ground shapes it: hollows and stream banks get
more trees, ridges and steep faces fewer, and a low-frequency noise gathers them into groves. Shrubs (one or
two leaf blocks) are scattered across the band and a little past it.

Never: within 3 blocks of anything built at the surface (roads, rails, houses), on water, on unscanned chunks,
or in columns another session's pending list touches (--keep-rows). Only air and loose plants are replaced.
Tiles overlap and are planned one after another, each seeing the trees the earlier ones placed.
"""
import argparse
import glob
import json
import os
import random
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr

CELL = 4
# relative trunk density against distance (blocks) from the forest rim, from the gradual-edge profile
PROFILE_D = np.array([0, 4, 8, 12, 16, 24, 32, 40, 56, 72, 88], float)
PROFILE_R = np.array([.5, .44, .28, .2, .16, .15, .14, .12, .07, .03, 0], float)


def profile(d):
    return np.interp(d, PROFILE_D, PROFILE_R)


def still_pending(rows, world, sample=300):
    """True when a list has not been written yet: most sampled rows still show their before state."""
    from write_deep_cells import read_chunk, decode
    folder = Path(world) / 'dimensions/projectseele/geofront/region'
    step = max(1, len(rows) // sample)
    pick = [r for r in rows[::step] if isinstance(r[0], int) and r[3] != r[4]][:sample]
    before = after = 0
    cache = {}
    for x, y, z, b, a in (r[:5] for r in pick):
        rx, rz, cx, cz = x >> 9, z >> 9, x >> 4, z >> 4
        if (cx, cz) not in cache:
            f = folder / f'r.{rx}.{rz}.mca'
            try:
                root = read_chunk(f.read_bytes(), cx, cz)[3]
                cache[(cx, cz)] = {int(s['Y']): decode(s['block_states']) for s in root['sections'] if 'block_states' in s}
            except Exception:
                cache[(cx, cz)] = None
        dec = cache[(cx, cz)]
        if not dec or (y >> 4) not in dec:
            continue
        ids, pal = dec[y >> 4]
        st = pal[ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]]
        before += st == b
        after += st == a
    return before > max(after, 0) and before >= .5 * max(1, len(pick))


def keep_columns(patterns, since_days, world=None):
    """Columns that other sessions' lists touch. With world, only lists that are still waiting to be written
    (their before states still stand) count; written ones are already in the world we plan on."""
    import time
    cols = set()
    now = time.time()
    for pat in patterns:
        for f in glob.glob(pat, recursive=True):
            if os.path.getsize(f) > 400e6 or now - os.path.getmtime(f) > since_days * 86400:
                continue
            try:
                rows = json.load(open(f))
            except Exception:
                continue
            if not isinstance(rows, list) or not rows or not isinstance(rows[0], list) or len(rows[0]) < 5:
                continue
            if world is not None and not still_pending(rows, world):
                continue
            cols.update((r[0], r[2]) for r in rows if isinstance(r[0], int))
    return cols


def plant_shrubs(box, ids, where, chance, rng):
    y0 = box.origin[1]
    k = box.kinds
    grass = box.state_id(tr.GRASS)
    air = box.state_id(tr.AIR_STATE)
    kinds = ['oak', 'oak', 'dark_oak', 'birch', 'spruce']
    states = [box.state_id(f'minecraft:{s}_leaves[distance=1,persistent=true,waterlogged=false]') for s in kinds]
    top = tr.top_of(k[ids] == tr.SOIL, y0)
    roll = rng.random(where.shape)
    n = 0
    for z, x in zip(*np.nonzero(where & (roll < chance))):
        y = int(top[z, x]) - y0
        if not (0 <= y and y + 3 < ids.shape[0] and ids[y, z, x] == grass and ids[y + 1, z, x] == air):
            continue
        s = states[int(rng.integers(len(states)))]
        ids[y + 1, z, x] = s
        if rng.random() < .3 and ids[y + 2, z, x] == air:
            ids[y + 2, z, x] = s
        n += 1
    return n


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--edges', type=Path, required=True, help='cells.npz from scan_forest_edges.py')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--reach', type=float, default=72)
    p.add_argument('--tile', type=int, default=256)
    p.add_argument('--margin', type=int, default=12)
    p.add_argument('--area', type=int, nargs=4, help='x0 x1 z0 z1: only tiles inside')
    p.add_argument('--keep-rows', nargs='*', default=[], help='globs of other sessions\' pending row lists')
    p.add_argument('--keep-days', type=float, default=4)
    p.add_argument('--shrubs', type=float, default=.012, help='shrub chance per open column at full profile')
    p.add_argument('--seed', type=int, default=11)
    p.add_argument('--resume', action='store_true', help='carry on from the checkpoint in --out')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    c = np.load(a.edges)
    ox, oz = (int(v) for v in c['origin'])
    forest, bare, hard = c['forest'], c['bare'], c['hard']
    reach_cells = int(a.reach / CELL) + 8
    near_hard = ndimage.distance_transform_edt(~hard) <= reach_cells
    zone_cells = near_hard & ~forest & (ndimage.distance_transform_edt(~forest) <= reach_cells) & (bare | (c['smooth'] < .2))
    keep = keep_columns(a.keep_rows, a.keep_days)
    print(f'{int(zone_cells.sum())} zone cells, {len(keep)} columns kept for other sessions', flush=True)
    zz, xx = np.nonzero(zone_cells)
    bx = ox + CELL * xx
    bz = oz + CELL * zz
    tiles = sorted({(int(x) // a.tile, int(z) // a.tile) for x, z in zip(bx, bz)})
    if a.area:
        tiles = [t for t in tiles if a.area[0] <= t[0] * a.tile < a.area[1] and a.area[2] <= t[1] * a.tile < a.area[3]]
    planned, by_chunk, report, done = {}, {}, [], set()
    ck = a.out / 'checkpoint.json'
    if a.resume and ck.exists():
        state = json.load(open(ck))
        for q in state['rows']:
            key = tuple(q[:3])
            planned[key] = q
            by_chunk.setdefault((key[0] >> 4, key[2] >> 4), []).append(key)
        report, done = state['report'], {tuple(t) for t in state['done']}
        print(f'resumed: {len(done)} tiles, {len(planned)} cells', flush=True)
    rng_master = np.random.default_rng(a.seed)
    for n, (tx, tz) in enumerate(tiles):
        # every tile draws its noise from its own seed, so a resumed run plans the same trees
        rng_master = np.random.default_rng([a.seed, tx + 10000, tz + 10000])
        if (tx, tz) in done:
            continue
        x0, z0 = tx * a.tile - a.margin, tz * a.tile - a.margin
        x1, z1 = x0 + a.tile + 2 * a.margin - 1, z0 + a.tile + 2 * a.margin - 1
        # cell arrays cut to the tile (cells cover 4 x 4 blocks)
        cx0, cz0 = (x0 - ox) // CELL, (z0 - oz) // CELL
        cx1, cz1 = (x1 - ox) // CELL + 1, (z1 - oz) // CELL + 1
        sl = (slice(max(cz0, 0), cz1), slice(max(cx0, 0), cx1))
        if not zone_cells[sl].any():
            continue
        def up(arr):
            sub = arr[sl]
            big = np.repeat(np.repeat(sub, CELL, 0), CELL, 1)
            zoff, xoff = z0 - (oz + CELL * max(cz0, 0)), x0 - (ox + CELL * max(cx0, 0))
            out = np.zeros((z1 - z0 + 1, x1 - x0 + 1), big.dtype)
            hz, hx = min(out.shape[0], big.shape[0] - zoff), min(out.shape[1], big.shape[1] - xoff)
            out[:hz, :hx] = big[zoff:zoff + hz, xoff:xoff + hx]
            return out
        f_b, h_b, z_b = up(forest), up(hard), up(zone_cells)
        hts = c['height'][sl]
        lo = int(np.nanmin(np.where(hts > -1000, hts, 1e9))) - 12
        hi = int(np.nanmax(hts)) + 24
        box = tr.Box(a.world, x0, x1, max(-64, lo), min(319, hi), z0, z1)
        by = box.origin[1]
        for cxk in range(x0 >> 4, (x1 >> 4) + 1):
            for czk in range(z0 >> 4, (z1 >> 4) + 1):
                for key in by_chunk.get((cxk, czk), ()):
                    px, py, pz = key
                    if key in planned and x0 <= px <= x1 and z0 <= pz <= z1 and by <= py < by + box.ids.shape[0]:
                        box.ids[py - by, pz - z0, px - x0] = box.state_id(planned[key][4])
        k = box.kind_grid()
        ground = tr.top_of(k == tr.SOIL, by)
        yy = np.arange(k.shape[0])[:, None, None] + by
        surface_built = ((k == tr.BUILT) & (yy >= ground[None] - 8)).any(0)
        wet = ((k == tr.FLUID) & (yy >= ground[None])).any(0)
        names = np.array([q.split('[')[0] for q in box.palette]).astype(str)
        is_leaf = np.char.endswith(names, '_leaves')
        canopy = is_leaf[box.ids].any(0)
        kept = np.zeros(ground.shape, bool)
        for (px, pz) in keep:
            if x0 <= px <= x1 and z0 <= pz <= z1:
                kept[pz - z0, px - x0] = True
        keepout = ndimage.binary_dilation(surface_built, iterations=3) | ndimage.binary_dilation(wet | kept, iterations=1) | ~box.loaded
        # distance from the forest rim, in blocks, and a wandering outer limit
        dist = ndimage.distance_transform_edt(~f_b)
        noise = ndimage.gaussian_filter(rng_master.standard_normal(ground.shape), 10)
        noise /= noise.std() + 1e-9
        reach = a.reach * (1 + .3 * noise)
        rel = profile(dist * a.reach / np.maximum(reach, 8)) * (dist <= reach)
        # the ground: hollows and stream banks wetter, ridges and steep faces drier
        g = ndimage.gaussian_filter(ground.astype(float), 2)
        lap = ndimage.gaussian_laplace(g, 8)
        lap_n = np.clip(lap / (np.std(lap) + 1e-9), -2, 2)
        gy, gx = np.gradient(g)
        steep = np.hypot(gx, gy)
        near_water = np.exp(-ndimage.distance_transform_edt(~wet) / 16) if wet.any() else 0
        clump = ndimage.gaussian_filter(rng_master.standard_normal(ground.shape), 9)
        clump /= clump.std() + 1e-9
        m = np.exp(.35 * lap_n + 1.15 * clump) * (1 + .6 * near_water) * np.where(steep > 1.3, .55, 1)
        zone = z_b.astype(bool) & ~f_b & ~canopy & ~keepout & (rel > 0)
        if zone.any():
            m = m / max(float(np.median(m[zone])), 1e-6)
        # trunk density and conifer share of the woods behind the rim
        trunks_c, trunks_b = tr.local_tree_chances(box, 40, counts=f_b | canopy)
        d_forest = trunks_c / 25 + trunks_b / 49
        share_c = np.where(d_forest > 0, (trunks_c / 25) / np.maximum(d_forest, 1e-9), .5) * .7
        existing = ndimage.uniform_filter(canopy.astype(float), 13)
        forest_share = max(float(c['smooth'][sl][forest[sl]].mean()) if forest[sl].any() else .6, .3)
        want = np.clip(rel * m - existing / forest_share, 0, 1)
        chance = (np.clip(25 * d_forest * share_c * want, 0, .9), np.clip(49 * d_forest * (1 - share_c) * want, 0, .9))
        ids = box.ids.copy()
        rng = random.Random(a.seed * 1000 + n)
        core = np.zeros(ground.shape, bool)
        core[a.margin:-a.margin, a.margin:-a.margin] = True
        tr.replant(box, ids, ground, zone & core, keepout, rng, chance=chance)
        # planting added states to the palette, so the leaf table is built again
        is_leaf = np.char.endswith(np.array([q.split('[')[0] for q in box.palette]).astype(str), '_leaves')
        shrub_where = zone & core & ~ndimage.binary_dilation(is_leaf[ids].any(0), iterations=1)
        shrubs = plant_shrubs(box, ids, shrub_where, a.shrubs * np.clip(profile(dist * .7) / .42, 0, 1) * m, np.random.default_rng(a.seed * 7 + n))
        rows = tr.rows_between(box, ids)
        for q in rows:
            key = tuple(q[:3])
            if key in planned:
                planned[key][4] = q[4]
                if planned[key][4] == planned[key][3]:
                    del planned[key]
            else:
                planned[key] = q
                by_chunk.setdefault((key[0] >> 4, key[2] >> 4), []).append(key)
        logs = sum(1 for q in rows if q[4].split('[')[0].endswith('_log') and q[3].split('[')[0] != q[4].split('[')[0])
        report.append(dict(tile=[tx, tz], box=[x0, z0, x1, z1], zone_columns=int((zone & core).sum()), cells=len(rows), log_cells=logs, shrubs=shrubs))
        print(json.dumps(report[-1]), flush=True)
        done.add((tx, tz))
        if len(done) % 10 == 0:
            tmp = a.out / 'checkpoint.tmp'
            tmp.write_text(json.dumps(dict(rows=list(planned.values()), report=report, done=sorted(done))), 'utf8')
            os.replace(tmp, ck)
    rows = list(planned.values())
    tr.write_rows(a.out / 'rows.json', rows)
    bases = {}
    for q in rows:
        if q[4].split('[')[0].endswith('_log'):
            key = (q[0], q[2])
            bases[key] = min(bases.get(key, 10 ** 4), q[1])
    (a.out / 'report.json').write_text(json.dumps(dict(cells=len(rows), trees=len(bases), shrubs=sum(t['shrubs'] for t in report), tiles=report), indent=0), 'utf8')
    print(json.dumps(dict(cells=len(rows), trees=len(bases), shrubs=sum(t['shrubs'] for t in report), tiles=len(report))))


if __name__ == '__main__':
    main()
