"""R65 owner feedback 2, item 44: two runways heading north from the GeoFront underground airport's apron, so J-16s can
take off and land.

  python geofront_runways.py <out dir>

Reads BUILDINGS_WORLD. Writes rows.json and report.json.

The apron is x -530..-350, z -350..-190, grey concrete at y -476, forest to the north. Runways 36L (x -490..-471) and
36R (x -430..-411) run from the apron's north edge (z -351) to z -800, 20 wide and 450 long, their surface at the apron's
height: grey concrete, a white centre line of 6-block dashes every 12, white threshold stripes over the last 8 blocks at
each end, sea lanterns flush in both edges every 10 blocks. Under the runway the ground is filled with stone.

One clearing covers both runways and 10 columns on their outer sides (x -500..-401): the ground top there is grass at
y -476, nothing above it. Beyond the clearing, within 6 columns, the ground is eased towards the clearing (at distance d its top
lies within -476 +- d). Trees that lose ground or stand in a clearing are handled whole (buried_fix.trees): moved down
onto the new ground, or removed when they stand in a clearing; leaves of trees beside a clearing that hang over
it are trimmed. The apron, its crew kiosk and the J-16 stands are not in
any of these columns; nothing built is ever removed.
"""
import json, sys
from collections import Counter
from pathlib import Path
from mca import REGION, World
from float_fix import guards
import buried_fix as B

AIR = 'minecraft:air'
GRASS = 'minecraft:grass_block[snowy=false]'
DIRT = 'minecraft:dirt'
STONE = 'minecraft:stone'
SURFACE = 'minecraft:gray_concrete'
PAINT = 'minecraft:white_concrete'
LIGHT = 'minecraft:sea_lantern'

TOP = -476
Z_START, Z_END = -351, -800          # apron edge side, far end
CENTRES = {'36L': -480, '36R': -420}  # runway x = c-10 .. c+9
HALF, CLEAR, BLEND = 10, 20, 6
APRON = (-530, -350, -350, -190)
SCAN_UP, SCAN_DOWN = 30, 14


def runway_cell(x, z):
    for name, c in CENTRES.items():
        if c - HALF <= x <= c + HALF - 1 and Z_END <= z <= Z_START:
            return name, c
    return None


def mark(x, z, c):
    """Surface block of a runway cell."""
    off = x - c                          # -10 .. 9
    if off in (-HALF, HALF - 1) and (z - Z_END) % 10 == 0:
        return LIGHT
    end = z - Z_END < 8 or Z_START - z < 8
    if end and off not in (-HALF, HALF - 1) and (off + HALF) % 3 != 2:
        return PAINT
    if off in (-1, 0) and (Z_START - z) % 12 < 6 and not end:
        return PAINT
    return SURFACE


def ground_top(plan, x, z):
    return B.top_solid(plan, x, z, TOP + SCAN_UP, TOP - SCAN_DOWN)


def main(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    w = World(REGION)
    plan = B.Plan(w)
    skipped = Counter()
    xs_all = range(min(CENTRES.values()) - CLEAR - BLEND, max(CENTRES.values()) + CLEAR + BLEND)
    for x in xs_all:
        for z in range(Z_END - BLEND, Z_START + 1):
            if APRON[0] <= x <= APRON[1] and APRON[2] <= z <= APRON[3]:
                continue
            cx0, cx1 = min(CENTRES.values()) - CLEAR, max(CENTRES.values()) + CLEAR - 1   # one field over both runways
            d = max(cx0 - x, x - cx1, 0)
            d = max(d, Z_END - z if z < Z_END else 0)
            if d > BLEND:
                continue
            if B.built_between(w, x, z, TOP - SCAN_DOWN, TOP + SCAN_UP):
                skipped['built'] += 1
                continue
            plan.zone.add((x, z))
            rw = runway_cell(x, z)
            top = ground_top(plan, x, z)
            if d == 0:
                plan.keepout.add((x, z))
                lo = hi = TOP
            else:
                lo, hi = TOP - d, TOP + d
            # cut what rises above the allowed top (plants and solid ground; trees are handled whole later)
            if top > hi or d == 0:
                for y in range(hi + 1, TOP + SCAN_UP + 1):
                    s = w.get(x, y, z)
                    if s is not None and B.is_ground(s) and not B.is_log(s) and not B.is_leaf(s):
                        plan.put((x, y, z), AIR, 'cut')
            new_top = min(max(top, lo), hi)
            if rw:
                for y in range(top + 1 if top < TOP else TOP - 3, TOP):
                    plan.put((x, y, z), STONE, 'runway base')
                plan.put((x, TOP, z), mark(x, z, rw[1]), 'runway')
                continue
            if top < lo:
                for y in range(top + 1, new_top):
                    plan.put((x, y, z), DIRT, 'fill')
                if B.name(w.get(x, top, z)) == 'grass_block':
                    plan.put((x, top, z), DIRT, 'fill')
                for y in range(new_top + 1, new_top + 3):
                    if B.name(w.get(x, y, z)) in B.PLANTS:
                        plan.put((x, y, z), AIR, 'fill')
            if new_top != top or d == 0:
                plan.put((x, new_top, z), GRASS, 'clearing' if d == 0 else 'blend')
    trees = B.trees(plan, TOP - SCAN_DOWN, TOP + SCAN_UP)
    # leaves of trees beside a clearing that hang over it are trimmed (a cut forest edge, nothing over the shoulders)
    trimmed = 0
    for x, z in plan.keepout:
        for y in range(TOP + 1, TOP + SCAN_UP + 1):
            s = plan.get(x, y, z)
            if s is not None and B.is_leaf(s):
                plan.put((x, y, z), AIR, 'edge trim')
                trimmed += 1
    trees['leaves trimmed over clearings'] = trimmed
    water = sum(1 for p in plan.want for q in [(p[0] + 1, p[1], p[2]), (p[0] - 1, p[1], p[2]), (p[0], p[1], p[2] + 1),
                                                (p[0], p[1], p[2] - 1), (p[0], p[1] + 1, p[2])]
                if B.name(w.get(*q)) in ('water', 'lava') and q not in plan.want)
    rows = []
    for (x, y, z), want in sorted(plan.want.items()):
        cur = w.get(x, y, z)
        if cur is None:
            raise SystemExit(f'{x},{y},{z} not generated')
        if cur == want:
            continue
        if w.block_entity(x, y, z):
            raise SystemExit(f'{x},{y},{z} {cur} carries a block entity')
        rows.append([x, y, z, cur, want])
    for g in guards():
        g.assert_positions([tuple(r[:3]) for r in rows])
    (out / 'rows.json').write_text(json.dumps(rows), 'utf8')
    xs, ys, zs = zip(*[r[:3] for r in rows])
    kinds = Counter((B.name(r[3]), B.name(r[4])) for r in rows)
    rep = dict(rows=len(rows), parts=dict(plan.parts), trees=trees, skipped=dict(skipped), water_next_to_change=water,
               box=[min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)],
               kinds=[[a, b, n] for (a, b), n in kinds.most_common(25)])
    (out / 'report.json').write_text(json.dumps(rep, indent=1), 'utf8')
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
