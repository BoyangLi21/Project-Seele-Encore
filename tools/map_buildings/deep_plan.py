"""Rows that take a swallowed building away and close the slope over its place.

The building is the flooded set of building blocks above its floor (deep_check.building_set).
Over its columns the new ground height comes from the terrain around it (inverse-distance
average of the ground 1..4 columns outside); below it earth (grass, three dirt, then stone),
above it air. Only the building's own blocks, open cells and natural cells are written.
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, is_natural, short
from e5_plan import is_building, is_veg
import deep_check as dc

GRASS, DIRT, STONE, AIRS = 'minecraft:grass_block[snowy=false]', 'minecraft:dirt', 'minecraft:stone', 'minecraft:air'
w = dc.w


def ground(x, z, top):
    y = top
    while y > top - 80:
        s = w.get(x, y, z)
        if s is None:
            return None
        if is_natural(s):
            return y
        if not (is_open(s) or is_veg(s)):
            return None          # built over: not a ground sample
        y -= 1
    return None


def plan_building(b):
    cells = dc.building_set(b)
    cols = {(x, z) for x, y, z in cells}
    x0 = min(c[0] for c in cols); x1 = max(c[0] for c in cols)
    z0 = min(c[1] for c in cols); z1 = max(c[1] for c in cols)
    F, hi = b['floor'], max(y for _, y, _ in cells) + 1
    samples = []
    for x in range(x0 - 4, x1 + 5):
        for z in range(z0 - 4, z1 + 5):
            if (x, z) in cols:
                continue
            d = min(max(abs(x - cx), abs(z - cz)) for cx, cz in cols) if len(cols) < 400 else 1
            if 1 <= d <= 4:
                g = ground(x, z, hi + 20)
                if g is not None:
                    samples.append((x, z, g))
    rows = {}
    for (x, z) in cols:
        num = den = 0.0
        for sx, sz, g in samples:
            wgt = 1.0 / ((sx - x) ** 2 + (sz - z) ** 2)
            num += wgt * g
            den += wgt
        S = round(num / den) if den else F
        for y in range(F + 1, max(hi, S) + 1):
            cur = w.get(x, y, z)
            if (x, y, z) not in cells and not (is_open(cur) or is_natural(cur)):
                continue
            want = GRASS if y == S else DIRT if S - 3 <= y < S else STONE if y < S else AIRS
            if y > S and cur in ('minecraft:air', 'minecraft:cave_air'):
                continue
            if cur != want and not (want == STONE and is_natural(cur) and (x, y, z) not in cells):
                rows[x, y, z] = [x, y, z, cur, want]
    return list(rows.values()), len(samples)


if __name__ == '__main__':
    ids = sys.argv[1].split(',')
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    allrows, report = [], []
    for b in dc.deep:
        if b['id'] not in ids:
            continue
        rows, ns = plan_building(b)
        bes = [r[:3] for r in rows if w.block_entity(*r[:3])]
        kinds = Counter(short(r[3]) + '->' + short(r[4]) for r in rows)
        report.append(dict(id=b['id'], bbox=b['bbox'], cells=len(rows), samples=ns, block_entities=bes, kinds=dict(kinds.most_common(10))))
        print(b['id'], len(rows), 'samples', ns, 'BE', len(bes), kinds.most_common(6))
        allrows += rows
    (out / 'rows.json').write_text(json.dumps(allrows), 'utf8')
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf8')
    print('total', len(allrows))
