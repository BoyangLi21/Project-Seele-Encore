"""Fit the outer black cladding to the three connected launch bays beneath the GeoFront roof."""
import argparse
import json
from collections import defaultdict
from itertools import groupby
import nbtlib
from write_deep_cells import state_name, state_entry
from pathlib import Path

import numpy as np
from query_blocks import AIR, iter_selected_sections

BLACK = 'minecraft:black_concrete'
WEST, EAST, NORTH, SOUTH = -34, 94, -55, 6
FLOOR, ROOF = -466, 24


def on_facade(x, y, z):
    if not (FLOOR <= y <= ROOF and WEST <= x <= EAST and NORTH <= z <= SOUTH):
        return False
    if x not in (WEST, EAST) and z not in (NORTH, SOUTH):
        return False
    # The personnel lift, its landing and the attached corridor occupy this corner.
    if x >= 87 and z <= -32 and y <= -435:
        return False
    if (x, z) == (30, SOUTH) and y <= -463:
        return False  # Existing guide panel where the shaft meets the floor.
    # Ground-level pedestrian passages between the three launch tubes.
    return not (y <= FLOOR + 3 and (6 <= x <= 12 or 48 <= x <= 54))


def stage_recipes(world, folder, rows):
    relative = Path('dimensions/projectseele/geofront/data')
    data = world / relative
    identity = nbtlib.load(next(data.glob('projectseele_city_rigid_control_r45_*.dat')))['data']['WorldUUID']
    chunks = defaultdict(lambda: defaultdict(list))
    for x, y, z, _, _ in rows:
        chunks[x >> 4, z >> 4][x,z].append(y)
    for (cx,cz), columns in chunks.items():
        rel = relative / 'city_rigid_generation_r45/surface' / f'{cx}_{cz}.dat'
        path = world / rel
        tag = nbtlib.load(path) if path.exists() else nbtlib.File({
            'Version':nbtlib.Int(1), 'WorldUUID':identity,
            'Palette':nbtlib.List[nbtlib.Compound](), 'Spans':nbtlib.List[nbtlib.IntArray](),
            'BlockEntities':nbtlib.List[nbtlib.Compound]()})
        palette = [state_name(v) for v in tag['Palette']]
        if BLACK not in palette:
            palette.append(BLACK)
            tag['Palette'].append(state_entry(BLACK))
        black = palette.index(BLACK)
        for (x,z), ys in columns.items():
            for _, group in groupby(enumerate(sorted(ys)), lambda pair: pair[1] - pair[0]):
                run = [y for _,y in group]
                tag['Spans'].append(nbtlib.IntArray([x,z,run[0],run[-1],black]))
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        tag.save(target)


def plan(world, output, recipe_folder):
    dim = 'projectseele:geofront'
    wanted = {(cx,cz):set(range(FLOOR//16,ROOF//16+1)) for cx in range(WEST//16,EAST//16+1) for cz in range(NORTH//16,SOUTH//16+1)}
    samples = {}
    for cx,cz,sy,palette,ids in iter_selected_sections(world,dim,wanted):
        samples[cx,sy,cz] = palette,np.asarray(ids).reshape(16,16,16)
    def state(x,y,z):
        p,ids = samples[x//16,y//16,z//16]
        return p[ids[y%16,z%16,x%16]]
    # On every exposed floor, each tube already has four uninterrupted walls.
    # The extension is on their outside and does not intersect an EVA opening.
    for y in range(FLOOR, ROOF+1):
        for left in (-29, 13, 55):
            wall=[(x,z) for x in (left,left+34) for z in range(-54,6)]
            wall.extend((x,z) for z in (-54,5) for x in range(left,left+35))
            if any(state(x,y,z) in AIR for x,z in wall):
                raise ValueError(f'Existing bay opening at {left}, {y}; resurvey cladding')
    footprint = {(x,z) for x in (WEST,EAST) for z in range(NORTH,SOUTH+1)}
    footprint.update((x,z) for z in (NORTH,SOUTH) for x in range(WEST,EAST+1))
    rows = []
    for x,z in sorted(footprint):
        for y in range(FLOOR,ROOF+1):
            if on_facade(x,y,z):
                old = state(x,y,z)
                if old in AIR:
                    rows.append([x,y,z,old,BLACK])
                elif old != BLACK:
                    raise ValueError(f'Unexpected exterior attachment {(x,y,z)} {old}')
    stage_recipes(world, recipe_folder, rows)
    output.write_text(json.dumps(rows),'utf8')
    print('Exterior cells',len(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('world',type=Path)
    parser.add_argument('out',type=Path)
    parser.add_argument('--recipes',type=Path,required=True,help='stage the chunk-generation recipes here')
    args=parser.parse_args()
    plan(args.world,args.out,args.recipes)
