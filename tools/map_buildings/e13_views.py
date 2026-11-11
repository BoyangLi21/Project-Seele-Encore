"""Side and aerial views for E13 sites: the deepest exposed edge cell of each, seen from outside.

e13_views.py <sites.json> <views out> [float file]
"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))

HERE = Path(__file__).parent
sites = json.load(open(sys.argv[1], encoding='utf8'))
A = np.load(HERE / (sys.argv[3] if len(sys.argv) > 3 else 'float.npy'))
views = []
for s in sites:
    x0, y0, z0, x1, y1, z1 = s['bbox']
    if 'write' in s:
        wx0, wz0, wx1, wz1 = s['write']
    else:
        wx0, wz0, wx1, wz1 = x0, z0, x1, z1
    m = (A[:, 0] >= max(x0, wx0)) & (A[:, 0] <= min(x1, wx1)) & (A[:, 2] >= max(z0, wz0)) & (A[:, 2] <= min(z1, wz1)) & (A[:, 1] >= y0) & (A[:, 1] <= y1)
    c = A[m]
    if not len(c):
        continue
    cols = {(int(r[0]), int(r[2])) for r in c}
    best = None
    for r in c.tolist():
        x, y, z, gap = r[0], r[1], r[2], r[3]
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, z + dz) not in cols and (best is None or gap > best[3]):
                best = (x, y, z, gap, dx, dz)
    if best is None:
        continue
    x, y, z, gap, dx, dz = best
    views.append(dict(name=f"{s['id']}-side", target=[x, y - gap // 2 - 1, z], dir=[dx + 0.3 * dz, dz + 0.3 * dx], dist=max(18, gap + 10), rise=3, wait=100))
    views.append(dict(name=f"{s['id']}-air", target=[x, y, z], dir=[dx + 0.4, dz + 0.4], dist=max(34, gap + 20), rise=max(26, gap + 12), wait=100))
json.dump(views, open(sys.argv[2], 'w'), indent=0)
print(len(views))
