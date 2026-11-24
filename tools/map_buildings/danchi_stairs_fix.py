"""Headroom over the danchi stair landings, and a way out of room 402 (R65 owner feedback round 2, item 6).

  python danchi_stairs_fix.py rei|kirisato <out dir>

The danchi slabs built by canon_homes.py have 3-block floors, so a landing has 2 blocks of headroom. A player is
1.8 tall and steps 0.5 up onto a stair, so stepping from a landing onto the first step of a flight, or down from the
last step onto a landing, puts the head into the slab above the landing: every flight is blocked at its landing
(measured in game: the walk stops 0.3 short of each landing). The slab strip right over the landing is a dead end on
the floor above (beyond the flights), so it is removed: over a north landing (even floors) the strip at z0+1 of the
odd slab above, over a south landing (odd floors) the strip at z0+5 of the even slab above, in both stair columns of
both cores. The roof slab stays: the top floor has no flight up.

Room 402 (rei only): the steel door is an iron door and opened from inside only with a button beside it, for one
second. A stone pressure plate in front of the door inside opens it as one walks up to it; the button stays.
Writes rows.json and report.json. Each slab is found in the world from its known x0, z0 (canon_homes.py) by the first
step of its west core.
"""
import json, sys
from pathlib import Path
from mca import REGION, World
from float_fix import guards
from canon_homes import CORES, FLOORS

AIR = 'minecraft:air'
PLATE = 'minecraft:stone_pressure_plate[powered=false]'
SITES = {
    'rei': [(-201, 498, 1), (-201, 513, 2), (-201, 528, 3)],
    'kirisato': [(ox + dx, oz + 6, None) for ox, oz in ((-2878, -1112), (-2790, -1112), (-2702, -1112),
                                                     (-2878, -1016), (-2790, -1016), (-2702, -1016)) for dx in (2, 42)],
}
SOLID_SLAB = ('light_gray_concrete', 'gray_concrete', 'smooth_stone')


def find_floor(w, x0, z0):
    """The slab's ground floor y: the west core's first step stands on it at (x0+7, gy+1, z0+2)."""
    for gy in range(40, 200):
        s = w.get(x0 + CORES[0][0], gy + 1, z0 + 2) or ''
        if s.startswith('minecraft:stone_brick_stairs[facing=south') and \
                (w.get(x0 + CORES[0][0], gy + 2, z0 + 3) or '').startswith('minecraft:stone_brick_stairs[facing=south'):
            return gy
    raise SystemExit(f'no danchi core at x0 {x0} z0 {z0}')


def main(site, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    w = World(REGION)
    gs = guards()
    rows, slabs = [], []
    for x0, z0, n in SITES[site]:
        gy = find_floor(w, x0, z0)
        cells = []
        for j in range(1, FLOORS):
            y = gy + 3 * j
            z = z0 + 1 if j % 2 else z0 + 5
            for c0, c1 in CORES:
                cells += [(x0 + c0, y, z), (x0 + c1, y, z)]
        for x, y, z in cells:
            cur = w.get(x, y, z)
            if cur.split('[')[0].split(':')[-1] not in SOLID_SLAB or w.block_entity(x, y, z):
                raise SystemExit(f'{x},{y},{z} is {cur}, not a plain slab block')
            rows.append([x, y, z, cur, AIR])
        slabs.append(dict(x0=x0, z0=z0, number=n, floor_y=gy, cells=len(cells)))
    if site == 'rei':
        plate = (-191, 103, 518)                     # inside 402, in front of the door at (-192, 103, 518)
        if w.get(*plate) != AIR or not (w.get(-192, 103, 518) or '').startswith('minecraft:iron_door[facing=east,half=lower'):
            raise SystemExit('room 402 is not as built')
        rows.append([*plate, AIR, PLATE])
    for g in gs:
        g.assert_positions([tuple(r[:3]) for r in rows])
    if len({tuple(r[:3]) for r in rows}) != len(rows):
        raise SystemExit('duplicate cells')
    (out / 'rows.json').write_text(json.dumps(rows), 'utf8')
    rep = dict(site=site, rows=len(rows), slabs=slabs, plate_402=site == 'rei', writer_flags=[])
    (out / 'report.json').write_text(json.dumps(rep, indent=1), 'utf8')
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
