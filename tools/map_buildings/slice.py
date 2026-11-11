"""Print a block slice: slice.py x0 x1 y0 y1 z0 z1 (one of the ranges may be a single value); legend after."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import short

w = World(sys.argv[7] if len(sys.argv) > 7 else REGION)
x0, x1, y0, y1, z0, z1 = map(int, sys.argv[1:7])
legend = {}
sym = iter('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789#$%&*+=?@')
for y in range(y1, y0 - 1, -1):
    print(f'y={y}')
    for z in range(z0, z1 + 1):
        line = ''
        for x in range(x0, x1 + 1):
            s = w.get(x, y, z)
            n = 'None' if s is None else short(s)
            if n in ('air', 'cave_air'):
                line += '.'
                continue
            if n not in legend:
                legend[n] = next(sym)
            line += legend[n]
        print(f'  z={z:5d} {line}')
print({v: k for k, v in legend.items()})
