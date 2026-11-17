"""M6 round 2 pilots for the Hakone hills: conifer plantation, pampas grassland, road cut protection, bamboo groves,
terraced paddies and Owakudani volcanic ground.

    plan_m6r2.py plantation --world W --mosaic M --at X Z --cells 40000 --out DIR [--keep-file F]
    plan_m6r2.py pampas     --world W --mosaic M --at X Z --cells 30000 --out DIR
    plan_m6r2.py roadcut    --world W --mosaic M --area x0 x1 z0 z1 --out DIR
    plan_m6r2.py bamboo     --world W --mosaic M --at X Z [--at X Z ...] --out DIR
    plan_m6r2.py terrace    --world W --mosaic M --at X Z --cells 10000 --out DIR
    plan_m6r2.py owaku      --world W --mosaic M --zone ZONE.npz --out DIR

Common rules: only natural ground and plants change; nothing within 3 blocks of anything built (8 for Owakudani),
on water, on other sessions' pending columns (--keep-file) or on unloaded chunks. Whole trees go together: a leaf or
branch belongs to the nearest trunk, and a tree is removed only when its trunk stands in the zone.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr
from plan_bare_faces import hash01, vnoise

LEAF = 'minecraft:{}_leaves[distance=1,persistent=true,waterlogged=false]'
PLANT_WORDS = ('grass', 'fern', 'flower', 'bush', 'poppy', 'dandelion', 'tulip', 'orchid', 'allium', 'bluet', 'daisy',
               'cornflower', 'lily_of_the_valley', 'rose', 'peony', 'lilac', 'sweet_berry', 'sapling')


class Area:
    def __init__(self, a, x0, x1, z0, z1, margin=10, built_gap=3):
        ox, oz = (int(v) for v in np.load(a.mosaic / 'origin.npy'))
        g = np.array(np.load(a.mosaic / 'ground.npy', mmap_mode='r')[z0 - margin - oz:z1 + margin - oz + 1, x0 - margin - ox:x1 + margin - ox + 1])
        g = g[g > -30000]
        self.box = tr.Box(a.world, x0 - margin, x1 + margin, int(g.min()) - 6, int(g.max()) + 30, z0 - margin, z1 + margin)
        b = self.box
        self.bx, self.by, self.bz = b.origin
        self.k = b.kind_grid()
        self.names = np.array([q.split('[')[0] for q in b.palette]).astype(str)
        self.ground = tr.top_of(self.k == tr.SOIL, self.by)
        self.wet = tr.top_of(self.k == tr.FLUID, self.by) >= self.ground
        yy = np.arange(self.k.shape[0])[:, None, None] + self.by
        self.built = ((self.k == tr.BUILT) & (yy >= self.ground[None] - 2)).any(0)
        self.kept = np.zeros(self.ground.shape, bool)
        if a.keep_file and a.keep_file.exists():
            for px, pz in json.loads(a.keep_file.read_text('utf8')):
                if self.bx <= px < self.bx + self.ground.shape[1] and self.bz <= pz < self.bz + self.ground.shape[0]:
                    self.kept[pz - self.bz, px - self.bx] = True
        jt = np.clip(self.ground - self.by, 0, self.k.shape[0] - 2)
        self.top = self.names[np.take_along_axis(b.ids, jt[None], 0)[0]]
        self.above = self.names[np.take_along_axis(b.ids, (jt + 1)[None], 0)[0]]
        self.keepout = (ndimage.binary_dilation(self.built, iterations=built_gap) if built_gap else self.built) | self.wet | self.kept | ~b.loaded
        zz, xx = np.mgrid[0:self.ground.shape[0], 0:self.ground.shape[1]]
        self.wx, self.wz = xx + self.bx, zz + self.bz
        g0 = self.ground.astype(np.float32)
        gy, gx = np.gradient(ndimage.gaussian_filter(g0, 2))
        self.slope = np.hypot(gx, gy)
        self.tpi = g0 - ndimage.gaussian_filter(g0, 25)
        self.ids = b.ids.copy()
        self._sid = {}
        is_log = np.char.endswith(self.names, '_log') | np.char.endswith(self.names, '_wood')
        is_leaf = np.char.endswith(self.names, '_leaves')
        self.is_log, self.is_leaf = is_log, is_leaf
        # trunks: a log standing on the ground
        self.trunk = is_log[np.take_along_axis(b.ids, (jt + 1)[None], 0)[0]] & b.loaded
        self.canopy = is_leaf[b.ids].any(0)

    def S(self, s):
        if s not in self._sid:
            self._sid[s] = self.box.state_id(s)
            # keep the per-state tables as long as the palette
            while len(self.is_log) < len(self.box.palette):
                n = self.box.palette[len(self.is_log)].split('[')[0]
                self.is_log = np.append(self.is_log, n.endswith(('_log', '_wood')))
                self.is_leaf = np.append(self.is_leaf, n.endswith('_leaves'))
        return self._sid[s]

    def owner(self):
        """For every column: the nearest trunk (z, x) and the distance to it."""
        d, (iz, ix) = ndimage.distance_transform_edt(~self.trunk, return_indices=True)
        return d, iz, ix

    def clear_trees(self, zone, keep_trunks=None, reach=7, leaves_only=False):
        """Remove the trees whose trunk stands in zone (all logs and leaves they own). Returns the trunk count."""
        d, iz, ix = self.owner()
        doomed = self.trunk & zone
        if keep_trunks is not None:
            doomed &= ~keep_trunks
        own = doomed[iz, ix] & (d <= reach)
        air = self.S(tr.AIR_STATE)
        y_lo = np.clip(self.ground - self.by + 1, 0, self.ids.shape[0] - 1)
        cols = np.nonzero(own)
        for z, x in zip(*cols):
            j0 = int(y_lo[z, x])
            col = self.ids[j0:, z, x]
            m = self.is_leaf[col] if leaves_only else (self.is_leaf[col] | self.is_log[col])
            col[m] = air
        return int(doomed.sum())

    def clear_plants(self, where):
        air = self.S(tr.AIR_STATE)
        for z, x in zip(*np.nonzero(where)):
            j = int(self.ground[z, x]) - self.by
            for dy in (1, 2):
                if 0 <= j + dy < self.ids.shape[0]:
                    n = self.box.palette[self.ids[j + dy, z, x]].split('[')[0]
                    if self.box.kinds[self.ids[j + dy, z, x]] == tr.SOFT and not n.endswith(('_log', '_leaves')):
                        self.ids[j + dy, z, x] = air

    def free_above(self, z, x, j, h):
        if j + h + 1 >= self.ids.shape[0]:
            return False
        sp = self.box.kinds[self.ids[j + 1:j + h + 1, z, x]]
        return bool(((sp == tr.AIRK) | (sp == tr.SOFT)).all())

    def rows(self, x0, x1, z0, z1, pad=7):
        return [r for r in tr.rows_between(self.box, self.ids) if x0 - pad <= r[0] <= x1 + pad and z0 - pad <= r[2] <= z1 + pad]


def pick_zone(A, cand, at, cells, band=True):
    """The connected part of cand nearest to the point at, cut to about cells columns along the contours: an elevation
    band round the point's height is widened until it holds enough, so the edges follow the terrain."""
    pz, px = at[1] - A.bz, at[0] - A.bx
    lab, n = ndimage.label(cand)
    if not n:
        return np.zeros(cand.shape, bool)
    d = ndimage.distance_transform_edt(lab == 0, return_indices=True)[1]
    k = lab[d[0][pz, px], d[1][pz, px]]
    comp = lab == k
    if comp.sum() <= cells or not band:
        return comp
    h0 = float(A.ground[d[0][pz, px], d[1][pz, px]])
    wob = (vnoise(A.wx, A.wz, 30, 5) - .5) * 6
    g = A.ground + wob
    lo, hi = 0.0, 200.0
    best = comp
    for _ in range(24):
        w = (lo + hi) / 2
        m = comp & (np.abs(g - h0) <= w)
        lab2, _ = ndimage.label(m)
        kk = lab2[d[0][pz, px], d[1][pz, px]] if m[d[0][pz, px], d[1][pz, px]] else 0
        m = lab2 == kk if kk else m & False
        if m.sum() > cells:
            hi = w
            best = m
        else:
            lo = w
            if m.sum() > .8 * cells:
                best = m
    return best


def cedar(A, z, x, h, rng):
    """A planted sugi: straight spruce trunk, narrow crown on the upper half (radius 1, a plus at the top)."""
    j = int(A.ground[z, x]) - A.by
    if z < 1 or x < 1 or z + 1 >= A.ids.shape[1] or x + 1 >= A.ids.shape[2] or not A.free_above(z, x, j, h + 2):
        return False
    log, leaf = A.S('minecraft:spruce_log[axis=y]'), A.S(LEAF.format('spruce'))
    air_like = lambda s: A.box.kinds[s] in (tr.AIRK, tr.SOFT) and not A.box.palette[s].split('[')[0].endswith(('_log', '_leaves'))
    for dy in range(1, h + 1):
        A.ids[j + dy, z, x] = log
    c0 = j + int(h * .45)
    for y in range(c0, j + h + 2):
        top = y >= j + h - 1
        full = (not top) and ((y - c0) % 3 != 2) and y < j + h - 2
        for dz in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dz == 0 and dx == 0:
                    if y > j + h:
                        A.ids[y, z, x] = leaf
                    continue
                if not full and dz and dx:
                    continue
                if y > j + h and (dz or dx):
                    continue
                if air_like(A.ids[y, z + dz, x + dx]):
                    A.ids[y, z + dz, x + dx] = leaf
    return True


def broadleaf_tree(A, z, x, rng, kinds=('oak', 'dark_oak', 'oak', 'birch')):
    """A full broadleaf crown: trunk 4-7, leaf ball radius 2.5-3.2 centred near the top."""
    j = int(A.ground[z, x]) - A.by
    h = 4 + int(rng.integers(0, 4))
    r = 2.5 + rng.random() * .7
    kind = kinds[int(rng.integers(len(kinds)))]
    if not A.free_above(z, x, j, h + 3):
        return False
    log, leaf = A.S(f'minecraft:{kind}_log[axis=y]'), A.S(LEAF.format(kind))
    for dy in range(1, h + 1):
        A.ids[j + dy, z, x] = log
    cy = j + h
    ri = int(np.ceil(r))
    for dy in range(-2, ri + 1):
        for dz in range(-ri, ri + 1):
            for dx in range(-ri, ri + 1):
                if dz * dz + dx * dx + (dy * 1.3) ** 2 > r * r + rng.random() * .6:
                    continue
                y, zz, xx = cy + dy, z + dz, x + dx
                if not (0 <= y < A.ids.shape[0] and 0 <= zz < A.ids.shape[1] and 0 <= xx < A.ids.shape[2]):
                    continue
                s_ = A.ids[y, zz, xx]
                if A.box.kinds[s_] in (tr.AIRK, tr.SOFT) and not A.box.palette[s_].split('[')[0].endswith(('_log', '_leaves')):
                    A.ids[y, zz, xx] = leaf
    return True


def cmd_plantation(a):
    X, Z = a.at
    R = 340
    A = Area(a, X - R, X + R, Z - R, Z + R)
    forest = ndimage.uniform_filter(A.canopy.astype(np.float32), 15) > .4
    # the stand stays well inside the planning box behind a wavy limit, so no edge comes out ruler-straight
    H_, W_ = A.ground.shape
    zz_, xx_ = np.mgrid[0:H_, 0:W_]
    d_box = np.minimum(np.minimum(zz_, H_ - 1 - zz_), np.minimum(xx_, W_ - 1 - xx_))
    inner = d_box > 60 + 45 * vnoise(A.wx, A.wz, 22, 9)
    mid = forest & (np.abs(A.tpi) < a.tpi_band) & (A.slope > .2) & (A.slope < 1.8) & ~A.keepout & inner
    mid = ndimage.binary_opening(mid, iterations=3)
    zone = pick_zone(A, mid, (X, Z), a.cells)
    zone = ndimage.binary_closing(zone, iterations=3) & ~A.keepout
    zone = ndimage.binary_opening(zone, iterations=2)
    # ridges and valleys next to the stand become broadleaf
    near = ndimage.binary_dilation(zone, iterations=40) & ~zone
    edge = near & forest & ((A.tpi >= a.tpi_band) | (A.tpi <= -a.tpi_band)) & ~A.keepout
    canopy_before = float(A.canopy[edge].mean()) if edge.any() else 0
    spruce_trunks = edge & A.trunk & np.isin(A.above, ['minecraft:spruce_log'])
    old_spruce = np.argwhere(spruce_trunks)
    n_cut = A.clear_trees(zone)
    n_cut_edge = A.clear_trees(spruce_trunks)
    A.clear_plants(zone)
    rng = np.random.default_rng(a.seed)
    # the stand: an exact 3-block grid, one height per row band, so it reads as one even-aged planting
    planted = 0
    for z, x in zip(*np.nonzero(zone & (A.wx % 3 == 0) & (A.wz % 3 == 0))):
        if A.top[z, x] not in ('minecraft:grass_block', 'minecraft:dirt', 'minecraft:podzol', 'minecraft:coarse_dirt', 'minecraft:moss_block'):
            continue
        h = 14 + (1 if hash01(A.wx[z, x] // 24, A.wz[z, x] // 24, 5) < .5 else 0)
        planted += cedar(A, z, x, h, rng)
    # dark floor: mostly podzol and coarse dirt, very few plants
    floor = vnoise(A.wx, A.wz, 6, 7)
    for z, x in zip(*np.nonzero(zone)):
        j = int(A.ground[z, x]) - A.by
        if A.top[z, x] not in ('minecraft:grass_block', 'minecraft:dirt'):
            continue
        if floor[z, x] > .32:
            A.ids[j, z, x] = A.S('minecraft:podzol[snowy=false]')
        elif floor[z, x] < .2:
            A.ids[j, z, x] = A.S('minecraft:coarse_dirt')
        if hash01(A.wx[z, x], A.wz[z, x], 8) < .04 and A.ids[j + 1, z, x] == A.S(tr.AIR_STATE):
            A.ids[j + 1, z, x] = A.S('minecraft:fern')
    # broadleaf on the ridges and in the valleys: one broad crown where each spruce stood, then fill any gap left
    # until the canopy is at least what it was
    keep = A.keepout | zone
    bl = 0
    for z, x in old_spruce:
        if not keep[z, x]:
            bl += broadleaf_tree(A, z, x, rng)
    is_leaf = np.array([q.split('[')[0].endswith('_leaves') for q in A.box.palette])
    cover = is_leaf[A.ids].any(0)
    gaps = edge & ~ndimage.binary_dilation(cover, iterations=1) & ~keep
    pts = np.argwhere(gaps)
    rng.shuffle(pts)
    filled = np.zeros(gaps.shape, bool)
    for z, x in pts:
        if filled[z, x] or A.top[z, x] not in ('minecraft:grass_block', 'minecraft:dirt', 'minecraft:podzol', 'minecraft:coarse_dirt', 'minecraft:moss_block'):
            continue
        if broadleaf_tree(A, z, x, rng):
            bl += 1
            filled[max(0, z - 3):z + 4, max(0, x - 3):x + 4] = True
    is_leaf = np.array([q.split('[')[0].endswith('_leaves') for q in A.box.palette])
    canopy_after = float(is_leaf[A.ids].any(0)[edge].mean()) if edge.any() else 0
    rows = A.rows(X - R, X + R, Z - R, Z + R)
    rep = dict(zone_columns=int(zone.sum()), broadleaf_edge_columns=int(edge.sum()), trees_removed=n_cut + n_cut_edge, cedars=planted, broadleaf_planted=bl,
               edge_canopy_before=round(canopy_before, 3), edge_canopy_after=round(canopy_after, 3), cells=len(rows))
    return rows, rep, zone, A


def cmd_pampas(a):
    X, Z = a.at
    R = 220
    A = Area(a, X - R, X + R, Z - R, Z + R)
    cand = ~A.keepout & (A.slope > .03) & (A.slope < a.max_slope) & np.isin(A.top, ['minecraft:grass_block', 'minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:podzol']) \
        & (A.tpi > a.min_tpi) & ~ndimage.binary_dilation(A.built, iterations=8)
    cand = ndimage.binary_closing(cand, iterations=3) & ~A.keepout
    zone = pick_zone(A, cand, (X, Z), a.cells)
    # one open field: holes left by steep bits or old tree clumps are filled, so no copse stands inside it
    zone = ndimage.binary_fill_holes(ndimage.binary_closing(zone, iterations=6)) & ~A.keepout & ~A.wet
    # keep a handful of lone trees, at least 40 blocks apart
    trunks = np.argwhere(A.trunk & zone)
    keep = np.zeros(zone.shape, bool)
    chosen = []
    for z, x in trunks[np.argsort(hash01(A.wx[trunks[:, 0], trunks[:, 1]], A.wz[trunks[:, 0], trunks[:, 1]], 11))]:
        if all((z - cz) ** 2 + (x - cx) ** 2 >= 1600 for cz, cx in chosen):
            chosen.append((z, x))
            keep[z, x] = True
        if len(chosen) >= a.lone:
            break
    n_cut = A.clear_trees(zone, keep_trunks=keep)
    A.clear_plants(zone)
    tall = (A.S('minecraft:tall_grass[half=lower]'), A.S('minecraft:tall_grass[half=upper]'))
    air = A.S(tr.AIR_STATE)
    dens = vnoise(A.wx, A.wz, 11, 12) * .6 + vnoise(A.wx, A.wz, 3, 13) * .4
    # colour patches that read from a distance: dark large-fern drifts and pale drifts where tall grass thins and
    # white flowers (oxeye daisy, lily of the valley) show between the tufts, like the silver of the plumes
    patch = vnoise(A.wx, A.wz, 17, 15)
    large_fern = (A.S('minecraft:large_fern[half=lower]'), A.S('minecraft:large_fern[half=upper]'))
    pale = [A.S('minecraft:oxeye_daisy'), A.S('minecraft:lily_of_the_valley'), A.S('minecraft:azure_bluet')]
    for z, x in zip(*np.nonzero(zone)):
        j = int(A.ground[z, x]) - A.by
        if A.ids[j + 1, z, x] != air or j + 2 >= A.ids.shape[0]:
            continue
        if A.top[z, x] in ('minecraft:dirt', 'minecraft:coarse_dirt'):
            A.ids[j, z, x] = A.S(tr.GRASS)
        u = float(hash01(A.wx[z, x], A.wz[z, x], 14))
        free2 = A.ids[j + 2, z, x] == air
        if a.patches and patch[z, x] < .28:
            if u < .55 and free2:
                A.ids[j + 1, z, x], A.ids[j + 2, z, x] = large_fern
            elif u < .8 and free2:
                A.ids[j + 1, z, x], A.ids[j + 2, z, x] = tall
            continue
        if a.patches and patch[z, x] > .7:
            if u < .45 and free2:
                A.ids[j + 1, z, x], A.ids[j + 2, z, x] = tall
            elif u < .85:
                A.ids[j + 1, z, x] = pale[int(u * 1000) % 3]
            continue
        p = .55 + .4 * dens[z, x]
        if u < p and free2:
            A.ids[j + 1, z, x], A.ids[j + 2, z, x] = tall
        elif u < p + .12:
            A.ids[j + 1, z, x] = A.S('minecraft:grass')
        elif u < p + .15:
            A.ids[j + 1, z, x] = A.S('minecraft:fern')
    rows = A.rows(X - R, X + R, Z - R, Z + R)
    return rows, dict(zone_columns=int(zone.sum()), trees_removed=n_cut, lone_trees_kept=len(chosen), cells=len(rows)), zone, A


def cmd_roadcut(a):
    x0, x1, z0, z1 = a.area
    A = Area(a, x0, x1, z0, z1, margin=6, built_gap=0)
    bname = A.names[np.take_along_axis(A.box.ids, np.clip(tr.top_of(A.k == tr.BUILT, A.by) - A.by, 0, A.k.shape[0] - 1)[None], 0)[0]]
    road = (np.char.startswith(bname, 'trafficcraft:') | (np.char.find(bname, 'asphalt') >= 0)) & (tr.top_of(A.k == tr.BUILT, A.by) >= A.by)
    # the kerb and sidewalk beside the carriageway count as road too
    walk = np.isin(bname, ['minecraft:smooth_stone', 'minecraft:smooth_stone_slab', 'minecraft:stone_bricks', 'minecraft:polished_andesite'])         & ndimage.binary_dilation(road, iterations=3) & (tr.top_of(A.k == tr.BUILT, A.by) >= A.by)
    if a.sidewalk:
        road |= walk
    solidtop = tr.top_of((A.k == tr.BUILT) | (A.k == tr.SOIL), A.by)
    d, (iz, ix) = ndimage.distance_transform_edt(~road, return_indices=True)
    road_y = tr.top_of(A.k == tr.BUILT, A.by)[iz, ix]  # the road surface, even under soil
    natural = ~A.built & ~A.wet & ~A.kept & A.box.loaded
    cut = natural & (d >= 1) & (d <= a.reach) & (A.ground - road_y >= a.min_h)
    cut = ndimage.binary_opening(cut, iterations=1) | (cut & ndimage.binary_dilation(cut, iterations=1))
    # soil left hanging over the road edge (old terrain above the carriageway) is cleared first, so the face reaches
    # down to the road
    builttop = tr.top_of(A.k == tr.BUILT, A.by)
    hang = road & (A.ground > builttop) & ~A.kept & A.box.loaded
    # only lips: at most 6 soil blocks thick and no wider than 4 columns (a road is wider); tunnel roofs stay
    soil_n = ((A.k == tr.SOIL) & (np.arange(A.k.shape[0])[:, None, None] + A.by > builttop[None])).sum(0)
    hang &= soil_n <= a.lip_thick
    if a.lip_narrow:
        wide = ndimage.binary_dilation(ndimage.binary_erosion(hang, iterations=2), iterations=3)
        hang &= ~wide
    air = A.S(tr.AIR_STATE)
    hung = 0
    for z, x in zip(*np.nonzero(hang)):
        for y in range(int(builttop[z, x]) + 1, int(A.ground[z, x]) + 3):
            jj = y - A.by
            if 0 <= jj < A.ids.shape[0] and A.box.kinds[A.ids[jj, z, x]] in (tr.SOIL, tr.SOFT):
                A.ids[jj, z, x] = air
                hung += 1
    surface = np.where(hang, builttop, np.maximum(solidtop, A.ground))
    cut = natural & ~hang & (d >= 1) & (d <= a.reach) & (A.ground - road_y >= a.min_h)
    # the face: in each cut column, the cells below its ground down to the level of a lower neighbour
    pad = np.pad(np.where(A.box.loaded, surface, 10 ** 6), 1, constant_values=10 ** 6)
    low = np.min([pad[:-2, 1:-1], pad[2:, 1:-1], pad[1:-1, :-2], pad[1:-1, 2:]], axis=0)
    frame, cellb = A.S('minecraft:light_gray_concrete'), A.S('minecraft:moss_block')
    replace = np.isin(A.names, ['minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:grass_block', 'minecraft:stone', 'minecraft:gravel',
                                'minecraft:rooted_dirt', 'minecraft:moss_block', 'minecraft:andesite', 'minecraft:tuff', 'minecraft:cobblestone',
                                'minecraft:mossy_cobblestone', 'minecraft:podzol'])
    faces = 0
    for z, x in zip(*np.nonzero(cut)):
        g, lo = int(A.ground[z, x]), int(low[z, x])
        if g - lo < (2 if a.reach <= 4 else 4):
            continue
        along = A.wx[z, x] if abs(int(iz[z, x]) - z) >= abs(int(ix[z, x]) - x) else A.wz[z, x]
        for y in range(lo + 1, g + 1):
            jj = y - A.by
            if not replace[A.box.ids[jj, z, x]]:
                continue
            on_frame = (y - lo) % 3 == 0 or along % 3 == 0 or y == g
            A.ids[jj, z, x] = frame if on_frame else cellb
            faces += 1
    # gutter at the foot: the verge column between face and road gets a smooth stone channel
    foot = natural & ~cut & ndimage.binary_dilation(cut, iterations=1) & (d >= 1) & (d <= 2) & (np.abs(A.ground - road_y) <= 1)
    gutters = 0
    for z, x in zip(*np.nonzero(foot)):
        j = int(A.ground[z, x]) - A.by
        if A.box.kinds[A.ids[j + 1, z, x]] not in (tr.AIRK, tr.SOFT):
            continue
        A.ids[j, z, x] = A.S('minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
        A.ids[j - 1, z, x] = A.S('minecraft:smooth_stone')
        if A.box.kinds[A.ids[j + 1, z, x]] == tr.SOFT:
            A.ids[j + 1, z, x] = A.S(tr.AIR_STATE)
        gutters += 1
    rows = A.rows(x0, x1, z0, z1, pad=0)
    return rows, dict(cut_columns=int(cut.sum()), face_cells=faces, gutter_columns=gutters, overhang_cells=hung, cells=len(rows)), cut, A


def cmd_bamboo(a):
    allrows, rep, zones = [], dict(groves=0, culms=0, cells=0), []
    world_rows = {}
    for i, (X, Z) in enumerate(zip(a.at[::2], a.at[1::2])):
        R = 90
        A = Area(a, X - R, X + R, Z - R, Z + R)
        # apply rows of earlier groves so overlapping areas build on them
        for (x, y, z), r in world_rows.items():
            if A.bx <= x < A.bx + A.ids.shape[2] and A.bz <= z < A.bz + A.ids.shape[1] and A.by <= y < A.by + A.ids.shape[0]:
                A.ids[y - A.by, z - A.bz, x - A.bx] = A.S(r[4])
        houses = A.built & ~A.wet
        dh = ndimage.distance_transform_edt(~houses) if houses.any() else np.full(A.ground.shape, 1e4)
        cand = ~A.keepout & (dh >= 4) & (dh <= 24) & np.isin(A.top, ['minecraft:grass_block', 'minecraft:dirt', 'minecraft:podzol', 'minecraft:coarse_dirt']) & (A.slope < 1.4)
        blob = vnoise(A.wx, A.wz, 14, 20 + i) > .45
        lab, n = ndimage.label(cand & blob)
        if not n:
            continue
        sizes = ndimage.sum(cand & blob, lab, range(1, n + 1))
        zone = lab == (1 + int(np.argmax(sizes)))
        if zone.sum() > a.cells:
            dd = ndimage.distance_transform_edt(~(houses))
            order = np.argsort(np.where(zone, dd, 1e9).ravel())[:a.cells]
            z2 = np.zeros(zone.size, bool)
            z2[order] = True
            zone = z2.reshape(zone.shape) & zone
        A.clear_trees(zone)
        A.clear_plants(zone)
        air = A.S(tr.AIR_STATE)
        culms = 0
        for z, x in zip(*np.nonzero(zone)):
            if hash01(A.wx[z, x], A.wz[z, x], 21) > .5:
                continue
            j = int(A.ground[z, x]) - A.by
            h = 8 + int(hash01(A.wx[z, x], A.wz[z, x], 22) * 7)
            if not A.free_above(z, x, j, h + 1):
                continue
            if A.top[z, x] != 'minecraft:grass_block':
                A.ids[j, z, x] = A.S(tr.GRASS)
            for dy in range(1, h + 1):
                lv = 'none' if dy < h - 2 else ('small' if dy == h - 2 else 'large')
                A.ids[j + dy, z, x] = A.S(f'minecraft:bamboo[age=1,leaves={lv},stage=0]')
            culms += 1
        # shoots and grass at the edge
        rim = ndimage.binary_dilation(zone, iterations=2) & ~zone & ~A.keepout
        for z, x in zip(*np.nonzero(rim)):
            j = int(A.ground[z, x]) - A.by
            u = hash01(A.wx[z, x], A.wz[z, x], 23)
            if A.ids[j + 1, z, x] != air or A.top[z, x] != 'minecraft:grass_block':
                continue
            if u < .12:
                A.ids[j + 1, z, x] = A.S('minecraft:bamboo_sapling')
            elif u < .35 and A.ids[j + 2, z, x] == air:
                A.ids[j + 1, z, x], A.ids[j + 2, z, x] = A.S('minecraft:tall_grass[half=lower]'), A.S('minecraft:tall_grass[half=upper]')
        rows = A.rows(X - R, X + R, Z - R, Z + R)
        for r in rows:
            world_rows[tuple(r[:3])] = r
        rep['groves'] += 1
        rep['culms'] += culms
        rep[f'grove_{X}_{Z}'] = int(zone.sum())
    merged = {}
    for k_, r in world_rows.items():
        merged[k_] = r
    allrows = list(merged.values())
    rep['cells'] = len(allrows)
    return allrows, rep, None, None


def cmd_terrace(a):
    X, Z = a.at
    R = 160
    A = Area(a, X - R, X + R, Z - R, Z + R)
    cand = ~A.keepout & (A.slope > .1) & (A.slope < .6) & np.isin(A.top, ['minecraft:grass_block']) & ~A.canopy
    zone = pick_zone(A, ndimage.binary_closing(cand, iterations=2) & ~A.keepout, (X, Z), a.cells)
    # each flat step (connected columns of one height) of 20+ columns becomes a paddy; its edge stays grass (the bund)
    g = np.where(zone, A.ground, -10 ** 6)
    paddies = np.zeros(zone.shape, bool)
    n_p = 0
    for h in np.unique(g[zone]):
        lab, n = ndimage.label(g == h)
        for i in range(1, n + 1):
            m = lab == i
            inner = ndimage.binary_erosion(m, iterations=1)
            if inner.sum() >= 20:
                paddies |= inner
                n_p += 1
    A.clear_trees(paddies)
    A.clear_plants(paddies)
    air = A.S(tr.AIR_STATE)
    flooded = hash01(np.floor(A.wx / 9), np.floor(A.wz / 9), 31) < .25
    for z, x in zip(*np.nonzero(paddies)):
        j = int(A.ground[z, x]) - A.by
        A.ids[j, z, x] = air
        if flooded[z, x]:
            A.ids[j - 1, z, x] = A.S('minecraft:water[level=0]')
            A.ids[j - 2, z, x] = A.S('minecraft:mud')
            if A.wx[z, x] % 3 == 0 and hash01(A.wx[z, x], A.wz[z, x], 32) < .4:
                A.ids[j - 1, z, x] = A.S('minecraft:seagrass')
        else:
            A.ids[j - 1, z, x] = A.S('minecraft:farmland[moisture=7]')
            A.ids[j, z, x] = A.S(f'minecraft:wheat[age={1 + int(hash01(A.wx[z, x] // 9, A.wz[z, x] // 9, 33) * 3)}]')
    # water must be held on every side
    for z, x in zip(*np.nonzero(paddies & flooded)):
        j = int(A.ground[z, x]) - A.by - 1
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            zz_, xx_ = z + dz, x + dx
            s = A.ids[j, zz_, xx_]
            if A.box.kinds[s] in (tr.AIRK, tr.SOFT) and not (paddies[zz_, xx_] and flooded[zz_, xx_]):
                A.ids[j, z, x] = A.S('minecraft:farmland[moisture=7]')
                A.ids[j + 1, z, x] = A.S('minecraft:wheat[age=2]')
                break
    rows = A.rows(X - R, X + R, Z - R, Z + R)
    return rows, dict(zone_columns=int(zone.sum()), paddies=n_p, paddy_columns=int(paddies.sum()), cells=len(rows)), zone, A


def cmd_terrace2(a):
    """Regrade an open slope into level benches (--step blocks high, from the smoothed slope, so each bench follows
    the contour), face the risers with mossy stone, and make paddies of the bench floors with a grass bund on the
    outer edge."""
    X, Z = a.at
    R = 160
    A = Area(a, X - R, X + R, Z - R, Z + R)
    # trees on the slope are cleared for the fields, as real terraces are
    cand = ~A.keepout & (A.slope > .12) & (A.slope < .7) & np.isin(A.top, ['minecraft:grass_block', 'minecraft:dirt'])         & ~ndimage.binary_dilation(A.built, iterations=6)
    cand = ndimage.binary_opening(cand, iterations=2)
    zone = pick_zone(A, cand, (X, Z), a.cells)
    zone = ndimage.binary_erosion(zone, iterations=1)
    g = A.ground.astype(np.float32)
    smooth = ndimage.gaussian_filter(g, 3)
    step = a.step
    bench = np.floor(smooth / step) * step
    target = np.where(zone, bench, g)
    # ease the zone edge back to the old ground at a slope of one
    d_out = ndimage.distance_transform_edt(zone)
    target = np.where(zone & (d_out <= 2), np.clip(target, g - d_out, g + d_out), target)
    frozen = ~zone
    A.clear_trees(zone)
    new_ids, change = tr.apply_heights(A.box, A.ground, target, frozen, rng_seed=a.seed, cover=False)
    A.ids = new_ids
    t = np.round(target).astype(int)
    # risers: a bench column with a lower neighbour; its exposed cells become mossy stone
    pad = np.pad(t, 1, mode='edge')
    low = np.min([pad[:-2, 1:-1], pad[2:, 1:-1], pad[1:-1, :-2], pad[1:-1, 2:]], axis=0)
    riser = zone & (low < t)
    stone = [A.S('minecraft:mossy_cobblestone'), A.S('minecraft:cobblestone'), A.S('minecraft:mossy_stone_bricks')]
    for z, x in zip(*np.nonzero(riser)):
        for y in range(int(low[z, x]) + 1, int(t[z, x])):
            jj = y - A.by
            if A.box.kinds[A.ids[jj, z, x]] == tr.SOIL:
                A.ids[jj, z, x] = stone[int(hash01(A.wx[z, x], y, A.wz[z, x], 51) * 3)]
    # paddy floors: bench columns away from the riser edge; bund = the outer row
    # the riser top is the bund; everything behind it on the bench is paddy (the zone edge stays grass)
    floor = zone & ~riser & ndimage.binary_erosion(zone, iterations=1)
    lab, n = ndimage.label(floor)
    sizes = ndimage.sum(floor, lab, range(1, n + 1)) if n else []
    keep = np.isin(lab, 1 + np.nonzero(np.array(sizes) >= 12)[0]) if n else floor
    paddy = keep
    air = A.S(tr.AIR_STATE)
    flooded = hash01(lab, 7, 52) < .25
    nf = 0
    for z, x in zip(*np.nonzero(paddy)):
        j = int(t[z, x]) - A.by
        if A.box.kinds[A.ids[j + 1, z, x]] == tr.SOFT:
            A.ids[j + 1, z, x] = air
        A.ids[j, z, x] = air
        held = all(int(t[z + dz, x + dx]) >= int(t[z, x]) for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if flooded[z, x] and held:
            A.ids[j - 1, z, x] = A.S('minecraft:water[level=0]')
            A.ids[j - 2, z, x] = A.S('minecraft:mud')
            nf += 1
            if A.wx[z, x] % 3 == 0 and hash01(A.wx[z, x], A.wz[z, x], 53) < .4:
                A.ids[j - 1, z, x] = A.S('minecraft:seagrass')
        else:
            A.ids[j - 1, z, x] = A.S('minecraft:farmland[moisture=7]')
            A.ids[j, z, x] = A.S(f'minecraft:wheat[age={1 + int(hash01(lab[z, x], 9, 54) * 3)}]')
    rows = A.rows(X - R, X + R, Z - R, Z + R)
    return rows, dict(zone_columns=int(zone.sum()), changed_columns=int(change.sum()), riser_columns=int(riser.sum()), paddy_columns=int(paddy.sum()),
                      flooded_columns=nf, cells=len(rows)), zone, A


def cmd_owaku(a):
    zz = np.load(a.zone)
    zx0, zz0 = (int(v) for v in zz['origin'])
    zm = zz['mask']
    x0, z0 = zx0, zz0
    x1, z1 = zx0 + zm.shape[1] - 1, zz0 + zm.shape[0] - 1
    A = Area(a, x0, x1, z0, z1, margin=30, built_gap=8)
    zone = np.zeros(A.ground.shape, bool)
    zone[z0 - A.bz:z1 - A.bz + 1, x0 - A.bx:x1 - A.bx + 1] = zm
    zone &= ~A.keepout
    # bare core: the valley floor and the south-facing slope, shaped by noise, about --cells columns
    cz_, cx_ = a.core[1] - A.bz, a.core[0] - A.bx
    dist = np.hypot(A.wx - a.core[0], A.wz - a.core[1]) * (.75 + .5 * vnoise(A.wx, A.wz, 26, 41))
    lo, hi = 10.0, 400.0
    for _ in range(24):
        r = (lo + hi) / 2
        if (zone & (dist <= r)).sum() > a.cells:
            hi = r
        else:
            lo = r
    core = zone & (dist <= lo)
    core = ndimage.binary_opening(core, iterations=2)
    ring = zone & ~core & (dist <= lo + 22)
    A.clear_trees(core)
    A.clear_plants(core)
    # dead trees round it: trunks stay, leaves go, bark stripped, dry ground
    n_dead = int((A.trunk & ring).sum())
    A.clear_trees(ring, leaves_only=True)
    for z, x in zip(*np.nonzero(ring & A.trunk)):
        j = int(A.ground[z, x]) - A.by
        for dy in range(1, 20):
            if j + dy >= A.ids.shape[0]:
                break
            n = A.box.palette[A.ids[j + dy, z, x]].split('[')[0]
            if not n.endswith('_log'):
                break
            A.ids[j + dy, z, x] = A.S(n.replace('minecraft:', 'minecraft:stripped_') + '[axis=y]')
    mix_grey = [('minecraft:calcite', .24), ('minecraft:diorite', .14), ('minecraft:tuff', .2), ('minecraft:gravel', .18), ('minecraft:white_terracotta', .08),
                ('minecraft:light_gray_terracotta', .16)]
    # yellow-brown, not yellow: ochre is only a fleck; sulphur yellow stays round the vents
    mix_brown = [('minecraft:terracotta', .22), ('minecraft:coarse_dirt', .24), ('minecraft:packed_mud', .14), ('minecraft:brown_terracotta', .1),
                 ('minecraft:gravel', .2), ('minecraft:yellow_terracotta', .1)]
    tone = vnoise(A.wx, A.wz, 18, 42) * .7 + vnoise(A.wx, A.wz, 5, 43) * .3
    replace = np.isin(A.names, ['minecraft:grass_block', 'minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:podzol', 'minecraft:stone',
                                'minecraft:moss_block', 'minecraft:rooted_dirt', 'minecraft:gravel', 'minecraft:andesite', 'minecraft:tuff'])

    def pick(mix, u):
        acc = 0
        for s, w in mix:
            acc += w
            if u < acc:
                return s
        return mix[-1][0]
    for z, x in zip(*np.nonzero(core)):
        j = int(A.ground[z, x]) - A.by
        mix = mix_grey if tone[z, x] > .45 else mix_brown
        for dd in (0, 1, 2):
            if replace[A.box.ids[j - dd, z, x]]:
                A.ids[j - dd, z, x] = A.S(pick(mix, float(hash01(A.wx[z, x], j - dd, A.wz[z, x], 44))))
    for z, x in zip(*np.nonzero(ring)):
        j = int(A.ground[z, x]) - A.by
        u = float(hash01(A.wx[z, x], A.wz[z, x], 45))
        if A.top[z, x] == 'minecraft:grass_block' and u < .45:
            A.ids[j, z, x] = A.S('minecraft:coarse_dirt' if u < .3 else 'minecraft:gravel')
            if A.box.kinds[A.ids[j + 1, z, x]] == tr.SOFT and not A.is_log[A.ids[j + 1, z, x]]:
                A.ids[j + 1, z, x] = A.S('minecraft:dead_bush') if u < .08 else A.S(tr.AIR_STATE)
    # vents: buried campfire on a hay block (taller smoke), an iron-bar grate over it so nothing stands in the fire;
    # sulphur yellow round the opening; not within 6 blocks of the ropeway pylons or north of --cable-z
    pylon = A.built & (tr.top_of(A.k == tr.BUILT, A.by) - A.ground >= 12)
    d_pylon = ndimage.distance_transform_edt(~pylon) if pylon.any() else np.full(A.ground.shape, 1e4)
    cand = core & (d_pylon > 8) & (A.wz >= a.cable_z + 6) & ndimage.binary_erosion(core, iterations=3)
    order = np.argsort(hash01(A.wx, A.wz, 46)[cand])
    pts = np.argwhere(cand)[order]
    vents = []
    for z, x in pts:
        if all((z - vz) ** 2 + (x - vx) ** 2 >= a.vent_gap ** 2 for vz, vx in vents):
            vents.append((z, x))
        if len(vents) >= a.vents:
            break
    fire = 'minecraft:campfire[facing=north,lit=true,signal_fire=true,waterlogged=false]'
    for vi, (z, x) in enumerate(vents):
        j = int(A.ground[z, x]) - A.by
        open_vent = a.vent_style == 'open' or (a.vent_style == 'mixed' and vi % 2 == 1)
        if open_vent:
            # open shaft: the fire two blocks down, nothing over it
            A.ids[j - 3, z, x] = A.S('minecraft:hay_block[axis=y]')
            A.ids[j - 2, z, x] = A.S(fire)
            A.ids[j - 1, z, x] = A.S(tr.AIR_STATE)
            A.ids[j, z, x] = A.S(tr.AIR_STATE)
        else:
            A.ids[j - 2, z, x] = A.S('minecraft:hay_block[axis=y]')
            A.ids[j - 1, z, x] = A.S(fire)
            A.ids[j, z, x] = A.S('minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]')
        for dz in range(-2, 3):
            for dx in range(-2, 3):
                if (dz or dx) and dz * dz + dx * dx <= 4 and hash01(A.wx[z, x] + dx, A.wz[z, x] + dz, 47) < .75:
                    zz_, xx_ = z + dz, x + dx
                    jj = int(A.ground[zz_, xx_]) - A.by
                    if core[zz_, xx_] and replace[A.box.ids[jj, zz_, xx_]]:
                        A.ids[jj, zz_, xx_] = A.S('minecraft:yellow_concrete_powder' if dz * dz + dx * dx <= 2 else 'minecraft:yellow_terracotta')
    # a few grey mud pools
    pools = 0
    for z, x in pts[::max(1, len(pts) // 6)][:6]:
        if any((z - vz) ** 2 + (x - vx) ** 2 < 36 for vz, vx in vents):
            continue
        j = int(A.ground[z, x]) - A.by
        ok = True
        for dz in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if int(A.ground[z + dz, x + dx]) != j + A.by or not core[z + dz, x + dx]:
                    ok = False
        if not ok:
            continue
        for dz in (-1, 0, 1):
            for dx in (-1, 0, 1):
                A.ids[j, z + dz, x + dx] = A.S('minecraft:mud')
        pools += 1
    rows = A.rows(x0 - 30, x1 + 30, z0 - 30, z1 + 30, pad=0)
    camp = sum(1 for r in rows if r[4].startswith('minecraft:campfire'))
    rep = dict(core_columns=int(core.sum()), dead_ring_columns=int(ring.sum()), dead_trees=n_dead, vents=len(vents), campfire_block_entities=camp,
               mud_pools=pools, cells=len(rows), vent_positions=[[int(A.wx[z, x]), int(A.ground[z, x]) - 1, int(A.wz[z, x])] for z, x in vents])
    return rows, rep, core, A


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['plantation', 'pampas', 'roadcut', 'bamboo', 'terrace', 'terrace2', 'owaku'])
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--mosaic', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--at', type=int, nargs='+')
    p.add_argument('--area', type=int, nargs=4)
    p.add_argument('--cells', type=int, default=30000)
    p.add_argument('--lone', type=int, default=7)
    p.add_argument('--max-slope', type=float, default=.5)
    p.add_argument('--tpi-band', type=float, default=5, help='plantation: |TPI| below this is mid-slope')
    p.add_argument('--min-tpi', type=float, default=-6)
    p.add_argument('--patches', action='store_true', help='pampas: dark fern and pale flower drifts')
    p.add_argument('--step', type=int, default=2, help='terrace2: bench height')
    p.add_argument('--zone', type=Path)
    p.add_argument('--core', type=int, nargs=2, default=[230, 960])
    p.add_argument('--cable-z', type=int, default=840)
    p.add_argument('--vents', type=int, default=26)
    p.add_argument('--vent-gap', type=int, default=11)
    p.add_argument('--vent-style', choices=['grate', 'open', 'mixed'], default='grate')
    p.add_argument('--reach', type=int, default=4, help='roadcut: faces up to this far from the road')
    p.add_argument('--min-h', type=int, default=3, help='roadcut: least height above the road')
    p.add_argument('--lip-thick', type=int, default=3, help='roadcut: thickest soil cleared off a road')
    p.add_argument('--lip-wide-ok', dest='lip_narrow', action='store_false', help='roadcut: clear lips of any width (only where the road is known to be open)')
    p.add_argument('--sidewalk', action='store_true', help='roadcut: count kerbs and sidewalks as road')
    p.add_argument('--keep-file', type=Path)
    p.add_argument('--seed', type=int, default=61)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rows, rep, _, _ = globals()['cmd_' + a.mode](a)
    tr.write_rows(a.out / 'rows.json', rows)
    (a.out / 'report.json').write_text(json.dumps(rep, indent=1), 'utf8')
    print(json.dumps(rep))


if __name__ == '__main__':
    main()
