"""Canon homes: Rei's old danchi rows (with room 402) on the Sengokuhara plateau, Comfort 17 (with apartment 11-A-2)
on the slope south of the city, and Kirisato restyled to the same danchi rows. Original vanilla-block designs.

  python canon_homes.py rei|comfort|kirisato <out dir>

Reads BUILDINGS_WORLD (the copy to plan on) and GUARDS_WORLD (protection tables). Writes rows.json
[[x, y, z, before, after], ...], signs.json for write_deep_cells --signs, report.json and refused.json.
"""
import json, sys, hashlib
from collections import Counter
from pathlib import Path
from mca import REGION, World
from blocks import is_open
from float_fix import guards

AIR = 'minecraft:air'


def M(s):
    return 'minecraft:' + s


def h(*a):
    return int(hashlib.md5('/'.join(map(str, a)).encode()).hexdigest()[:8], 16)


def door(kind, facing, hinge='left'):
    p = f'facing={facing},hinge={hinge},open=false,powered=false'
    return M(f'{kind}[half=lower,{p}]'), M(f'{kind}[half=upper,{p}]')


def stair(kind, facing, half='bottom'):
    return M(f'{kind}[facing={facing},half={half},shape=straight,waterlogged=false]')


PANE = M('glass_pane[east=false,north=false,south=false,waterlogged=false,west=false]')


def pane(colour=None):
    return M((f'{colour}_stained_' if colour else '') + 'glass_pane[east=false,north=false,south=false,waterlogged=false,west=false]')


BARS = M('iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]')
LAMP_OFF, LAMP_ON = M('redstone_lamp[lit=false]'), M('redstone_lamp[lit=true]')


def lever(on):
    return M(f'lever[face=ceiling,facing=north,powered={"true" if on else "false"}]')


def button(facing):
    return M(f'stone_button[face=wall,facing={facing},powered=false]')


def wall_sign(facing, wood='spruce'):
    return M(f'{wood}_wall_sign[facing={facing},waterlogged=false]')


class Build:
    """World-coordinate cells plus signs; stairs are laid last so later floor slabs cannot cover them."""

    def __init__(self):
        self.c, self.signs, self.late = {}, [], []

    def later(self, x, y, z, s):
        self.late.append((x, y, z, s))

    def finish(self):
        for x, y, z, s in self.late:
            self.c[x, y, z] = s
        self.late = []

    def put(self, x, y, z, s):
        self.c[x, y, z] = s

    def box(self, x0, y0, z0, x1, y1, z1, s):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    self.c[x, y, z] = s(x, y, z) if callable(s) else s

    def sign(self, x, y, z, state, front, color='black'):
        self.c[x, y, z] = state
        self.signs.append(dict(pos=[x, y, z], front=front, color=color))


# ---------------------------------------------------------------- old danchi slab (31 x 9, 5 floors)
DIGITS = {'0': ['###', '#.#', '#.#', '#.#', '###'], '1': ['.#.', '##.', '.#.', '.#.', '###'], '2': ['###', '..#', '###', '#..', '###'],
          '3': ['###', '..#', '###', '..#', '###'], '4': ['#.#', '#.#', '###', '..#', '..#'], '5': ['###', '#..', '###', '..#', '###'],
          '6': ['###', '#..', '###', '#.#', '###'], '7': ['###', '..#', '..#', '..#', '..#'], '8': ['###', '#.#', '###', '#.#', '###'],
          '9': ['###', '#.#', '###', '..#', '###']}
SLAB_L, SLAB_D, FLOORS = 31, 9, 5
UNITS = [(1, 5, 6, 'west'), (10, 14, 9, 'east'), (16, 20, 21, 'west'), (25, 29, 24, 'east')]   # (u0, u1, door wall x, door faces)
CORES = [(7, 8), (22, 23)]


def old_concrete(x, y, z):
    v = h('dc', x, y, z) % 100
    return M('light_gray_concrete') if v < 74 else M('smooth_stone') if v < 82 else M('stone') if v < 88 else \
        M('cracked_stone_bricks') if v < 93 else M('tuff')


def danchi(b, x0, y0, z0, number, rei=False, seed=0):
    """South (balcony) face at z0+8, stair cores open on the north face z0. Floor k has its slab at y0+3k."""
    top = y0 + 3 * FLOORS
    # air inside the whole volume first, so terrain or old blocks inside are cleared
    b.box(x0, y0 + 1, z0, x0 + SLAB_L - 1, top + 3, z0 + SLAB_D - 1, AIR)
    for k in range(FLOORS + 1):
        y = y0 + 3 * k
        b.box(x0, y, z0, x0 + SLAB_L - 1, y, z0 + 7, M('light_gray_concrete') if k else M('smooth_stone'))
        b.box(x0, y, z0 + 8, x0 + SLAB_L - 1, y, z0 + 8, M('gray_concrete'))          # balcony slab and floor band
        for x in range(x0, x0 + SLAB_L):
            for z in (z0, z0 + 7):
                b.put(x, y, z, M('gray_concrete'))
        for z in range(z0, z0 + 8):
            b.put(x0, y, z, M('gray_concrete')); b.put(x0 + SLAB_L - 1, y, z, M('gray_concrete'))
        if k == FLOORS:
            break
        # stairwell: no slab over the flights (cols, z0+2..z0+4)
        for c0, c1 in CORES:
            for x in (c0, c1):
                for z in (z0 + 2, z0 + 3, z0 + 4):
                    if k > 0:
                        b.put(x0 + x, y, z, AIR)
        for dy in (1, 2):
            yy = y + dy
            for x in range(x0, x0 + SLAB_L):                                    # north and south walls
                b.put(x, yy, z0, old_concrete(x, yy, z0)); b.put(x, yy, z0 + 7, old_concrete(x, yy, z0 + 7))
            for z in range(z0, z0 + 8):                                         # gables and party walls
                for wx in (0, 6, 9, 15, 21, 24, SLAB_L - 1):
                    b.put(x0 + wx, yy, z, old_concrete(x0 + wx, yy, z))
            for wx in (6, 9, 15, 21, 24):                                       # balcony dividers
                b.put(x0 + wx, yy, z0 + 8, old_concrete(x0 + wx, yy, z0 + 8))
        for u0, u1, dwx, face in UNITS:
            unit_no = (k + 1) * 100 + UNITS.index((u0, u1, dwx, face)) + 1
            curtain = h('cur', seed, number, k, u0) % 5
            colour = None if curtain < 2 else ('white' if curtain < 4 else 'brown')
            if rei and unit_no == 402:
                colour = 'white'
            for x in range(u0 + 1, u1):                                         # south windows / balcony doors
                for dy in (1, 2):
                    b.put(x0 + x, y + dy, z0 + 7, pane(colour))
            b.put(x0 + (u0 + u1) // 2, y + 2, z0, pane())                       # small north kitchen window
            for x in range(u0, u1 + 1):                                         # balcony rail
                b.put(x0 + x, y + 1, z0 + 8, BARS)
        # stair core: landing north on even floors, south on odd floors; two columns of stairs between
        for c0, c1 in CORES:
            north = k % 2 == 0
            lz = (z0 + 1,) if north else (z0 + 5, z0 + 6)
            if k < FLOORS - 1:
                col = c0 if north else c1
                steps = [(z0 + 2, 1), (z0 + 3, 2), (z0 + 4, 3)] if north else [(z0 + 4, 1), (z0 + 3, 2), (z0 + 2, 3)]
                for z, dy in steps:
                    b.later(x0 + col, y + dy, z, stair('stone_brick_stairs', 'south' if north else 'north'))
                    if dy > 1:
                        b.later(x0 + col, y + dy - 1, z, M('stone_bricks'))
            for x in (c0, c1):
                for z in lz:
                    b.put(x0 + x, y, z, M('smooth_stone'))
            # north face of the core: open entrance on the ground floor, half wall with bars above
            for x in (c0, c1):
                if k == 0:
                    b.put(x0 + x, y + 1, z0, AIR); b.put(x0 + x, y + 2, z0, AIR)
                else:
                    b.put(x0 + x, y + 1, z0, M('light_gray_concrete')); b.put(x0 + x, y + 2, z0, BARS)
            # unit doors in the core side walls at this floor's landing
            for u0, u1, dwx, face in UNITS:
                if dwx not in (c0 - 1, c1 + 1):
                    continue
                dz = lz[0]
                unit_no = (k + 1) * 100 + UNITS.index((u0, u1, dwx, face)) + 1
                lo, up = door('iron_door', face, 'left' if face == 'west' else 'right')
                b.put(x0 + dwx, y + 1, dz, lo); b.put(x0 + dwx, y + 2, dz, up)
                if rei and unit_no == 402:
                    rei_room(b, x0, y, z0, u0, u1, dwx, dz)
    # roof: parapet and a water tank over the west core
    for x in range(x0, x0 + SLAB_L):
        for z in (z0, z0 + 8):
            b.put(x, top + 1, z, M('light_gray_concrete'))
    for z in range(z0, z0 + 9):
        b.put(x0, top + 1, z, M('light_gray_concrete')); b.put(x0 + SLAB_L - 1, top + 1, z, M('light_gray_concrete'))
    b.box(x0 + 6, top + 1, z0 + 2, x0 + 10, top + 3, z0 + 5, M('gray_concrete'))
    b.box(x0 + 7, top + 4, z0 + 3, x0 + 9, top + 4, z0 + 4, M('gray_concrete'))
    # painted block numbers on both gables (2 rows per pixel)
    digits = str(number)
    width = 4 * len(digits) - 1
    zs = z0 + (8 - width) // 2
    for i, d in enumerate(digits):
        for r, line in enumerate(DIGITS[d]):
            for cidx, ch in enumerate(line):
                if ch != '#':
                    continue
                for gx in (x0, x0 + SLAB_L - 1):
                    for dy in (0, 1):
                        b.put(gx, y0 + 12 - 2 * r - dy + 1, zs + i * 4 + cidx, M('black_concrete'))
    # foundation under the slab and its balcony row
    return (x0, z0, x0 + SLAB_L - 1, z0 + 8)


def rei_room(b, x0, y, z0, u0, u1, dwx, dz):
    """402: bare concrete, iron-pipe bed, small fridge, sink, beaker and cups, pills, the bag of bandages, the
    commander's broken glasses in their case on the chest of drawers, curtains drawn, one bare bulb."""
    X = lambda u: x0 + u
    inside = 1 if dwx < u0 else -1                                   # direction from the door into the room
    floor = M('light_gray_concrete')
    for u in range(u0, u1 + 1):
        for z in range(z0 + 1, z0 + 7):
            b.put(X(u), y, z, floor)
    north, south = z0 + 1, z0 + 6
    far = u1 if inside > 0 else u0                                   # the wall opposite the door
    near = u0 if inside > 0 else u1
    b.put(X(near), y + 1, north, M('white_concrete'))                # small fridge
    b.put(X(near + inside), y + 1, north, M('cauldron'))            # sink
    b.put(X(far), y + 1, north, M('white_bed[facing=south,occupied=false,part=head]'))
    b.put(X(far), y + 1, north + 1, M('white_bed[facing=south,occupied=false,part=foot]'))
    b.put(X(far), y + 1, north + 2, BARS)                            # iron-pipe foot rail
    b.put(X(far), y + 2, north, BARS)                                # head rail against the wall
    mid = X(near + 2 * inside)
    b.put(mid, y + 1, north, M('smooth_stone_slab[type=top,waterlogged=false]'))
    b.put(mid, y + 2, north, M('brewing_stand[has_bottle_0=true,has_bottle_1=false,has_bottle_2=true]'))
    b.put(mid + inside, y + 1, north, M('smooth_stone_slab[type=top,waterlogged=false]'))
    b.put(mid + inside, y + 2, north, M('white_candle[candles=3,lit=false,waterlogged=false]'))
    b.put(X(near), y + 1, north + 2, M('barrel[facing=up,open=false]'))       # chest of drawers
    b.put(X(near), y + 2, north + 2, M('black_carpet'))                        # the glasses case on top
    b.sign(X(near), y + 2, north + 3, wall_sign('east' if inside > 0 else 'west', 'birch'), ['眼镜盒', '碇司令的', '破眼镜', ''])
    b.put(X(far - inside), y + 1, south - 1, M('white_wool'))                  # bin bag
    b.put(X(far - inside), y + 2, south - 1, M('red_carpet'))                  # bloodied bandages on top
    b.put(X(near + 2 * inside), y + 3, north + 2, LAMP_OFF)                   # bare bulb in the ceiling
    b.put(X(near + 2 * inside), y + 2, north + 2, lever(False))
    # buttons each side of the steel door, the stuffed letterbox and the name card on the landing side
    out = dwx - inside
    b.put(X(out), y + 2, dz + 1, button('west' if inside > 0 else 'east'))          # on the landing, beside the door
    b.put(X(dwx + inside), y + 2, dz + 1, button('east' if inside > 0 else 'west'))  # inside, beside the door
    b.put(X(dwx), y + 1, dz + 1, M(f'barrel[facing={"west" if inside > 0 else "east"},open=false]'))
    b.sign(X(out), y + 3, dz + 1, wall_sign('west' if inside > 0 else 'east'), ['402', '綾波', '信箱塞满了传单', ''])


# ---------------------------------------------------------------- Comfort 17 (50 x 14, 14 floors)
C17_L, C17_D, C17_F = 50, 14, 14
C17_UNITS = [('A-1', 1, 7), ('A-2', 9, 19), ('B-1', 30, 38), ('B-2', 40, 48)]
C17_WALLS = (0, 8, 20, 29, 39, 49)


def comfort17(b, x0, y0, z0):
    """North face (z0) is the balcony side facing the city; south face carries the outdoor corridor.
    z0 balcony, z0+1 north wall, z0+2..z0+9 rooms, z0+10 south wall, z0+11..12 corridor, z0+13 parapet."""
    top = y0 + 3 * C17_F
    b.box(x0, y0 + 1, z0, x0 + C17_L - 1, top + 5, z0 + C17_D - 1, AIR)
    zN, zS, zC, zP = z0 + 1, z0 + 10, z0 + 11, z0 + 13
    for k in range(C17_F + 1):
        y = y0 + 3 * k
        b.box(x0, y, z0, x0 + C17_L - 1, y, zP, M('white_concrete') if k else M('smooth_stone'))
        b.box(x0 + 1, y, zN + 1, x0 + C17_L - 2, y, zS - 1, M('light_gray_concrete') if k else M('polished_andesite'))
        if k == C17_F:
            break
        for x in (23, 24, 25):                                               # stairwell open through every floor
            for z in (zS - 2, zS - 1):
                if k > 0:
                    b.put(x0 + x, y, z, AIR)
        for dy in (1, 2):
            yy = y + dy
            for x in range(x0, x0 + C17_L):
                b.put(x, yy, zN, M('light_gray_concrete')); b.put(x, yy, zS, M('light_gray_concrete'))
            for z in range(zN, zS + 1):
                for wx in C17_WALLS:
                    b.put(x0 + wx, yy, z, M('light_gray_concrete'))
            for wx in C17_WALLS[1:-1]:
                b.put(x0 + wx, yy, z0, M('light_gray_concrete'))              # balcony dividers
        for x in range(x0, x0 + C17_L):
            b.put(x, y + 1, z0, PANE if k else AIR)                            # glass balcony front
            b.put(x, y + 1, zP, M('light_gray_concrete'))                      # corridor parapet
        b.put(x0, y + 1, z0, M('light_gray_concrete')); b.put(x0 + C17_L - 1, y + 1, z0, M('light_gray_concrete'))
        for name, u0, u1 in C17_UNITS:
            for x in range(u0 + 1, u1):                                        # big windows to the balcony
                for dy in (1, 2):
                    b.put(x0 + x, y + dy, zN, PANE)
            if k == 0:
                continue
            for x in (u1 - 2, u1 - 1):                                        # small corridor windows
                b.put(x0 + x, y + 2, zS, PANE)
            if name == 'A-2' and k == 10:
                apartment_11a2(b, x0, y, z0, u0, u1, zN, zS)
            else:
                lo, up = door('iron_door', 'north')
                b.put(x0 + u0 + 2, y + 1, zS, lo); b.put(x0 + u0 + 2, y + 2, zS, up)
        # core: elevator shaft (shut) and a switchback stair along x, landing west on even floors, east on odd
        b.box(x0 + 24, y + 1, zN + 1, x0 + 27, y + 2, zN + 4, M('gray_concrete'))
        b.box(x0 + 25, y + 1, zN + 2, x0 + 26, y + 2, zN + 3, AIR)
        lo, up = door('iron_door', 'south')
        b.put(x0 + 25, y + 1, zN + 4, lo); b.put(x0 + 25, y + 2, zN + 4, up)
        if k < C17_F - 1:
            row = zS - 1 if k % 2 == 0 else zS - 2
            xs = [(23, 1), (24, 2), (25, 3)] if k % 2 == 0 else [(25, 1), (24, 2), (23, 3)]
            for x, dy in xs:
                b.later(x0 + x, y + dy, row, stair('smooth_quartz_stairs', 'east' if k % 2 == 0 else 'west'))
                if dy > 1:
                    b.later(x0 + x, y + dy - 1, row, M('smooth_quartz'))
        for x in (21, 22, 26, 27):                                             # doorways from the corridor
            b.put(x0 + x, y + 1, zS, AIR); b.put(x0 + x, y + 2, zS, AIR)
    # ground floor entrance from the road side and the lobby name
    for x in (21, 22):
        b.put(x0 + x, y0 + 1, zN, AIR); b.put(x0 + x, y0 + 2, zN, AIR)
    lo, up = door('dark_oak_door', 'north')
    b.put(x0 + 21, y0 + 1, zN, lo); b.put(x0 + 21, y0 + 2, zN, up)
    lo, up = door('dark_oak_door', 'north', 'right')
    b.put(x0 + 22, y0 + 1, zN, lo); b.put(x0 + 22, y0 + 2, zN, up)
    b.put(x0 + 23, y0 + 2, zN, M('light_gray_concrete'))
    b.sign(x0 + 23, y0 + 2, z0, wall_sign('north', 'dark_oak'), ['コンフォート17', 'COMFORT 17', '', ''], color='white')
    # roof parapet and the stair/elevator penthouse
    for x in range(x0, x0 + C17_L):
        b.put(x, top + 1, z0, M('light_gray_concrete')); b.put(x, top + 1, zP, M('light_gray_concrete'))
    for z in range(z0, zP + 1):
        b.put(x0, top + 1, z, M('light_gray_concrete')); b.put(x0 + C17_L - 1, top + 1, z, M('light_gray_concrete'))
    b.box(x0 + 21, top + 1, zN, x0 + 28, top + 4, zS, M('light_gray_concrete'))
    b.box(x0 + 21, top + 5, zN, x0 + 28, top + 5, zS, M('white_concrete'))
    return (x0, z0, x0 + C17_L - 1, zP)


A2_PLAN = ['LLLLLL#MMMM',
           'LLLLLLdMMMM',
           'LLLLLL#MMMM',
           'KKKKKKh####',
           'KKKKKKhdAAA',
           '##d##dh#AAA',
           'SSS#BBh#AAA',
           'SSS#BBG#AAA']


def apartment_11a2(b, x0, y, z0, u0, u1, zN, zS):
    """Misato's apartment, after the plan registered in the atlas: entrance and corridor, kitchen-dining open to the
    living room and balcony, Misato's (messy), Asuka's and Shinji's rooms, the bathroom, Pen Pen's fridge."""
    X = lambda u: x0 + u0 + u
    Z = lambda v: zN + 1 + v
    floors = {'B': M('white_concrete'), 'S': M('oak_planks'), 'A': M('birch_planks'), 'M': M('oak_planks')}
    for v, row in enumerate(A2_PLAN):
        for u, ch in enumerate(row):
            x, z = X(u), Z(v)
            b.put(x, y, z, floors.get(ch, M('spruce_planks')))
            if ch == '#':
                b.put(x, y + 1, z, M('white_concrete')); b.put(x, y + 2, z, M('white_concrete'))
            elif ch == 'd':
                lo, up = door('oak_door', {(6, 1): 'east', (7, 4): 'east'}.get((u, v), 'south'))
                b.put(x, y + 1, z, lo); b.put(x, y + 2, z, up)
    # entrance door from the corridor at the genkan
    gu = A2_PLAN[7].index('G')
    lo, up = door('dark_oak_door', 'north')
    b.put(X(gu), y + 1, zS, lo); b.put(X(gu), y + 2, zS, up)
    b.sign(X(gu) + 1, y + 2, zS + 1, wall_sign('south'), ['11-A-2', '葛城', '碇・惣流', ''])
    # living room: TV on its stand, low table, cushions
    b.put(X(0), y + 1, Z(1), M('dark_oak_slab[type=top,waterlogged=false]')); b.put(X(0), y + 2, Z(1), M('black_concrete'))
    b.put(X(3), y + 1, Z(1), M('spruce_slab[type=bottom,waterlogged=false]'))
    b.put(X(2), y + 1, Z(1), M('orange_carpet')); b.put(X(4), y + 1, Z(1), M('light_blue_carpet'))
    # kitchen-dining: stove, sink, the tall fridge, Pen Pen's fridge, the table with beer cans
    b.put(X(0), y + 1, Z(3), M('furnace[facing=east,lit=false]'))
    b.put(X(0), y + 1, Z(4), M('cauldron'))
    b.put(X(5), y + 1, Z(3), M('white_concrete')); b.put(X(5), y + 2, Z(3), M('white_concrete'))
    b.put(X(4), y + 1, Z(4), M('light_blue_concrete'))
    b.sign(X(4), y + 2, Z(4), M('birch_sign[rotation=8,waterlogged=false]'), ['Pen Pen', '的冰箱', '', ''])
    b.put(X(2), y + 1, Z(3), M('spruce_slab[type=top,waterlogged=false]')); b.put(X(3), y + 1, Z(3), M('spruce_slab[type=top,waterlogged=false]'))
    b.put(X(2), y + 2, Z(3), M('yellow_candle[candles=3,lit=false,waterlogged=false]'))
    b.put(X(3), y + 2, Z(3), M('yellow_candle[candles=4,lit=false,waterlogged=false]'))
    b.put(X(1), y + 1, Z(3), stair('oak_stairs', 'west')); b.put(X(4), y + 1, Z(3), stair('oak_stairs', 'east'))
    # Misato's room: bed, cans and clothes on the floor
    b.put(X(10), y + 1, Z(0), M('red_bed[facing=east,occupied=false,part=head]'))
    b.put(X(9), y + 1, Z(0), M('red_bed[facing=east,occupied=false,part=foot]'))
    for u, v, s in ((7, 1, M('yellow_candle[candles=2,lit=false,waterlogged=false]')), (9, 2, M('yellow_candle[candles=1,lit=false,waterlogged=false]')),
                    (8, 2, M('purple_carpet')), (10, 2, M('black_carpet')), (7, 0, M('white_carpet'))):
        b.put(X(u), y + 1, Z(v), s)
    # Asuka's room: bed, desk, rug
    b.put(X(10), y + 1, Z(7), M('pink_bed[facing=north,occupied=false,part=foot]'))
    b.put(X(10), y + 1, Z(6), M('pink_bed[facing=north,occupied=false,part=head]'))
    b.put(X(8), y + 1, Z(7), M('birch_slab[type=top,waterlogged=false]')); b.put(X(9), y + 1, Z(5), M('red_carpet'))
    # Shinji's small room: futon and the cello standing in the corner
    b.put(X(0), y + 1, Z(6), M('light_blue_carpet')); b.put(X(0), y + 1, Z(7), M('light_blue_carpet'))
    b.put(X(2), y + 1, Z(7), M('stripped_spruce_wood[axis=y]')); b.put(X(2), y + 2, Z(7), M('spruce_fence[east=false,north=false,south=false,waterlogged=false,west=false]'))
    b.sign(X(1), y + 1, Z(7), M('birch_sign[rotation=0,waterlogged=false]'), ['大提琴', '', '', ''])
    # bathroom: tub and basin
    b.put(X(4), y + 1, Z(6), M('water_cauldron[level=3]')); b.put(X(4), y + 1, Z(7), M('water_cauldron[level=3]'))
    b.put(X(5), y + 1, Z(7), M('water_cauldron[level=1]'))
    # ceiling lamps, all on (only this home is lit at night), each with its lever
    for u, v in ((2, 0), (2, 4), (8, 1), (9, 5), (1, 6), (5, 6), (6, 4)):
        b.put(X(u), y + 3, Z(v), LAMP_ON); b.put(X(u), y + 2, Z(v), lever(True))


# ---------------------------------------------------------------- sites
def construction_site(b, x0, z0, x1, z1, gy):
    """Fenced site with a pit, a pile driver, a tower crane, rebar and a site office."""
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            edge = x in (x0, x1) or z in (z0, z1)
            if edge:
                b.put(x, gy + 1, z, M('white_concrete')); b.put(x, gy + 2, z, M('white_concrete'))
                b.put(x, gy + 3, z, BARS if (x + z) % 2 else M('white_concrete'))
    gx0, gz0, gx1, gz1 = x0 + 3, z0 + 8, x1 - 3, z0 + 26                  # the pit
    for x in range(gx0, gx1 + 1):
        for z in range(gz0, gz1 + 1):
            for y in range(gy - 3, gy + 1):
                b.put(x, y, z, AIR)
            b.put(x, gy - 4, z, M('gravel'))
            if (x - gx0) % 4 == 1 and (z - gz0) % 4 == 1:
                for y in range(gy - 3, gy + 1):
                    b.put(x, y, z, BARS)                                    # rebar starts
    # pile driver: crawler base, tall leader and the hammer
    px, pz = x0 + 5, z0 + 3
    b.box(px - 1, gy + 1, pz - 1, px + 1, gy + 1, pz + 1, M('yellow_concrete'))
    b.put(px - 1, gy + 1, pz - 1, M('black_concrete')); b.put(px + 1, gy + 1, pz + 1, M('black_concrete'))
    for y in range(gy + 2, gy + 20):
        b.put(px, y, pz, M('iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]') if y % 3 else M('yellow_concrete'))
    b.put(px, gy + 9, pz + 1, M('anvil[facing=north]')); b.put(px, gy + 20, pz, M('yellow_concrete'))
    # tower crane: lattice mast, jib over the pit, counterweight
    cx, cz = x1 - 4, z1 - 6
    H = 34
    for y in range(gy + 1, gy + H):
        for dx, dz in ((0, 0), (1, 0), (0, 1), (1, 1)):
            b.put(cx + dx, y, cz + dz, M('yellow_concrete') if (dx + dz + y) % 2 == 0 else BARS)
    for z in range(cz - 22, cz + 7):
        b.put(cx, gy + H, z, M('yellow_concrete')); b.put(cx + 1, gy + H, z, BARS)
    b.box(cx, gy + H - 2, cz + 5, cx + 1, gy + H - 1, cz + 6, M('gray_concrete'))
    b.box(cx - 1, gy + H - 3, cz - 1, cx + 2, gy + H - 1, cz, M('white_concrete'))          # cab
    for y in range(gy + H - 8, gy + H):
        b.put(cx, y, cz - 16, M('chain[axis=y,waterlogged=false]'))
    # site office and stacked materials
    b.box(x0 + 2, gy + 1, z1 - 5, x0 + 8, gy + 3, z1 - 2, M('white_concrete'))
    b.box(x0 + 3, gy + 1, z1 - 4, x0 + 7, gy + 2, z1 - 3, AIR)
    b.put(x0 + 5, gy + 2, z1 - 5, PANE)
    lo, up = door('iron_door', 'south'); b.put(x0 + 4, gy + 1, z1 - 2, lo); b.put(x0 + 4, gy + 2, z1 - 2, up)
    b.box(x1 - 9, gy + 1, z0 + 2, x1 - 7, gy + 1, z0 + 4, M('stripped_spruce_log[axis=z]'))
    b.box(x1 - 5, gy + 1, z0 + 2, x1 - 4, gy + 2, z0 + 3, M('iron_block'))


def bus_stop(b, x, gy, z, facing='east'):
    b.put(x, gy + 1, z, M('stone_brick_wall[east=none,north=none,south=none,up=true,waterlogged=false,west=none]'))
    b.put(x, gy + 2, z, M('stone_brick_wall[east=none,north=none,south=none,up=true,waterlogged=false,west=none]'))
    b.put(x, gy + 3, z, M('light_gray_concrete'))
    b.sign(x + (1 if facing == 'east' else -1), gy + 3, z, wall_sign(facing, 'birch'), ['仙石高原', 'SENGOKU-KŌGEN', '箱根登山バス', ''])
    b.put(x, gy + 1, z + 2, stair('spruce_stairs', facing))
    b.put(x, gy + 1, z + 3, stair('spruce_stairs', facing))


# ---------------------------------------------------------------- planning
SOFT = ('short_grass', 'tall_grass', 'fern', 'leaves', 'log', 'flower', 'poppy', 'dandelion', 'bush', 'sapling', 'vine', 'snow[', 'moss_carpet')


def ground_y(w, x, z, lo=40, hi=240):
    for y in range(hi, lo, -1):
        s = w.get(x, y, z)
        if s and not s.endswith(':air') and not any(k in s for k in SOFT):
            return y
    return None


def writable(cur, demolish):
    if cur is None:
        return False
    if is_open(cur) or any(k in cur for k in SOFT):
        return True
    natural = ('grass_block', 'dirt', 'coarse_dirt', 'stone', 'gravel', 'moss_block', 'rooted_dirt', 'podzol', 'andesite', 'diorite',
               'granite', 'tuff', 'deepslate', 'sand', 'clay', 'mud', 'cobblestone', 'mossy_cobblestone')
    if cur.split('[')[0].split(':')[-1] in natural:
        return True
    return demolish


def pad(b, w, box, gy, margin=2, keep=()):
    """Level a building pad: cut terrain above gy, fill below, grass on the open margin; trees over the pad go whole,
    and the edge of a cut or a fill is faced with stone bricks so no bare earth wall is left."""
    x0, z0, x1, z1 = box
    for x in range(x0 - margin - 1, x1 + margin + 2):
        for z in range(z0 - margin - 1, z1 + margin + 2):
            g = ground_y(w, x, z) or gy
            inside = x0 <= x <= x1 and z0 <= z <= z1
            ring = not (x0 - margin <= x <= x1 + margin and z0 - margin <= z <= z1 + margin)
            for y in range(gy + 1, gy + 30):
                s = w.get(x, y, z) or ''
                if 'leaves' in s or '_log' in s:
                    b.c.setdefault((x, y, z), AIR)
            if ring:
                if g > gy:
                    for y in range(gy + 1, g + 1):
                        b.c.setdefault((x, y, z), M('stone_bricks'))
                    for y in range(g + 1, g + 3):
                        s = w.get(x, y, z) or ''
                        if any(k in s for k in SOFT):
                            b.c.setdefault((x, y, z), AIR)
                continue
            for y in range(gy + 1, max(g, gy) + 6):
                b.c.setdefault((x, y, z), AIR)
            edge = not inside and (x in (x0 - margin, x1 + margin) or z in (z0 - margin, z1 + margin))
            for y in range(min(g, gy) + 1 if g < gy else gy, gy):
                b.c.setdefault((x, y, z), M('stone') if inside else M('stone_bricks') if edge else M('dirt'))
            b.c.setdefault((x, gy, z), M('smooth_stone') if inside else M('grass_block[snowy=false]'))


def plan(site, out):
    w = World(REGION)
    gs = guards()
    b = Build()
    report = dict(site=site)
    demolish_boxes = []
    if site == 'rei':
        slabs = [(-201, 498, 1), (-201, 513, 2), (-201, 528, 3)]
        for x0, z0, n in slabs:
            box = (x0, z0, x0 + SLAB_L - 1, z0 + 8)
            ys = sorted(ground_y(w, x, z) for x in range(box[0], box[2] + 1) for z in range(box[1], box[3] + 1))
            gy = ys[len(ys) // 2]
            pad(b, w, box, gy)
            danchi(b, x0, gy, z0, n, rei=(n == 2), seed=n)
            report[f'slab{n}'] = dict(box=box, floor_y=gy, ground_min=ys[0], ground_max=ys[-1])
        sx0, sz0, sx1, sz1 = -140, 500, -118, 545
        ys = sorted(ground_y(w, x, z) for x in range(sx0, sx1 + 1) for z in range(sz0, sz1 + 1))
        gy = ys[len(ys) // 2]
        pad(b, w, (sx0, sz0, sx1, sz1), gy, margin=0)
        construction_site(b, sx0, sz0, sx1, sz1, gy)
        report['site'] = dict(box=[sx0, sz0, sx1, sz1], ground_y=gy, ground_min=ys[0], ground_max=ys[-1])
        gy = ground_y(w, -168, 553)
        bus_stop(b, -168, gy, 553, facing='east')
        report['bus_stop'] = [-168, gy, 553]
    elif site == 'comfort':
        x0, z0 = -66, 768
        box = (x0, z0, x0 + C17_L - 1, z0 + C17_D - 1)
        ys = sorted(ground_y(w, x, z) for x in range(box[0], box[2] + 1) for z in range(box[1], box[3] + 1))
        # the lobby floor sits one above the road kerb in front of the entrance
        front = [ground_y(w, x0 + 21, z) for z in range(z0 - 6, z0)]
        gy = max(front[0], ys[len(ys) // 2] - 2)
        pad(b, w, box, gy, margin=3)
        for z in range(z0 - 6, z0):                                          # path from the road to the doors
            for x in (x0 + 20, x0 + 21, x0 + 22, x0 + 23):
                g = ground_y(w, x, z)
                b.c[x, gy, z] = M('polished_andesite')
                for y in range(min(g, gy) + 1, gy):
                    b.c[x, y, z] = M('stone')
                for y in range(gy + 1, max(g, gy) + 3):
                    b.c[x, y, z] = AIR
        comfort17(b, x0, gy, z0)
        report['comfort17'] = dict(box=box, lobby_floor_y=gy, ground_min=ys[0], ground_max=ys[-1], entrance=[x0 + 21.5, gy + 1, z0 - 1],
                                   unit_11a2_floor_y=gy + 30)
    elif site == 'kirisato':
        old = [(-2878, -1112), (-2790, -1112), (-2702, -1112), (-2878, -1016), (-2790, -1016), (-2702, -1016)]   # measured: 75 x 21, y 70..115
        n = 1
        for ox, oz in old:
            obox = (ox, oz, ox + 74, oz + 20)
            ring = [ground_y(w, x, z) for x in range(obox[0] - 3, obox[2] + 4, 4) for z in (obox[1] - 3, obox[3] + 3)]
            gy = sorted(ring)[len(ring) // 2]
            demolish_boxes.append(obox)
            top = 0
            for x in range(obox[0], obox[2] + 1):
                for z in range(obox[1], obox[3] + 1):
                    for y in range(gy + 1, gy + 60):
                        s = w.get(x, y, z)
                        if s and not s.endswith(':air'):
                            b.c.setdefault((x, y, z), AIR); top = max(top, y)
                    s = w.get(x, gy, z) or ''
                    if not any(k in s for k in ('grass_block', 'dirt', 'path')):
                        b.c.setdefault((x, gy, z), M('grass_block[snowy=false]'))
            for dx in (2, 42):
                danchi(b, ox + dx, gy, oz + 6, n, seed=100 + n)
                n += 1
            report[f'old_{ox}_{oz}'] = dict(box=obox, ground_y=gy, old_top=top)
    b.finish()
    rows, refused, refused_at = [], Counter(), []
    def in_demolition(x, z):
        return any(a <= x <= c and bz <= z <= d for a, bz, c, d in demolish_boxes)
    for (x, y, z), want in b.c.items():
        cur = w.get(x, y, z)
        if cur is None or cur == want:
            continue
        if not writable(cur, in_demolition(x, z)):
            refused['occupied'] += 1; refused_at.append([x, y, z, cur, want]); continue
        try:
            for g in gs:
                g.assert_positions([(x, y, z)])
        except ValueError:
            refused['protected'] += 1; refused_at.append([x, y, z, cur, want, 'protected']); continue
        if w.block_entity(x, y, z) and not in_demolition(x, z):
            refused['block entity'] += 1; refused_at.append([x, y, z, cur, want, 'be']); continue
        rows.append([x, y, z, cur, want])
    written = {(r[0], r[1], r[2]) for r in rows}
    signs = [s for s in b.signs if tuple(s['pos']) in written or w.get(*s['pos']) == b.c[tuple(s['pos'])]]
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (Path(out) / 'signs.json').write_text(json.dumps(signs, ensure_ascii=False, indent=1), 'utf8')
    (Path(out) / 'refused.json').write_text(json.dumps(refused_at), 'utf8')
    report.update(rows=len(rows), signs=len(signs), refused=dict(refused))
    (Path(out) / 'report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False), 'utf8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    plan(sys.argv[1], sys.argv[2])
