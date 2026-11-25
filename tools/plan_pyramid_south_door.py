"""R65 feedback 36: the NERV pyramid's south entrance, laid out after the owner's two reference pictures.

- Door house: a low flat-roofed box on the south face, light grey top, opening to the south, on axis x 41 (the
  pictures put the entrance right of the face's middle; the face runs x -25..85 at ground level, and x 41 is as far
  right as a straight stair can go and still land inside the briefing hall, x 5..51).
- One straight axis from the door: an inner landing, five steps down to corridor A (walking -471), straight across
  it, then eleven steps (9 wide, x 37..45) down through the office floor and the hall ceiling into the briefing hall
  (walking -482). Side walls hide the stair profile, rails on top, lights in the office ceiling above.
- A light grey paved band along the south face's foot, a car park east of the door house, travelator steps that
  cross a junction turned into floor.
- The big red marking on the south face goes back to black panels; a small copy of it, sampled from the old one,
  goes above the white light band (y -405/-407), under the apex.
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
PAVE = 'minecraft:light_gray_concrete'
ROOF = 'minecraft:smooth_stone'
ASPH = 'minecraft:gray_concrete'
LINE = 'minecraft:white_concrete'
AIRS = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
PLANTS = ('air', 'grass', 'short_grass', 'tall_grass', 'fern')


def stairs(facing):
    return f'minecraft:smooth_quartz_stairs[facing={facing},half=bottom,shape=straight,waterlogged=false]'


def rail(n=False, e=False, s=False, w=False):
    t = lambda b: 'true' if b else 'false'
    return f'projectseele:nerv_edge_rail[east={t(e)},north={t(n)},south={t(s)},west={t(w)}]'


def short(s):
    return s.split('[')[0].split(':')[-1]


box = read_box(W, D, (-32, -505, 288), (111, -385, 447))
want = {}


def put(x, y, z, s):
    want[x, y, z] = s


def get(x, y, z):
    return want.get((x, y, z), box[(x, y, z)])


def clear(x, y, z):
    if short(get(x, y, z)) != 'air':
        put(x, y, z, AIR)


def face_cell(x, y):
    """The south face's outermost block at (x, y), or None."""
    for z in range(446, 326, -1):
        if box[(x, y, z)].split('[')[0] not in AIRS:
            return z if short(box[(x, y, z)]) in ('nerv_pyramid_panel', 'nerv_pyramid_marking') else None
    return None


AX = 41
X0, X1 = AX - 4, AX + 4                     # stair and door opening width 9
face_z = {y: [z for z in range(370, 395) if short(box[(AX, y, z)]) in ('nerv_pyramid_panel', 'nerv_pyramid_marking')]
          for y in range(-470, -455)}

# ---- the entrance: seen from above an isosceles triangle, its base on the face's foot (z 383, x 33..49) and its point
# reaching south to z 393, as in the reference picture. It is low, clad in the pyramid's panels, its top sloping down
# from -461 at the base to -463 at the point; the door (3 wide, 3 high) is the point itself, on the main stair's axis.
BASE, TIP, HALF = 383, 393, 8


def extent(z):
    """Half-width of the triangle in row z (the base width behind it, nothing beyond the point)."""
    if z > TIP:
        return -1
    return HALF if z <= BASE else round(HALF * (TIP - z) / (TIP - BASE))


def roof_at(z):
    return -461 - round(2 * (min(max(z, BASE), TIP - 2) - BASE) / (TIP - 2 - BASE))


for z in range(374, TIP + 1):
    e, ahead = extent(z), extent(z + 1)
    for d in range(-e, e + 1):
        x, top = AX + d, roof_at(z)
        for y in range(-467, top + 1):
            f = face_cell(x, y)
            if f is not None and z <= f:
                continue                        # inside the pyramid already
            if y == -467 and z < BASE:
                continue                        # the gutter behind the base is left as it is
            door = abs(d) <= 1 and -467 < y < -463
            shell = abs(d) == e or abs(d) > ahead   # the sides, and the south-facing step of each row
            if y == top:
                s_ = PYR
            elif y == -467:
                s_ = FLOOR if abs(d) < e or door else PYR
            elif door or not shell:
                s_ = AIR
            else:
                s_ = PYR
            put(x, y, z, s_)
for x, z in ((AX - 2, 385), (AX + 2, 385), (AX, 389)):
    put(x, -467, z, LIGHT)
# the opening in the face, and the inner landing (floor -467, z 380..382)
for x in range(X0, X1 + 1):
    for y in range(-466, -463):
        for z in face_z.get(y, []):
            put(x, y, z, AIR)
    for z in (380, 381, 382):
        put(x, -467, z, FLOOR)
        for y in (-466, -465, -464):
            if short(get(x, y, z)) in ('nerv_pyramid_panel', 'nerv_pyramid_marking'):
                put(x, y, z, AIR)

# ---- five steps down to corridor A, the top one level with the landing; landing z 371..374; corridor wall opened
steps = {379: -467, 378: -468, 377: -469, 376: -470, 375: -471}
for x in range(X0, X1 + 1):
    for z, y in steps.items():
        put(x, y, z, stairs('south'))
        for h in range(y + 1, y + 5):
            clear(x, h, z)
    for z in range(371, 375):
        put(x, -472, z, FLOOR)
        for h in (-471, -470, -469, -468):
            clear(x, h, z)
for z in range(372, 380):
    top = steps.get(z, -472) + 1
    put(X0 - 1, top, z, rail(e=True))           # beams along the edge, on the side facing the steps
    put(X1 + 1, top, z, rail(w=True))
for x, z in ((X0, 373), (X1, 373), (X0, 381), (X1, 381)):
    put(x, -472 if z < 380 else -467, z, LIGHT)

# ---- straight across corridor A: open its north wall (z 365), under the rest room's sign at -468
for x in range(X0, X1 + 1):
    for h in (-471, -470, -469):
        clear(x, h, 365)

# ---- the main stair: z 364 (top, level with corridor A) to z 354, walking -471 down to -482, x 37..45.
# Over z 355..364 it is open to the rest room ceiling (rest room floor, gap and hall ceiling cut); the bottom step
# z 354 stays under the hall ceiling, so the rest room keeps its floor from z 354 north (its beds at z 352..353).
STAIR = {364 - k: -472 - k for k in range(11)}
OPEN = range(355, 365)
for x in range(X0, X1 + 1):
    for z, y in STAIR.items():
        put(x, y, z, stairs('south'))
        for h in range(y + 1, -463 if z in OPEN else -474):
            clear(x, h, z)
        for h in range(-482, y):            # under the flight
            clear(x, h, z)
for z in STAIR:                              # side walls from the hall floor to the rest room floor, rail on top
    for x in (X0 - 1, X1 + 1):
        top = -472 if z in OPEN else -475
        for h in range(-482, top + 1):
            put(x, h, z, WALL)
        if z in OPEN:
            put(x, -471, z, rail(e=True) if x < AX else rail(w=True))
            for h in range(-470, -463):
                clear(x, h, z)
# rest room level: rail along the north edge of the opening (z 354)
for x in range(X0, X1 + 1):
    put(x, -472, 354, FLOOR) if short(get(x, -472, 354)) == 'air' else None
    put(x, -471, 354, rail(s=True))
    for h in range(-470, -463):
        clear(x, h, 354)
# lights in the office ceiling over the stair
for x in (AX - 3, AX, AX + 3):
    for z in (356, 359, 362):
        if short(get(x, -463, z)) != 'air':
            put(x, -463, z, LIGHT)
# hall: the flight lands on open floor (z 350..353 cleared of furniture, lights kept)
for x in range(X0 - 1, X1 + 2):
    for z in range(350, 354):
        for h in range(-482, -476):
            if short(get(x, h, z)) != 'air' and 'light' not in get(x, h, z):
                put(x, h, z, AIR)

# ---- travelators: steps crossing a junction become floor
cuts = [(x, -458, z) for x in (9, 10, 12, 13) for z in (299, 300, 301)]           # west passage at z 299
cuts += [(x, y, z) for y in (-486, -500) for x in (76, 77) for z in range(307, 312)]  # east passage z 308..310
n_cut = 0
for c in cuts:
    s = box[c]
    if 'escalator_step' in s and 'orientation=flat' in s and c not in want:
        put(*c, FLOOR)
        n_cut += 1

# ---- paved band along the south face foot (z 384..389; the lantern line at z 386 kept), x 21..88
for x in range(21, 89):
    for z in range(384, 390):
        if (x, -467, z) in want:
            continue
        s = short(box[(x, -467, z)])
        if s in ('grass_block', 'dirt') or (s == 'air' and z in (384, 385)):
            put(x, -467, z, PAVE)
            if short(box[(x, -466, z)]) in PLANTS:
                clear(x, -466, z)

# ---- helipad east of the entrance, where the reference has its car park: a grey apron with two square pads, each
# with a white edge, a white ring and a white H, lights flush at the corners and edge middles. map-buildings parks
# the two helicopters on the pad centres (PADS), noses south.
PADS = ((65, 402), (86, 402))
R = 9
for x in range(PADS[0][0] - R - 2, PADS[1][0] + R + 3):
    for z in range(391, 414):
        if short(box[(x, -467, z)]) in ('grass_block', 'dirt') and short(box[(x, -466, z)]) in PLANTS:
            put(x, -467, z, ASPH)
            clear(x, -466, z)
H = {(dx, dz) for dz in range(-3, 4) for dx in (-2, 2)} | {(dx, 0) for dx in (-1, 0, 1)}
for cx, cz in PADS:
    for dx in range(-R, R + 1):
        for dz in range(-R, R + 1):
            r = (dx * dx + dz * dz) ** .5
            edge = max(abs(dx), abs(dz)) == R
            mark = edge or 5.6 <= r <= 6.6 or (dx, dz) in H
            light = edge and (abs(dx), abs(dz)) in ((R, R), (R, 0), (0, R))
            put(cx + dx, -467, cz + dz, LIGHT if light else LINE if mark else ASPH)
            clear(cx + dx, -466, cz + dz)

# ---- the marking: the big one goes back to panels; a small copy above the light band
old = {}
for x in range(-30, 92):
    for y in range(-466, -419):
        z = face_cell(x, y)
        if z is not None and short(box[(x, y, z)]) == 'nerv_pyramid_marking':
            old[x, y] = z
for x in range(-30, 92):                    # every marking block on the south face, not only the outermost
    for y in range(-466, -419):
        for z in range(327, 447):
            if short(box[(x, y, z)]) == 'nerv_pyramid_marking':
                put(x, y, z, PYR)
ox0, ox1 = min(x for x, _ in old), max(x for x, _ in old)
oy0, oy1 = min(y for _, y in old), max(y for _, y in old)
NW, NH = int(sys.argv[3]) if len(sys.argv) > 3 else 11, int(sys.argv[4]) if len(sys.argv) > 4 else 11
nx0, ny0 = 30 - NW // 2, -404               # far-view base under the high-resolution plate (agreed frame x 25..35, y -404..-394)
sx, sy = (ox1 - ox0 + 1) / NW, (oy1 - oy0 + 1) / NH
new = set()
for i in range(NW):
    for j in range(NH):
        cells = [(x, y) for x in range(ox0 + round(i * sx), ox0 + round((i + 1) * sx))
                 for y in range(oy0 + round(j * sy), oy0 + round((j + 1) * sy))]
        if cells and sum((c in old) for c in cells) / len(cells) >= 0.35:
            new.add((nx0 + i, ny0 + j))
placed = 0
for x, y in new:
    z = face_cell(x, y)
    if z is not None:
        put(x, y, z, MARK)
        placed += 1

rows = [[x, y, z, box[(x, y, z)], s] for (x, y, z), s in sorted(want.items()) if box[(x, y, z)] != s]
json.dump(rows, open(sys.argv[2], 'w', encoding='utf8'))
print(len(rows), 'rows; travelator steps cut', n_cut, '; old marking cells', len(old), (ox0, ox1, oy0, oy1),
      '; new marking', placed, 'of', len(new))
print(Counter((short(r[3]), short(r[4])) for r in rows).most_common(20))
