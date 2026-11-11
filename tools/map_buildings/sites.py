"""Split the E5 candidate groups into houses and write the site table with camera views."""
import json, math, sys
from collections import Counter, deque
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import short, FACING, is_natural
from cluster import zone_of, nearest

HERE = Path(__file__).parent
w = World(REGION)
F = np.load(HERE / 'fill_room.npy')
D = json.load(open(HERE / 'doors.json'))
G = json.load(open(HERE / 'groups.json'))
zones = json.load(open(HERE / 'zones.json'))
stations = json.load(open(HERE / 'stations.json', encoding='utf8'))
sel = [g for g in G if g['fill'] >= 20 or g['doors'] or g['glass'] >= 5]

houses = []
for gi, g in enumerate(sel):
    x0, y0, z0, x1, y1, z1 = g['bbox']
    m = (F[:, 0] >= x0) & (F[:, 0] <= x1) & (F[:, 2] >= z0) & (F[:, 2] <= z1)
    cols = {}
    for x, y, z, _ in F[m].tolist():
        cols.setdefault((x, z), []).append(y)
    seen = set()
    comps = []
    for c in cols:
        if c in seen:
            continue
        q, comp = deque([c]), []
        seen.add(c)
        while q:
            a = q.popleft()
            comp.append(a)
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    n = (a[0] + dx, a[1] + dz)
                    if n in cols and n not in seen:
                        seen.add(n)
                        q.append(n)
        comps.append(comp)
    gdoors = [d for d in D if x0 - 4 <= d['pos'][0] <= x1 + 4 and z0 - 4 <= d['pos'][2] <= z1 + 4 and y0 - 4 <= d['pos'][1] <= y1 + 4
              and any((d['sides'][k]['blocked'] or d['sides'][k]['step']) and any(d['sides'][k]['natural'][:2]) for k in ('front', 'back'))]
    if not comps:
        comps = [[]]
    for comp in comps:
        if comp:
            xs = [c[0] for c in comp]; zs = [c[1] for c in comp]
            ys = [y for c in comp for y in cols[c]]
            bx0, bz0, bx1, bz1 = min(xs), min(zs), max(xs), max(zs)
            floors = Counter(min(cols[c]) - 1 for c in comp)
            floor = floors.most_common(1)[0][0]
            fill_n = len(ys)
            mats = Counter(short(w.get(c[0], y, c[1])) for c in comp[:200] for y in cols[c])
        else:
            bx0, bz0, bx1, bz1 = x0, z0, x1, z1
            floor, fill_n, mats, ys = y0, 0, Counter(), [y0, y1]
        hd = [d for d in gdoors if bx0 - 3 <= d['pos'][0] <= bx1 + 3 and bz0 - 3 <= d['pos'][2] <= bz1 + 3]
        if not comp:
            hd = gdoors
        if fill_n < 15 and not hd and g['glass'] < 5:
            continue
        houses.append(dict(group=gi, bbox=[bx0, bz0, bx1, bz1], ymin=min(ys), ymax=max(ys), floor=floor, fill=fill_n,
                           mats=dict(mats.most_common(3)), doors=[d['pos'] for d in hd], door_facing=[d['facing'] for d in hd],
                           group_bbox=g['bbox'], group_glass=g['glass'], group_wall=g['wall']))
for n, h in enumerate(houses):
    bx0, bz0, bx1, bz1 = h['bbox']
    cx, cz = (bx0 + bx1) // 2, (bz0 + bz1) // 2
    h['id'] = f'E5-{n + 1:03d}'
    h['zone'] = zone_of(cx, cz, zones)
    h['station'] = nearest(cx, h['floor'], cz, stations)
print(len(houses), 'houses')
for h in houses:
    print(h['id'], h['bbox'], 'floor', h['floor'], 'y', h['ymin'], h['ymax'], 'fill', h['fill'], h['mats'], 'doors', len(h['doors']), h['station'])
json.dump(houses, open(HERE / 'houses.json', 'w', encoding='utf8'), ensure_ascii=False, indent=0)
