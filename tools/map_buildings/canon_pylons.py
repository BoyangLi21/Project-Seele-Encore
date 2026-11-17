"""Transmission pylons on the ridge north of Tokyo-3, original design: iron-bar lattice towers on one line (z fixed) so
the conductors run straight and level from tower to tower, two crossarms, chain insulators, an earth wire on top.

  python canon_pylons.py <out dir>
"""
import json, sys
from collections import Counter
from pathlib import Path
from mca import REGION, World
from float_fix import guards

M = lambda n: 'minecraft:' + n
SOFT = ('leaves', '_log', 'short_grass', 'tall_grass', 'fern', 'flower', 'bush', 'sapling', 'vine', 'snow[')
LINE_Z = -405
TOWERS_X = (-180, -60, 60)
ARM_Y, TOP_Y = 222, 236                       # conductors hang at ARM_Y - 2, the earth wire on the top
ARM = 7


def bar(**conn):
    p = {k: 'false' for k in ('east', 'north', 'south', 'west')}
    p.update({k: 'true' for k, v in conn.items() if v})
    return M('iron_bars[' + ','.join(f'{k}={p[k]}' for k in ('east', 'north', 'south')) + ',waterlogged=false,west=' + p['west'] + ']')


POST = bar()
RUN_X = bar(east=True, west=True)
RUN_Z = bar(north=True, south=True)


def plan(out):
    w = World(REGION)
    gs = guards()
    c, rep = {}, Counter()

    def ground(x, z):
        for y in range(260, 40, -1):
            s = w.get(x, y, z) or ''
            if s and not s.endswith(':air') and not any(k in s for k in SOFT):
                return y
        return 40

    for tx in TOWERS_X:
        g0 = min(ground(tx + dx, LINE_Z + dz) for dx in (-3, 3) for dz in (-3, 3))
        for y in range(g0 + 1, TOP_Y + 1):
            t = (y - g0) / (TOP_Y - g0)
            half = max(1, round(3 - 2 * t))
            legs = [(tx - half, LINE_Z - half), (tx + half, LINE_Z - half), (tx - half, LINE_Z + half), (tx + half, LINE_Z + half)]
            for lx, lz in legs:
                if y > ground(lx, lz):
                    c[lx, y, lz] = POST
            if (y - g0) % 5 == 0:                               # horizontal bracing ring
                for x in range(tx - half, tx + half + 1):
                    for z in (LINE_Z - half, LINE_Z + half):
                        if y > ground(x, z):
                            c[x, y, z] = RUN_X if x not in (tx - half, tx + half) else POST
                for z in range(LINE_Z - half + 1, LINE_Z + half):
                    for x in (tx - half, tx + half):
                        if y > ground(x, z):
                            c[x, y, z] = RUN_Z
        for ay in (ARM_Y, ARM_Y + 8):                           # two crossarms across the line
            for z in range(LINE_Z - ARM, LINE_Z + ARM + 1):
                c[tx, ay, z] = RUN_Z
        for ay in (ARM_Y, ARM_Y + 8):
            for z in (LINE_Z - ARM, LINE_Z + ARM):
                c[tx, ay - 1, z] = M('chain[axis=y,waterlogged=false]')     # insulator string
        c[tx, TOP_Y + 1, LINE_Z] = M('lightning_rod[facing=up,powered=false,waterlogged=false]')
        rep['towers'] += 1
    # conductors and the earth wire, straight along x between neighbouring towers
    for a, b in zip(TOWERS_X, TOWERS_X[1:]):
        for y, z in ((ARM_Y - 2, LINE_Z - ARM), (ARM_Y - 2, LINE_Z + ARM), (ARM_Y + 6, LINE_Z - ARM), (ARM_Y + 6, LINE_Z + ARM), (TOP_Y, LINE_Z)):
            for x in range(a + 1, b):
                c.setdefault((x, y, z), M('chain[axis=x,waterlogged=false]'))
        rep['spans'] += 1
    rows, refused = [], Counter()
    for (x, y, z), want in c.items():
        cur = w.get(x, y, z)
        if cur is None or cur == want:
            continue
        if not (cur.endswith(':air') or any(k in cur for k in SOFT)):
            refused['occupied'] += 1; continue
        try:
            for g in gs:
                g.assert_positions([(x, y, z)])
        except ValueError:
            refused['protected'] += 1; continue
        rows.append([x, y, z, cur, want])
    for st in set(r[4] for r in rows):
        if '[' in st:
            props = st[st.index('[') + 1:-1].split(',')
            assert props == sorted(props), st
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    rep = dict(rep, rows=len(rows), refused=dict(refused))
    (Path(out) / 'report.json').write_text(json.dumps(rep, indent=1), 'utf8')
    print(json.dumps(rep))


if __name__ == '__main__':
    plan(sys.argv[1])
