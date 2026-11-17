"""Per-column obstacle mask for road routing: built (something man-made standing on the ground) and water.

For every fully generated column of a capture, reads the block on the soil top and the three above it.
water: the first block above the soil top is water. built: any of the three is solid and not soil,
plants, leaves, logs or snow. Read 512 blocks at a time so memory stays flat.
usage: road_obstacle_mask.py <capture> <out.npz>"""
import gc
import sys

import numpy as np

from plan_station_access_corridor import CapturedSurface

src = sys.argv[1]
cap = CapturedSurface(src, partial=True)
m = cap.measured
cx, cz = map(int, cap.bounds[:2])
top, full = m['top'], m['full'].astype(bool)
del cap
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
NATURAL = ('minecraft:grass_block', 'minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:stone', 'minecraft:gravel', 'minecraft:sand', 'minecraft:podzol',
           'minecraft:andesite', 'minecraft:granite', 'minecraft:diorite', 'minecraft:moss_block', 'minecraft:rooted_dirt', 'minecraft:clay', 'minecraft:mud',
           'minecraft:snow', 'minecraft:snow_block', 'minecraft:ice', 'minecraft:water')
SOFT_END = ('grass', 'fern', 'flower', 'bush', 'tulip', 'sapling', 'vine', 'roots', 'mushroom', '_leaves', '_log', '_wood', 'dandelion', 'poppy',
            'orchid', 'allium', 'bluet', 'daisy', 'cornflower', 'lily', 'seagrass', 'kelp', 'kelp_plant')
H, W = top.shape
built = np.zeros((H, W), bool)
water = np.zeros((H, W), bool)
zz, xx = np.nonzero(full)
tile = ((zz + cz) // 512) * 1000 + ((xx + cx) // 512)
for t in np.unique(tile):
    cap = CapturedSurface(src, partial=True)
    sel = np.flatnonzero(tile == t)
    for z, x in zip(zz[sel], xx[sel]):
        y = int(top[z, x])
        try:
            names = [cap.state(int(x + cx), y + k, int(z + cz)).split('[')[0] for k in (1, 2, 3)]
        except ValueError:
            continue
        if names[0] == 'minecraft:water':
            water[z, x] = True
        for n in names:
            if n not in AIR and n not in NATURAL and not n.endswith(SOFT_END) and not n.startswith('trafficcraft:'):
                built[z, x] = True
                break
    del cap
    gc.collect()
    print('tile', t, len(sel), flush=True)
np.savez_compressed(sys.argv[2], built=built, water=water, bounds=np.array([cx, cz, cx + W - 1, cz + H - 1]))
print('built columns', int(built.sum()), 'water columns', int(water.sum()))
