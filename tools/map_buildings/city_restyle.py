"""Restyle Tokyo-3 lift towers in place, and build static infill blocks on empty parcels.

city_restyle.py towers <ids,...> <out dir>       rebuild these towers inside their own boxes
city_restyle.py infill <x0,z0,x1,z1> <out dir>   static mid- and low-rise block on a parcel

A tower's box is its footprint x its current base (RetractedBaseY while the city is lowered,
the street level + 1 while raised) up to base + Height + 3, read from the city topology in
BUILDINGS_WORLD. Nothing is planned outside the box, so the tower's travel and its clearance
from the dome and the static city stay as they are. Kept exactly: project blocks (personnel
doors, gutters, pipes), iron blocks, redstone lamps and any block entity other than beds and
barrels; the three cells inside a personnel door stay open.

The designs are original and realistic for a near-future Japanese city, read at EVA scale:
curtain-wall offices with mullions, floor bands, setbacks, planted terraces and rooftop plant;
apartment slabs with balconies and glass rails; shop podiums with an overhanging awning band,
sign bands and vertical signboards; warm lit windows on staggered floors. Interiors keep only
perimeter floor rings and a core so the block count stays near today's. Only full blocks, slabs
and blocks whose shape does not depend on neighbours are used.
"""
import json, sys, zlib
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World, WORLD

AIR = 'minecraft:air'
M = lambda n: 'minecraft:' + n
SLAB = lambda n: M(n + '_slab[type=bottom,waterlogged=false]')
LIGHTS = (M('ochre_froglight[axis=y]'), M('pearlescent_froglight[axis=y]'), M('verdant_froglight[axis=y]'))
KEEP_NS = ('projectseele:',)


def h(*v):
    return zlib.crc32(repr(v).encode()) & 0xffffffff


def topology():
    import nbtlib
    for f in Path(WORLD, 'dimensions/projectseele/geofront/data').glob('projectseele_city_rigid_topology_r45_*.dat'):
        d = nbtlib.load(str(f))['data']

        def sx(v, b):
            return v - (1 << b) if v >= 1 << (b - 1) else v

        def unpack(v):
            v = int(v)
            return sx((v >> 38) & ((1 << 26) - 1), 26), sx(v & 0xFFF, 12), sx((v >> 12) & ((1 << 26) - 1), 26)
        out = []
        for i, t in enumerate(d['Towers']):
            f2 = t['Footprint']
            out.append(dict(id=i, kind=str(t['Kind']), centre=unpack(t['Centre']), H=int(t['Height']),
                            fp=[int(f2['MinX']), int(f2['MaxX']), int(f2['MinZ']), int(f2['MaxZ'])], ret=int(t['RetractedBaseY'])))
        return out
    raise SystemExit('no city topology in ' + WORLD)


class Model:
    """Local voxel model of one building: (lx, ly, lz) -> state, W x D footprint."""

    def __init__(self, W, D, seed):
        self.W, self.D, self.seed, self.v = W, D, seed, {}

    def put(self, x, y, z, s):
        if 0 <= x < self.W and 0 <= z < self.D and y >= 0:
            self.v[x, y, z] = s

    def ring(self, k):
        """Perimeter cells at inset k with the position u along their face (0 at corners)."""
        x0, z0, x1, z1 = k, k, self.W - 1 - k, self.D - 1 - k
        if x1 < x0 or z1 < z0:
            return
        for x in range(x0, x1 + 1):
            for z in (z0, z1):
                yield x, z, min(x - x0, x1 - x), (x in (x0, x1))
        for z in range(z0 + 1, z1):
            for x in (x0, x1):
                yield x, z, min(z - z0, z1 - z), False

    def fill(self, k, y, s):
        for x in range(k, self.W - k):
            for z in range(k, self.D - k):
                self.put(x, y, z, s)


def lobby(m, top, k, glass, frame, floor):
    m.fill(0, 0, floor)
    for y in range(1, top + 1):
        for x, z, u, corner in m.ring(k):
            m.put(x, y, z, frame if corner or u % 4 == 0 or y == top else glass)


def core(m, y0, y1, mat):
    cx0, cz0 = m.W // 2 - 2, m.D // 2 - 2
    for y in range(y0, y1 + 1):
        for x in range(cx0, cx0 + 5):
            for z in range(cz0, cz0 + 5):
                if x in (cx0, cx0 + 4) or z in (cz0, cz0 + 4):
                    m.put(x, y, z, mat)


def floor_ring(m, y, k, depth, mat):
    for d in range(depth):
        for x, z, u, c in m.ring(k + 1 + d):
            m.put(x, y, z, mat)


def lit(m, y, k, rate):
    """Warm lights just inside the glass on some floors, some bays."""
    if h(m.seed, 'floor', y) % 100 >= rate:
        return
    tone = LIGHTS[h(m.seed, 'tone', y // 12) % len(LIGHTS)] if h(m.seed, 'cool') % 4 == 0 else LIGHTS[0]
    for x, z, u, c in m.ring(k + 1):
        if h(m.seed, x, y, z) % 3 == 0:
            m.put(x, y, z, tone)


def roof_plant(m, y, k, w):
    """Parapet and a rooftop plant room with louvred walls; uses levels y..y+2 (y+2 is the box top)."""
    for x, z, u, c in m.ring(k):
        m.put(x, y, z, SLAB('smooth_quartz'))
    a = m.W // 2 - w // 2
    b = m.D // 2 - w // 2
    for yy in (y, y + 1):
        for x in range(a, a + w):
            for z in range(b, b + w):
                if x in (a, a + w - 1) or z in (b, b + w - 1):
                    m.put(x, yy, z, M('gray_concrete') if (x + z + yy) % 2 else M('light_gray_concrete'))
    for x in range(a, a + w):
        for z in range(b, b + w):
            m.put(x, y + 2, z, SLAB('smooth_stone'))


def terrace(m, y, k_in, k_out):
    """A setback terrace: paving, planters at the corners, glass railing slab on the edge."""
    for kk in range(k_out, k_in):
        for x, z, u, c in m.ring(kk):
            m.put(x, y, z, M('smooth_stone'))
            if kk == k_out:
                m.put(x, y + 1, z, SLAB('smooth_quartz'))
            elif c or u <= 1:
                m.put(x, y + 1, z, M('azalea_leaves[distance=1,persistent=true,waterlogged=false]'))


def office(m, H, landmark=False):
    W = m.W
    glass = M('light_blue_stained_glass') if h(m.seed, 'g') % 3 else M('gray_stained_glass')
    mull = (M('smooth_quartz'), M('light_gray_concrete'), M('white_concrete'))[h(m.seed, 'm') % 3]
    band = M('gray_concrete') if h(m.seed, 'b') % 2 else M('light_gray_concrete')
    lobby(m, 7, 1, M('glass'), M('black_concrete'), M('polished_andesite'))
    for x, z, u, c in m.ring(0):
        m.put(x, 8, z, M('polished_andesite'))          # canopy over the recessed lobby
    s1, s2 = int(H * 0.5), int(H * 0.78)
    ks = [(9, s1, 1), (s1, s2, 2), (s2, H, 3)] if W >= 15 else [(9, H, 1)]
    for a, b, k in ks:
        if a > 9:
            terrace(m, a, k, k - 1)
        for y in range(a + (1 if a > 9 else 0), b + 1):
            for x, z, u, c in m.ring(k):
                if c or u % 3 == 0:
                    m.put(x, y, z, mull)
                elif y % 4 == 0:
                    m.put(x, y, z, band)
                else:
                    m.put(x, y, z, glass)
            if landmark and k > 1:
                for x, z, u, c in m.ring(k - 1):
                    if not c and u % 3 == 0 and (y // 4) % 2 == 0:
                        m.put(x, y, z, mull)                  # vertical fins standing proud
            if y % 4 == 0:
                floor_ring(m, y, k, 2, M('smooth_stone'))
            elif y % 4 == 2:
                lit(m, y, k, 45)
        core(m, a, b, M('light_gray_concrete'))
    k = ks[-1][2]
    m.fill(k, H, M('smooth_stone'))
    if landmark:
        for y in range(H + 1, H + 4):
            for x, z, u, c in m.ring(k + 1 + (y - H)):
                m.put(x, y, z, mull if c or u % 2 == 0 else glass)
        m.put(W // 2, H + 3, m.D // 2, M('lightning_rod[facing=up,powered=false,waterlogged=false]'))
    else:
        roof_plant(m, H + 1, k, 7)


def apartments(m, H):
    wall = (M('white_concrete'), M('light_gray_concrete'), M('white_terracotta'))[h(m.seed, 'w') % 3]
    trim = M('gray_concrete') if wall != M('light_gray_concrete') else M('white_concrete')
    lobby(m, 4, 1, M('glass'), M('dark_oak_planks'), M('polished_andesite'))
    long_x = h(m.seed, 'axis') % 2 == 0
    for y in range(5, H + 1):
        fl = (y - 5) % 3 == 0
        for x, z, u, c in m.ring(1):
            facing_balcony = (z in (1, m.D - 2)) if long_x else (x in (1, m.W - 2))
            if c:
                m.put(x, y, z, trim)
            elif fl:
                m.put(x, y, z, trim)
            elif u % 4 in (1, 2) and (facing_balcony or u % 8 in (1, 2)):
                m.put(x, y, z, M('glass'))
            else:
                m.put(x, y, z, wall)
        for x, z, u, c in m.ring(0):
            on_balcony_face = (z in (0, m.D - 1)) if long_x else (x in (0, m.W - 1))
            if not on_balcony_face or c:
                continue
            if fl:
                m.put(x, y, z, SLAB('smooth_stone'))
            elif (y - 5) % 3 == 1:
                m.put(x, y, z, wall if u % 5 == 0 else M('white_stained_glass'))
                if u % 7 == 3 and h(m.seed, x, y, z) % 3 == 0:
                    m.put(x, y + 1, z, M('light_gray_concrete'))    # an air-conditioner unit
        if fl:
            floor_ring(m, y, 1, 2, M('smooth_stone'))
        elif (y - 5) % 3 == 2:
            lit(m, y, 1, 55)
    core(m, 1, H, M('light_gray_concrete'))
    m.fill(1, H, M('smooth_stone'))
    roof_plant(m, H + 1, 1, 5)


SIGNS = ('red_concrete', 'yellow_concrete', 'blue_concrete', 'orange_concrete', 'white_concrete', 'lime_concrete', 'magenta_concrete')


def mixed(m, H):
    """Shop podium with an awning band and sign band, then a tower above (offices or flats)."""
    m.fill(0, 0, M('polished_andesite'))
    for y in range(1, 6):
        for x, z, u, c in m.ring(1):
            m.put(x, y, z, M('black_concrete') if c or u % 5 == 0 else M('glass'))
        if y == 3:
            floor_ring(m, y, 1, 1, M('smooth_stone'))
    for x, z, u, c in m.ring(0):
        shop = u // 5
        m.put(x, 6, z, M('white_wool') if (u + shop) % 2 else M(('red_wool', 'green_wool', 'blue_wool', 'orange_wool')[h(m.seed, shop) % 4]))
    for y in (7, 8):
        for x, z, u, c in m.ring(0):
            m.put(x, y, z, M(SIGNS[h(m.seed, x // 5, z // 5) % len(SIGNS)]) if not c else M('black_concrete'))
    for x, z, u, c in m.ring(1):
        m.put(x, 7, z, M('light_gray_concrete'))
    lit(m, 4, 1, 100)
    sub = Model(m.W - 2, m.D - 2, m.seed ^ 0x5bd1)
    if h(m.seed, 'upper') % 2:
        office(sub, H)
    else:
        apartments(sub, H)
    for (x, y, z), s in sub.v.items():
        if y >= 9:
            m.put(x + 1, y, z + 1, s)
    # vertical signboards on two corners above the podium
    for n, (x, z) in enumerate(((0, 0), (m.W - 1, m.D - 1))):
        col = M(SIGNS[h(m.seed, 'v', n) % len(SIGNS)])
        top = min(H - 2, 9 + 12)
        for y in range(9, top):
            m.put(x, y, z, M('sea_lantern') if y in (9, top - 1) else col)


def lowrise(m, H):
    if H >= 24:
        mixed(m, H)
        return
    m.fill(0, 0, M('polished_andesite'))
    for y in range(1, H + 1):
        for x, z, u, c in m.ring(1):
            m.put(x, y, z, M('black_concrete') if c or u % 5 == 0 or y in (6, 7) else M('glass'))
        if y % 4 == 0:
            floor_ring(m, y, 1, 2, M('smooth_stone'))
        elif y % 4 == 2:
            lit(m, y, 1, 70)
    for x, z, u, c in m.ring(0):
        m.put(x, 6, z, M(SIGNS[h(m.seed, x // 6, z // 6) % len(SIGNS)]))
    m.fill(1, H, M('smooth_stone'))
    roof_plant(m, H + 1, 1, 5)


def design(t):
    W, D = t['fp'][1] - t['fp'][0] + 1, t['fp'][3] - t['fp'][2] + 1
    m = Model(W, D, h('tower', t['id']))
    H = t['H']
    if H >= 90:
        office(m, H, landmark=True)
        kind = 'landmark'
    elif H >= 56:
        office(m, H)
        kind = 'office'
    elif H >= 34:
        kind = 'apartments' if h(m.seed, 'k') % 2 else 'mixed'
        (apartments if kind == 'apartments' else mixed)(m, H)
    else:
        lowrise(m, H)
        kind = 'lowrise'
    return m, kind


def keep(w, s, pos):
    if s is None:
        return False
    if s.startswith(KEEP_NS) or 'iron_block' in s or 'redstone_lamp' in s:
        return True
    be = w.block_entity(*pos)
    return bool(be) and be not in ('minecraft:bed', 'minecraft:barrel')


def tower_rows(w, t, base):
    cx, cy, cz = t['centre']
    x0, z0 = cx + t['fp'][0], cz + t['fp'][2]
    m, kind = design(t)
    rows, before, after = [], 0, 0
    doors = []
    for lx in range(m.W):
        for lz in range(m.D):
            for ly in range(0, t['H'] + 4):
                p = (x0 + lx, base + ly, z0 + lz)
                s = w.get(*p)
                if s and 'city_personnel_door' in s:
                    doors.append((lx, ly, lz))
    clear = set()
    for lx, ly, lz in doors:
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                clear.add((lx + dx, ly, lz + dz))
                clear.add((lx + dx, ly + 1, lz + dz))
    for lx in range(m.W):
        for lz in range(m.D):
            for ly in range(0, t['H'] + 4):
                p = (x0 + lx, base + ly, z0 + lz)
                s = w.get(*p) or AIR
                if s != AIR and 'air' not in s:
                    before += 1
                if keep(w, s, p):
                    if s != AIR:
                        after += 1
                    continue
                want = AIR if (lx, ly, lz) in clear else m.v.get((lx, ly, lz), AIR)
                if want != AIR:
                    after += 1
                if want != s:
                    rows.append([*p, s, want])
    return rows, dict(id=t['id'], kind=kind, H=t['H'], base=base, blocks_before=before, blocks_after=after, doors=len(doors))


def main_towers(ids, out):
    w = World(REGION)
    T = {t['id']: t for t in topology()}
    allrows, report = [], []
    for i in ids:
        t = T[i]
        cx, cy, cz = t['centre']
        x0, z0 = cx + t['fp'][0], cz + t['fp'][2]
        raised = any('air' not in (w.get(x0 + dx, cy + 1 + dy, z0 + dz) or 'minecraft:air')
                     for dx in (0, 4, 8) for dz in (0, 4, 8) for dy in (0, 3, 6))
        lowered = not raised
        base = t['ret'] if lowered else cy + 1
        rows, rep = tower_rows(w, t, base)
        rep['state'] = 'lowered' if lowered else 'raised'
        allrows += rows
        report.append(rep)
        print(rep)
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(allrows), 'utf8')
    (Path(out) / 'report.json').write_text(json.dumps(report, indent=1), 'utf8')
    print('rows', len(allrows), 'blocks', sum(r['blocks_before'] for r in report), '->', sum(r['blocks_after'] for r in report))


if __name__ == '__main__':
    if sys.argv[1] == 'towers':
        main_towers([int(v) for v in sys.argv[2].split(',')], sys.argv[3])
    elif sys.argv[1] == 'infill':
        from city_infill import main as infill
        infill([int(v) for v in sys.argv[2].split(',')], sys.argv[3])
