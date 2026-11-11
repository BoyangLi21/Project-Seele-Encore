"""R1: sort each dead end into reasonable terminal / map boundary / unexplained, from the blocks around it.
usage: road_dead_ends_classify.py <capture> <network.npz> <ends.json> <out.json>"""
import json
import sys
from collections import Counter

import numpy as np
from scipy import ndimage

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
net = np.load(sys.argv[2])
ends = json.load(open(sys.argv[3], encoding='utf8'))['ends']
ax, az = map(int, net['bounds'][:2])
m = cap.measured
cx, cz = map(int, cap.bounds[:2])
full = m['full'].astype(bool)
# Distance (blocks) from every column to the nearest column outside the fully generated map.
edge_dist = ndimage.distance_transform_edt(np.pad(full, 1, constant_values=False))[1:-1, 1:-1]
road, walk, g2 = net['road'], net['walk'], net['grade2']
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
SOFT = ('grass', 'fern', 'flower', 'snow', 'bush', 'torch', 'lantern', 'sign', 'button', 'carpet', 'rail', 'pressure_plate', 'vine', 'leaves')


def name(s):
    return s.split('[')[0]


def scan(x, z, feet, r, y0, y1):
    c = Counter()
    for dx in range(-r, r + 1):
        for dz in range(-r, r + 1):
            for y in range(int(feet) + y0, int(feet) + y1):
                try:
                    n = name(cap.state(x + dx, y, z + dz))
                except ValueError:
                    c['outside'] += 1
                    continue
                if n in AIR:
                    continue
                if n.startswith('mtr:') or 'platform' in n or 'station' in n:
                    c['station'] += 1
                if n.endswith('_door') or n.endswith('door'):
                    c['door'] += 1
                if n in ('minecraft:water', 'minecraft:bubble_column') or 'kelp' in n or 'seagrass' in n:
                    c['water'] += 1
                if n.startswith('trafficcraft:'):
                    c['tc'] += 1
    return c


rows = []
for i, e in enumerate(ends):
    x, z = e['x'], e['z']
    iz, ix = z - az, x - ax
    feet = g2[iz, ix] / 2 + 1
    ed = float(edge_dist[z - cz, x - cx]) if 0 <= z - cz < full.shape[0] and 0 <= x - cx < full.shape[1] else 0.0
    # Direction of the road at the end: from the point 8 back along the spur to the end.
    bx, bz = e['back']
    d = np.array([x - bx, z - bz], float)
    d = d / (np.linalg.norm(d) or 1)
    ahead = [(int(round(x + d[0] * k)), int(round(z + d[1] * k))) for k in range(1, 9)]
    walk_ahead = sum(1 for (px, pz) in ahead if walk[pz - az, px - ax] and not road[pz - az, px - ax])
    # Steps out of the generated map within 64 blocks straight ahead.
    out_ahead = next((k for k in range(1, 65) if not (0 <= int(round(z + d[1] * k)) - cz < full.shape[0] and 0 <= int(round(x + d[0] * k)) - cx < full.shape[1])
                      or not full[int(round(z + d[1] * k)) - cz, int(round(x + d[0] * k)) - cx]), None)
    near = scan(x, z, feet, 12, -3, 4)
    close = scan(x, z, feet, 4, -2, 4)
    # Cover: solid blocks over the end within 2..10 above feet (tunnel or building).
    cover = 0
    for y in range(int(feet) + 2, int(feet) + 11):
        n = name(cap.state(x, y, z))
        if n not in AIR and not n.endswith(SOFT):
            cover = y - int(feet)
            break
    paved7 = int(road[iz - 3:iz + 4, ix - 3:ix + 4].sum())
    walk7 = int((walk & ~road)[iz - 4:iz + 5, ix - 4:ix + 5].sum())
    reasons = []
    if ed <= 24 or (out_ahead and out_ahead <= 48):
        cls = 'boundary'
        reasons.append(f'map edge {ed:.0f} away' + (f', {out_ahead} ahead' if out_ahead else ''))
    else:
        if near['station'] >= 4:
            reasons.append('station')
        if close['door'] >= 1:
            reasons.append('door')
        if near['water'] >= 20:
            reasons.append('water/pier')
        if cover:
            reasons.append(f'covered +{cover}')
        if paved7 >= 35:
            reasons.append('wide paved end')
        if walk_ahead >= 3 or walk7 >= 20:
            reasons.append('continues as footway')
        cls = 'terminal' if reasons else 'unexplained'
    rows.append(dict(e, id=i, feet=float(feet), cls=cls, why=reasons, edge=round(ed), out_ahead=out_ahead, cover=cover, paved7=paved7, walk7=walk7,
                     walk_ahead=walk_ahead, near={k: v for k, v in near.items()}, close={k: v for k, v in close.items()}))
json.dump(dict(ends=rows), open(sys.argv[4], 'w', encoding='utf8'), ensure_ascii=False, indent=0)
print(Counter(r['cls'] for r in rows))
print(Counter(w.split(' ')[0] for r in rows if r['cls'] == 'terminal' for w in r['why']))
