"""Group the E5 signals into buildings and print a summary.

Signals: walls.npy (building wall with terrain outside and a room inside, buried glass),
fill.npy (terrain inside a building enclosure), doors.json (blocked door thresholds).
"""
import json, math, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
G = 8          # clustering grid


def zone_of(x, z, zones):
    for zn in zones:
        b = zn['bounds']
        if b[0] <= x <= b[1] and b[2] <= z <= b[3] and zn['kind'] == 'district':
            return zn['id']
    return ''


def nearest(x, y, z, stations):
    best = min((s for s in stations if abs(s['y'] - y) < 60) or stations, key=lambda s: (s['x'] - x) ** 2 + (s['z'] - z) ** 2)
    return best['name'], int(math.hypot(best['x'] - x, best['z'] - z))


def load(min_depth=2, min_fill=1):
    W = np.load(HERE / 'walls_room.npy')
    F = np.load(HERE / 'fill_room.npy')
    D = json.load(open(HERE / 'doors.json'))
    wall = W[W[:, 8] == 0]
    glass = W[W[:, 8] == 1]
    doors = [d for d in D if d['pos'][1] > -128 and any(
        (d['sides'][k]['blocked'] or d['sides'][k]['step']) and any(d['sides'][k]['natural'][:2]) for k in ('front', 'back'))]
    return wall, glass, F, doors


def clusters(wall, glass, fill, doors):
    pts = defaultdict(lambda: dict(wall=0, glass=0, fill=0, doors=[], ys=[], cells=set()))
    for arr, key in ((wall, 'wall'), (glass, 'glass'), (fill, 'fill')):
        for r in arr:
            k = (int(r[0]) // G, int(r[2]) // G)
            pts[k][key] += 1
            pts[k]['ys'].append(int(r[1]))
    for d in doors:
        k = (d['pos'][0] // G, d['pos'][2] // G)
        pts[k]['doors'].append(d['pos'])
        pts[k]['ys'].append(d['pos'][1])
    # connected components over 8-neighbour grid cells
    seen, groups = set(), []
    for k in pts:
        if k in seen:
            continue
        stack, comp = [k], []
        seen.add(k)
        while stack:
            c = stack.pop()
            comp.append(c)
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    n = (c[0] + dx, c[1] + dz)
                    if n in pts and n not in seen:
                        seen.add(n)
                        stack.append(n)
        groups.append(comp)
    out = []
    for comp in groups:
        g = dict(wall=0, glass=0, fill=0, doors=[], ys=[])
        for c in comp:
            for key in ('wall', 'glass', 'fill'):
                g[key] += pts[c][key]
            g['doors'] += pts[c]['doors']
            g['ys'] += pts[c]['ys']
        xs = [c[0] * G for c in comp]
        zs = [c[1] * G for c in comp]
        g['bbox'] = [min(xs), min(g['ys']), min(zs), max(xs) + G - 1, max(g['ys']), max(zs) + G - 1]
        g['cells'] = len(comp)
        out.append(g)
    return out


if __name__ == '__main__':
    wall, glass, fill, doors = load()
    zones = json.load(open(HERE / 'zones.json'))
    stations = json.load(open(HERE / 'stations.json', encoding='utf8'))
    groups = clusters(wall, glass, fill, doors)
    groups.sort(key=lambda g: -(g['wall'] + g['glass'] + 3 * g['fill'] + 50 * len(g['doors'])))
    print('signals: wall', len(wall), 'glass', len(glass), 'fill', len(fill), 'doors', len(doors), 'groups', len(groups))
    for g in groups[:int(sys.argv[1]) if len(sys.argv) > 1 else 60]:
        b = g['bbox']
        cx, cz = (b[0] + b[3]) // 2, (b[2] + b[5]) // 2
        st = nearest(cx, (b[1] + b[4]) / 2, cz, stations)
        print(b, 'w', g['wall'], 'g', g['glass'], 'f', g['fill'], 'd', len(g['doors']), zone_of(cx, cz, zones), st)
    json.dump(groups, open(HERE / 'groups.json', 'w'))
