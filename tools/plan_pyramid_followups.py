"""R65 feedback 39 and 43, after the south gate (batch 725) and its helicopters (batch 726).

39: the rest room over the main stair (x 32..51, z 350..363, floor -472) lost its way out when the stair opening took
its door; it gets a door on each side of the opening (x 33..35 and x 47..49, 3 high) through its south wall (z 364) and
corridor A's north wall (z 365), and the travelator steps of corridor A's north lanes in front of them become floor.

43: the helipads move further south (centres z 426) and a short east-west runway runs along the lawn's south edge
(z 444..452, x 40..164, pointing along the face, not at it), with an apron and two J16 stands at its east end, noses
south to the runway. The old pads go back to grass.
Writes rows [x, y, z, before, after]. usage: plan_pyramid_followups.py <world> <out.json>"""
import json
import sys
from collections import Counter
from pathlib import Path

from query_blocks import read_box

W = Path(sys.argv[1])
D = 'projectseele:geofront'
AIR = 'minecraft:air'
FLOOR = 'projectseele:nerv_floor_panel'
GRASS = 'minecraft:grass_block[snowy=false]'
ASPH = 'minecraft:gray_concrete'
LINE = 'minecraft:white_concrete'
LIGHT = 'minecraft:sea_lantern'
PLANTS = ('air', 'grass', 'short_grass', 'tall_grass', 'fern')
box = read_box(W, D, (16, -475, 336), (191, -440, 463))
want = {}


def short(s):
    return s.split('[')[0].split(':')[-1]


def put(x, y, z, s):
    want[x, y, z] = s


def clear(x, y, z):
    if short(box[(x, y, z)]) != 'air':
        put(x, y, z, AIR)


# ---- 39: two doors out of the rest room
for x0 in (33, 47):
    for x in range(x0, x0 + 3):
        for z in (364, 365):
            for y in (-471, -470, -469):
                clear(x, y, z)
        for z in (366, 367):
            if 'escalator_step' in box[(x, -472, z)]:
                put(x, -472, z, FLOOR)

# ---- 43: old pads (centres z 414) back to grass
OLD = ((62, 414), (94, 414))
R = 9
for cx, cz in OLD:
    for dx in range(-R, R + 1):
        for dz in range(-R, R + 1):
            if short(box[(cx + dx, -467, cz + dz)]) in ('gray_concrete', 'white_concrete', 'sea_lantern'):
                put(cx + dx, -467, cz + dz, GRASS)


def lawn(x, z):
    return short(box[(x, -467, z)]) in ('grass_block', 'dirt', 'gray_concrete', 'white_concrete', 'sea_lantern') \
        and short(box[(x, -466, z)]) in PLANTS


def pave(x, z, s):
    if not lawn(x, z):
        raise SystemExit(f'not open lawn at {x},{z}: {box[(x, -467, z)]} / {box[(x, -466, z)]}')
    put(x, -467, z, s)
    clear(x, -466, z)


# new helipads
PADS = ((62, 426), (94, 426))
H = {(dx, dz) for dz in range(-3, 4) for dx in (-2, 2)} | {(dx, 0) for dx in (-1, 0, 1)}
for cx, cz in PADS:
    for dx in range(-R, R + 1):
        for dz in range(-R, R + 1):
            r = (dx * dx + dz * dz) ** .5
            edge = max(abs(dx), abs(dz)) == R
            mark = edge or 5.6 <= r <= 6.6 or (dx, dz) in H
            light = edge and (abs(dx), abs(dz)) in ((R, R), (R, 0), (0, R))
            pave(cx + dx, cz + dz, LIGHT if light else LINE if mark else ASPH)

# runway: 9 wide, edge lights every 8, threshold bars at both ends, dashed centre line
RX0, RX1, RZ0, RZ1 = 40, 164, 444, 452
CZ = (RZ0 + RZ1) // 2
for x in range(RX0, RX1 + 1):
    for z in range(RZ0, RZ1 + 1):
        edge = z in (RZ0, RZ1)
        threshold = (x - RX0 in (2, 3) or RX1 - x in (2, 3)) and z not in (RZ0, RZ1) and (z - RZ0) % 2 == 1
        centre = z == CZ and RX0 + 8 <= x <= RX1 - 8 and (x - RX0) % 8 < 4
        light = edge and (x - RX0) % 8 == 0 or (x in (RX0, RX1) and not edge)
        pave(x, z, LIGHT if light else LINE if threshold or centre else ASPH)

# apron with two J16 stands at the east end, joined to the runway; noses south (yaw 0) to the runway
AX0, AX1, AZ0 = 120, 161, 420
STANDS = ((130, 432), (152, 432))
for x in range(AX0, AX1 + 1):
    for z in range(AZ0, RZ0):
        stand_edge = any(max(abs(x - sx), abs(z - sz)) == 8 for sx, sz in STANDS)
        corner_light = any((abs(x - sx), abs(z - sz)) == (8, 8) for sx, sz in STANDS)
        pave(x, z, LIGHT if corner_light else LINE if stand_edge else ASPH)

rows = [[x, y, z, box[(x, y, z)], s] for (x, y, z), s in sorted(want.items()) if box[(x, y, z)] != s]
json.dump(rows, open(sys.argv[2], 'w', encoding='utf8'))
print(len(rows), 'rows')
print(Counter((short(r[3]), short(r[4])) for r in rows).most_common(12))
print('helipads', [(cx + .5, -466, cz + .5) for cx, cz in PADS], 'J16 stands', [(sx + .5, -466, sz + .5) for sx, sz in STANDS])
