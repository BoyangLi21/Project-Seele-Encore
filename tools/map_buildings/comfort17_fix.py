"""Comfort 17: stairs a player can climb, and lights (R65 owner feedback round 2 add-ons 29 and 30).

  python comfort17_fix.py <out dir>

Reads BUILDINGS_WORLD. Writes rows.json and report.json.

Stairs. Floors are 3 blocks apart with 2 blocks of headroom, so stepping from a landing onto the first step (0.5 up)
or down off the last one puts the head into the slab over the landing. The slab cell right over each flight's start
cell is opened, and on the floor above that cell gets a smooth quartz block at foot height so nobody walks into the
opening (it sits above the climber's head). Even floors climb east along z 777 from (-44, 777); odd floors climb
west along z 776 from (-40, 776): the caps stand beside the west corridor doorway on odd floors and in front of the
left half of the lift door on even floors (the right half stays free).

Lights. The 7 levers in 11-A-2 hang under bare concrete (their lamps were overwritten by the slab above): the levers
go and a sea lantern sits in the ceiling where each lamp was. The outdoor corridor gets a sea lantern in its ceiling
every 6 blocks on every floor, the core (lobby strip and lift landing) two per floor.
"""
import json, sys
from collections import Counter
from pathlib import Path
from mca import REGION, World
from float_fix import guards

AIR = 'minecraft:air'
CAP = 'minecraft:smooth_quartz'
LIGHT = 'minecraft:sea_lantern'
LOBBY_FLOOR, FLOORS = 132, 14
CORRIDOR_X = range(-64, -17, 6)
CORE_LIGHTS = [(-45, 773), (-38, 777)]
CEILING_OK = ('light_gray_concrete', 'white_concrete', 'smooth_stone', 'polished_andesite')


def slab(k):
    return LOBBY_FLOOR + 3 * k


def main(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    w = World(REGION)
    c, parts = {}, Counter()
    # stairs: flights from floor k = 0 .. 12
    holes = set()
    for k in range(FLOORS - 1):
        x, z = (-44, 777) if k % 2 == 0 else (-40, 776)
        y = slab(k + 1)
        c[x, y, z] = AIR; c[x, y + 1, z] = CAP; holes.add((x, z, k + 1))
        parts['stairs'] += 2
    # lights in 11-A-2: the levers' cells and the ceiling above them
    for x in range(-58, -45):
        for z in range(769, 779):
            s = w.get(x, 164, z) or ''
            if s.startswith('minecraft:lever'):
                c[x, 164, z] = AIR; c[x, 165, z] = LIGHT; parts['11-A-2'] += 2
    # corridor and core lights in each floor's ceiling
    for k in range(FLOORS):
        y = slab(k + 1)
        for x in CORRIDOR_X:
            c.setdefault((x, y, 779), LIGHT); parts['corridor'] += 1
        for x, z in CORE_LIGHTS:
            c.setdefault((x, y, z), LIGHT); parts['core'] += 1
    gs = guards()
    rows, refused = [], []
    for (x, y, z), want in sorted(c.items()):
        cur = w.get(x, y, z)
        if cur == want:
            continue
        name = cur.split('[')[0].split(':')[-1]
        if want == LIGHT and name not in CEILING_OK:
            refused.append([x, y, z, cur]); continue
        if want == CAP and not cur.endswith('air'):
            refused.append([x, y, z, cur]); continue
        if w.block_entity(x, y, z):
            refused.append([x, y, z, cur]); continue
        rows.append([x, y, z, cur, want])
    for g in gs:
        g.assert_positions([tuple(r[:3]) for r in rows])
    (out / 'rows.json').write_text(json.dumps(rows), 'utf8')
    xs, ys, zs = zip(*[r[:3] for r in rows])
    rep = dict(rows=len(rows), parts=dict(parts), refused=refused, box=[min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)])
    (out / 'report.json').write_text(json.dumps(rep, indent=1), 'utf8')
    print(json.dumps(rep))


if __name__ == '__main__':
    main(sys.argv[1])
