"""Build short TrafficCraft road connections from a list of centrelines.

Each connection: {"id", "points": [[x, z], ...] from the dead end to the road it joins,
"feet": [start, end] walking heights (optional: taken from the declared network at the two ends),
"road": asphalt half width in cells, "walk": footway width each side, "purpose"}.
Cells within road+0.5 of the centreline get asphalt, the next `walk` cells concrete; declared cells
are left as they are. The walking height runs linearly along the line in eighths (TrafficCraft
slope layers), at most a quarter of a block per block. Under the deck: up to 4 blocks of air or
water are filled with dirt; deeper gaps become a bridge (stone brick beam under the deck, stone
brick piers every 6 blocks on the outer cells, stone brick walls on the outer footway). Above the
deck 4 blocks are cleared of soil and plants only; anything built there is reported as blocked.
Outputs rows.json (write_deep_cells.py), network.npz, check.json.
usage: build_road_connection.py <capture> <network.npz> <connections.json> <outdir>"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
net = np.load(sys.argv[2])
network = {k: net[k].copy() for k in net.files}
conns = json.load(open(sys.argv[3], encoding='utf8'))
out = Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
ax, az = map(int, network['bounds'][:2])
road, walk, g2 = network['road'], network['walk'], network['grade2']
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
LOOSE = ('minecraft:water', 'minecraft:grass', 'minecraft:short_grass', 'minecraft:tall_grass', 'minecraft:fern', 'minecraft:large_fern',
         'minecraft:snow', 'minecraft:dead_bush', 'minecraft:seagrass', 'minecraft:tall_seagrass', 'minecraft:kelp', 'minecraft:kelp_plant')
SOIL = ('minecraft:grass_block', 'minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:stone', 'minecraft:gravel', 'minecraft:sand', 'minecraft:podzol',
        'minecraft:andesite', 'minecraft:granite', 'minecraft:diorite', 'minecraft:moss_block', 'minecraft:rooted_dirt', 'minecraft:clay', 'minecraft:mud')
FILL_MAX, PIER_EVERY, HEAD = 4, 6, 4


def name(s):
    return s.split('[')[0]


def soft(n):
    return n in AIR or n in LOOSE or n.endswith(('_leaves', '_log', 'flower', 'tulip', 'sapling', 'bush', 'vine', 'roots', 'mushroom'))


def declared_feet(x, z):
    for d in range(4):
        for dx in range(-d, d + 1):
            for dz in range(-d, d + 1):
                if road[z + dz - az, x + dx - ax] or walk[z + dz - az, x + dx - ax]:
                    return g2[z + dz - az, x + dx - ax] / 2 + 1
    raise ValueError(('No declared cell near', x, z))


writes, errors, report = {}, [], []


def put(x, y, z, state, purpose):
    before = cap.state(x, y, z)
    if before != state:
        writes[x, y, z] = [x, y, z, before, state, purpose]


def deck(x, z, feet, surface, purpose):
    """Deck, headroom and fill for one column; returns 'fill' or 'bridge'."""
    base = math.floor(feet) - 1
    layers = int(round((feet - math.floor(feet)) * 8))
    put(x, base, z, surface, purpose)
    if layers:
        put(x, base + 1, z, f'{surface}_slope[layers={layers},waterlogged=false]', purpose)
    for y in range(base + (2 if layers else 1), base + 2 + HEAD):
        n = name(cap.state(x, y, z))
        if n in AIR:
            continue
        if soft(n) or n in SOIL:
            put(x, y, z, 'minecraft:air', 'connection headroom')
        else:
            errors.append([purpose, 'blocked', [x, y, z], n])
    depth = 0
    while depth <= 40 and soft(name(cap.state(x, base - 1 - depth, z))):
        depth += 1
    if depth > FILL_MAX:
        return 'deep', base, layers, depth
    for k in range(depth):
        put(x, base - 1 - k, z, 'minecraft:dirt', 'connection fill')
    return 'fill', base, layers, depth


def paved_near(x, z, feet):
    return any(cap.state(x, y, z).startswith('trafficcraft:') for y in range(math.floor(feet) - 2, math.floor(feet) + 1))


for c in [c for c in conns if 'repave_box' in c]:
    # Declared cells in the box with no TrafficCraft paving at their declared height get it back.
    x0, z0, x1, z1 = c['repave_box']
    n0, cols = len(writes), 0
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if not (road[z - az, x - ax] or walk[z - az, x - ax]):
                continue
            feet = g2[z - az, x - ax] / 2 + 1
            if paved_near(x, z, feet):
                continue
            kind = deck(x, z, feet, 'trafficcraft:asphalt' if road[z - az, x - ax] else 'trafficcraft:concrete', c['id'] + ' repave')
            if kind[0] == 'deep':
                errors.append([c['id'], 'repave over a drop', [x, z], kind[3]])
            cols += 1
    report.append(dict(id=c['id'], repaved_columns=cols, cells=len(writes) - n0, purpose=c.get('purpose', '')))
conns = [c for c in conns if 'repave_box' not in c]

for c in conns:
    pts = np.array(c['points'], float) + .5
    seg = np.diff(pts, axis=0)
    lens = np.hypot(*seg.T)
    total = float(lens.sum())
    f0, f1 = c.get('feet') or (declared_feet(*map(int, c['points'][0])), declared_feet(*map(int, c['points'][-1])))
    if abs(f1 - f0) > total * .25 + .01:
        errors.append([c['id'], f'too steep: {f1 - f0:+.2f} over {total:.1f}'])
        continue
    rw, ww = c.get('road', 2), c.get('walk', 1)
    reach = rw + ww + .5
    cells = {}
    # Sample the centreline densely; each cell keeps the nearest sample's distance and along-position.
    for k in range(len(seg)):
        n = max(2, int(lens[k] * 8))
        for t in np.linspace(0, 1, n):
            p = pts[k] + seg[k] * t
            s = float(lens[:k].sum() + lens[k] * t)
            for dx in range(-int(reach) - 1, int(reach) + 2):
                for dz in range(-int(reach) - 1, int(reach) + 2):
                    x, z = int(math.floor(p[0])) + dx, int(math.floor(p[1])) + dz
                    d = math.hypot(x + .5 - p[0], z + .5 - p[1])
                    if d <= reach and (d < cells.get((x, z), (9e9,))[0]):
                        cells[x, z] = (d, s)
    n0 = len(writes)
    kinds = Counter()
    for (x, z), (d, s) in sorted(cells.items()):
        if road[z - az, x - ax] or walk[z - az, x - ax]:
            continue
        feet = round((f0 + (f1 - f0) * s / total) * 8) / 8
        surface = 'trafficcraft:asphalt' if d <= rw + .5 else 'trafficcraft:concrete'
        base = math.floor(feet) - 1
        layers = int(round((feet - math.floor(feet)) * 8))
        put(x, base, z, surface, 'connection deck')
        if layers:
            put(x, base + 1, z, f'{surface}_slope[layers={layers},waterlogged=false]', 'connection deck')
        for y in range(base + (2 if layers else 1), base + 2 + HEAD):
            n = name(cap.state(x, y, z))
            if n in AIR:
                continue
            if soft(n) or n in SOIL:
                put(x, y, z, 'minecraft:air', 'connection headroom')
            else:
                errors.append([c['id'], 'blocked', [x, y, z], n])
        # Support.
        depth = 0
        while depth <= 40 and soft(name(cap.state(x, base - 1 - depth, z))):
            depth += 1
        outer = d > rw + ww - .5
        if depth <= FILL_MAX:
            for k in range(depth):
                put(x, base - 1 - k, z, 'minecraft:dirt', 'connection fill')
            kinds['fill'] += 1
        else:
            put(x, base - 1, z, 'minecraft:stone_bricks', 'bridge beam')
            if outer and int(s) % PIER_EVERY == 0:
                for k in range(1, depth):
                    put(x, base - 1 - k, z, 'minecraft:stone_bricks', 'bridge pier')
            if outer and ww:
                put(x, base + (2 if layers else 1), z, 'minecraft:stone_brick_wall', 'bridge parapet')
            kinds['bridge'] += 1
        walk[z - az, x - ax] = True
        road[z - az, x - ax] = surface == 'trafficcraft:asphalt'
        g2[z - az, x - ax] = int(round((feet - 1) * 2))
    report.append(dict(id=c['id'], length=round(total, 1), feet=[f0, f1], grade=round(abs(f1 - f0) / total, 3), columns=sum(kinds.values()),
                       support=dict(kinds), cells=len(writes) - n0, purpose=c.get('purpose', '')))
rows = [w[:5] for w in writes.values()]
json.dump(rows, open(out / 'rows.json', 'w', encoding='utf8'))
np.savez_compressed(out / 'network.npz', **network)
check = dict(errors=errors, connections=report, cells=len(rows), purposes=Counter(w[5] for w in writes.values()))
json.dump(check, open(out / 'check.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print(json.dumps(dict(cells=len(rows), errors=len(errors), purposes=check['purposes']), ensure_ascii=False))
for r in report:
    print(r)
for e in errors[:20]:
    print('ERROR', e)
