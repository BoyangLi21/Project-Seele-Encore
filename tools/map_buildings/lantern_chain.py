"""Hang the loose lights of the GeoFront halls from their ceiling with chains.

lantern_chain.py <pieces.json> <out dir> [max gap]

For each isolated one-block light piece (sea lantern, lantern, glowstone, NERV ceiling light) from
float_blocks.py, look straight up: when a solid block stands 1..max gap (default 3) cells above
it, the open cells between become vertical chains, so the light reads as a hanging lamp. Lights
with no ceiling that close are only reported. Cells in protected volumes are never planned.
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from float_blocks import is_solid
from float_fix import guards

CHAIN = 'minecraft:chain[axis=y,waterlogged=false]'
LIGHTS = ('sea_lantern', 'lantern', 'glowstone', 'nerv_ceiling_light', 'shroomlight')


def main(src, out, max_gap=3):
    w = World(REGION)
    gs = guards()
    rows, why = [], Counter()
    for p in json.load(open(src)):
        if p['size'] != 1 or not p.get('iso') or not any(l in k for k in p['kinds'] for l in LIGHTS):
            continue
        x, y, z = p['at']
        gap = None
        for k in range(1, int(max_gap) + 2):
            if is_solid(w.get(x, y + k, z) or 'minecraft:air'):
                gap = k - 1
                break
        if not gap:
            why['no ceiling within reach' if gap is None else 'touching already'] += 1
            continue
        cells = [(x, y + k, z) for k in range(1, gap + 1)]
        try:
            for g in gs:
                g.assert_positions(cells)
        except ValueError:
            why['protected'] += 1
            continue
        rows += [[*c, w.get(*c), CHAIN] for c in cells]
        why['chained'] += 1
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    print(len(rows), 'rows', dict(why))


if __name__ == '__main__':
    main(*sys.argv[1:])
