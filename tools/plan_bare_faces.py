"""Weather the bare earth and rock faces of natural slopes the way real cut slopes and cliffs look after a few years.

A natural column shows a vertical face where its ground stands above the lowest neighbour (solid top or water surface).
drop = ground - lowest neighbour; smoothed slope from the ground heights.

    rock    drop >= 4, or drop >= 2 on a slope steeper than --rock-slope: the face cells under the top become layered
            andesite, stone and tuff (bands about two blocks thick that waver sideways and change from area to area),
            with mossy cobblestone patches; a grass top stays as a cap
    bank    drop 2-3: moss, rooted and coarse dirt, andesite pebbles and some plain dirt in patches
    stripe  drop 1 on a slope steeper than --stripe-slope: tall grass, ferns, grass and low bushes at the foot of the
            steps (--stripe-cover of them), nothing on gentler terraces
Bare dirt and coarse dirt on top of a slope becomes grass. The foot of banks and rock faces gets tall grass, ferns and
low bushes; their tops get the odd shrub.

Only dirt, coarse dirt, grass, rooted dirt and stone are replaced, only air above ground gets plants. Never within 2
blocks of anything built, on water, on unloaded chunks, or in columns other sessions' pending lists touch (--keep-rows).
Patterns use value noise over world coordinates, so tiles join without seams.

    plan_bare_faces.py --world W --faces DIR --mosaic DIR --out DIR [--area x0 x1 z0 z1] [--keep-rows GLOB ...]
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr
from plan_forest_transitions import keep_columns

REPLACE = ('minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:grass_block', 'minecraft:rooted_dirt', 'minecraft:stone')
ROCK = [('minecraft:andesite', .42), ('minecraft:stone', .28), ('minecraft:tuff', .14), ('minecraft:cobblestone', .06), ('minecraft:andesite', .10)]
BANK = [('minecraft:moss_block', .42), ('minecraft:rooted_dirt', .10), ('minecraft:coarse_dirt', .10), ('minecraft:andesite', .12),
        ('minecraft:mossy_cobblestone', .06), (None, .20)]
LEAVES = 'minecraft:{}_leaves[distance=1,persistent=true,waterlogged=false]'


def hash01(*keys):
    with np.errstate(over='ignore'):
        return _hash01(*keys)


def _hash01(*keys):
    h = np.uint64(1469598103934665603)
    for k in keys:
        h = (h ^ (np.asarray(k).astype(np.int64).astype(np.uint64) + np.uint64(0x9E3779B97F4A7C15))) * np.uint64(1099511628211)
        h ^= h >> np.uint64(29)
    return (h & np.uint64(0xFFFFFF)).astype(np.float64) / float(0xFFFFFF)


def vnoise(x, z, scale, seed):
    """Smooth value noise in 0..1 over world coordinates."""
    fx, fz = x / scale, z / scale
    ix, iz = np.floor(fx).astype(np.int64), np.floor(fz).astype(np.int64)
    tx, tz = fx - ix, fz - iz
    tx, tz = tx * tx * (3 - 2 * tx), tz * tz * (3 - 2 * tz)
    a, b = hash01(ix, iz, seed), hash01(ix + 1, iz, seed)
    c, d = hash01(ix, iz + 1, seed), hash01(ix + 1, iz + 1, seed)
    return (a * (1 - tx) + b * tx) * (1 - tz) + (c * (1 - tx) + d * tx) * tz


def pick(weights, u):
    acc, out = 0, None
    for state, w in weights:
        acc += w
        if u < acc:
            return state
    return weights[-1][0] if out is None else out


def plan_tile(box, x0, x1, z0, z1, kept, a, seed):
    """Rows for the core x0..x1, z0..z1 of box (which carries a 2-block ring for neighbour heights)."""
    bx, by, bz = box.origin
    k = box.kind_grid()
    names = np.array([q.split('[')[0] for q in box.palette]).astype(str)
    soil = k == tr.SOIL
    ground = tr.top_of(soil, by)
    solidtop = tr.top_of(soil | (k == tr.BUILT), by)
    fluidtop = tr.top_of(k == tr.FLUID, by)
    yy = np.arange(k.shape[0])[:, None, None] + by
    built = ((k == tr.BUILT) & (yy >= ground[None] - 2)).any(0)
    wet = fluidtop >= ground
    surf = np.where(box.loaded, np.maximum(solidtop, fluidtop), 10 ** 6)
    pad = np.pad(surf, 1, constant_values=10 ** 6)
    low = np.min([pad[:-2, 1:-1], pad[2:, 1:-1], pad[1:-1, :-2], pad[1:-1, 2:]], axis=0)
    drop = np.clip(ground - low, 0, 200)
    gy, gx = np.gradient(ndimage.gaussian_filter(ground.astype(float), 1.5))
    slope = np.hypot(gx, gy)
    keepout = ndimage.binary_dilation(built, iterations=2) | ndimage.binary_dilation(kept, iterations=1) | wet | ~box.loaded | (ground < by + 1)
    core = np.zeros(ground.shape, bool)
    core[z0 - bz:z1 - bz + 1, x0 - bx:x1 - bx + 1] = True
    ok = core & ~keepout
    rock = ok & ((drop >= 4) | ((drop >= 2) & (slope >= a.rock_slope)))
    bank = ok & ~rock & (drop >= 2)
    stripe = ok & (drop == 1) & (slope >= a.stripe_slope)
    ids = box.ids.copy()
    replace = np.isin(names, REPLACE)
    zz, xx = np.mgrid[0:ground.shape[0], 0:ground.shape[1]]
    wx, wz = xx + bx, zz + bz
    region = (wx // 256) * 7919 + (wz // 256)
    n_bank = vnoise(wx, wz, 7, seed + 1) * .7 + vnoise(wx, wz, 2.5, seed + 2) * .3
    shift = vnoise(wx, wz, 40, seed + 3) * 4 + .03 * wx - .02 * wz
    moss_n = vnoise(wx, wz, 9, seed + 4)
    sid = {}

    def state(s):
        if s not in sid:
            sid[s] = box.state_id(s)
        return sid[s]
    counts = dict(rock_cells=0, bank_cells=0, bare_tops=0, plants=0, shrubs=0)
    # faces
    for z, x in zip(*np.nonzero(rock | bank)):
        g, lo = int(ground[z, x]), int(low[z, x])
        for y in range(max(lo + 1, by), g):
            j = y - by
            if not replace[box.ids[j, z, x]]:
                continue
            if rock[z, x]:
                band = int(np.floor((y + shift[z, x]) / 2.2))
                u = hash01(band, region[z, x], seed)
                s = pick(ROCK, float(u))
                if hash01(x + bx, y, z + bz, seed + 5) < .1 + .25 * max(moss_n[z, x] - .5, 0) * 2:
                    s = 'minecraft:mossy_cobblestone'
                counts['rock_cells'] += 1
            else:
                u = (n_bank[z, x] + .25 * (hash01(x + bx, y, z + bz, seed + 6) - .5)) % 1
                s = pick(BANK, float(u))
                if s is None:
                    continue
                counts['bank_cells'] += 1
            ids[j, z, x] = state(s)
        top_name = names[box.ids[g - by, z, x]] if g >= by else ''
        if rock[z, x] and top_name in ('minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:stone'):
            band = int(np.floor((g + shift[z, x]) / 2.2))
            ids[g - by, z, x] = state(pick(ROCK, float(hash01(band, region[z, x], seed))))
            counts['rock_cells'] += 1
    # steep terraces: moss patches on the step tops, whose sides read green where grass blocks show dirt
    steep_stripe = stripe & (slope >= a.moss_slope)
    moss_patch = vnoise(wx, wz, 6, seed + 9) * .75 + hash01(wx, wz, seed + 10) * .25
    moss = state('minecraft:moss_block')
    for z, x in zip(*np.nonzero(steep_stripe & (moss_patch > 1 - a.stripe_moss))):
        j = int(ground[z, x]) - by
        if 0 <= j < ids.shape[0] and names[box.ids[j, z, x]] == 'minecraft:grass_block':
            ids[j, z, x] = moss
            counts['moss_tops'] = counts.get('moss_tops', 0) + 1
    # bare dirt tops on slopes become grass
    air_like = (k == tr.AIRK) | (k == tr.SOFT)
    for z, x in zip(*np.nonzero(ok & ~rock & (slope > .6))):
        j = int(ground[z, x]) - by
        if j + 1 >= ids.shape[0] or names[box.ids[j, z, x]] not in ('minecraft:dirt', 'minecraft:coarse_dirt') or not air_like[j + 1, z, x]:
            continue
        ids[j, z, x] = state(tr.GRASS)
        counts['bare_tops'] += 1
    # plants: the foot of every face column, the steep terrace steps, shrubs on ledges
    face = rock | bank
    foot = ok & ~face & ndimage.binary_dilation(face, iterations=1)
    pad_g = np.pad(ground, 1, mode='edge')
    riser = np.max([pad_g[:-2, 1:-1], pad_g[2:, 1:-1], pad_g[1:-1, :-2], pad_g[1:-1, 2:]], axis=0) > ground
    stripe_foot = ok & ~face & riser & ndimage.binary_dilation(stripe, iterations=1)
    grass_ids = {state(tr.GRASS), state('minecraft:moss_block')}
    air = state(tr.AIR_STATE)
    tall = (state('minecraft:tall_grass[half=lower]'), state('minecraft:tall_grass[half=upper]'))
    short, fern = state('minecraft:grass'), state('minecraft:fern')
    bushes = [state(LEAVES.format(s)) for s in ('oak', 'dark_oak', 'oak', 'birch')]
    roll = hash01(wx, wz, seed + 7)
    kind_u = hash01(wx, wz, seed + 8)
    for z, x in zip(*np.nonzero(foot | stripe_foot | face)):
        j = int(ground[z, x]) - by
        if not (0 <= j and j + 2 < ids.shape[0] and ids[j, z, x] in grass_ids and ids[j + 1, z, x] == air):
            continue
        r, u = roll[z, x], kind_u[z, x]
        if face[z, x]:
            if r < a.ledge_shrubs:
                ids[j + 1, z, x] = bushes[int(u * 4) % 4]
                counts['shrubs'] += 1
            elif r < a.ledge_shrubs + .15:
                ids[j + 1, z, x] = short
                counts['plants'] += 1
            continue
        if r >= (a.foot_cover if foot[z, x] else a.stripe_cover):
            continue
        if u < .32 and ids[j + 2, z, x] == air:
            ids[j + 1, z, x], ids[j + 2, z, x] = tall
        elif u < .44:
            ids[j + 1, z, x] = bushes[int(u * 97) % 4]
            counts['shrubs'] += 1
            continue
        elif u < .6:
            ids[j + 1, z, x] = fern
        else:
            ids[j + 1, z, x] = short
        counts['plants'] += 1
    rows = [r for r in tr.rows_between(box, ids) if x0 <= r[0] <= x1 and z0 <= r[2] <= z1]
    counts.update(rock_columns=int(rock.sum()), bank_columns=int(bank.sum()), stripe_columns=int(stripe.sum()))
    return rows, counts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--faces', type=Path, required=True, help='scan_bare_faces.py output (to skip empty tiles)')
    p.add_argument('--mosaic', type=Path, required=True, help='scan mosaic (height range per tile)')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--area', type=int, nargs=4, help='x0 x1 z0 z1')
    p.add_argument('--tile', type=int, default=256)
    p.add_argument('--rock-slope', type=float, default=2.2)
    p.add_argument('--stripe-slope', type=float, default=.85)
    p.add_argument('--stripe-cover', type=float, default=.35)
    p.add_argument('--foot-cover', type=float, default=.55)
    p.add_argument('--ledge-shrubs', type=float, default=.04)
    p.add_argument('--stripe-moss', type=float, default=.3, help='share of step tops turned to moss on steep terraces')
    p.add_argument('--moss-slope', type=float, default=.9)
    p.add_argument('--keep-rows', nargs='*', default=[])
    p.add_argument('--keep-days', type=float, default=4)
    p.add_argument('--keep-file', type=Path, help='json [[x, z], ...] of kept columns: read if it exists, else written from --keep-rows')
    p.add_argument('--seed', type=int, default=61)
    p.add_argument('--resume', action='store_true')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    f = np.load(a.faces / 'faces.npz')
    ox, oz = (int(v) for v in f['origin'])
    drop = f['drop']
    work = (drop >= 2) | f['bare_top']
    ground = np.load(a.mosaic / 'ground.npy', mmap_mode='r')
    x_lo, x_hi, z_lo, z_hi = a.area or (ox, ox + drop.shape[1] - 1, oz, oz + drop.shape[0] - 1)
    T = a.tile
    tiles = []
    for tz in range(z_lo // T, z_hi // T + 1):
        for tx in range(x_lo // T, x_hi // T + 1):
            X0, X1 = max(tx * T, x_lo), min(tx * T + T - 1, x_hi)
            Z0, Z1 = max(tz * T, z_lo), min(tz * T + T - 1, z_hi)
            sl = (slice(max(Z0 - oz, 0), max(Z1 - oz + 1, 0)), slice(max(X0 - ox, 0), max(X1 - ox + 1, 0)))
            w = work[sl]
            if w.size == 0:
                continue
            if not w.any():
                d1 = drop[sl] == 1
                if d1.sum() < 200:
                    continue
            tiles.append((X0, X1, Z0, Z1))
    if a.keep_file and a.keep_file.exists():
        kept_all = {tuple(c) for c in json.loads(a.keep_file.read_text('utf8'))}
    else:
        kept_all = keep_columns(a.keep_rows, a.keep_days, a.world) if a.keep_rows else set()
        if a.keep_file:
            a.keep_file.write_text(json.dumps(sorted(kept_all)), 'utf8')
    kept_index = {}
    for (px, pz) in kept_all:
        kept_index.setdefault((px // a.tile, pz // a.tile), []).append((px, pz))
    ck = a.out / 'checkpoint.json'
    rows, report, done = [], [], set()
    if a.resume and ck.exists():
        c = json.loads(ck.read_text('utf8'))
        rows, report, done = c['rows'], c['report'], {tuple(t) for t in c['done']}
    t0 = time.time()
    for i, (X0, X1, Z0, Z1) in enumerate(tiles):
        if (X0, Z0) in done:
            continue
        g = np.array(ground[max(Z0 - oz - 2, 0):Z1 - oz + 3, max(X0 - ox - 2, 0):X1 - ox + 3])
        g = g[g > -30000]
        if not g.size:
            done.add((X0, Z0))
            continue
        ylo, yhi = int(g.min()) - 40, int(g.max()) + 4
        box = tr.Box(a.world, X0 - 2, X1 + 2, max(ylo, -64), min(yhi, 319), Z0 - 2, Z1 + 2)
        kept = np.zeros(box.loaded.shape, bool)
        for kx in range((X0 - 2) // a.tile, (X1 + 2) // a.tile + 1):
            for kz in range((Z0 - 2) // a.tile, (Z1 + 2) // a.tile + 1):
                for (px, pz) in kept_index.get((kx, kz), ()):
                    if X0 - 2 <= px <= X1 + 2 and Z0 - 2 <= pz <= Z1 + 2:
                        kept[pz - Z0 + 2, px - X0 + 2] = True
        r, cnt = plan_tile(box, X0, X1, Z0, Z1, kept, a, a.seed)
        rows += r
        cnt.update(tile=[X0, Z0], cells=len(r))
        report.append(cnt)
        done.add((X0, Z0))
        if i % 10 == 9:
            print(f'{i + 1}/{len(tiles)} tiles, {len(rows)} cells, {time.time() - t0:.0f} s', flush=True)
            tmp = a.out / 'checkpoint.tmp'
            tmp.write_text(json.dumps(dict(rows=rows, report=report, done=sorted(done))), 'utf8')
            tmp.replace(ck)
    tr.write_rows(a.out / 'rows.json', rows)
    tot = {k: sum(r.get(k, 0) for r in report) for k in ('cells', 'rock_cells', 'bank_cells', 'bare_tops', 'moss_tops', 'plants', 'shrubs', 'rock_columns', 'bank_columns', 'stripe_columns')}
    tot['tiles'] = len(tiles)
    (a.out / 'report.json').write_text(json.dumps(dict(total=tot, tiles=report), indent=1), 'utf8')
    print(json.dumps(tot))


if __name__ == '__main__':
    main()
