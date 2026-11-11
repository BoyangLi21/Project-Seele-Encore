"""Rail and path dead ends: what is ahead of them.

rail: the nearest rail sample within 20 blocks ahead of the end (45 degrees either side, within 30 in height); its height over the road (rail height
minus walking height), whether a declared road continues within 30 blocks beyond the rail on the same line,
and the suggested treatment: underpass when the rail is 5 or more above the road, else overpass when a
road continues beyond, else cut back.
path: follow old paving (smooth stone, slabs, stone bricks, gravel paths) from the end; report how far it
runs and whether it reaches a door, a station block or a declared road elsewhere within 300 steps.
usage: analyze_rail_path_ends.py <capture> <network.npz> <samples.json> <old-paving.npz> <ends.json> <out.json>"""
import json
import math
import sys
from collections import deque

import numpy as np
from scipy.spatial import cKDTree

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
net = np.load(sys.argv[2])
samples = json.load(open(sys.argv[3], encoding='utf8'))
op = np.load(sys.argv[4])
ends = [e for e in json.load(open(sys.argv[5], encoding='utf8')) if e['kind'] in ('rail', 'path')]
ax, az = map(int, net['bounds'][:2])
ox, oz = map(int, op['bounds'][:2])
road, walk, g2 = net['road'], net['walk'], net['grade2']
oldp = op['kind'] > 0
pts, rid = [], []
for s in samples:
    p = np.array(s['points'])
    pts.append(p)
    rid += [s['file']] * len(p)
pts = np.concatenate(pts)
tree = cKDTree(pts[:, [0, 2]])
rows = []
for e in ends:
    x0, z0, f = e['x'], e['z'], e['feet']
    d = np.array([x0 - e['back'][0], z0 - e['back'][1]], float)
    d /= np.linalg.norm(d) or 1
    if e['kind'] == 'rail':
        best = None
        c = np.array([x0 + .5, z0 + .5])
        for i in tree.query_ball_point(c, 20):
            v = pts[i, [0, 2]] - c
            r = float(np.hypot(*v))
            if r < 1e-6 or v @ d / r < .7 or abs(pts[i, 1] - f) > 30:
                continue
            if best is None or r < best[0]:
                best = (r, float(pts[i, 1]), rid[i])
        beyond = None
        if best:
            for t in range(int(best[0]) + 3, int(best[0]) + 31):
                x, z = int(round(x0 + d[0] * t)), int(round(z0 + d[1] * t))
                if road[z - az, x - ax]:
                    beyond = dict(at=[x, z], feet=g2[z - az, x - ax] / 2 + 1, distance=t)
                    break
        if not best:
            advice = 'no rail ahead within 20: re-check by eye'
        elif best[1] - f >= 5:
            advice = 'underpass (rail 5+ above the road)'
        elif beyond:
            advice = 'overpass or cut back (rail less than 5 above the road; road continues beyond)'
        else:
            advice = 'cut back (no road beyond the rail)'
        rows.append(dict(id=e['id'], kind='rail', x=x0, z=z0, feet=f, rail_ahead=best and dict(distance=best[0], rail_y=round(best[1], 2), rail=best[2][:16],
                         above_road=round(best[1] - f, 2)), beyond=beyond, advice=advice))
    else:
        start = [(x0 + dx, z0 + dz) for dx in range(-3, 4) for dz in range(-3, 4) if oldp[z0 + dz - oz, x0 + dx - ox]]
        seen, q = set(start), deque((p, 0) for p in start)
        reached, far = [], 0
        while q:
            (x, z), k = q.popleft()
            far = max(far, k)
            if k >= 300:
                continue
            if k > 10 and (road[z - az, x - ax] or walk[z - az, x - ax]) and math.hypot(x - x0, z - z0) > 15:
                reached.append(('declared road', [x, z]))
                break
            if k % 3 == 0:
                for dx in (-2, 0, 2):
                    for dz in (-2, 0, 2):
                        for y in range(math.floor(f) - 8, math.floor(f) + 10):
                            try:
                                n = cap.state(x + dx, y, z + dz).split('[')[0]
                            except ValueError:
                                continue
                            if n.endswith('_door') or n.startswith('mtr:'):
                                reached.append(('door' if n.endswith('_door') else 'station', [x + dx, y, z + dz]))
                                break
                        if reached:
                            break
                    if reached:
                        break
            if reached:
                break
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    p = (x + dx, z + dz)
                    if p not in seen and oldp[p[1] - oz, p[0] - ox]:
                        seen.add(p)
                        q.append((p, k + 1))
        rows.append(dict(id=e['id'], kind='path', x=x0, z=z0, feet=f, path_columns=len(seen), path_steps=far, reaches=reached[:1],
                         advice=('reasonable terminal: road turns into a path to the ' + reached[0][0]) if reached else 'cut back (the path leads nowhere)'))
    print(rows[-1], flush=True)
json.dump(rows, open(sys.argv[6], 'w', encoding='utf8'), ensure_ascii=False, indent=0, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
