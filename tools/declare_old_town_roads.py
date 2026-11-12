"""Declare an undeclared old street grid so the TrafficCraft converter can take it.

Inside the box, each column's surface is the first block under the sky that is not air, a plant or a light.
Carriageway: black, white, grey or yellow concrete (old asphalt and its paint) at ground level (within 2 of
the soil top). Footway: smooth stone, its slab or stone bricks within 3 blocks of a carriageway cell, at
ground level. The walking height is the block top (half a block lower on a bottom slab). Pieces under
MIN_PIECE cells are left out. Cells already declared keep their declaration.
usage: declare_old_town_roads.py <capture> <network.npz> <out-network.npz> x0 z0 x1 z1 [ymin ymax]
With ymin ymax, paving whose top block lies in that height band counts even over air (a town platform's
edge roads standing over a slope that is still to be filled), instead of the ground-level test."""
import sys
from collections import Counter

import numpy as np
from scipy import ndimage

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
net = np.load(sys.argv[2])
network = {k: net[k].copy() for k in net.files}
X0, Z0, X1, Z1 = map(int, sys.argv[4:8])
BAND = tuple(map(int, sys.argv[8:10])) if len(sys.argv) > 9 else None
ax, az = map(int, network['bounds'][:2])
cx, cz = map(int, cap.bounds[:2])
hi, top = cap.measured['highest'], cap.measured['top']
CARRIAGE = {'minecraft:black_concrete', 'minecraft:white_concrete', 'minecraft:gray_concrete', 'minecraft:yellow_concrete'}
FOOT = {'minecraft:smooth_stone', 'minecraft:smooth_stone_slab', 'minecraft:stone_bricks'}
SKIP = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air', 'minecraft:light', 'minecraft:snow')
PLANT_END = ('grass', 'fern', 'flower', 'bush', 'tulip', 'sapling', 'torch', 'lantern', 'carpet', 'button', 'pressure_plate')
MIN_PIECE = 40
H, W = Z1 - Z0 + 1, X1 - X0 + 1
kind = np.zeros((H, W), np.int8)          # 1 carriage, 2 foot
feet = np.zeros((H, W))
blocks = Counter()
for j in range(H):
    for i in range(W):
        x, z = X0 + i, Z0 + j
        y = int(hi[z - cz, x - cx])
        s = cap.state(x, y, z)
        while (s.split('[')[0] in SKIP or s.split('[')[0].endswith(PLANT_END)) and y > -64:
            y -= 1
            s = cap.state(x, y, z)
        n = s.split('[')[0]
        if BAND:
            if not (BAND[0] <= y <= BAND[1]):
                continue
        elif y - int(top[z - cz, x - cx]) > 2:
            continue
        if n in CARRIAGE:
            kind[j, i] = 1
        elif n in FOOT:
            kind[j, i] = 2
        else:
            continue
        feet[j, i] = y + (0.5 if 'type=bottom' in s else 1.0)
        blocks[n] += 1
carriage = kind == 1
near = ndimage.distance_transform_edt(~carriage) <= 3
foot = (kind == 2) & near
walk = carriage | foot
lab, n = ndimage.label(walk, np.ones((3, 3)))
sizes = np.bincount(lab.ravel())
keep = sizes >= MIN_PIECE
keep[0] = False
walk &= keep[lab]
carriage &= walk
win = np.s_[Z0 - az:Z1 - az + 1, X0 - ax:X1 - ax + 1]
already = network['walk'][win] | network['road'][win]
new = walk & ~already
network['walk'][win] |= new
network['road'][win] |= carriage & new
g = np.round((feet - 1) * 2).astype(network['grade2'].dtype)
network['grade2'][win] = np.where(new, g, network['grade2'][win])
np.savez_compressed(sys.argv[3], **network)
print(dict(new_walk=int(new.sum()), new_carriage=int((carriage & new).sum()), already_declared=int((walk & already).sum()), pieces=int(keep.sum()),
           surface_blocks=dict(blocks.most_common()), feet_range=[float(feet[walk].min()), float(feet[walk].max())] if walk.any() else None))
