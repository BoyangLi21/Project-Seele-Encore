"""R65 owner feedback 2, item 42: the old glass stair shaft at x -191..-175, z 81..97 goes, a card lift to the hanging
city takes its place, and the scraps around it are cleared.

  python hanging_city_lift.py <out dir>

Reads BUILDINGS_WORLD. Writes rows.json (the old shaft and scrap cells inside city lift spaces are in it:
write with --item42-city-lift-obstructions), public_lifts_r65.json (the world-root file with this lift added) and report.json.

The old shaft ran from the surface down through the GeoFront roof to a floor at y -112, where the hanging city's
walkway (polished deepslate, iron rails, z 74-78) starts. All of it goes: in the GeoFront air it becomes air, in the
rock and the roof armour each cell takes the material the rock beside the shaft has at that height, near the surface
the ground is rebuilt to the height of the ground round it (grass on top). The short walkway stub that led into the old
shaft from the west goes too and the walkway's rail is closed there.

The new lift is an ordinary public lift (public_lifts_r65.json), two stops, both opening north:
- shaft x -186..-180, z 82..88 (7 x 7, light grey concrete with grey glass bands where it is seen), car x -185..-181,
  z 83..87, controllers in x -186, z 85 facing east; pit floor y -113, cap y 74;
- stop y 69 on the surface and y -111 at the walkway; at each a hall x -187..-179, z 79..81 in front of the landing
  doors (x -184..-182 in the shaft's north wall z 82), the call button beside them;
- the hall's north wall z 78 holds two NERV staff gate lanes: x -184 a card lane into the hall, x -182 a free lane out,
  so nobody without a card reaches the call button and nobody is shut in. Below, that wall stands in the walkway's south
  rail.
The scraps (a floating slab road edge and its deepslate wall along x -195/-194, a dead road stub at z 116-124, two
floating slabs with benches) go; a road block lying on the ground becomes grass.
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
WALL = 'minecraft:light_gray_concrete'
BAND = 'minecraft:gray_stained_glass'
PIT = 'projectseele:nerv_shaft_panel'
FLOOR = 'minecraft:polished_deepslate'
HALL_FLOOR = 'minecraft:smooth_stone'
LAMP = 'minecraft:sea_lantern'
RAIL = 'minecraft:iron_bars'
CAR_FLOOR = 'minecraft:polished_deepslate'
CAR_WALL = 'projectseele:nerv_machine_edge'
CAR_ROOF = 'minecraft:smooth_quartz'
LANDING_DOOR = 'minecraft:gray_stained_glass'
CABIN_DOOR = 'minecraft:light_gray_stained_glass'
CONTROLLER = 'movingelevators:elevator_block[facing=east]'
BUTTON = 'minecraft:polished_blackstone_button[face=wall,facing=north,powered=false]'
GATE = 'projectseele:nerv_staff_gate[card={card},facing={facing},half={half},open=false]'

OLD = (-191, -175, 81, 97)
OLD_Y = (-112, 86)
ENCL = (-186, -180, 82, 88)
CAR = (-185, -181, 83, 87)
CX, CZ, CTRL_X = -183, 85, -186
PIT_Y, CAP_Y = -113, 74
HALL = (-187, -179, 79, 81)               # inside; walls x -188 / -178, gate wall z 78, roof over all
DOOR_X = (-184, -183, -182)
CARD_LANE, EXIT_LANE = -184, -182
STOPS = [dict(y=-111, label='倒挂城市 空中走廊', color=1), dict(y=69, label='地面 (旧玻璃井)', color=3)]
LIFT_ID = 'r65-public-hanging-city'
CALLS = []
STUB = (-196, -192, 79, 86)                # walkway spur into the old shaft
SCRAPS = [((-195, -194), (0, 114), (74, 80)),            # slab deck + deepslate wall
          ((-162, -142), (80, 107), (82, 83)),           # floating L slab, benches
          ((-144, -120), (129, 155), (83, 84))]          # floating cross slab, benches
ROAD_STUB = ((-221, -194), (116, 124), 80)
# the old shaft's south-east corner and two of the scraps stand in city lift spaces (original96/66 lowered, raised and
# hatch; original96/2 raised); these cells may only be cleared, and only from these blocks
OBSTRUCTIONS = [((-179, -175), (-8, 85), (91, 97)), ((-162, -142), (82, 83), (80, 107)), ((-144, -120), (83, 84), (129, 155))]
OBSTRUCTION_BLOCKS = {'light_gray_concrete', 'gray_stained_glass', 'polished_deepslate', 'iron_bars', 'smooth_stone',
                      'oak_stairs', 'stone_brick_stairs'}


def in_obstruction(x, y, z):
    return any(xa <= x <= xb and ya <= y <= yb and za <= z <= zb for (xa, xb), (ya, yb), (za, zb) in OBSTRUCTIONS)


def inside(box, x, z):
    return box[0] <= x <= box[1] and box[2] <= z <= box[3]


def band(y):
    return y % 8 in (0, 1, 2) and (y <= 22 or y >= 69)     # only where the shaft is seen from outside


class Plan(B.Plan):
    pass


def ring_material(w):
    """For each y the material of the rock round the old shaft (2-wide ring outside it); air where the ring is air."""
    x0, x1, z0, z1 = OLD
    out = {}
    for y in range(OLD_Y[0], OLD_Y[1] + 1):
        c = Counter()
        for x in range(x0 - 2, x1 + 3):
            for z in range(z0 - 2, z1 + 3):
                if inside(OLD, x, z):
                    continue
                s = w.get(x, y, z)
                n = B.name(s)
                if B.is_air(s) or n in B.PLANTS or B.is_leaf(s) or B.is_log(s) or n == 'water':
                    c['air'] += 1
                elif B.is_solid_ground(s) or n == 'nerv_structural_panel':
                    c[s] += 1
                else:
                    c['built'] += 1
        solid = [(k, v) for k, v in c.items() if k not in ('air', 'built')]
        out[y] = AIR if c['air'] > sum(c.values()) / 2 or not solid else max(solid, key=lambda kv: kv[1])[0]
    return out


ROOF_EDGE = (18, 30)


def nearest_ring(w, x, z, y):
    x0, x1, z0, z1 = OLD
    options = sorted([(x - x0 + 1, (x0 - 1, z)), (x1 - x + 1, (x1 + 1, z)), (z - z0 + 1, (x, z0 - 1)), (z1 - z + 1, (x, z1 + 1))])
    for _, (rx, rz) in options:
        s = w.get(rx, y, rz)
        if B.is_air(s) or B.is_solid_ground(s) or B.name(s) == 'nerv_structural_panel':
            return AIR if B.is_air(s) else s
    return AIR


def ground_top(w, x, z):
    for y in range(OLD_Y[1], 40, -1):
        s = w.get(x, y, z)
        if s is None:
            return None
        n = B.name(s)
        if B.is_solid_ground(s):
            return y
        if not (B.is_air(s) or n in B.PLANTS or B.is_leaf(s) or B.is_log(s)):
            return None
    return None


def surface(w):
    """Ground height over the old outline, blended from the ground just outside it on all four sides."""
    x0, x1, z0, z1 = OLD
    def edge(points):
        hs = [ground_top(w, x, z) for x, z in points]
        hs = [h for h in hs if h is not None]
        return sum(hs) / len(hs) if hs else None
    out = {}
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            west = edge([(x0 - 1, z), (x0 - 2, z)]); east = edge([(x1 + 1, z), (x1 + 2, z)])
            north = edge([(x, z0 - 1), (x, z0 - 2)]); south = edge([(x, z1 + 1), (x, z1 + 2)])
            tx = (west * (x1 + 1 - x) + east * (x - x0 + 1)) / (x1 - x0 + 2)
            tz = (north * (z1 + 1 - z) + south * (z - z0 + 1)) / (z1 - z0 + 2)
            out[x, z] = round((tx + tz) / 2)
    return out


def old_shaft(plan, w):
    mat = ring_material(w)
    top = surface(w)
    x0, x1, z0, z1 = OLD
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            plan.zone.add((x, z)); plan.keepout.add((x, z))
            h = top[x, z]
            for y in range(OLD_Y[0], OLD_Y[1] + 1):
                if y > h:
                    want = AIR
                elif y == h:
                    want = GRASS
                elif y >= h - 3:
                    want = DIRT
                elif ROOF_EDGE[0] <= y <= ROOF_EDGE[1]:
                    want = nearest_ring(w, x, z, y)    # the uneven underside of the roof: copy the nearest rock beside
                else:
                    want = mat[y]
                plan.put((x, y, z), want, 'old shaft')
    # the walkway spur that led into it, and the rail closed across its mouth
    sx0, sx1, sz0, sz1 = STUB
    for x in range(sx0, sx1 + 1):
        for z in range(sz0, sz1 + 1):
            for y in range(-112, -108):
                plan.put((x, y, z), AIR, 'walkway spur')
    for x in range(sx0 + 1, sx1 + 1):
        plan.put((x, -111, 78), RAIL, 'walkway spur')
    return mat, top


def shaft(plan, entities):
    x0, x1, z0, z1 = ENCL
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            edge = not inside(CAR, x, z)
            plan.put((x, PIT_Y, z), PIT, 'lift shaft')
            plan.put((x, CAP_Y, z), WALL, 'lift shaft')
            for y in range(PIT_Y + 1, CAP_Y):
                plan.put((x, y, z), (BAND if band(y) and (x in (x0, x1) or z in (z0, z1)) and not (z == z0) else WALL) if edge else AIR,
                         'lift shaft')
    floors = []
    for s in STOPS:
        y = s['y']
        ctrl = (CTRL_X, y, CZ)
        plan.put(ctrl, CONTROLLER, 'lift shaft')
        entities[ctrl] = {'id': 'movingelevators:elevator_tile',
                          'snbt': '{data: {camoState: {Name: "minecraft:black_concrete"}, showButtons: 0b, hasName: 1b, '
                                  f'color: {s["color"]}, name: "{s["label"]}", facing: 3, redstone: 0b}}}}'}
        landing = [(x, y + dy, z0) for dy in range(3) for x in DOOR_X]
        cabin = [(x, y + dy, CAR[2]) for dy in range(3) for x in DOOR_X]
        for p in landing:
            plan.put(p, LANDING_DOOR, 'lift shaft')
        call = (DOOR_X[0] - 1, y + 1, z0 - 1)
        CALLS.append(call)                     # placed after the hall is built (halls() clears its inside)
        floors.append(dict(label=s['label'], cabin=[CX, y, CZ], exit='north', approach_y=y, controller=list(ctrl),
                           calls=[dict(kind='vanilla_button', position=list(call), state=BUTTON, facing='north',
                                       target_controller=list(ctrl))],
                           restricted=False,
                           landing_doors=[dict(pos=list(p), closed_state=LANDING_DOOR) for p in landing],
                           cabin_doors=[dict(pos=list(p), closed_state=CABIN_DOOR) for p in cabin]))
    # the car, at the surface stop
    y0 = STOPS[-1]['y']
    for x in range(CAR[0], CAR[1] + 1):
        for z in range(CAR[2], CAR[3] + 1):
            plan.put((x, y0 - 1, z), CAR_FLOOR, 'lift car')
            plan.put((x, y0 + 4, z), LAMP if (x, z) == (CX, CZ) else CAR_ROOF, 'lift car')
            e = x in (CAR[0], CAR[1]) or z in (CAR[2], CAR[3])
            for y in range(y0, y0 + 4):
                plan.put((x, y, z), CAR_WALL if e else AIR, 'lift car')
    for x in DOOR_X:
        for dy in range(3):
            plan.put((x, y0 + dy, CAR[2]), CABIN_DOOR, 'lift car')
    button, display = (CX - 2, y0 + 1, CZ), (CX - 2, y0 + 2, CZ)
    plan.put(button, 'movingelevators:button_block', 'lift car')
    plan.put(display, 'movingelevators:display_block', 'lift car')
    entities[button] = {'id': 'movingelevators:button_tile',
                        'snbt': '{data: {camoState: {Name: "minecraft:black_concrete"}, '
                                f'controllerX: {CTRL_X}, controllerY: {y0}, controllerZ: {CZ}, '
                                'facing: 5, controllerFacing: 3, redstone: 0b}}'}
    entities[display] = {'id': 'movingelevators:display_tile', 'snbt': '{data: {camoState: {Name: "minecraft:black_concrete"}}}'}
    return dict(id=LIFT_ID, controller_side='west', controller_facing='east',
                inside_button_offset=[-2, 1, 0], inside_display_offset=[-2, 2, 0], floors=floors)


def halls(plan, entities):
    hx0, hx1, hz0, hz1 = HALL
    for s in STOPS:
        y = s['y']
        fl, roof = y - 1, y + 3
        surface_stop = y > 0
        for x in range(hx0 - 1, hx1 + 2):
            for z in range(hz0 - 1, hz1 + 1):            # z 78..81 (the shaft wall z 82 is the back)
                plan.put((x, fl, z), HALL_FLOOR if surface_stop else FLOOR, 'lift hall')
                plan.put((x, roof, z), LAMP if (x, z) == (CX, 80) else WALL, 'lift hall')
                wall = x in (hx0 - 1, hx1 + 1) or z == hz0 - 1
                for yy in range(y, roof):
                    if not wall:
                        plan.put((x, yy, z), AIR, 'lift hall')
                    elif z == hz0 - 1 and x in (CARD_LANE, EXIT_LANE) and yy < y + 2:
                        card = 'true' if x == CARD_LANE else 'false'
                        facing = 'south' if x == CARD_LANE else 'north'
                        half = 'lower' if yy == y else 'upper'
                        plan.put((x, yy, z), GATE.format(card=card, facing=facing, half=half), 'staff gates')
                        if half == 'lower':
                            entities[(x, yy, z)] = {'id': 'projectseele:nerv_staff_gate', 'snbt': '{}'}
                    else:
                        plan.put((x, yy, z), WALL if yy == y else BAND, 'lift hall')
            if surface_stop:
                for z in range(hz0 - 1, hz1 + 1):
                    for yy in range(fl - 4, fl):
                        if B.is_air(plan.get(x, yy, z)) or B.name(plan.get(x, yy, z)) in B.PLANTS:
                            plan.put((x, yy, z), STONE, 'lift hall')
    # in front of the surface gates: a level pad of grass, the ground beyond eased down to it
    y = STOPS[-1]['y']
    for x in range(hx0 - 1, hx1 + 2):
        for z in range(hz0 - 5, hz0 - 1):
            plan.zone.add((x, z)); plan.keepout.add((x, z))
            plan.put((x, y - 1, z), GRASS, 'hall approach')
            for yy in range(y, y + 6):
                if not B.is_air(plan.get(x, yy, z)):
                    plan.put((x, yy, z), AIR, 'hall approach')
            for yy in range(y - 5, y - 1):
                if B.is_air(plan.get(x, yy, z)) or B.name(plan.get(x, yy, z)) in B.PLANTS:
                    plan.put((x, yy, z), DIRT, 'hall approach')


def grade_surface(plan, w):
    """Ground round the surface hall and its pad eased to the hall floor: at distance d its top lies within floor +- d."""
    y_floor = STOPS[-1]['y'] - 1
    hx0, hx1, hz0, hz1 = HALL
    box = (hx0 - 1, hx1 + 1, hz0 - 5, hz1)             # hall walls and pad
    for x in range(box[0] - 6, box[1] + 7):
        for z in range(box[2] - 6, box[3] + 1):
            if box[0] <= x <= box[1] and box[2] <= z <= box[3]:
                continue
            if inside(OLD, x, z) or inside(ENCL, x, z):
                continue
            d = max(box[0] - x, x - box[1], box[2] - z, z - box[3], 0)
            lo, hi = y_floor - d, y_floor + d
            if B.built_between(w, x, z, y_floor - 8, y_floor + 12):
                continue
            plan.zone.add((x, z))
            top = B.top_solid(plan, x, z, y_floor + 14, y_floor - 10)
            if top > hi:
                for y in range(hi + 1, y_floor + 15):
                    t = plan.get(x, y, z)
                    if t and B.is_ground(t) and not B.is_log(t) and not B.is_leaf(t):
                        plan.put((x, y, z), AIR, 'hall grading')
                plan.put((x, hi, z), GRASS, 'hall grading')
            elif top < lo:
                for y in range(top, lo):
                    plan.put((x, y, z), DIRT, 'hall grading')
                plan.put((x, lo, z), GRASS, 'hall grading')
                for y in range(lo + 1, lo + 3):
                    if B.name(plan.get(x, y, z)) in B.PLANTS:
                        plan.put((x, y, z), AIR, 'hall grading')
    for call in CALLS:
        plan.put(call, BUTTON, 'lift hall')


def scraps(plan, w):
    for (xa, xb), (za, zb), (ya, yb) in SCRAPS:
        for x in range(xa, xb + 1):
            for z in range(za, zb + 1):
                for y in range(ya, yb + 1):
                    s = w.get(x, y, z)
                    if s and not B.is_air(s) and not B.is_ground(s) and B.name(s) != 'water':
                        plan.put((x, y, z), AIR, 'scraps')
    (xa, xb), (za, zb), y = ROAD_STUB
    for x in range(xa, xb + 1):
        for z in range(za, zb + 1):
            s = w.get(x, y, z)
            if s and not B.is_air(s) and not B.is_ground(s):
                plan.put((x, y, z), GRASS if B.is_solid_ground(w.get(x, y - 1, z)) else AIR, 'road stub')
                for yy in range(y + 1, y + 4):
                    t = w.get(x, yy, z)
                    if t and not B.is_air(t) and not B.is_ground(t):
                        plan.put((x, yy, z), AIR, 'road stub')


def main(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    w = World(REGION)
    plan = Plan(w)
    entities = {}
    mat, top = old_shaft(plan, w)
    lift = shaft(plan, entities)
    halls(plan, entities)
    grade_surface(plan, w)
    scraps(plan, w)
    trees = B.trees(plan) if plan.zone else {}
    rows = []
    for (x, y, z), want in sorted(plan.want.items()):
        cur = w.get(x, y, z)
        if cur is None:
            raise SystemExit(f'{x},{y},{z} not generated')
        e = entities.get((x, y, z))
        if cur == want and e is None:
            continue
        if w.block_entity(x, y, z) and e is None and not B.is_air(cur):
            raise SystemExit(f'{x},{y},{z} {cur} carries a block entity')
        rows.append([x, y, z, cur, want] + ([e] if e else []))
    protected = set()
    for g in guards():
        if hasattr(g, 'inside'):
            protected |= g.inside([tuple(r[:3]) for r in rows])
    # cells in a city lift's space: only old shaft and scrap blocks going to air (write_deep_cells
    # --item42-city-lift-obstructions checks the same boxes and blocks); anything else there stops the run
    held = [r for r in rows if tuple(r[:3]) in protected]
    bad = [r for r in held if not (in_obstruction(*r[:3]) and B.name(r[3]) in OBSTRUCTION_BLOCKS and r[4] == AIR)]
    if bad:
        raise SystemExit(f'{len(bad)} rows change a city lift space beyond the old shaft and scraps: {bad[:3]}')
    for g in guards():
        g.assert_positions([tuple(r[:3]) for r in rows if tuple(r[:3]) not in protected])
    from mca import WORLD
    manifest = json.loads((Path(WORLD) / 'public_lifts_r65.json').read_text('utf8'))
    manifest['lifts'] = [l for l in manifest['lifts'] if l['id'] != LIFT_ID] + [lift]
    (out / 'rows.json').write_text(json.dumps(rows, ensure_ascii=False), 'utf8')
    (out / 'public_lifts_r65.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), 'utf8')
    xs, ys, zs = zip(*[r[:3] for r in rows])
    kinds = Counter((B.name(r[3]), B.name(r[4])) for r in rows)
    rep = dict(rows=len(rows), entities=len(entities), in_city_lift_space=len(held),
               parts=dict(plan.parts), trees=trees, box=[min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)],
               rock=sorted(Counter(mat.values()).items()), lifts=[l['id'] for l in manifest['lifts']],
               kinds=[[a, b, n] for (a, b), n in kinds.most_common(30)])
    (out / 'report.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), 'utf8')
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1])
