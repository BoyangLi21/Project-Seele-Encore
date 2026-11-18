"""The missing LCL Sync Lab stop of personnel lift r25-west-observation, as blocks plus a new lift manifest.

  python lcl_lift_landing.py <out dir>

The LCL corridor (x 87-96, floor y -1089, z 299-375) was copied down with the GeoFront, but the lift kept only its
hangar (-1014) and observation (-987) stops and its shaft is solid panel from -1016 down to -1088. Its 5 x 5 x 6
Moving Elevators cage (x 87-91, z 364-368) gets a stop with feet at -1088, the cage floor in the pit that is already
at -1089. The blocks follow the -1014 landing: shaft hollowed, a 3-wide opening in the shaft face (z 369) with glass
either side and a lintel, the 5-wide landing door plane at z 370 (closed glass; the lift writes it open or closed),
and the controller in the controller column. The hall is only x 87-91 wide, so the call button sits on its west wall
facing east, at the height of the other floors' buttons. The corridor meets the shaft at x 92, so that side gets a
shaft wall for the 4 open layers.

No lift code changes: the Moving Elevators controller has no saved data, so the game creates it on first access and it
joins the shaft's elevator group on its first tick (floors are inserted in ascending order), and the R52 lift
directory reads the manifest again when the file changes. Writes rows.json, personnel_lifts_r52.json (replaces the
world root file, epoch unchanged) and patch.json with both md5 sums.
"""
import copy, hashlib, json, os, sys
from pathlib import Path
from mca import REGION, World, WORLD
from float_fix import guards

LIFT = 'r25-west-observation'
CABIN = (89, -1088, 366)
X0, X1, Z0, Z1 = 87, 91, 364, 368          # cage footprint
TOP = -1016                                 # first solid layer below the hangar stop's cage floor (-1015)
FACE, DOORS = 369, 370
SHAFT = 'projectseele:nerv_shaft_panel'
WALL = 'projectseele:nerv_wall_panel'
GLASS = 'projectseele:clear_glass'
CLOSED = 'minecraft:gray_stained_glass'
CONTROLLER = (86, CABIN[1], 366)
BUTTON = (87, CABIN[1] + 1, 371)
BUTTON_STATE = 'minecraft:polished_blackstone_button[face=wall,facing=east,powered=false]'
LABEL = 'LCL同步实验层'


def cells():
    y0 = CABIN[1]
    c = {}
    for y in range(y0, TOP + 1):
        for x in range(X0, X1 + 1):
            for z in range(Z0, Z1 + 1):
                c[x, y, z] = 'minecraft:air'
    for y in range(y0, y0 + 4):                                    # shaft wall towards the corridor
        for z in range(Z0, Z1 + 1):
            c[92, y, z] = SHAFT
    c[87, y0, FACE] = WALL                                         # shaft face like the hangar stop
    for y in (y0 + 1, y0 + 2):
        c[87, y, FACE] = GLASS
        c[91, y, FACE] = GLASS
    for x in range(88, 91):
        for y in range(y0, y0 + 3):
            c[x, y, FACE] = 'minecraft:air'
    for x in range(87, 92):
        c[x, y0 + 3, FACE] = WALL                                  # lintel
        for y in range(y0, y0 + 3):
            c[x, y, DOORS] = CLOSED
    c[CONTROLLER] = 'movingelevators:elevator_block[facing=east]'
    c[86, BUTTON[1], BUTTON[2]] = 'minecraft:black_concrete'       # button plate, as on the hangar floor
    c[BUTTON] = BUTTON_STATE
    return c


def floor_entry():
    y0 = CABIN[1]
    return {
        'label': LABEL, 'cabin': list(CABIN), 'exit': 'south', 'approach_y': y0, 'controller': list(CONTROLLER),
        'calls': [{'kind': 'vanilla_button', 'position': list(BUTTON), 'state': BUTTON_STATE, 'facing': 'east',
                   'target_controller': list(CONTROLLER)}],
        'restricted': False,
        'landing_doors': [{'pos': [x, y, DOORS], 'closed_state': CLOSED} for x in range(87, 92) for y in range(y0, y0 + 3)],
        'cabin_doors': [{'pos': [x, y, Z1], 'closed_state': 'minecraft:light_gray_stained_glass'} for x in range(88, 91) for y in range(y0, y0 + 3)],
    }


def main(out):
    w = World(REGION)
    gs = guards()
    rows = []
    for (x, y, z), want in sorted(cells().items()):
        cur = w.get(x, y, z)
        if cur is None:
            raise SystemExit(f'{x},{y},{z} not generated')
        if cur == want:
            continue
        if w.block_entity(x, y, z):
            raise SystemExit(f'{x},{y},{z} {cur} carries a block entity')
        for g in gs:
            g.assert_positions([(x, y, z)])
        rows.append([x, y, z, cur, want])
    src = Path(WORLD, 'personnel_lifts_r52.json')
    raw = src.read_bytes()
    doc = json.loads(raw.decode('utf8'))
    lift = next(l for l in doc['lifts'] if l['id'] == LIFT)
    if any(f['cabin'][1] == CABIN[1] for f in lift['floors']):
        raise SystemExit('stop already declared')
    lift['floors'] = sorted(lift['floors'] + [floor_entry()], key=lambda f: f['cabin'][1])
    new = json.dumps(doc, ensure_ascii=False, separators=(',', ':')).encode('utf8')   # compact, as the world file is
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (Path(out) / 'personnel_lifts_r52.json').write_bytes(new)
    patch = dict(rows=len(rows), manifest=dict(file='personnel_lifts_r52.json (world root)', before_md5=hashlib.md5(raw).hexdigest(),
                                              after_md5=hashlib.md5(new).hexdigest(), lift=LIFT, added_floor=floor_entry()['label'],
                                              cabin=list(CABIN), floors_after=[f['cabin'][1] for f in lift['floors']]),
                 rows_md5=hashlib.md5((Path(out) / 'rows.json').read_bytes()).hexdigest())
    (Path(out) / 'patch.json').write_text(json.dumps(patch, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(patch, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
