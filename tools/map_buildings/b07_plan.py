"""South residential white building (B07): open its street front.

Forecourt x 175..183, z 527..556 is cut down to the street level (floor 80) and paved with
smooth stone. The hill left around it (not the street, not the building) gets a stone-brick
retaining wall on the first column out, up to 8 cells; where the hill is higher, a 3-column
grass bench at y 89 and a second wall behind it. The terrain inside the building above its
floors goes too (the fill cells found by the scan, re-checked against the world).
"""
import json, sys
from collections import Counter
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, is_natural, short
from e5_plan import is_building, is_veg

w = World(REGION)
F = 80
FX0, FX1, FZ0, FZ1 = 175, 183, 527, 556
WALL, PAVE, GRASS, AIR = 'minecraft:stone_bricks', 'minecraft:smooth_stone', 'minecraft:grass_block[snowy=false]', 'minecraft:air'
T1 = F + 9                     # top of the first wall and level of the bench
rows = {}


def put(x, y, z, after):
    s = w.get(x, y, z)
    if s != after and not w.block_entity(x, y, z):
        rows[x, y, z] = [x, y, z, s, after]


def top(x, z):
    for y in range(F + 40, F - 5, -1):
        s = w.get(x, y, z)
        if is_natural(s):
            return y
        if not (is_open(s) or is_veg(s)):
            return None            # built over: street, building
    return None


zone = {(x, z) for x in range(FX0, FX1 + 1) for z in range(FZ0, FZ1 + 1)}
# forecourt
for (x, z) in zone:
    for y in range(F + 1, F + 40):
        s = w.get(x, y, z)
        if is_natural(s) or is_veg(s) or (is_open(s) and s not in ('minecraft:air', 'minecraft:cave_air')):
            put(x, y, z, AIR)
    s = w.get(x, F, z)
    if is_natural(s):
        put(x, F, z, PAVE)


def dist(c):
    return max(max(FX0 - c[0], c[0] - FX1, 0), max(FZ0 - c[1], c[1] - FZ1, 0))


# the hill around it, only on the sides away from the street (x >= FX0) and outside the building
ring = {}
for x in range(FX0, FX1 + 6):
    for z in range(FZ0 - 6, FZ1 + 7):
        c = (x, z)
        if c in zone:
            continue
        d = dist(c)
        if 1 <= d <= 5:
            t = top(x, z)
            if t is not None and t > F:
                ring[c] = (d, t)
for (x, z), (d, t) in ring.items():
    if d == 1:
        for y in range(F + 1, min(t, T1) + 1):
            put(x, y, z, WALL)
        if t > T1:
            for y in range(T1 + 1, t + 1):
                put(x, y, z, AIR)
    elif d <= 4 and t > T1:
        for y in range(T1 + 1, t + 1):
            put(x, y, z, AIR)
        put(x, T1, z, GRASS)
    elif d == 5 and t > T1:
        for y in range(T1 + 1, t + 1):
            put(x, y, z, WALL)
# terrain inside the building
fill = np.load(Path(__file__).parent / 'fill_room.npy')
m = (fill[:, 0] >= 184) & (fill[:, 0] <= 208) & (fill[:, 2] >= 527) & (fill[:, 2] <= 556)
for x, y, z, _ in fill[m].tolist():
    if is_natural(w.get(x, y, z)):
        put(x, y, z, AIR)
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
R = list(rows.values())
(out / 'rows.json').write_text(json.dumps(R), 'utf8')
print(len(R), Counter(short(r[3]) + '->' + short(r[4]) for r in R).most_common(10))
