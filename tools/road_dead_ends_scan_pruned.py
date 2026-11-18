"""Dead ends of a road mask like road_dead_ends_scan, with ends found by crossing number.

Thinning leaves a small knot of cells at the end of a wide road (three cells in a triangle), so no cell there has
exactly one neighbour and road_dead_ends_scan, which looks for degree-1 cells, never reported it (the owner's
(-721, 1046) is one). Here an end is a skeleton cell whose ring of 8 neighbours has exactly one run of skeleton
cells (crossing number 1), a junction one with three runs or more; short prongs (under min_spur) that end at a
junction are pruned first. Each end is traced by breadth-first search along the skeleton to the nearest junction,
which also survives small knots. Output as road_dead_ends_scan.
usage: road_dead_ends_scan_pruned.py <mask.npz> <out.json> [min_spur]"""
import json
import sys

import numpy as np
from scipy import ndimage

from road_dead_ends_scan import thin

K = np.ones((3, 3), np.int16)


def degree(sk):
    d = ndimage.convolve(sk.astype(np.int16), K, mode='constant') - 1
    d[~sk] = 0
    return d


def trace(sk, deg, start, limit):
    path, prev, cur = [start], None, start
    while len(path) <= limit:
        nb = [(cur[0] + dz, cur[1] + dx) for dz in (-1, 0, 1) for dx in (-1, 0, 1) if (dz or dx)
              and 0 <= cur[0] + dz < sk.shape[0] and 0 <= cur[1] + dx < sk.shape[1] and sk[cur[0] + dz, cur[1] + dx]
              and (cur[0] + dz, cur[1] + dx) != prev and (cur[0] + dz, cur[1] + dx) not in path[-3:]]
        if len(nb) != 1 or (deg[cur] >= 3 and cur != start):
            break
        prev, cur = cur, nb[0]
        path.append(cur)
    return path, cur


def prune(sk, min_spur):
    for _ in range(4):
        deg = degree(sk)
        cut = 0
        for z, x in np.argwhere(sk & (deg == 1)):
            path, end = trace(sk, deg, (z, x), min_spur)
            if deg[end] >= 3 and len(path) < min_spur:
                for p in path[:-1]:          # keep the fork cell itself
                    sk[p] = False
                cut += 1
        if not cut:
            break
    return sk


RING = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]


def crossing(sk):
    p = np.pad(sk, 1).astype(np.int8)
    nb = [p[1 + dz:p.shape[0] - 1 + dz, 1 + dx:p.shape[1] - 1 + dx] for dz, dx in RING]
    c = sum(((nb[i] == 0) & (nb[(i + 1) % 8] == 1)).astype(np.int8) for i in range(8))
    c[~sk] = 0
    return c


def bfs_spur(sk, cross, start, limit):
    """Path from an end to the nearest junction (crossing >= 3) along the skeleton, or to where it runs out."""
    from collections import deque
    prev, q = {start: None}, deque([start])
    while q:
        cur = q.popleft()
        if cur != start and cross[cur] >= 3:
            break
        if len(prev) > limit:
            break
        for dz, dx in RING:
            n = (cur[0] + dz, cur[1] + dx)
            if 0 <= n[0] < sk.shape[0] and 0 <= n[1] < sk.shape[1] and sk[n] and n not in prev:
                prev[n] = cur
                q.append(n)
    path = [cur]
    while prev[path[-1]] is not None:
        path.append(prev[path[-1]])
    return path[::-1], cur


def main():
    f = np.load(sys.argv[1])
    mask, (ax, az) = f['mask'].astype(bool), map(int, f['bounds'][:2])
    min_spur = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    mask = ndimage.binary_closing(mask, np.ones((3, 3)))
    sk = prune(thin(mask), min_spur)
    cross = crossing(sk)
    lab, _ = ndimage.label(mask, np.ones((3, 3)))
    sizes = np.bincount(lab.ravel())
    rows = []
    for z, x in np.argwhere(sk & (cross == 1)):
        path, cur = bfs_spur(sk, cross, (int(z), int(x)), 4000)
        kind = 'junction' if cross[cur] >= 3 else 'isolated'
        if kind == 'junction' and len(path) < min_spur:
            continue
        if any(abs(r['x'] - (x + ax)) <= 3 and abs(r['z'] - (z + az)) <= 3 for r in rows):
            continue                         # one knot gives two end cells: keep the first
        w = int(mask[max(0, z - 3):z + 4, max(0, x - 3):x + 4].sum())
        back = path[min(len(path) - 1, 8)]
        rows.append(dict(x=int(x + ax), z=int(z + az), spur=len(path), to=kind, comp=int(lab[z, x]),
                         comp_cells=int(sizes[lab[z, x]]), near=w, back=[int(back[1] + ax), int(back[0] + az)]))
    json.dump(dict(ends=rows, skeleton_cells=int(sk.sum()), mask_cells=int(mask.sum())), open(sys.argv[2], 'w'), indent=0)
    np.save(sys.argv[2].replace('.json', '-skeleton.npy'), sk)
    print(len(rows), 'dead ends;', sum(r['to'] == 'isolated' for r in rows), 'on isolated pieces')


if __name__ == '__main__':
    main()
