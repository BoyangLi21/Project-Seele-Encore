"""One R1 batch from the per-end decisions: connections, cut-backs and viewpoints.

connect: the end's route from plan_dead_end_options becomes a build_road_connection centreline whose
walking profile follows the ground within MAX_GRADE, pinned to the declared heights at both ends.
cut: the declared cells whose nearest skeleton cell lies on the spur part being taken up (end to the
junction, or to the last door) are taken up like R1-A: paving back to the natural top of the untouched
columns around, buried paving filled, the declaration dropped.
undeclare (取消声明): the same spur columns as a cut leave the declaration and no block changes (paving buried in the hill).
viewpoint: the end stays as a terminal; its outer edge cells that face water or a drop of 2 or more get a
stone brick wall on the footway, and a lantern on a wall post marks the end.
Writes connections.json (for build_road_connection), rows-cut.json, rows-view.json, network-cut.npz,
batch.json. Run build_road_connection on connections.json with network-cut.npz afterwards.
R1_CUT_INSTEAD=id,id in the environment turns those connections into cut-backs (a route found blocked by a structure).
usage: plan_road_r1_batch.py <capture> <network.npz> <skeleton.npy> <decisions.json> <options.json> <outdir> id [id ...]"""
import json
import math
import sys
from collections import Counter, deque
from pathlib import Path

import numpy as np
from scipy import ndimage

from plan_station_access_corridor import CapturedSurface
from verify_hakone_network_candidate import PAVEMENT

cap = CapturedSurface(sys.argv[1], partial=True)
net = np.load(sys.argv[2])
network = {k: net[k].copy() for k in net.files}
sk = np.load(sys.argv[3])
decisions = {d['id']: d for d in json.load(open(sys.argv[4], encoding='utf8'))}
options = {o['id']: o for o in json.load(open(sys.argv[5], encoding='utf8'))}
out = Path(sys.argv[6])
out.mkdir(parents=True, exist_ok=True)
ids = [int(a) for a in sys.argv[7:]]
ax, az = map(int, network['bounds'][:2])
cx, cz = map(int, cap.bounds[:2])
road, walk, g2 = network['road'], network['walk'], network['grade2']
top = cap.measured['top']
MAX_GRADE = 0.2
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
NATURAL = ('minecraft:grass_block', 'minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:stone', 'minecraft:gravel', 'minecraft:sand',
           'minecraft:podzol', 'minecraft:andesite', 'minecraft:granite', 'minecraft:diorite', 'minecraft:moss_block', 'minecraft:rooted_dirt')
PLANTS = ('grass', 'fern', 'flower', 'bush', 'dandelion', 'poppy', 'tulip', 'orchid', 'allium', 'bluet', 'daisy', 'cornflower', 'lily')
deg = ndimage.convolve(sk.astype(np.int16), np.ones((3, 3), np.int16), mode='constant') - 1


def name(s):
    return s.split('[')[0]


def paving(s):
    return s.startswith('trafficcraft:') or name(s) in PAVEMENT


def G(a, x, z, ox=ax, oz=az):
    return a[z - oz, x - ox]


def feet_at(x, z):
    return G(g2, x, z) / 2 + 1


def measured_feet(x, z):
    """Walking height of the paving actually at (x, z), near its declared height; the declared one if none."""
    near = feet_at(x, z)
    for y in range(math.floor(near) + 3, math.floor(near) - 4, -1):
        s = cap.state(x, y, z)
        if paving(s) and name(cap.state(x, y + 1, z)) in AIR:
            top = y + int(s.split('layers=')[1][0]) / 8 if 'layers=' in s else (y + .5 if 'type=bottom' in s else y + 1.0)
            if abs(top - near) <= 2.5:
                return top
    return near


# ---- connections
conns, report, failed = [], [], set(int(a) for a in __import__('os').environ.get('R1_CUT_INSTEAD', '').split(',') if a)
for i in ids:
    d, o = decisions[i], options[i]
    if d['decision'] not in ('接通', '架桥接通') or i in failed:
        continue
    c = o['connect']
    pts = [tuple(p) for p in c['route']]
    if pts[0] != (d['x'], d['z']):
        pts.insert(0, (d['x'], d['z']))
    seg = [math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(pts, pts[1:])]
    s = np.concatenate([[0], np.cumsum(seg)])
    ground = np.array([G(top, x, z, cx, cz) + 1.0 for x, z in pts])
    f0, f1 = measured_feet(*pts[0]), measured_feet(*pts[-1])     # what the new road will actually meet
    lo, hi = np.full(len(pts), -1e9), np.full(len(pts), 1e9)
    lo[0] = hi[0] = f0
    lo[-1] = hi[-1] = f1
    dist = np.abs(s[:, None] - s[None, :])
    for grade in (MAX_GRADE, 0.24):
        U = (hi[None, :] + grade * dist).min(1)
        L = (lo[None, :] - grade * dist).max(1)
        if (L <= U + 1e-9).all():
            break
    else:
        report.append(dict(id=i, decision=d['decision'], error='height difference too big along the drawn route: cut back instead'))
        failed.add(i)
        continue
    prof = np.clip(ground, L, U)
    # Limit the grade between neighbouring points too, sweeping both ways with the two ends fixed.
    seg = np.diff(s)
    for _ in range(200):
        before = prof.copy()
        for k in range(1, len(prof) - 1):
            prof[k] = np.clip(prof[k], prof[k - 1] - grade * seg[k - 1], prof[k - 1] + grade * seg[k - 1])
        for k in range(len(prof) - 2, 0, -1):
            prof[k] = np.clip(prof[k], prof[k + 1] - grade * seg[k], prof[k + 1] + grade * seg[k])
        if np.abs(prof - before).max() < 1e-6:
            break
    conns.append(dict(id=f'r1-{i}', points=[list(p) for p in pts], profile=[round(float(v) * 8) / 8 for v in prof], road=1.5, walk=1,
                      purpose=f"#{i} {d['why']}"))
    report.append(dict(id=i, decision=d['decision'], length=round(float(s[-1]), 1), feet=[f0, f1]))
json.dump(conns, open(out / 'connections.json', 'w', encoding='utf8'), ensure_ascii=False, indent=0)

# ---- cut-backs
dt_idx = ndimage.distance_transform_edt(~sk, return_distances=False, return_indices=True)


def spur(x, z):
    for r in range(6):
        hits = [(x + dx, z + dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1) if G(sk, x + dx, z + dz)]
        if hits:
            break
    else:
        return []
    path, prev, cur = [hits[0]], None, hits[0]
    while len(path) < 4000:
        nb = [(cur[0] + dx, cur[1] + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (dx or dz) and G(sk, cur[0] + dx, cur[1] + dz)
              and (cur[0] + dx, cur[1] + dz) != prev and (cur[0] + dx, cur[1] + dz) not in path[-3:]]
        if len(nb) != 1 or G(deg, *cur) >= 3:
            break
        prev, cur = cur, nb[0]
        path.append(cur)
    return path


def doors_along(path):
    found = {}
    for k, (x, z) in enumerate(path):
        f = math.floor(feet_at(x, z))
        for dx in range(-6, 7):
            for dz in range(-6, 7):
                for y in range(f - 1, f + 3):
                    try:
                        if name(cap.state(x + dx, y, z + dz)).endswith('_door'):
                            found.setdefault(k, (x + dx, y, z + dz))
                    except ValueError:
                        pass
    return found


def natural_top(x, y, z, skip):
    seen = Counter()
    for r in range(1, 9):     # wide cuts have only paving within three columns
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if max(abs(dx), abs(dz)) != r or (x + dx, z + dz) in skip:
                    continue
                # From well above, so an uphill neighbour gives its surface (grass) and not the rock inside the hill.
                for yy in range(y + 16, y - 5, -1):
                    n = name(cap.state(x + dx, yy, z + dz))
                    if n in AIR or n.endswith(PLANTS) or n.endswith(('_leaves', '_log')):
                        continue
                    if n in NATURAL:
                        seen['minecraft:grass_block[snowy=false]' if n == 'minecraft:grass_block' else n] += 1
                    break
        if seen:
            return seen.most_common(1)[0][0]
    return None


cut_rows, cut_report = {}, []
for i in ids:
    d = decisions[i]
    undeclare = d['decision'] == '取消声明'
    if d['decision'] == '拆除碎片':
        # A stray piece of declared road joined to nothing: all of it goes, not just the spur.
        pieces, _ = ndimage.label(road | walk, structure=np.ones((3, 3)))
        near = [(d['x'] + dx, d['z'] + dz) for r in range(4) for dx in range(-r, r + 1) for dz in range(-r, r + 1)
                if G(road, d['x'] + dx, d['z'] + dz) or G(walk, d['x'] + dx, d['z'] + dz)]
        if not near:
            cut_report.append(dict(id=i, error='no declared cell near the fragment'))
            continue
        lab = G(pieces, *near[0])
        zs, xs = np.nonzero(pieces == lab)
        if len(xs) > 2000:
            cut_report.append(dict(id=i, error=f'piece of {len(xs)} cells is not a fragment'))
            continue
        cols = {(int(x) + ax, int(z) + az) for x, z in zip(xs, zs)}
        path, doors = [], {}
    elif not (d['decision'].startswith('截回') or i in failed or undeclare):
        continue
    else:
        path = None
    if path is None:
        path = spur(d['x'], d['z'])
        if not path:
            cut_report.append(dict(id=i, error='no skeleton near the end'))
            continue
        # In plan view a tunnel road and the hill road over it share skeleton cells; stop where the height jumps.
        for k in range(1, len(path)):
            if abs(feet_at(*path[k]) - feet_at(*path[k - 1])) > 2:
                path = path[:k]
                break
        doors = doors_along(path)
        stop = min(doors) if doors else len(path) - 3       # leave the last cells before the junction to the junction road
        # Another end of the same piece is being connected in this batch: take up only this end's half.
        for j in ids:
            if j != i and decisions[j]['decision'] in ('接通', '架桥接通') and j not in failed:
                near = [k for k, p in enumerate(path) if abs(p[0] - decisions[j]['x']) + abs(p[1] - decisions[j]['z']) <= 4]
                if near:
                    stop = min(stop, max(0, near[0] // 2))
        taken = set(path[:max(0, stop)])
        cols = set()
        if taken:
            xs = [p[0] for p in path]
            zs = [p[1] for p in path]
            x0, x1, z0, z1 = min(xs) - 12, max(xs) + 12, min(zs) - 12, max(zs) + 12
            for z in range(z0, z1 + 1):
                for x in range(x0, x1 + 1):
                    if not (G(road, x, z) or G(walk, x, z)):
                        continue
                    nz, nx = dt_idx[:, z - az, x - ax]
                    q = (int(nx) + ax, int(nz) + az)
                    # A road passing over or under the spur (hill road over a tunnel) shares the plan view, not the height.
                    if q in taken and abs(feet_at(x, z) - feet_at(*q)) <= 3:
                        cols.add((x, z))
    n0 = len(cut_rows)
    for (x, z) in sorted(cols):
        if undeclare:
            walk[z - az, x - ax] = road[z - az, x - ax] = False
            continue
        f = feet_at(x, z)
        ys = [y for y in range(math.floor(f) - 3, math.floor(f) + 2) if paving(cap.state(x, y, z))]
        if ys:
            base = min(ys)
            above = name(cap.state(x, max(ys) + 1, z))
            buried = above in NATURAL
            for y in sorted(ys):
                s = cap.state(x, y, z)
                if buried:
                    under = name(cap.state(x, y - 1, z))
                    after = 'minecraft:stone' if under == 'minecraft:stone' and above == 'minecraft:stone' else 'minecraft:dirt'
                elif y == base:
                    below = name(cap.state(x, y - 1, z))
                    after = natural_top(x, y, z, cols) if below not in AIR else 'minecraft:air'
                    if after is None:
                        after = 'minecraft:grass_block[snowy=false]' if below in ('minecraft:dirt', 'minecraft:grass_block') else (below if below in NATURAL else 'minecraft:air')
                else:
                    after = 'minecraft:air'
                if s != after:
                    cut_rows[x, y, z] = [x, y, z, s, after]
        walk[z - az, x - ax] = road[z - az, x - ax] = False
    cut_report.append(dict(id=i, spur=len(path), kept_for_doors=bool(doors), columns=len(cols), cells=len(cut_rows) - n0))
json.dump(list(cut_rows.values()), open(out / 'rows-cut.json', 'w', encoding='utf8'))

# ---- viewpoints
view_rows, view_report = {}, []
for i in ids:
    d = decisions[i]
    if d['decision'] != '观景点':
        continue
    x0, z0 = d['x'], d['z']
    edge = []
    for x in range(x0 - 6, x0 + 7):
        for z in range(z0 - 6, z0 + 7):
            if not G(walk, x, z):
                continue
            f = math.floor(feet_at(x, z))
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (x + dx, z + dz)
                if G(walk, *q):
                    continue
                # Water or a drop of 2+ beside the paved edge.
                col = [name(cap.state(q[0], y, q[1])) for y in range(f - 3, f + 1)]
                wet = 'minecraft:water' in col
                drop = all(n in AIR or n == 'minecraft:water' for n in col[1:])
                if wet or drop:
                    edge.append((x, f, z))
                    break
    for (x, f, z) in edge:
        if name(cap.state(x, f, z)) in AIR:
            view_rows[x, f, z] = [x, f, z, cap.state(x, f, z), 'minecraft:stone_brick_wall[east=none,north=none,south=none,up=true,waterlogged=false,west=none]']
    if edge:
        x, f, z = min(edge, key=lambda p: math.hypot(p[0] - x0, p[2] - z0))
        if name(cap.state(x, f + 1, z)) in AIR:
            view_rows[x, f + 1, z] = [x, f + 1, z, cap.state(x, f + 1, z), 'minecraft:lantern[hanging=false,waterlogged=false]']
    view_report.append(dict(id=i, wall_cells=len(edge)))
json.dump(list(view_rows.values()), open(out / 'rows-view.json', 'w', encoding='utf8'))
np.savez_compressed(out / 'network-cut.npz', **network)
json.dump(dict(errors=[], connections=report, cuts=cut_report, viewpoints=view_report, cut_cells=len(cut_rows), view_cells=len(view_rows)),
          open(out / 'batch.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print(json.dumps(dict(connections=len(conns), cuts=len(cut_report), cut_cells=len(cut_rows), viewpoints=len(view_report), view_cells=len(view_rows)), ensure_ascii=False))
for r in cut_report + view_report:
    print(r)
