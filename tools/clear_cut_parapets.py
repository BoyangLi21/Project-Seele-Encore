"""Take away what a cut-back road leaves standing: parapets of a raised road and floating deck remnants.

Looks within two columns of the cut columns, on a capture taken after the cut, for columns topped by a parapet
or deck (stone bricks, their slab or wall, iron bars) standing two or more blocks
above the restored ground. Below the top, bridge work also takes in stone brick stairs and light grey concrete. Columns within two of a declared cell are a road that stays and are left alone.
A run of such blocks with air under it is a floating remnant and goes entirely; otherwise the run comes down to
the ground beside it (lowest neighbouring non-bridge top), whose level gets grass and below it dirt.
usage: clear_cut_parapets.py <capture-after-cut> <network.npz> <rows-cut.json> <out-rows.json>"""
import json
import sys

import numpy as np

from plan_station_access_corridor import CapturedSurface

c = CapturedSurface(sys.argv[1], partial=True)
a, b, _, _ = c.bounds
H = c.measured['highest']
net = np.load(sys.argv[2])
ax, az = map(int, net['bounds'][:2])
declared = net['road'] | net['walk']
cutcols = {(r[0], r[2]) for r in json.load(open(sys.argv[3], encoding='utf8'))}
DETECT = ('iron_bars', 'stone_brick_wall', 'stone_bricks', 'stone_brick_slab')   # what a parapet or deck top is made of
STRUCT = ('iron_bars', 'stone_brick_wall', 'stone_bricks', 'stone_brick_slab', 'light_gray_concrete', 'stone_brick_stairs')
AIR = ('minecraft:air', 'minecraft:cave_air')


def name(s):
    return s.split('[')[0]


def top(x, z):
    return int(H[z - b, x - a])


found = set()
for (x, z) in cutcols:
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            q = (x + dx, z + dz)
            if q in cutcols or q in found:
                continue
            if name(c.state(q[0], top(*q), q[1])).endswith(DETECT) and top(*q) - top(x, z) >= 2:
                found.add(q)
rows = []
for x, z in sorted(found):
    if declared[z - 2 - az:z + 3 - az, x - 2 - ax:x + 3 - ax].any():
        continue
    gs = [top(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)
          if not name(c.state(x + dx, top(x + dx, z + dz), z + dz)).endswith(STRUCT)]
    g = min(gs) if gs else None
    y = top(x, z)
    yb = y
    while name(c.state(x, yb, z)).endswith(STRUCT):
        yb -= 1
    if c.state(x, yb, z) in AIR:
        g = None
    while name(c.state(x, y, z)).endswith(STRUCT):
        s = c.state(x, y, z)
        if g is not None and y <= g:
            rows.append([x, y, z, s, 'minecraft:grass_block[snowy=false]' if y == g else 'minecraft:dirt'])
            if y <= g - 1:
                break
        else:
            rows.append([x, y, z, s, 'minecraft:air'])
        y -= 1
json.dump(rows, open(sys.argv[4], 'w', encoding='utf8'))
print(len(found), 'bridge-work columns beside the cut,', len(rows), 'rows')
