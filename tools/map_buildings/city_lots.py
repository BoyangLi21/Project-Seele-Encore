"""Survey of the Tokyo-3 grid lots: which hold a lift tower, which are built on, protected or empty.

Called as city_lots.py <out.json>. The grid is 40 cells (towers sit in the middle of a cell, 9-wide
roads on the lines); a lot is the cell centre +-16 (the sidewalk edge). For every lot without a tower
it counts what stands above street level (y 81..150), what the street-level surface is, and whether
any sample point falls inside the writer's protections (lift travel, launch volumes, lifts).
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open
from city_restyle import topology
from float_fix import guards

Y, HALF = 80, 16
XS = range(-290, 271, 40)
ZS = range(20, 541, 40)


def protected(gs, pts):
    hits = Counter()
    for p in pts:
        for g in gs:
            try:
                g.assert_positions([p])
            except ValueError as e:
                hits[type(g).__name__] += 1
                break
    return dict(hits)


def main(out):
    w = World(REGION)
    gs = guards()
    towers = topology()
    lots = []
    for cz in ZS:
        for cx in XS:
            lot = dict(cx=cx, cz=cz, box=[cx - HALF, cz - HALF, cx + HALF, cz + HALF])
            t = [tw for tw in towers if abs(tw['centre'][0] - cx) <= 20 and abs(tw['centre'][2] - cz) <= 20]
            if t:
                lot.update(kind='tower', towers=[tw['id'] for tw in t])
                lots.append(lot)
                continue
            built, ground, top = Counter(), Counter(), Y
            for x in range(cx - HALF, cx + HALF + 1):
                for z in range(cz - HALF, cz + HALF + 1):
                    g = w.get(x, Y, z)
                    ground[(g or 'None').split('[')[0].split(':')[-1]] += 1
                    for y in range(Y + 1, 151):
                        s = w.get(x, y, z)
                        if s and not is_open(s):
                            built[s.split('[')[0].split(':')[-1]] += 1
                            top = max(top, y)
            pts = [(x, y, z) for x in range(cx - HALF, cx + HALF + 1, 4) for z in range(cz - HALF, cz + HALF + 1, 4) for y in (81, 100, 130)]
            lot.update(built=sum(built.values()), built_kinds=dict(built.most_common(6)), top=top,
                       ground=dict(ground.most_common(4)), protected=protected(gs, pts))
            n = lot['built']
            lot['kind'] = 'protected' if lot['protected'] else 'empty' if n < 60 else 'light' if n < 600 else 'built'
            lots.append(lot)
    Path(out).write_text(json.dumps(lots, indent=1), 'utf8')
    sym = dict(tower='T', protected='P', empty='.', light='l', built='B')
    print('     ' + ''.join(f'{x:>5}' for x in XS))
    for cz in ZS:
        print(f'{cz:>5}' + ''.join(f'{sym[l["kind"]]:>5}' for l in lots if l['cz'] == cz))
    print(Counter(l['kind'] for l in lots))


if __name__ == '__main__':
    main(sys.argv[1])
