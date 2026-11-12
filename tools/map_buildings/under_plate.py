"""What stands under a plate before anyone fills it: ground kinds and man-made blocks in the gap.

under_plate.py <plates.json> <index,index,...>

For every hanging deck column of the plate (float.npy) it reads the ground block at the bottom of
the gap. Inside the plate's bbox it also counts man-made blocks between the deck and the ground
(pillars, roads, signs, stairs): a deck with a street or a building under it is an elevated
level and stays hollow; one over bare hillside is a platform to fill.
"""
import glob, json, math, sys
from collections import Counter
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World, WORLD
from blocks import is_open, is_natural, short
from rails import path
from stations import unpack

HERE = Path(__file__).parent


def main(plates_file, idx):
    w = World(REGION)
    A = np.load(HERE / 'float.npy')
    P = json.load(open(plates_file, encoding='utf8'))
    rails = [unpack(open(f, 'rb').read())[0] for f in glob.glob(WORLD + '/mtr/projectseele/geofront/rails/*/*')]
    for i in idx:
        p = P[i]
        x0, y0, z0, x1, y1, z1 = p['bbox']
        m = (A[:, 0] >= x0) & (A[:, 0] <= x1) & (A[:, 2] >= z0) & (A[:, 2] <= z1) & (A[:, 1] >= y0) & (A[:, 1] <= y1)
        cols = A[m].tolist()
        ground, man = Counter(), Counter()
        nat = 0
        for x, y, z, gap, gr, gy in cols:
            s = w.get(int(x), int(y - gap - 1), int(z))
            ground[short(s)] += 1
            nat += bool(s) and is_natural(s)
        # man-made blocks in the open space under the deck, sampled every 2 columns
        lo = int(min((y - gap for x, y, z, gap, gr, gy in cols), default=y0 - 1))
        for x in range(x0, x1 + 1, 2):
            for z in range(z0, z1 + 1, 2):
                for yy in range(lo, y0 - 1):
                    s = w.get(x, yy, z)
                    if s and not is_open(s) and not is_natural(s) and 'leaves' not in s and '_log' not in s:
                        man[short(s)] += 1
        nrail = 0
        for d in rails:
            if any(x0 - 2 <= px <= x1 + 2 and z0 - 2 <= pz <= z1 + 2 for px, pz, ry in path(d)):
                nrail += 1
        print(f"#{i} {p['station']} {p['bbox']} gap_max {p['gap_max']} hanging {len(cols)} natural-ground {nat * 100 // max(1, len(cols))}%"
              f" rails {nrail}\n   ground {dict(ground.most_common(5))}\n   under-deck man-made {sum(man.values())} {dict(man.most_common(8))}")


if __name__ == '__main__':
    main(sys.argv[1], [int(v) for v in sys.argv[2].split(',')])
