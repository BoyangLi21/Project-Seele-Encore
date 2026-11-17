"""Soften the cliffs left where an E5 dig-out ran into its slope limit.

cliff_plan.py <dig rows.json> <bbox x0,z0,x1,z1> <out> [plants density override]

The dug zone is every column a dig-out turned natural cells to air in (from its rows file,
inside the bbox). Outside it, column by column at distance d from the zone and with the ground
level b of the nearest zone column: where the hill stands at most SLOPE_MAX above b, the 1:1
slope simply continues (cut to b + d, grass top). Higher, terraces cut into the hill: a
stone-brick wall at most TIER_H high on the first column of each tier, a TIER_W - 1 column grass
bench behind it at the wall's top, bushes and small trees on the benches as dense as the woods
around. Only natural cells are cut or faced; roads, buildings and water stop a column; a tree on
a cut column goes whole.
"""
import json, sys
from collections import Counter, deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, is_natural, base, short
from e5_plan import is_veg
from e13_plan import local_trees

GRASS, WALL, AIR = 'minecraft:grass_block[snowy=false]', 'minecraft:stone_bricks', 'minecraft:air'
SLOPE_MAX, TIER_H, TIER_W, MAXD = 6, 8, 4, 24


def main(rows_file, bbox, out):
    w = World(REGION)
    x0, z0, x1, z1 = bbox
    dug = {(r[0], r[2]) for r in json.load(open(rows_file)) if x0 <= r[0] <= x1 and z0 <= r[2] <= z1
           and r[4] == AIR and is_natural(r[3])}

    def top(x, z, start=160):
        y = start
        while y > -120:
            s = w.get(x, y, z)
            if s is None:
                return None, None
            if not (is_open(s) or is_veg(s)):
                return y, s
            y -= 1
        return None, None

    level = {}
    for (x, z) in dug:
        y, s = top(x, z)
        if y is not None:
            level[x, z] = y
    dist, src = {c: 0 for c in level}, dict((c, c) for c in level)
    q = deque(level)
    while q:
        c = q.popleft()
        if dist[c] >= MAXD:
            continue
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                n = (c[0] + dx, c[1] + dz)
                if n not in dist:
                    dist[n] = dist[c] + 1
                    src[n] = src[c]
                    q.append(n)
    rows, benches, trees = {}, [], []

    def put(x, y, z, after):
        s = w.get(x, y, z)
        if s != after:
            rows[x, y, z] = [x, y, z, s, after]

    for c, d in dist.items():
        if d == 0:
            continue
        x, z = c
        b = level[src[c]]
        h, s = top(x, z)
        if h is None or not is_natural(s) or h <= b + 1:
            continue
        if h - b <= SLOPE_MAX + d - 1 and h - b <= SLOPE_MAX:
            t, kind = b + d, 'slope'
        else:
            tier = (d - 1) // TIER_W + 1
            p = (d - 1) % TIER_W + 1
            t = b + TIER_H * (tier if p > 1 else tier)        # wall top = bench level of its tier
            kind = 'wall' if p == 1 else 'bench'
            if kind == 'wall':
                t = b + TIER_H * tier
        if h <= t and kind != 'wall':
            continue
        # walk down from the top: cut natural above t, keep a column only if it is natural all the way
        yy = h
        ok = True
        while yy > t:
            st = w.get(x, yy, z)
            if not is_natural(st):
                ok = False
                break
            yy -= 1
        if not ok:
            continue
        if '_log' in (w.get(x, h + 1, z) or ''):
            trees.append((x, h + 1, z))
        for yy in range(t + 1, h + 1):
            put(x, yy, z, AIR)
        if kind == 'wall':
            lo = b + TIER_H * (tier - 1) + 1
            for yy in range(lo, min(t, h) + 1):
                if is_natural(w.get(x, yy, z)):
                    put(x, yy, z, WALL)
        else:
            if is_natural(w.get(x, t, z)):
                put(x, t, z, GRASS)
            if kind == 'bench':
                benches.append((x, t, z))
    # trees standing on cut ground go whole
    removed = set()
    for tx, ty, tz in trees:
        q = deque([(tx, ty, tz)])
        while q:
            c = q.popleft()
            if c in removed or abs(c[0] - tx) > 3 or abs(c[2] - tz) > 3 or c[1] - ty > 20:
                continue
            st = w.get(*c)
            if not st or not ('_log' in st or '_wood' in st):
                continue
            removed.add(c)
            for dd in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q.append((c[0] + dd[0], c[1] + dd[1], c[2] + dd[2]))
    for c in removed:
        if c not in rows:
            rows[c] = [*c, w.get(*c), AIR]
    for (lx, ly, lz) in list(removed):
        for dx in range(-2, 3):
            for dy in range(-1, 4):
                for dz in range(-2, 3):
                    c = (lx + dx, ly + dy, lz + dz)
                    st = w.get(*c)
                    if st and 'leaves' in st and c not in rows:
                        rows[c] = [*c, st, AIR]
    # planting on the benches
    density, log = local_trees(w, [x0, 60, z0, x1, 100, z1])
    leaves = log.replace('_log', '_leaves') + '[distance=1,persistent=true,waterlogged=false]'
    taken = set()
    for x, t, z in benches:
        r = ((x * 73856093) ^ (z * 19349663)) % 1000 / 1000.0
        free = lambda c: (c not in rows and w.get(*c) in ('minecraft:air', 'minecraft:cave_air')) or (c in rows and rows[c][4] == AIR)
        if r < density * 0.4 and all((x + dx, z + dz) not in taken for dx in range(-3, 4) for dz in range(-3, 4)):
            taken.add((x, z))
            cells = [((x, t + k, z), log + '[axis=y]') for k in range(1, 4)]
            cells += [((x + dx, t + dy, z + dz), leaves) for dy in (3, 4) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (dx, dz) != (0, 0) or dy == 4]
            cells += [((x, t + 5, z), leaves)]
            for c, a in cells:
                if free(c):
                    rows[c] = [*c, rows[c][3] if c in rows else w.get(*c), a]
        elif r < density * 0.7 and free((x, t + 1, z)):
            c = (x, t + 1, z)
            rows[c] = [*c, rows[c][3] if c in rows else w.get(*c), leaves]
    R = [r for r in rows.values() if not w.block_entity(*r[:3])]
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(R), 'utf8')
    kinds = Counter(short(r[3]) + '->' + short(r[4]) for r in R)
    print(len(R), 'dug columns', len(dug), 'benches', len(benches), 'trees removed', len({(c[0], c[2]) for c in removed}), kinds.most_common(8))


if __name__ == '__main__':
    main(sys.argv[1], [int(v) for v in sys.argv[2].split(',')], sys.argv[3])
