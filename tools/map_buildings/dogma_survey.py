"""Survey for the Central Dogma main shaft (ROADMAP 5.2a): classify every cell of a box under the hangar level.

  python dogma_survey.py <out.npz> [x0 x1 z0 z1 y0 y1]

Reads BUILDINGS_WORLD. Classes: 0 air, 1 rock (natural), 2 built, 3 glass/light, 4 LCL or water, 5 ungenerated.
Also keeps the most common built block per column band so sections can be labelled. Writes classes (y, z, x) uint8.
"""
import sys
from collections import Counter
import numpy as np
from mca import REGION, World

NATURAL = ('stone', 'deepslate', 'dirt', 'gravel', 'andesite', 'diorite', 'granite', 'tuff', 'calcite', 'basalt', 'blackstone',
           'grass_block', 'sand', 'clay', 'bedrock', 'netherrack', 'ore', 'cobblestone', 'moss', 'mud')


def classify(state):
    n = state.split('[')[0].split(':')[-1]
    if n in ('air', 'cave_air', 'void_air'):
        return 0
    if 'lcl' in n or n == 'water':
        return 4
    if 'glass' in n or 'lantern' in n or 'light' in n or 'lamp' in n:
        return 3
    if state.startswith('minecraft:') and any(n == k or n.endswith('_' + k) or n.startswith(k) for k in NATURAL) \
            and 'brick' not in n and 'polished' not in n and 'smooth' not in n and 'chiseled' not in n:
        return 1
    return 2


def main(out, x0=-90, x1=150, z0=140, z1=410, y0=-1280, y1=-990):
    x0, x1, z0, z1, y0, y1 = map(int, (x0, x1, z0, z1, y0, y1))
    w = World(REGION)
    cls = np.full((y1 - y0 + 1, z1 - z0 + 1, x1 - x0 + 1), 5, np.uint8)
    built = Counter()
    for cx in range(x0 >> 4, (x1 >> 4) + 1):
        for cz in range(z0 >> 4, (z1 >> 4) + 1):
            c = w.chunk(cx, cz)
            if c is None:
                continue
            secs = c[0]
            for sy in range(y0 >> 4, (y1 >> 4) + 1):
                if sy in secs:
                    ids, pal = secs[sy]
                    lut = np.array([classify(p) for p in pal], np.uint8)
                    block = lut[ids].reshape(16, 16, 16)          # y, z, x
                    for i, p in enumerate(pal):
                        if lut[i] == 2:
                            built[p.split('[')[0]] += int((ids == i).sum())
                else:
                    block = np.zeros((16, 16, 16), np.uint8)
                ys, zs, xs = sy * 16, cz * 16, cx * 16
                a0, a1 = max(ys, y0), min(ys + 15, y1)
                b0, b1 = max(zs, z0), min(zs + 15, z1)
                c0, c1 = max(xs, x0), min(xs + 15, x1)
                if a0 > a1 or b0 > b1 or c0 > c1:
                    continue
                cls[a0 - y0:a1 - y0 + 1, b0 - z0:b1 - z0 + 1, c0 - x0:c1 - x0 + 1] = \
                    block[a0 - ys:a1 - ys + 1, b0 - zs:b1 - zs + 1, c0 - xs:c1 - xs + 1]
    np.savez_compressed(out, classes=cls, origin=np.array([x0, y0, z0]))
    print('saved', out, cls.shape, 'built top', built.most_common(25))


if __name__ == '__main__':
    main(sys.argv[1], *sys.argv[2:])
