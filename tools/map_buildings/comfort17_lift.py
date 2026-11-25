"""The Comfort 17 lift (R65 owner request after feedback round 2): Misato's building gets a personnel lift, glass
landing doors like the South Residential one, stopping at the lobby and every residential floor (11F is 11-A-2).

  python comfort17_lift.py <out dir> [--two-stop]

--two-stop: the South Residential lift in the shared file without its y 63 stop.

Reads BUILDINGS_WORLD. Writes rows.json (controllers and the cabin panel carry their Moving Elevators block entities),
public_lifts_r65.json (BOTH public lifts: the South Residential one from south_residential_lift.py and this one; it
replaces that lift's file in the writer's queue) and report.json.

Comfort 17 (canon_homes.py): x0 -66, z0 768, lobby floor y 132, floor k slab at 132 + 3k (feet 133 + 3k), 14 floors,
roof y 174, stair/lift penthouse x -45..-38, y 175-179. The core between the A-2 and B-1 walls is x -45..-38,
z 770-777: the old shut shaft (2 x 2, x -42..-39, z 770-773), the switchback stair in z 776-777 at x -43..-41, corridor
doorways at z 778 (x -45/-44 and x -40/-39), the lobby doors at x -45/-44 in the north wall.
- Shaft x -43..-37, z 769-775 (the north wall and the B-1 party wall are its outer walls), car x -42..-38, z 770-774,
  controllers in x -43, z 772 facing east. Walls keep their concrete where it is already solid.
- Landing doors 2 wide in the shaft's south wall at x -40/-39, facing the corridor doorway; floors are 2 blocks high,
  so the doors are 2 high. Call button beside them at x -38. The car is written at the lobby.
"""
import json, sys
from collections import Counter
from pathlib import Path
from mca import REGION, World
from float_fix import guards
import south_residential_lift as SR

AIR = 'minecraft:air'
WALL = 'minecraft:light_gray_concrete'
SOLID_KEEP = ('light_gray_concrete', 'white_concrete', 'gray_concrete', 'smooth_stone', 'polished_andesite', 'stone')
CAR_FLOOR = 'minecraft:polished_deepslate'
CAR_WALL = 'minecraft:white_concrete'
CAR_ROOF = 'minecraft:smooth_quartz'
CAR_LIGHT = 'minecraft:sea_lantern'
LANDING_DOOR = 'minecraft:gray_stained_glass'
CABIN_DOOR = 'minecraft:light_gray_stained_glass'
CONTROLLER = 'movingelevators:elevator_block[facing=east]'
BUTTON = 'minecraft:polished_blackstone_button[face=wall,facing=south,powered=false]'

ENCL = (-43, -37, 769, 775)
CAR = (-42, -38, 770, 774)
CX, CZ = -40, 772
CTRL_X = -43
LOBBY_FLOOR = 132
FLOORS = 14
BOTTOM, CAP = 131, 177             # pit floor under the lobby car floor; cap inside the penthouse
DOOR_X = (-40, -39)
LIFT_ID = 'r65-public-comfort17'


def stops():
    out = []
    for k in range(FLOORS):
        label = '1F ロビー / 大堂' if k == 0 else '11F 葛城 (11-A-2)' if k == 10 else f'{k + 1}F'
        out.append(dict(y=LOBBY_FLOOR + 1 + 3 * k, label=label, color=1 if k == 0 else 3))
    return out


def inside(box, x, z):
    return box[0] <= x <= box[1] and box[2] <= z <= box[3]


def plan(w):
    c, entities = {}, {}
    for x in range(ENCL[0], ENCL[1] + 1):
        for z in range(ENCL[2], ENCL[3] + 1):
            for y in range(BOTTOM, CAP + 1):
                if inside(CAR, x, z) and BOTTOM < y < CAP:
                    c[x, y, z] = AIR
                else:
                    cur = (w.get(x, y, z) or '').split('[')[0].split(':')[-1]
                    c[x, y, z] = 'minecraft:' + cur if cur in SOLID_KEEP else WALL
    floors = []
    for s in stops():
        y = s['y']
        ctrl = (CTRL_X, y, CZ)
        c[ctrl] = CONTROLLER
        entities[ctrl] = {'id': 'movingelevators:elevator_tile',
                          'snbt': '{data: {camoState: {Name: "minecraft:black_concrete"}, showButtons: 0b, hasName: 1b, '
                                  f'color: {s["color"]}, name: "{s["label"]}", facing: 3, redstone: 0b}}}}'}
        landing = [(x, y + dy, 775) for dy in (0, 1) for x in DOOR_X]
        cabin = [(x, y + dy, 774) for dy in (0, 1) for x in DOOR_X]
        for p in landing:
            c[p] = LANDING_DOOR
        call = (-38, y + 1, 776)
        c[call] = BUTTON
        floors.append(dict(label=s['label'], cabin=[CX, y, CZ], exit='south', approach_y=y, controller=list(ctrl),
                           calls=[dict(kind='vanilla_button', position=list(call), state=BUTTON, facing='south',
                                       target_controller=list(ctrl))],
                           restricted=False,
                           landing_doors=[dict(pos=list(p), closed_state=LANDING_DOOR) for p in landing],
                           cabin_doors=[dict(pos=list(p), closed_state=CABIN_DOOR) for p in cabin]))
    # the car at the lobby
    y0 = LOBBY_FLOOR + 1
    for x in range(CAR[0], CAR[1] + 1):
        for z in range(CAR[2], CAR[3] + 1):
            c[x, y0 - 1, z] = CAR_FLOOR
            c[x, y0 + 4, z] = CAR_LIGHT if (x, z) == (CX, CZ) else CAR_ROOF
            edge = x in (CAR[0], CAR[1]) or z in (CAR[2], CAR[3])
            for y in range(y0, y0 + 4):
                c[x, y, z] = CAR_WALL if edge else AIR
    for x in DOOR_X:
        for dy in (0, 1):
            c[x, y0 + dy, 774] = CABIN_DOOR
    button, display = (CX - 2, y0 + 1, CZ), (CX - 2, y0 + 2, CZ)
    c[button] = 'movingelevators:button_block'
    c[display] = 'movingelevators:display_block'
    entities[button] = {'id': 'movingelevators:button_tile',
                        'snbt': '{data: {camoState: {Name: "minecraft:white_concrete"}, '
                                f'controllerX: {CTRL_X}, controllerY: {y0}, controllerZ: {CZ}, '
                                'facing: 3, controllerFacing: 3, redstone: 0b}}'}
    entities[display] = {'id': 'movingelevators:display_tile', 'snbt': '{data: {camoState: {Name: "minecraft:white_concrete"}}}'}
    lift = dict(id=LIFT_ID, controller_side='west', controller_facing='east',
                inside_button_offset=[-2, 1, 0], inside_display_offset=[-2, 2, 0], floors=floors)
    return c, entities, lift


def main(out, two_stop=False):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    w = World(REGION)
    c, entities, lift = plan(w)
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
        if w.block_entity(x, y, z):
            carried.append([x, y, z, cur])
        rows.append([x, y, z, cur, want] + ([e] if e else []))
        kinds[(cur.split('[')[0].split(':')[-1], want.split('[')[0].split(':')[-1])] += 1
    for g in gs:
        g.assert_positions([tuple(r[:3]) for r in rows])
    if carried:
        raise SystemExit(f'{len(carried)} cells carry a block entity: {carried[:5]}')
    _, _, south = SR.plan(two_stop)
    manifest = dict(schema=south['schema'], lifts=south['lifts'] + [lift])
    (out / 'rows.json').write_text(json.dumps(rows, ensure_ascii=False), 'utf8')
    (out / 'public_lifts_r65.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), 'utf8')
    xs, ys, zs = zip(*[r[:3] for r in rows])
    rep = dict(rows=len(rows), entities=len(entities), box=[min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)],
               kinds=[[a, b, n] for (a, b), n in kinds.most_common(25)], lift=LIFT_ID, stops=[s['y'] for s in stops()],
               lifts_in_file=[l['id'] for l in manifest['lifts']])
    (out / 'report.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), 'utf8')
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1], '--two-stop' in sys.argv)
