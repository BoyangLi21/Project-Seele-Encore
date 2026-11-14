"""Add bridge decks to a paved network: paving standing above the measured ground top.

Over a stream the capture's measured top is the bed or the water, and the road deck crossing it sits
higher, so the paved network had a gap at every small bridge. Columns within REACH of the paving that are
not paved are searched upwards (up to RISE blocks above the top) for TrafficCraft paving with air above it.
usage: paved_network_bridges.py <capture> <net-in.npz> <net-out.npz>"""
import gc
import re
import sys

import numpy as np
from scipy import ndimage

from plan_station_access_corridor import CapturedSurface

src = sys.argv[1]
net = dict(np.load(sys.argv[2]))
cap = CapturedSurface(src, partial=True)
cx, cz = map(int, cap.bounds[:2])
top, full = cap.measured['top'], cap.measured['full'].astype(bool)
del cap
REACH, RISE = 6, 12
walk, road, g2 = net['walk'], net['road'], net['grade2']
cand = ndimage.binary_dilation(walk, iterations=REACH) & ~walk & full
AIR = ('minecraft:air', 'minecraft:cave_air')


def kind(s):
    n = s.split('[')[0]
    if n.startswith('trafficcraft:asphalt') or n.startswith('trafficcraft:road') or n.startswith('projectseele:road'):
        return 'road'
    if n.startswith('trafficcraft:concrete'):
        return 'walk'
    return None


zz, xx = np.nonzero(cand)
tile = ((zz + cz) // 512) * 1000 + ((xx + cx) // 512)
found = 0
for t in np.unique(tile):
    cap = CapturedSurface(src, partial=True)
    sel = np.flatnonzero(tile == t)
    for z, x in zip(zz[sel], xx[sel]):
        X, Z, y0 = int(x + cx), int(z + cz), int(top[z, x])
        hit = None
        try:
            for y in range(y0 + 1, y0 + RISE + 1):
                s = cap.state(X, y, Z)
                if kind(s) and cap.state(X, y + 1, Z).split('[')[0] in AIR + ('minecraft:snow',):
                    hit = (y, s)
                    break
        except ValueError:
            continue
        if not hit:
            continue
        y, s = hit
        lay = re.search(r'layers=(\d)', s)
        h = y + int(lay.group(1)) / 8 if lay else y + (0.5 if 'type=bottom' in s else 1.0)
        walk[z, x] = True
        road[z, x] = kind(s) == 'road'
        g2[z, x] = int(round((h - 1) * 2))
        found += 1
    del cap
    gc.collect()
    print('tile', t, len(sel), 'found so far', found, flush=True)
np.savez_compressed(sys.argv[3], **net)
print('candidates', int(cand.sum()), 'bridge paving found', found)
