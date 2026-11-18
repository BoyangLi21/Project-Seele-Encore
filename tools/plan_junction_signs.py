"""Plan Japanese road direction signs (案内標識) at the major road junctions of the surface map (batch S-3).

Reads a stopped world only. Finds the drivable surface (TrafficCraft asphalt, plus the old paving left in the Kirisato
boxes), thins it to a centre-line graph, picks the junctions that place-to-place routes branch at, and gives each
approach one sign on the LEFT shoulder a few blocks before the junction, facing oncoming traffic: a two-high iron-bar
post with a warped (blue-green) standing sign, white glowing text, line 1 the junction name when one fits, then up to
three lines "arrow + Japanese place", the place being the next notable town or station that way along the roads.

    plan_junction_signs.py --world E:/eva-terrain/world14 --work E:/eva-signs/s3work --out E:/eva-signs \\
        --notes <side-session-notes folder>

Writes s3-rows.json ([x, y, z, before, after]), s3-signs.json ({pos, front, back, color, glow}) and s3-junctions.json
into --out; install with write_deep_cells.py --rows ... --signs ... . The road scan is cached in --work (roads.npy);
pass --rescan after the world changed. About 4 minutes.

Posts stay off the carriageway, outside rail hulls (each MTR rail's ends and tangent meeting point, 3.5 blocks
margin), off lift/city/launch protection, and out of the columns of other sessions' row lists that are still waiting
to be written (a list counts as written when the world already shows its after states). Dead ends within 45 blocks
of another piece of road are joined by virtual links, used for routing only.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')      # sixteen scan workers each start a BLAS pool otherwise
import argparse
import glob
import heapq
import io
import json
import math
import time
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import nbtlib
import numpy as np
from scipy import ndimage as ndi

from sign_rules import SIGN_WIDTH, text_width

REGION = 'dimensions/projectseele/geofront/region'
X0, Z0, X1, Z1 = -2960, -1410, 4480, 2530
# Old paving counts as road only here (Kirisato and its link road); elsewhere it is runways, plazas and floors.
OLD_BOXES = [(-2950, -2250, -1400, -900), (-2400, -2355, -1100, 200), (-2400, -1880, 155, 205), (-1965, -1880, 155, 320)]
OLD = {'minecraft:black_concrete', 'projectseele:road_asphalt_slab', 'projectseele:road_marking_slab'}
# Unconverted kerbs, islands and crossings between two TrafficCraft roads: they only bridge gaps of a few blocks.
PAVE2 = {'minecraft:smooth_stone', 'minecraft:smooth_stone_slab', 'minecraft:gray_concrete', 'minecraft:white_concrete',
         'minecraft:yellow_concrete', 'minecraft:light_gray_concrete', 'minecraft:polished_andesite', 'minecraft:andesite_slab'}
AIRISH = {'minecraft:air', 'minecraft:cave_air', 'minecraft:light', 'minecraft:short_grass', 'minecraft:grass', 'minecraft:snow'}
N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

POST_STATE = 'minecraft:iron_bars[east={east},north={north},south={south},waterlogged=false,west={west}]'
SIGN = 'minecraft:warped_sign[rotation={r},waterlogged=false]'
REPLACE = {'minecraft:air', 'minecraft:cave_air', 'minecraft:short_grass', 'minecraft:grass', 'minecraft:fern',
           'minecraft:dandelion', 'minecraft:poppy', 'minecraft:dead_bush', 'minecraft:azure_bluet', 'minecraft:oxeye_daisy',
           'minecraft:cornflower', 'minecraft:allium', 'minecraft:blue_orchid', 'minecraft:white_tulip',
           'minecraft:red_tulip', 'minecraft:orange_tulip', 'minecraft:pink_tulip', 'minecraft:lily_of_the_valley'}
NOT_GROUND = ('air', 'water', 'lava', 'leaves', 'fence', '_wall', 'pane', 'bars', 'sign', 'door', 'button', 'torch',
              'lantern', 'carpet', 'rail', 'sapling', 'vine', 'chain', 'ladder', 'scaffolding', 'bamboo', 'cane', 'kelp',
              'grass', 'fern', 'flower', 'bush', 'tulip', 'poppy', 'dandelion', 'snow', 'light', 'cobweb', 'glass',
              'iron_block', 'gold_block', 'copper')

# Places: stations by MTR position, plus real places without a station (lat/lon -> blocks, 4 m per block).
ANCHOR = (139.0085, 35.2662, 30, 220)
REAL_PLACES = [('宮城野', 35.2555, 139.0590, 2), ('芦ノ湯', 35.2135, 139.0465, 2), ('箱根園', 35.2196, 139.0178, 2),
               ('箱根峠', 35.1797, 139.0431, 2)]
# Station -> (sign name, weight). Weight 4: towns a sign names from far; 2: districts and sights; 1: small stops.
# Stations missing here are not destinations (cable-car stops, NERV inside stations, the unused Bayside link).
PLACE_TABLE = {
    '小田原駅': ('小田原', 4), '箱根湯本駅': ('箱根湯本', 4), '強羅駅': ('強羅', 4), '宮ノ下駅': ('宮ノ下', 4),
    '元箱根港': ('元箱根', 4), '箱根町港': ('箱根町', 4), '第三新东京中央': ('第3新東京市中央', 4), '新箱根中央': ('新箱根中央', 4),
    '箱根板橋駅': ('箱根板橋', 1), '風祭駅': ('風祭', 1), '入生田駅': ('入生田', 1), '塔ノ沢駅': ('塔ノ沢', 1),
    '大平台駅': ('大平台', 1), '小涌谷駅': ('小涌谷', 2), '彫刻の森駅': ('彫刻の森', 1), '早雲山': ('早雲山', 2),
    '大涌谷': ('大涌谷', 2), '姥子': ('姥子', 1), '桃源台': ('桃源台', 2), '早川駅': ('早川', 1), '鴨宮駅': ('鴨宮', 2),
    '緑町駅': ('緑町', 1), '井細田駅': ('井細田', 1), '五百羅漢駅': ('五百羅漢', 1), '穴部駅': ('穴部', 1),
    '飯田岡駅': ('飯田岡', 1), '相模沼田駅': ('相模沼田', 1), '岩原駅': ('岩原', 1), '塚原駅': ('塚原', 1),
    '和田河原駅': ('和田河原', 2), '螢田駅': ('螢田', 1), '富水駅': ('富水', 1), '栢山駅': ('栢山', 2),
    '上大井駅': ('上大井', 1), '下曽我駅': ('下曽我', 1), '联合国总部机场': ('国連本部空港', 2),
    '西部城区': ('西部市街', 2), '南部住宅区': ('南部住宅地区', 2), '湾岸防卫区': ('湾岸防衛区', 2),
    'NERV 地面入口': ('NERV地上入口', 2), 'NERV 航空基地': ('NERV航空基地', 1), 'NERV 港口': ('NERV港', 1),
    '箱根湾机场': ('箱根湾空港', 2), '新箱根市民广场': ('新箱根市民広場', 2), '地区技术中心': ('地区技術センター', 1),
    '新箱根机场': ('新箱根空港', 2), '雾里住宅区': ('霧里住宅地区', 2),
}
TOKYO3 = {'第3新東京市中央', '西部市街', '南部住宅地区', '湾岸防衛区', 'NERV地上入口', 'NERV航空基地', 'NERV港', '箱根湾空港',
          '新箱根中央', '新箱根市民広場', '地区技術センター', '新箱根空港', '霧里住宅地区'}
HERE = 150          # a place this close (straight line) is where the junction is, not a destination
FAR = 3500          # road blocks: further places are not signed
SPACING = 70        # between chosen junctions
GRID_SPACING = 190  # inside the two street grids


# ---------------------------------------------------------------- world reading

def decode(bs):
    pal = bs['palette']
    data = bs.get('data')
    if data is None or len(pal) == 1:
        return np.zeros(4096, np.int64), pal
    bits = max(4, (len(pal) - 1).bit_length())
    per = 64 // bits
    words = np.array(data, dtype=np.int64).astype(np.uint64)
    at = np.arange(4096)
    return ((words[at // per] >> ((at % per) * bits).astype(np.uint64)) & np.uint64((1 << bits) - 1)).astype(np.int64), pal


def state_name(entry):
    name = str(entry['Name'])
    props = entry.get('Properties')
    if not props:
        return name
    return name + '[' + ','.join(f'{k}={props[k]}' for k in sorted(props)) + ']'


def code_of(name):
    if name.startswith('trafficcraft:asphalt'):
        return 1
    if name.startswith('trafficcraft:concrete'):
        return 2
    return 3 if name in OLD else 4 if name in PAVE2 else 0


def chunks_of(path):
    buf = open(path, 'rb').read()
    for i in range(1024):
        loc = int.from_bytes(buf[4 * i:4 * i + 3], 'big')
        if loc:
            n = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
            yield nbtlib.File.parse(io.BytesIO(zlib.decompress(buf[loc * 4096 + 5:loc * 4096 + 4 + n])))


def scan_region(path):
    """Road cells of one region: x, y, z, code (1 asphalt, 2 concrete footway, 3 old paving, 4 other paving; 3 and 4
    only with air above)."""
    out = []
    for root in chunks_of(path):
        cx, cz = int(root['xPos']), int(root['zPos'])
        secs = {int(s['Y']): s for s in root.get('sections', []) if 'block_states' in s}
        for sy, s in secs.items():
            if sy < -10:
                continue                   # the GeoFront cavern
            names = [str(p['Name']) for p in s['block_states']['palette']]
            codes = np.array([code_of(n) for n in names])
            if not codes.any():
                continue
            ids, _ = decode(s['block_states'])
            c = codes[ids]
            idx = np.nonzero(c)[0]
            ly, lz, lx, cc = idx >> 8, (idx >> 4) & 15, idx & 15, c[idx]
            open_ = np.array([n in AIRISH for n in names])
            above = np.ones(len(idx), bool)
            low = ly < 15
            above[low] = open_[ids[((ly[low] + 1) << 8) | (lz[low] << 4) | lx[low]]]
            up = secs.get(sy + 1)
            if (~low).any() and up is not None:
                uids, upal = decode(up['block_states'])
                uopen = np.array([str(p['Name']) in AIRISH for p in upal])
                above[~low] = uopen[uids[(lz[~low] << 4) | lx[~low]]]
            keep = (cc <= 2) | above
            out.append(np.column_stack((cx * 16 + lx[keep], sy * 16 + ly[keep], cz * 16 + lz[keep], cc[keep])).astype(np.int32))
    return np.concatenate(out) if out else np.empty((0, 4), np.int32)


def scan(world, dest):
    paths = sorted(glob.glob(str(world / REGION / '*.mca')))
    with ProcessPoolExecutor(16) as ex:
        cells = np.concatenate(list(ex.map(scan_region, paths)))
    np.save(dest, cells)
    return cells


class Blocks:
    """Block states and block entity positions of a world, chunk by chunk."""

    def __init__(self, world):
        self.folder = Path(world) / REGION
        self.bufs, self.chunks = {}, {}

    def chunk(self, cx, cz):
        if (cx, cz) not in self.chunks:
            key = (cx >> 5, cz >> 5)
            if key not in self.bufs:
                p = self.folder / f'r.{key[0]}.{key[1]}.mca'
                self.bufs[key] = p.read_bytes() if p.exists() else None
            buf = self.bufs[key]
            data = None
            if buf is not None:
                i = 4 * ((cx & 31) + (cz & 31) * 32)
                loc = int.from_bytes(buf[i:i + 3], 'big')
                if loc:
                    n = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
                    root = nbtlib.File.parse(io.BytesIO(zlib.decompress(buf[loc * 4096 + 5:loc * 4096 + 4 + n])))
                    secs = {}
                    for s in root['sections']:
                        if 'block_states' in s:
                            secs[int(s['Y'])] = s['block_states']
                    ents = {(int(e['x']), int(e['y']), int(e['z'])): str(e['id']) for e in root.get('block_entities', [])}
                    data = dict(raw=secs, dec={}, ents=ents)
            self.chunks[cx, cz] = data
        return self.chunks[cx, cz]

    def get(self, x, y, z):
        c = self.chunk(x >> 4, z >> 4)
        if c is None:
            return None
        sy = y >> 4
        if sy not in c['dec']:
            bs = c['raw'].get(sy)
            if bs is None:
                c['dec'][sy] = None
            else:
                ids, pal = decode(bs)
                c['dec'][sy] = (ids, [state_name(p) for p in pal])
        d = c['dec'][sy]
        if d is None:
            return 'minecraft:air'
        return d[1][d[0][((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]]

    def entity(self, x, y, z):
        c = self.chunk(x >> 4, z >> 4)
        return None if c is None else c['ents'].get((x, y, z))


# ---------------------------------------------------------------- road graph

def grids(cells):
    cells = cells[(cells[:, 0] >= X0) & (cells[:, 0] < X1) & (cells[:, 2] >= Z0) & (cells[:, 2] < Z1)]
    car = cells[:, 3] == 1
    inbox = np.zeros(len(cells), bool)
    for x0, x1, z0, z1 in OLD_BOXES:
        inbox |= (cells[:, 0] >= x0) & (cells[:, 0] <= x1) & (cells[:, 2] >= z0) & (cells[:, 2] <= z1)
    car |= (cells[:, 3] == 3) & inbox
    Y = np.full((Z1 - Z0, X1 - X0), -9999, np.int32)
    s = cells[car]
    np.maximum.at(Y, (s[:, 2] - Z0, s[:, 0] - X0), s[:, 1])
    F = np.full_like(Y, -9999)
    s = cells[cells[:, 3] == 2]
    np.maximum.at(F, (s[:, 2] - Z0, s[:, 0] - X0), s[:, 1])
    paved = np.zeros(Y.shape, bool)
    s = cells[cells[:, 3] >= 2]
    paved[s[:, 2] - Z0, s[:, 0] - X0] = True
    return Y, F, paved


def road_mask(Y, paved):
    C = Y > -9999
    # A road passing under a bridge touches the deck in plan: cut the lower cell of every pair more than 2 apart.
    drop = np.zeros_like(C)
    for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = np.roll(np.roll(Y, -dz, 0), -dx, 1)
        drop |= C & (n > -9999) & (n - Y > 2)
    C &= ~drop
    # Kerbs, islands and crossings left in other paving split one road into pieces: bridge paved gaps up to 8 wide.
    yy, xx = np.ogrid[-4:5, -4:5]
    C |= ndi.binary_closing(C, (xx * xx + yy * yy) <= 16) & paved & ~drop
    holes, _ = ndi.label(~C)
    small = np.bincount(holes.ravel()) < 40
    small[0] = False
    C |= small[holes]
    lab, _ = ndi.label(C)
    keep = np.bincount(lab.ravel()) >= 200
    keep[0] = False
    return ndi.binary_opening(keep[lab], np.ones((2, 2)))


def thin(img):
    """Zhang-Suen thinning."""
    img = img.astype(np.uint8)
    img[0, :] = img[-1, :] = img[:, 0] = img[:, -1] = 0
    while True:
        changed = 0
        for step in (0, 1):
            P = np.pad(img, 1)
            p2, p3, p4, p5 = P[:-2, 1:-1], P[:-2, 2:], P[1:-1, 2:], P[2:, 2:]
            p6, p7, p8, p9 = P[2:, 1:-1], P[2:, :-2], P[1:-1, :-2], P[:-2, :-2]
            nb = [p2, p3, p4, p5, p6, p7, p8, p9]
            B = sum(n.astype(np.int8) for n in nb)
            A = sum(((nb[i] == 0) & (nb[(i + 1) % 8] == 1)).astype(np.int8) for i in range(8))
            c1, c2 = ((p2 * p4 * p6) == 0, (p4 * p6 * p8) == 0) if step == 0 else ((p2 * p4 * p8) == 0, (p2 * p6 * p8) == 0)
            m = (img == 1) & (B >= 2) & (B <= 6) & (A == 1) & c1 & c2
            changed += int(m.sum())
            img[m] = 0
        if not changed:
            return img.astype(bool)


def path_len(path):
    p = np.asarray(path, float)
    return float(np.hypot(*np.diff(p, axis=0).T).sum()) if len(p) > 1 else 0.0


def skeleton_edges(S):
    nb = sum(np.roll(np.roll(S, -dz, 0), -dx, 1).astype(np.int8) for dz, dx in N8) * S
    lab, n = ndi.label(S & ((nb >= 3) | (nb == 1)), np.ones((3, 3)))
    nodes = defaultdict(list)
    for z, x in np.argwhere(lab):
        nodes[int(lab[z, x])].append((int(z), int(x)))
    seen, edges = set(), []
    for nid, pix in nodes.items():
        for z, x in pix:
            for dz, dx in N8:
                q = (z + dz, x + dx)
                if not S[q] or lab[q] or (z, x) + q in seen:
                    continue
                path, prev, cur, end = [(z, x), q], (z, x), q, None
                while len(path) < 20000:
                    nxt = [(cur[0] + a, cur[1] + b) for a, b in N8]
                    nxt = [p for p in nxt if p != prev and p not in path[-3:] and S[p]]
                    hit = [p for p in nxt if lab[p]]
                    if hit:
                        path.append(hit[0])
                        end = int(lab[hit[0]])
                        break
                    if not nxt:
                        break
                    nxt.sort(key=lambda p: abs(p[0] - cur[0]) + abs(p[1] - cur[1]))
                    prev, cur = cur, nxt[0]
                    path.append(cur)
                seen.add((z, x) + q)
                if end is not None:
                    seen.add(path[-1] + path[-2])
                    edges.append((nid, end, path))
    return nodes, edges


class Graph:
    def __init__(self, nodes, edges):
        self.pos = {i: np.mean(p, axis=0) for i, p in nodes.items()}
        self.E, self.adj, self.next = {}, defaultdict(set), 0
        for a, b, p in edges:
            self.add(a, b, p)

    def add(self, a, b, p):
        k = self.next
        self.next += 1
        self.E[k] = [a, b, list(p)]
        self.adj[a].add(k)
        self.adj[b].add(k)
        return k

    def remove(self, k):
        a, b, _ = self.E.pop(k)
        self.adj[a].discard(k)
        self.adj[b].discard(k)

    def deg(self, n):
        return sum(2 if self.E[k][0] == self.E[k][1] else 1 for k in self.adj[n])

    def other(self, k, n):
        a, b, _ = self.E[k]
        return b if a == n else a

    def oriented(self, k, n):
        a, b, p = self.E[k]
        return p if a == n else p[::-1]

    def contract(self):
        changed = True
        while changed:
            changed = False
            for n in list(self.adj):
                ks = list(self.adj[n])
                if not ks:
                    del self.adj[n]
                    continue
                if len(ks) == 2 and self.deg(n) == 2:
                    k1, k2 = ks
                    a, b = self.other(k1, n), self.other(k2, n)
                    if a == n or b == n:
                        continue
                    p = self.oriented(k1, a) + self.oriented(k2, n)[1:]
                    self.remove(k1)
                    self.remove(k2)
                    self.add(a, b, p)
                    del self.adj[n]
                    changed = True

    def merge(self, keep, gone):
        for k in list(self.adj[gone]):
            a, b, p = self.E[k]
            self.E[k] = [keep if a == gone else a, keep if b == gone else b, p]
            self.adj[keep].add(k)
        del self.adj[gone]

    def split(self, k, i):
        """New node at pixel i of edge k."""
        a, b, p = self.E[k]
        n = max(self.pos) + 1
        self.pos[n] = np.asarray(p[i], float)
        self.remove(k)
        first = self.add(a, n, p[:i + 1])
        self.add(n, b, p[i:])
        return n, first


def build_graph(C, D):
    S = thin(C)
    nodes, edges = skeleton_edges(S)
    G = Graph(nodes, edges)
    for k in list(G.E):
        a, b, p = G.E[k]
        if a == b and path_len(p) < 60:
            G.remove(k)                     # a hole inside a wide road
    G.contract()

    def half(n):
        z, x = np.round(G.pos[n]).astype(int)
        return float(D[max(0, z - 3):z + 4, max(0, x - 3):x + 4].max())
    for _ in range(4):                      # spurs: corner nubs and stubs shorter than the road is wide
        cut = 0
        for k in list(G.E):
            if k not in G.E:
                continue
            a, b, p = G.E[k]
            for end, base in ((a, b), (b, a)):
                if G.deg(end) == 1 and G.deg(base) >= 3:
                    if path_len(p) < 2.5 * half(base) + 8:
                        G.remove(k)
                        del G.adj[end]
                        cut += 1
                    break
        G.contract()
        if not cut:
            break
    for _ in range(6):                      # a wide junction thins to two or more nodes a short edge apart
        merged = 0
        for k in sorted(G.E, key=lambda k: path_len(G.E[k][2])):
            if k not in G.E:
                continue
            a, b, p = G.E[k]
            if a != b and G.deg(a) >= 3 and G.deg(b) >= 3 and path_len(p) < max(8, 1.6 * (half(a) + half(b))):
                G.remove(k)
                G.pos[a] = (G.pos[a] + G.pos[b]) / 2
                G.merge(a, b)
                merged += 1
        G.contract()
        if not merged:
            break
    for k in list(G.E):
        a, b, p = G.E[k]
        if a == b and path_len(p) < 40:
            G.remove(k)
    G.contract()
    return G


def components(G):
    comp = {}
    for s in G.adj:
        if s in comp:
            continue
        stack, comp[s] = [s], s
        while stack:
            n = stack.pop()
            for k in G.adj[n]:
                m = G.other(k, n)
                if m not in comp:
                    comp[m] = s
                    stack.append(m)
    return comp


def link_gaps(G, Y, reach=45):
    """Join each dead end to the nearest centre line of another piece within reach and 8 blocks of height: bridges,
    level crossings and stations in older paving cut the drivable surface without cutting the road. The links are
    marked virtual: they carry routes but never make a junction."""
    from scipy.spatial import cKDTree
    comp = components(G)
    pix = [(k, i, z, x) for k, (_, _, p) in G.E.items() for i, (z, x) in enumerate(p)]
    tree = cKDTree(np.array([(z, x) for _, _, z, x in pix], float))
    links = []
    for n in list(G.adj):
        if G.deg(n) != 1:
            continue
        z, x = np.round(G.pos[n]).astype(int)
        yn = Y[z, x]
        best = None
        for j in tree.query_ball_point((z, x), reach):
            k, i, pz, px = pix[j]
            a, b, _ = G.E[k]
            if comp[a] == comp[n] or Y[pz, px] <= -9999 or yn <= -9999 or abs(int(Y[pz, px]) - int(yn)) > 8:
                continue
            d = math.hypot(pz - z, px - x)
            if best is None or d < best[0]:
                best = (d, k, i)
        if best:
            links.append((n, best[1], best[2]))
    by_edge = defaultdict(list)
    for n, k, i in links:
        by_edge[k].append((i, n))
    G.virtual = set()
    G.virtual_nodes = set()
    for k, items in by_edge.items():
        current = k
        for i, n in sorted(items, reverse=True):
            a, b, p = G.E[current]
            if i == 0:
                m = a
            elif i == len(p) - 1:
                m = b
            else:
                m, current = G.split(current, i)
                G.virtual_nodes.add(m)
            if m == n:
                continue
            z0, x0 = np.round(G.pos[n]).astype(int)
            z1, x1 = np.round(G.pos[m]).astype(int)
            steps = max(abs(z1 - z0), abs(x1 - x0), 1)
            path = [(int(round(z0 + (z1 - z0) * t / steps)), int(round(x0 + (x1 - x0) * t / steps))) for t in range(steps + 1)]
            G.virtual.add(G.add(n, m, path))
    return len(G.virtual)


def dijkstra(G, src, lengths):
    """dist, first edge out of src, for every node."""
    dist, first = {src: 0.0}, {src: None}
    heap = [(0.0, src, None)]
    while heap:
        d, n, f = heapq.heappop(heap)
        if d > dist.get(n, 1e18):
            continue
        for k in G.adj[n]:
            m = G.other(k, n)
            nd = d + lengths[k]
            if nd < dist.get(m, 1e18):
                dist[m] = nd
                first[m] = k if n == src else f
                heapq.heappush(heap, (nd, m, first[m]))
    return dist, first


# ---------------------------------------------------------------- places

def load_places(world, notes):
    from prepare_mtr_member_patch_r52 import Parser
    places = []
    # since batch 521 the MTR names are the R-4 "日本語|中文|English" form; the table is keyed by the old names
    renamed = {}
    for line in Path(notes, 'map-roads-R4-names-20261118.tsv').read_text('utf8').splitlines():
        parts = line.split('	')
        if len(parts) == 3 and parts[0] == 'stations':
            renamed[parts[2]] = parts[1]
    for f in sorted((Path(world) / 'mtr/projectseele/geofront/stations').rglob('*')):
        if not f.is_file():
            continue
        v = Parser(f.read_bytes()).node().value
        v['name'] = renamed.get(v['name'], v['name'])
        if v['name'] not in PLACE_TABLE or v['position1']['y'] < -150:
            continue
        name, weight = PLACE_TABLE[v['name']]
        x = (v['position1']['x'] + v['position2']['x']) / 2
        z = (v['position1']['z'] + v['position2']['z']) / 2
        kind = 'station' if v['name'].endswith('駅') or name in TOKYO3 and '空港' not in name and 'NERV' not in name else 'facility'
        if name.endswith('港') or '空港' in name:
            kind = 'facility'
        places.append(dict(name=name, x=x, z=z, weight=weight, kind=kind, source=v['name']))
    lon0, lat0, ax, az = ANCHOR
    for name, lat, lon, weight in REAL_PLACES:
        x = ax + (lon - lon0) * math.cos(math.radians(lat0)) * 111320 / 4
        z = az + (lat0 - lat) * 110950 / 4
        places.append(dict(name=name, x=x, z=z, weight=weight, kind='area', source='lat/lon'))
    # every Japanese name must be the table's: check against the R4 station names
    table = {}
    for line in Path(notes, 'map-roads-R4-names-20261118.tsv').read_text('utf8').splitlines():
        parts = line.split('\t')
        if len(parts) == 3 and parts[0] == 'stations':
            table[parts[1]] = parts[2].split('|')[0]
    for p in places:
        if p['source'] in table and table[p['source']] not in (p['name'], p['name'] + '港'):
            if not (p['source'].endswith('港') and table[p['source']].startswith(p['name'])):
                raise SystemExit(f"{p['source']}: R4 says {table[p['source']]}, plan says {p['name']}")
    return places


# ---------------------------------------------------------------- rails and other sessions

def rail_hulls(world):
    """Each MTR rail as the hull of its ends and the meeting point of its end tangents: the curve stays inside."""
    from map_pipeline.native_rails import load_rails
    from prepare_mtr_member_patch_r52 import Parser
    ang = {'E': 0, 'ESE': 22.5, 'SE': 45, 'SSE': 67.5, 'S': 90, 'SSW': 112.5, 'SW': 135, 'WSW': 157.5, 'W': 180,
           'WNW': 202.5, 'NW': 225, 'NNW': 247.5, 'N': 270, 'NNE': 292.5, 'NE': 315, 'ENE': 337.5,
           'NEE': 337.5, 'SEE': 22.5, 'SWW': 157.5, 'NWW': 202.5}
    hulls = []
    for f in sorted((Path(world) / 'mtr/projectseele/geofront/rails').rglob('*')):
        if not f.is_file():
            continue
        r = Parser(f.read_bytes()).node().value
        a = np.array([r['position1']['x'], r['position1']['z']], float)
        b = np.array([r['position2']['x'], r['position2']['z']], float)
        ys = (r['position1']['y'], r['position2']['y'])
        t1 = np.array([math.cos(math.radians(ang[r['angle1']])), math.sin(math.radians(ang[r['angle1']]))])
        t2 = np.array([math.cos(math.radians(ang[r['angle2']])), math.sin(math.radians(ang[r['angle2']]))])
        pts = [a, b]
        M = np.column_stack((t1, -t2))
        if abs(np.linalg.det(M)) > 1e-6:
            s, t = np.linalg.solve(M, b - a)
            if s > 0 and t > 0:
                pts.append(a + s * t1)
            else:
                L = np.linalg.norm(b - a)
                pts += [a + t1 * L / 2, b + t2 * L / 2]
        else:
            L = np.linalg.norm(b - a)
            pts += [a + t1 * L / 2, b + t2 * L / 2]
        hulls.append(dict(pts=np.array(pts), y0=min(ys) - 4, y1=max(ys) + 8, mode=r['transportMode']))
    return hulls


def near_rail(hulls, x, y, z, margin=3.5):
    q = np.array([x + .5, z + .5])
    for h in hulls:
        if not (h['y0'] <= y <= h['y1']):
            continue
        p = h['pts']
        if np.any(q < p.min(0) - margin) or np.any(q > p.max(0) + margin):
            continue
        if point_hull_distance(q, p) <= margin:
            return True
    return False


def point_hull_distance(q, pts):
    """Distance from q to the convex hull of a few points (0 inside)."""
    from scipy.spatial import ConvexHull
    try:
        hull = ConvexHull(pts)
        eq = hull.equations
        if np.all(eq[:, :2] @ q + eq[:, 2] <= 1e-9):
            return 0.0
        v = pts[hull.vertices]
    except Exception:
        v = pts
    best = 1e18
    for i in range(len(v)):
        a, b = v[i], v[(i + 1) % len(v)]
        d = b - a
        t = 0 if not d.any() else np.clip((q - a) @ d / (d @ d), 0, 1)
        best = min(best, float(np.linalg.norm(q - a - t * d)))
    return best


LIST_GLOBS = ['E:/eva-map-*/**/rows*.json', 'F:/eva/.claude/map-roads-work/plans/**/rows*.json', 'F:/eva/.claude/map-work/**/rows*.json']


def list_conflicts(cells, world, globs=LIST_GLOBS):
    """Other sessions' row lists still waiting to be written that touch one of cells, or its column within 4 blocks
    of height: {cell: [files]}, and the number of lists read. A list counts as written when most of its sampled
    rows already show their after state in the world (plan_forest_transitions.still_pending)."""
    from plan_forest_transitions import still_pending
    cols = defaultdict(list)
    for x, y, z in cells:
        cols[x, z].append((x, y, z))
    files = set()
    for pat in globs:
        files.update(f for f in glob.glob(pat, recursive=True) if '/client/' not in f.replace(os.sep, '/').replace('\\', '/'))
    hits, used = defaultdict(list), 0
    for f in sorted(files):
        try:
            rows = json.load(open(f, encoding='utf8'))
        except Exception:
            continue
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], list):
            continue
        used += 1
        found = defaultdict(list)
        for r in rows:
            if len(r) >= 5 and isinstance(r[0], int) and (r[0], r[2]) in cols:
                for q in cols[r[0], r[2]]:
                    if abs(r[1] - q[1]) <= 4:
                        found[q].append(f)
        if found and still_pending(rows, world):
            for q, fs in found.items():
                hits[q] += fs
    return hits, used


# ---------------------------------------------------------------- signs

def arrow(h, d):
    """Arrow for leaving along direction d when arriving heading h (x east, z south)."""
    ang = math.degrees(math.atan2(h[0] * d[1] - h[1] * d[0], h[0] * d[0] + h[1] * d[1]))   # >0: right turn
    a = abs(ang)
    if a < 22:
        return '↑'
    if a < 65:
        return '↗' if ang > 0 else '↖'
    return '→' if ang > 0 else '←'


def junction_name(n_pos, places):
    best = None
    for p in places:
        d = math.hypot(p['x'] - n_pos[0], p['z'] - n_pos[1])
        if d < 130 and (best is None or d < best[0]):
            best = (d, p)
    if best is None:
        return None, None
    p = best[1]
    suffix = '駅前' if p['kind'] == 'station' else '入口' if p['kind'] == 'facility' and not p['name'].endswith('入口') else ''
    name = p['name'] + suffix
    if text_width(name) > SIGN_WIDTH:
        name = p['name']
    return name, p['name']


def area_of(x, z):
    if x < -1000:
        return '新箱根・霧里'
    if z >= 1500:
        return '芦ノ湖畔（元箱根・箱根町）'
    if x < 640:
        return '第3新東京市'
    if x < 1700:
        return '箱根（強羅・宮ノ下・小涌谷）'
    if x >= 2400 and z < 0:
        return '小田原北部（大雄山線・小田急線沿線）'
    if x < 2900:
        return '箱根湯本・風祭'
    return '小田原'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--notes', type=Path, required=True)
    ap.add_argument('--signs-audit', type=Path, help='existing signs (rail-signs-audit signs.json); default under --notes')
    ap.add_argument('--rescan', action='store_true')
    ap.add_argument('--target', type=int, default=60)
    ap.add_argument('--only', help='fill-in pass: only candidates within 15 blocks of these "x,z;x,z" centres')
    ap.add_argument('--right-fallback', action='store_true', help='fill-in pass: try the right shoulder when the left has no spot')
    ap.add_argument('--deck-post', action='store_true',
                    help='fill-in pass: on a deck with nothing under the shoulder, stand the post on the outer footway cell')
    ap.add_argument('--min-approaches', type=int, default=2)
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    a.out.mkdir(parents=True, exist_ok=True)
    cache = a.work / 'roads.npy'
    cells = scan(a.world, cache) if a.rescan or not cache.exists() else np.load(cache)
    Y, F, paved = grids(cells)
    C = road_mask(Y, paved)
    D = ndi.distance_transform_edt(C).astype(np.float32)
    G = build_graph(C, D)
    nlinks = link_gaps(G, Y)
    lengths = {k: path_len(p) for k, (_, _, p) in G.E.items()}
    places = load_places(a.world, a.notes)

    # snap places onto the graph: nearest centre-line pixel within 220 blocks (350 for areas), a piece under 1500
    # blocks long counting as 80 blocks further away (a station forecourt loop is not where its roads are)
    comp = components(G)
    comp_len = Counter()
    for k, (a_, _, p) in G.E.items():
        comp_len[comp[a_]] += lengths[k]

    def pixels():
        pix = [(k, i, z, x) for k, (a_, _, pp) in G.E.items() if k not in G.virtual for i, (z, x) in enumerate(pp)]
        pen = np.array([0 if comp_len[comp.get(G.E[k][0], -1)] >= 1500 else 80 for k, _, _, _ in pix], float)
        return pix, np.array([(z, x) for _, _, z, x in pix], float), pen
    pix, arr, pen = pixels()
    place_node = {}
    for p in places:
        pz, px = p['z'] - Z0, p['x'] - X0
        d = np.hypot(arr[:, 0] - pz, arr[:, 1] - px)
        j = int(np.argmin(d + pen))
        if d[j] > (350 if p['kind'] == 'area' else 220):      # a pass or a lakeside area lies off the road's end
            p['snapped'] = None
            continue
        k, i, _, _ = pix[j]
        _, _, path = G.E[k]
        if i in (0, len(path) - 1):
            n = G.E[k][0] if i == 0 else G.E[k][1]
        else:
            a0 = G.E[k][0]
            n, _ = G.split(k, i)
            comp[n] = comp[a0]
            pix, arr, pen = pixels()
        p['snapped'] = float(d[j])
        place_node[p['name']] = n
    lengths = {k: path_len(p) for k, (_, _, p) in G.E.items()}

    # route usage: shortest paths between every two places, counted per (junction, edge)
    usage = defaultdict(Counter)
    through = Counter()
    pnames = list(place_node)
    for i, s in enumerate(pnames):
        parent = {place_node[s]: None}
        heap = [(0.0, place_node[s])]
        best = {place_node[s]: 0.0}
        while heap:
            d0, n = heapq.heappop(heap)
            if d0 > best[n]:
                continue
            for k in G.adj[n]:
                m = G.other(k, n)
                nd = d0 + lengths[k]
                if nd < best.get(m, 1e18):
                    best[m] = nd
                    parent[m] = (n, k)
                    heapq.heappush(heap, (nd, m))
        for t in pnames[i + 1:]:
            m = place_node[t]
            if m not in parent or best[m] > FAR * 2:
                continue
            chain = []
            while parent[m] is not None:
                n, k = parent[m]
                chain.append((n, k, m))
                m = n
            for (n1, k1, m1), (n2, k2, m2) in zip(chain, chain[1:]):
                # node m2 == n1 is passed through, entering by k2 and leaving by k1
                usage[n1][k1] += 1
                usage[n1][k2] += 1
                through[n1] += 1

    def arms(n):
        out = []
        c = G.pos[n]
        R = float(D[int(round(c[0])), int(round(c[1]))])
        for k in G.adj[n]:
            a_, b_, _ = G.E[k]
            if a_ == b_:
                continue
            path = G.oriented(k, n)
            pz = np.asarray(path, float)
            dist = np.hypot(pz[:, 0] - c[0], pz[:, 1] - c[1])
            i = int(np.argmax(dist >= R + 12)) if (dist >= R + 12).any() else len(pz) - 1
            v = pz[i] - c
            if not np.hypot(*v):
                continue
            v = v / np.hypot(*v)
            seg = (dist >= R + 3) & (dist <= R + 25)
            ws = [2 * D[int(z), int(x)] - 1 for z, x in pz[seg]] or [3.0]
            m = G.other(k, n)
            out.append(dict(edge=k, d=(float(v[1]), float(v[0])), width=float(np.median(ws)), length=lengths[k], to=m,
                            real=k not in G.virtual and (G.deg(m) >= 3 or lengths[k] >= 60 or m in place_node.values()),
                            used=usage[n][k], path=path))
        # two centre lines leaving within 25 degrees are one road (a split carriageway or a thinning fork)
        kept = []
        for arm in sorted(out, key=lambda o: (-o['real'], -o['used'], -o['width'])):
            if all(math.degrees(math.acos(max(-1, min(1, arm['d'][0] * o['d'][0] + arm['d'][1] * o['d'][1])))) > 25 for o in kept):
                kept.append(arm)
        return kept, R

    def destinations(n, A, wx, wz, here):
        """Per arm: the place a sign names that way. Distances run along the roads leaving by that arm without coming
        back through the junction; a place counts for an arm whose route is within 30% of its best one and whose
        bearing is within 100 degrees of the arm."""
        best = {}
        per_arm = {}
        for arm in A:
            k = arm['edge']
            m = arm['to']
            saved = G.adj[n]
            G.adj[n] = set()                   # no way back through the junction
            dist, _ = dijkstra(G, m, lengths)
            G.adj[n] = saved
            per_arm[k] = {name: dist[node] + lengths[k] for name, node in place_node.items() if node in dist}
            for name, d in per_arm[k].items():
                best[name] = min(best.get(name, 1e18), d)
        for arm in A:
            arm['options'] = []
            if not arm['real']:
                continue
            ang_arm = math.atan2(arm['d'][1], arm['d'][0])
            for p in places:
                name = p['name']
                if name == here or name not in per_arm[arm['edge']]:
                    continue
                d = per_arm[arm['edge']][name]
                straight = math.hypot(p['x'] - wx, p['z'] - wz)
                if straight < HERE or d > FAR or d > 1.3 * best[name]:
                    continue
                diff = abs((math.atan2(p['z'] - wz, p['x'] - wx) - ang_arm + math.pi) % (2 * math.pi) - math.pi)
                if math.degrees(diff) > 100:
                    continue
                arm['options'].append((d / p['weight'], round(d), name))
            arm['options'].sort()
        # one name per junction: the arm it is nearest along keeps it
        for arm in A:
            arm['dest'] = arm['options'][0] if arm['options'] else None
        for _ in range(6):
            owner = {}
            for arm in A:
                if arm['dest']:
                    _, d, name = arm['dest']
                    if name not in owner or owner[name][1] > d:
                        owner[name] = (arm['edge'], d)
            moved = False
            for arm in A:
                if arm['dest'] and owner[arm['dest'][2]][0] != arm['edge']:
                    arm['options'] = [o for o in arm['options'] if o[2] != arm['dest'][2]]
                    arm['dest'] = arm['options'][0] if arm['options'] else None
                    moved = True
            if not moved:
                break

    # candidates: three or more real arms, two of them carrying place-to-place routes, two with a place to name
    cand = []
    for n in list(G.adj):
        if G.deg(n) < 3 or n in G.virtual_nodes:
            continue
        A, R = arms(n)
        real = [x for x in A if x['real']]
        used = [x for x in real if x['used'] > 0]
        if len(real) < 3 or len(used) < 2:
            continue
        z, x = G.pos[n]
        wx, wz = float(x + X0), float(z + Z0)
        name, here = junction_name((wx, wz), places)
        destinations(n, A, wx, wz, here)
        named = [x for x in A if x['dest']]
        if len(named) < 2:
            continue
        score = through[n] + 2 * len(named) * 10 + (10 if len(used) >= 3 else 0)
        cand.append(dict(node=n, x=wx, z=wz, y=int(Y[int(round(z)), int(round(x))]) if Y[int(round(z)), int(round(x))] > -9999
                         else int(np.max(Y[int(z) - 6:int(z) + 7, int(x) - 6:int(x) + 7])), R=R, arms=A, score=score, area=area_of(wx, wz), name=name, here=here))
    cand.sort(key=lambda c: -c['score'])
    print('candidate junctions', len(cand), flush=True)

    def in_grid(c):
        return (-1900 <= c['x'] <= -1100 and 290 <= c['z'] <= 1030) or (-380 <= c['x'] <= 330 and 0 <= c['z'] <= 720)

    order = []
    for key in ('箱根湯本', '小田原', '強羅', '第3新東京市中央', '宮ノ下', '新箱根中央', '元箱根', '箱根町', '小涌谷', '大涌谷'):
        p = next(p for p in places if p['name'] == key)
        near = [c for c in cand if math.hypot(c['x'] - p['x'], c['z'] - p['z']) < 400 and c not in order]
        if near:
            order.append(min(near, key=lambda c: math.hypot(c['x'] - p['x'], c['z'] - p['z']) - c['score'] * .3))
    order += [c for c in cand if c not in order]

    # ---------------------------------------------------------------- placement
    B = Blocks(a.world)
    hulls = rail_hulls(a.world)
    blocked_cols = set()
    from map_pipeline.city_protection import load as city_load
    from map_pipeline.lift_protection import load as lift_load
    from map_pipeline.launch_protection import load as launch_load
    guards = [g(a.world) for g in (city_load, lift_load, launch_load)]
    audit = a.signs_audit or a.notes / 'rail-signs-audit-20261117' / 'signs.json'
    existing = [s_ for s_ in json.loads(Path(audit).read_text('utf8')) if s_['y'] > -150]
    ex_xyz = np.array([(s_['x'], s_['y'], s_['z']) for s_ in existing], float)
    ex_arrow = np.array([any(ch in s_['text'] for ch in '←→↑↓↖↗') for s_ in existing])

    def guarded(x, y, z):
        for g in guards:
            try:
                g.assert_positions([(x, y, z)])
            except ValueError:
                return True
        return False

    def is_open(st):
        return st is not None and (st.split('[')[0] in REPLACE or st.split('[')[0] == 'minecraft:light')

    def connects(st):
        """Whether an iron-bar post joins this neighbour (IronBarsBlock.attachsTo): bars, panes, walls and blocks
        with a full side do; plants, fences, slabs, stairs, slopes, leaves and signs do not."""
        if st is None:
            return False
        base = st.split('[')[0].split(':')[-1]
        if 'bars' in base or 'pane' in base or base.endswith('_wall'):
            return True
        if st.split('[')[0] in REPLACE or any(w in base for w in (
                'air', 'light', 'snow', 'slope', 'slab', 'stairs', 'fence', 'leaves', 'sign', 'carpet', 'torch', 'lantern',
                'chain', 'door', 'button', 'lever', 'rail', 'flower', 'grass', 'fern', 'bush', 'sapling', 'vine', 'water',
                'lava', 'ladder', 'pot', 'head', 'skull', 'banner', 'candle', 'cake', 'bed', 'scaffolding', 'bamboo')):
            return False
        return True

    def ground_ok(st):
        if st is None:
            return False
        if st.split('[')[0] in OLD:
            return False                       # unconverted carriageway
        if 'type=bottom' in st or ('slope' in st and 'layers=' in st and int(st.split('layers=')[1].split(',')[0].rstrip(']')) < 6):
            return False                       # a post on a low slope or a bottom slab would float above it
        base = st.split('[')[0].split(':')[-1]
        if base in ('grass_block', 'snow_block'):
            return True
        return not any(w in base for w in NOT_GROUND)

    def see_through(st):
        base = st.split('[')[0]
        return is_open(st) or base in ('minecraft:snow', 'minecraft:light') or 'slope' in base or base.endswith('_sign') \
            or base.endswith('carpet') or base == 'minecraft:rail'

    def line_of_sight(p0, p1):
        steps = int(max(abs(p1[i] - p0[i]) for i in range(3)) * 2) + 1
        for t in range(1, steps):
            q = [p0[i] + (p1[i] - p0[i]) * t / steps for i in range(3)]
            c_ = (math.floor(q[0]), math.floor(q[1]), math.floor(q[2]))
            if c_ == tuple(math.floor(v) for v in p1):
                continue
            st = B.get(*c_)
            if st is None or not see_through(st):
                return False
        return True

    def cell_type(z, x):
        if not (0 <= z < Y.shape[0] and 0 <= x < Y.shape[1]):
            return 'out'
        if Y[z, x] > -9999 or C[z, x]:
            return 'road'
        if F[z, x] > -9999:
            return 'foot'
        return 'other'

    def place_sign(c, arm, side=1):
        """First good post spot for an approach, or the reason there is none. side=-1 tries the right shoulder."""
        path = np.asarray(arm['path'], float)
        cz, cx = G.pos[c['node']]
        along = np.r_[0, np.cumsum(np.hypot(*np.diff(path, axis=0).T))]
        reasons = Counter()
        mouth = max(c['R'], 2.0) + 2
        for s_ in [mouth + v for v in (5, 6, 4, 7, 8, 9, 3, 10, 11, 12, 14, 16, 18)]:
            if s_ + 4 > along[-1]:
                reasons['approach too short'] += 1
                continue
            i = int(np.searchsorted(along, s_))
            j0, j1 = max(0, i - 4), min(len(path) - 1, i + 4)
            t = path[j1] - path[j0]
            if not np.hypot(*t):
                continue
            t = t / np.hypot(*t)                                   # (dz, dx) outward
            hx, hz = -t[1], -t[0]                                  # driving towards the junction
            lx, lz = hz * side, -hx * side                         # driver's left (right when side is -1)
            z0, x0 = path[i]
            yroad = None
            post = None
            foot = 0
            last_foot = None
            for step in np.arange(0.5, 16, 0.5):
                zz, xx = int(round(z0 + lz * step)), int(round(x0 + lx * step))
                ct = cell_type(zz, xx)
                if ct == 'road':
                    if Y[zz, xx] > -9999:
                        yroad = int(Y[zz, xx])
                    if foot:
                        break                                      # another road beyond the footway: a median
                    continue
                if ct == 'foot':
                    if last_foot != (zz, xx):
                        foot += 1
                        last_foot = (zz, xx)
                    continue
                post = (zz, xx)
                break
            if yroad is None:
                reasons['no road level'] += 1
                continue
            if abs(yroad - c['y']) > 2 + 0.3 * s_:
                reasons['road beside is on another level'] += 1
                continue
            if post is None or foot > 3:
                if last_foot is None:
                    reasons['no shoulder'] += 1
                    continue
                post = last_foot                                   # wide footway: its outer edge
            outward = [post] if post == last_foot else [post] + [(int(round(post[0] + lz * k_)), int(round(post[1] + lx * k_))) for k_ in (1, 2)]
            if a.deck_post and last_foot is not None and last_foot not in outward:
                outward.append(last_foot)                          # deck: the outer footway cell, tried last
            for pz, px in outward:
                if math.hypot(pz - z0, px - x0) > arm['width'] / 2 + 6:
                    reasons['shoulder too far'] += 1
                    continue
                wx_, wz_ = px + X0, pz + Z0
                # ground: the top solid block within 3 of the road level with open cells above
                gy = None
                for y in range(yroad + 3, yroad - 4, -1):
                    st = B.get(wx_, y, wz_)
                    if st is not None and ground_ok(st) and is_open(B.get(wx_, y + 1, wz_)):
                        gy = y
                        break
                if gy is None:
                    reasons['no ground'] += 1
                    continue
                base = gy + 1
                if base > yroad + 3 or base < yroad - 1:
                    reasons['ground too high or low'] += 1
                    continue
                cells3 = [(wx_, base + h, wz_) for h in range(3)]
                states = [B.get(*q) for q in cells3]
                if not all(is_open(st) for st in states):
                    reasons['post cells taken'] += 1
                    continue
                if any(B.entity(*q) for q in cells3):
                    reasons['block entity'] += 1
                    continue
                links = [{side: connects(B.get(wx_ + ddx, base + h, wz_ + ddz)) for side, ddx, ddz in
                          (('east', 1, 0), ('west', -1, 0), ('south', 0, 1), ('north', 0, -1))} for h in range(2)]
                if any(sum(lk.values()) >= 3 for lk in links):
                    reasons['post boxed in'] += 1
                    continue
                if any(near_rail(hulls, *q) for q in cells3):
                    reasons['rail clearance'] += 1
                    continue
                if any(guarded(*q) for q in cells3):
                    reasons['protected (lift, city, launch)'] += 1
                    continue
                if (wx_, wz_) in blocked_cols:
                    reasons['other session list'] += 1
                    continue
                if len(ex_xyz) and (np.linalg.norm(ex_xyz - np.array([wx_, base + 2, wz_]), axis=1) < 4).any():
                    reasons['existing sign next to it'] += 1
                    continue
                if any('sign' in (B.entity(wx_ + ddx, base + ddy, wz_ + ddz) or '') for ddx in range(-3, 4) for ddy in range(-1, 5)
                       for ddz in range(-3, 4)):
                    reasons['existing sign next to it'] += 1
                    continue
                # the approaching driver sees the sign face: from 18 blocks back along the approach lane, eye 2 up
                k = int(np.searchsorted(along, min(along[-1], s_ + 18)))
                ez, ex = path[k]
                eye = (ex + X0 + .5 + lx * arm['width'] / 4, yroad + 2.6, ez + Z0 + .5 + lz * arm['width'] / 4)
                if not line_of_sight(eye, (wx_ + .5, base + 2.5, wz_ + .5)):
                    reasons['hidden from the approach'] += 1
                    continue
                fx, fz = t[1], t[0]                                    # the face looks back along the approach
                rot = int(round(math.degrees(math.atan2(-fx, fz)) / 22.5)) % 16
                return dict(pos=[wx_, base + 2, wz_], post=[[wx_, base, wz_], [wx_, base + 1, wz_]], rotation=rot, links=links,
                            states=states, along=round(float(s_), 1), heading=(hx, hz), eye=[round(v, 1) for v in eye],
                            road_y=yroad), None
        return None, dict(reasons)

    def run():
      rows, signs, junctions, skipped = [], [], [], []
      used_cells, used_names = set(), set()
      only = [tuple(float(v) for v in q.split(',')) for q in a.only.split(';')] if a.only else None
      for c in order:
          if len(junctions) >= a.target:
              break
          if only is not None and not any(math.hypot(c['x'] - ox, c['z'] - oz) <= 15 for ox, oz in only):
              continue
          sp = GRID_SPACING if in_grid(c) else SPACING
          if any(math.hypot(c['x'] - o['x'], c['z'] - o['z']) < sp for o in junctions):
              continue
          if c['name'] in used_names:
              c['name'] = None
              p = next((p for p in places if p['name'] == c['here']), None)
              if p and p['kind'] == 'station':
                  dx, dz = c['x'] - p['x'], c['z'] - p['z']
                  side = ('東' if dx > 0 else '西') if abs(dx) > abs(dz) else ('南' if dz > 0 else '北')
                  alt = f"{p['name']}駅{side}口"
                  if alt not in used_names and text_width(alt) <= SIGN_WIDTH:
                      c['name'] = alt
          approaches, misses = [], []
          real = [arm for arm in c['arms'] if arm['real']]
          for arm in real:
              h = (-arm['d'][0], -arm['d'][1])
              lines = []
              others = [o for o in real if o is not arm and o['dest']]
              others.sort(key=lambda o: -o['used'])
              others = others[:3]
              for o in others:
                  ar = arrow(h, o['d'])
                  if all(ar != l[0] for l in lines):
                      lines.append((ar, o['dest'][2], o['dest'][1]))
              if not lines:
                  misses.append(dict(dir=arm['d'], reason='no place to name'))
                  continue
              rank = {'←': 0, '↖': 1, '↑': 2, '↗': 3, '→': 4}
              lines.sort(key=lambda l: rank[l[0]])
              text = [f'{ar} {nm}' for ar, nm, _ in lines]
              front = ([c['name']] if c['name'] else []) + text
              if len(front) <= 2:
                  front = [''] + front
              front = (front + [''] * 4)[:4]
              bad = [t_ for t_ in front if text_width(t_) > SIGN_WIDTH]
              if bad:
                  raise SystemExit(f'line too wide: {bad}')
              spot, why = place_sign(c, arm)
              if spot is None and a.right_fallback:
                  spot, why2 = place_sign(c, arm, -1)
                  if spot is not None:
                      spot['side'] = 'right'
                  else:
                      why = Counter(why) + Counter({f'right: {k}': v for k, v in why2.items()})
              if spot is None:
                  misses.append(dict(dir=arm['d'], reason=max(why, key=why.get) if why else 'no spot', tried=why))
                  continue
              cells3 = [tuple(spot['post'][0]), tuple(spot['post'][1]), tuple(spot['pos'])]
              if any(q in used_cells for q in cells3):
                  misses.append(dict(dir=arm['d'], reason='spot shared with another approach'))
                  continue
              used_cells.update(cells3)
              approaches.append(dict(arm=arm, spot=spot, front=front, lines=lines))
          if len(approaches) < a.min_approaches:
              skipped.append(dict(x=round(c['x']), z=round(c['z']), name=c['name'],
                                  reason=f'only {len(approaches)} approach(es) could take a sign',
                                  misses=[m['reason'] for m in misses]))
              for ap_ in approaches:
                  for q in ap_['spot']['post'] + [ap_['spot']['pos']]:
                      used_cells.discard(tuple(q))
              continue
          if c['name']:
              used_names.add(c['name'])
          jid = f'J{len(junctions) + 1:02d}'
          jrec = dict(id=jid, centre=[round(c['x']), round(c['z'])], name=c['name'], area=c['area'], score=c['score'],
                      approaches=[], missed=[dict(direction_deg=round(math.degrees(math.atan2(m['dir'][1], m['dir'][0]))), reason=m['reason'])
                                             for m in misses])
          for ap_ in approaches:
              spot, arm = ap_['spot'], ap_['arm']
              (x, y, z), (pxz) = spot['pos'], spot['post']
              for q, st, lk in zip(spot['post'], spot['states'][:2], spot['links']):
                  rows.append([q[0], q[1], q[2], st, POST_STATE.format(**{k_: str(v).lower() for k_, v in lk.items()})])
              rows.append([x, y, z, spot['states'][2], SIGN.format(r=spot['rotation'])])
              signs.append(dict(pos=[x, y, z], front=ap_['front'], back=['', '', '', ''], color='white', glow=True))
              fdeg = (spot['rotation'] * 22.5) % 360
              jrec['approaches'].append(dict(
                  arm_direction_deg=round(math.degrees(math.atan2(arm['d'][1], arm['d'][0]))),
                  sign=[x, y, z], post=spot['post'], rotation=spot['rotation'],
                  facing={0: 'S', 1: 'SSW', 2: 'SW', 3: 'WSW', 4: 'W', 5: 'WNW', 6: 'NW', 7: 'NNW', 8: 'N', 9: 'NNE', 10: 'NE',
                          11: 'ENE', 12: 'E', 13: 'ESE', 14: 'SE', 15: 'SSE'}[spot['rotation']],
                  along=spot['along'], road_y=spot['road_y'], driver_eye=spot['eye'], lines=ap_['front'], side=spot.get('side', 'left'),
                  destinations=[dict(arrow=ar, place=nm, road_blocks=d) for ar, nm, d in ap_['lines']]))
          junctions.append(dict(jrec, x=c['x'], z=c['z']))
      return rows, signs, junctions, skipped

    for attempt in range(4):
        rows, signs, junctions, skipped = run()
        hits, lists_used = list_conflicts({tuple(r[:3]) for r in rows}, a.world)
        print('placement pass', attempt + 1, 'signs', len(signs), 'cells touching other lists', len(hits), flush=True)
        if not hits:
            break
        for q, fs in list(hits.items())[:4]:
            print('  ', q, sorted(set(fs))[:2], flush=True)
        blocked_cols.update((x + dx, z + dz) for x, _, z in hits for dx in range(-2, 3) for dz in range(-2, 3))
    else:
        raise SystemExit('cells still touch lists of other sessions after four passes')
    for j in junctions:
        j.pop('x'), j.pop('z')
    (a.out / 's3-rows.json').write_text(json.dumps(rows, ensure_ascii=False), 'utf8')
    (a.out / 's3-signs.json').write_text(json.dumps(signs, ensure_ascii=False, indent=1), 'utf8')
    summary = dict(world=str(a.world), junctions=len(junctions), signs=len(signs), cells=len(rows),
                   by_area=dict(Counter(j['area'] for j in junctions)), virtual_links=nlinks,
                   other_session_lists=lists_used, places=[dict(name=p['name'], x=round(p['x']), z=round(p['z']), weight=p['weight'],
                                                                 snapped=p.get('snapped')) for p in places],
                   skipped=skipped,
                   candidates=[dict(x=round(c['x']), z=round(c['z']), score=c['score'], name=c['name'],
                                    chosen=any(abs(j['centre'][0] - c['x']) < 1 and abs(j['centre'][1] - c['z']) < 1 for j in junctions))
                               for c in order])
    (a.out / 's3-junctions.json').write_text(json.dumps(dict(summary=summary, junctions=junctions), ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps({k: summary[k] for k in ('junctions', 'signs', 'cells', 'by_area', 'virtual_links', 'other_session_lists')}, ensure_ascii=False))
    print('skipped', len(skipped))
    return a, G, C, D, Y, F, places, junctions

if __name__ == '__main__':
    main()
