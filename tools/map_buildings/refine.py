"""Keep wall rows that face a real room (roof above the inner cell) and glass that is really buried."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, is_natural, base
from e5_plan import is_veg, is_building

w = World(REGION)
W = np.load(Path(__file__).parent / 'walls.npy')
order = np.lexsort((W[:, 2] >> 4, W[:, 0] >> 4))   # chunk order for the cache
W = W[order]
keep = np.zeros(len(W), bool)
for n, (x, y, z, dx, dz, ot, fl, isw, isg) in enumerate(W.tolist()):
    s = w.get(x, y, z)
    if s is None or is_veg(s) or not is_building(s):
        continue
    b = base(s)
    if any(k in b for k in ('fence', '_wall', 'bars', 'slab', 'stairs', 'trapdoor', 'ladder', 'scaffold', 'chain')):
        continue
    out = w.get(x + dx, y, z + dz)
    if not is_natural(out):
        continue
    ix, iz = x - dx, z - dz
    # the cell behind must be a room: roof within 8 above, a floor that is not terrain
    roof = any(is_building(w.get(ix, y + k, iz)) for k in range(1, 9))
    if not roof:
        continue
    floor = None
    for k in range(0, 12):
        c = w.get(ix, y - k, iz)
        if not is_open(c):
            floor = c
            break
    if floor is None or is_natural(floor):
        continue
    if isg or (ot - fl) >= 2:
        keep[n] = True
np.save(Path(__file__).parent / 'walls_room.npy', W[keep])
print('kept', int(keep.sum()), 'of', len(W))
