"""Views for round 2: swallowed houses, look-at items (from inside, at buried glass), the south
building from its streets, the ladder door, and the E13 samples."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from shots import view_steps

HERE = Path(__file__).parent
views = []
deep = {b['id']: b for b in json.load(open(HERE / 'deep_check.json', encoding='utf8'))}
for i in ('B01', 'B03', 'B04', 'B05', 'B02', 'B06'):
    x0, z0, x1, z1 = deep[i]['bbox']
    views.append(dict(name=f'deep-{i}-air', target=[(x0 + x1) // 2, deep[i]['roof'], (z0 + z1) // 2], dir=[0.6, 1], dist=26, rise=20))
# look-at items: buried glass seen from the room behind it
W = np.load(HERE / 'walls_room.npy')
looks = {'B25': [432, 73, 16, 671, 80, 39], 'B26': [-190, 45, 82, -178, 64, 94], 'B27': [488, 105, 104, 495, 106, 119], 'B28': [664, 105, 112, 671, 109, 127]}
for k, (x0, y0, z0, x1, y1, z1) in looks.items():
    m = (W[:, 0] >= x0) & (W[:, 0] <= x1) & (W[:, 2] >= z0) & (W[:, 2] <= z1) & (W[:, 1] >= y0) & (W[:, 1] <= y1)
    cells = W[m]
    g = cells[cells[:, 8] == 1] if (cells[:, 8] == 1).any() else cells
    pick = g[np.linspace(0, len(g) - 1, min(3, len(g))).astype(int)] if len(g) else []
    for n, c in enumerate(pick):
        x, y, z, dx, dz = (int(v) for v in c[:5])
        views.append(dict(name=f'look-{k}-{n}', target=[x, y, z], dir=[-dx, -dz], dist=3, rise=0.2))
# the south building from its streets (west and north of it) and from above
for n, (d, dist) in enumerate((([-1, 0], 24), ([-1, -0.6], 30), ([0, -1], 24), ([-0.6, 1], 26))):
    views.append(dict(name=f'south-B07-street-{n}', target=[196, 86, 541], dir=d, dist=dist, rise=0.5, wait=80))
views.append(dict(name='south-B07-air', target=[196, 100, 541], dir=[-1, 0.3], dist=40, rise=28, wait=80))
views.append(dict(name='nerv-door-ladder', target=[24, -516, 254], dir=[1, 0], dist=3, rise=0.3))
for s in json.load(open('E:/eva-map-buildings/plans/e13-sites.json')):
    x0, y0, z0, x1, y1, z1 = s['bbox']
    cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
    views.append(dict(name=f'{s["id"]}-air', target=[cx, y0, cz], dir=[0.5, 1], dist=max(30, (x1 - x0) // 2), rise=max(24, (x1 - x0) // 3), wait=100))
    views.append(dict(name=f'{s["id"]}-side', target=[cx, y0 - 10, cz], dir=[1, 0.2] if (z1 - z0) > (x1 - x0) else [0.2, 1], dist=35, rise=2, wait=100))
json.dump(views, open('E:/eva-map-buildings/shots/round2-views.json', 'w'), indent=0)
b, a = [], []
for v in views:
    b += view_steps(v, 'r2before-')
json.dump(b, open('E:/eva-map-buildings/shots/r2-before.json', 'w'))
print(len(views))
