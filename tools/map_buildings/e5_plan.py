"""E5 rows: dig a buried building out of the terrain heaped on and into it.

Per site (bbox and floor height F, the paving the building stands on):
- interior: natural terrain enclosed by the building (fill.npy cells in the bbox) becomes air;
- outside: an apron of `apron` columns around the footprint is cut down to F, then a 1:1 slope
  climbs back to the surrounding ground; only the natural cells at the top of a column are cut,
  and a column stops at the first block that is not natural terrain (roads, paving, other
  buildings stay as they are and keep what they stand on);
- a cut column whose new top is dirt above F gets grass back; plants standing on a removed cell go too.
Rows [x, y, z, before, after]; cells with block entities are refused.
"""
import json, sys
from collections import deque
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World, AIR
from blocks import is_open, is_natural, base, short

VEG = ('leaves', '_log', '_wood', 'mushroom_block', 'vine', 'azalea')


def is_veg(s):
    return s is not None and any(k in base(s) for k in VEG)


def is_building(s):
    return s is not None and not is_open(s) and not is_natural(s) and not is_veg(s)


ROADLIKE = ('asphalt', 'trafficcraft', 'road', 'curb', 'lamp', 'sign', 'rail')


def wall_column(w, x, z, F):
    for y in range(F + 1, F + 4):
        s = w.get(x, y, z)
        if is_building(s) and not any(k in s for k in ROADLIKE):
            return True
    return False


def footprint(w, seed, F, limit=30):
    """Columns holding building blocks just above the floor, flooded (4-neighbour) from the seed box."""
    sx0, sz0, sx1, sz1 = seed
    start = [(x, z) for x in range(sx0 - 1, sx1 + 2) for z in range(sz0 - 1, sz1 + 2) if wall_column(w, x, z, F)]
    # the seed interior counts even where it is still full of terrain
    cols = {(x, z) for x in range(sx0, sx1 + 1) for z in range(sz0, sz1 + 1)}
    q = deque(start)
    cols |= set(start)
    while q:
        x, z = q.popleft()
        for n in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if n in cols or abs(n[0] - (sx0 + sx1) / 2) > limit or abs(n[1] - (sz0 + sz1) / 2) > limit:
                continue
            if wall_column(w, n[0], n[1], F):
                cols.add(n)
                q.append(n)
    return cols


def site_targets(w, site, fill, foot_floor, targets, interior, near):
    """Add one site's footprint floors, ring targets and interior fill cells to the shared maps."""
    F = site['floor']
    cols = footprint(w, site['seed'], F, site.get('limit', 30)) if 'seed' in site else None
    if cols:
        xs, zs = [c[0] for c in cols], [c[1] for c in cols]
        site['bbox'] = [min(xs), min(zs), max(xs), max(zs)]
    else:
        x0, z0, x1, z1 = site['bbox']
        cols = {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) if wall_column(w, x, z, F)}
    x0, z0, x1, z1 = site['bbox']
    apron = site.get('apron', 2)
    reach = site.get('slope', 8)
    for c in cols:
        foot_floor[c] = min(foot_floor.get(c, 10 ** 6), F)
    dist = {c: 0 for c in cols}
    q = deque(cols)
    while q:
        c = q.popleft()
        if dist[c] >= apron + reach:
            continue
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                n = (c[0] + dx, c[1] + dz)
                if n not in dist:
                    dist[n] = dist[c] + 1
                    q.append(n)
    for c, d in dist.items():
        if d:
            t = F if d <= apron else F + (d - apron)
            targets[c] = min(targets.get(c, 10 ** 6), t)
            if d <= apron:
                near[c] = True
    inside = fill[(fill[:, 0] >= x0) & (fill[:, 0] <= x1) & (fill[:, 2] >= z0) & (fill[:, 2] <= z1) & (fill[:, 1] > F)]
    interior.update((x, y, z) for x, y, z, _ in inside.tolist())


def plan(w, sites, fill):
    foot_floor, targets, interior, near = {}, {}, set(), {}
    for site in sites:
        site_targets(w, site, fill, foot_floor, targets, interior, near)
    rows = {}
    trees = []

    def cut(x, y, z, before, after='minecraft:air'):
        rows[x, y, z] = [x, y, z, before, after]

    for x, y, z in interior:
        s = w.get(x, y, z)
        if is_natural(s):
            cut(x, y, z, s)
    # inside a footprint (porches, eaves, corners): every natural cell above the floor
    for (x, z), F in foot_floor.items():
        for y in range(F + 1, F + 41):
            s = w.get(x, y, z)
            if is_natural(s):
                cut(x, y, z, s)
    # apron and slope: cut the natural cells at the top of each column down to its target
    for (x, z), target in targets.items():
        if (x, z) in foot_floor:
            continue
        if near.get((x, z)):
            # next to the house, from the floor up: the terrain run above the target goes unless
            # something stands on it (a lamp, a fence post) or it holds up a wall of another building
            y = target + 1
            run = []
            while y <= target + 12 and is_natural(w.get(x, y, z)):
                run.append(y)
                y += 1
            if not run:
                continue
            cap = w.get(x, y, z)
            ok = is_open(cap) or is_veg(cap)
            if not ok and is_building(cap) and not any(k in cap for k in ROADLIKE):
                sideways = any(is_building(w.get(x + dx, y, z + dz)) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                wall = sum(is_building(w.get(x, y + k, z)) for k in range(3)) >= 2
                ok = sideways and not wall
            if ok:
                for yy in run:
                    cut(x, yy, z, w.get(x, yy, z))
                if 'log' in (cap or ''):
                    trees.append((x, y, z))
            continue
        y = target + 40
        while y > target and (is_open(w.get(x, y, z)) or is_veg(w.get(x, y, z))):
            y -= 1
        col_top = y
        trunk = 'log' in (w.get(x, y + 1, z) or '')
        while y > target:
            s = w.get(x, y, z)
            if not is_natural(s):
                break
            cut(x, y, z, s)
            y -= 1
        if trunk and y < col_top:
            trees.append((x, col_top + 1, z))
    # trees whose ground was cut go whole: connected logs, then the leaves nearer to them than to a kept log
    removed_logs = set()
    for tx, ty, tz in trees:
        logs, q = set(), deque([(tx, ty, tz)])
        while q:
            c = q.popleft()
            if c in logs or abs(c[0] - tx) > 3 or abs(c[2] - tz) > 3 or c[1] - ty > 16:
                continue
            s = w.get(*c)
            if not s or not ('_log' in s or '_wood' in s):
                continue
            logs.add(c)
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q.append((c[0] + d[0], c[1] + d[1], c[2] + d[2]))
        removed_logs |= logs
    for c in removed_logs:
        cut(*c, w.get(*c))

    def nearest_log(p, pool, r):
        best = 99
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    q = (p[0] + dx, p[1] + dy, p[2] + dz)
                    s = w.get(*q)
                    if s and ('_log' in s or '_wood' in s) and ((q in removed_logs) == pool):
                        best = min(best, max(abs(dx), abs(dy), abs(dz)))
        return best

    candidates = set()
    for lx, ly, lz in removed_logs:
        for dx in range(-3, 4):
            for dy in range(-2, 4):
                for dz in range(-3, 4):
                    q = (lx + dx, ly + dy, lz + dz)
                    s = w.get(*q)
                    if s and 'leaves' in s and q not in rows:
                        candidates.add(q)
    for q in candidates:
        if nearest_log(q, True, 4) <= nearest_log(q, False, 4):
            cut(*q, w.get(*q))
    # plants left standing on removed cells, grass on the new tops
    for (x, y, z) in list(rows):
        above = w.get(x, y + 1, z)
        if above not in AIR and is_open(above) and (x, y + 1, z) not in rows and 'water' not in above:
            cut(x, y + 1, z, above)
            if base(above).endswith(('tall_grass', 'large_fern')) or 'half=lower' in above:
                up = w.get(x, y + 2, z)
                if up and 'half=upper' in up:
                    cut(x, y + 2, z, up)
    tops = {}
    for (x, y, z) in rows:
        if rows[x, y, z][4] == 'minecraft:air':
            tops[x, z] = min(tops.get((x, z), 10 ** 6), y)
    for (x, z), y in tops.items():
        below = w.get(x, y - 1, z)
        if (x, y - 1, z) not in rows and is_natural(below) and base(below) != 'minecraft:grass_block' and y - 1 >= min(foot_floor.get((x, z), 10 ** 6), targets.get((x, z), 10 ** 6)):
            cut(x, y - 1, z, below, 'minecraft:grass_block[snowy=false]')
    for r in rows.values():
        if w.block_entity(r[0], r[1], r[2]):
            raise SystemExit(f'block entity at {r[:3]}')
    return list(rows.values())




if __name__ == '__main__':
    sites = json.load(open(sys.argv[1], encoding='utf8'))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    fill = np.load(Path(__file__).parent / 'fill_room.npy')
    w = World(REGION)
    rows = plan(w, sites, fill)
    allrows = {tuple(r[:3]): r for r in rows}
    report = []
    for site in sites:
        x0, z0, x1, z1 = site['bbox']
        mine = [r for r in rows if x0 - 12 <= r[0] <= x1 + 12 and z0 - 12 <= r[2] <= z1 + 12]
        kinds = {}
        for r in mine:
            k = short(r[3]) + '->' + short(r[4])
            kinds[k] = kinds.get(k, 0) + 1
        report.append(dict(site=site['id'], bbox=site['bbox'], cells_near=len(mine), kinds=kinds))
        print(site['id'], site['bbox'], len(mine), sorted(kinds.items(), key=lambda kv: -kv[1])[:5])
    (out / 'rows.json').write_text(json.dumps(list(allrows.values())), 'utf8')
    (out / 'sites.json').write_text(json.dumps(sites, ensure_ascii=False, indent=1), 'utf8')
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf8')
    print('total', len(allrows))
