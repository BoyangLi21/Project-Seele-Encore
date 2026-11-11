"""E13: ground the floating edge of a large platform, in the outer-slope style of plan_outer_slopes.

Per site (bbox + y range of one platform piece):
- edge band: platform columns within 2 of the platform's outline get the open cells under them
  filled from the ground up to the platform (the outermost column is the face of the first wall
  when terraces are used);
- outside, per column, U = underside of the nearest platform column and D = U minus the ground
  next to the edge. D <= SLOPE_MAX: a 1:1 earth cone (grass over dirt), never more than one cell
  above a neighbour that cannot be raised. D larger, or a cone that would run past REACH:
  terraces, an 8-cell retaining wall every 4 columns with a 3-column grass bench between, down
  to the natural ground;
- a tree standing on a filled column goes whole (logs, then leaves nearer to it than to a kept log).
Only open cells are filled, only over natural ground; water, roads and buildings stop a column.
"""
import json, sys
from collections import Counter, deque
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, is_natural, base, short
from e5_plan import is_veg

HERE = Path(__file__).parent
GRASS, DIRT = 'minecraft:grass_block[snowy=false]', 'minecraft:dirt'
SLOPE_MAX, REACH, TIER_H, TIER_W = 10, 16, 8, 4


def fillable(s):
    return s is not None and is_open(s) and 'water' not in s and 'lava' not in s


def local_trees(w, bbox):
    """Share of columns around the site whose top is a tree, and the commonest log there."""
    x0, y0, z0, x1, y1, z1 = bbox
    n = hit = 0
    logs = Counter()
    for x in range(x0 - 40, x1 + 41, 4):
        for z in range(z0 - 40, z1 + 41, 4):
            if x0 <= x <= x1 and z0 <= z <= z1:
                continue
            for y in range(y1 + 40, y0 - 80, -1):
                st = w.get(x, y, z)
                if st is None or st in ('minecraft:air', 'minecraft:cave_air'):
                    continue
                n += 1
                if 'leaves' in st or '_log' in st:
                    hit += 1
                    for yy in range(y, y - 20, -1):
                        b = w.get(x, yy, z) or ''
                        if '_log' in b:
                            logs[b.split('[')[0]] += 1
                            break
                break
    kind = logs.most_common(1)[0][0] if logs else 'minecraft:oak_log'
    return (hit / n if n else 0.0), kind


def plant(w, sites, benches, rows):
    """Bushes and small trees on the terrace benches, as thick as the woods around the site."""
    def free(x, y, z):
        if (x, y, z) in rows and rows[x, y, z][4] not in ('minecraft:air',):
            return False
        s = w.get(x, y, z)
        return s is not None and (s in ('minecraft:air', 'minecraft:cave_air') or (x, y, z) in rows and rows[x, y, z][4] == 'minecraft:air')

    def set_cell(x, y, z, after):
        if free(x, y, z):
            rows[x, y, z] = [x, y, z, rows[x, y, z][3] if (x, y, z) in rows else w.get(x, y, z), after]

    by_site = {}
    for b in benches:
        by_site.setdefault(b[4], []).append(b)
    taken = set()
    for site in sites:
        mine = by_site.get(site['id'], [])
        if not mine:
            continue
        density, log = local_trees(w, site['bbox'])
        leaves = log.replace('_log', '_leaves') + '[distance=1,persistent=true,waterlogged=false]'
        trunk = log + '[axis=y]'
        site['planting'] = dict(density=round(density, 2), log=log)
        for x, t, z, p, _ in mine:
            r = ((x * 73856093) ^ (z * 19349663)) % 1000 / 1000.0
            if p == 2 and r < density * 0.45 and all((x + dx, z + dz) not in taken for dx in range(-3, 4) for dz in range(-3, 4)):
                taken.add((x, z))
                for k in range(1, 4):
                    set_cell(x, t + k, z, trunk)
                for dy in (3, 4):
                    for dx in (-1, 0, 1):
                        for dz in (-1, 0, 1):
                            if (dx, dz) != (0, 0) or dy == 4:
                                set_cell(x + dx, t + dy, z + dz, leaves)
                set_cell(x, t + 5, z, leaves)
            elif r < density * 0.6 and (x, z) not in taken:
                set_cell(x, t + 1, z, leaves)


def plan(w, sites, A):
    rows, trees, benches = {}, [], []

    def put(x, y, z, after):
        s = w.get(x, y, z)
        if fillable(s) and (x, y, z) not in rows:
            rows[x, y, z] = [x, y, z, s, after]

    def ground(x, z, start):
        y = start
        while y > start - 140 and (fillable(w.get(x, y, z)) or is_veg(w.get(x, y, z))):
            y -= 1
        return y

    for site in sites:
        x0, y0, z0, x1, y1, z1 = site['bbox']
        m = (A[:, 0] >= x0) & (A[:, 0] <= x1) & (A[:, 2] >= z0) & (A[:, 2] <= z1) & (A[:, 1] >= y0) & (A[:, 1] <= y1)
        U = {}
        for x, y, z, gap, gr, gy in A[m].tolist():
            if gr == 1:
                U[x, z] = min(U.get((x, z), 10 ** 6), y)
        mat = Counter(short(w.get(x, u, z)) for (x, z), u in list(U.items())[:500]).most_common(1)[0][0]
        wall = 'minecraft:light_gray_concrete' if 'concrete' in mat else 'minecraft:stone_bricks'
        site['wall'] = wall
        # distance inside the platform to its outline
        din = {}
        q = deque()
        for (x, z) in U:
            if any((x + dx, z + dz) not in U for dx in (-1, 0, 1) for dz in (-1, 0, 1)):
                din[x, z] = 1
                q.append((x, z))
        while q:
            c = q.popleft()
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    n = (c[0] + dx, c[1] + dz)
                    if n in U and n not in din:
                        din[n] = din[c] + 1
                        q.append(n)
        # outside: distance and source column
        dist, src = {}, {}
        q = deque()
        for c, d in din.items():
            if d == 1:
                dist[c] = 0
                src[c] = c
                q.append(c)
        while q:
            c = q.popleft()
            if dist[c] >= REACH + 8:
                continue
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    n = (c[0] + dx, c[1] + dz)
                    if n not in dist and n not in U:
                        dist[n] = dist[c] + 1
                        src[n] = src[c]
                        q.append(n)
        # drop at each edge column: platform underside minus the ground right outside it
        drop = {}
        for c, d in din.items():
            if d == 1:
                outs = [ground(c[0] + dx, c[1] + dz, U[c]) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (c[0] + dx, c[1] + dz) not in U]
                drop[c] = U[c] - min(outs) if outs else 0
        terr = {c: drop[c] > SLOPE_MAX for c in drop}
        site['edge_cols'] = len(drop)
        site['terrace_edge_cols'] = sum(terr.values())
        site['max_drop'] = max(drop.values(), default=0)
        # edge band under the platform
        for c, d in din.items():
            if d > 2:
                continue
            x, z = c
            u = U[c]
            col = []
            y = u - 1
            while y > u - 140 and fillable(w.get(x, y, z)):
                col.append(y)
                y -= 1
            if not is_natural(w.get(x, y, z)):
                continue
            s = src.get(c, c)
            face = d == 1 and terr.get(c, False)
            for yy in col:
                put(x, yy, z, wall if face and yy >= u - TIER_H else DIRT)
        # outside targets
        target, kind = {}, {}
        benchpos = {}
        for c, d in dist.items():
            if d == 0:
                continue
            s = src[c]
            u = U[s]
            if terr.get(s, False):
                tier = (d - 1) // TIER_W + 1
                p = (d - 1) % TIER_W + 1
                t = u - TIER_H * tier
                k = 'wall' if p == TIER_W else 'bench'
                benchpos[c] = p
            else:
                if d > REACH:
                    continue
                t, k = u - d, 'slope'
            if t > target.get(c, -10 ** 6):
                target[c], kind[c] = t, k
        cur, can = {}, {}
        for (x, z), t in target.items():
            y = ground(x, z, t + 60)
            top = w.get(x, y, z)
            cur[x, z] = y
            can[x, z] = is_natural(top) and all(fillable(w.get(x, yy, z)) or is_veg(w.get(x, yy, z)) for yy in range(y + 1, t + 1))
        final = {c: max(cur[c], target[c]) if can[c] else cur[c] for c in target}
        for (x, z) in list(target):
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, z + dz)
                if n not in final and n not in U:
                    final[n] = ground(n[0], n[1], target[x, z] + 60)
                    can[n] = False
        changed = True
        while changed:
            changed = False
            for c in target:
                if not can[c] or kind[c] == 'wall':
                    continue
                lim = min((final[n] for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1))
                           if n in final and n not in U and not can.get(n, False)), default=10 ** 6) + 1
                v = max(cur[c], min(final[c], lim))
                if v != final[c]:
                    final[c] = v
                    changed = True
        for (x, z) in target:
            t, y = final[x, z], cur[x, z]
            if not can[x, z] or y >= t:
                continue
            if 'log' in (w.get(x, y + 1, z) or ''):
                trees.append((x, y + 1, z))
            for yy in range(y + 1, t + 1):
                if kind[x, z] == 'wall':
                    after = wall
                else:
                    after = GRASS if yy == t else DIRT
                s = w.get(x, yy, z)
                if is_veg(s):
                    continue           # handled with the tree
                put(x, yy, z, after)
            top = w.get(x, y, z)
            if base(top) == 'minecraft:grass_block':
                rows[x, y, z] = [x, y, z, top, DIRT]
            if kind[x, z] == 'bench':
                benches.append((x, t, z, benchpos.get((x, z), 2), site['id']))
        site['_bbox_for_density'] = site['bbox']
    # trees on filled ground go whole
    removed = set()
    for tx, ty, tz in trees:
        q = deque([(tx, ty, tz)])
        while q:
            c = q.popleft()
            if c in removed or abs(c[0] - tx) > 3 or abs(c[2] - tz) > 3 or c[1] - ty > 20:
                continue
            s = w.get(*c)
            if not s or not ('_log' in s or '_wood' in s):
                continue
            removed.add(c)
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q.append((c[0] + d[0], c[1] + d[1], c[2] + d[2]))
    for c in removed:
        rows[c] = [*c, w.get(*c), 'minecraft:air']

    def near_log(p, mine, r=4):
        best = 99
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    q = (p[0] + dx, p[1] + dy, p[2] + dz)
                    s = w.get(*q)
                    if s and ('_log' in s or '_wood' in s) and ((q in removed) == mine):
                        best = min(best, max(abs(dx), abs(dy), abs(dz)))
        return best

    leaves = set()
    for lx, ly, lz in removed:
        for dx in range(-3, 4):
            for dy in range(-2, 4):
                for dz in range(-3, 4):
                    q = (lx + dx, ly + dy, lz + dz)
                    s = w.get(*q)
                    if s and 'leaves' in s and q not in rows:
                        leaves.add(q)
    for q in leaves:
        if near_log(q, True) <= near_log(q, False):
            rows[q] = [*q, w.get(*q), 'minecraft:air']
    plant(w, sites, benches, rows)
    for r in rows.values():
        if w.block_entity(r[0], r[1], r[2]):
            raise SystemExit(f'block entity at {r[:3]}')
    return list(rows.values())


if __name__ == '__main__':
    sites = json.load(open(sys.argv[1], encoding='utf8'))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    A = np.load(HERE / sys.argv[3]) if len(sys.argv) > 3 else np.load(HERE / 'float_new.npy')
    w = World(REGION)
    rows = plan(w, sites, A)

    def inside(r, site):
        if 'write' in site:
            x0, z0, x1, z1 = site['write']
        else:
            x0, z0, x1, z1 = site['bbox'][0] - 30, site['bbox'][2] - 30, site['bbox'][3] + 30, site['bbox'][5] + 30
        return x0 <= r[0] <= x1 and z0 <= r[2] <= z1
    rows = [r for r in rows if any(inside(r, s) for s in sites)]
    for site in sites:
        x0, y0, z0, x1, y1, z1 = site['bbox']
        mine = [r for r in rows if inside(r, site)]
        kinds = Counter(short(r[3]) + '->' + short(r[4]) for r in mine)
        site['cells_near'] = len(mine)
        print(site['id'], site['bbox'], 'edge', site['edge_cols'], 'terrace edge', site['terrace_edge_cols'], 'max drop', site['max_drop'],
              len(mine), kinds.most_common(6))
    (out / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (out / 'sites.json').write_text(json.dumps(sites, ensure_ascii=False, indent=1), 'utf8')
    print('total', len(rows))
