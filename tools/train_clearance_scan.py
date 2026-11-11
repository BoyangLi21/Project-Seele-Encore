"""Train clearance on a capture, using the E8 rail samples.
Envelope (from E8): body ry+1..ry+3.8 within 1.3 of the rail centre line, underbody ry+0.25..ry+1 within 0.9,
roof ry+3.8..ry+4.6 within 1.3. Distance is from the rail line to the nearest edge of the block's square.
usage: train_clearance_scan.py <capture> x0 z0 x1 z1 <out.json>"""
import json
import sys

import numpy as np
from scipy.spatial import cKDTree

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
X0, Z0, X1, Z1 = map(int, sys.argv[2:6])
samples = json.load(open('F:/eva/.claude/map-work/e8/run3/samples.json', encoding='utf8'))
PASS = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air', 'minecraft:light', 'mtr:rail', 'minecraft:rail')
pts, rid = [], []
for s in samples:
    p = np.array(s['points'])
    m = (p[:, 0] >= X0 - 3) & (p[:, 0] <= X1 + 3) & (p[:, 2] >= Z0 - 3) & (p[:, 2] <= Z1 + 3)
    if m.any():
        pts.append(p[m])
        rid += [s['file']] * int(m.sum())
pts = np.concatenate(pts)
tree = cKDTree(pts[:, [0, 2]])
rails = sorted(set(rid))
hits = []
cols = set()
for (x, ry, z) in pts:
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            cols.add((int(np.floor(x)) + dx, int(np.floor(z)) + dz))
for (bx, bz) in sorted(cols):
    # Nearest point on the line to the block square: sample the square's edge and centre.
    q = np.array([[bx + u, bz + v] for u in (0, .25, .5, .75, 1) for v in (0, .25, .5, .75, 1)])
    d, i = tree.query(q)
    k = int(np.argmin(d))
    dist, near = float(d[k]), int(i[k])
    if dist >= 1.3:
        continue
    ry = float(pts[near, 1])
    for y in range(int(np.floor(ry)), int(np.ceil(ry + 4.6))):
        st = cap.state(bx, y, bz)
        name = st.split('[')[0]
        if name in PASS or name.startswith('mtr:'):
            continue
        lo, hi = y, y + 1
        if name.endswith('_slab') and 'type=bottom' in st:
            hi = y + .5
        if 'layers=' in st and name.startswith('trafficcraft:'):
            hi = y + int(st.split('layers=')[1][0]) / 8
        band = None
        if dist < 1.3 and hi > ry + 1 and lo < ry + 3.8:
            band = 'body'
        elif dist < 0.9 and hi > ry + .25 and lo < ry + 1:
            band = 'under'
        elif dist < 1.3 and hi > ry + 3.8 and lo < ry + 4.6:
            band = 'roof'
        if band:
            hits.append(dict(x=bx, y=y, z=bz, state=st, band=band, edge=round(dist, 2), ry=round(ry, 2), rail=rid[near]))
json.dump(dict(rails=rails, samples=len(pts), hits=hits), open(sys.argv[6], 'w', encoding='utf8'), ensure_ascii=False, indent=0)
from collections import Counter
print(len(rails), 'rails', len(pts), 'samples', len(hits), 'hits', Counter(h['band'] for h in hits), Counter(h['state'].split('[')[0] for h in hits).most_common(8))
for h in hits[:40]:
    print(h)
