"""The south residential lift (R65 owner feedback round 2, items 22, 25 and 31): the 80-block staircase by the South
Residential station becomes a four-stop personnel lift, glass landing doors like the headquarters lifts.

  python south_residential_lift.py <out dir>

Reads BUILDINGS_WORLD. Writes rows.json (only cells that change; the controllers and the cabin panel carry their
Moving Elevators block entities as a sixth item), public_lifts_r65.json (the world-root file the R65 public lift code
reads) and report.json.

The staircase room is x 150-158, z 760-776 (walls x 149/159, z 759/777), floor y 80, top floor y 160.
- Shaft x 150-156, z 765-771 from the pit floor y 79 to a cap at y 166 (one above the pavilion roof, so the car's roof
  has room at the top stop); car 5 x 6 x 5 at x 151-155, z 766-770; controllers in x 150, z 768, facing east.
- Stops: y 81 (the old bottom, out through the east tunnel), y 95 (the old station's west platform, floor y 94),
  y 106 (the old station's roof, y 105, where the through line's eastbound platform joins it), y 161 (the hilltop
  pavilion, out south to its door).
- 95 and 106: a hall x 157-158 cut out of the fill, an opening in the room wall x 159 and a covered walkway over the
  open trench x 160-162 (ground y 90). At 95 the walkway runs north along the trench to z 759-761, where the station's
  west glass has no waiting room behind it, and opens into the platform; at 106 it steps straight onto the roof.
- The rest of the room: the bottom hall y 81-84 stays open with a ceiling at y 85, y 86-159 filled solid, the top hall
  floor closed over the old stair opening and its railing removed.
The car is written at the y 81 stop.
"""
import json, sys
from collections import Counter
from pathlib import Path
from mca import REGION, World
from float_fix import guards

AIR = 'minecraft:air'
SHAFT = 'projectseele:nerv_shaft_panel'
FLOORP = 'projectseele:nerv_floor_panel'
STATION_FLOOR = 'projectseele:period_station_floor'
CEILING = 'minecraft:light_gray_concrete'
FILL = 'minecraft:stone'
CAR_FLOOR = 'minecraft:polished_deepslate'          # the cabin floor the lift code recognises
CAR_WALL = 'projectseele:nerv_machine_edge'
CAR_ROOF = 'minecraft:smooth_quartz'
CAR_LIGHT = 'minecraft:sea_lantern'
LANDING_DOOR = 'minecraft:gray_stained_glass'
CABIN_DOOR = 'minecraft:light_gray_stained_glass'
CONTROLLER = 'movingelevators:elevator_block[facing=east]'
BUTTON = 'minecraft:polished_blackstone_button[face=wall,facing={},powered=false]'

ROOM = (150, 158, 760, 776)
ENCL = (150, 156, 765, 771)
CAR = (151, 155, 766, 770)
CX, CZ = 153, 768                 # cabin centre
CTRL_X = 150
PIT, CAP = 61, 166
START = 81
LIFT_ID = 'r65-public-south-residential'
STOPS = [
    dict(y=81, label='南部住宅区 东口通道', exit='east', color=3),
    dict(y=95, label='南部住宅区站 ホーム', exit='east', color=1),
    dict(y=106, label='直通線ホーム (屋上)', exit='east', color=1),
    dict(y=161, label='南部住宅区 山顶', exit='south', color=3),
]
GLASS = 'projectseele:clear_glass'
ROOF = 'minecraft:light_gray_concrete'
LAMP = 'minecraft:sea_lantern'


def inside(box, x, z):
    return box[0] <= x <= box[1] and box[2] <= z <= box[3]


def landing_doors(stop):
    y = stop['y']
    if stop['exit'] == 'east':
        return [(156, y + dy, z) for dy in range(3) for z in (767, 768, 769)]
    return [(x, y + dy, 771) for dy in range(3) for x in (152, 153, 154)]


def cabin_doors(stop):
    y = stop['y']
    if stop['exit'] == 'east':
        return [(155, y + dy, z) for dy in range(3) for z in (767, 768, 769)]
    return [(x, y + dy, 770) for dy in range(3) for x in (152, 153, 154)]


def call(stop):
    y = stop['y']
    if stop['exit'] == 'east':
        return (157, y + 1, 766), 'east'
    return (151, y + 1, 772), 'south'


def plan(two_stop=False):
    stops = [s for s in STOPS if not (two_stop and s['y'] == 63)]
    pit = min(s['y'] for s in stops) - 2
    c, entities = {}, {}
    put = lambda p, s: c.__setitem__(p, s)
    # the staircase room outside the shaft
    for x in range(ROOM[0], ROOM[1] + 1):
        for z in range(ROOM[2], ROOM[3] + 1):
            if inside(ENCL, x, z):
                continue
            put((x, 80, z), STATION_FLOOR)
            for y in range(81, 85):
                put((x, y, z), AIR)
            put((x, 85, z), CEILING)
            for y in range(86, 160):
                put((x, y, z), FILL)
            put((x, 160, z), STATION_FLOOR)
            for y in range(161, 165):
                put((x, y, z), AIR)
    # the shaft: walls, pit floor, cap, clear travel space
    for x in range(ENCL[0], ENCL[1] + 1):
        for z in range(ENCL[2], ENCL[3] + 1):
            put((x, pit, z), SHAFT)
            put((x, CAP, z), SHAFT)
            for y in range(pit + 1, CAP):
                put((x, y, z), AIR if inside(CAR, x, z) else SHAFT)
    # the platform stop (95) and the roof stop (106): a hall east of the shaft cut out of the fill, an opening in the room
    # wall x 159, and a covered walkway over the open trench x 160-162 (ground y 90) to the station
    for y0 in [s['y'] for s in stops if s['y'] in (95, 106)]:
        fl, top = y0 - 1, y0 + 3
        for x in (157, 158):
            for z in range(766, 771):
                put((x, fl, z), FLOORP)
                for y in range(y0, top):
                    put((x, y, z), AIR)
        for z in (767, 768, 769):
            for y in range(y0, top):
                put((159, y, z), AIR)
        zs = range(758, 771) if y0 == 95 else range(766, 771)   # 95 turns north to the open platform at z 759-761
        for x in (160, 161, 162):
            for z in zs:
                put((x, fl, z), STATION_FLOOR)
                for y in range(y0, top):
                    put((x, y, z), GLASS if z in (zs[0], zs[-1]) else AIR)
                put((x, top, z), LAMP if (x, z) in ((161, 768), (161, 762)) else ROOF)
        if y0 == 95:
            for z in (759, 760, 761):                     # into the station through its west glass, door height
                for y in (95, 96):
                    put((163, y, z), AIR)
    # landing hall at the y 63 stop
    for x in ((157, 158) if any(s['y'] == 63 for s in stops) else ()):
        for z in range(765, 772):
            put((x, 62, z), FLOORP)
            for y in range(63, 67):
                put((x, y, z), AIR)
    floors = []
    for i, s in enumerate(stops):
        y = s['y']
        ctrl = (CTRL_X, y, CZ)
        put(ctrl, CONTROLLER)
        name = s['label'].replace('"', '')
        entities[ctrl] = {'id': 'movingelevators:elevator_tile',
                          'snbt': '{data: {camoState: {Name: "minecraft:black_concrete"}, showButtons: 0b, hasName: 1b, '
                                  f'color: {s["color"]}, name: "{name}", facing: 3, redstone: 0b}}}}'}
        for p in landing_doors(s):
            put(p, LANDING_DOOR)
        pos, facing = call(s)
        put(pos, BUTTON.format(facing))
        floors.append(dict(label=s['label'], cabin=[CX, y, CZ], exit=s['exit'], approach_y=y, controller=list(ctrl),
                           calls=[dict(kind='vanilla_button', position=list(pos), state=BUTTON.format(facing), facing=facing,
                                       target_controller=list(ctrl))],
                           restricted=False,
                           landing_doors=[dict(pos=list(p), closed_state=LANDING_DOOR) for p in landing_doors(s)],
                           cabin_doors=[dict(pos=list(p), closed_state=CABIN_DOOR) for p in cabin_doors(s)]))
    # the car, at the y 81 stop
    y0 = START
    start_ctrl = (CTRL_X, y0, CZ)
    for x in range(CAR[0], CAR[1] + 1):
        for z in range(CAR[2], CAR[3] + 1):
            put((x, y0 - 1, z), CAR_FLOOR)
            put((x, y0 + 4, z), CAR_LIGHT if (x, z) == (CX, CZ) else CAR_ROOF)
            edge = x in (CAR[0], CAR[1]) or z in (CAR[2], CAR[3])
            for y in range(y0, y0 + 4):
                put((x, y, z), CAR_WALL if edge else AIR)
    for s in stops:                                   # both door sides travel with the car
        for (x, dy, z) in [(p[0], p[1] - s['y'], p[2]) for p in cabin_doors(s)]:
            put((x, y0 + dy, z), CABIN_DOOR)
    button, display = (CX - 2, y0 + 1, CZ), (CX - 2, y0 + 2, CZ)
    put(button, 'movingelevators:button_block')
    put(display, 'movingelevators:display_block')
    entities[button] = {'id': 'movingelevators:button_tile',
                        'snbt': '{data: {camoState: {Name: "minecraft:black_concrete"}, '
                                f'controllerX: {start_ctrl[0]}, controllerY: {start_ctrl[1]}, controllerZ: {start_ctrl[2]}, '
                                'facing: 5, controllerFacing: 3, redstone: 0b}}'}
    entities[display] = {'id': 'movingelevators:display_tile', 'snbt': '{data: {camoState: {Name: "minecraft:black_concrete"}}}'}
    manifest = dict(schema='projectseele.r65.public-lifts.v1',
                    lifts=[dict(id=LIFT_ID, controller_side='west', controller_facing='east',
                                inside_button_offset=[-2, 1, 0], inside_display_offset=[-2, 2, 0], floors=floors)])
    return c, entities, manifest


def main(out, two_stop=False):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    c, entities, manifest = plan(two_stop)
    w = World(REGION)
    gs = guards()
    rows, kinds, carried = [], Counter(), []
    for (x, y, z), want in sorted(c.items()):
        cur = w.get(x, y, z)
        if cur is None:
            raise SystemExit(f'{x},{y},{z} not generated')
        e = entities.get((x, y, z))
        if cur == want and e is None:
            continue
        if want == AIR and cur.split('[')[0].endswith('air'):
            continue
        if w.block_entity(x, y, z) and e is None:    # an existing lift block is only rewritten with its new entity
            carried.append([x, y, z, cur])
        row = [x, y, z, cur, want] + ([e] if e else [])
        rows.append(row)
        kinds[(cur.split('[')[0].split(':')[-1], want.split('[')[0].split(':')[-1])] += 1
    for g in gs:
        g.assert_positions([tuple(r[:3]) for r in rows])
    if carried:
        raise SystemExit(f'{len(carried)} cells carry a block entity: {carried[:5]}')
    (out / 'rows.json').write_text(json.dumps(rows, ensure_ascii=False), 'utf8')
    (out / 'public_lifts_r65.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), 'utf8')
    xs, ys, zs = zip(*[r[:3] for r in rows])
    rep = dict(rows=len(rows), entities=len(entities), box=[min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)],
               kinds=[[a, b, n] for (a, b), n in kinds.most_common(25)], lift=LIFT_ID, stops=[f['approach_y'] for f in manifest['lifts'][0]['floors']])
    (out / 'report.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), 'utf8')
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1], '--two-stop' in sys.argv)
