"""Canon street furniture for Tokyo-3: utility poles with overhead wires along the sidewalks, transformer boxes,
air-raid sirens, shelter entrances and static traffic lights. Original vanilla-block designs.

  python canon_street.py <out dir> [x0,z0,x1,z1]

Lots are the 33 x 33 squares round the grid centres (x -290..270, z 20..540, every 40). Everything stands on the lot's
own sidewalk ring (ring 1 = the cell next to the kerb, ring 2 = trees and lamps), so nothing spans a street and the
EVA corridor between the buildings keeps its middle clear. Wires run at street + 8, above tree crowns and lamps.
An element is planned only if every cell it needs is air now and outside the protection tables; otherwise the whole
element is skipped and reported, so trees, lamps, buildings and roads are never touched.
"""
import json, sys
from collections import Counter
from pathlib import Path
from mca import REGION, World
from float_fix import guards
from city_body_sync import topology
from mca import WORLD

Y = 80
M = lambda n: 'minecraft:' + n
WALL = M('andesite_wall[east=none,north=none,south=none,up=true,waterlogged=false,west=none]')
INSUL = M('end_rod[facing=up]')
CH = {'x': M('chain[axis=x,waterlogged=false]'), 'z': M('chain[axis=z,waterlogged=false]')}


def lots():
    for ix, cx in enumerate(range(-290, 271, 40)):
        for iz, cz in enumerate(range(20, 541, 40)):
            yield ix, iz, cx, cz


def plan(out, box=None):
    w = World(REGION)
    gs = guards()
    towers = [s['centre'] for s in topology(WORLD).values()]
    # cells the street-fixture table (battlefield_r21.json) puts back before a raise count as taken: after the first
    # raise in play those fixtures stand there for good
    fixtures = {tuple(c[:3]) for c in json.load(open(Path(WORLD) / 'battlefield_r21.json', encoding='utf8'))['cells']
                if not str(c[3]).endswith(':air')}
    rows, signs, rep = [], [], Counter()
    taken = set()

    def free(cells):
        for (x, y, z) in cells:
            if (x, y, z) in taken or (x, y, z) in fixtures or (w.get(x, y, z) or '') != 'minecraft:air':
                return False
        try:
            for g in gs:
                g.assert_positions(list(cells))
        except ValueError:
            return False
        return True

    def ground(x, z):
        """Top of the solid ground at a spot (lawns and kerb ramps can stand above street level)."""
        for y in range(Y + 5, Y - 3, -1):
            s = w.get(x, y, z) or ''
            if s and not s.endswith(':air') and not any(k in s for k in ('leaves', 'short_grass', 'tall_grass', 'fern', 'flower')):
                return y
        return Y

    def commit(cells, kind):
        for (x, y, z), s in cells.items():
            rows.append([x, y, z, 'minecraft:air', s]); taken.add((x, y, z))
        rep[kind] += 1

    for ix, iz, cx, cz in lots():
        x0, z0 = cx - 16, cz - 16
        if box and not (box[0] <= cx <= box[2] and box[1] <= cz <= box[3]):
            continue
        L = lambda lx, lz: (x0 + lx, z0 + lz)
        # a real lot: solid ground (sidewalk, kerb or lawn) at street level along ring 1, nothing standing on it
        side = [w.get(x0 + lx, Y, z0 + 1) for lx in range(3, 30, 6)]
        if sum(1 for s in side if s and not s.endswith(':air') and 'water' not in s) < 4:
            rep['not a lot'] += 1
            continue
        tower = any(abs(tx - cx) <= 16 and abs(tz - cz) <= 16 for tx, ty, tz in towers)
        dense = not tower                                       # infill and housing lots get poles closer together
        us = (1, 11, 21, 31) if dense else (1, 16, 31)
        poles = {(u, 1) for u in us} | {(u, 31) for u in us} | {(1, u) for u in us} | {(31, u) for u in us}
        siren = ix % 2 == 0 and iz % 2 == 0
        # utility poles
        placed = set()
        for lx, lz in sorted(poles):
            x, z = L(lx, lz)
            top = Y + (10 if siren and (lx, lz) == (1, 1) else 8)
            g = ground(x, z)
            if g > Y + 4:
                rep['pole on high ground skipped'] += 1
                continue
            cells = {(x, y, z): WALL for y in range(g + 1, top + 1)}
            if siren and (lx, lz) == (1, 1):
                cells[x, top + 1, z] = M('gray_concrete')
                cells[x - 1, top + 1, z] = M('iron_trapdoor[facing=west,half=top,open=true,powered=false,waterlogged=false]')
                cells[x, top + 1, z - 1] = M('iron_trapdoor[facing=north,half=top,open=true,powered=false,waterlogged=false]')
                kind = 'siren'
            else:
                cells[x, top + 1, z] = INSUL
                kind = 'pole'
            mid = (lx in (16, 11, 21) and lz in (1, 31)) or (lz in (16, 11, 21) and lx in (1, 31))
            if mid:                                             # transformer box on the lot side of the pole
                tx, tz = L(lx + (1 if lx == 1 else -1 if lx == 31 else 0), lz + (1 if lz == 1 else -1 if lz == 31 else 0))
                cells[tx, Y + 6, tz] = M('smooth_stone')
            if free(cells):
                commit(cells, kind); placed.add((lx, lz))
            else:
                rep[kind + ' skipped'] += 1
        # wires between neighbouring poles (a span only between two poles that both stand, so no wire end hangs) along each side, at street + 8
        for a, b in ((0, 1), (0, 31), (1, 0), (31, 0)):
            if a == 0:
                line = [(u, b) for u in range(1, 32)]; axis = 'x'
            else:
                line = [(a, u) for u in range(1, 32)]; axis = 'z'
            span, start = [], None
            for lx, lz in line:
                if (lx, lz) in poles:
                    if span and start in placed and (lx, lz) in placed:
                        cells = {(L(sx, sz)[0], Y + 8, L(sx, sz)[1]): CH[axis] for sx, sz in span}
                        if free(cells):
                            commit(cells, 'wire span')
                        else:
                            rep['wire span skipped'] += 1
                    elif span:
                        rep['wire span without both poles'] += 1
                    span, start = [], (lx, lz)
                else:
                    span.append((lx, lz))
        # shelter entrance on one lot of each 2 x 2 block: kiosk on the south sidewalk near the south-west corner
        if ix % 2 == 1 and iz % 2 == 1:
            cells = {}
            for lx in (2, 3, 4):
                for lz in (29, 30, 31):
                    x, z = L(lx, lz)
                    back, sidewall = lz == 29, lx in (2, 4)
                    for y in range(Y + 1, Y + 4):
                        if back or (sidewall and lz != 31):
                            cells[x, y, z] = M('light_gray_concrete')
                        elif not back:
                            cells[x, y, z] = 'minecraft:air'
                    cells[x, Y + 4, z] = M('smooth_stone_slab[type=bottom,waterlogged=false]')
            dx, dz = L(3, 29)
            cells[dx, Y + 1, dz] = M('iron_door[facing=south,half=lower,hinge=left,open=false,powered=false]')
            cells[dx, Y + 2, dz] = M('iron_door[facing=south,half=upper,hinge=left,open=false,powered=false]')
            sx, sz = L(3, 30)
            cells[sx, Y + 3, sz] = M('birch_wall_sign[facing=south,waterlogged=false]')
            need = {k: v for k, v in cells.items() if v != 'minecraft:air'}
            if free(need):
                commit(need, 'shelter')
                signs.append(dict(pos=[sx, Y + 3, sz], front=['避難所', 'SHELTER', '', ''], color='green'))
            else:
                rep['shelter skipped'] += 1
        # static traffic lights at alternate intersections: two heads on the corner of this lot
        if ix % 2 == 0 and iz % 2 == 1:
            for pole, heads in (((3, 1), [(2, 0), (3, 0), (4, 0)]), ((1, 3), [(0, 2), (0, 3), (0, 4)])):
                px, pz = L(*pole)
                cells = {(px, y, pz): WALL for y in range(ground(px, pz) + 1, Y + 5)}
                for (hx, hz), col in zip(heads, ('lime_concrete', 'yellow_concrete', 'red_concrete')):
                    x, z = L(hx, hz)
                    cells[x, Y + 5, z] = M(col)
                    cells[x, Y + 6, z] = M('black_concrete')
                if free(cells):
                    commit(cells, 'traffic light')
                else:
                    rep['traffic light skipped'] += 1
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (Path(out) / 'signs.json').write_text(json.dumps(signs, ensure_ascii=False, indent=1), 'utf8')
    (Path(out) / 'report.json').write_text(json.dumps(dict(rows=len(rows), signs=len(signs), elements=rep), indent=1, ensure_ascii=False), 'utf8')
    print(len(rows), len(signs), dict(rep))


if __name__ == '__main__':
    plan(sys.argv[1], [int(v) for v in sys.argv[2].split(',')] if len(sys.argv) > 2 else None)
