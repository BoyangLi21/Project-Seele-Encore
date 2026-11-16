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


def clear_ok(ids, kinds, j, z0, z1, x0, x1, h):
    """True if columns z0..z1, x0..x1 hold only air or loose plants from j+1 to j+h (and lie inside ids)."""
    if z0 < 0 or x0 < 0 or z1 >= ids.shape[1] or x1 >= ids.shape[2] or j + h + 1 >= ids.shape[0]:
        return False
    sp = kinds[ids[j + 1:j + h + 1, z0:z1 + 1, x0:x1 + 1]]
    return bool(((sp == tr.AIRK) | (sp == tr.SOFT)).all())


def flat(g, z0, z1, x0, x1):
    if z0 < 0 or x0 < 0 or z1 >= g.shape[0] or x1 >= g.shape[1]:
        return False
    f = g[z0:z1 + 1, x0:x1 + 1]
    return bool(f.size) and f.min() == f.max()


def gable(ids, S, j_eave, z0, z1, x0, x1, end_fill):
    """Gable roof along x over walls z0..z1, one-block overhang, eaves at j_eave; gable ends filled with end_fill."""
    half = (z1 - z0 + 2) // 2
    for step in range(half + 1):
        y = j_eave + step
        for xx in range(x0 - 1, x1 + 2):
            zn, zs = z0 - 1 + step, z1 + 1 - step
            if zn < zs:
                ids[y, zn, xx] = S('minecraft:deepslate_tile_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]')
                ids[y, zs, xx] = S('minecraft:deepslate_tile_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
                if xx in (x0, x1) and step >= 1:
                    for zz in range(zn + 1, zs):
                        ids[y, zz, xx] = end_fill
            elif zn == zs:
                ids[y, zn, xx] = S('minecraft:deepslate_tile_slab[type=bottom,waterlogged=false]')


def house(ids, kinds, g, z, x, S, air, by, storeys=1):
    """Farmhouse with its south-east corner at (z, x): 9 x 7, timber frame and calcite plaster, dark tile gable roof,
    one or two storeys. Returns (z0, z1, x0, x1) or None if the ground is not flat or the space is taken."""
    L, W = 9, 7
    z0, x0 = z - W + 1, x - L + 1
    wall_h = 3 if storeys == 1 else 6
    if not flat(g, z0 - 1, z + 1, x0 - 1, x + 1):
        return None
    j = int(g[z, x]) - by
    if not clear_ok(ids, kinds, j, z0 - 1, z + 1, x0 - 1, x + 1, wall_h + 6):
        return None
    ids[j + 1:j + wall_h + 6, z0 - 1:z + 2, x0 - 1:x + 2] = air
    log, plank, plaster = S('minecraft:stripped_spruce_log[axis=y]'), S('minecraft:spruce_planks'), S('minecraft:calcite')
    found, glass = S('minecraft:cobblestone'), S('minecraft:glass')
    beam = S('minecraft:stripped_spruce_log[axis=x]')
    for zz in range(z0, z + 1):
        for xx in range(x0, x + 1):
            edge = zz in (z0, z) or xx in (x0, x)
            ids[j, zz, xx] = found if edge else plank
            if storeys == 2 and not edge:
                ids[j + 3, zz, xx] = plank
            if not edge:
                continue
            corner = zz in (z0, z) and xx in (x0, x)
            for dy in range(1, wall_h + 1):
                if corner:
                    s_ = log
                elif dy == 1:
                    s_ = plank
                elif storeys == 2 and dy == 4:
                    s_ = beam if zz in (z0, z) else plank
                else:
                    s_ = plaster
                ids[j + dy, zz, xx] = s_
    for xx in range(x0 + 2, x, 3):
        for dy in ((2,) if storeys == 1 else (2, 5)):
            ids[j + dy, z0, xx] = glass
            ids[j + dy, z, xx] = glass
    dx = x0 + L // 2
    ids[j + 1, z, dx] = S('minecraft:spruce_door[facing=south,half=lower,hinge=left,open=false,powered=false]')
    ids[j + 2, z, dx] = S('minecraft:spruce_door[facing=south,half=upper,hinge=left,open=false,powered=false]')
    gable(ids, S, j + wall_h + 1, z0, z, x0, x, plaster)
    return (z0, z, x0, x)


def barn(ids, kinds, g, z, x, S, air, by):
    """Open-fronted barn 9 x 7 (south side on posts), dark plank walls, dark tile roof, hay inside."""
    L, W = 9, 7
    z0, x0 = z - W + 1, x - L + 1
    if not flat(g, z0 - 1, z + 1, x0 - 1, x + 1):
        return None
    j = int(g[z, x]) - by
    if not clear_ok(ids, kinds, j, z0 - 1, z + 1, x0 - 1, x + 1, 10):
        return None
    ids[j + 1:j + 10, z0 - 1:z + 2, x0 - 1:x + 2] = air
    post, plank = S('minecraft:spruce_log[axis=y]'), S('minecraft:dark_oak_planks')
    for zz in range(z0, z + 1):
        for xx in range(x0, x + 1):
            ids[j, zz, xx] = S('minecraft:coarse_dirt')
            corner = zz in (z0, z) and xx in (x0, x)
            wall = (zz == z0 or xx in (x0, x)) and not corner
            front_post = zz == z and xx in (x0, x0 + 4, x)
            for dy in range(1, 4):
                if corner or front_post:
                    ids[j + dy, zz, xx] = post
                elif wall:
                    ids[j + dy, zz, xx] = plank
    for xx in range(x0 + 1, x0 + 4):
        for zz in range(z0 + 1, z0 + 3):
            ids[j + 1, zz, xx] = S('minecraft:hay_block[axis=y]')
            if xx < x0 + 3:
                ids[j + 2, zz, xx] = S('minecraft:hay_block[axis=x]')
    gable(ids, S, j + 4, z0, z, x0, x, plank)
    return (z0, z, x0, x)


def greenhouse(ids, kinds, g, z, x, S, air, by):
    """Greenhouse 11 x 5: frosted glass walls and a stepped ridge, crops on farmland inside, door gap in front."""
    L, W = 11, 5
    z0, x0 = z - W + 1, x - L + 1
    if not flat(g, z0, z, x0, x):
        return None
    j = int(g[z, x]) - by
    if not clear_ok(ids, kinds, j, z0, z, x0, x, 6):
        return None
    ids[j + 1:j + 6, z0:z + 1, x0:x + 1] = air
    glass = S('minecraft:white_stained_glass')
    for zz in range(z0, z + 1):
        for xx in range(x0, x + 1):
            if zz in (z0, z) or xx in (x0, x):
                ids[j + 1, zz, xx] = glass
                ids[j + 2, zz, xx] = glass
            else:
                ids[j, zz, xx] = S('minecraft:farmland[moisture=7]')
                ids[j + 1, zz, xx] = S('minecraft:carrots[age=5]') if (xx + zz) % 2 else S('minecraft:beetroots[age=2]')
            if zz in (z0, z0 + 1, z - 1, z):
                ids[j + 3, zz, xx] = glass
            if zz == z0 + 2:
                ids[j + 4, zz, xx] = glass
    for xx in (x0, x):
        ids[j + 3, z0 + 2, xx] = glass
    ids[j + 1, z, x0 + L // 2] = air
    ids[j + 2, z, x0 + L // 2] = air
    return (z0, z, x0, x)


def shrine(ids, kinds, g, z, x, S, air, by):
    """Village shrine: small hall (5 x 5, dark tile roof) at the north end, a red torii near the south end, a stone
    path between; the footprint is 7 wide and 13 deep ending at (z, x) in the middle of its south edge."""
    z0, z1, x0, x1 = z - 12, z, x - 3, x + 3
    if not flat(g, z0, z1, x0, x1):
        return None
    j = int(g[z, x]) - by
    if not clear_ok(ids, kinds, j, z0, z1, x0, x1, 9):
        return None
    ids[j + 1:j + 9, z0:z1 + 1, x0:x1 + 1] = air
    hz0, hz1, hx0, hx1 = z0, z0 + 4, x - 2, x + 2
    for zz in range(hz0, hz1 + 1):
        for xx in range(hx0, hx1 + 1):
            ids[j, zz, xx] = S('minecraft:stone_bricks')
            if zz in (hz0, hz1) or xx in (hx0, hx1):
                corner = zz in (hz0, hz1) and xx in (hx0, hx1)
                for dy in (1, 2, 3):
                    ids[j + dy, zz, xx] = S('minecraft:stripped_dark_oak_log[axis=y]') if corner else S('minecraft:dark_oak_planks')
    ids[j + 1, hz1, x] = air
    ids[j + 2, hz1, x] = air
    gable(ids, S, j + 4, hz0, hz1, hx0, hx1, S('minecraft:dark_oak_planks'))
    for zz in range(hz1 + 1, z1 + 1):
        ids[j, zz, x] = S('minecraft:stone_bricks') if zz % 2 else S('minecraft:polished_andesite')
    tz = z1 - 1
    red = S('minecraft:red_concrete')
    for xx in (x - 2, x + 2):
        for dy in range(1, 5):
            ids[j + dy, tz, xx] = red
    for xx in range(x - 3, x + 4):
        ids[j + 4, tz, xx] = red
        ids[j + 5, tz, xx] = S('minecraft:polished_blackstone_slab[type=bottom,waterlogged=false]')
    return (z0, z1, x0, x1)


def shelter_ns(ids, kinds, g, z, x, S, air, by, road_east=True):
    """Bus shelter for a north-south road: 2 wide (x) by 4 long (z) ending at (z, x), glass back on the side away from
    the road, bench facing the road."""
    z0, x0 = z - 3, x - 1
    if not flat(g, z0, z, x0, x):
        return None
    j = int(g[z, x]) - by
    if not clear_ok(ids, kinds, j, z0, z, x0, x, 4):
        return None
    back, front = (x0, x) if road_east else (x, x0)
    for zz in range(z0, z + 1):
        ids[j, zz, x0] = ids[j, zz, x] = S('minecraft:smooth_stone')
        ids[j + 1, zz, back] = ids[j + 2, zz, back] = S('minecraft:glass')
        ids[j + 3, zz, x0] = ids[j + 3, zz, x] = S('minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    for zz in (z0, z):
        ids[j + 1, zz, front] = ids[j + 2, zz, front] = S('minecraft:spruce_fence[east=false,north=false,south=false,waterlogged=false,west=false]')
    facing = 'west' if road_east else 'east'
    for zz in range(z0 + 1, z):
        ids[j + 1, zz, front] = S(f'minecraft:spruce_stairs[facing={facing},half=bottom,shape=straight,waterlogged=false]')
    return (z0, z, x0, x)


def shelter(ids, kinds, g, z, x, S, air, by, vending=False):
    """Bus shelter 4 x 2 (glass back, slab roof, bench facing south) or a vending machine (white body, lit panel)."""
    if vending:
        j = int(g[z, x]) - by
        if not clear_ok(ids, kinds, j, z, z, x, x, 3):
            return None
        ids[j + 1, z, x] = S('minecraft:white_concrete')
        ids[j + 2, z, x] = S('minecraft:sea_lantern')
        return (z, z, x, x)
    z0, x0 = z - 1, x - 3
    if not flat(g, z0, z, x0, x):
        return None
    j = int(g[z, x]) - by
    if not clear_ok(ids, kinds, j, z0, z, x0, x, 4):
        return None
    for xx in range(x0, x + 1):
        ids[j, z0, xx] = ids[j, z, xx] = S('minecraft:smooth_stone')
        ids[j + 1, z0, xx] = ids[j + 2, z0, xx] = S('minecraft:glass')
        ids[j + 3, z0, xx] = ids[j + 3, z, xx] = S('minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    for xx in (x0, x):
        ids[j + 1, z, xx] = ids[j + 2, z, xx] = S('minecraft:spruce_fence[east=false,north=false,south=false,waterlogged=false,west=false]')
    for xx in range(x0 + 1, x):
        ids[j + 1, z, xx] = S('minecraft:spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
    return (z0, z, x0, x)


def orchard_tree(ids, kinds, j, z, x, S, air, kind):
    """A small fruit tree: 2-block trunk, a 3 x 3 crown two high with a cap."""
    if not clear_ok(ids, kinds, j, z - 1, z + 1, x - 1, x + 1, 5):
        return False
    leaf = S(LEAVES.format(kind))
    ids[j + 1, z, x] = ids[j + 2, z, x] = S('minecraft:oak_log[axis=y]')
    for dy in (3, 4):
        for dz in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 4 and dz and dx:
                    continue
                ids[j + dy, z + dz, x + dx] = leaf
    ids[j + 5, z, x] = leaf
    return True


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
    p.add_argument('--edge-band', type=float, default=60, help='blocks this close to the plain edge may be orchards or hedged meadows')
    p.add_argument('--keep-file', type=Path)
    p.add_argument('--plain-mask', type=Path, help='npz with mask and origin: where fields may go; feather from its edge')
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
    if a.plain_mask:
        # fields only on the plain; the edge thins out where the plain ends (hills, rivers, towns), not where this
        # run's box ends, so neighbouring runs join without a seam
        pm = np.load(a.plain_mask)
        px0, pz0 = (int(v) for v in pm['origin'])
        mk = pm['mask']
        plain = np.zeros(ground.shape, bool)
        zs, xs = max(bz, pz0), max(bx, px0)
        ze, xe = min(bz + ground.shape[0], pz0 + mk.shape[0]), min(bx + ground.shape[1], px0 + mk.shape[1])
        if ze > zs and xe > xs:
            plain[zs - bz:ze - bz, xs - bx:xe - bx] = mk[zs - pz0:ze - pz0, xs - px0:xe - px0]
        free &= plain
        # feather from the plain's outer edge; ditches and lanes inside it are holes, not edges
        outer = ndimage.binary_fill_holes(ndimage.binary_closing(np.pad(plain, 12, constant_values=False), iterations=10))[12:-12, 12:-12] | plain
        d_edge = ndimage.distance_transform_edt(np.pad(outer, 1, constant_values=True))[1:-1, 1:-1]
    else:
        d_edge = ndimage.distance_transform_edt(inside)
    feather = np.clip(d_edge / a.feather * (.75 + .5 * vnoise(wx, wz, 23, a.seed)), 0, 1)
    ids = box.ids.copy()
    sid = {}

    def S(s):
        if s not in sid:
            sid[s] = box.state_id(s)
        return sid[s]
    air = S(tr.AIR_STATE)
    # plot orientation: long side across the nearest channels and roads (each plot's short end faces one), from the
    # smoothed direction of the distance gradient; north-south where nothing is near
    roads = built & ~tall_built
    lines = (wet | roads) & box.loaded
    phi_field = np.full(ground.shape, np.pi / 2)
    if lines.any():
        dl = ndimage.distance_transform_edt(~lines)
        gz_, gx_ = np.gradient(dl)
        jxx = ndimage.gaussian_filter(gx_ * gx_, 25)
        jxy = ndimage.gaussian_filter(gx_ * gz_, 25)
        jzz = ndimage.gaussian_filter(gz_ * gz_, 25)
        coh = np.hypot(jxx - jzz, 2 * jxy) / np.maximum(jxx + jzz, 1e-9)
        phi_field = np.where(coh > .3, .5 * np.arctan2(2 * jxy, jxx - jzz), np.pi / 2)
    dist_built = ndimage.distance_transform_edt(~built)
    bxs = cuts(x0, x1, a.block_x, a.seed + 1)
    bzs = cuts(z0, z1, a.block_z, a.seed + 2)
    plot_id = np.full(ground.shape, -1, np.int32)
    plot_kind = {}
    track = np.zeros(ground.shape, bool)
    channel = np.zeros(ground.shape, bool)
    hedge = np.zeros(ground.shape, bool)
    reserved = np.zeros(ground.shape, bool)
    grove = np.zeros(ground.shape, bool)
    windbreak = np.zeros(ground.shape, bool)
    kitchen = np.zeros(ground.shape, bool)
    orchards = []
    hamlets, shrines, junctions = [], [], []
    counts = dict(blocks=0, plots=0, houses=0, two_storey=0, barns=0, greenhouses=0, shrines=0, shelters=0, vending=0,
                  orchards=0, hedged_meadows=0, **{kk: 0 for kk in KINDS})
    cum = np.cumsum(a.mix) / np.sum(a.mix)
    H_, W_ = ground.shape

    def sl(za, zb, xa, xb):
        return (slice(min(max(za - bz, 0), H_), min(max(zb - bz + 1, 0), H_)), slice(min(max(xa - bx, 0), W_), min(max(xb - bx + 1, 0), W_)))
    n = 0
    for bi in range(len(bxs) - 1):
        for bj in range(len(bzs) - 1):
            X0, X1, Z0, Z1 = bxs[bi], bxs[bi + 1] - 1, bzs[bj], bzs[bj + 1] - 1
            if X1 < x0 or X0 > x1 or Z1 < z0 or Z0 > z1:
                continue
            bsl = sl(Z0, Z1, X0, X1)
            bfree = free[bsl]
            if bfree.sum() < 200:
                continue
            counts['blocks'] += 1
            tw = 2 + int(hash01(bi, bj, a.seed + 3) < .4)
            fb = float(np.mean(feather[bsl][bfree]))
            u_fate = float(hash01(bi, bj, a.seed + 13))
            fate = 'fields'
            # blocks that reach within --edge-band of the plain's outer edge become orchards and hedged meadows as often
            # as fields, so the farmland thins out instead of stopping on a line
            if float(d_edge[bsl][bfree].min()) < a.edge_band:
                fate = 'orchard' if u_fate < .25 else 'meadow' if u_fate < .5 else 'fields'
            # a hamlet in the south-east corner, or a shrine in the north-east
            if fate == 'fields' and fb > .6 and hash01(bi, bj, a.seed + 4) < 1 / a.house_every:
                hz, hx = Z1 - 26, X1 - 30
                if free[sl(hz, Z1, hx, X1)].mean() > .7:
                    hamlets.append((Z1, X1))
                    reserved[sl(hz, Z1, hx, X1)] = True
            elif hash01(bi, bj, a.seed + 20) < 1 / 8 and fb > .5:
                sz_, sx_ = Z0 + 16, X1 - 13
                if free[sl(sz_ - 21, sz_ + 9, sx_ - 9, sx_ + 9)].mean() > .7:
                    shrines.append((sz_, sx_))
                    reserved[sl(sz_ - 21, sz_ + 9, sx_ - 9, sx_ + 9)] = True
            bm = np.zeros(ground.shape, bool)
            bm[bsl] = True
            bm &= free & ~reserved
            if fate == 'meadow':
                counts['hedged_meadows'] += 1
                ring = bm & ~ndimage.binary_erosion(bm, iterations=1)
                hedge |= ring
                continue
            cz_c, cx_c = (Z0 + Z1) / 2, (X0 + X1) / 2
            phi = float(phi_field[min(max(int(cz_c) - bz, 0), H_ - 1), min(max(int(cx_c) - bx, 0), W_ - 1)])
            phi = round(phi / (np.pi / 12)) * (np.pi / 12)
            c, s_ = np.cos(phi), np.sin(phi)
            zb_, xb_ = np.nonzero(bm)
            if not len(zb_):
                continue
            # global frame of this orientation: blocks facing the same way share tracks and channels
            ug = (xb_ + bx) * c + (zb_ + bz) * s_
            vg = -(xb_ + bx) * s_ + (zb_ + bz) * c
            if fate == 'orchard':
                counts['orchards'] += 1
                pick = (np.round(ug).astype(int) % 6 == 0) & (np.round(vg).astype(int) % 5 == 0)
                kindsel = ['oak', 'azalea', 'oak', 'birch'][int(hash01(bi, bj, a.seed + 23) * 4)]
                orchards += [(int(zb_[i]), int(xb_[i]), kindsel) for i in np.nonzero(pick)[0]]
                ring = bm & ~ndimage.binary_erosion(bm, iterations=1)
                hedge |= ring & (hash01(wx, wz, a.seed + 24) < .5)
                continue
            SUP, PU = 60, 70
            vmod = np.mod(vg, 2 * SUP)
            is_track = vmod < tw
            umod = np.mod(ug, PU)
            is_chan = (umod < 1) & ~is_track
            track[zb_[is_track], xb_[is_track]] = True
            channel[zb_[is_chan], xb_[is_chan]] = True
            rest = ~is_track & ~is_chan
            # strips inside each 60-wide band, 4-13 wide, one-block aze between
            ks = np.floor(vg / SUP).astype(np.int64)
            vl = vg - ks * SUP
            sidx = np.full(len(zb_), -1, np.int64)
            for kk in np.unique(ks[rest]):
                bounds, p_, q = [], tw + 1 if (kk % 2 == 0) else 0, 0
                while p_ < SUP:
                    w = 4 + int(hash01(int(kk), q, a.seed + 5) * 10)
                    bounds.append((p_, min(p_ + w, SUP)))
                    p_ += w + 1
                    q += 1
                sel = np.nonzero(rest & (ks == kk))[0]
                for qi, (lo, hi) in enumerate(bounds):
                    inb = (vl[sel] >= lo) & (vl[sel] < hi)
                    sidx[sel[inb]] = (int(kk) + 1000000) * 32 + qi  # kept positive: rotated coordinates go negative
            # each strip between two channels is one plot, or two split at a random point
            ku = np.floor(ug / PU).astype(np.int64) + 1000000
            pid = np.full(len(zb_), -1, np.int64)
            ok_ = rest & (sidx >= 0)
            cut_at = 1 + (hash01(sidx, ku, a.seed + 25) * (PU - 2))
            two = hash01(sidx, ku, a.seed + 28) < .45
            second = two & (umod > cut_at)
            onaze = two & (np.abs(umod - cut_at) < .5)
            pid[ok_ & ~onaze] = (sidx * 100000 + ku * 2 + second)[ok_ & ~onaze]
            for key in np.unique(pid[pid >= 0]):
                sel = np.nonzero(pid == key)[0]
                if len(sel) < 24:
                    continue
                cz_, cx_ = zb_[sel], xb_[sel]
                if hash01(int(key % 1000003), bi, a.seed + 6) >= float(np.mean(feather[cz_, cx_])):
                    continue
                if plot_id[cz_[0], cx_[0]] >= 0:
                    continue
                kind = int(np.searchsorted(cum, float(hash01(int(key % 1000003), 7, a.seed + 7))))
                plot_id[cz_, cx_] = n
                plot_kind[n] = kind
                counts[KINDS[kind]] += 1
                n += 1
            # where this block's tracks meet a road
            tcells = np.zeros(ground.shape, bool)
            tcells[zb_[is_track], xb_[is_track]] = True
            near_road = tcells & (dist_built <= 5) & ~built
            if near_road.any() and hash01(bi, bj, a.seed + 21) < .5:
                zr, xr = np.argwhere(near_road)[0]
                junctions.append((int(zr), int(xr) + 3, hash01(bi, bj, a.seed + 22) < .55))
            if fb < .95:
                ring = bm & ~ndimage.binary_erosion(bm, iterations=1) & (plot_id < 0)
                hedge |= ring & (hash01(wx, wz, a.seed + 26) < .6 * (1 - fb) / .15)
    counts['plots'] = n
    counts['hamlet_sites'] = len(hamlets)
    # tracks run on to the road edge
    track_ext = inside & box.loaded & ~free & ~built & ~wet & ~kept & (dist_built >= 1) & (top_name == 'minecraft:grass_block')
    for _ in range(4):
        track |= ndimage.binary_dilation(track) & track_ext & (dist_built <= 5)
    # water a block down: channels and flooded paddies, kept only where every side is solid at that height
    lowered = plot_id >= 0
    water_plan = (channel & free & ~reserved) | np.isin(plot_id, [i for i, kk in plot_kind.items() if kk == 1])
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
            if u < .3 and ids[j + 2, z, x] == air:
                ids[j + 1, z, x], ids[j + 2, z, x] = S('minecraft:tall_grass[half=lower]'), S('minecraft:tall_grass[half=upper]')
            elif u < .62:
                ids[j + 1, z, x] = S('minecraft:grass')
            elif u < .68:
                ids[j + 1, z, x] = S(FLOWERS[int(u * 1000) % len(FLOWERS)])
    # farm tracks: dirt path in the middle, coarse dirt verges
    track_core = ndimage.binary_erosion(track, iterations=1) | (track & ~ndimage.binary_erosion(track, structure=np.ones((3, 3))) & (hash01(wx, wz, a.seed + 29) < .3))
    for z, x in zip(*np.nonzero(track & (free | track_ext) & ~reserved)):
        j = int(ground[z, x]) - by
        mid = hash01(wx[z, x], wz[z, x], a.seed + 10) < .85 and track_core[z, x]
        ids[j, z, x] = S('minecraft:dirt_path') if mid else S('minecraft:coarse_dirt')
        if ids[j + 1, z, x] != air and k[j + 1, z, x] == tr.SOFT:
            ids[j + 1, z, x] = air
    rng = np.random.default_rng(a.seed)
    kinds_arr = box.kinds
    # hamlets: one or two houses (some two-storey), a barn or a greenhouse, windbreak on the north and west, kitchen plots
    for (Z1h, X1h) in hamlets:
        zc, xc = Z1h - 8 - bz, X1h - 4 - bx
        st = 2 if hash01(Z1h, X1h, a.seed + 30) < .35 else 1
        fp = house(ids, box.kinds, ground, zc, xc, S, air, by, st)
        if fp is None:
            continue
        counts['houses'] += 1
        counts['two_storey'] += st == 2
        if hash01(Z1h, X1h, a.seed + 31) < .5:
            st2 = 2 if hash01(Z1h, X1h, a.seed + 32) < .25 else 1
            if house(ids, box.kinds, ground, zc, xc - 11, S, air, by, st2):
                counts['houses'] += 1
                counts['two_storey'] += st2 == 2
        if hash01(Z1h, X1h, a.seed + 33) < .5:
            counts['barns'] += barn(ids, box.kinds, ground, zc - 10, xc, S, air, by) is not None
        else:
            counts['greenhouses'] += greenhouse(ids, box.kinds, ground, zc - 10, xc, S, air, by) is not None
        windbreak[max(Z1h - 26 - bz, 0):Z1h - 19 - bz, max(X1h - 30 - bx, 0):X1h - bx + 1] = True
        windbreak[max(Z1h - 26 - bz, 0):Z1h - bz + 1, max(X1h - 30 - bx, 0):X1h - 24 - bx] = True
        kitchen[Z1h - 6 - bz:Z1h - bz - 1, X1h - 24 - bx:X1h - bx - 2] = True
    # shrines in a dense grove
    for (zc, xc) in shrines:
        fp = shrine(ids, box.kinds, ground, zc - bz, xc - bx, S, air, by)
        if fp is None:
            continue
        counts['shrines'] += 1
        g0 = np.zeros(ground.shape, bool)
        g0[sl(zc - 21, zc + 9, xc - 9, xc + 9)] = True
        g0[fp[0] - 1:fp[1] + 2, fp[2] - 1:fp[3] + 2] = False
        g0[fp[1] + 1:fp[1] + 10, fp[2] + 2:fp[3] - 1] = False
        grove |= g0
    # bus shelters and vending machines where tracks meet roads: the nearest spot 2-6 blocks off the road whose whole
    # footprint is grass and not taken by plots, tracks or another structure
    road_side = (dist_built >= 2) & (dist_built <= 8) & (top_name == 'minecraft:grass_block') & ~kept & ~wet & ~reserved \
        & (plot_id < 0) & ~track & box.loaded
    for (zr, xr, vend) in junctions:
        placed = False
        cand = [(abs(dz) + abs(dx), zr + dz, xr + dx) for dz in range(-12, 13) for dx in range(-12, 13)]
        for _, zc, xc in sorted(cand):
            if placed:
                break
            for kind in ((['vending'] if vend else ['shelter', 'shelter_ns', 'vending'])):
                fz0, fz1, fx0, fx1 = {'vending': (zc, zc, xc, xc), 'shelter': (zc - 1, zc, xc - 3, xc), 'shelter_ns': (zc - 3, zc, xc - 1, xc)}[kind]
                if fz0 < 0 or fx0 < 0 or fz1 >= H_ or fx1 >= W_ or not road_side[fz0:fz1 + 1, fx0:fx1 + 1].all():
                    continue
                counts['spot_' + kind] = counts.get('spot_' + kind, 0) + 1
                if kind == 'shelter_ns':
                    # bench toward the road: the road lies on the side with the smaller distance
                    east = dist_built[zc, min(xc + 1, W_ - 1)] < dist_built[zc, max(xc - 2, 0)]
                    built_ok = shelter_ns(ids, box.kinds, ground, zc, xc, S, air, by, road_east=bool(east))
                else:
                    built_ok = shelter(ids, box.kinds, ground, zc, xc, S, air, by, vending=(kind == 'vending'))
                if built_ok:
                    counts['vending' if kind == 'vending' else 'shelters'] += 1
                    road_side[max(fz0 - 2, 0):fz1 + 3, max(fx0 - 2, 0):fx1 + 3] = False
                    placed = True
                    break
    windbreak &= free & (plot_id < 0) & ~track
    kitchen &= free & (plot_id < 0) & ~track
    for z, x in zip(*np.nonzero(kitchen)):
        j = int(ground[z, x]) - by
        if box.kinds[ids[j + 1, z, x]] not in (tr.AIRK, tr.SOFT) or names[box.ids[j, z, x]] != 'minecraft:grass_block':
            continue
        crop = ['carrots', 'potatoes', 'beetroots'][int(hash01(wx[z, x] // 4, wz[z, x], a.seed + 11) * 3)]
        if wz[z, x] % 2:
            ids[j, z, x] = farmland
            ids[j + 1, z, x] = S(f'minecraft:{crop}[age=3]')
    # orchards and hedgerows
    for (z, x, kind) in orchards:
        j = int(ground[z, x]) - by
        orchard_tree(ids, box.kinds, j, z, x, S, air, kind)
    hedge &= free & (plot_id < 0) & ~track & ~channel & ~reserved
    hedge_u = hash01(wx, wz, a.seed + 27)
    for z, x in zip(*np.nonzero(hedge)):
        j = int(ground[z, x]) - by
        if ids[j + 1, z, x] != air and box.kinds[ids[j + 1, z, x]] != tr.SOFT:
            continue
        if hedge_u[z, x] < .82:
            leaf = S(LEAVES.format(['oak', 'dark_oak', 'azalea', 'oak'][int(hedge_u[z, x] * 400) % 4]))
            ids[j + 1, z, x] = leaf
            if hedge_u[z, x] < .2 and ids[j + 2, z, x] == air:
                ids[j + 2, z, x] = leaf
    # edge scrub and trees in the gaps the feather leaves, channel-side trees, windbreaks and shrine groves
    aze = ndimage.binary_dilation(plot_id >= 0, iterations=1) & (plot_id < 0)
    gap = inside & free & (plot_id < 0) & ~aze & ~track & ~channel & ~windbreak & ~kitchen & ~reserved & ~hedge & (feather < 1)
    d_water = ndimage.distance_transform_edt(~(wet | water_plan))
    bank = inside & free & (plot_id < 0) & ~aze & ~track & ~reserved & (d_water >= 2) & (d_water <= 3)
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
    c_con = np.where(windbreak, .6, 0) + np.where(grove, .45, 0) + np.where(gap, .06 * (1 - feather), 0)
    c_broad = np.where(windbreak, .25, 0) + np.where(grove, .45, 0) + np.where(gap, .22 * (1 - feather), 0) + np.where(bank, .12, 0)
    where = (windbreak | grove | gap | bank) & (top_name == 'minecraft:grass_block')
    tr.replant(box, ids, ground, where, road_keep | wet | water_plan | (plot_id >= 0) | track | kept | hedge, random.Random(a.seed), chance=(c_con, c_broad))
    # crowns of edge trees may reach 6 blocks past the box; tiles are planned one after another on the updated world
    rows = [r for r in tr.rows_between(box, ids) if x0 - 6 <= r[0] <= x1 + 6 and z0 - 6 <= r[2] <= z1 + 6]
    tr.write_rows(a.out / 'rows.json', rows)
    bases = {(q[0], q[2]) for q in rows if q[4].split('[')[0].endswith('_log') and 'stripped' not in q[4]}
    counts.update(cells=len(rows), open_water_columns=int(water_plan.sum()), trees=len(bases), area=a.area)
    (a.out / 'report.json').write_text(json.dumps(counts, indent=1), 'utf8')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
