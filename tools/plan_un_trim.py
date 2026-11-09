"""Make the moved UN base read as reclaimed land: cut the old hills it brought along, face its edge with a sea wall.

Reads the world after move_un_base.py's chunk stage; writes rows for write_deep_cells. Only natural
ground, trees and plants are cut, and only in columns that hold nothing built; the base itself is
never touched.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from move_un_base import CDX, CDZ, X0, X1, Z0, Z1, DX, DZ
from query_blocks import iter_selected_sections
from write_deep_cells import split_rows

DIM = 'projectseele:geofront'
Y0, Y1 = -112, 63
PLATFORM = -70            # the old base floor, y 74, after the move
SEA = -82
AIR, WATER, SOIL, PLANT, OTHER = 0, 1, 2, 3, 4
SOILS = {'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block', 'minecraft:coarse_dirt', 'minecraft:podzol', 'minecraft:gravel', 'minecraft:sand',
         'minecraft:andesite', 'minecraft:diorite', 'minecraft:granite', 'minecraft:deepslate', 'minecraft:tuff', 'minecraft:clay', 'minecraft:moss_block',
         'minecraft:rooted_dirt', 'minecraft:mud', 'minecraft:sandstone', 'minecraft:snow_block'}


def kind(name):
    if name in ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'):
        return AIR
    if name in ('minecraft:water', 'minecraft:seagrass', 'minecraft:tall_seagrass', 'minecraft:kelp', 'minecraft:kelp_plant'):
        return WATER
    if name in SOILS:
        return SOIL
    if name.endswith(('_leaves', '_log', '_wood')) or name in ('minecraft:grass', 'minecraft:tall_grass', 'minecraft:fern', 'minecraft:large_fern', 'minecraft:snow',
                                                              'minecraft:dandelion', 'minecraft:poppy', 'minecraft:vine', 'minecraft:sweet_berry_bush', 'minecraft:dead_bush'):
        return PLANT
    return OTHER


def plan(a):
    # Whole chunks: the old footprint's south edge falls inside a chunk that moved whole.
    x0, x1, z0, z1 = X0 + DX, (X1 + DX) | 15, Z0 + DZ, (Z1 + DZ) | 15
    nx, nz, ny = x1 - x0 + 1, z1 - z0 + 1, Y1 - Y0 + 1
    kinds = np.zeros((ny, nz, nx), np.uint8)
    states = np.zeros((ny, nz, nx), np.int32)
    names, table = [], {}
    moved = np.zeros((nz, nx), bool)
    selection = {(cx, cz): set(range(Y0 >> 4, (Y1 >> 4) + 1)) for cx in range(x0 >> 4, (x1 >> 4) + 1) for cz in range(z0 >> 4, (z1 >> 4) + 1)}
    source_full = {tuple(c) for c in json.loads(Path(a.moved).read_text('utf8'))}
    for cx, cz, sy, palette, ids in iter_selected_sections(a.world, DIM, selection, skip_unfinished=True):
        if (cx - CDX, cz - CDZ) not in source_full:
            continue
        code = np.array([table.setdefault(p, len(table)) for p in palette], np.int32)
        for p in palette:
            if table[p] == len(names):
                names.append(p)
        k = np.array([kind(p.split('[')[0]) for p in palette], np.uint8)
        base = sy * 16
        ya, yb = max(base, Y0), min(base + 16, Y1 + 1)
        ax, az = cx * 16 - x0, cz * 16 - z0
        block_k, block_s = k[ids].reshape(16, 16, 16), code[ids].reshape(16, 16, 16)
        kinds[ya - Y0:yb - Y0, az:az + 16, ax:ax + 16] = block_k[ya - base:yb - base]
        states[ya - Y0:yb - Y0, az:az + 16, ax:ax + 16] = block_s[ya - base:yb - base]
        moved[az:az + 16, ax:ax + 16] = True
    built = (kinds == OTHER).any(axis=0)
    soil = kinds == SOIL
    ground = np.where(soil.any(axis=0), ny - 1 - np.argmax(soil[::-1], axis=0) + Y0, -9999)
    edits, tally = {}, Counter()

    def put(ix, y, iz, after, why):
        before = names[states[y - Y0, iz, ix]]
        if before != after:
            edits[int(ix) + x0, int(y), int(iz) + z0] = (before, after)
            tally[why] += 1

    # The hills: natural columns standing above the platform are cut to it.
    hill = moved & ~built & (ground > PLATFORM + 3)
    for iz, ix in zip(*np.nonzero(hill)):
        for y in range(PLATFORM + 1, Y1 + 1):
            if kinds[y - Y0, iz, ix] in (SOIL, PLANT):
                put(ix, y, iz, 'minecraft:air', 'cut hill')
        put(ix, PLATFORM, iz, 'minecraft:grass_block[snowy=false]', 'cut hill top')
        for y in range(SEA, PLATFORM):
            if kinds[y - Y0, iz, ix] in (AIR, WATER, PLANT):
                put(ix, y, iz, 'minecraft:dirt', 'fill under cut')
    # Trees left on a cut hill's rim would stand on nothing; the rim is cleared with it.
    ground_after = np.where(hill, PLATFORM, ground)
    # The sea wall: the outermost land column of the moved area, faced from the sea bed to the ground.
    inside = np.pad(moved, 1)
    edge = moved & ~(inside[:-2, 1:-1] & inside[2:, 1:-1] & inside[1:-1, :-2] & inside[1:-1, 2:])
    wall = edge & ~built & (ground_after > SEA)
    for iz, ix in zip(*np.nonzero(wall)):
        top = int(ground_after[iz, ix])
        floor_level = next((y for y in range(SEA, Y0, -1) if kinds[y - Y0, iz, ix] == SOIL and kinds[y - Y0 + 1, iz, ix] in (AIR, WATER)), SEA - 12)
        for y in range(max(floor_level - 2, Y0), top):
            put(ix, y, iz, 'minecraft:stone_bricks', 'sea wall')
        put(ix, top, iz, 'minecraft:smooth_stone', 'sea wall cap')
        for y in range(top + 1, min(top + 12, Y1 + 1)):
            if kinds[y - Y0, iz, ix] == PLANT:
                put(ix, y, iz, 'minecraft:air', 'sea wall clear')
    rows = [[x, y, z, b, s] for (x, y, z), (b, s) in sorted(edits.items())]
    a.out.mkdir(parents=True, exist_ok=True)
    report = dict(cells=len(rows), kinds=dict(tally), hill_columns=int(hill.sum()), wall_columns=int(wall.sum()), batches=split_rows(rows, a.out))
    (a.out / 'report.json').write_text(json.dumps(report, indent=1), 'utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--moved', type=Path, required=True, help='JSON list of the source chunks that moved')
    parser.add_argument('--out', type=Path, required=True)
    plan(parser.parse_args())
