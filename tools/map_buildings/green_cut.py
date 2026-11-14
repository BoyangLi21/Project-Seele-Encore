"""Green a bare stone cut on a wooded slope: grass over its surface, a little planting.

green_cut.py <seed x,z> <radius> <out dir>

From the seed column, flood the columns whose surface (first block that is neither open nor
plant) is bare rock (stone, andesite, diorite, granite, tuff, cobblestone, gravel) and lies under
open sky, within radius. Each surface block becomes grass and the rock right under it dirt, so the
cut reads as the terraced hillside around it; its step faces keep their rock below the dirt.
Bushes and small trees go on it as dense as the woods around (e13_plan.local_trees).
"""
import json, sys
from collections import Counter, deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, short
from e5_plan import is_veg
from e13_plan import local_trees

ROCK = ('minecraft:stone', 'minecraft:andesite', 'minecraft:diorite', 'minecraft:granite', 'minecraft:tuff',
        'minecraft:cobblestone', 'minecraft:gravel', 'minecraft:deepslate')
GRASS, DIRT = 'minecraft:grass_block[snowy=false]', 'minecraft:dirt'


def surface(w, x, z, start=200):
    y = start
    while y > -64:
        s = w.get(x, y, z)
        if s is None:
            return None, None
        if not (is_open(s) or is_veg(s)):
            return y, s
        y -= 1
    return None, None


def main(seed, radius, out):
    w = World(REGION)
    sx, sz = (int(v) for v in seed.split(','))
    radius = int(radius)
    q, seen, cut = deque([(sx, sz)]), {(sx, sz)}, {}
    while q:
        x, z = q.popleft()
        y, s = surface(w, x, z)
        if y is None or s.split('[')[0] not in ROCK:
            continue
        if any(not is_open(w.get(x, yy, z) or 'minecraft:air') for yy in range(y + 1, y + 40)):
            continue        # under a roof or a deck: not part of the open cut
        cut[x, z] = y
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, z + dz)
            if n not in seen and abs(n[0] - sx) <= radius and abs(n[1] - sz) <= radius:
                seen.add(n)
                q.append(n)
    rows = {}
    for (x, z), y in cut.items():
        rows[x, y, z] = [x, y, z, w.get(x, y, z), GRASS]
        below = w.get(x, y - 1, z)
        if below and below.split('[')[0] in ROCK:
            rows[x, y - 1, z] = [x, y - 1, z, below, DIRT]
    if cut:
        xs = [c[0] for c in cut]; zs = [c[1] for c in cut]; ys = list(cut.values())
        density, log = local_trees(w, [min(xs) - 20, min(ys), min(zs) - 20, max(xs) + 20, max(ys) + 20, max(zs) + 20])
    else:
        density, log = 0, 'minecraft:oak_log'
    leaves = log.replace('_log', '_leaves') + '[distance=1,persistent=true,waterlogged=false]'
    taken = set()
    for (x, z), t in sorted(cut.items()):
        r = ((x * 73856093) ^ (z * 19349663)) % 1000 / 1000.0
        free = lambda c: w.get(*c) in ('minecraft:air', 'minecraft:cave_air') and c not in rows
        if r < density * 0.4 and all((x + dx, z + dz) not in taken for dx in range(-3, 4) for dz in range(-3, 4)):
            taken.add((x, z))
            cells = [((x, t + k, z), log + '[axis=y]') for k in range(1, 4)]
            cells += [((x + dx, t + dy, z + dz), leaves) for dy in (3, 4) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (dx, dz) != (0, 0) or dy == 4]
            cells += [((x, t + 5, z), leaves)]
            for c, a in cells:
                if free(c):
                    rows[c] = [*c, w.get(*c), a]
        elif r < density * 0.8 and free((x, t + 1, z)):
            rows[x, t + 1, z] = [x, t + 1, z, w.get(x, t + 1, z), leaves]
    R = [r for r in rows.values() if not w.block_entity(*r[:3]) and r[3] != r[4]]
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(R), 'utf8')
    print(len(R), 'cut columns', len(cut), Counter(short(r[3]) + '->' + short(r[4]) for r in R).most_common(6))


if __name__ == '__main__':
    main(*sys.argv[1:])
