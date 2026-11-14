"""Lay out Japanese lowland farmland on flat, bare plain: consolidated blocks of strip plots between farm tracks and
irrigation channels, mostly planted paddies that read green, some freshly flooded ones, dry crops and fallow, a few
farmhouses with windbreak groves and kitchen plots, and an edge that thins out into scrub and trees.

Layout (all positions from world coordinates, so neighbouring runs line up):
    blocks   --block-x by --block-z blocks (each side jittered by a third), a farm track along the west side
             (2-3 wide, dirt path with coarse verges) and an irrigation channel (1 wide, water a block down) along the
             north side
    plots    strips running north-south, 4 to 13 wide, a 1-block grass path (aze) between them; a plot is clipped by
             anything kept (existing ditches, roads, buildings), so plots that meet a channel or road on the slant come
             out as trapezoids; plots under 24 columns stay grass
    kinds    planted paddy (farmland a block down under young green crops, growth stage varying by plot), flooded
             paddy (water a block down over mud, a few seedlings), ripening wheat, vegetables, fallow meadow
    houses   about one block in --house-every gets a farmhouse (timber and plaster, dark tile gable roof) on its south-
             east corner, an L of windbreak trees on its north and west, and kitchen plots in front
    edge     within --feather blocks of the area edge the chance of a plot falls off and the gaps get tall grass, bushes
             and trees
Nothing within 3 blocks of roads or buildings, within 1 of existing water, on other sessions' pending columns or on
unloaded chunks. Water a block down is kept only where every side is solid, so nothing can flow.

    plan_farmland.py --world W --mosaic DIR --area x0 x1 z0 z1 --out DIR [--keep-file F]
"""
import argparse
import json
import random
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr
from plan_bare_faces import hash01, vnoise

FLOWERS = ['minecraft:dandelion', 'minecraft:poppy', 'minecraft:oxeye_daisy', 'minecraft:cornflower', 'minecraft:azure_bluet']
KINDS = ['planted', 'flooded', 'wheat', 'veg', 'fallow']
LEAVES = 'minecraft:{}_leaves[distance=1,persistent=true,waterlogged=false]'


def cuts(lo, hi, base, salt):
    """Boundaries from lo to hi with widths base +- a third, deterministic in world coordinates."""
    start = (lo // base) * base
    out, p, i = [], start, int(start // base)
    while p <= hi + base:
        out.append(p)
        p += int(base * (0.67 + 0.66 * float(hash01(i, salt))))
        i += 1
    return out


def house(ids, kinds, g, z, x, rng, S, air, by, facing_long_x=True):
    """A small farmhouse with its south-east corner at column (z, x): 9 x 7, timber and plaster, gable roof.
    Returns the footprint mask cells or None if it does not fit (ground must be flat and the space empty)."""
    L, W = (9, 7) if facing_long_x else (7, 9)
    z0, x0 = z - W + 1, x - L + 1
    if z0 < 1 or x0 < 1 or z + 2 >= ids.shape[1] or x + 2 >= ids.shape[2]:
        return None
    foot = g[z0 - 1:z + 2, x0 - 1:x + 2]
    if foot.min() != foot.max():
        return None
    j = int(foot.min()) - by
    space = ids[j + 1:j + 10, z0 - 1:z + 2, x0 - 1:x + 2]
    if j + 10 >= ids.shape[0] or ((kinds[space] != tr.AIRK) & (kinds[space] != tr.SOFT)).any():
        return None
    space[...] = air
    log, plank, plaster = S('minecraft:stripped_spruce_log[axis=y]'), S('minecraft:spruce_planks'), S('minecraft:white_terracotta')
    found, glass = S('minecraft:cobblestone'), S('minecraft:glass')
    for zz in range(z0, z + 1):
        for xx in range(x0, x + 1):
            ids[j, zz, xx] = found if (zz in (z0, z) or xx in (x0, x)) else plank
            edge = zz in (z0, z) or xx in (x0, x)
            if not edge:
                continue
            corner = zz in (z0, z) and xx in (x0, x)
            for dy in range(1, 4):
                if corner:
                    s = log
                elif dy == 1:
                    s = plank
                else:
                    s = plaster
                ids[j + dy, zz, xx] = s
    # windows on the long sides, a door in the south wall
    for xx in range(x0 + 2, x, 3):
        ids[j + 2, z0, xx] = glass
        ids[j + 2, z, xx] = glass
    dx = x0 + L // 2
    ids[j + 1, z, dx] = S('minecraft:spruce_door[facing=south,half=lower,hinge=left,open=false,powered=false]')
    ids[j + 2, z, dx] = S('minecraft:spruce_door[facing=south,half=upper,hinge=left,open=false,powered=false]')
    # gable roof along x: stairs rise from both long sides, slab ridge, one-block overhang
    half = (W + 1) // 2
    for step in range(half + 1):
        y = j + 4 + step
        for xx in range(x0 - 1, x + 2):
            zn, zs = z0 - 1 + step, z + 1 - step
            if zn < zs:
                ids[y, zn, xx] = S('minecraft:deepslate_tile_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]')
                ids[y, zs, xx] = S('minecraft:deepslate_tile_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
                for zz in range(zn + 1, zs):
                    if xx in (x0, x) and step >= 1:
                        ids[y, zz, xx] = plaster
            elif zn == zs:
                ids[y, zn, xx] = S('minecraft:deepslate_tile_slab[type=bottom,waterlogged=false]')
    return (z0, z, x0, x)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--mosaic', type=Path, required=True)
    p.add_argument('--area', type=int, nargs=4, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--block-x', type=int, default=72)
    p.add_argument('--block-z', type=int, default=48)
    p.add_argument('--mix', type=float, nargs=5, default=[.55, .17, .08, .06, .14], help='planted flooded wheat veg fallow')
    p.add_argument('--house-every', type=int, default=5)
    p.add_argument('--feather', type=float, default=40)
    p.add_argument('--keep-file', type=Path)
    p.add_argument('--seed', type=int, default=91)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    x0, x1, z0, z1 = a.area
    m = 12
    ox, oz = (int(v) for v in np.load(a.mosaic / 'origin.npy'))
    g = np.array(np.load(a.mosaic / 'ground.npy', mmap_mode='r')[z0 - m - oz:z1 + m - oz + 1, x0 - m - ox:x1 + m - ox + 1])
    g = g[g > -30000]
    box = tr.Box(a.world, x0 - m, x1 + m, int(g.min()) - 4, int(g.max()) + 24, z0 - m, z1 + m)
    bx, by, bz = box.origin
    k = box.kind_grid()
    names = np.array([q.split('[')[0] for q in box.palette]).astype(str)
    ground = tr.top_of(k == tr.SOIL, by)
    wet = tr.top_of(k == tr.FLUID, by) >= ground
    yy = np.arange(k.shape[0])[:, None, None] + by
    built = ((k == tr.BUILT) & (yy >= ground[None] - 2)).any(0)
    tall_built = ((k == tr.BUILT) & (yy >= ground[None] + 3)).any(0)
    kept = np.zeros(ground.shape, bool)
    if a.keep_file and a.keep_file.exists():
        for px, pz in json.loads(a.keep_file.read_text('utf8')):
            if bx <= px < bx + ground.shape[1] and bz <= pz < bz + ground.shape[0]:
                kept[pz - bz, px - bx] = True
    jt = np.clip(ground - by, 2, k.shape[0] - 3)
    top_name = names[np.take_along_axis(box.ids, jt[None], 0)[0]]
    above_k = np.take_along_axis(k, (jt + 1)[None], 0)[0]
    leafy = (np.char.endswith(names, '_leaves')[box.ids] | np.char.endswith(names, '_log')[box.ids]).any(0)
    inside = np.zeros(ground.shape, bool)
    inside[z0 - bz:z1 - bz + 1, x0 - bx:x1 - bx + 1] = True
    road_keep = ndimage.binary_dilation(built, iterations=3)
    free = inside & box.loaded & (top_name == 'minecraft:grass_block') & (above_k != tr.BUILT) & (above_k != tr.FLUID) \
        & ~leafy & ~kept & ~road_keep & ~ndimage.binary_dilation(wet, iterations=1)
    zz, xx = np.mgrid[0:ground.shape[0], 0:ground.shape[1]]
    wx, wz = xx + bx, zz + bz
    d_edge = ndimage.distance_transform_edt(inside)
    feather = np.clip(d_edge / a.feather, 0, 1) * (.75 + .5 * vnoise(wx, wz, 23, a.seed))
    ids = box.ids.copy()
    sid = {}

    def S(s):
        if s not in sid:
            sid[s] = box.state_id(s)
        return sid[s]
    air = S(tr.AIR_STATE)
    bxs = cuts(x0, x1, a.block_x, a.seed + 1)
    bzs = cuts(z0, z1, a.block_z, a.seed + 2)
    plot_id = np.full(ground.shape, -1, np.int32)
    plot_kind = {}
    track = np.zeros(ground.shape, bool)
    channel = np.zeros(ground.shape, bool)
    houses = []
    counts = dict(blocks=0, plots=0, houses=0, **{kk: 0 for kk in KINDS})
    cum = np.cumsum(a.mix) / np.sum(a.mix)
    n = 0
    for bi in range(len(bxs) - 1):
        for bj in range(len(bzs) - 1):
            X0, X1, Z0, Z1 = bxs[bi], bxs[bi + 1] - 1, bzs[bj], bzs[bj + 1] - 1
            if X1 < x0 or X0 > x1 or Z1 < z0 or Z0 > z1:
                continue
            counts['blocks'] += 1
            tw = 2 + int(hash01(bi, bj, a.seed + 3) < .4)
            sl = lambda za, zb, xa, xb: (slice(max(za - bz, 0), max(zb - bz + 1, 0)), slice(max(xa - bx, 0), max(xb - bx + 1, 0)))
            track[sl(Z0, Z1, X0, X0 + tw - 1)] = True
            channel[sl(Z0, Z0, X0 + tw + 1, X1)] = True
            # farmhouse in this block?
            hb = None
            if hash01(bi, bj, a.seed + 4) < 1 / a.house_every:
                cz, cx = Z1 - 3 - bz, X1 - 3 - bx
                if 0 < cz < ground.shape[0] and 0 < cx < ground.shape[1] and free[max(cz - 18, 0):cz + 3, max(cx - 22, 0):cx + 3].mean() > .9:
                    hb = (Z1 - 26, Z1, X1 - 30, X1)
            # strips along z
            px = X0 + tw + 1
            si = 0
            while px < X1:
                w = 4 + int(hash01(px, bj, a.seed + 5) * 10)
                xa, xb = px, min(px + w - 1, X1)
                za, zb = Z0 + 2, Z1
                cells = np.zeros(ground.shape, bool)
                cells[sl(za, zb, xa, xb)] = True
                cells &= free & ~track & ~channel
                if hb:
                    cells[sl(hb[0], hb[1], hb[2], hb[3])] = False
                if cells.sum() >= 24 and hash01(px, Z0, a.seed + 6) < float(np.mean(feather[cells])):
                    u = float(hash01(bi * 131 + si, bj, a.seed + 7))
                    kind = int(np.searchsorted(cum, u))
                    plot_id[cells] = n
                    plot_kind[n] = kind
                    counts[KINDS[kind]] += 1
                    n += 1
                px = xb + 2
                si += 1
            if hb:
                houses.append(hb)
    counts['plots'] = n
    # water a block down: channels and flooded paddies, kept only where every side is solid at that height
    lowered = plot_id >= 0
    water_plan = (channel & free) | np.isin(plot_id, [i for i, kk in plot_kind.items() if kk == 1])
    while True:
        ok = np.ones(water_plan.shape, bool)
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb_water = np.roll(water_plan, (-dz, -dx), (0, 1))
            nb_ground = np.roll(ground, (-dz, -dx), (0, 1))
            nb_solid = (nb_ground >= ground) & np.roll(box.loaded & ~wet, (-dz, -dx), (0, 1))
            ok &= nb_water | nb_solid
        drop = water_plan & ~ok
        if not drop.any():
            break
        water_plan &= ~drop
    water, mud = S('minecraft:water[level=0]'), S('minecraft:mud')
    farmland = S('minecraft:farmland[moisture=7]')
    for z, x in zip(*np.nonzero(water_plan)):
        j = int(ground[z, x]) - by
        ids[j, z, x] = air
        if k[j + 1, z, x] == tr.SOFT and not names[box.ids[j + 1, z, x]].endswith(('_log', '_leaves')):
            ids[j + 1, z, x] = air
        ids[j - 1, z, x] = water
        ids[j - 2, z, x] = mud
        if plot_id[z, x] >= 0 and (wx[z, x] % 3 == 0) and hash01(wx[z, x], wz[z, x], a.seed + 8) < .35:
            ids[j - 1, z, x] = S('minecraft:seagrass')
    for z, x in zip(*np.nonzero(lowered & ~water_plan)):
        kind = plot_kind[int(plot_id[z, x])]
        j = int(ground[z, x]) - by
        if ids[j + 1, z, x] != air and k[j + 1, z, x] != tr.SOFT:
            continue
        no = int(plot_id[z, x])
        u = float(hash01(wx[z, x], wz[z, x], a.seed + 9))
        ids[j + 1, z, x] = air
        if kind == 0:
            stage = int(hash01(no, 1, a.seed) * 4)
            age = min(4, max(1, stage + (1 if u < .25 else 0) - (1 if u > .85 else 0) + 1))
            ids[j, z, x] = S(f'minecraft:wheat[age={age}]')
            ids[j - 1, z, x] = farmland
        elif kind == 2:
            age = 6 + int(u < .5) if hash01(no, 2, a.seed) < .6 else 4 + int(u * 3)
            ids[j, z, x] = S(f'minecraft:wheat[age={min(age, 7)}]')
            ids[j - 1, z, x] = farmland
        elif kind == 3:
            crop = ['carrots', 'potatoes', 'beetroots'][int(hash01(no, 3, a.seed) * 3)]
            line = wx[z, x] % 3
            ids[j - 1, z, x] = farmland
            ids[j, z, x] = S(f'minecraft:{crop}[age={3 if crop == "beetroots" else 5 + int(u * 3)}]') if line else air
        else:
            # fallow: stays at path height, rough grass and flowers
            if u < .3 and ids[j + 2, z, x] == air:
                ids[j + 1, z, x], ids[j + 2, z, x] = S('minecraft:tall_grass[half=lower]'), S('minecraft:tall_grass[half=upper]')
            elif u < .62:
                ids[j + 1, z, x] = S('minecraft:grass')
            elif u < .68:
                ids[j + 1, z, x] = S(FLOWERS[int(u * 1000) % len(FLOWERS)])
    # farm tracks: dirt path in the middle, coarse dirt verges
    for z, x in zip(*np.nonzero(track & free)):
        j = int(ground[z, x]) - by
        mid = hash01(wx[z, x], wz[z, x], a.seed + 10) < .85 and np.roll(track, -1, 1)[z, x] and np.roll(track, 1, 1)[z, x]
        ids[j, z, x] = S('minecraft:dirt_path') if mid else S('minecraft:coarse_dirt')
        if ids[j + 1, z, x] != air and k[j + 1, z, x] == tr.SOFT:
            ids[j + 1, z, x] = air
    # houses, their windbreaks (north and west, 3-6 deep) and kitchen plots in front
    rng = np.random.default_rng(a.seed)
    windbreak = np.zeros(ground.shape, bool)
    kitchen = np.zeros(ground.shape, bool)
    for hb in houses:
        cz, cx = hb[1] - 4 - bz, hb[3] - 4 - bx
        fp = house(ids, box.kinds, ground, cz, cx, rng, S, air, by, True)
        if fp is None:
            continue
        counts['houses'] += 1
        hz0, hz1, hx0, hx1 = fp
        windbreak[max(hz0 - 9, 0):hz0 - 2, max(hx0 - 9, 0):hx1 + 2] = True
        windbreak[max(hz0 - 9, 0):hz1 + 1, max(hx0 - 9, 0):hx0 - 2] = True
        kitchen[hz1 + 3:hz1 + 9, hx0:hx1 + 1] = True
    windbreak &= free & (plot_id < 0) & ~track
    kitchen &= free & (plot_id < 0) & ~track
    for z, x in zip(*np.nonzero(kitchen)):
        j = int(ground[z, x]) - by
        crop = ['carrots', 'potatoes', 'beetroots'][int(hash01(wx[z, x] // 4, wz[z, x], a.seed + 11) * 3)]
        if wz[z, x] % 2:
            ids[j, z, x] = farmland
            ids[j + 1, z, x] = S(f'minecraft:{crop}[age=3]')
    # edge scrub and trees in the gaps the feather leaves, channel-side trees
    aze = ndimage.binary_dilation(plot_id >= 0, iterations=1) & (plot_id < 0)
    gap = inside & free & (plot_id < 0) & ~aze & ~track & ~channel & ~windbreak & ~kitchen & (feather < 1)
    d_water = ndimage.distance_transform_edt(~(wet | water_plan))
    bank = inside & free & (plot_id < 0) & ~aze & ~track & (d_water >= 2) & (d_water <= 3)
    scrub_u = hash01(wx, wz, a.seed + 12)
    for z, x in zip(*np.nonzero(gap & (scrub_u < .45 * (1 - feather)))):
        j = int(ground[z, x]) - by
        if ids[j + 1, z, x] != air:
            continue
        u = scrub_u[z, x] / max(.45 * (1 - feather[z, x]), 1e-6)
        if u < .35 and ids[j + 2, z, x] == air:
            ids[j + 1, z, x], ids[j + 2, z, x] = S('minecraft:tall_grass[half=lower]'), S('minecraft:tall_grass[half=upper]')
        elif u < .55:
            ids[j + 1, z, x] = S(LEAVES.format(['oak', 'dark_oak', 'birch'][int(u * 97) % 3]))
        else:
            ids[j + 1, z, x] = S('minecraft:grass')
    c_con = np.where(windbreak, .6, 0) + np.where(gap, .06 * (1 - feather), 0)
    c_broad = np.where(windbreak, .25, 0) + np.where(gap, .22 * (1 - feather), 0) + np.where(bank, .12, 0)
    where = (windbreak | gap | bank) & (top_name == 'minecraft:grass_block')
    tr.replant(box, ids, ground, where, road_keep | wet | water_plan | (plot_id >= 0) | track | kept, random.Random(a.seed), chance=(c_con, c_broad))
    rows = [r for r in tr.rows_between(box, ids) if x0 <= r[0] <= x1 and z0 <= r[2] <= z1]
    tr.write_rows(a.out / 'rows.json', rows)
    bases = {(q[0], q[2]) for q in rows if q[4].split('[')[0].endswith('_log') and 'stripped' not in q[4]}
    counts.update(cells=len(rows), open_water_columns=int(water_plan.sum()), trees=len(bases), area=a.area)
    (a.out / 'report.json').write_text(json.dumps(counts, indent=1), 'utf8')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
