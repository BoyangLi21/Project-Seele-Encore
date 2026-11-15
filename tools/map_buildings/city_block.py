"""Static city blocks on the empty Tokyo-3 grid lots, filled edge to edge as Japanese blocks are.

city_block.py lots <cx,cz;cx,cz;...|all> <out dir> [lots.json]

A lot is a grid cell centre +-16 (city_lots.py). Its outer ring is the city's TrafficCraft kerb and
is left alone; rings 1-3 become the sidewalk with street trees and lamps (the city's own lamps are
kept, nothing is planted within 3 cells of them); the 25 x 25 inside is split into parcels that touch
each other, and each parcel gets a building: offices, flats, shop-and-flat blocks, narrow shops, a
multistorey car park, a clinic, a pocket park or a small shrine; a few lots become a whole park or a
school. Street plus sidewalks stay 17 wide, wall to wall. 4 to 15 storeys, so the lift towers stay
the peaks. Rows are planned only on open air, plants, the old lawn tree and the ground surface of a
lot, never on a road piece, a block entity or inside a protected volume.
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open
from city_restyle import (Model, office, apartments, mixed, lowrise, vsign, floor_ring, lit, roof_plant,
                          M, SLAB, h, AIR, SIGN_FACES)
from city_infill import tree, lamp, city_posts, Y, SUMMER_TREES, species, crown
from float_fix import guards

HALF, IN = 16, 4                      # lot half size; buildings start 4 in from the lot edge
N = 2 * (HALF - IN) + 1               # 25: the buildable square

# lots kept free: the central launch block, the battle plaza and the two substations
# (city origin (30, 80, 220) + ThirdTokyoSurfaceBuilder offsets)
RESERVED = {(x, z) for x in (-10, 30, 70) for z in (180, 220, 260)} | {(30, 300), (30, 140), (110, 220)}
RESERVED |= {(-210, 340)}           # the M5 pilot block, written on its own

LAYOUTS = (
    ('one', ((0, 0, 25, 25),)),
    ('two', ((0, 0, 12, 25), (12, 0, 13, 25))),
    ('three', ((0, 0, 25, 11), (0, 11, 12, 14), (12, 11, 13, 14))),
    ('four', ((0, 0, 12, 12), (12, 0, 13, 12), (0, 12, 12, 13), (12, 12, 13, 13))),
    ('row', ((0, 0, 6, 10), (6, 0, 6, 10), (12, 0, 6, 10), (18, 0, 7, 10), (0, 10, 25, 15))),
    ('row2', ((0, 0, 8, 9), (8, 0, 8, 9), (16, 0, 9, 9), (0, 9, 12, 16), (12, 9, 13, 16))),
)
LAYOUT_WEIGHTS = (1, 3, 3, 3, 3, 2)


def rot(p, r):
    """Turn a parcel (x, z, w, d) in the 25 square by r quarter turns."""
    x, z, w, d = p
    for _ in range(r):
        x, z, w, d = N - z - d, x, d, w
    return x, z, w, d


def pick(seed, table):
    total = sum(w for _, w in table)
    r = h(seed) % total
    for v, w in table:
        if r < w:
            return v
        r -= w


def storeys(seed, lo, hi):
    return lo + h(seed, 'st') % (hi - lo + 1)


# --- buildings the tower set does not have -------------------------------------------------------

def carpark(m, decks):
    """Open-deck car park: columns, slab decks every 3, a waist-high parapet, stair core, lit P sign."""
    m.fill(0, 0, M('polished_andesite'))
    top = 3 * decks
    for d in range(1, decks + 1):
        y = 3 * d
        m.fill(0, y, M('smooth_stone'))
        for x, z, u, c in m.ring(0):
            m.put(x, y + 1, z, M('light_gray_concrete'))
    for y in range(1, top):
        for x, z, u, c in m.ring(0):
            if c or u % 6 == 0:
                m.put(x, y, z, M('light_gray_concrete'))
    for x in range(2, m.W - 2, 6):                  # inner columns
        for z in range(2, m.D - 2, 6):
            for y in range(1, top):
                m.put(x, y, z, M('light_gray_concrete'))
    for y in range(1, top + 4):                       # stair core rising above the top deck
        for x in (m.W - 4, m.W - 1):
            for z in (m.D - 4, m.D - 1):
                m.put(x, y, z, M('white_concrete'))
    for x in range(m.W - 4, m.W):
        for z in range(m.D - 4, m.D):
            m.put(x, top + 4, z, SLAB('smooth_stone'))
    for x in range(1, m.W - 1, 8):                    # deck lamps on the roof
        m.put(x, top + 2, 2, M('polished_basalt[axis=y]'))
        m.put(x, top + 3, 2, M('pearlescent_froglight[axis=y]'))
    for y in range(2, top + 1):
        m.put(0, y, 0, M('ochre_froglight[axis=y]') if y in (2, top) else M('blue_terracotta'))


def clinic(m, st):
    """Small white clinic: ribbon windows, glass entrance, a green cross board above the door."""
    H = 4 * st
    m.fill(0, 0, M('polished_andesite'))
    for y in range(1, H + 1):
        for x, z, u, c in m.ring(0):
            if y <= 3:
                m.put(x, y, z, M('white_concrete') if c or u % 4 == 0 else M('glass'))
            else:
                m.put(x, y, z, M('white_concrete') if c or y % 4 in (0, 1) else M('light_blue_stained_glass'))
        if y % 4 == 0:
            floor_ring(m, y, 0, 2, M('smooth_stone'))
    m.fill(0, H, M('smooth_stone'))
    for x, z, u, c in m.ring(0):
        m.put(x, H + 1, z, SLAB('smooth_quartz'))
    a = m.W // 2
    for dy in range(5):
        for dx in range(-2, 3):
            m.put(a + dx, 4 + dy, 0, M('white_concrete'))
    for d in (-1, 0, 1):
        m.put(a + d, 6, 0, M('green_concrete'))
        m.put(a, 6 + d, 0, M('green_concrete'))


def shrine(m):
    """A small Shinto shrine: gravel court, vermilion torii at the front, wooden hall, stone lanterns."""
    m.fill(0, 0, M('gravel'))
    a = m.W // 2
    for x in (a - 2, a + 2):                          # torii posts
        for y in range(1, 6):
            m.put(x, y, 0, M('red_concrete'))
    for x in range(a - 3, a + 4):
        m.put(x, 6, 0, M('black_concrete'))           # kasagi
    for x in range(a - 2, a + 3):
        m.put(x, 4, 0, M('red_concrete'))             # nuki
    for z in range(0, m.D - 5):
        m.put(a, 0, z, M('stone_bricks'))             # approach
    hz = m.D - 5
    for x in range(a - 2, a + 3):
        for z in range(hz, hz + 4):
            m.put(x, 0, z, M('stone_bricks'))
            for y in (1, 2, 3):
                if x in (a - 2, a + 2) or z in (hz, hz + 3):
                    m.put(x, y, z, M('spruce_planks') if not (z == hz and x == a and y < 3) else AIR)
    for x in range(a - 3, a + 4):
        for z in range(hz - 1, hz + 5):
            m.put(x, 4, z, M('deepslate_tiles'))
    for x in range(a - 2, a + 3):
        m.put(x, 5, hz + 1, M('deepslate_tiles'))
        m.put(x, 5, hz + 2, M('deepslate_tiles'))
    for x in (a - 2, a + 2):                          # stone lanterns along the approach
        z = max(1, hz - 3)
        m.put(x, 1, z, M('stone_bricks'))
        m.put(x, 2, z, M('lantern[hanging=false,waterlogged=false]'))
    for x, z in ((0, m.D - 1), (m.W - 1, m.D - 1), (0, 1), (m.W - 1, 1)):
        trunk(m, x, z, 'camphor' if (x + z) % 2 else 'dark_oak')


def trunk(m, x, z, kind, H=4):
    log, leaf, flat = species(kind)
    for y in range(1, H + 1):
        m.put(x, y, z, log)
    for dx, dy, dz in crown(flat):
        if (x + dx, H + dy, z + dz) not in m.v:
            m.put(x + dx, H + dy, z + dz, leaf)


def park(m, seed):
    """Grass, a looping path, summer trees, benches and a small lit pavilion."""
    m.fill(0, 0, M('grass_block[snowy=false]'))
    for x, z, u, c in m.ring(2):
        m.put(x, 0, z, M('smooth_stone'))
    for i in range(m.W):
        m.put(i, 0, m.D // 2, M('smooth_stone'))
    kinds = SUMMER_TREES
    for n, (x, z) in enumerate(((5, 5), (m.W - 6, 5), (5, m.D - 6), (m.W - 6, m.D - 6), (m.W // 2, 5), (m.W // 2, m.D - 6))):
        if 0 < x < m.W - 1 and 0 < z < m.D - 1:
            trunk(m, x, z, kinds[h(seed, n) % len(kinds)], 4 + h(seed, 'h', n) % 2)
    for x in range(4, m.W - 4, 4):
        m.put(x, 1, m.D // 2 + 1, M('spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]'))
    if m.W >= 15:
        a, b = m.W // 2 - 2, m.D // 2 + 3
        for x in (a, a + 4):
            for z in (b, b + 4):
                for y in (1, 2, 3):
                    m.put(x, y, z, M('dark_oak_log[axis=y]'))
        for x in range(a - 1, a + 6):
            for z in range(b - 1, b + 6):
                m.put(x, 4, z, M('dark_oak_slab[type=bottom,waterlogged=false]'))
        m.put(a + 2, 3, b + 2, M('lantern[hanging=true,waterlogged=false]'))


def school(m, seed):
    """School: a four-storey classroom wing along one side, a sand sports ground with a track line,
    camphor trees along the ground and a clock on the wing."""
    wing = 9
    wm = Model(m.W, wing, seed)
    H = 16
    wm.fill(0, 0, M('polished_andesite'))
    for y in range(1, H + 1):
        for x, z, u, c in wm.ring(0):
            wm.put(x, y, z, M('white_concrete') if c or y % 4 in (0, 1) or u % 5 == 0 else M('glass'))
        if y % 4 == 0:
            floor_ring(wm, y, 0, 2, M('smooth_stone'))
        elif y % 4 == 2:
            lit(wm, y, 0, 60)
    wm.fill(0, H, M('smooth_stone'))
    for x, z, u, c in wm.ring(0):
        wm.put(x, H + 1, z, SLAB('smooth_quartz'))
    a = m.W // 2
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            wm.put(a + dx, H - 2 + dy, wing - 1, M('white_concrete') if (dx, dy) != (0, 0) else M('black_concrete'))
    for (x, y, z), s in wm.v.items():
        m.put(x, y, z, s)
    for x in range(m.W):
        for z in range(wing, m.D):
            edge = min(x, m.W - 1 - x, z - wing, m.D - 1 - z)
            m.put(x, 0, z, M('smooth_sandstone') if edge else M('stone_bricks'))
    cx, cz, rx, rz = m.W // 2, (wing + m.D) // 2, m.W // 2 - 3, (m.D - wing) // 2 - 3
    for x in range(m.W):
        for z in range(wing, m.D):
            d = ((x - cx) / max(rx, 1)) ** 2 + ((z - cz) / max(rz, 1)) ** 2
            if 0.82 <= d <= 1.0:
                m.put(x, 0, z, M('white_concrete'))
    for x in range(2, m.W - 1, 5):
        trunk(m, x, m.D - 1, 'camphor')


# --- one lot -------------------------------------------------------------------------------------

def parcel_kind(seed, w, d, lot_seed):
    s, area = min(w, d), w * d
    if s >= 20:
        return pick(seed, (('office', 4), ('apartments', 3), ('mixed', 2), ('carpark', 1)))
    if s >= 12:
        return pick(seed, (('office', 2), ('apartments', 3), ('mixed', 3), ('carpark', 1), ('clinic', 1)))
    if s >= 9 and area >= 81:
        allow_shrine = h(lot_seed, 'shrine') % 4 == 0
        return pick(seed, (('apartments', 2), ('shop', 3), ('clinic', 1), ('pocket_park', 1), ('shrine', 2 if allow_shrine else 0)))
    return pick(seed, (('shop', 5), ('apartments', 1)))


def build(kind, w, d, seed):
    m = Model(w, d, seed)
    if kind == 'office':
        office(m, 4 * storeys(seed, 6, 15) + 4)
    elif kind == 'apartments':
        apartments(m, 4 + 3 * storeys(seed, 4, 14))
    elif kind == 'mixed':
        mixed(m, 4 * storeys(seed, 6, 12) + 4)
    elif kind == 'shop':
        lowrise(m, (10, 14, 18, 22)[h(seed, 'sh') % 4])
        if w <= 8:
            vsign(m, 0, 0, 3, (10, 14, 18, 22)[h(seed, 'sh') % 4] - 2, h(seed, 'vs'))
    elif kind == 'carpark':
        carpark(m, storeys(seed, 3, 6))
    elif kind == 'clinic':
        clinic(m, storeys(seed, 3, 5))
    elif kind == 'shrine':
        shrine(m)
    elif kind in ('pocket_park', 'park'):
        park(m, seed)
    elif kind == 'school':
        school(m, seed)
    return m


def plan_lot(cx, cz, w, special=None):
    """Cells for one lot: {(x, y, z): state} plus the parcel report."""
    x0, z0 = cx - HALF, cz - HALF
    seed = h('lot', cx, cz)
    cells, report = {}, []
    # sidewalk rings 1-3 (ring 0 is the city's kerb)
    for x in range(x0 + 1, x0 + 2 * HALF):
        for z in range(z0 + 1, z0 + 2 * HALF):
            e = min(x - x0, x0 + 2 * HALF - x, z - z0, z0 + 2 * HALF - z)
            if e <= 3:
                cells[x, Y, z] = M('polished_andesite') if e == 3 else M('smooth_stone')
    posts = city_posts(w, x0, z0, x0 + 2 * HALF, z0 + 2 * HALF)
    clear = lambda x, z: all(max(abs(x - px), abs(z - pz)) > 3 for px, pz in posts)
    spots = []
    for i, t in enumerate(range(6, 2 * HALF - 5, 7)):
        spots += [(x0 + t, z0 + 2, i), (x0 + t, z0 + 2 * HALF - 2, i + 1), (x0 + 2, z0 + t, i + 1), (x0 + 2 * HALF - 2, z0 + t, i)]
    for x, z, i in spots:
        if clear(x, z):
            (tree(cells, x, z, SUMMER_TREES[h(seed, 'tk') % len(SUMMER_TREES)]) if i % 2 == 0 else lamp(cells, x, z))
    ix0, iz0 = x0 + IN, z0 + IN
    if special:
        parcels = [((0, 0, N, N), special)]
    else:
        name, layout = pick(h(seed, 'layout'), list(zip(LAYOUTS, LAYOUT_WEIGHTS)))
        r = h(seed, 'rot') % 4
        parcels = [(rot(p, r), None) for p in layout]
    work = list(parcels)
    n = -1
    while work:
        (px, pz, pw, pd), kind = work.pop(0)
        n += 1
        ps = h(seed, 'parcel', n)
        kind = kind or parcel_kind(ps, pw, pd, seed)
        if kind == 'apartments' and min(pw, pd) >= 18:
            # flats are slabs about 11 deep: the rest of a deep parcel is a car park or a garden
            back = pick(h(ps, 'back'), (('carpark', 1), ('pocket_park', 2)))
            if pw >= pd:
                work[:0] = [((px, pz, pw, 11), 'apartments'), ((px, pz + 11, pw, pd - 11), back)]
            else:
                work[:0] = [((px, pz, 11, pd), 'apartments'), ((px + 11, pz, pw - 11, pd), back)]
            continue
        m = build(kind, pw, pd, ps)
        for (lx, ly, lz), s in m.v.items():
            cells[ix0 + px + lx, Y + ly, iz0 + pz + lz] = s
        report.append(dict(parcel=[ix0 + px, iz0 + pz, pw, pd], kind=kind, palette=m.pal['name'],
                           height=max((ly for (_, ly, _) in m.v), default=0)))
    return cells, report


def writable(cur, y, x, z, box):
    if cur is None:
        return False
    if is_open(cur) or 'leaves' in cur or 'short_grass' in cur or 'tall_grass' in cur or 'flower' in cur:
        return True
    if '_log' in cur and Y < y < Y + 12:
        return True                                    # the old lawn tree
    return y == Y and any(k in cur for k in ('grass_block', 'dirt', 'minecraft:stone'))


def main(sel, out, lots_file='E:/eva-map-buildings/plans/m5-lots.json'):
    w = World(REGION)
    gs = guards()
    lots = json.load(open(lots_file, encoding='utf8'))
    if sel == 'all':
        chosen = [l for l in lots if candidate(l)]
    else:
        want = {tuple(int(v) for v in p.split(',')) for p in sel.split(';')}
        chosen = [l for l in lots if (l['cx'], l['cz']) in want]
    specials = specials_for([l for l in lots if candidate(l)] + [l for l in chosen if not candidate(l)])
    rows, refused, report = [], Counter(), []
    for l in chosen:
        cx, cz = l['cx'], l['cz']
        cells, rep = plan_lot(cx, cz, w, specials.get((cx, cz)))
        box = (cx - HALF, cz - HALF, cx + HALF, cz + HALF)
        # the old lawn tree and plants inside the lot go when nothing new takes their place
        for x in range(cx - HALF + 1, cx + HALF):
            for z in range(cz - HALF + 1, cz + HALF):
                for y in range(Y + 1, Y + 12):
                    s = w.get(x, y, z) or ''
                    if ('leaves' in s or '_log' in s) and (x, y, z) not in cells:
                        cells[x, y, z] = AIR
        lot_rows = 0
        for (x, y, z), want in cells.items():
            cur = w.get(x, y, z)
            if cur is None or cur == want:
                continue
            if not writable(cur, y, x, z, box):
                refused['occupied'] += 1
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
            lot_rows += 1
        report.append(dict(lot=[cx, cz], rows=lot_rows, parcels=rep, special=specials.get((cx, cz))))
        print(cx, cz, lot_rows, [(p['kind'], p['palette'], p['height']) for p in rep])
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (Path(out) / 'report.json').write_text(json.dumps(report, indent=1), 'utf8')
    print('lots', len(chosen), 'rows', len(rows), 'refused', dict(refused))


def candidate(l):
    if (l['cx'], l['cz']) in RESERVED or l['kind'] not in ('light', 'empty'):
        return False
    g = l['ground']
    leaves = sum(v for k, v in l['built_kinds'].items() if 'leaves' in k)
    road = sum(v for k, v in g.items() if 'asphalt' in k) + g.get('air', 0)
    return g.get('grass_block', 0) >= 800 and leaves <= 120 and road < 60


SCHOOLS = {(-210, 180)}                # the west school, written in batch 1


def specials_for(lots):
    """A whole park on about one lot in eight; one school on each side of the city. Called with every
    candidate lot of the city, so batches planned one at a time agree on where the schools go."""
    out = {}
    for l in lots:
        if h('park', l['cx'], l['cz']) % 8 == 0:
            out[l['cx'], l['cz']] = 'park'
    for side in (-1, 1):
        fixed = [s for s in SCHOOLS if (s[0] - 30) * side > 0]
        if fixed:
            out.update({s: 'school' for s in fixed})
            continue
        cand = sorted((l for l in lots if (l['cx'] - 30) * side > 0 and (l['cx'], l['cz']) not in out), key=lambda l: h('school', l['cx'], l['cz']))
        if cand:
            out[cand[0]['cx'], cand[0]['cz']] = 'school'
    return out


if __name__ == '__main__':
    main(sys.argv[2], sys.argv[3], *sys.argv[4:]) if sys.argv[1] == 'lots' else None
