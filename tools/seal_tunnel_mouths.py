"""Wall up the mouth of a half-dug tunnel whose road has been cut back.

Works on the capture with the cut rows laid over it, on columns within two of the cut columns near each
listed tunnel (x z radius). Each column is probed at the height of its nearest cut column: it is tunnel
when the air there has a natural roof (rock or soil, not a viaduct or a tree) within ROOF blocks, and open
when that air reaches the sky. Cut tunnel columns with air beside them outside the cut (open ground or the
kept road the spur branched from) form the mouth; their air from the floor to the roof is filled with stone
bricks, one block thick, so nothing is left open into the hill.
usage: seal_tunnel_mouths.py <capture> <rows-cut.json> <out-rows.json> x z r [x z r ...]"""
import json
import sys

from plan_station_access_corridor import CapturedSurface

c = CapturedSurface(sys.argv[1], partial=True)
cut = json.load(open(sys.argv[2], encoding='utf8'))
over = {(r[0], r[1], r[2]): r[4] for r in cut}
cutcols = {}
for x, y, z in over:
    cutcols[x, z] = min(cutcols.get((x, z), 10 ** 6), y)
AIR = ('minecraft:air', 'minecraft:cave_air')
NATURAL = ('minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block', 'minecraft:coarse_dirt', 'minecraft:gravel', 'minecraft:andesite',
           'minecraft:granite', 'minecraft:diorite', 'minecraft:tuff', 'minecraft:deepslate', 'minecraft:podzol', 'minecraft:rooted_dirt')
ROOF = 12
WALL = 'minecraft:stone_bricks'


def state(x, y, z):
    return over.get((x, y, z)) or c.state(x, y, z)


def solid(s):
    n = s.split('[')[0]
    return n not in AIR and not n.endswith(('_leaves', 'grass', 'fern', 'flower', 'torch', 'lantern', 'vine'))


def probe(x, z, yref):
    """('tunnel'|'open', floor, roof) for the air run at yref; None when the column is solid there."""
    y = yref - 1
    while y <= yref + 3 and solid(state(x, y, z)):
        y += 1
    if y > yref + 3:
        return None
    floor = y - 1
    while y <= floor + ROOF and not solid(state(x, y, z)):
        y += 1
    if y > floor + ROOF:
        return 'open', floor, None
    return ('tunnel' if state(x, y, z).split('[')[0] in NATURAL else 'built'), floor, y


rows, report = [], []
args = list(map(int, sys.argv[4:]))
for k in range(0, len(args), 3):
    tx, tz, tr = args[k:k + 3]
    near = {p: y for p, y in cutcols.items() if abs(p[0] - tx) <= tr and abs(p[1] - tz) <= tr}
    if not near:
        report.append(dict(at=[tx, tz], error='no cut cells'))
        continue
    info = {}
    for (cx, cz) in near:
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                q = (cx + dx, cz + dz)
                if q in info:
                    continue
                ref = min(near, key=lambda p: (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2)
                p = probe(q[0], q[1], near[ref])
                if p:
                    info[q] = p
    def passage(q, n):
        # n is outside the cut and has air at the height of q's opening
        if n in near:
            return False
        _, f, roof = info[q]
        return any(not solid(state(n[0], y, n[1])) for y in range(f + 1, min(f + 4, roof)))
    mouth = [q for q, (kind, f, roof) in info.items() if kind == 'tunnel' and q in near
             and any(passage(q, (q[0] + dx, q[1] + dz)) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    n0 = len(rows)
    for x, z in mouth:
        _, f, roof = info[x, z]
        for y in range(f + 1, roof):
            rows.append([x, y, z, c.state(x, y, z), WALL])     # world state as before: merged over the cut rows, this row wins
    kinds = [v[0] for v in info.values()]
    report.append(dict(at=[tx, tz], tunnel=kinds.count('tunnel'), open=kinds.count('open'), built=kinds.count('built'),
                       mouth_columns=len(mouth), cells=len(rows) - n0))
json.dump(rows, open(sys.argv[3], 'w', encoding='utf8'))
for r in report:
    print(r)
