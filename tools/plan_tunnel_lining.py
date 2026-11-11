"""Line exposed soil inside a tunnel cavity with stone.

Cavity cells: air with a solid roof within 16 blocks above (open cuttings under the sky are left alone).
Every soil block (dirt, grass, coarse dirt, podzol, rooted dirt, mud) touching a cavity cell on any of
its six faces becomes stone; grass and plants standing in the cavity go too. Nothing else is touched.
usage: plan_tunnel_lining.py <capture> x0 y0 z0 x1 y1 z1 <outdir> [sx sy sz]
With a seed cell, only the roofed cavity connected to it is lined (side pockets in the hills are not)."""
import json
import sys
from collections import Counter
from pathlib import Path

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
x0, y0, z0, x1, y1, z1 = map(int, sys.argv[2:8])
out = Path(sys.argv[8])
out.mkdir(parents=True, exist_ok=True)
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
SOIL = ('minecraft:dirt', 'minecraft:grass_block', 'minecraft:coarse_dirt', 'minecraft:podzol', 'minecraft:rooted_dirt', 'minecraft:mud')
PLANTS = ('minecraft:grass', 'minecraft:short_grass', 'minecraft:tall_grass', 'minecraft:fern', 'minecraft:large_fern', 'minecraft:dead_bush')


def solid(n):
    return n not in AIR and n not in PLANTS and not n.endswith(('_leaves', '_log', '_wood', 'vine'))


def name(x, y, z):
    return cap.state(x, y, z).split('[')[0]


def open_cell(n):
    return n in AIR or n in PLANTS


def roofed(x, y, z):
    return any(solid(name(x, yy, z)) for yy in range(y + 1, y + 17))


if len(sys.argv) > 11:
    from collections import deque
    seed = tuple(map(int, sys.argv[9:12]))
    cavity, q = {seed}, deque([seed])
    while q:
        x, y, z = q.popleft()
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            p = (x + dx, y + dy, z + dz)
            if p in cavity or not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and z0 <= p[2] <= z1):
                continue
            if open_cell(name(*p)) and roofed(*p):
                cavity.add(p)
                q.append(p)
else:
    cavity = {(x, y, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) for y in range(y0, y1 + 1)
              if open_cell(name(x, y, z)) and roofed(x, y, z)}
rows, kinds = {}, Counter()
for (x, y, z) in cavity:
    if name(x, y, z) in PLANTS:
        rows[x, y, z] = [x, y, z, cap.state(x, y, z), 'minecraft:air']
        kinds['plant'] += 1
    for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        p = (x + dx, y + dy, z + dz)
        if p not in rows and name(*p) in SOIL:
            rows[p] = [*p, cap.state(*p), 'minecraft:stone']
            kinds[name(*p)] += 1
rows = list(rows.values())
json.dump(rows, open(out / 'rows.json', 'w', encoding='utf8'))
check = dict(errors=[], cells=len(rows), kinds=kinds, box=[x0, y0, z0, x1, y1, z1], cavity_cells=len(cavity))
json.dump(check, open(out / 'check.json', 'w', encoding='utf8'), indent=1)
print(json.dumps(check))
