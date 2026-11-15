"""Face the bare earth of a cut hillside (house plots dug into a slope) with masonry.

wall_dirt.py <x0,z0,x1,z1> <y0,y1> <out>

A cut face is a column run, at least 4 high, of solid cells each with open air on a horizontal side:
the vertical stone face of a dug plot with its dirt cap, or a trench beside a house. Dirt in such a
run becomes stone bricks, the masonry of a Japanese retaining wall (kenchi-ishi), with a mossy brick
here and there. One- to three-high grass terrace steps on the natural slope are not cuts and stay;
grass tops stay too, so every wall keeps its green lip. Cells inside a writer protection or with a
block entity are refused.
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
MIN_CUT = 4


def exposed(w, x, y, z):
    s = w.get(x, y, z) or ''
    if not s or is_open(s) or 'leaves' in s or 'log' in s:
        return None
    for dx, dz in SIDES:
        t = w.get(x + dx, y, z + dz)
        # leaves count as open: cut-off crowns decay as soon as a client ticks the chunk
        if t is not None and (is_open(t) or 'leaves' in t):
            return s
    return None


def cut_dirt(w, x, z, y0, y1):
    """Dirt cells of this column that sit in an exposed run at least MIN_CUT high."""
    col = [exposed(w, x, y, z) for y in range(y0, y1 + 1)]
    out, i = [], 0
    while i < len(col):
        if col[i] is None:
            i += 1
            continue
        j = i
        while j < len(col) and col[j] is not None:
            j += 1
        if j - i >= MIN_CUT:
            out += [y0 + k for k in range(i, j) if 'dirt' in col[k] and 'grass' not in col[k]]
        i = j
    return out


def main(box, ys, out):
    x0, z0, x1, z1 = box
    w = World(REGION)
    gs = guards()
    rows, refused = [], Counter()
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            for y in cut_dirt(w, x, z, ys[0], ys[1]):
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
