"""Block list for the Central Dogma main shaft (ROADMAP 5.2a), from the geometry in dogma_shaft_plan.py.

  python dogma_shaft_build.py <out dir>

Reads BUILDINGS_WORLD. Writes rows.json (only cells that change), report.json and a copy of shaft_r66.json.
- Hall doorway x 94-95, z 230-254, y -1051..-989: opened (write with --dogma-hall-doorway).
- Aisle x 96-103 in front of it, z 226-257: floor raised to the hall's level (top -1052), so the EVA walks in level.
- Entry bay over the shaft, x 104-135, z 226-257, y -1051..-990, lined on its three rock sides, ceiling at -989.
- Shaft x 104-135, z 226-257, y -1264..-1052, lining 2 blocks of nerv_shaft_panel on all four sides, floor at -1265.
- Rung grooves: every 8 blocks the inner lining layer is cut out (air) all round, a light strip behind it.
- Bulkheads: an armour band in the inner lining at each bulkhead's two layers; the plates themselves are left open
  (air) until the code that opens and closes them exists (shaft_r66.json carries their closed state).
- Stations and hand ledges: 2-block slabs, floor panel on top, structural panel under.
- Bottom gallery x 96-103, z 230-254, y -1264..-1202 into the lobby's east wall, floor level with the shaft floor.
Every cell is checked against the city, lift and launch guards; only the doorway may lie in the launch reservation.
"""
import json, sys
from collections import Counter
from pathlib import Path
from mca import REGION, World
from float_fix import guards
import dogma_shaft_plan as P
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from plan_r66_dogma_doorway import DOOR, in_doorway

AIR = 'minecraft:air'
SHAFT = 'projectseele:nerv_shaft_panel'
FLOORP = 'projectseele:nerv_floor_panel'
STRUCT = 'projectseele:nerv_structural_panel'
ARMOR = 'projectseele:nerv_launch_armor'
LIGHT = 'projectseele:nerv_strip_light'
HALL_FLOOR = -1052                     # the hall floor beside the doorway (it slopes -1049..-1055 along z)
BAY_TOP = -990
X0, X1, Z0, Z1, FLOOR = P.X0, P.X1, P.Z0, P.Z1, P.FLOOR


def plan_cells():
    c = {}
    put = lambda x, y, z, s: c.__setitem__((x, y, z), s)
    # shaft void and bay void
    for y in range(FLOOR + 1, BAY_TOP + 1):
        for x in range(X0, X1 + 1):
            for z in range(Z0, Z1 + 1):
                put(x, y, z, AIR)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            put(x, FLOOR, z, FLOORP)
    # lining: two layers on all four sides below the aisle floor, three sides (not west) in the bay
    for y in range(FLOOR, BAY_TOP + 1):
        for k in (1, 2):
            for z in range(Z0 - k, Z1 + k + 1):
                put(X1 + k, y, z, SHAFT)
                if y <= HALL_FLOOR - 1:
                    put(X0 - k, y, z, SHAFT)
            for x in range(X0 - k, X1 + k + 1):
                if x < X0 and y > HALL_FLOOR - 1:
                    continue
                put(x, y, Z0 - k, SHAFT)
                put(x, y, Z1 + k, SHAFT)
    for x in range(X0, X1 + 3):                       # bay ceiling
        for z in range(Z0 - 2, Z1 + 3):
            put(x, BAY_TOP + 1, z, SHAFT)
    # rung grooves with a light strip behind
    rungs = list(range(HALL_FLOOR - 8, FLOOR + 8, -P.RUNG_STEP))
    for y in rungs:
        for z in range(Z0, Z1 + 1):
            put(X0 - 1, y, z, AIR); put(X0 - 2, y, z, LIGHT)
            put(X1 + 1, y, z, AIR); put(X1 + 2, y, z, LIGHT)
        for x in range(X0, X1 + 1):
            put(x, y, Z0 - 1, AIR); put(x, y, Z0 - 2, LIGHT)
            put(x, y, Z1 + 1, AIR); put(x, y, Z1 + 2, LIGHT)
    # bulkhead armour bands (the plates open)
    for b in P.BULKHEADS:
        for y in (b, b + 1):
            for z in range(Z0 - 1, Z1 + 2):
                put(X0 - 1, y, z, ARMOR); put(X1 + 1, y, z, ARMOR)
            for x in range(X0 - 1, X1 + 2):
                put(x, y, Z0 - 1, ARMOR); put(x, y, Z1 + 1, ARMOR)
    # aisle floor raised to the hall's level in front of the doorway and at the lip
    for x in range(DOOR['x'][1] + 1, X0):
        for z in range(Z0, Z1 + 1):
            for y in range(HALL_FLOOR - 3, HALL_FLOOR + 1):
                put(x, y, z, FLOORP if y == HALL_FLOOR else STRUCT)
    # hall doorway
    for x in range(DOOR['x'][0], DOOR['x'][1] + 1):
        for y in range(DOOR['y'][0], DOOR['y'][1] + 1):
            for z in range(DOOR['z'][0], DOOR['z'][1] + 1):
                put(x, y, z, AIR)
    # bottom gallery into the lobby (through the west lining)
    gx, gz, gy = P.GALLERY['x'], P.GALLERY['z'], P.GALLERY['y']
    for x in range(gx[0], X0):
        for z in range(gz[0] - 1, gz[1] + 2):
            put(x, FLOOR, z, FLOORP)
            put(x, gy[1] + 1, z, SHAFT)
            for y in range(gy[0], gy[1] + 1):
                put(x, y, z, AIR if gz[0] <= z <= gz[1] else SHAFT)
    # stations and hand ledges, re-planned from the same rules
    return c, rungs


def main(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    c, rungs = plan_cells()
    plan = json.loads(Path('E:/eva-map-buildings/dogma/plan/shaft_r66.json').read_text('utf8'))
    for p in plan['stations'] + plan['ledges']:
        x0, y0, z0, x1, y1, z1 = p['box']
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                c[x, y1, z] = FLOORP
                c[x, y0, z] = STRUCT
    w = World(REGION)
    city, lift, launch = guards()
    rows, kinds, keep = [], Counter(), Counter()
    for (x, y, z), want in sorted(c.items()):
        cur = w.get(x, y, z)
        if cur is None:
            raise SystemExit(f'{x},{y},{z} not generated')
        if cur == want:
            continue
        if want == AIR and cur.split('[')[0].endswith('air'):
            continue
        if w.block_entity(x, y, z):
            raise SystemExit(f'{x},{y},{z} {cur} carries a block entity')
        city.assert_positions([(x, y, z)])
        lift.assert_positions([(x, y, z)])
        try:
            launch.assert_positions([(x, y, z)])
        except ValueError:
            if not (in_doorway(x, y, z) and want == AIR):
                raise
        rows.append([x, y, z, cur, want])
        kinds[(cur.split('[')[0].split(':')[-1], want.split('[')[0].split(':')[-1])] += 1
    (out / 'rows.json').write_text(json.dumps(rows), 'utf8')
    plan['shaft']['lip_y'] = HALL_FLOOR
    plan['rungs_y'] = rungs
    (out / 'shaft_r66.json').write_text(json.dumps(plan, indent=1), 'utf8')
    rep = dict(rows=len(rows), kinds=[[a, b, n] for (a, b), n in kinds.most_common(20)], rungs=len(rungs), writer_flags=['--dogma-hall-doorway'])
    (out / 'report.json').write_text(json.dumps(rep, indent=1), 'utf8')
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
