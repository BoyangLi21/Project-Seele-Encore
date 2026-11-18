"""Terrain profile from the Yashima firing position toward Ramiel, for the client's far-horizon clip
(RamielHorizonClipR64). Distant Horizons draws terrain past the vanilla render distance into its own depth, so the
far Angel would be drawn over the ridges in front of it; the client uses these profiles to draw it only above them.

  python ramiel_horizon.py <out json>

Reads BUILDINGS_WORLD (the formal world or a copy) for the site files and terrain. For each azimuth around the line
from the emplacement to the Angel's axis, the highest solid-or-leaf block within 5 x 5 of a point every STEP blocks out
to the axis; lift
towers count at their raised height, the state the far view is baked in. Rerun after terrain or skyline changes
between the emplacement and the city.
"""
import json, math, sys
from pathlib import Path
from mca import REGION, WORLD, World
from city_body_sync import topology

STEP = 4
SPAN_DEG, AZ_STEP_DEG = 8.0, 0.25


def main(out):
    w = World(REGION)
    site = json.load(open(Path(WORLD) / 'tv_encounter_sites_r45.json', encoding='utf8'))['sites']['ramiel']
    hero, angel = site['hero'], site['angel']
    towers = [(t['centre'][0] + t['fp'][0], t['centre'][0] + t['fp'][1], t['centre'][2] + t['fp'][2], t['centre'][2] + t['fp'][3],
               t['centre'][1] + t['H'] + 3) for t in topology(WORLD).values()]
    cache = {}
    def top(x, z):
        if (x, z) in cache: return cache[x, z]
        h = 40
        for y in range(330, 30, -1):
            s = w.get(x, y, z)
            if s and not s.endswith('air') and 'water' not in s:
                h = y; break
        for x0, x1, z0, z1, raised in towers:
            if x0 <= x <= x1 and z0 <= z <= z1: h = max(h, raised)
        cache[x, z] = h
        return h
    dx, dz = angel[0] - hero[0], angel[2] - hero[2]
    base = math.degrees(math.atan2(dz, dx)); reach = math.hypot(dx, dz) + 48
    n = int(round(2 * SPAN_DEG / AZ_STEP_DEG)) + 1
    lines = []
    for i in range(n):
        az = math.radians(base - SPAN_DEG + i * AZ_STEP_DEG)
        row = []
        for k in range(1, int(reach // STEP) + 1):
            d = k * STEP
            x, z = int(math.floor(hero[0] + math.cos(az) * d)), int(math.floor(hero[2] + math.sin(az) * d))
            # the highest top in the 5 x 5 cell around the sample: tree crowns on ridges, which the far view draws too
            row.append(max(top(x + i, z + j) for i in range(-2, 3) for j in range(-2, 3)) + 1)
        lines.append(row)
    doc = dict(schema=1, site=site['id'], anchor=[hero[0], hero[1], hero[2]], axis=[angel[0], angel[2]], step=STEP,
               azimuth_start_deg=base - SPAN_DEG, azimuth_step_deg=AZ_STEP_DEG, tops=lines,
               note='top of terrain + 1 every step blocks along each azimuth from anchor; lift towers at raised height')
    Path(out).write_text(json.dumps(doc, separators=(',', ':')), 'utf8')
    print('lines', n, 'samples', len(lines[0]), 'bytes', Path(out).stat().st_size)


if __name__ == '__main__':
    main(sys.argv[1])
