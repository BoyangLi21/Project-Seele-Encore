"""Turn a stretch of flat, bare plain into the patchwork of a Japanese lowland: small rice paddies between raised grass
paths, wheat and vegetable plots, hay meadows, trees along the channels and windbreaks round the farmhouses.

Plots are laid on a grid of --plot W H blocks with a 1-block grass path (aze) between them. A plot is used only where
its ground is flat (one height) and free: nothing built within 3 blocks, no water within 1, no other session's pending
column, chunk loaded. Plot types come from a noise over the plot index:
    paddy   the top grass becomes water one block below the paths, mud underneath, rice seedlings (seagrass) in rows;
            water only where all four sides are path, water or plot, so nothing can flow
    wheat   farmland under ripe or ripening wheat
    veg     farmland under carrots or potatoes
    meadow  tall grass, grass and wild flowers
Trees: oak and birch along the channels (2-3 blocks from the water), spruce windbreaks on the north and west sides of
buildings (4-9 blocks off), both kept 3 blocks from roads.

    plan_farm_pilot.py --world W --mosaic DIR --area x0 x1 z0 z1 --out DIR [--plot 11 19] [--keep-file F]
"""
import argparse
import json
import random
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr
from plan_bare_faces import hash01

FLOWERS = ['minecraft:dandelion', 'minecraft:poppy', 'minecraft:oxeye_daisy', 'minecraft:cornflower', 'minecraft:azure_bluet']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--mosaic', type=Path, required=True)
    p.add_argument('--area', type=int, nargs=4, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--plot', type=int, nargs=2, default=[11, 19])
    p.add_argument('--mix', type=float, nargs=4, default=[.58, .14, .1, .18], help='paddy wheat veg meadow')
    p.add_argument('--keep-file', type=Path)
    p.add_argument('--seed', type=int, default=71)
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
    fluid_top = tr.top_of(k == tr.FLUID, by)
    wet = fluid_top >= ground
    yy = np.arange(k.shape[0])[:, None, None] + by
    built_any = ((k == tr.BUILT) & (yy >= ground[None] - 2)).any(0)
    tall_built = ((k == tr.BUILT) & (yy >= ground[None] + 3)).any(0)
    kept = np.zeros(ground.shape, bool)
    if a.keep_file and a.keep_file.exists():
        for px, pz in json.loads(a.keep_file.read_text('utf8')):
            if bx <= px < bx + ground.shape[1] and bz <= pz < bz + ground.shape[0]:
                kept[pz - bz, px - bx] = True
    j_top = np.clip(ground - by, 0, k.shape[0] - 2)
    top_name = names[np.take_along_axis(box.ids, j_top[None], 0)[0]]
    above_k = np.take_along_axis(k, (j_top + 1)[None], 0)[0]
    open_sky = (above_k == tr.AIRK) | (above_k == tr.SOFT)
    leafy = np.char.endswith(names, ('_leaves'))[box.ids].any(0) | np.char.endswith(names, '_log')[box.ids].any(0)
    inside = np.zeros(ground.shape, bool)
    inside[z0 - bz:z1 - bz + 1, x0 - bx:x1 - bx + 1] = True
    free = inside & box.loaded & (top_name == 'minecraft:grass_block') & open_sky & ~leafy & ~kept \
        & ~ndimage.binary_dilation(built_any, iterations=3) & ~ndimage.binary_dilation(wet, iterations=1)
    ids = box.ids.copy()
    sid = {}

    def S(s):
        if s not in sid:
            sid[s] = box.state_id(s)
        return sid[s]
    W, H = a.plot
    cw, ch = W + 1, H + 1
    plot_kind = np.full(ground.shape, -1, np.int8)
    plot_no = np.full(ground.shape, -1, np.int32)
    counts = dict(paddy=0, wheat=0, veg=0, meadow=0, plots_skipped=0)
    kinds = ['paddy', 'wheat', 'veg', 'meadow']
    cum = np.cumsum(a.mix) / np.sum(a.mix)
    n = 0
    for pz in range(z0, z1 - ch + 2, ch):
        for px in range(x0, x1 - cw + 2, cw):
            sl = (slice(pz - bz, pz - bz + H), slice(px - bx, px - bx + W))
            f = free[sl]
            if f.mean() < .85:
                counts['plots_skipped'] += 1
                continue
            gh = ground[sl][f]
            mode = np.bincount(gh - gh.min()).argmax() + gh.min()
            ok = f & (ground[sl] == mode)
            if ok.mean() < .8:
                counts['plots_skipped'] += 1
                continue
            u = float(hash01(px // cw, pz // ch, a.seed))
            kind = int(np.searchsorted(cum, u))
            # neighbouring plots tend to share a crop, as real holdings do
            if kind != 0 and hash01(px // cw, pz // ch, a.seed + 1) < .35:
                kind = 0
            plot_kind[sl] = np.where(ok, kind, -1)
            plot_no[sl] = np.where(ok, n, -1)
            counts[kinds[kind]] += 1
            n += 1
    # paddies: water must be closed on all four sides by path (unchanged grass at the same height), water or paddy
    paddy = plot_kind == 0
    while True:
        nb_ok = np.ones(paddy.shape, bool)
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb_ok &= np.roll(paddy, (-dz, -dx), (0, 1)) | (np.roll(ground, (-dz, -dx), (0, 1)) >= ground)
        drop = paddy & ~nb_ok
        if not drop.any():
            break
        paddy &= ~drop
    water, mud, seagrass = S('minecraft:water[level=0]'), S('minecraft:mud'), S('minecraft:seagrass')
    zz, xx = np.mgrid[0:ground.shape[0], 0:ground.shape[1]]
    wx, wz = xx + bx, zz + bz
    for z, x in zip(*np.nonzero(paddy)):
        j = int(ground[z, x]) - by
        ids[j, z, x] = water
        ids[j - 1, z, x] = mud
        row = (wx[z, x] % 2 == 0) if (W < H) else (wz[z, x] % 2 == 0)
        if row and hash01(wx[z, x], wz[z, x], a.seed + 2) < .75:
            ids[j, z, x] = seagrass
    # dry plots
    air = S(tr.AIR_STATE)
    for z, x in zip(*np.nonzero((plot_kind >= 1))):
        j = int(ground[z, x]) - by
        if ids[j + 1, z, x] != air and k[j + 1, z, x] != tr.SOFT:
            continue
        kind = plot_kind[z, x]
        no = int(plot_no[z, x])
        u = hash01(wx[z, x], wz[z, x], a.seed + 3)
        if kind == 1:
            ids[j, z, x] = S('minecraft:farmland[moisture=7]')
            age = 7 if hash01(no, 9, a.seed) < .6 else 5 + int(u * 3) % 3
            ids[j + 1, z, x] = S(f'minecraft:wheat[age={age}]')
        elif kind == 2:
            crop = 'carrots' if hash01(no, 11, a.seed) < .5 else 'potatoes'
            # rows: every third line is a furrow left bare
            line = (wx[z, x] if W < H else wz[z, x]) % 3
            ids[j, z, x] = S('minecraft:farmland[moisture=7]')
            ids[j + 1, z, x] = S(f'minecraft:{crop}[age=7]') if line else air
        else:
            if u < .28:
                if j + 2 < ids.shape[0] and ids[j + 2, z, x] == air:
                    ids[j + 1, z, x], ids[j + 2, z, x] = S('minecraft:tall_grass[half=lower]'), S('minecraft:tall_grass[half=upper]')
            elif u < .6:
                ids[j + 1, z, x] = S('minecraft:grass')
            elif u < .68:
                ids[j + 1, z, x] = S(FLOWERS[int(u * 1000) % len(FLOWERS)])
    # trees: along channels and as windbreaks on the north and west of buildings
    road_keep = ndimage.binary_dilation(built_any, iterations=3)
    d_water = ndimage.distance_transform_edt(~wet)
    channel = inside & (d_water >= 2) & (d_water <= 3.5) & (plot_kind < 0) & ~road_keep & box.loaded
    dist_b, (iz, ix) = ndimage.distance_transform_edt(~tall_built, return_indices=True)
    north_west = ((zz - iz) < 0) | ((xx - ix) < 0)
    windbreak = inside & tall_built.any() & (dist_b >= 4) & (dist_b <= 9) & north_west & (plot_kind < 0) & ~road_keep & box.loaded
    c_con = np.where(windbreak, .55, np.where(channel, .08, 0))
    c_broad = np.where(channel, .5, np.where(windbreak, .15, 0))
    where = (channel | windbreak) & (top_name == 'minecraft:grass_block') & open_sky
    keepout = road_keep | wet | (plot_kind >= 0) | kept
    tr.replant(box, ids, ground, where, keepout, random.Random(a.seed), chance=(c_con, c_broad))
    rows = [r for r in tr.rows_between(box, ids) if x0 <= r[0] <= x1 and z0 <= r[2] <= z1]
    tr.write_rows(a.out / 'rows.json', rows)
    bases = {(q[0], q[2]) for q in rows if q[4].split('[')[0].endswith('_log')}
    counts.update(cells=len(rows), paddy_water=int(paddy.sum()), trees=len(bases), area=a.area, plot=a.plot)
    (a.out / 'report.json').write_text(json.dumps(counts, indent=1), 'utf8')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
