"""Group floating underside cells into pieces and describe each (size, gap, materials, doors on it)."""
import json, sys
from collections import Counter, defaultdict, deque
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import short
from cluster import zone_of, nearest

HERE = Path(__file__).parent
A = np.load(HERE / 'float.npy')
cells = {}
for x, y, z, g, gr, gy in A.tolist():
    cells[(x, y, z)] = (g, gr, gy)
by_col = defaultdict(list)
for (x, y, z) in cells:
    by_col[x, z].append(y)
seen, comps = set(), []
for c in cells:
    if c in seen:
        continue
    q, comp = deque([c]), []
    seen.add(c)
    while q:
        x, y, z = q.popleft()
        comp.append((x, y, z))
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for yy in by_col.get((x + dx, z + dz), ()):
                    if abs(yy - y) <= 2 and (x + dx, yy, z + dz) not in seen:
                        seen.add((x + dx, yy, z + dz))
                        q.append((x + dx, yy, z + dz))
    comps.append(comp)
doors = json.load(open(HERE / 'doors.json'))
zones = json.load(open(HERE / 'zones.json'))
stations = json.load(open(HERE / 'stations.json', encoding='utf8'))
w = World(REGION)
ROAD = ('asphalt', 'trafficcraft', 'rail', 'road', 'track', 'ballast', 'sleeper', 'bridge', 'guideway', 'catenary')
out = []
for comp in comps:
    if len(comp) < 6:
        continue
    xs = [c[0] for c in comp]; ys = [c[1] for c in comp]; zs = [c[2] for c in comp]
    gaps = [cells[c][0] for c in comp]
    water = sum(cells[c][1] == 5 for c in comp)
    bx0, bx1, bz0, bz1 = min(xs), max(xs), min(zs), max(zs)
    mats = Counter(short(w.get(*c)) for c in comp[:400])
    roadlike = sum(v for k, v in mats.items() if any(r in k for r in ROAD)) / max(1, sum(mats.values()))
    dz = [d['pos'] for d in doors if bx0 <= d['pos'][0] <= bx1 and bz0 <= d['pos'][2] <= bz1 and min(ys) <= d['pos'][1] <= max(ys) + 8]
    cols = len({(c[0], c[2]) for c in comp})
    span = max(bx1 - bx0, bz1 - bz0) + 1
    width = min(bx1 - bx0, bz1 - bz0) + 1
    cx, cz = (bx0 + bx1) // 2, (bz0 + bz1) // 2
    out.append(dict(bbox=[bx0, min(ys), bz0, bx1, max(ys), bz1], cells=len(comp), cols=cols, span=span, width=width,
                    gap_med=float(np.median(gaps)), gap_max=max(gaps), gap_min=min(gaps), water=water, roadlike=round(roadlike, 2),
                    mats=dict(mats.most_common(4)), doors=dz, zone=zone_of(cx, cz, zones), station=nearest(cx, min(ys), cz, stations)))
out.sort(key=lambda o: -o['cols'])
json.dump(out, open(HERE / 'float_groups.json', 'w', encoding='utf8'), ensure_ascii=False)
print(len(comps), 'pieces,', len(out), 'with 6+ cells')
for o in out[:int(sys.argv[1]) if len(sys.argv) > 1 else 60]:
    print(o['bbox'], 'cols', o['cols'], 'w', o['width'], 'gap', o['gap_min'], o['gap_med'], o['gap_max'], 'water', o['water'], 'road', o['roadlike'], 'doors', len(o['doors']), o['mats'], o['station'][0])
