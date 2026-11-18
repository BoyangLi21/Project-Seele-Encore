"""Thin a maze of winding roads in a box down to one tree that still reaches everything worth reaching.

Anchors: the given points (where the box meets the roads that stay) and every door within DOOR_R of the box's
declared paving, each snapped to the nearest skeleton cell in the box. The tree is grown from the first anchor by
repeatedly adding the shortest skeleton path to the nearest anchor not yet reached (8-neighbour, diagonal steps
cost 1.41). Declared cells in the box whose nearest skeleton cell lies in the box but off the tree are listed as
columns to take up (plan_road_r1_batch decision 拆除列); cells nearer a skeleton cell outside the box belong to the
roads around and stay. Skeleton pieces in the box that the tree does not reach are served from outside and stay. Writes <out>.json (columns, anchors, tree length) and <out>-tree.npy.
usage: prune_road_maze.py <capture> <network.npz> <skeleton.npy> <out> x0 z0 x1 z1 ax,az [ax,az ...]"""
import heapq
import json
import math
import sys

import numpy as np
from scipy import ndimage

from plan_station_access_corridor import CapturedSurface

DOOR_R = 10


def main():
    capdir, netp, skp, out = sys.argv[1:5]
    x0, z0, x1, z1 = map(int, sys.argv[5:9])
    given = [tuple(map(int, a.split(','))) for a in sys.argv[9:]]
    cap = CapturedSurface(capdir, partial=True)
    net = np.load(netp)
    ax, az = map(int, net['bounds'][:2])
    decl = net['road'] | net['walk']
    g2 = net['grade2']
    sk = np.load(skp).astype(bool)
    box = np.zeros_like(sk)
    box[z0 - az:z1 - az + 1, x0 - ax:x1 - ax + 1] = True
    skb = sk & box

    def snap(x, z, r=12):
        best = None
        for dz in range(-r, r + 1):
            for dx in range(-r, r + 1):
                iz, ix = z + dz - az, x + dx - ax
                if 0 <= iz < sk.shape[0] and 0 <= ix < sk.shape[1] and skb[iz, ix]:
                    d = dx * dx + dz * dz
                    if best is None or d < best[0]:
                        best = (d, (iz, ix))
        return best[1] if best else None

    anchors = []
    for x, z in given:
        p = snap(x, z)
        if p is None:
            raise SystemExit(f'anchor {x},{z}: no skeleton within 12 in the box')
        anchors.append(dict(kind='given', at=[x, z], snap=[int(p[1] + ax), int(p[0] + az)]))
    # doors near the box's paving
    seen = set()
    for z in range(z0 - DOOR_R, z1 + DOOR_R + 1):
        for x in range(x0 - DOOR_R, x1 + DOOR_R + 1):
            iz, ix = z - az, x - ax
            near = decl[max(0, iz - DOOR_R):iz + DOOR_R + 1, max(0, ix - DOOR_R):ix + DOOR_R + 1] & box[max(0, iz - DOOR_R):iz + DOOR_R + 1, max(0, ix - DOOR_R):ix + DOOR_R + 1]
            if not near.any():
                continue
            f = None
            zz, xx = np.nonzero(near)
            k = int(np.argmin((zz - min(DOOR_R, iz)) ** 2 + (xx - min(DOOR_R, ix)) ** 2))
            f = int(g2[zz[k] + max(0, iz - DOOR_R), xx[k] + max(0, ix - DOOR_R)] // 2 + 1)
            for y in range(f - 2, f + 4):
                try:
                    s = cap.state(x, y, z)
                except ValueError:
                    break
                n = s.split('[')[0]
                if n.endswith('_door') and 'trapdoor' not in n and 'half=lower' in s:
                    key = (x // 3, z // 3)
                    if key in seen:
                        break
                    seen.add(key)
                    p = snap(x, z, DOOR_R + 2)
                    if p is not None:
                        anchors.append(dict(kind='door', door=[x, y, z], snap=[int(p[1] + ax), int(p[0] + az)]))
                    break
    # grow the tree
    tree = np.zeros_like(sk)
    first = anchors[0]['snap']
    tree[first[1] - az, first[0] - ax] = True
    todo = {(a['snap'][1] - az, a['snap'][0] - ax) for a in anchors[1:]}
    todo.discard((first[1] - az, first[0] - ax))
    RING = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.41), (-1, 1, 1.41), (1, -1, 1.41), (1, 1, 1.41)]
    while todo:
        dist, prev, heap = {}, {}, []
        for p in zip(*np.nonzero(tree)):
            dist[p] = 0
            heap.append((0, p))
        heapq.heapify(heap)
        hit = None
        while heap:
            d, p = heapq.heappop(heap)
            if d > dist.get(p, 1e18):
                continue
            if p in todo:
                hit = p
                break
            for dz, dx, w in RING:
                q = (p[0] + dz, p[1] + dx)
                if 0 <= q[0] < sk.shape[0] and 0 <= q[1] < sk.shape[1] and skb[q] and d + w < dist.get(q, 1e18):
                    dist[q] = d + w
                    prev[q] = p
                    heapq.heappush(heap, (d + w, q))
        if hit is None:
            print('unreachable anchors:', [(int(p[1] + ax), int(p[0] + az)) for p in todo])
            break
        p = hit
        while not tree[p]:
            tree[p] = True
            p = prev[p]
        todo.discard(hit)
        todo -= {q for q in todo if tree[q]}
    # Box skeleton pieces the tree never reached are served from outside the box (a door on a road coming in): they stay.
    lab, _ = ndimage.label(skb, np.ones((3, 3)))
    reached = set(np.unique(lab[tree])) - {0}
    apart = skb & ~np.isin(lab, list(reached))
    # columns to take up
    dist_all, idx = ndimage.distance_transform_edt(~sk, return_indices=True)
    cols = []
    zs, xs = np.nonzero(decl & box)
    for iz, ix in zip(zs, xs):
        nz, nx = idx[:, iz, ix]
        if box[nz, nx] and not tree[nz, nx] and not apart[nz, nx]:
            # within 3 of the tree it is the kept road's own width
            cols.append([int(ix + ax), int(iz + az)])
    tdist = ndimage.distance_transform_edt(~tree)
    keep_w = []
    cols2 = []
    for x, z in cols:
        if tdist[z - az, x - ax] <= 3.5:
            keep_w.append([x, z])
        else:
            cols2.append([x, z])
    np.save(out + '-tree.npy', tree)
    json.dump(dict(box=[x0, z0, x1, z1], anchors=anchors, tree_cells=int(tree.sum()), box_skeleton=int(skb.sum()),
                   columns=cols2, kept_beside_tree=len(keep_w)), open(out + '.json', 'w', encoding='utf8'), ensure_ascii=False)
    print(dict(anchors=len(anchors), doors=sum(a['kind'] == 'door' for a in anchors), tree=int(tree.sum()), box_skeleton=int(skb.sum()),
               take_up=len(cols2), kept_beside_tree=len(keep_w)))


if __name__ == '__main__':
    main()
