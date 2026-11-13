"""A road network from the paving actually in the world, not from declarations.

For every generated column of a capture, looks at the block on the measured top (and the one above it, for
a slope layer standing on a full block): TrafficCraft asphalt (marked or not, slab or slope) or a Project
SEELE road block is road; TrafficCraft concrete is footway. Writes the same arrays as a declared network
(road, walk = road or footway, grade2 = walking height x2 - 2, bounds) so the dead-end scan and the R1
planners run on what a player actually sees. Columns are read one 512-block tile at a time.
usage: paved_network_from_capture.py <capture> <out.npz>"""
import gc
import re
import sys

import numpy as np

from plan_station_access_corridor import CapturedSurface

src = sys.argv[1]
cap = CapturedSurface(src, partial=True)
m = cap.measured
cx, cz = map(int, cap.bounds[:2])
top, full = m['top'], m['full'].astype(bool)
del cap
H, W = top.shape
road = np.zeros((H, W), bool)
walk = np.zeros((H, W), bool)
grade2 = np.zeros((H, W), np.int16)


def kind(s):
    n = s.split('[')[0]
    if n.startswith('trafficcraft:asphalt') or n.startswith('trafficcraft:road') or n.startswith('projectseele:road'):
        return 'road'
    if n.startswith('trafficcraft:concrete'):
        return 'walk'
    return None


def height(s, y):
    k = re.search(r'layers=(\d)', s)
    if k:
        return y + int(k.group(1)) / 8
    return y + (0.5 if 'type=bottom' in s else 1.0)


zz, xx = np.nonzero(full)
tile = ((zz + cz) // 512) * 1000 + ((xx + cx) // 512)
for t in np.unique(tile):
    cap = CapturedSurface(src, partial=True)
    sel = np.flatnonzero(tile == t)
    n = 0
    for z, x in zip(zz[sel], xx[sel]):
        y = int(top[z, x])
        try:
            s0 = cap.state(int(x + cx), y, int(z + cz))
            s1 = cap.state(int(x + cx), y + 1, int(z + cz))
        except ValueError:
            continue
        k1, k0 = kind(s1), kind(s0)
        if k1:                      # a slope layer on top of the measured top
            k, h = k1, height(s1, y + 1)
        elif k0:
            k, h = k0, height(s0, y)
        else:
            continue
        walk[z, x] = True
        road[z, x] = k == 'road'
        grade2[z, x] = int(round((h - 1) * 2))
        n += 1
    del cap
    gc.collect()
    print('tile', t, len(sel), 'paved', n, flush=True)
np.savez_compressed(sys.argv[2], road=road, walk=walk, grade2=grade2, bounds=np.array([cx, cz, cx + W - 1, cz + H - 1]))
print('road columns', int(road.sum()), 'footway columns', int((walk & ~road).sum()))
