"""Bare dirt faces a rows list would leave: dirt the plan writes or leaves with open air beside it.

exposed_check.py <rows.json> [out.json]

The rows are applied in memory over the world (BUILDINGS_WORLD). A dirt cell with an open
horizontal neighbour after the change is a bare earth face: a step of two or more in a fill, or
a fill cut off at a road, house or write-box edge. Faces are grouped by column and by why the
neighbour is open (beside a planned cell, or beside an untouched one).
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, short


def main(rows_file, out=None):
    w = World(REGION)
    rows = json.load(open(rows_file))
    after = {tuple(r[:3]): r[4] for r in rows}

    def get(c):
        return after[c] if c in after else w.get(*c)

    faces, cols, why = [], set(), Counter()
    for c, a in after.items():
        if 'dirt' not in a or 'grass' in a:
            continue
        x, y, z = c
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y, z + dz)
            s = get(n)
            if s and is_open(s):
                # a face under a deck or eave is out of the light and rarely seen: count it apart
                covered = any(not is_open(get((n[0], y + k, n[2])) or 'minecraft:air') and 'leaves' not in (get((n[0], y + k, n[2])) or '')
                              for k in range(1, 24))
                if covered:
                    why['covered'] += 1
                    break
                faces.append([x, y, z, dx, dz])
                cols.add((x, z))
                why['open sky, beside planned' if n in after else 'open sky, beside untouched'] += 1
                break
    print(rows_file, 'rows', len(rows), 'bare dirt faces under open sky', len(faces), 'columns', len(cols), dict(why))
    if out:
        json.dump(faces, open(out, 'w'))


if __name__ == '__main__':
    main(*sys.argv[1:])
