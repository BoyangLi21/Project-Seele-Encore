"""Score floating pieces: house-like (walls stand on the floating floor) and exposed (the gap shows at the edge)."""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, short
from e5_plan import is_building

HERE = Path(__file__).parent
G = json.load(open(HERE / 'float_groups.json', encoding='utf8'))
A = np.load(HERE / 'float.npy')
w = World(REGION)
ROAD = ('asphalt', 'trafficcraft', 'rail', 'road', 'track', 'ballast', 'sleeper', 'guideway', 'catenary', 'platform')
cells_by_piece = []
idx = defaultdict(list)
for x, y, z, g, gr, gy in A.tolist():
    idx[x >> 4, z >> 4].append((x, y, z, g, gr, gy))
out = []
for g in G:
    if g['cols'] < 9:
        continue
    x0, y0, z0, x1, y1, z1 = g['bbox']
    cells = [c for cx in range(x0 >> 4, (x1 >> 4) + 1) for cz in range(z0 >> 4, (z1 >> 4) + 1) for c in idx[cx, cz]
             if x0 <= c[0] <= x1 and z0 <= c[2] <= z1 and y0 <= c[1] <= y1]
    cols = {(c[0], c[2]): c for c in cells}
    sample = list(cols.values())[:3000]
    walls = sum(is_building(w.get(x, y + 2, z)) and is_building(w.get(x, y + 3, z)) for x, y, z, *_ in sample[:1500]) / max(1, min(len(sample), 1500))
    road = sum(any(r in w.get(x, y, z) or r in (w.get(x, y + 1, z) or '') for r in ROAD) for x, y, z, *_ in sample[:800]) / max(1, min(len(sample), 800))
    exposed = []
    for (x, z), (_, y, _, gap, gr, gy) in cols.items():
        if gap < 1:
            continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, z + dz) in cols:
                continue
            s = w.get(x + dx, y - 1, z + dz)
            if is_open(s) and is_open(w.get(x + dx, y, z + dz)):
                exposed.append((x, y, z, gap))
                break
    water = g['water'] / max(1, g['cells'])
    g.update(walls=round(walls, 2), road=round(road, 2), exposed=len(exposed), exposed_gap=max([e[3] for e in exposed], default=0),
             exposed_cells=exposed[:2000], water_frac=round(water, 2))
    if road >= 0.3 or water > 0.3:
        g['kind'] = 'bridge'
    elif walls >= 0.08 and len(exposed) >= 3:
        g['kind'] = 'house'
    elif len(exposed) >= 3:
        g['kind'] = 'plate'
    else:
        g['kind'] = 'hidden'
    out.append(g)
json.dump(out, open(HERE / 'float_ranked.json', 'w', encoding='utf8'), ensure_ascii=False)
print(Counter(g['kind'] for g in out))
for g in sorted([g for g in out if g['kind'] == 'house'], key=lambda g: -g['exposed'])[:50]:
    print(g['bbox'], 'cols', g['cols'], 'walls', g['walls'], 'exp', g['exposed'], 'gapmax', g['exposed_gap'], 'doors', len(g['doors']), list(g['mats'])[:2], g['station'][0])
