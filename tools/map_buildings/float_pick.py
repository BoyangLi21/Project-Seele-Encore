"""Choose which float_blocks.py pieces to remove: the ones that read as floating in game.

float_pick.py <pieces.json> <out.json>

Kept out: the GeoFront hanging city and anything with nothing under it (gap >= 200), pieces at
or below y 40 (underground halls, judged apart), lift cabins, cable-car parts, airport hangar
panels standing on barriers, and built pieces with other man-made blocks within 3 cells (trim
standing off a facade, a lamp head beside its post: they read as attached). Taken: pieces that
touch nothing at all, even at a corner (iso), and leaf scraps with no trunk within 2.
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, is_natural

SKIP = ('nerv_wall_panel', 'mtr:', 'skyweave', 'period_station_floor', 'nerv_machine_edge', 'clear_glass',
        'stained_glass', 'elevator', 'lift')
LOOSE = ('leaves', '_log', 'lantern', 'chain', 'torch', 'flower', 'bluet', 'poppy', 'dandelion', 'daisy', 'tulip',
         'cornflower', 'grass', 'fern', 'bush')


def near_built(w, p):
    x0, y0, z0, x1, y1, z1 = p['bbox']
    for x in range(x0 - 3, x1 + 4):
        for z in range(z0 - 3, z1 + 4):
            for y in range(y0 - 3, y1 + 4):
                if x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1:
                    continue
                s = w.get(x, y, z) or 'minecraft:air'
                if not is_open(s) and not is_natural(s) and 'leaves' not in s and '_log' not in s:
                    return True
    return False


def main(src, out):
    w = World(REGION)
    picked, why = [], Counter()
    for p in json.load(open(src)):
        ks = ' '.join(p['kinds'])
        if p['gap'] >= 200 or p['at'][1] <= 40 or any(s in ks for s in SKIP):
            why['kept: structure or underground'] += 1
            continue
        if not (p.get('iso') or (p['cat'] == 'canopy' and p.get('logs_near') == 0)):
            continue
        if p['cat'] == 'built' and not all(any(l in k for l in LOOSE) for k in p['kinds']) and near_built(w, p):
            why['kept: trim beside a structure'] += 1
            continue
        picked.append(p)
        why['picked ' + p['cat']] += 1
    json.dump(picked, open(out, 'w'))
    print(len(picked), 'pieces', sum(p['size'] for p in picked), 'blocks', dict(why))


if __name__ == '__main__':
    main(*sys.argv[1:])
