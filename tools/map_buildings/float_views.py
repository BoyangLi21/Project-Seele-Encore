"""Side views of floating pieces: look at the deepest edge cell of each piece from outside, plus an aerial look."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))

HERE = Path(__file__).parent
G = json.load(open(HERE / 'float_groups.json', encoding='utf8'))
A = np.load(HERE / 'float.npy')
pick = G[:20] + [g for g in G if g['doors']][:12]
seen, sel = set(), []
for g in pick:
    k = tuple(g['bbox'])
    if k not in seen:
        seen.add(k)
        sel.append(g)
views = []
for n, g in enumerate(sel):
    x0, y0, z0, x1, y1, z1 = g['bbox']
    m = (A[:, 0] >= x0) & (A[:, 0] <= x1) & (A[:, 2] >= z0) & (A[:, 2] <= z1) & (A[:, 1] >= y0) & (A[:, 1] <= y1)
    cells = A[m]
    # distance to the bbox edge; prefer edge cells with a large gap
    edge = np.minimum.reduce([cells[:, 0] - x0, x1 - cells[:, 0], cells[:, 2] - z0, z1 - cells[:, 2]])
    score = cells[:, 3] - 3 * edge
    c = cells[int(np.argmax(score))]
    x, y, z, gap = int(c[0]), int(c[1]), int(c[2]), int(c[3])
    d = {(x - x0): (-1, 0), (x1 - x): (1, 0), (z - z0): (0, -1), (z1 - z): (0, 1)}
    dx, dz = d[min(d)]
    g['view_id'] = f'F{n + 1:02d}'
    g['view_cell'] = [x, y, z, gap]
    views.append(dict(name=f'{g["view_id"]}-side', target=[x, y - gap // 2 - 1, z], dir=[dx, dz], dist=max(10, gap + 6), rise=1))
    views.append(dict(name=f'{g["view_id"]}-air', target=[x, y, z], dir=[dx + 0.3, dz + 0.3], dist=28, rise=22))
json.dump(sel, open(HERE / 'float_selected.json', 'w', encoding='utf8'), ensure_ascii=False, indent=0)
json.dump(views, open(sys.argv[1], 'w'), indent=0)
print(len(sel), len(views))
