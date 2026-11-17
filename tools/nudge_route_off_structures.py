"""Move connection centrelines clear of built columns (viaduct piers, walls) standing in the road's width.

Each centreline is resampled every 2 blocks with its profile interpolated along it. A column is built work
when three solid blocks that are not soil, plants or paving-on-the-ground stand from the walking height up.
Points (not the two ends) closer than CLEAR to any such column are pushed straight away from it, a block at
a time, then the line is smoothed once; the profile goes with the points. Connections left with a built
column inside the width are reported.
usage: nudge_route_off_structures.py <capture> <connections.json> <out.json> [clear]"""
import json
import math
import sys

import numpy as np

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
conns = json.load(open(sys.argv[2], encoding='utf8'))
CLEAR = float(sys.argv[4]) if len(sys.argv) > 4 else 3.5
SOFT = ('minecraft:air', 'minecraft:cave_air', 'minecraft:water', 'minecraft:grass', 'minecraft:short_grass', 'minecraft:tall_grass',
        'minecraft:fern', 'minecraft:large_fern', 'minecraft:snow')
SOIL = ('minecraft:grass_block', 'minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:stone', 'minecraft:gravel', 'minecraft:sand',
        'minecraft:podzol', 'minecraft:andesite', 'minecraft:granite', 'minecraft:diorite', 'minecraft:moss_block', 'minecraft:rooted_dirt')
LAMP = ('minecraft:iron_bars', 'minecraft:lantern', 'minecraft:end_rod')


def name(s):
    return s.split('[')[0]


def built(x, z, feet):
    run = 0
    for y in range(math.floor(feet), math.floor(feet) + 5):
        n = name(cap.state(x, y, z))
        if n in SOFT or n in SOIL or n in LAMP or n.endswith(('_leaves', '_log', 'flower', 'sapling')) or n.startswith('trafficcraft:'):
            run = 0
            continue
        run += 1
        if run >= 3:
            return True
    return False


out, report = [], []
for c in conns:
    P = np.array(c['points'], float) + .5      # block centres
    seg = np.hypot(*np.diff(P, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    prof = np.array(c['profile'], float) if c.get('profile') else None
    n = max(2, int(s[-1] // 2) + 1)
    ss = np.linspace(0, s[-1], n)
    pts = np.stack([np.interp(ss, s, P[:, 0]), np.interp(ss, s, P[:, 1])], 1)
    pr = np.interp(ss, s, prof) if prof is not None else None
    reach = c.get('road', 2) + c.get('walk', 1) + 1.5
    blocks = set()
    for (x, z), f in zip(pts, pr if pr is not None else [0] * n):
        for dx in range(-int(reach) - 2, int(reach) + 3):
            for dz in range(-int(reach) - 2, int(reach) + 3):
                q = (int(math.floor(x)) + dx, int(math.floor(z)) + dz)
                if q not in blocks and built(q[0], q[1], f):
                    blocks.add(q)
    B = np.array(sorted(blocks), float) + .5 if blocks else np.zeros((0, 2))
    moved = 0
    for _ in range(6):
        changed = False
        for k in range(1, n - 1):
            if not len(B):
                break
            d = np.hypot(*(B - pts[k]).T)
            j = int(np.argmin(d))
            if d[j] < CLEAR:
                v = pts[k] - B[j]
                v = v / (np.hypot(*v) or 1)
                pts[k] = pts[k] + v * (CLEAR - d[j] + .25)
                changed = True
                moved += 1
        if not changed:
            break
        pts[1:-1] = (pts[:-2] + 2 * pts[1:-1] + pts[2:]) / 4
    left = [list(map(int, b - .5)) for b in B if np.hypot(*(pts - b).T).min() < c.get('road', 2) + c.get('walk', 1) + .5]
    if not moved:
        out.append(c)
        report.append(dict(id=c['id'], built_columns_near=len(blocks), point_moves=0, built_left_in_width=len(left)))
        continue
    ip = [[int(math.floor(x)), int(math.floor(z))] for x, z in pts]
    ip = [p for k, p in enumerate(ip) if k == 0 or p != ip[k - 1]]
    nc = dict(c, points=ip)
    if pr is not None:
        # Profile along the moved line: interpolate by fraction of length, then keep each step within the grade.
        q = np.array(ip, float)
        sq = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(q, axis=0).T))])
        v = np.interp(sq / sq[-1] * s[-1], s, prof)
        lens = np.diff(sq)
        for _ in range(200):
            before = v.copy()
            for k in range(1, len(v) - 1):
                v[k] = np.clip(v[k], v[k - 1] - .24 * lens[k - 1], v[k - 1] + .24 * lens[k - 1])
            for k in range(len(v) - 2, 0, -1):
                v[k] = np.clip(v[k], v[k + 1] - .24 * lens[k], v[k + 1] + .24 * lens[k])
            if np.abs(v - before).max() < 1e-6:
                break
        nc['profile'] = [round(float(x) * 8) / 8 for x in v]
    out.append(nc)
    report.append(dict(id=c['id'], built_columns_near=len(blocks), point_moves=moved, built_left_in_width=len(left)))
json.dump(out, open(sys.argv[3], 'w', encoding='utf8'), ensure_ascii=False, indent=0)
for r in report:
    print(r)
