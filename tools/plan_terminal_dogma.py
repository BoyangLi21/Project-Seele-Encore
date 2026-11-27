"""Plan the R64 Terminal Dogma changes (D1-D3) as write_deep_cells rows and signs, read-only on a world copy.

D1  Heaven's Door: an antechamber in the old void behind the chamber's north wall on the cross's axis, reached
    from the retained B lift via a west-side approach, and a 25 x 29 gate in the north wall with its two leaves left ajar; the 7-wide gap
    lines up with the crucifix and Lilith.  Original blocks only.
D2  The grey kiosk inside the chamber next to the porch (x 16..30, z 262..277) goes; the gallery floor continues.
D5  The cross arms move up six blocks to meet Lilith's palms at her new scale (the scale itself is entity data,
    written with write_entity_fields.py).
D3  The LCL lake is deepened to 14 blocks under the unchanged surface (the leg-like growths stay just above it,
    as in the TV series where the lake pools below the cross); a tiled bed at the bottom.
The B lift is retained. The old X12 porch and direct gallery approach are retired.  write_deep_cells runs the lift,
launch and city protection checks when the rows are written.

    plan_terminal_dogma.py --world W --out DIR      (writes DIR/rows.json, DIR/signs.json, DIR/summary.json)
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from write_deep_cells import REGION, read_chunk, decode

AIR = 'minecraft:air'
FLOOR = 'projectseele:nerv_floor_panel'
WALL = 'projectseele:nerv_structural_panel'
FRAME = 'minecraft:polished_basalt[axis=y]'
LINTEL = 'minecraft:polished_basalt[axis=x]'
RED = 'minecraft:red_concrete'
BAND = 'minecraft:black_concrete'
BOLT = 'minecraft:iron_block'
LAMP = 'minecraft:sea_lantern'
GUIDE = 'minecraft:red_terracotta'
DECK = 'minecraft:gray_concrete'
BED = 'minecraft:deepslate_tiles'

# geometry (world coordinates)
ANTE_X = (15, 45)            # shell, interior 16..44
ANTE_Z = (239, 257)          # north shell at 239; the chamber's north wall (z 258..260) closes the south side
ANTE_Y = (-1231, -1198)      # floor and ceiling
WALL_Z = (258, 260)
GATE_X = (18, 42)
GATE_Y = (-1230, -1202)
GAP_X = (27, 33)
FRAME_X = (16, 17, 43, 44)
LINTEL_Y = (-1201, -1199)
KIOSK = dict(x=(16, 30), z=(262, 277), y=(-1230, -1224))
LCL_SURFACE = -1265
LCL_FLOOR_OLD = -1266
LCL_NEW_BOTTOM = -1279
BED_Y = -1280
LCL_BOX = dict(x=(-34, 94), z=(262, 392))
PROTECTED = ('red_concrete',)        # the crucifix passes through the lake floor
# D5: at the measured scale 1.95 Lilith's nailed palms sit 3 blocks in from the arm ends, 39.6 blocks above her
# anchor (y -1264), so the arms move up six blocks to meet them; her growths stay above the lake
CROSS_Z = (352, 355)
BEAM_X = (27, 33)
ARM_X = (-2, 62)
ARMS_OLD_Y = (-1233, -1228)
ARMS_NEW_Y = (-1227, -1222)


class Cells:
    """Full block states of a world copy, one decoded section at a time."""

    def __init__(self, world):
        self.world = Path(world)
        self.regions, self.sections = {}, {}

    def get(self, x, y, z):
        key = (x >> 4, y >> 4, z >> 4)
        if key not in self.sections:
            rk = (x >> 9, z >> 9)
            if rk not in self.regions:
                self.regions[rk] = (self.world / REGION / f'r.{rk[0]}.{rk[1]}.mca').read_bytes()
            root = read_chunk(self.regions[rk], x >> 4, z >> 4)[3]
            for s in root['sections']:
                if 'block_states' in s:
                    self.sections[(x >> 4, int(s['Y']), z >> 4)] = decode(s['block_states'])
            self.sections.setdefault(key, None)
        sec = self.sections[key]
        if sec is None:
            return AIR
        ids, palette = sec
        return palette[ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]]


def inside(v, lo_hi):
    return lo_hi[0] <= v <= lo_hi[1]


def leaf_block(x, y, z):
    if x in (GAP_X[0] - 1, GAP_X[1] + 1):
        return RED                                   # leading edges of the two leaves
    if -1217 <= y <= -1215:
        return BAND
    face = z in WALL_Z
    if face and y in (-1227, -1206) and x in (20, 24, 36, 40):
        return BOLT
    return WALL


def gate_approach():
    """Retire the X12 porch and take the existing B lift to the west side of Heaven's Door."""
    want = {}
    for x in range(-32, 16):
        for z in range(257, 262):
            infill = BED
            if z == 257:
                infill = 'minecraft:stone'
            elif z == 261:
                infill = AIR
            for y in range(-1231, -1225):
                want[x, y, z] = infill
            if z == 261:
                want[x, -1231, z] = DECK
    for x in range(8, 16):
        for z in range(250, 258):
            for y in range(-1231, -1224):
                want[x, y, z] = 'minecraft:stone'
        for z in range(258, 261):
            for y in range(-1233, -1224):
                want[x, y, z] = BED
    for x in range(9, 32):
        for z in range(261, 278):
            if x > 15 and z < 270:
                continue
            want[x, -1231, z] = DECK
            for y in range(-1230, -1224):
                want[x, y, z] = AIR
    for z in range(239, 258):
        for y in range(-1230, -1197):
            want[15, y, z] = WALL
        want[15, -1231, z] = FLOOR
    # The lift exits south. Turn north outside the shaft, then run east into the antechamber.
    inside = {(x, z) for x in range(-42, -32) for z in range(258, 261)}
    inside |= {(x, z) for x in range(-35, -32) for z in range(245, 261)}
    inside |= {(x, z) for x in range(-35, 16) for z in range(245, 248)}
    shell = {(x + dx, z + dz) for x, z in inside for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
    for x, z in shell:
        # Keep the native B landing, including its south door, call and sign.
        if (x < -38 and z >= 257) or x == 16:
            continue
        ceiling_light = (z == 246 and x % 8 == 0) or (x == -34 and z % 8 == 0)
        for y in range(-1231, -1225):
            state = WALL
            if (x, z) in inside:
                if y == -1231:
                    state = FLOOR
                elif y == -1226:
                    state = LAMP if ceiling_light else WALL
                else:
                    state = AIR
            want[x, y, z] = state
    return want


def plan(world):
    w = Cells(world)
    want = {}

    # D1 antechamber
    for x in range(ANTE_X[0], ANTE_X[1] + 1):
        for z in range(ANTE_Z[0], ANTE_Z[1] + 1):
            for y in range(ANTE_Y[0], ANTE_Y[1] + 1):
                shell = x in ANTE_X or z == ANTE_Z[0] or y in ANTE_Y
                if not shell:
                    want[x, y, z] = AIR
                elif y == ANTE_Y[0]:
                    want[x, y, z] = GUIDE if x in (30, 31) and z > ANTE_Z[0] else FLOOR
                elif y == ANTE_Y[1]:
                    lamp = (x - 16) % 7 == 0 and (z - 241) % 6 == 0 and x not in ANTE_X and z != ANTE_Z[0]
                    want[x, y, z] = LAMP if lamp else WALL
                else:
                    want[x, y, z] = WALL

    # D1 gate in the north wall
    for x in range(FRAME_X[0], FRAME_X[-1] + 1):
        for z in range(WALL_Z[0], WALL_Z[1] + 1):
            for y in range(GATE_Y[0] - 1, LINTEL_Y[1] + 1):
                if y == GATE_Y[0] - 1:
                    want[x, y, z] = GUIDE if x in (30, 31) else (FLOOR if inside(x, GATE_X) else FRAME)
                elif inside(y, LINTEL_Y):
                    want[x, y, z] = RED if y == LINTEL_Y[0] else LINTEL
                elif x in FRAME_X:
                    want[x, y, z] = FRAME
                elif inside(x, GAP_X):
                    want[x, y, z] = AIR
                else:
                    want[x, y, z] = leaf_block(x, y, z)

    # D2 kiosk
    for x in range(KIOSK['x'][0], KIOSK['x'][1] + 1):
        for z in range(KIOSK['z'][0], KIOSK['z'][1] + 1):
            for y in range(KIOSK['y'][0], KIOSK['y'][1] + 1):
                if w.get(x, y, z).split('[')[0] != AIR:
                    want[x, y, z] = AIR

    # D3 deeper lake under the existing surface
    lcl_state = None
    columns = 0
    for x in range(LCL_BOX['x'][0], LCL_BOX['x'][1] + 1):
        for z in range(LCL_BOX['z'][0], LCL_BOX['z'][1] + 1):
            top = w.get(x, LCL_SURFACE, z)
            if not top.startswith('projectseele:lcl'):
                continue
            columns += 1
            if lcl_state is None:
                lcl_state = w.get(x, LCL_FLOOR_OLD, z)
            for y in range(LCL_NEW_BOTTOM, LCL_FLOOR_OLD):
                if not any(p in w.get(x, y, z) for p in PROTECTED):
                    want[x, y, z] = 'projectseele:lcl[level=0]'
            # A later basin pass can deepen this column below the R64 bed.
            existing_bed = w.get(x, BED_Y, z)
            if not existing_bed.startswith('projectseele:lcl') and not any(p in existing_bed for p in PROTECTED):
                want[x, BED_Y, z] = BED

    # D5 cross arms up six blocks (the upright stays)
    for x in range(ARM_X[0], ARM_X[1] + 1):
        if inside(x, BEAM_X):
            continue
        for z in range(CROSS_Z[0], CROSS_Z[1] + 1):
            for y in range(ARMS_OLD_Y[0], ARMS_OLD_Y[1] + 1):
                if not inside(y, ARMS_NEW_Y):
                    want[x, y, z] = AIR
            for y in range(ARMS_NEW_Y[0], ARMS_NEW_Y[1] + 1):
                want[x, y, z] = RED

    want[30, LINTEL_Y[1], WALL_Z[1] + 1] = 'minecraft:dark_oak_wall_sign[facing=south,waterlogged=false]'
    want[30, LINTEL_Y[1], WALL_Z[0] - 1] = 'minecraft:dark_oak_wall_sign[facing=north,waterlogged=false]'

    want.update(gate_approach())
    rows, kinds, skipped = [], Counter(), Counter()
    for (x, y, z), after in sorted(want.items()):
        before = w.get(x, y, z)
        if before == after:
            continue
        if 'lift' in before or 'elevator' in before or 'sign' in before:
            skipped[before.split('[')[0]] += 1
            continue
        rows.append([x, y, z, before, after])
        kinds[after.split('[')[0]] += 1
    signs = [dict(pos=[30, LINTEL_Y[1], WALL_Z[1] + 1], front=['', "HEAVEN'S DOOR", 'ヘブンズドア', ''],
                  back=['', '', '', ''], color='white', glow=True),
             dict(pos=[30, LINTEL_Y[1], WALL_Z[0] - 1], front=['', "HEAVEN'S DOOR", 'TERMINAL DOGMA', ''],
                  back=['', '', '', ''], color='white', glow=True)]
    return rows, signs, dict(rows=len(rows), by_block=dict(kinds), skipped=dict(skipped), lake_columns=columns,
                             old_lcl_state=lcl_state)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    rows, signs, summary = plan(a.world)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'rows.json').write_text(json.dumps(rows, ensure_ascii=False), 'utf8')
    (a.out / 'signs.json').write_text(json.dumps(signs, ensure_ascii=False, indent=1), 'utf8')
    (a.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
