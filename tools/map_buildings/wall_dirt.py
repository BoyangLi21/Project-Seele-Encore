"""Face bare earth beside a retaining wall or a house cut with masonry.

wall_dirt.py <x0,z0,x1,z1> <y0,y1> <out>

Every dirt cell in the box with open air on a horizontal side is a bare earth face (a hill cut off
beside a house, a terrace edge). It becomes stone bricks, the masonry of a Japanese retaining wall
(kenchi-ishi), with a mossy brick here and there. Grass tops stay: only the exposed dirt below them
changes, so the slope keeps its green edge. Cells inside a writer protection or with a block entity
are refused.
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open
from city_restyle import M, h
from float_fix import guards

SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))


def bare(w, x, y, z):
    s = w.get(x, y, z) or ''
    if 'dirt' not in s or 'grass' in s:
        return False
    for dx, dz in SIDES:
        t = w.get(x + dx, y, z + dz)
        if t is not None and is_open(t):
            return True
    return False


def main(box, ys, out):
    x0, z0, x1, z1 = box
    w = World(REGION)
    gs = guards()
    rows, refused = [], Counter()
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            for y in range(ys[0], ys[1] + 1):
                if not bare(w, x, y, z):
                    continue
                want = M('mossy_stone_bricks') if h('moss', x, y, z) % 6 == 0 else M('stone_bricks')
                try:
                    for g in gs:
                        g.assert_positions([(x, y, z)])
                except ValueError:
                    refused['protected'] += 1
                    continue
                if w.block_entity(x, y, z):
                    refused['block entity'] += 1
                    continue
                rows.append([x, y, z, w.get(x, y, z), want])
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    cols = Counter((r[0], r[2]) for r in rows)
    print('rows', len(rows), 'columns', len(cols), 'refused', dict(refused))


if __name__ == '__main__':
    main([int(v) for v in sys.argv[1].split(',')], [int(v) for v in sys.argv[2].split(',')], sys.argv[3])
