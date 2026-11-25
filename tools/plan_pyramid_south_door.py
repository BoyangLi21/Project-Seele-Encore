"""R65 feedback 36: a door on the NERV pyramid's south face, its porch, the inner bridge down to corridor A, a stair
from corridor A to the briefing level, travelator cuts at junctions and a car park on the lawn in front.

The door is on the pyramid's axis (x 30: the face's corners at ground level are x -25 and 85; the -440 and -400
cross-sections centre there too). The porch is a small gabled vestibule whose ridge stays below the red marking band
(y -461 and up). Inside, a landing and five stairs come down to corridor A (walking -471) through its south wall.
The stair to the briefing level runs east under corridor A's north lanes (z 366..367), clear of the briefing screen on
the hall's south wall (x 22..33), and enters the hall at x 47..49. Travelator steps that cross a junction become floor.
Writes rows [x, y, z, before, after] against the given world.
usage: plan_pyramid_south_door.py <world> <out.json>"""
import json
import sys
from collections import Counter
from pathlib import Path

from query_blocks import read_box

W = Path(sys.argv[1])
D = 'projectseele:geofront'
AIR = 'minecraft:air'
FLOOR = 'projectseele:nerv_floor_panel'
WALL = 'projectseele:nerv_wall_panel'
PYR = 'projectseele:nerv_pyramid_panel'
MARK = 'projectseele:nerv_pyramid_marking'
LIGHT = 'minecraft:sea_lantern'
ASPH = 'minecraft:gray_concrete'
LINE = 'minecraft:white_concrete'


def stairs(facing):
    return f'minecraft:smooth_quartz_stairs[facing={facing},half=bottom,shape=straight,waterlogged=false]'


def rail(n=False, e=False, s=False, w=False):
    t = lambda b: 'true' if b else 'false'
    return f'projectseele:nerv_edge_rail[east={t(e)},north={t(n)},south={t(s)},west={t(w)}]'


def short(s):
    return s.split('[')[0].split(':')[-1]


box = read_box(W, D, (-10, -505, 280), (95, -440, 430))
want = {}


def put(x, y, z, s):
    want[x, y, z] = s


def get(x, y, z):
    return want.get((x, y, z), box[(x, y, z)])


CX = 30
face_z = {y: [z for z in range(370, 395) if short(box[(CX, y, z)]) in ('nerv_pyramid_panel', 'nerv_pyramid_marking')]
          for y in range(-470, -455)}

# ---- porch: side walls x 25 / 35, roof stepping up to the ridge at -462, red edge on the gable front
PX0, PX1, FRONT, BACK = 25, 35, 389, 383


def roof_y(x):
    return -462 - (abs(x - CX) // 2)


for x in range(PX0, PX1 + 1):
    ry = roof_y(x)
    for z in range(BACK, FRONT + 1):
        put(x, -467, z, FLOOR)
        for y in range(-466, ry):
            put(x, y, z, PYR if x in (PX0, PX1) else AIR)
        put(x, ry, z, MARK if z == FRONT else PYR)
    for z in range(BACK - 5, BACK):         # the roof runs back to the face at its own height
        if face_z.get(ry) and z > max(face_z[ry]):
            put(x, ry, z, PYR)
for z in (385, 388):
    put(CX, -462, z, LIGHT)

# ---- the opening: face cells inside the porch section
for x in range(PX0 + 1, PX1):
    for y in range(-466, roof_y(x)):
        for z in face_z.get(y, []):
            put(x, y, z, AIR)

# ---- landing inside (floor -467, z 380..382) across the porch width, rails on its north edge beside the stairs
for x in range(PX0 + 1, PX1):
    for z in (380, 381, 382):
        put(x, -467, z, FLOOR)
        for y in (-466, -465, -464):
            if short(get(x, y, z)) in ('nerv_pyramid_panel', 'nerv_pyramid_marking'):
                put(x, y, z, AIR)
for x in list(range(PX0 + 1, 28)) + list(range(33, PX1)):
    put(x, -466, 379, rail(e=True, w=True))

# ---- five stairs (the top one level with the landing floor) north to corridor A's walking level, a landing and the opening in its south wall (z 371)
steps = {379: -467, 378: -468, 377: -469, 376: -470, 375: -471}
for x in range(28, 33):
    for z, y in steps.items():
        put(x, y, z, stairs('south'))
        for h in range(y + 1, y + 4):
            put(x, h, z, AIR)
    for z in range(371, 375):
        put(x, -472, z, FLOOR)
        for h in (-471, -470, -469, -468):
            if z == 371 or h < -468:
                put(x, h, z, AIR)
for x, y, z in ((26, -467, 381), (34, -467, 381), (28, -472, 373), (32, -472, 373)):   # the shell is dark inside
    put(x, y, z, LIGHT)
for z in range(372, 380):
    top = steps.get(z, -472) + 1
    for x in (27, 33):
        put(x, top, z, rail(n=True, s=True))

# ---- stair from corridor A down to the briefing level under the north lanes (z 366..367), entered at x 35
SX0 = 36
for i, x in enumerate(range(SX0, SX0 + 11)):
    y = -472 - i                            # stair block; the top one takes the corridor floor (walking -471 to -481)
    for z in (366, 367):
        put(x, y, z, stairs('west'))
        for h in range(y + 1, y + 4):
            if h <= -472:
                put(x, h, z, AIR)
    for h in range(y, -473):                # stairwell walls below the corridor floor
        for z in (365, 368):
            if short(get(x, h, z)) == 'air':
                put(x, h, z, WALL)
hole = [x for x in range(SX0, SX0 + 11) if get(x, -472, 366) == AIR]
for x in hole:
    put(x, -471, 368, rail(e=True, w=True))
if hole:
    for z in (366, 367):
        put(max(hole) + 1, -471, z, rail(n=True, s=True))
# landing x 47..49 (floor -483, z 364..367) and the doorway through the hall's south wall z 363
for x in (47, 48, 49):
    for z in (364, 365, 366, 367):
        put(x, -483, z, FLOOR)
        for h in (-482, -481, -480):
            put(x, h, z, AIR)
    for h in (-482, -481, -480):
        put(x, h, 363, AIR)
for z in (364, 365, 366, 367):
    for h in range(-483, -473):
        if short(get(50, h, z)) == 'air':
            put(50, h, z, FLOOR if h == -483 else WALL)
for x in (47, 48, 49):
    for h in range(-483, -473):
        if short(get(x, h, 368)) == 'air':
            put(x, h, 368, WALL)
for x, h, z in ((39, -475, 365), (43, -479, 365), (48, -478, 368)):
    put(x, h, z, LIGHT)

# ---- travelators: steps crossing a junction become floor
cuts = [(x, -472, z) for x in range(17, 35) for z in (366, 367, 369, 370)]       # corridor A: door and stair
# Not the lift door at x 55..57 (-472 and -458): the Moving Elevators guard puts lift 55;366's travel volume over the
# corridor's north lanes there (x 56..60, z 364..368), so map work may not write those steps.
cuts += [(x, -458, z) for x in (9, 10, 12, 13) for z in (299, 300, 301)]          # west passage at z 299
cuts += [(x, y, z) for y in (-486, -500) for x in (76, 77) for z in range(307, 312)]  # east passage z 308..310
n_cut = 0
for c in cuts:
    s = box[c]
    if 'escalator_step' in s and 'orientation=flat' in s and c not in want:
        put(*c, FLOOR)
        n_cut += 1

# ---- car park on the lawn south of the porch: two rows of bays and an aisle; a path from the porch; four lamps
# The lawn at -467 starts at x 21 (west of it the ground drops to the lakeside walk), so the car park runs east of the
# door: x 21..51, ten bays a row; the walk from the porch crosses the first row of bays to the aisle.
PLANTS = ('air', 'grass', 'short_grass', 'tall_grass', 'fern')
CP0, CP1 = 21, 51
for x in range(CP0, CP1 + 1):
    for z in range(390, 412):
        if short(box[(x, -467, z)]) not in ('grass_block', 'dirt') or short(box[(x, -466, z)]) not in PLANTS:
            continue
        walk = 28 <= x <= 32 and z <= 398
        if z < 394 and not walk:
            continue
        bay = 394 <= z <= 398 or 407 <= z <= 411
        line = (bay and (x - CP0) % 3 == 0) or z in (394, 411)
        put(x, -467, z, FLOOR if walk else LINE if line else ASPH)
        if short(box[(x, -466, z)]) != 'air':
            put(x, -466, z, AIR)
for x, z in ((CP0, 399), (CP0, 406), (CP1, 399), (CP1, 406)):
    for h in (-466, -465, -464):
        put(x, h, z, 'minecraft:iron_bars')
    put(x, -463, z, LIGHT)

rows = [[x, y, z, box[(x, y, z)], s] for (x, y, z), s in sorted(want.items()) if box[(x, y, z)] != s]
json.dump(rows, open(sys.argv[2], 'w', encoding='utf8'))
print(len(rows), 'rows; travelator steps cut', n_cut)
print(Counter((short(r[3]), short(r[4])) for r in rows).most_common(16))
