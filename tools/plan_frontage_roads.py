"""Frontage roads along a strip that cut a street grid: chain the cut street ends on each side of it.

Ends facing the same way (their spur heading within ~45 degrees) and within MAX_GAP of each other are joined
pairwise, each end to its nearest such neighbour on either side, without duplicates, so the ends form chains. Each join is routed on the cell grid
around built columns, water and declared cells (other than the two ends' own pieces), with a turn cost so
the road stays straight; the route becomes a build_road_connection centreline at the two ends' heights.
Writes connections.json and pairs.json.
usage: plan_frontage_roads.py <network.npz> <obstacles.npz> <ends.json> <outdir> [road_half] [walk]"""
import heapq
import json
import math
import sys
from pathlib import Path

import numpy as np

net = np.load(sys.argv[1])
obs = np.load(sys.argv[2])
ends = json.load(open(sys.argv[3], encoding='utf8'))
ends = ends['ends'] if isinstance(ends, dict) else ends
out = Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
RH = float(sys.argv[5]) if len(sys.argv) > 5 else 2
WW = int(sys.argv[6]) if len(sys.argv) > 6 else 1
ax, az = map(int, net['bounds'][:2])
ox, oz = map(int, obs['bounds'][:2])
road, walk, g2 = net['road'], net['walk'], net['grade2']
built, water = obs['built'], obs['water']
MAX_GAP, MAX_ROUTE, TURN = 110, 160, 0.6
END_FREE = 14   # around each end the route may run beside its own street


def heading(e):
    v = np.array([e['x'] - e['back'][0], e['z'] - e['back'][1]], float)
    return v / (np.linalg.norm(v) or 1)


pairs = set()
for i, a in enumerate(ends):
    ha = heading(a)
    side = {-1: None, 1: None}
    for j, b in enumerate(ends):
        if i == j:
            continue
        d = math.hypot(a['x'] - b['x'], a['z'] - b['z'])
        if d > MAX_GAP or ha @ heading(b) < .7:
            continue
        # The neighbour must lie to the side, not ahead across the strip; keep the nearest on each side.
        v = np.array([b['x'] - a['x'], b['z'] - a['z']], float) / d
        if abs(v @ ha) > .7:
            continue
        k = 1 if ha[0] * v[1] - ha[1] * v[0] > 0 else -1
        if side[k] is None or d < side[k][0]:
            side[k] = (d, j)
    for k in side.values():
        if k:
            pairs.add(tuple(sorted((i, k[1]))))


def route(a, b):
    """Grid route from end a to end b; cells beside declared roads other than near the ends are refused."""
    x0, z0, x1, z1 = a['x'], a['z'], b['x'], b['z']
    R = int(max(abs(x1 - x0), abs(z1 - z0)) / 2 + 30)
    cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
    W = 2 * R + 1

    def ok(x, z):
        if math.hypot(x - x0, z - z0) <= END_FREE or math.hypot(x - x1, z - z1) <= END_FREE:
            return True
        if built[z - oz, x - ox] or water[z - oz, x - ox]:
            return False
        # Keep the new road and its footways off existing declared cells.
        r = int(RH + WW + 1)
        return not (road[z - r - az:z + r + 1 - az, x - r - ax:x + r + 1 - ax].any() or walk[z - r - az:z + r + 1 - az, x - r - ax:x + r + 1 - ax].any())

    dist = {(x0, z0, 0, 0): 0.0}
    prev = {}
    heap = [(math.hypot(x1 - x0, z1 - z0), 0.0, x0, z0, 0, 0)]
    while heap:
        f, g, x, z, dx0, dz0 = heapq.heappop(heap)
        if (x, z) == (x1, z1):
            path, k = [], (x, z, dx0, dz0)
            while k in prev:
                path.append(k[:2])
                k = prev[k]
            path.append((x0, z0))
            return path[::-1], g
        if g > MAX_ROUTE * 2:
            break
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, nz = x + dx, z + dz
            if abs(nx - cx) > R or abs(nz - cz) > R or not ok(nx, nz):
                continue
            step = math.hypot(dx, dz) + (TURN if (dx0 or dz0) and (dx, dz) != (dx0, dz0) else 0)
            key = (nx, nz, dx, dz)
            if g + step < dist.get(key, 1e18):
                dist[key] = g + step
                prev[key] = (x, z, dx0, dz0)
                heapq.heappush(heap, (g + step + math.hypot(x1 - nx, z1 - nz), g + step, nx, nz, dx, dz))
    return None, None


def simplify(path):
    """Keep the corners of a grid path."""
    keep = [path[0]]
    for p, q, r in zip(path, path[1:], path[2:]):
        if (q[0] - p[0], q[1] - p[1]) != (r[0] - q[0], r[1] - q[1]):
            keep.append(q)
    keep.append(path[-1])
    return keep


conns, report = [], []
for i, j in sorted(pairs):
    a, b = ends[i], ends[j]
    path, cost = route(a, b)
    fa = g2[a['z'] - az, a['x'] - ax] / 2 + 1
    fb = g2[b['z'] - az, b['x'] - ax] / 2 + 1
    if not path:
        report.append(dict(pair=[a['id'], b['id']], error='no route'))
        continue
    length = sum(math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in zip(path, path[1:]))
    if length > MAX_ROUTE:
        report.append(dict(pair=[a['id'], b['id']], error=f'route {length:.0f} too long'))
        continue
    pts = simplify(path)
    conns.append(dict(id=f"frontage-{a['id']}-{b['id']}", points=[list(p) for p in pts], feet=[fa, fb], road=RH, walk=WW,
                      purpose=f"frontage road along the green strip from ({a['x']},{a['z']}) to ({b['x']},{b['z']})"))
    report.append(dict(pair=[a['id'], b['id']], length=round(length, 1), corners=len(pts) - 2))
json.dump(conns, open(out / 'connections.json', 'w', encoding='utf8'), ensure_ascii=False, indent=0)
json.dump(report, open(out / 'pairs.json', 'w', encoding='utf8'), ensure_ascii=False, indent=0)
print(len(ends), 'ends', len(pairs), 'pairs', len(conns), 'routed', sum(1 for r in report if 'error' in r), 'failed')
