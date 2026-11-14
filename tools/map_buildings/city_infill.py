"""Static infill on an empty Tokyo-3 parcel: a mid-rise block, a shop block and a pocket plaza.

Called as city_restyle.py infill <x0,z0,x1,z1> <out dir>, with the parcel inside the roads
(street level y 80). A 4-cell strip along the parcel edge becomes a paved sidewalk with street
trees, lamps and a bus shelter, so street plus sidewalks stay at least 17 cells wide for an EVA;
the buildings stand inside it. Rows are planned only where the world is open air or the ground
surface, and never inside a lift tower's travel space, a launch volume or a lift.
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World, WORLD
from blocks import is_open
from city_restyle import Model, apartments, lowrise, M, SLAB, h, AIR
from float_fix import guards

Y = 80
POST = M('polished_basalt[axis=y]')   # the city's own street lamp: basalt post, sea lantern, slab cap


def tree(cells, x, z, kind):
    log, leaf = M(kind + '_log[axis=y]'), M(kind + '_leaves[distance=1,persistent=true,waterlogged=false]')
    for y in range(Y + 1, Y + 5):
        cells[x, y, z] = log
    for dy in (4, 5, 6):
        r = 2 if dy < 6 else 1
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if abs(dx) + abs(dz) <= r + (1 if dy == 5 else 0) and (dx, dz) != (0, 0) or dy == 6:
                    cells.setdefault((x + dx, Y + dy, z + dz), leaf)


def lamp(cells, x, z):
    for y in range(Y + 1, Y + 5):
        cells[x, y, z] = POST
    cells[x, Y + 5, z] = M('sea_lantern')
    cells[x, Y + 6, z] = SLAB('smooth_stone')


def city_posts(w, x0, z0, x1, z1):
    """Street lamps the city already has on or next to the parcel (kept; nothing planted beside them)."""
    return [(x, z) for x in range(x0 - 2, x1 + 3) for z in range(z0 - 2, z1 + 3)
            if 'polished_basalt' in (w.get(x, Y + 1, z) or '') and 'sea_lantern' in (w.get(x, Y + 5, z) or '')]


def shelter(cells, x0, z0, along_x):
    """Bus shelter, 5 long: posts, glass back, slab roof, bench."""
    for i in range(5):
        x, z = (x0 + i, z0) if along_x else (x0, z0 + i)
        bx, bz = (x, z0 + 1) if along_x else (x0 + 1, z)
        for y in (Y + 1, Y + 2):
            cells[bx, y, bz] = M('light_gray_stained_glass')
        cells[bx, Y + 3, bz] = SLAB('smooth_stone')
        cells[x, Y + 3, z] = SLAB('smooth_stone')
        if i in (0, 4):
            for y in (Y + 1, Y + 2):
                cells[x, y, z] = M('polished_andesite')
        else:
            cells[x, Y + 1, z] = M('dark_oak_slab[type=bottom,waterlogged=false]')


def place(cells, m, ox, oz):
    for (x, y, z), s in m.v.items():
        cells[ox + x, Y + y, oz + z] = s


def main(box, out):
    x0, z0, x1, z1 = box
    w = World(REGION)
    seed = h('infill', x0, z0)
    cells = {}
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            edge = min(x - x0, x1 - x, z - z0, z1 - z)
            if edge < 4:
                cells[x, Y, z] = M('smooth_stone') if edge else M('polished_andesite')   # kerb, then paving
    # street trees and lamps on the sidewalk, one cell in from the kerb; the city's own lamps stay and
    # nothing goes within 3 cells of them (a canopy over a lamp hides its light)
    posts = city_posts(w, x0, z0, x1, z1)
    clear = lambda x, z: all(max(abs(x - px), abs(z - pz)) > 3 for px, pz in posts)
    spots = [(x, z, i % 2 == 0) for i, x in enumerate(range(x0 + 3, x1 - 2, 6)) for z in (z0 + 1, z1 - 1)]
    spots += [(x, z, i % 2 == 1) for i, z in enumerate(range(z0 + 6, z1 - 5, 6)) for x in (x0 + 1, x1 - 1)]
    for x, z, is_tree in spots:
        if clear(x, z):
            (tree(cells, x, z, 'birch') if is_tree else lamp(cells, x, z))
    shelter(cells, x0 + (x1 - x0) // 2 - 2, z1 - 2, True)
    ix0, iz0, ix1, iz1 = x0 + 4, z0 + 4, x1 - 4, z1 - 4
    W, D = ix1 - ix0 + 1, iz1 - iz0 + 1
    north = Model(W, D // 2, seed)
    apartments(north, 26)
    place(cells, north, ix0, iz0)
    shop = Model(W // 2, D - D // 2 - 1, seed ^ 7)
    lowrise(shop, 17)
    place(cells, shop, ix0 + W - W // 2, iz0 + D // 2 + 1)
    # pocket plaza in the remaining corner: paving, a tree, benches
    px0, pz0, px1, pz1 = ix0, iz0 + D // 2 + 1, ix0 + W - W // 2 - 2, iz1
    for x in range(px0, px1 + 1):
        for z in range(pz0, pz1 + 1):
            cells[x, Y, z] = M('polished_andesite') if (x + z) % 2 else M('smooth_stone')
    tree(cells, (px0 + px1) // 2, (pz0 + pz1) // 2, 'oak')
    for x in range(px0 + 1, px1, 3):
        cells[x, Y + 1, pz1] = M('spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
    gs = guards()
    rows, refused, refused_at = [], Counter(), []
    for (x, y, z), want in cells.items():
        cur = w.get(x, y, z)
        if cur is None or cur == want:
            continue
        ground = y == Y and ('grass' in cur or 'dirt' in cur or 'stone' in cur)
        if not (is_open(cur) or ground or 'leaves' in cur or 'short_grass' in cur or 'tall_grass' in cur):
            refused['occupied'] += 1
            refused_at.append([x, y, z, cur, want])
            continue
        try:
            for g in gs:
                g.assert_positions([(x, y, z)])
        except ValueError:
            refused['protected'] += 1
            continue
        if w.block_entity(x, y, z):
            refused['block entity'] += 1
            continue
        rows.append([x, y, z, cur, want])
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (Path(out) / 'refused.json').write_text(json.dumps(refused_at), 'utf8')
    print('infill rows', len(rows), 'refused', dict(refused))
