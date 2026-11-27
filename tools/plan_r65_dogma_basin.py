"""Prepare the R65 Heaven's Door approach, Lilith chamber and surveyed column feet.

Writes explicit before/after states for write_deep_cells.py. The basin follows the
existing waterline. Structural supports below the galleries stay solid.
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

from plan_terminal_dogma import AIR, BED, FLOOR, GUIDE, LCL_BOX, LCL_SURFACE, RED, Cells

LCL = 'projectseele:lcl[level=0]'
SUBSTRATE = {BED, 'minecraft:deepslate[axis=y]', 'minecraft:stone'}
POST = 'minecraft:black_concrete'
CEILING = 'projectseele:nerv_structural_panel'


def basin_depth(x, z):
    # A shallow perimeter shelf falls away into the collector beneath the crucifix.
    x_inset = min(x + 35, 95 - x)
    z_inset = min(z - 261, 393 - z)
    shore = max(0.0, min(1.0, min(x_inset, z_inset) / 29))
    shore = shore * shore * (3 - 2 * shore)
    sump = math.exp(-((x - 30) / 33) ** 2 - ((z - 352) / 26) ** 2)
    return round(19 + 16 * shore + 9 * sump)


def plan(world, surveyed_posts):
    cells = Cells(world)
    rows = []
    depths = Counter()
    def change(x, y, z, after, allowed):
        before = cells.get(x, y, z)
        if before == after:
            return
        if before not in allowed:
            raise ValueError(f'Unexpected block at {x}, {y}, {z}: {before}')
        rows.append([x, y, z, before, after])

    # The closed leaves terminate at X=30 and X=31, including all three threshold blocks.
    for x in (30, 31):
        for z in range(240, 261):
            change(x, -1231, z, GUIDE, {FLOOR, GUIDE})

    feet = []
    for line in surveyed_posts.read_text().splitlines():
        x, z, bottom, top, floor, floor_state, ceiling = line.split()
        if (int(bottom), int(top), int(floor), floor_state, ceiling) != (-481, -475, -483, FLOOR, CEILING):
            continue
        x, z = int(x), int(z)
        if cells.get(x, -483, z) != FLOOR or cells.get(x, -481, z) != POST:
            raise ValueError(f'Column moved at {x}, {z}')
        change(x, -482, z, POST, {AIR})
        feet.append([x, -482, z])

    # The signed block entity and door drive occupy other elevations.
    small = len(rows)
    for x in range(LCL_BOX['x'][0], LCL_BOX['x'][1] + 1):
        for z in range(LCL_BOX['z'][0], LCL_BOX['z'][1] + 1):
            depth = basin_depth(x, z)
            bed = LCL_SURFACE - depth
            top = cells.get(x, LCL_SURFACE, z)
            if top == RED and 27 <= x <= 33 and 352 <= z <= 355:
                for y in range(bed + 1, -1287):
                    change(x, y, z, RED, SUBSTRATE)
                change(x, bed, z, BED, SUBSTRATE)
            elif top == LCL:
                # Leave built columns/piles and their original foundations untouched.
                if cells.get(x, -1280, z) not in SUBSTRATE | {LCL}:
                    continue
                for y in range(bed + 1, -1279):
                    change(x, y, z, LCL, SUBSTRATE)
                change(x, bed, z, BED, SUBSTRATE)
                depths[depth] += 1

    # Raking light across the nail heads, upper beam and face. The rim and
    # observation gallery retain their own practical fixtures and deep shadow.
    for x,y,z,level in [(30,-1218,343,12),(27,-1220,342,10),
                        (0,-1224,349,11),(60,-1224,349,11),
                        (14,-1224,351,9),(46,-1224,351,9),
                        (30,-1239,345,11),(30,-1257,346,7)]:
        change(x,y,z,f'minecraft:light[level={level},waterlogged=false]',{AIR})
    positions={(x,y,z) for x,y,z,_,_ in rows}
    if len(positions)!=len(rows):
        raise ValueError('Duplicate position')
    return rows, dict(posts=feet, floor_and_posts=small, pool_columns=sum(depths.values()),
                      depth_histogram=sorted(depths.items()), cells=len(rows))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world',type=Path,required=True)
    parser.add_argument('--survey',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    rows,summary=plan(args.world,args.survey)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'rows.json').write_text(json.dumps(rows,separators=(',',':')),'utf8')
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2),'utf8')
    print(summary)
