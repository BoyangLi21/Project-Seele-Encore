import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_natural
from e5_plan import is_building
w = World(REGION)
F = np.load('fill.npy')
F = F[np.lexsort((F[:, 2] >> 4, F[:, 0] >> 4))]
keep = np.zeros(len(F), bool)
for n, (x, y, z, top) in enumerate(F.tolist()):
    k = 1
    while k < 13 and is_natural(w.get(x, y + k, z)):
        k += 1
    keep[n] = is_building(w.get(x, y + k, z))
np.save('fill_room.npy', F[keep]); print(int(keep.sum()), len(F))
