"""R65 feedback 40: leftover pieces of an old structure on the hillside north of the HQ (y 77..81, z -177..-159):
two black deck slabs with a white centre stripe (x 48..56 and x 160..168 at y 80), their railings at y 81 along
z -176..-160 (and the loose railing posts between them), a basalt pier under the west slab and a polished deepslate
footing sticking out of the slope beside it. They go; each touched column gets its hillside back, its surface
interpolated along z from the untouched columns on either side.
Writes rows [x, y, z, before, after]. usage: plan_hillside_leftovers.py <world> <out.json>"""
import json
import sys
from collections import Counter
from pathlib import Path

from query_blocks import read_box

W = Path(sys.argv[1])
D = 'projectseele:geofront'
X0, X1, Z0, Z1, Y0, Y1 = -48, 191, -192, -145, 60, 95
box = read_box(W, D, (X0, Y0, Z0), (X1, Y1, Z1))
AIRS = ('minecraft:air', 'minecraft:cave_air')
ROAD = ('light_gray_concrete', 'asphalt', 'trafficcraft', 'period_station_floor')


def name(s):
    return s.split('[')[0]


def leftover(x, y, z):
    n = name(box[(x, y, z)])
    if not (-177 <= z <= -159):
        return False
    if n in ('minecraft:black_concrete', 'minecraft:white_concrete') and y == 80 and (48 <= x <= 56 or 160 <= x <= 168):
        return True
    if n == 'projectseele:nerv_edge_rail' and y == 81 and -20 <= x <= 180:
        if (x, y, z) == (48, 81, -162):
            return True                     # a loose post on the west slab's edge, beside the road's end
        return not any(r in box.get((x + dx, y + dy, z + dz), '') for r in ROAD
                       for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)))
    if n == 'minecraft:polished_basalt' and x == 48 and z == -168 and 68 <= y <= 76:
        return True
    if n == 'minecraft:polished_deepslate' and 36 <= x <= 51 and 77 <= y <= 79 and -171 <= z <= -165:
        return True
    return False


cells = {(x, y, z) for x in range(-20, 181) for y in range(66, 83) for z in range(-177, -158) if leftover(x, y, z)}
columns = {(x, z) for x, y, z in cells}


def natural_top(x, z):
    for y in range(Y1, Y0, -1):
        n = name(box[(x, y, z)])
        if n in AIRS or 'leaves' in n or 'log' in n or 'grass' == n.split(':')[-1] or n.endswith('short_grass') \
                or n.endswith('tall_grass') or n.endswith('fern') or (x, y, z) in cells:
            continue
        return y
    return Y0


def surface(x, z):
    """Hillside height for a touched column: interpolated along z between the nearest untouched columns."""
    lo = next(zz for zz in range(z, Z0, -1) if (x, zz) not in columns)
    hi = next(zz for zz in range(z, Z1) if (x, zz) not in columns)
    a, b = natural_top(x, lo), natural_top(x, hi)
    return round(a + (b - a) * (z - lo) / (hi - lo)) if hi != lo else a


want = {}
for x, z in columns:
    h = surface(x, z)
    ys = [y for (cx, y, cz) in cells if (cx, cz) == (x, z)]
    for y in range(min(min(ys), h - 3), max(ys) + 1):
        s = box[(x, y, z)]
        if (x, y, z) in cells or (name(s) in AIRS and y <= h):
            want[x, y, z] = ('minecraft:grass_block[snowy=false]' if y == h else 'minecraft:dirt' if y >= h - 3
                             else 'minecraft:stone') if y <= h else 'minecraft:air'
# a column whose new top is bare stone or dirt gets a grass top and dirt under it, like the slope around it
for x, z in columns:
    top = next(y for y in range(Y1, Y0, -1)
               if name(want.get((x, y, z), box[(x, y, z)])) not in AIRS
               and not any(k in name(want.get((x, y, z), box[(x, y, z)])) for k in ('leaves', 'log', 'short_grass', 'tall_grass', 'fern')))
    if name(want.get((x, top, z), box[(x, top, z)])) in ('minecraft:stone', 'minecraft:dirt'):
        want[x, top, z] = 'minecraft:grass_block[snowy=false]'
        for y in (top - 1, top - 2):
            if name(want.get((x, y, z), box[(x, y, z)])) == 'minecraft:stone':
                want[x, y, z] = 'minecraft:dirt'
rows = [[x, y, z, box[(x, y, z)], s] for (x, y, z), s in sorted(want.items()) if box[(x, y, z)] != s]
json.dump(rows, open(sys.argv[2], 'w', encoding='utf8'))
print(len(cells), 'leftover cells in', len(columns), 'columns;', len(rows), 'rows')
print(Counter((name(r[3]).split(':')[-1], name(r[4]).split(':')[-1]) for r in rows).most_common(12))
