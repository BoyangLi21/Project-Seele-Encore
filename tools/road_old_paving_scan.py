"""R1/E5: ground-level old paving outside the declared network (top block within 2 of the soil top, not declared).
usage: road_old_paving_scan.py <capture> <network.npz> <out.npz>"""
import gc
import sys
from collections import Counter

import numpy as np
from scipy import ndimage

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
net = np.load(sys.argv[2])
ax, az = map(int, net['bounds'][:2])
cx, cz = map(int, cap.bounds[:2])
m = cap.measured
hi, top, full = m['highest'], m['top'], m['full'].astype(bool)
OLD = {'minecraft:smooth_stone', 'minecraft:smooth_stone_slab', 'minecraft:stone_brick_slab', 'minecraft:stone_bricks', 'minecraft:gravel',
       'projectseele:road_asphalt_slab', 'projectseele:road_marking_slab', 'minecraft:black_concrete', 'minecraft:gray_concrete', 'minecraft:andesite_slab',
       'minecraft:polished_andesite', 'minecraft:polished_andesite_slab', 'minecraft:cobblestone', 'minecraft:cobblestone_slab', 'minecraft:dirt_path'}
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
H, Wd = hi.shape
cand = full & (hi - top <= 2) & (hi >= top)
oz, ox = np.nonzero(cand)
print(len(oz), 'ground-level columns to read', flush=True)
out = np.zeros(hi.shape, np.uint8)
names = sorted(OLD)
idx = {n: i + 1 for i, n in enumerate(names)}
cnt = Counter()

tile = ((oz + cz) // 512) * 100 + ((ox + cx) // 512)
for t in np.unique(tile):
    cap = CapturedSurface(sys.argv[1], partial=True)
    sel = np.flatnonzero(tile == t)
    for z, x in zip(oz[sel], ox[sel]):
        y = int(hi[z, x])
        try:
            s = cap.state(x + cx, y, z + cz).split('[')[0]
            if s in AIR:
                s = cap.state(x + cx, y - 1, z + cz).split('[')[0]
        except ValueError:
            continue
        if s in idx:
            out[z, x] = idx[s]
            cnt[s] += 1
    del cap
    gc.collect()
    print('tile', t, len(sel), flush=True)
# Drop declared network cells and keep components of at least 6 columns.
gx, gz = np.meshgrid(np.arange(Wd) + cx, np.arange(H) + cz)
inside = (gx - ax >= 0) & (gx - ax < net['walk'].shape[1]) & (gz - az >= 0) & (gz - az < net['walk'].shape[0])
declared = np.zeros(hi.shape, bool)
declared[inside] = (net['walk'] | net['road'])[(gz - az)[inside], (gx - ax)[inside]]
mask = (out > 0) & ~declared
lab, n = ndimage.label(mask, np.ones((3, 3)))
sizes = np.bincount(lab.ravel())
keep = sizes >= 6
keep[0] = False
mask = keep[lab]
print('old paving columns by block', cnt.most_common())
print('undeclared ground-level old paving: columns', int(mask.sum()), 'components', int(keep.sum()))
np.savez_compressed(sys.argv[3], kind=out, mask=mask, bounds=np.array([cx, cz, cx + Wd - 1, cz + H - 1]), names=np.array(names))
