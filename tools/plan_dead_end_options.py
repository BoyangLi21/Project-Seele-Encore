"""Per dead end: a connect option (a route of at most MAX_ROUTE blocks to a road that closes a loop) and a
cut-back option (take the spur up back to its junction, or to the last door along it).

Routing runs on the soil-top grid around the end, avoiding built columns; water is allowed only for ends
marked river (it becomes bridge length). A target must be a declared road cell that the declared network
reaches from the end only the long way round (or not at all), so joining it closes a loop. The route's
walking profile follows the ground within MAX_GRADE, pinned to the declared heights at both ends; the
earthwork is the cut and fill between that profile and the ground over the road width.
Cut-back: the skeleton spur from the end to its junction; doors within 6 blocks of the spur stop it
early so their frontage stays. Cells = road and walk cells within the spur's reach x 2 blocks.
usage: plan_dead_end_options.py <capture> <network.npz> <obstacles.npz> <skeleton.npy> <ends.json> <out.json> [ids...]"""
import heapq
import json
import math
import sys
from collections import deque

import numpy as np
from scipy import ndimage

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
net = np.load(sys.argv[2])
obs = np.load(sys.argv[3])
sk = np.load(sys.argv[4])
ends = json.load(open(sys.argv[5], encoding='utf8'))
ends = ends['ends'] if isinstance(ends, dict) else ends
pick = set(map(int, sys.argv[7:]))
ax, az = map(int, net['bounds'][:2])
cx, cz = map(int, cap.bounds[:2])
road, walk, g2 = net['road'], net['walk'], net['grade2']
top = cap.measured['top']
built, water = obs['built'], obs['water']
MAX_ROUTE, MAX_GRADE, R, WIDTH = 150, 0.2, 160, 7
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
deg = ndimage.convolve(sk.astype(np.int16), np.ones((3, 3), np.int16), mode='constant') - 1
# R1_MIN_PIECE: a target must lie in a declared piece of at least this many cells; joining a stray fragment
# only moves the dead end (five such connections were withdrawn on 2026-11-12).
MIN_PIECE = int(__import__('os').environ.get('R1_MIN_PIECE', '0'))
if MIN_PIECE:
    piece, _ = ndimage.label(road | walk, structure=np.ones((3, 3)))
    piece_size = np.bincount(piece.ravel())


def G(a, x, z, ox=ax, oz=az):
    return a[z - oz, x - ox]


def spur_path(x, z):
    path, prev, cur = [(x, z)], None, (x, z)
    while len(path) < 4000:
        nb = [(cur[0] + dx, cur[1] + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (dx or dz) and G(sk, cur[0] + dx, cur[1] + dz)
              and (cur[0] + dx, cur[1] + dz) != prev and (cur[0] + dx, cur[1] + dz) not in path[-3:]]
        if len(nb) != 1 or G(deg, *cur) >= 3:
            break
        prev, cur = cur, nb[0]
        path.append(cur)
    return path


def nearest_sk(x, z):
    for d in range(6):
        for dx in range(-d, d + 1):
            for dz in range(-d, d + 1):
                if G(sk, x + dx, z + dz):
                    return x + dx, z + dz
    return x, z


def network_distance(x, z, limit):
    """Geodesic distance over declared road+walk from (x, z), up to limit, in a dict."""
    dist, q = {(x, z): 0}, deque([(x, z)])
    while q:
        p = q.popleft()
        if dist[p] >= limit:
            continue
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                n = (p[0] + dx, p[1] + dz)
                if n not in dist and (G(road, *n) or G(walk, *n)):
                    dist[n] = dist[p] + 1
                    q.append(n)
    return dist


def doors_near(cells):
    found = []
    for (x, z) in cells[::2]:
        f = math.floor(G(g2, x, z) / 2 + 1)
        for dx in range(-6, 7, 2):
            for dz in range(-6, 7, 2):
                for y in range(f - 1, f + 3):
                    try:
                        if cap.state(x + dx, y, z + dz).split('[')[0].endswith('_door'):
                            found.append((x, z))
                            break
                    except ValueError:
                        pass
    return found


def profile(ground, f0, f1):
    n = len(ground)
    d = np.arange(n)
    lo, hi = np.full(n, -1e9), np.full(n, 1e9)
    lo[0] = hi[0] = f0
    lo[-1] = hi[-1] = f1
    U = (hi[None, :] + MAX_GRADE * np.abs(d[:, None] - d[None, :])).min(1)
    L = (lo[None, :] - MAX_GRADE * np.abs(d[:, None] - d[None, :])).max(1)
    if (L > U + 1e-9).any():
        return None
    return np.clip(ground, L, U)


rows = []
for e in ends:
    if pick and e['id'] not in pick:
        continue
    x0, z0 = e['x'], e['z']
    f0 = float(e.get('feet', G(g2, x0, z0) / 2 + 1))
    # Cut-back.
    path = spur_path(*nearest_sk(x0, z0))
    doors = doors_near(path)
    stop = len(path)
    if doors:
        idx = {p: i for i, p in enumerate(path)}
        stop = min(idx[d] for d in doors)
    taken = path[:max(0, stop - 2)]
    reach = set()
    for (x, z) in taken:
        for dx in range(-4, 5):
            for dz in range(-4, 5):
                if (G(road, x + dx, z + dz) or G(walk, x + dx, z + dz)):
                    reach.add((x + dx, z + dz))
    cut = dict(spur=len(path), doors=len(doors), columns=len(reach), cells=2 * len(reach), to=('door' if doors else 'junction'))
    # Connect.
    near = network_distance(x0, z0, 4 * MAX_ROUTE)
    river = e.get('kind') == 'river'
    W = 2 * R + 1
    dist = np.full((W, W), np.inf)
    prev = np.full((W, W, 2), -1, np.int32)
    dist[R, R] = 0
    heap = [(0.0, R, R)]
    found = None
    while heap:
        dcost, i, j = heapq.heappop(heap)
        if dcost > dist[i, j] or dcost > MAX_ROUTE * 3:
            continue
        x, z = x0 + j - R, z0 + i - R
        r = math.hypot(i - R, j - R)
        if (i, j) != (R, R) and G(road, x, z) and r > 6 and near.get((x, z), 1e9) > 2 * r + 40 \
                and (not MIN_PIECE or piece_size[G(piece, x, z)] >= MIN_PIECE):
            found = (i, j)
            break
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if not (di or dj):
                    continue
                ni, nj = i + di, j + dj
                if not (0 <= ni < W and 0 <= nj < W):
                    continue
                nx, nz = x0 + nj - R, z0 + ni - R
                try:
                    b, w = G(built, nx, nz, cx, cz), G(water, nx, nz, cx, cz)
                    h0, h1 = G(top, x, z, cx, cz), G(top, nx, nz, cx, cz)
                except IndexError:
                    continue
                if b and not G(road, nx, nz):
                    continue
                if w and not river:
                    continue
                step = math.hypot(di, dj)
                c = step * (1 + 3 * max(0.0, abs(h1 - h0) / step - MAX_GRADE)) * (3 if w else 1)
                if dcost + c < dist[ni, nj]:
                    dist[ni, nj] = dcost + c
                    prev[ni, nj] = (i, j)
                    heapq.heappush(heap, (dcost + c, ni, nj))
    connect = None
    if found:
        cells, p = [], found
        while tuple(p) != (R, R):
            cells.append((x0 + p[1] - R, z0 + p[0] - R))
            p = tuple(prev[p[0], p[1]])
        cells.append((x0, z0))
        cells.reverse()
        length = sum(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(cells, cells[1:]))
        if length <= MAX_ROUTE:
            f1 = G(g2, *cells[-1]) / 2 + 1
            ground = np.array([G(top, x, z, cx, cz) + 1.0 for x, z in cells])
            prof = profile(ground, f0, f1)
            wet = sum(1 for x, z in cells if G(water, x, z, cx, cz))
            if prof is not None:
                earth = float(np.abs(prof - ground).sum())
                connect = dict(to=list(cells[-1]), to_feet=f1, length=round(length, 1), max_dh=round(float(np.abs(np.diff(prof)).max()), 2), bridge=wet,
                               earthwork_per_block=round(earth / len(cells), 2),
                               cells=int(len(cells) * WIDTH * (2 + earth / len(cells))), route=[list(c) for c in cells[::4]] + [list(cells[-1])])
            else:
                connect = dict(to=list(cells[-1]), length=round(length, 1), infeasible='height difference too big for the grade')
    rows.append(dict(id=e['id'], x=x0, z=z0, feet=f0, kind=e.get('kind'), cut=cut, connect=connect))
    print(e['id'], e.get('kind'), 'cut', cut['columns'], cut['to'], '| connect', None if not connect else {k: connect[k] for k in connect if k != 'route'}, flush=True)
json.dump(rows, open(sys.argv[6], 'w', encoding='utf8'), ensure_ascii=False, indent=0, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
