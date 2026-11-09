"""Plan the GeoFront lake from the reference model's water, on natural ground only.

Reads the saved world and the mesh parts exported from the model; writes rows for
write_deep_cells. Nothing is written to the world here. Columns holding anything but
natural ground and plants, or close to such columns, are left alone.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation, binary_erosion, distance_transform_edt, label

from map_pipeline.launch_protection import load as load_launch
from map_pipeline.native_rails import load_rails
from plan_geofront_city import DIM, SCALE
from query_blocks import iter_selected_sections
from write_deep_cells import split_rows

Y0, Y1 = -512, -385
HQ_KEEP_RADIUS = 420          # the model's water around the pyramid would flood the headquarters apron
MIN_PIECE = 20000
MAX_DEPTH = 10
MAX_BANK = 8
CLEARANCE = 10
SHORE_BUFFER = 4
LEAF_REACH = 5

GROUND = ('minecraft:grass_block', 'minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:podzol', 'minecraft:stone',
          'minecraft:gravel', 'minecraft:sand', 'minecraft:moss_block', 'minecraft:rooted_dirt', 'minecraft:deepslate',
          'minecraft:andesite', 'minecraft:diorite', 'minecraft:granite', 'minecraft:tuff', 'minecraft:mud',
          'minecraft:clay')
PLANTS = ('minecraft:grass', 'minecraft:tall_grass', 'minecraft:fern', 'minecraft:large_fern', 'minecraft:dandelion',
          'minecraft:poppy', 'minecraft:azure_bluet', 'minecraft:oxeye_daisy', 'minecraft:cornflower',
          'minecraft:lily_of_the_valley', 'minecraft:dead_bush', 'minecraft:sweet_berry_bush', 'minecraft:vine',
          'minecraft:moss_carpet', 'minecraft:snow')
AIRS = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
BED_SHALLOW = 'minecraft:sand'
BED_DEEP = 'minecraft:gravel'
WATER = 'minecraft:water[level=0]'
BANK = 'minecraft:dirt'
BANK_TOP = 'minecraft:grass_block[snowy=false]'
AIR_STATE = 'minecraft:air'
OTHER, AIR, SOIL, PLANT, LOG, LEAF, WET = 0, 1, 2, 3, 4, 5, 6
WATERY = ('minecraft:water', 'minecraft:seagrass', 'minecraft:tall_seagrass', 'minecraft:kelp', 'minecraft:kelp_plant')


def classify(name):
    if name in AIRS:
        return AIR
    if name in WATERY:
        return WET
    if name in GROUND:
        return SOIL
    if name in PLANTS:
        return PLANT
    if name.endswith('_log') or name.endswith('_wood'):
        return LOG
    if name.endswith('_leaves'):
        return LEAF
    return OTHER


def water_mask(parts, rows, cx, cz, x0, z0, nx, nz):
    index = next(n for n, row in enumerate(rows) if row['name'].endswith('Aigua'))
    tri = parts[f'{index}_v'][parts[f'{index}_f']]
    flat = np.ptp(tri[:, :, 2], axis=1) < 1
    image = Image.new('L', (nx, nz), 0)
    draw = ImageDraw.Draw(image)
    px, py = 23.0, -29.0
    for corners in tri[flat]:
        draw.polygon([(float(cx + (p[0] - px) * SCALE - x0), float(cz - (p[1] - py) * SCALE - z0)) for p in corners], fill=255)
    return np.array(image) > 0


def read_band(world, x0, z0, x1, z1):
    nx, nz = x1 - x0 + 1, z1 - z0 + 1
    kinds = np.zeros((Y1 - Y0 + 1, nz, nx), np.uint8)
    states = np.zeros_like(kinds, dtype=np.int16)
    names, table = [], {}
    selection = {(cx, cz): set(range(Y0 >> 4, (Y1 >> 4) + 1)) for cx in range(x0 >> 4, (x1 >> 4) + 1) for cz in range(z0 >> 4, (z1 >> 4) + 1)}
    for cx, cz, sy, palette, ids in iter_selected_sections(world, DIM, selection, skip_unfinished=True):
        codes = np.array([table.setdefault(p, len(table)) for p in palette], np.int16)
        for p in palette:
            if table[p] == len(names):
                names.append(p)
        kind = np.array([classify(p.split('[')[0]) for p in palette], np.uint8)
        kind_block, state_block = kind[ids].reshape(16, 16, 16), codes[ids].reshape(16, 16, 16)
        base = sy * 16
        ya, yb = max(base, Y0), min(base + 16, Y1 + 1)
        ax, az = cx * 16 - x0, cz * 16 - z0
        xa, xb, za, zb = max(ax, 0), min(ax + 16, nx), max(az, 0), min(az + 16, nz)
        if ya < yb and xa < xb and za < zb:
            kinds[ya - Y0:yb - Y0, za:zb, xa:xb] = kind_block[ya - base:yb - base, za - az:zb - az, xa - ax:xb - ax]
            states[ya - Y0:yb - Y0, za:zb, xa:xb] = state_block[ya - base:yb - base, za - az:zb - az, xa - ax:xb - ax]
    return kinds, states, names


def ground_height(kinds):
    """Index of the highest ground block per column, and whether the ground beneath it is unbroken."""
    soil = kinds == SOIL
    top = soil.shape[0] - 1 - np.argmax(soil[::-1], axis=0)
    has = soil.any(axis=0)
    return top, has


def plan(a):
    parts = np.load(a.parts)
    rows = json.loads(Path(str(a.parts) + '.json').read_text('utf8'))
    cx, cz = a.centre
    x0, z0, x1, z1 = -1500, -1150, 1000, 1250
    nx, nz = x1 - x0 + 1, z1 - z0 + 1
    mask = water_mask(parts, rows, cx, cz, x0, z0, nx, nz)
    xx, zz = np.meshgrid(np.arange(nx) + x0, np.arange(nz) + z0)
    mask &= np.hypot(xx - cx, zz - cz) > HQ_KEEP_RADIUS
    pieces, count = label(mask)
    sizes = np.bincount(pieces.ravel())
    keep_ids = [i for i in range(1, count + 1) if sizes[i] >= MIN_PIECE]
    print('water pieces', count, 'kept', [(i, int(sizes[i])) for i in keep_ids], flush=True)
    mask = np.isin(pieces, keep_ids)

    kinds, states, names = read_band(a.world, x0, z0, x1, z1)
    other = (kinds == OTHER).any(axis=0)
    guard = load_launch(a.world)
    for (kx, kz) in guard.by_chunk:
        ax, az = kx * 16 - x0, kz * 16 - z0
        if -16 < ax < nx and -16 < az < nz:
            if guard.chunk_mask(kx, kz, y0=Y0, height=Y1 - Y0 + 1).any():
                other[max(az, 0):max(az + 16, 0), max(ax, 0):max(ax + 16, 0)] = True
    for rail in load_rails(a.native):
        p, q = np.array(rail['a'], float), np.array(rail['b'], float)
        line = (p + np.outer(np.linspace(0, 1, max(2, int(np.linalg.norm(q - p)) + 1)), q - p)).astype(int)
        inside = (line[:, 0] >= x0) & (line[:, 0] <= x1) & (line[:, 2] >= z0) & (line[:, 2] <= z1) & (line[:, 1] >= Y0) & (line[:, 1] <= Y1 + 16)
        other[line[inside, 2] - z0, line[inside, 0] - x0] = True
    found = Counter()
    wanted = np.isin(states, np.array([n for n, name in enumerate(names) if classify(name.split('[')[0]) == OTHER], np.int16))
    for code, amount in zip(*np.unique(states[wanted & mask[None, :, :]], return_counts=True)):
        found[names[code].split('[')[0]] += int(amount)
    print('other blocks under the water', found.most_common(14), flush=True)
    keep_out = binary_dilation(other, iterations=CLEARANCE)
    ground, has_ground = ground_height(kinds)
    wet = kinds == WET
    wet_top = wet.shape[0] - 1 - np.argmax(wet[::-1], axis=0)
    has_wet = wet.any(axis=0)
    report_pieces = []
    lake = np.zeros_like(mask)
    level = np.zeros_like(ground) - 9999
    for i in keep_ids:
        here = (pieces == i) & ~keep_out & has_ground
        if not here.any():
            continue
        surfaces = wet_top[(pieces == i) & has_wet]
        if len(surfaces) >= 1000:      # an existing body of water sets the level
            water_index = int(np.bincount(surfaces).argmax())
        else:
            water_index = int(np.percentile(ground[here], 30))
        here &= ~has_wet
        here &= ground >= water_index - MAX_BANK
        here &= ground <= water_index + 12
        grown, _ = label(here)
        big = np.bincount(grown.ravel())
        big[0] = 0
        here = grown == big.argmax()
        lake |= here
        level[here] = water_index
        report_pieces.append(dict(piece=i, water_y=water_index + Y0, columns=int(here.sum())))
    print('pieces', report_pieces, flush=True)

    # Shore columns outside the lake are raised where they sit below the water.
    for _ in range(6):
        ring = binary_dilation(lake, iterations=1) & ~lake
        spread = level.copy()
        for _ in range(1):
            spread = np.maximum(spread, np.max([np.roll(level, s, axis=d) for d in (0, 1) for s in (1, -1)], axis=0))
        low = ring & (ground < spread) & ~has_wet
        bad = low & (keep_out | ~has_ground | (spread - ground > MAX_BANK))
        if not bad.any():
            break
        lake &= ~binary_dilation(bad, iterations=2)
        level[~lake] = -9999
    ring = binary_dilation(lake, iterations=1) & ~lake
    spread = np.maximum(level, np.max([np.roll(level, s, axis=d) for d in (0, 1) for s in (1, -1)], axis=0))
    bank = ring & (ground < spread) & ~has_wet

    edits = {}
    cleared = binary_dilation(lake, iterations=SHORE_BUFFER) & ~keep_out
    distance = distance_transform_edt(lake | has_wet)
    tally = Counter()

    def put(iy, iz, ix, after, why):
        before = names[states[iy, iz, ix]]
        if before != after:
            edits[int(ix), int(iy), int(iz)] = (before, after)
            tally[why] += 1

    # Trees come off in the lake and a narrow strip of shore.
    for jz, jx in zip(*np.nonzero(cleared)):
        floor_at = int(ground[jz, jx]) + 1 if has_ground[jz, jx] else 0
        for iy in np.nonzero(np.isin(kinds[floor_at:, jz, jx], (LOG, LEAF, PLANT)))[0] + floor_at:
            put(iy, jz, jx, AIR_STATE, 'tree or plant')
    logs_left = (kinds == LOG)
    logs_left[:, cleared] = False
    near_log = binary_dilation(logs_left, structure=np.ones((3, 3, 3), bool), iterations=LEAF_REACH)
    stranded = (kinds == LEAF) & ~near_log
    stranded[:, cleared] = False
    for iy, jz, jx in zip(*np.nonzero(stranded & binary_dilation(cleared[None, :, :].repeat(kinds.shape[0], 0), iterations=LEAF_REACH * 2))):
        put(iy, jz, jx, AIR_STATE, 'stranded leaves')

    for jz, jx in zip(*np.nonzero(lake)):
        surface = int(level[jz, jx])
        bed = surface - min(MAX_DEPTH, 1 + int(distance[jz, jx] / 3))
        top = int(ground[jz, jx])
        bed = min(bed, top)
        if kinds[bed - 1, jz, jx] == AIR:
            tally['bed with a void under it'] += 1
            continue
        put(bed, jz, jx, BED_DEEP if distance[jz, jx] > 8 else BED_SHALLOW, 'lake bed')
        for iy in range(bed + 1, surface + 1):
            put(iy, jz, jx, WATER, 'water')
        for iy in range(surface + 1, top + 1):
            put(iy, jz, jx, AIR_STATE, 'cut ground')
    for jz, jx in zip(*np.nonzero(bank)):
        for iy in range(int(ground[jz, jx]) + 1, int(spread[jz, jx]) + 1):
            put(iy, jz, jx, BANK_TOP if iy == spread[jz, jx] else BANK, 'bank')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(str(a.out) + '.masks.npz', lake=lake, keep_out=keep_out, level=level, footprint=mask, origin=np.array([x0, z0]))
    output = [[ix + x0, iy + Y0, iz + z0, before, after] for (ix, iy, iz), (before, after) in sorted(edits.items())]
    report = dict(existing_water_columns=int(has_wet.sum()), cells=len(output), kinds=dict(tally), pieces=report_pieces, lake_columns=int(lake.sum()), bank_columns=int(bank.sum()),
                  keep_out_columns=int(keep_out.sum()), world_written=False)
    report['batches'] = split_rows(output, a.out.parent)
    Path(str(a.out) + '.report.json').write_text(json.dumps(report, indent=1), 'utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--parts', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--centre', type=int, nargs=2, required=True, metavar=('X', 'Z'))
    parser.add_argument('--out', type=Path, required=True)
    plan(parser.parse_args())
