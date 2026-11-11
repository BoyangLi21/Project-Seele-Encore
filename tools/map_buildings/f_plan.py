"""Rows that ground a floating building: fill the gap under its floor and slope the ground up to its base.

Per site (a piece bbox from float_ranked.json): footprint = columns whose underside is at the floor
level (within one cell of the most common underside height). Under the footprint every open cell
from the ground up to the floor becomes earth. Around it the ground is raised to meet the base:
at distance d the top may reach U - d (U = the floor underside of the nearest footprint column),
so the first ring is flush with the bottom of the base and the slope drops 1:1. Only open cells
(air, plants) are filled, only on columns whose top is natural terrain; trees, water, roads and
other buildings stop a column. New tops are grass, two cells of dirt under them, stone deeper.
"""
import json, sys
from collections import Counter, deque
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World, AIR
from blocks import is_open, is_natural, base, short
from e5_plan import is_veg

HERE = Path(__file__).parent
GRASS = 'minecraft:grass_block[snowy=false]'
DIRT = 'minecraft:dirt'
STONE = 'minecraft:stone'


def fillable(s):
    return s is not None and is_open(s) and 'water' not in s and 'lava' not in s


def plan(w, sites, A):
    under, targets, src = {}, {}, {}
    for site in sites:
        x0, y0, z0, x1, y1, z1 = site['bbox']
        m = (A[:, 0] >= x0) & (A[:, 0] <= x1) & (A[:, 2] >= z0) & (A[:, 2] <= z1) & (A[:, 1] >= y0) & (A[:, 1] <= y1)
        cells = A[m]
        floor = Counter(cells[:, 1].tolist()).most_common(1)[0][0]
        foot = {}
        for x, y, z, gap, gr, gy in cells.tolist():
            if y <= floor + 1 and gr == 1:
                foot[x, z] = min(foot.get((x, z), 10 ** 6), y)
        site['floor_underside'] = floor
        site['footprint_cols'] = len(foot)
        reach = site.get('slope', 10)
        for c, u in foot.items():
            under[c] = min(under.get(c, 10 ** 6), u)
        dist = {c: 0 for c in foot}
        near = dict(foot)
        q = deque(foot)
        while q:
            c = q.popleft()
            if dist[c] >= reach:
                continue
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    n = (c[0] + dx, c[1] + dz)
                    if n not in dist:
                        dist[n] = dist[c] + 1
                        near[n] = near[c]
                        q.append(n)
        for c, d in dist.items():
            if d and c not in foot:
                t = near[c] - d
                if t > targets.get(c, -10 ** 6):
                    targets[c] = t
    rows = {}

    def put(x, y, z, after):
        s = w.get(x, y, z)
        if fillable(s) and (x, y, z) not in rows:
            rows[x, y, z] = [x, y, z, s, after]

    # under the footprint: everything open from the ground to the floor
    for (x, z), u in under.items():
        y = u - 1
        col = []
        while y > u - 64 and fillable(w.get(x, y, z)):
            col.append(y)
            y -= 1
        if not is_natural(w.get(x, y, z)):
            continue                       # not standing over terrain (water, a road, a cave mouth): leave it
        # the outer ring of the footprint shows from outside where no slope can be raised (paths,
        # roads): continue the base itself down to the ground there, if it is a full block
        edge = any((x + dx, z + dz) not in under for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        plinth = w.get(x, u, z)
        full = plinth and not any(k in plinth for k in ('slab', 'stairs', 'wall', 'fence', 'pane', 'trapdoor', 'carpet', 'door',
                                                         'glass', 'gutter', 'button', 'sign', 'light', 'lamp', 'lantern', 'bars'))
        for yy in col:
            if edge and full:
                put(x, yy, z, plinth)
            else:
                put(x, yy, z, DIRT if u - 1 - yy <= 2 else STONE)   # dirt right under the floor, stone deeper
    # around it: raise the ground to the slope, never more than one cell above a neighbour that
    # cannot be raised (a road, a path, stairs, a tree), so no earth wall faces the street
    def ground(x, z, start):
        y = start
        while y > start - 104 and fillable(w.get(x, y, z)):
            y -= 1
        return y

    ring = {c: t for c, t in targets.items() if c not in under}
    cur, can = {}, {}
    for (x, z), t in ring.items():
        y = ground(x, z, t + 40)
        top = w.get(x, y, z)
        cur[x, z] = y
        can[x, z] = is_natural(top) and not is_veg(top) and all(fillable(w.get(x, yy, z)) for yy in range(y + 1, t + 1))
    final = {c: max(cur[c], ring[c]) if can[c] else cur[c] for c in ring}
    for (x, z) in list(ring):
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, z + dz)
            if n not in final and n not in under:
                final[n] = ground(n[0], n[1], ring[x, z] + 40)
                can[n] = False
    changed = True
    while changed:
        changed = False
        for c in ring:
            if not can[c]:
                continue
            lim = min((final[n] for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1))
                       if n in final and n not in under), default=10 ** 6) + 1
            v = max(cur[c], min(final[c], lim))
            if v != final[c]:
                final[c] = v
                changed = True
    for (x, z), t0 in ring.items():
        t = final[x, z]
        y = cur[x, z]
        top = w.get(x, y, z)
        if not can[x, z] or y >= t:
            continue
        # nothing that is not open between the ground and the target (tree trunks, leaves, structures)
        span = list(range(y + 1, t + 1))
        if any(not fillable(w.get(x, yy, z)) for yy in span):
            continue
        for yy in span:
            k = t - yy                     # 0 at the new top
            put(x, yy, z, GRASS if k == 0 else DIRT if k <= 2 else STONE)
        if base(top) == 'minecraft:grass_block' and span:
            rows[x, y, z] = [x, y, z, top, DIRT]   # the old turf is buried now
    for r in rows.values():
        if w.block_entity(r[0], r[1], r[2]):
            raise SystemExit(f'block entity at {r[:3]}')
    return list(rows.values())


if __name__ == '__main__':
    sites = json.load(open(sys.argv[1], encoding='utf8'))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    A = np.load(HERE / 'float.npy')
    w = World(REGION)
    rows = plan(w, sites, A)
    for site in sites:
        x0, y0, z0, x1, y1, z1 = site['bbox']
        mine = [r for r in rows if x0 - 12 <= r[0] <= x1 + 12 and z0 - 12 <= r[2] <= z1 + 12]
        kinds = Counter(short(r[3]) + '->' + short(r[4]) for r in mine)
        site['cells_near'] = len(mine)
        print(site['id'], site['bbox'], 'floor', site['floor_underside'], 'foot', site['footprint_cols'], len(mine), kinds.most_common(5))
    (out / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (out / 'sites.json').write_text(json.dumps(sites, ensure_ascii=False, indent=1), 'utf8')
    print('total', len(rows))
