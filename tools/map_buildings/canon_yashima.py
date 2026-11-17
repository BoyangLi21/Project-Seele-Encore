"""Yashima summit position in the look of the original (TV episode 6), around the installed mission without moving it.

  python canon_yashima.py <out dir>      writes y1-deck, y2-site, y3-pylons, y4-forest under <out dir>

Every mission coordinate stays: the fixed cannon and its hatch, EVA-01's prone spot, EVA-00's shield spots, the grid
levers and pylons, the coolant and reload buttons, the supply racks, the landing pads and all EVA routes. New blocks go
only outside their clearance volumes (keepout below); the writer's launch guards are checked too, so flight and lift
space is refused. Cables are carpets, so EVAs and people walk over them.

  Y1 deck: airport markings to plain deck, steel plates under the prone EVA, hazard rim and guide posts at the hatch,
     cable bundles from the substation to the pylons and the cannon breech.
  Y2 site: substation and capacitor yard, cooling tanks, fuse store, command post, light towers, pilots' balcony.
  Y3 pylons: the power line coming in over the north-east slope.
  Y4 forest: grass on the bare dirt dome, spruce forest on the slopes, the summit ring kept clear.
"""
import json, math, os, sys
from collections import Counter
from pathlib import Path
from mca import REGION, WORLD, World
from float_fix import guards

M = lambda n: 'minecraft:' + n
AIR = M('air')
SOFT = ('air', 'short_grass', 'tall_grass', 'fern', 'flower', 'dandelion', 'poppy', 'snow[', 'vine', 'dead_bush', 'sweet_berry')
NATURAL = SOFT + ('leaves', '_log', 'dirt', 'grass_block', 'podzol', 'stone', 'gravel', 'andesite', 'tuff', 'moss', 'coarse')
DECK_Y = 174


def bar(**on):
    p = {k: ('true' if on.get(k) else 'false') for k in ('east', 'north', 'south', 'west')}
    return M(f"iron_bars[east={p['east']},north={p['north']},south={p['south']},waterlogged=false,west={p['west']}]")


POST = bar()
LEAF = M('spruce_leaves[distance=1,persistent=true,waterlogged=false]')
LOG = M('spruce_log[axis=y]')
LAMP = M('sea_lantern')
ROD = M('lightning_rod[facing=up,powered=false,waterlogged=false]')
ENDROD = M('end_rod[facing=up]')


class Site:
    def __init__(self):
        self.w = World(REGION)
        root = Path(WORLD)
        site = json.load(open(root / 'tv_encounter_sites_r45.json', encoding='utf8'))['sites']['ramiel']
        st = json.load(open(root / 'yashima_cannon_station_r52.json', encoding='utf8'))
        self.site, self.st, self.yc = site, st, site['yashima_controls']
        self.hero = site['hero']
        yaw = math.radians(site['yaw'])
        self.fx, self.fz = -math.sin(yaw), math.cos(yaw)
        self.gs = guards()
        self.keep = self.keepout()
        self.taken = set()                      # cells an earlier list of this run already changes

    def keepout(self):
        s, st, yc = self.site, self.st, self.yc
        k = []
        for r in list(s['eva_access_routes'].values()) + [s['cover_after_supply_route'], st['eva_access_route']]:
            for p in r:
                k.append((p[0] - 9.5, p[2] - 9.5, p[0] + 9.5, p[2] + 9.5, 'route'))
        k.append((-1279, -1429, -1223, -1365, 'hatch'))
        hx, hz = self.hero[0], self.hero[2]
        for t in range(0, 66, 2):
            x, z = hx - self.fx * t, hz - self.fz * t
            k.append((x - 11, z - 11, x + 11, z + 11, 'prone body'))
        for t in range(0, 900, 3):
            x, z = hx + self.fx * t, hz + self.fz * t
            k.append((x - 14, z - 14, x + 14, z + 14, 'firing corridor'))
        for p, r, n in ((s['cover'], 22, 'shield'), (s['shield_wait_port'], 20, 'shield wait'), (s['support_port'], 16, 'support port')):
            k.append((p[0] - r, p[2] - r, p[0] + r, p[2] + r, n))
        for l in s['landings'].values():
            k.append((l['point'][0] - 35, l['point'][2] - 35, l['point'][0] + 35, l['point'][2] + 35, 'pad'))
        k.append((-1405, -1555, -1335, -1485, 'pad west'))
        for r in yc['supply_racks']:
            (a, _, b), (c, _, e) = r['footprint']
            k.append((a - 3, b - 3, c + 3, e + 3, 'rack'))
        k.append((-1318, -1380, -1296, -1358, 'levers'))
        return k

    def blocked(self, x, z, ignore=()):
        for a, b, c, d, n in self.keep:
            if a <= x <= c and b <= z <= d and n not in ignore:
                return n
        return None

    def guarded(self, cells):
        try:
            for g in self.gs:
                g.assert_positions(list(cells))
        except ValueError:
            return True
        return False

    def ground(self, x, z, top=200):
        for y in range(top, 40, -1):
            s = self.w.get(x, y, z) or ''
            if s and not any(k in s for k in SOFT + ('leaves', '_log', 'carpet')):
                return y
        return 40


class Plan:
    def __init__(self, site, name):
        self.s, self.name, self.cells, self.rep = site, name, {}, Counter()

    def put(self, x, y, z, st, replace=SOFT):
        cur = self.s.w.get(x, y, z) or AIR
        if (x, y, z) in self.cells or (x, y, z) in self.s.taken:
            return
        if cur == st:
            return
        if not any(k in cur for k in replace):
            self.rep['occupied'] += 1
            return
        self.cells[x, y, z] = (cur, st)

    def piece(self, cells, kind, replace=SOFT, ignore=()):
        """All or nothing: a piece stands only if none of its columns is in a clearance volume or guarded."""
        cols = {(x, z) for x, y, z in cells}
        for x, z in cols:
            n = self.s.blocked(x, z, ignore)
            if n:
                self.rep[f'{kind} skipped ({n})'] += 1
                return False
        if any(c in self.s.taken for c in cells):
            self.rep[f'{kind} skipped (other list)'] += 1
            return False
        if self.s.guarded(cells.keys()):
            self.rep[f'{kind} skipped (launch guard)'] += 1
            return False
        for (x, y, z), st in cells.items():
            self.put(x, y, z, st, replace)
        self.rep[kind] += 1
        return True

    def rows(self):
        out = [[x, y, z, b, a] for (x, y, z), (b, a) in sorted(self.cells.items())]
        for st in {r[4] for r in out}:
            if '[' in st:
                props = st[st.index('[') + 1:-1].split(',')
                assert props == sorted(props), st
        return out


def y1_deck(s):
    p = Plan(s, 'y1-deck')
    pads = [(-1130, -1520), (-1250, -1520), (-1370, -1520)]
    near_pad = lambda x, z: any((x - a) ** 2 + (z - b) ** 2 <= 40 ** 2 for a, b in pads)
    # hazard rim around the hatch, flat in the deck
    x0, z0, x1, z1 = -1280, -1430, -1222, -1364
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if x in (x0, x1) or z in (z0, z1):
                if (s.w.get(x, DECK_Y, z) or '') in (M('gray_concrete'), M('white_concrete'), M('light_gray_concrete')):
                    p.put(x, DECK_Y, z, M('yellow_concrete') if (x + z) // 2 % 2 else M('black_concrete'), replace=('concrete',))
    hx, hz = s.hero[0], s.hero[2]
    for x in range(-1405, -1095):
        for z in range(-1560, -1344):
            st = s.w.get(x, DECK_Y, z) or ''
            if st not in (M('white_concrete'), M('light_gray_concrete'), M('gray_concrete')) or near_pad(x, z):
                continue
            # steel plates where EVA-01 lies: a band behind the firing spot along its body
            along = (x - hx) * -s.fx + (z - hz) * -s.fz
            across = abs((x - hx) * s.fz - (z - hz) * s.fx)
            if -4 <= along <= 64 and across <= 10:
                want = M('polished_deepslate') if (int(along) // 4 + int(across) // 4) % 2 else M('deepslate_tiles')
            elif st != M('gray_concrete'):
                want = M('gray_concrete')
            else:
                continue
            if not s.guarded([(x, DECK_Y, z)]):
                p.put(x, DECK_Y, z, want, replace=('concrete',))
                p.rep['deck cells'] += 1
    for x, z in ((x0 - 2, z0 - 2), (x1 + 2, z0 - 2), (x0 - 2, z1 + 2), (x1 + 2, z1 + 2)):     # guide posts at the corners
        g = s.ground(x, z)
        p.piece({(x, y, z): M('iron_block') if y % 4 == 0 else POST for y in range(g + 1, DECK_Y + 13)}, 'hatch guide post')
    # cable bundles: from the substation south edge (x -1210..-1170, z -1556) across the plateau onto the deck, round the
    # far end of EVA-01's prone body, down the west side to the pylon base and to the cannon breech. Black carpet on full
    # blocks only. Carpet tops are 1/16 above the deck, and the fixed stations require the floor top within +0.05 of the
    # hull, so no carpet where an EVA docks or stands: the prone body, the hatch, the shield stations and the pads.
    DOCKS = ('prone body', 'hatch', 'shield', 'shield wait')
    touchdown = [(l['point'][0], l['point'][2]) for l in s.site['landings'].values()] + [(-1370, -1520)]
    def lay(path, kind):
        n = 0
        for a, b in zip(path, path[1:]):
            steps = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
            for i in range(steps + 1):
                x = round(a[0] + (b[0] - a[0]) * i / max(1, steps)); z = round(a[1] + (b[1] - a[1]) * i / max(1, steps))
                if any(n in DOCKS for a0, b0, c0, d0, n in s.keep if a0 <= x <= c0 and b0 <= z <= d0)                         or any(abs(x - tx) <= 14 and abs(z - tz) <= 14 for tx, tz in touchdown):
                    p.rep[kind + ' cell left out (dock or station)'] += 1
                    continue
                g = s.ground(x, z)
                under = s.w.get(x, g, z) or ''
                if any(k in under for k in ('slab', 'stairs', 'carpet', 'wall', 'bars', 'fence', 'lever', 'button', 'barrier', 'pylon', 'door', 'trapdoor')):
                    continue
                if (s.w.get(x, g + 1, z) or AIR) != AIR or s.guarded([(x, g + 1, z)]):
                    continue
                p.put(x, g + 1, z, M('black_carpet'), replace=('air',)); n += 1
        p.rep[kind] += n
    for i in range(10):                          # 6 lines to the grid pylons, 4 on to the cannon breech
        o = i * 2
        # west of the prone body's far end (x < -1318), then east of the support port (box x >= -1325 from z -1416)
        zr = -1506 + min(i, 7)                   # rows between pad 1 touchdown (z <= -1506.7) and the body end (z >= -1498.8)
        path = [(-1200 + o, -1557), (-1200 + o, zr), (-1328 + i, zr), (-1328 + i, -1426 + i), (-1318 + i, -1426 + i)]
        if i < 6:
            lay(path + [(-1318 + i, -1384 + i), (-1310, -1384 + i)], 'cable to pylons')
        else:
            lay(path + [(-1318 + i, -1420 + (i - 6) * 2), (-1281, -1420 + (i - 6) * 2)], 'cable to breech')
    return p


def terrace(p, box, y, top=M('gravel')):
    """Level a building plot: fill natural ground up to y, clear natural blocks above it."""
    x0, z0, x1, z1 = box
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if p.s.blocked(x, z):
                continue
            g = p.s.ground(x, z, top=y + 30)
            for yy in range(min(g, y) - 6, y):
                if yy > g:
                    p.put(x, yy, z, M('dirt'), replace=SOFT + ('leaves', '_log'))
            p.put(x, y, z, top, replace=NATURAL)
            for yy in range(y + 1, y + 30):
                st = p.s.w.get(x, yy, z) or AIR
                if any(k in st for k in ('leaves', '_log', 'grass', 'fern', 'flower', 'dirt', 'stone', 'gravel', 'moss', 'snow')):
                    p.put(x, yy, z, AIR, replace=NATURAL)


def box_cells(x0, y0, z0, x1, y1, z1, st):
    return {(x, y, z): st for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)}


def y2_site(s):
    p = Plan(s, 'y2-site')
    # substation and capacitor yard on the north plateau between pads 1 and 0
    SX0, SZ0, SX1, SZ1, SY = -1212, -1580, -1168, -1557, 173
    terrace(p, (SX0, SZ0, SX1, SZ1), SY)
    for row, z in enumerate(range(SZ0 + 3, SZ1 - 2, 6)):
        for x in range(SX0 + 3, SX1 - 3, 6):
            c = box_cells(x, SY + 1, z, x + 2, SY + 3, z + 1, M('smooth_stone'))
            c.update(box_cells(x, SY + 1, z + 2, x + 2, SY + 3, z + 2, M('gray_concrete')))       # cooling fins side
            c[x, SY + 4, z] = ENDROD; c[x + 2, SY + 4, z] = ENDROD; c[x + 1, SY + 4, z + 1] = ROD
            p.piece(c, 'transformer')
    for x in range(SX0 + 3, SX1 - 2, 3):                                                         # capacitor cabinets
        p.piece(box_cells(x, SY + 1, SZ1 - 2, x + 1, SY + 3, SZ1 - 2, M('light_gray_concrete')) | {(x, SY + 4, SZ1 - 2): M('gray_concrete')}, 'capacitor cabinet')
    fence = {}
    for x in range(SX0, SX1 + 1):
        for z in (SZ0, SZ1):
            fence[x, SY + 1, z] = bar(east=x < SX1, west=x > SX0)
    for z in range(SZ0 + 1, SZ1):
        for x in (SX0, SX1):
            fence[x, SY + 1, z] = bar(north=True, south=True)
    gate = {(SX0 + 20 + i, SY + 1, SZ1) for i in range(8)}                                       # cables leave through here
    p.piece({k: v for k, v in fence.items() if k not in gate}, 'yard fence')
    # cooling plant west of the levers, tanks standing on the ground up to above the deck
    for cx, cz in ((-1340, -1376), (-1332, -1366), (-1340, -1356)):
        g = s.ground(cx, cz)
        c = {}
        for x in range(cx - 3, cx + 4):
            for z in range(cz - 3, cz + 4):
                d = (x - cx) ** 2 + (z - cz) ** 2
                if d <= 10:
                    for y in range(g + 1, DECK_Y + 9):
                        c[x, y, z] = M('white_concrete') if d > 4 or y == DECK_Y + 8 else M('white_concrete')
                    if d > 6:
                        c[x, DECK_Y + 9, z] = M('iron_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]')
        for y in range(DECK_Y + 2, DECK_Y + 4):
            c[cx + 4, y, cz] = M('gray_concrete')                                                   # pipe stub toward the levers
        p.piece(c, 'cooling tank')
    # fuse and reload store: two containers beside the reload button
    for i, (x0, z0) in enumerate(((-1294, -1362), (-1294, -1356))):
        g = s.ground(x0, z0)
        c = box_cells(x0, g + 1, z0, x0 + 9, g + 4, z0 + 3, M('cyan_terracotta') if i else M('light_gray_terracotta'))
        c.update(box_cells(x0, g + 2, z0, x0, g + 3, z0 + 3, M('iron_block')))
        p.piece(c, 'fuse container')
    # command post on the south bench (y 131): two command trucks, two tents, a mast with a dish, a generator
    CY = s.ground(-1275, -1331)
    terrace(p, (-1302, -1336, -1250, -1326), CY)
    for x0 in (-1300, -1285):
        c = box_cells(x0, CY + 2, -1335, x0 + 10, CY + 5, -1332, M('white_concrete'))
        c.update(box_cells(x0 + 11, CY + 2, -1335, x0 + 13, CY + 4, -1332, M('gray_concrete')))     # cab
        for wx in (x0 + 1, x0 + 4, x0 + 9, x0 + 12):
            c[wx, CY + 1, -1335] = M('black_concrete'); c[wx, CY + 1, -1332] = M('black_concrete')
        c[x0 + 2, CY + 6, -1334] = ROD; c[x0 + 2, CY + 7, -1334] = ROD; c[x0 + 8, CY + 6, -1333] = ENDROD
        c[x0 + 5, CY + 4, -1331] = LAMP
        p.piece(c, 'command truck')
    for x0 in (-1268, -1259):
        c = {}
        for x in range(x0, x0 + 7):
            for z in range(-1335, -1328):
                h = 3 - abs(z - (-1332)) // 2
                for y in range(CY + 1, CY + 1 + h):
                    if z in (-1335, -1329) or x in (x0, x0 + 6) or y == CY + h:
                        c[x, y, z] = M('white_wool')
                c[x, CY + 1 + h, z] = M('white_wool') if z == -1332 else c.get((x, CY + h, z), M('white_wool'))
        for x in range(x0 + 2, x0 + 5):
            c.pop((x, CY + 1, -1329), None); c.pop((x, CY + 2, -1329), None)
        c[x0 + 3, CY + 1, -1332] = M('oak_planks'); c[x0 + 3, CY + 2, -1332] = M('black_carpet')      # table with screens
        c[x0 + 1, CY + 2, -1332] = LAMP
        p.piece(c, 'tent')
    c = {(-1252, y, -1330): POST for y in range(CY + 1, CY + 16)}
    c.update({(-1252, CY + 16, -1330): M('iron_block'), (-1251, CY + 16, -1330): M('daylight_detector[inverted=false,power=0]'), (-1252, CY + 17, -1330): ROD})
    p.piece(c, 'comms mast')
    p.piece(box_cells(-1300, CY + 1, -1328, -1296, CY + 2, -1327, M('gray_concrete')) | {(-1298, CY + 3, -1327): M('iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]')}, 'generator')
    # light towers: lattice of iron bars, a head of sea lanterns facing the deck
    for x, z in ((-1420, -1500), (-1420, -1418), (-1356, -1336), (-1236, -1330), (-1142, -1342), (-1104, -1410), (-1100, -1468)):
        g = s.ground(x, z)
        top = max(g + 20, DECK_Y + 16)
        c = {}
        for y in range(g + 1, top + 1):
            for dx, dz in ((0, 0), (1, 0), (0, 1), (1, 1)):
                c[x + dx, y, z + dz] = M('iron_block') if (y - g) % 6 == 0 else POST
        for dx in range(-1, 3):
            for dz in range(-1, 3):
                c[x + dx, top + 1, z + dz] = LAMP if (dx in (0, 1) and dz in (0, 1)) else M('gray_concrete')
        p.piece(c, 'light tower')
    # pilots' balcony off the east deck edge, facing the city
    c = {}
    for x in range(-1140, -1128):
        for z in range(-1452, -1435):
            c[x, DECK_Y, z] = M('polished_deepslate')
            if x == -1129 or z in (-1452, -1436):
                c[x, DECK_Y + 1, z] = bar(north=x == -1129 and z > -1452, south=x == -1129 and z < -1436,
                                          east=z in (-1452, -1436) and x < -1129, west=z in (-1452, -1436) and x > -1140)
    for x, z in ((-1131, -1450), (-1131, -1438)):
        g = s.ground(x, z)
        for y in range(g + 1, DECK_Y):
            c[x, y, z] = M('iron_block') if y % 5 == 0 else POST
    p.piece(c, 'pilots balcony', replace=SOFT + ('leaves', '_log'))
    return p


def y3_pylons(s):
    p = Plan(s, 'y3-pylons')
    line = [(-1190, -1585), (-1090, -1660), (-985, -1735), (-880, -1810)]
    tops = []
    for tx, tz in line[1:]:
        g0 = min(s.ground(tx + dx, tz + dz) for dx in (-3, 3) for dz in (-3, 3))
        if (s.w.get(tx, g0, tz) or '').endswith('water'):
            p.rep['pylon in water skipped'] += 1
            continue
        top = g0 + 34
        c = {}
        for y in range(g0 + 1, top + 1):
            t = (y - g0) / (top - g0); half = max(1, round(3 - 2 * t))
            for lx, lz in ((tx - half, tz - half), (tx + half, tz - half), (tx - half, tz + half), (tx + half, tz + half)):
                if y > s.ground(lx, lz):
                    c[lx, y, lz] = POST
            if (y - g0) % 5 == 0:
                for x in range(tx - half, tx + half + 1):
                    for z in (tz - half, tz + half):
                        c[x, y, z] = POST
        for z in range(tz - 6, tz + 7):
            c[tx, top - 4, z] = M('iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]')
        for z in (tz - 6, tz + 6):
            c[tx, top - 5, z] = M('chain[axis=y,waterlogged=false]')
        c[tx, top + 1, tz] = ROD
        if p.piece(c, 'pylon'):
            tops.append((tx, top - 6, tz))
    # conductors: straight chains between neighbouring pylons at the arm ends (they sag in the original; ours are taut)
    for (ax, ay, az), (bx, by, bz) in zip(tops, tops[1:]):
        for dz in (-6, 6):
            n = max(abs(bx - ax), abs(bz - az))
            c = {}
            for i in range(1, n):
                x = round(ax + (bx - ax) * i / n); z = round(az + (bz - az) * i / n) + dz; y = round(ay + (by - ay) * i / n)
                c[x, y, z] = M('chain[axis=x,waterlogged=false]') if abs(bx - ax) >= abs(bz - az) else M('chain[axis=z,waterlogged=false]')
            p.piece(c, 'conductor')
    return p


def y4_forest(s):
    p = Plan(s, 'y4-forest')
    X0, Z0, X1, Z1 = -1530, -1740, -970, -1290
    hx, hz = s.hero[0], s.hero[2]
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            g = s.ground(x, z)
            top = s.w.get(x, g, z) or ''
            if top != M('dirt'):
                continue
            if (s.w.get(x, g + 1, z) or AIR) != AIR or s.guarded([(x, g, z)]):
                continue
            p.put(x, g, z, M('grass_block[snowy=false]'), replace=('dirt',))
            p.rep['dirt to grass'] += 1
    # spruce: deterministic scatter, one tree per ~9x9 cell, only on slopes below the summit ring
    for cx in range(X0, X1, 9):
        for cz in range(Z0, Z1, 9):
            h = (cx * 73856093 ^ cz * 19349663) & 0xffff
            x, z = cx + h % 7, cz + (h >> 3) % 7
            if p.s.blocked(x, z) or abs(x - hx) < 1 and abs(z - hz) < 1:
                continue
            g = s.ground(x, z)
            top = s.w.get(x, g, z) or ''
            if g >= 168 or not any(k in top for k in ('dirt', 'grass_block', 'podzol')):
                continue                                   # summit ring (deck level) stays clear
            if any((s.w.get(x + dx, g - 1, z + dz) or AIR) == AIR for dx, dz in ((3, 0), (-3, 0), (0, 3), (0, -3))):
                continue                                   # terrace edges
            H = 10 + h % 7
            c = {(x, y, z): LOG for y in range(g + 1, g + H)}
            for y in range(g + 4, g + H + 2):
                r = max(0, round((g + H + 1 - y) / 3))
                for dx in range(-r, r + 1):
                    for dz in range(-r, r + 1):
                        if abs(dx) + abs(dz) <= r + (y % 2) and (dx, dz) != (0, 0) or (dx, dz) == (0, 0) and y >= g + H:
                            c[x + dx, y, z + dz] = LEAF
            p.piece(c, 'spruce')
    return p


def main(out):
    s = Site()
    for fn in (y1_deck, y2_site, y3_pylons, y4_forest):
        p = fn(s)
        rows = p.rows()
        d = Path(out) / p.name
        d.mkdir(parents=True, exist_ok=True)
        (d / 'rows.json').write_text(json.dumps(rows), 'utf8')
        (d / 'report.json').write_text(json.dumps(dict(rows=len(rows), parts=p.rep), indent=1), 'utf8')
        print(p.name, len(rows), dict(p.rep))
        s.taken |= set(p.cells)


if __name__ == '__main__':
    main(sys.argv[1])
