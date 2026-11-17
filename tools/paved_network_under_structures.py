"""Add paving hidden under viaducts, bridges and roofs to a network built by paved_network_from_capture.

The capture's measured top is the first solid block from the sky, so a road passing under a viaduct deck
shows as the deck and the road looks cut in two there. Columns within REACH of the paving that are not paved
on top are searched downwards (up to DEPTH blocks) for TrafficCraft paving with two blocks of air above it;
what is found joins the network with its own walking height.
usage: paved_network_under_structures.py <capture> <net-in.npz> <net-out.npz>"""
import gc
import re
import sys

import numpy as np
from scipy import ndimage

from plan_station_access_corridor import CapturedSurface

src = sys.argv[1]
net = dict(np.load(sys.argv[2]))
cap = CapturedSurface(src, partial=True)
m = cap.measured
cx, cz = map(int, cap.bounds[:2])
top, full = m['top'], m['full'].astype(bool)
del cap
REACH, DEPTH = 8, 30
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
        try:
            # walk down: need an air pocket under the structure, then paving at its floor
            y = y0 - 1
            while y > y0 - DEPTH and cap.state(X, y, Z).split('[')[0] not in AIR:
                y -= 1
            if y <= y0 - DEPTH:
                continue
            while y > y0 - DEPTH and cap.state(X, y, Z).split('[')[0] in AIR:
                y -= 1
            s = cap.state(X, y, Z)
        except ValueError:
            continue
        k = kind(s)
        if not k or cap.state(X, y + 2, Z).split('[')[0] not in AIR:
            continue
        lay = re.search(r'layers=(\d)', s)
        h = y + int(lay.group(1)) / 8 if lay else y + (0.5 if 'type=bottom' in s else 1.0)
        walk[z, x] = True
        road[z, x] = k == 'road'
        g2[z, x] = int(round((h - 1) * 2))
        found += 1
    del cap
    gc.collect()
    print('tile', t, len(sel), 'found so far', found, flush=True)
np.savez_compressed(sys.argv[3], **net)
print('candidates', int(cand.sum()), 'paving found under structures', found)
