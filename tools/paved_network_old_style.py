"""A road network from old-style paving (before TrafficCraft), for convert_roads_trafficcraft.

The outer districts were paved with black concrete and Project SEELE asphalt slabs on the carriageway and
smooth stone (full or slab) on the footways, and were never declared, so there is no network to convert from.
For every generated column the block on the measured top (or one above it) is read: carriageway blocks make
road; smooth stone within FOOT blocks of a carriageway makes footway (smooth stone further away is a yard or
a plaza and stays out). Carriageway pieces smaller than MIN_PIECE columns are dropped (single slabs in
gardens). Writes road, walk, grade2 (walking height x2 - 2) and bounds, the arrays the converter reads.
usage: paved_network_old_style.py <capture> <out.npz> [x0 z0 x1 z1]"""
import gc
import sys

import numpy as np
from scipy import ndimage

from plan_station_access_corridor import CapturedSurface

ROAD = ('minecraft:black_concrete', 'projectseele:road_asphalt_slab', 'projectseele:road_marking_slab')
FOOTWAY = ('minecraft:smooth_stone', 'minecraft:smooth_stone_slab')
FOOT, MIN_PIECE = 4, 40
AIR = ('minecraft:air', 'minecraft:cave_air')

src = sys.argv[1]
cap = CapturedSurface(src, partial=True)
cx, cz = map(int, cap.bounds[:2])
top, full = cap.measured['top'], cap.measured['full'].astype(bool)
del cap
H, W = top.shape
x0, z0, x1, z1 = map(int, sys.argv[3:7]) if len(sys.argv) > 6 else (cx, cz, cx + W - 1, cz + H - 1)
road = np.zeros((H, W), bool)
foot = np.zeros((H, W), bool)
grade2 = np.zeros((H, W), np.int16)


def height(s, y):
    return y + (0.5 if 'type=bottom' in s else 1.0)


sel_mask = np.zeros((H, W), bool)
sel_mask[z0 - cz:z1 - cz + 1, x0 - cx:x1 - cx + 1] = True
zz, xx = np.nonzero(full & sel_mask)
tile = ((zz + cz) // 512) * 1000 + ((xx + cx) // 512)
for t in np.unique(tile):
    cap = CapturedSurface(src, partial=True)
    sel = np.flatnonzero(tile == t)
    for z, x in zip(zz[sel], xx[sel]):
        y = int(top[z, x])
        X, Z = int(x + cx), int(z + cz)
        try:
            for yy in (y + 1, y):
                s = cap.state(X, yy, Z)
                if s.split('[')[0] not in AIR:
                    break
        except ValueError:
            continue
        n = s.split('[')[0]
        if n in ROAD:
            road[z, x] = True
        elif n in FOOTWAY:
            foot[z, x] = True
        else:
            continue
        grade2[z, x] = int(round((height(s, yy) - 1) * 2))
    del cap
    gc.collect()
    print('tile', t, len(sel), flush=True)
lab, n = ndimage.label(road, np.ones((3, 3), int))
sizes = ndimage.sum(road, lab, range(1, n + 1))
road &= np.isin(lab, 1 + np.flatnonzero(sizes >= MIN_PIECE))
near = ndimage.binary_dilation(road, iterations=FOOT)
walk = road | (foot & near)
np.savez_compressed(sys.argv[2], road=road, walk=walk, grade2=grade2, bounds=np.array([cx, cz, cx + W - 1, cz + H - 1]))
print('road columns', int(road.sum()), 'footway columns', int((walk & ~road).sum()), 'dropped road pieces', int((sizes < MIN_PIECE).sum()))
