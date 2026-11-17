"""Recompute the arrows on NERV pyramid / GeoFront wayfinding boards and signs from the current blocks.

Reads a stopped world copy only (never writes into it). Builds a walkable-cell graph for the pyramid and the
GeoFront levels under it from the block states, joins lift landings with lift edges and the HQ train with transit
edges, runs one multi-source Dijkstra per destination, and turns the first straight leg of each board's path (the
furthest path cell walkable in a straight line from the reading spot; the 6 m point when that leg is under 3 m) into
an arrow in the R40/R53 board convention (reader stands on the board's `facing` side; see arrow()).
Doors count as open; platform screen doors, lift landing doors, track ballast and escalator balustrades do not;
escalators are one-way as in the R53 graph (direction=true runs with `facing`); thin panels close the cell side they
sit on; ladders cost 25 per rung.

    . E:/eva-terrain/env.sh; PYTHONIOENCODING=utf-8 $PY tools/plan_nerv_arrows.py --world E:/eva-terrain/world14 \
        --signs <rail-signs-audit>/signs.json --out E:/eva-signs

Writes OUT/p-arrows.json (one entry per arrow row) and OUT/p-landings.json (lift landings and corridor branch points
with no wayfinding board within 8 blocks), plus p-arrows-meta.json. About 30 s on world14; well under 2 GB.
"""
import argparse
import gzip
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

from write_deep_cells import REGION, read_chunk, decode
from write_block_texts import current
import sign_rules as R

# graph box: pyramid, its floors and the GeoFront levels under it, plus the LCL wing and both HQ stations
X0, X1, Z0, Z1, Y0, Y1 = -112, 175, -160, 575, -1240, -400
YL = Y0 - 2                      # flags arrays start two below the lowest feet cell
NY = (Y1 + 3) - YL
PYRAMID = (-90, 150, -1100, -294, 207, 447)
NORMAL = {'north': (0, -1), 'south': (0, 1), 'west': (-1, 0), 'east': (1, 0)}
FEET, LOW, HEAD, SUPPORT, CLIMB, OPTICAL = 1, 2, 4, 8, 16, 32
ARROWS = '←→↑↓'
RUN = 5.0                        # metres of path turned into the arrow
BRANCH_RADIUS = 8

# destination -> lift id for lift destinations (R24 named_lift_landings)
LIFT_A, LIFT_B, LIFT_CMD = 'r25-east-command-gallery', 's20-command-rear-x12-z253-v4', 's23-commander-office-x28-z321-v1'
LIFT_LAKE = 's20-surface-transit-v2'
EXTRA_NAMES = {'总指挥专梯': '司令直通エレベーター', '循阶梯到电梯': 'エレベーター', '机库登机层': 'EVA ケイジ',
               '指挥室入口': '第一発令所', 'LCL 実験室': 'LCL 実験室'}
NON_CANON = {'湖畔电梯': ('湖畔エレベーター (not in the naming table)', 'lift:' + LIFT_LAKE)}


# ---------------------------------------------------------------- block classes

def parse_state(state):
    name, _, rest = state.partition('[')
    props = dict(p.split('=', 1) for p in rest[:-1].split(',')) if rest else {}
    return name, props


def norm_state(state):
    name, props = parse_state(state)
    return name + ('[' + ','.join(f'{k}={props[k]}' for k in sorted(props)) + ']' if props else '')


def free_square(occ, size=5):
    """True when an 8x8 occupancy grid has a free size x size window (a 0.6-wide player fits)."""
    c = np.zeros((9, 9), int)
    c[1:, 1:] = occ.astype(int).cumsum(0).cumsum(1)
    for i in range(9 - size):
        for j in range(9 - size):
            if c[i + size, j + size] - c[i, j + size] - c[i + size, j] + c[i, j] == 0:
                return True
    return False


def occupancy(boxes):
    occ = np.zeros((8, 8), bool)
    g = (np.arange(8) + .5) / 8
    for b in boxes:
        occ |= ((g[:, None] > b[0]) & (g[:, None] < b[3]))[:, :] & ((g[None, :] > b[2]) & (g[None, :] < b[5]))
    return occ


SIDE_N, SIDE_S, SIDE_W, SIDE_E = 1, 2, 4, 8


def edge_sides(boxes, feet):
    """Sides of a passable cell closed by a thin panel along that edge (railings, wall plates, guards). At feet
    height only parts taller than a step count; at head height only parts reaching below 0.8."""
    boxes = [b for b in boxes if (b[4] > .6 if feet else b[1] < .8)]
    if not boxes:
        return 0
    occ = occupancy(boxes)
    m = 0

    def closed(line):
        run = best = 0
        for v in line:
            run = 0 if v else run + 1
            best = max(best, run)
        return best < 5
    if closed(occ[:, 0]):
        m |= SIDE_N
    if closed(occ[:, 7]):
        m |= SIDE_S
    if closed(occ[0, :]):
        m |= SIDE_W
    if closed(occ[7, :]):
        m |= SIDE_E
    return m


def from_boxes(boxes):
    if not boxes:
        return FEET | HEAD
    f = 0
    feet = free_square(occupancy(boxes))
    if feet:
        f |= FEET
    head = [b for b in boxes if b[1] < .8]
    if not head or free_square(occupancy(head)):
        f |= HEAD
    top = max(b[4] for b in boxes)
    if not feet and top <= .5626:
        f |= LOW
    if .85 <= top <= 1.01:
        high = [b for b in boxes if b[4] >= .85]
        if occupancy(high).mean() >= .5:
            f |= SUPPORT
    return f


PASS_WORDS = ('sign', 'banner', 'torch', 'button', 'lever', 'pressure_plate', 'rail', 'redstone_wire', 'tripwire',
              'sapling', 'flower', 'tulip', 'grass', 'fern', 'dandelion', 'poppy', 'orchid', 'allium', 'bluet', 'daisy',
              'cornflower', 'lily_of_the_valley', 'carpet', 'mushroom', 'dead_bush', 'string', 'cobweb', 'kelp',
              'seagrass', 'lichen', 'roots', 'sprouts', 'coral_fan', 'frame', 'rose', 'peony', 'lilac', 'sunflower')


def classify(state, shapes, unknown):
    name, props = parse_state(state)
    ns, base = name.split(':', 1)
    if base in ('air', 'cave_air', 'void_air', 'light', 'structure_void', 'water', 'bubble_column', 'moving_piston'):
        return FEET | HEAD | OPTICAL
    if base in ('lava', 'fire', 'soul_fire', 'powder_snow'):
        return 0
    if base in ('ladder', 'vine', 'twisting_vines', 'twisting_vines_plant', 'weeping_vines', 'weeping_vines_plant'):
        return FEET | HEAD | CLIMB | OPTICAL
    if base == 'scaffolding':
        return FEET | HEAD | CLIMB | SUPPORT | OPTICAL
    if base.startswith(('apg_', 'psd_')) or base.startswith('lift_door_interlock'):
        return OPTICAL                         # platform screen doors and lift landing doors stay shut
    if ('door' in base and 'trapdoor' not in base) or 'fence_gate' in base:
        return FEET | HEAD | OPTICAL          # doors count as passable (cards and switches are not modelled)
    if 'trapdoor' in base:
        if props.get('open') == 'true':
            return FEET | HEAD | OPTICAL
        return LOW if props.get('half') == 'bottom' else HEAD | SUPPORT
    if base.endswith('_slab') or base == 'slab':
        t = props.get('type', 'double')
        return LOW if t == 'bottom' else SUPPORT
    if 'escalator_side' in base:
        return OPTICAL                         # balustrade: never walked on
    if 'escalator_step' in base:
        return SUPPORT if props.get('orientation', 'flat') in ('flat', 'landing_top', 'landing_bottom') else LOW
    if base.endswith('_stairs'):
        return LOW
    if ns == 'minecraft':
        if base.endswith('_fence') or base.endswith('_wall') or base == 'iron_bars' or base.endswith('glass_pane') \
                or base == 'glass_pane' or base == 'chain':
            return OPTICAL
        if 'glass' in base:
            return SUPPORT | OPTICAL
        if base == 'barrier':
            return SUPPORT | OPTICAL
        if base == 'gravel':
            return 0                           # track ballast: walking along the tunnels is not a route
        if base.endswith('leaves'):
            return SUPPORT
        if any(w in base for w in PASS_WORDS) and 'stone' not in base and 'block' not in base:
            return FEET | HEAD | OPTICAL
        if base.startswith('snow') and base == 'snow':
            return LOW if int(props.get('layers', 1)) <= 4 else SUPPORT
    key = norm_state(state)
    if key in shapes:
        f = from_boxes(shapes[key])
        if 'glass' in base or 'window' in base:
            f |= OPTICAL
        if f & FEET:
            f |= OPTICAL
        return f
    if 'escalator_side' in base or 'railing' in base or 'fence' in base:
        unknown[name] += 1
        return OPTICAL
    if 'glass' in base or 'window' in base:
        unknown[name] += 1
        return SUPPORT | OPTICAL
    if ns != 'minecraft':
        unknown[name] += 1
    return SUPPORT


# ---------------------------------------------------------------- world reading

class World:
    """Per-chunk flag columns (y YL..YL+NY) for the graph box, kept for line-of-sight checks."""

    def __init__(self, world, shapes):
        self.world = Path(world)
        self.shapes = shapes
        self.cache = {}
        self.unknown = Counter()
        self.cols = {}
        self.regions = {}
        self.side_cache = {}
        self.sides = {}
        self.esc = {}                          # escalator step cell -> flow (dx, dz)

    def flags_of(self, state):
        f = self.cache.get(state)
        if f is None:
            f = self.cache[state] = classify(state, self.shapes, self.unknown)
        return f

    def sides_of(self, state):
        s = self.side_cache.get(state)
        if s is None:
            boxes = self.shapes.get(norm_state(state))
            base = parse_state(state)[0].split(':', 1)[1]
            if not boxes or not self.flags_of(state) & (FEET | HEAD) or 'door' in base or 'gate' in base:
                s = 0
            else:                                  # low nibble: sides at feet height, high nibble: at head height
                s = (edge_sides(boxes, True) if self.flags_of(state) & FEET else 0xF) | (edge_sides(boxes, False) << 4)
            self.side_cache[state] = s
        return s

    def region(self, rx, rz):
        if (rx, rz) not in self.regions:
            p = self.world / REGION / f'r.{rx}.{rz}.mca'
            self.regions[rx, rz] = p.read_bytes() if p.exists() else None
        return self.regions[rx, rz]

    def load_chunk(self, cx, cz):
        buf = self.region(cx >> 5, cz >> 5)
        col = np.zeros((NY, 16, 16), np.uint8)
        sd = np.zeros((NY, 16, 16), np.uint8)
        self.sides[cx, cz] = sd
        if buf is None:
            return col
        try:
            root = read_chunk(buf, cx, cz)[3]
        except ValueError:
            return col
        air = self.flags_of('minecraft:air')
        col[:] = air
        for s in root['sections']:
            sy = int(s['Y']) * 16
            if sy + 16 <= YL or sy >= YL + NY or 'block_states' not in s:
                continue
            ids, palette = decode(s['block_states'])
            lut = np.array([self.flags_of(p) for p in palette], np.uint8)
            slut = np.array([self.sides_of(p) for p in palette], np.uint8)
            for pi, p in enumerate(palette):
                if 'escalator_step' in p:
                    name, props = parse_state(p)
                    fx, fz = NORMAL.get(props.get('facing'), (0, 0))
                    if props.get('direction') == 'false':          # R53 graph: false runs against facing
                        fx, fz = -fx, -fz
                    for i in np.nonzero(ids == pi)[0]:
                        y, z, x = i >> 8, (i >> 4) & 15, i & 15
                        self.esc[cx * 16 + int(x), sy + int(y), cz * 16 + int(z)] = (fx, fz)
            block = lut[ids].reshape(16, 16, 16)            # [y, z, x]
            a, b = max(sy, YL), min(sy + 16, YL + NY)
            col[a - YL:b - YL] = block[a - sy:b - sy]
            if slut.any():
                sd[a - YL:b - YL] = slut[ids].reshape(16, 16, 16)[a - sy:b - sy]
        return col

    def load_box(self):
        for cx in range(X0 >> 4, (X1 >> 4) + 1):
            for cz in range(Z0 >> 4, (Z1 >> 4) + 1):
                self.cols[cx, cz] = self.load_chunk(cx, cz)

    def flag(self, x, y, z):
        col = self.cols.get((x >> 4, z >> 4))
        if col is None or not (YL <= y < YL + NY):
            return None
        return int(col[y - YL, z & 15, x & 15])


def key_of(x, y, z):
    return ((np.int64(x) + 4096) * 8192 + (np.int64(z) + 4096)) * 4096 + (np.int64(y) + 2048)


def walkable_cells(w):
    """Feet cells: head clear and (standing on support, inside a climbable, or on a low block with headroom)."""
    xs, ys, zs, h2s, climbs, sides = [], [], [], [], [], []
    for (cx, cz), F in w.cols.items():
        S = w.sides[cx, cz]
        cur, up, below = F[2:NY - 2], F[3:NY - 1], F[1:NY - 3]
        up2 = F[4:NY]
        walk = ((up & HEAD) > 0) & ((((cur & FEET) > 0) & ((below & SUPPORT) > 0)) | ((cur & CLIMB) > 0) |
                                    (((cur & LOW) > 0) & ((up & FEET) > 0) & ((up2 & HEAD) > 0)))
        iy, iz, ix = np.nonzero(walk)
        x0, z0 = cx * 16, cz * 16
        keep = (x0 + ix >= X0) & (x0 + ix <= X1) & (z0 + iz >= Z0) & (z0 + iz <= Z1) & (iy + YL + 2 <= Y1)
        iy, iz, ix = iy[keep], iz[keep], ix[keep]
        xs.append(x0 + ix)
        zs.append(z0 + iz)
        ys.append(iy + YL + 2)
        h2s.append((up2[iy, iz, ix] & HEAD) > 0)
        climbs.append((cur[iy, iz, ix] & CLIMB) > 0)
        low = (cur[iy, iz, ix] & LOW) > 0
        feet_s = np.where(low, S[iy + 3, iz, ix], S[iy + 2, iz, ix]) & 15
        head_s = np.where(low, S[iy + 4, iz, ix], S[iy + 3, iz, ix]) >> 4
        sides.append(feet_s | head_s)
    c = np.stack([np.concatenate(xs), np.concatenate(ys), np.concatenate(zs)], 1).astype(np.int64)
    h2 = np.concatenate(h2s)
    cl = np.concatenate(climbs)
    sd = np.concatenate(sides)
    k = key_of(c[:, 0], c[:, 1], c[:, 2])
    order = np.argsort(k)
    return c[order], k[order], h2[order], cl[order], sd[order]


def lookup(K, keys):
    i = np.searchsorted(K, keys)
    i = np.minimum(i, len(K) - 1)
    return np.where(K[i] == keys, i, -1)


OUT_SIDE = {(1, 0): (SIDE_E, SIDE_W), (-1, 0): (SIDE_W, SIDE_E), (0, 1): (SIDE_S, SIDE_N), (0, -1): (SIDE_N, SIDE_S)}


def open_between(sd, i, j, dx, dz):
    """Neither cell has a panel on the shared edge (j < 0 means no cell)."""
    a, b = OUT_SIDE[dx, dz]
    jj = np.maximum(j, 0)
    return (j >= 0) & ((sd[i] & a) == 0) & ((sd[jj] & b) == 0)


def build_edges(c, K, h2, cl, sd):
    rows, cols, wts = [], [], []
    x, y, z = c[:, 0], c[:, 1], c[:, 2]
    allc = np.arange(len(c))
    for dx, dz in ((1, 0), (0, 1)):
        for dy in (0, 1, -1):
            j = lookup(K, key_of(x + dx, y + dy, z + dz))
            ok = open_between(sd, allc, j, dx, dz)
            if dy == 1:
                ok &= h2                       # rising a block needs headroom over the lower cell
            elif dy == -1:
                ok &= np.where(j >= 0, h2[np.maximum(j, 0)], False)
            i = np.nonzero(ok)[0]
            rows.append(i); cols.append(j[i]); wts.append(np.full(len(i), 1.0 if dy == 0 else 1.4))
    for dx, dz in ((1, 1), (1, -1)):
        j = lookup(K, key_of(x + dx, y, z + dz))
        a = lookup(K, key_of(x + dx, y, z))
        b = lookup(K, key_of(x, y, z + dz))
        ok = (j >= 0) & open_between(sd, allc, a, dx, 0) & open_between(sd, allc, b, 0, dz)
        ok &= open_between(sd, np.maximum(a, 0), j, 0, dz) & open_between(sd, np.maximum(b, 0), j, dx, 0)
        i = np.nonzero(ok)[0]
        rows.append(i); cols.append(j[i]); wts.append(np.full(len(i), math.sqrt(2)))
    j = lookup(K, key_of(x, y + 1, z))
    i = np.nonzero((j >= 0) & (cl | np.where(j >= 0, cl[np.maximum(j, 0)], False)))[0]
    rows.append(i); cols.append(j[i]); wts.append(np.full(len(i), 25.0))    # ladders only where nothing else leads
    return np.concatenate(rows), np.concatenate(cols), np.concatenate(wts)


def flows(w, c):
    """Escalator flow under each walkable cell (step below the feet, or at the feet for a sloped step)."""
    f = np.zeros((len(c), 2), np.int8)
    if not w.esc:
        return f
    ek = np.array([key_of(x, y, z) for x, y, z in w.esc], np.int64)
    ev = np.array(list(w.esc.values()), np.int8)
    order = np.argsort(ek)
    ek, ev = ek[order], ev[order]
    for dy in (1, 0):
        j = lookup(ek, key_of(c[:, 0], c[:, 1] - dy, c[:, 2]))
        hit = (j >= 0) & (f == 0).all(1)
        f[hit] = ev[j[hit]]
    return f


def directed(c, fl, r, q, wt):
    """Both directions of each walking pair, minus moves against a running escalator (as the R53 graph does)."""
    d = c[q] - c[r]
    fwd = np.ones(len(r), bool)
    back = np.ones(len(r), bool)
    for f in (fl[r], fl[q]):
        along = d[:, 0] * f[:, 0] + d[:, 2] * f[:, 1]
        fwd &= along >= 0
        back &= along <= 0
    return (np.concatenate([r[fwd], q[back]]), np.concatenate([q[fwd], r[back]]),
            np.concatenate([wt[fwd], wt[back]]))


def snap(c, K, p, radius=3):
    """Nearest walkable cell to p (same height first, then +-1)."""
    best = None
    for dy in (0, -1, 1, -2, 2):
        for r in range(radius + 1):
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if max(abs(dx), abs(dz)) != r:
                        continue
                    j = lookup(K, np.array([key_of(p[0] + dx, p[1] + dy, p[2] + dz)]))[0]
                    if j >= 0:
                        d = math.hypot(dx, dz) + abs(dy) * 1.5
                        if best is None or d < best[0]:
                            best = (d, int(j))
            if best is not None:
                return best[1]
    return None


# ---------------------------------------------------------------- arrows

def arrow(d, face):
    """R53 refresh_r53_pyramid_signs.direction(): reader stands on the facing side and looks into the board."""
    nx, nz = NORMAL[face]
    right = d[0] * nz - d[2] * nx
    forward = -d[0] * nx - d[2] * nz
    if right == 0 and forward == 0:
        return '●'
    return '→' if right > abs(forward) else '←' if -right > abs(forward) else '↑' if forward > 0 else '↓'


def trace(c, pred, start, run):
    pts = [start]
    cur, h, special = start, 0.0, None
    while h < run:
        nxt = pred[cur]
        if nxt < 0:
            break
        d = c[nxt] - c[cur]
        hd = math.hypot(d[0], d[2])
        if abs(d[1]) > 1 or hd > 1.5:
            special = 'lift_or_train'
            break
        h += hd
        cur = nxt
        pts.append(cur)
    return pts, h, special


def visible(K, a, b, ylo, yhi):
    """Straight walk from a to b stays on walkable cells (a 0.6-wide body, heights ylo..yhi)."""
    d = np.array([b[0] - a[0], b[2] - a[2]], float)
    n = np.linalg.norm(d)
    if n == 0:
        return True
    side = np.array([-d[1], d[0]]) / n * .3
    ts = np.linspace(0, 1, max(2, int(n * 4) + 1))
    pts = np.concatenate([np.array([a[0] + .5, a[2] + .5]) + ts[:, None] * d + s * side for s in (-1, 0, 1)])
    cells = np.unique(np.floor(pts).astype(np.int64), axis=0)
    ok = np.zeros(len(cells), bool)
    for y in range(ylo, yhi + 1):
        ok |= lookup(K, key_of(cells[:, 0], y, cells[:, 1])) >= 0
    return bool(ok.all())


def first_leg(c, K, pred, start, cap=60):
    """End of the first taut-string leg of the path: the furthest path cell reachable in a straight line from the
    reader before the first corner, lift or train. Returns (cell index, leg length, special)."""
    a = c[start]
    cur, best, special = start, start, None
    ys = [int(a[1])]
    for _ in range(cap):
        nxt = pred[cur]
        if nxt < 0:
            break
        d = c[nxt] - c[cur]
        if abs(d[1]) > 1 or math.hypot(d[0], d[2]) > 1.5:
            special = 'lift_or_train'
            break
        cur = nxt
        ys.append(int(c[cur, 1]))
        if not visible(K, a, c[cur], min(ys) - 1, max(ys) + 1):
            break
        best = cur
    b = c[best]
    return best, round(math.hypot(b[0] - a[0], b[2] - a[2]), 1), special


def path_length(c, pred, start, limit=20000):
    cur, n, total = start, 0, 0.0
    while n < limit:
        nxt = pred[cur]
        if nxt < 0:
            break
        d = c[nxt] - c[cur]
        if abs(d[1]) <= 1 and math.hypot(d[0], d[2]) <= 1.5:
            total += math.sqrt(d[0] ** 2 + d[2] ** 2 + d[1] ** 2)
        cur, n = nxt, n + 1
    return round(total, 1)


# ---------------------------------------------------------------- boards

def sign_facing(name, props):
    if 'facing' in props:
        return props['facing']
    if 'rotation' in props:
        r = int(props['rotation']) % 16
        return ['south', 'west', 'north', 'east'][((r + 2) // 4) % 4]
    return None


def destination(name):
    """(canonical name, target key) for a row's destination text, or (None, None)."""
    name = re.sub(r'\s*·\s*(经楼梯|直梯|梯)$', '', name.strip())
    if name in NON_CANON:
        return NON_CANON[name]
    first = name.split('  ')[0]
    for cand in (name, first, EXTRA_NAMES.get(name), EXTRA_NAMES.get(first)):
        if not cand:
            continue
        p = R.place(cand)
        if p is None:
            for variants, names in R.NERV_PLACES:
                if cand == names[0]:
                    p = names
        if p:
            return p[0], p[0]
    return None, None


def read_boards(world, signs_path):
    s = json.loads(Path(signs_path).read_text('utf8'))
    wanted = [e for e in s if e.get('area') in ('pyramid', 'geofront')]
    out = []
    for e in wanted:
        x, y, z = e['x'], e['y'], e['z']
        buf = world.region(x >> 9, z >> 9)
        root = read_chunk(buf, x >> 4, z >> 4)[3]
        ent = next((b for b in root.get('block_entities', []) if (int(b['x']), int(b['y']), int(b['z'])) == (x, y, z)), None)
        if ent is None:
            continue
        sec = next((q for q in root['sections'] if int(q['Y']) == y >> 4 and 'block_states' in q), None)
        ids, pal = decode(sec['block_states'])
        state = pal[ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]]
        name, props = parse_state(state)
        eid = str(ent['id'])
        if eid.endswith('sign'):
            cur = current(ent, 'sign')
            face = sign_facing(name, props)
            sides = [('front', face, cur['front'])]
            if face:
                back = {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}[face]
                sides.append(('back', back, cur['back']))
            out.append(dict(pos=(x, y, z), block=name, kind='sign', area=e['area'], text_h=.5, sides=sides))
        elif eid == 'projectseele:station_departure_board' and int(ent.get('Wayfinding', 0)):
            cur = current(ent, 'board')
            face = props.get('facing')
            compact = name == 'projectseele:nerv_direction_panel'
            rows = [cur[k] for k in ('Row0', 'Row1', 'Row2')]
            sides = [('front', face, rows)]
            rear = [str(r) for r in ent.get('RearRowsR47', [])]
            if not compact and rear and face:
                back = {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}[face]
                sides.append(('rear', back, rear))
            out.append(dict(pos=(x, y, z), block=name, kind='board', area=e['area'], text_h=.8 if compact else 1.73,
                            sides=sides, station=cur['Station'], route=cur['Route'], map='MapRows' in ent))
    return out


def los(w, eye, target, own):
    a, b = np.array(eye, float), np.array(target, float)
    n = max(2, int(np.linalg.norm(b - a) * 5))
    for t in np.linspace(0, 1, n)[1:-1]:
        p = a + (b - a) * t
        q = (int(math.floor(p[0])), int(math.floor(p[1])), int(math.floor(p[2])))
        if q == own:
            continue
        f = w.flag(*q)
        if f is None or not (f & (FEET | OPTICAL)):
            return False
    return True


def reader(w, c, K, size, pos, face, text_h):
    nx, nz = NORMAL[face]
    qx, qy, qz = pos
    target = (qx + .5 + nx * .45, qy + text_h, qz + .5 + nz * .45)
    cand = []
    for fwd in range(1, 7):
        for lat in range(-3, 4):
            x, z = qx + nx * fwd + nz * lat, qz + nz * fwd - nx * lat
            for y in range(qy - 4, qy + 3):
                cand.append((x, y, z, fwd, lat))
    keys = np.array([key_of(x, y, z) for x, y, z, _, _ in cand])
    j = lookup(K, keys)
    scored = []
    for (x, y, z, fwd, lat), jj in zip(cand, j):
        if jj < 0 or size[jj] < 30:            # pockets (door planes, sealed niches) are not reading spots
            continue
        dv = target[1] - (y + 1.62)
        if not (-2.5 <= dv <= 3.5):
            continue
        scored.append((abs(fwd - 2.5) + abs(lat) + abs(dv) * .7, int(jj), (x + .5, y + 1.62, z + .5)))
    scored.sort()
    for s, jj, eye in scored:
        if los(w, eye, target, pos):
            return jj, True
    return (scored[0][1], False) if scored else (None, False)


# ---------------------------------------------------------------- branch points

def floor_label(y):
    names = {-554: 'B1 交通接驳层', -541: '1F 总部门厅', -535: '湖畔电梯接驳层', -527: '2F 勤务联络层', -516: '主指挥台',
             -513: '3F 科研联络层', -512: '指挥后方勤务层', -502: '指挥室观察廊', -499: '4F 作战指挥层',
             -485: '5F 指挥室上层', -481: '总指挥联络厅', -471: '6F 上部办公层', -457: '7F 上部观察层',
             -433: '总指挥会客厅', -1230: '终极教条层', -1030: '发射区检修廊', -1014: '机库登机层', -987: '机库上层观察廊',
             -468: 'LCL 同步实验层', -442: '原机库站接驳层', -559: '总部车站层'}
    k = min(names, key=lambda h: abs(h - y))
    return names[k] if abs(k - y) <= 2 else f'Y={y}'


def runs(a, axis):
    """Length of the run of True cells through each cell along an axis (0 elsewhere)."""
    a = np.moveaxis(a, axis, 0)
    out = np.zeros(a.shape, int)
    start = np.zeros(a.shape[1:], int)
    for i in range(a.shape[0]):
        start = np.where(a[i], start, i + 1)
        out[i] = np.where(a[i], i - start + 1, 0)
    for i in range(a.shape[0] - 2, -1, -1):          # spread each run's full length back over the run
        out[i] = np.where(a[i] & a[i + 1], out[i + 1], out[i])
    return np.moveaxis(out, 0, axis)


def branch_points(c, K, floors, box, long_=8, narrow=5):
    """Corridor junctions: crossing cells (long runs both ways) with a narrow x-corridor beside them along x and a
    narrow z-corridor beside them along z. One point per connected junction patch."""
    from scipy.ndimage import label, binary_dilation
    x0, x1, z0, z1 = box
    out = []
    for y in floors:
        sel = (np.abs(c[:, 1] - y) <= 1) & (c[:, 0] >= x0) & (c[:, 0] <= x1) & (c[:, 2] >= z0) & (c[:, 2] <= z1)
        if not sel.any():
            continue
        g = np.zeros((x1 - x0 + 1, z1 - z0 + 1), bool)
        g[c[sel, 0] - x0, c[sel, 2] - z0] = True
        rx, rz = runs(g, 0), runs(g, 1)
        cor_x = (rx >= long_) & (rz <= narrow) & g
        cor_z = (rz >= long_) & (rx <= narrow) & g
        cross = (rx >= long_) & (rz >= long_) & g
        near_x = binary_dilation(cor_x, np.ones((7, 1), bool))
        near_z = binary_dilation(cor_z, np.ones((1, 7), bool))
        hit = cross & near_x & near_z
        lab, n = label(hit, np.ones((3, 3), bool))
        for k in range(1, n + 1):
            ii, kk = np.nonzero(lab == k)
            p = (int(round(ii.mean())) + x0, y, int(round(kk.mean())) + z0)
            j = snap(c, K, p, 2)
            if j is not None:
                out.append(tuple(int(v) for v in c[j]))
    kept = []
    for p in sorted(set(out)):
        if not any(abs(p[0] - q[0]) <= 3 and abs(p[2] - q[2]) <= 3 and abs(p[1] - q[1]) <= 2 for q in kept):
            kept.append(p)
    return kept


def wall_spot(w, c, K, p):
    """Nearest wall cell at eye height next to the walkway around p, the side it faces, and whether it is glass."""
    best = None
    for r in range(1, 9):
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if max(abs(dx), abs(dz)) != r:
                    continue
                x, z = p[0] + dx, p[2] + dz
                f1 = w.flag(x, p[1] + 1, z)
                if f1 is None or f1 & FEET or not f1 & (SUPPORT | OPTICAL):
                    continue
                for face, (nx, nz) in NORMAL.items():
                    if lookup(K, np.array([key_of(x + nx, p[1], z + nz)]))[0] >= 0:
                        d = math.hypot(x + nx - p[0], z + nz - p[2]) + (3 if f1 & OPTICAL else 0)
                        if best is None or d < best[0]:
                            best = (d, [x, p[1] + 1, z], face, bool(f1 & OPTICAL))
        if best and best[0] <= r + 1:
            break
    return (best[1], best[2], best[3]) if best else (None, None, None)


# ---------------------------------------------------------------- main

def build(world, t0):
    """Walkable graph, lift/train links and one shortest-path tree per destination."""
    shapes = {norm_state(k): v for k, v in json.loads((world / 'native_collision_shapes.json').read_text('utf8')).items()}
    w = World(world, shapes)
    w.load_box()
    t_load = time.time() - t0
    c, K, h2, cl, sd = walkable_cells(w)
    r, q, wt = build_edges(c, K, h2, cl, sd)
    fl = flows(w, c)
    r, q, wt = directed(c, fl, r, q, wt)
    N = len(c)
    print(f'walkable cells {N}, walking edges {len(r)}, load {t_load:.0f}s', flush=True)

    g = json.loads(gzip.decompress((world / 'nerv_routes_r24.json.gz').read_bytes()))
    nodes = g['nodes']
    lifts = defaultdict(list)
    landing_rows = []
    for row in g['named_lift_landings']:
        j = snap(c, K, row['actual'])
        landing_rows.append(dict(lift_id=row['lift_id'], label=row['label'], actual=row['actual'],
                                 restricted=row['restricted'], cell=None if j is None else c[j].tolist()))
        if j is not None:
            lifts[row['lift_id']].append(j)
    extra_r, extra_q, extra_w = [], [], []
    for lid, js in lifts.items():
        for i1 in range(len(js)):
            for i2 in range(i1 + 1, len(js)):
                cost = 20 + abs(int(c[js[i1], 1] - c[js[i2], 1])) * .05
                extra_r += [js[i1], js[i2]]; extra_q += [js[i2], js[i1]]; extra_w += [cost, cost]
    transit = []
    for e in g.get('transport_edges', []):
        a1, b1 = snap(c, K, nodes[e['from']][:3]), snap(c, K, nodes[e['to']][:3])
        if a1 is not None and b1 is not None:
            extra_r.append(a1); extra_q.append(b1); extra_w.append(120.0)
            transit.append(dict(line=e['line'], a=c[a1].tolist(), b=c[b1].tolist()))
    # transposed: a tree grown from the destination over reversed edges gives each cell its next step towards it
    walk_m = coo_matrix((wt, (q, r)), shape=(N, N)).tocsr()
    full_m = coo_matrix((np.concatenate([wt, extra_w]), (np.concatenate([q, extra_q]), np.concatenate([r, extra_r]))),
                        shape=(N, N)).tocsr()
    del r, q, wt

    goals = {gg['id']: gg for gg in g['goals']}
    targets = {}
    missing = {}

    def goal_cell(gid):
        j = snap(c, K, goals[gid]['actual'])
        if j is None:
            missing[gid] = goals[gid]['actual']
        return [] if j is None else [j]
    targets['第一発令所'] = (goal_cell('command'), full_m)
    targets['本部駅'] = (goal_cell('station'), full_m)
    targets['EVA ケイジ'] = (goal_cell('hangars'), full_m)
    targets['LCL 実験室'] = (goal_cell('experiment'), full_m)
    targets['A号エレベーター'] = (lifts.get(LIFT_A, []), full_m)
    targets['B号エレベーター'] = (lifts.get(LIFT_B, []), full_m)
    targets['司令直通エレベーター'] = (lifts.get(LIFT_CMD, []), full_m)
    targets['lift:' + LIFT_LAKE] = (lifts.get(LIFT_LAKE, []), full_m)
    targets['エレベーター'] = (sorted({j for js in lifts.values() for j in js}), walk_m)
    preds = {}
    dists = {}
    for name, (src, m) in targets.items():
        if not src:
            continue
        d, p, _ = dijkstra(m, directed=True, indices=src, min_only=True, return_predecessors=True)
        preds[name], dists[name] = p, d
    print(f'dijkstra done {time.time() - t0:.0f}s', flush=True)
    _, lab = connected_components(full_m, directed=True, connection='weak')
    size = np.bincount(lab)[lab]
    return dict(w=w, c=c, K=K, size=size, preds=preds, dists=dists, landing_rows=landing_rows, missing=missing, transit=transit)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--signs', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    t0 = time.time()
    G = build(a.world, t0)
    w, c, K, preds, dists = G['w'], G['c'], G['K'], G['preds'], G['dists']
    landing_rows, missing, transit = G['landing_rows'], G['missing'], G['transit']
    N = len(c)
    boards = read_boards(w, a.signs)
    entries = []
    reader_cache = {}
    for b in boards:
        x, y, z = b['pos']
        for side, face, rows in b['sides']:
            for ri, row in enumerate(rows):
                if not row or not re.search(f'[{ARROWS}]', row):
                    continue
                old = re.search(f'[{ARROWS}]', row).group(0)
                dest_text = re.sub(f'[{ARROWS}●]', '', row).strip()
                canon, tkey = destination(dest_text)
                e = dict(pos=[x, y, z], block=b['block'], kind=b['kind'], area=b['area'], side=side, facing=face,
                         row=ri, text=row, destination=canon, old_arrow=old, new_arrow=None, path_length=None)
                if b['kind'] == 'board':
                    e['station'] = b['station']
                if not (X0 <= x <= X1 and Z0 <= z <= Z1 and Y0 <= y <= Y1 + 8):
                    e['status'] = 'no-destination' if canon is None else 'unreachable'
                    e['note'] = 'outside the graph box'
                    entries.append(e); continue
                if canon is None:
                    e['status'] = 'no-destination'
                    entries.append(e); continue
                if face not in NORMAL:
                    e['status'] = 'unreachable'; e['note'] = 'no facing'
                    entries.append(e); continue
                if (b['pos'], face) not in reader_cache:
                    reader_cache[b['pos'], face] = reader(w, c, K, G['size'], b['pos'], face, b['text_h'])
                ri_, clear = reader_cache[b['pos'], face]
                if ri_ is None:
                    e['status'] = 'unreachable'; e['note'] = 'no walkable reading cell in front of the face'
                    entries.append(e); continue
                e['reader'] = c[ri_].tolist()
                if not clear:
                    e['note'] = 'reading cell has no clear sight line (glass or fittings); nearest used'
                if tkey not in preds or not np.isfinite(dists[tkey][ri_]):
                    e['status'] = 'unreachable'
                    if tkey not in preds:
                        e['note'] = 'destination cell not found in current blocks'
                    entries.append(e); continue
                p = preds[tkey]
                end, leg, special = first_leg(c, K, p, ri_)
                pts, _, _ = trace(c, p, ri_, RUN)
                if leg < 3 and not (special and end == ri_):
                    # the reader stands right at a corner: the corridor beyond it carries the direction
                    long_pts, _, _ = trace(c, p, ri_, 6.0)
                    end = long_pts[-1]
                    e['note'] = (e.get('note', '') + '; ' if e.get('note') else '') + f'corner within {leg} m, 6 m point used'
                new = arrow(c[end] - c[ri_], face)
                dv = c[end] - c[ri_]
                nx_, nz_ = NORMAL[face]
                rt, fw = dv[0] * nz_ - dv[2] * nx_, -dv[0] * nx_ - dv[2] * nz_
                ang = math.degrees(math.atan2(abs(rt), abs(fw))) if (rt or fw) else 0.0
                e['leg_right_forward'] = [int(rt), int(fw)]
                if 35 <= ang <= 55:
                    e['diagonal'] = True       # first leg within 10 degrees of the diagonal: either arrow reads
                e['new_arrow'] = new
                e['arrow_5m_path'] = arrow(c[pts[-1]] - c[pts[0]], face)
                e['path_length'] = path_length(c, p, ri_)
                e['first_leg'] = [c[ri_].tolist(), c[end].tolist(), leg]
                if special and end == ri_:
                    e['note'] = (e.get('note', '') + '; ' if e.get('note') else '') + 'reader stands at the lift/train: ride first'
                e['status'] = 'same' if new == old else 'changed'
                entries.append(e)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'p-arrows.json').write_text(json.dumps(entries, ensure_ascii=False, indent=1), 'utf8')

    # landings and branch points without a board within 8 blocks
    board_pos = np.array([b['pos'] for b in boards if b['kind'] == 'board'] or [[0, 0, 0]])
    floors = sorted({row['cell'][1] for row in landing_rows if row['cell']} |
                    {int(c[v[0], 1]) for v in reader_cache.values() if v[0] is not None})
    cands = [dict(type='lift_landing', lift_id=row['lift_id'], label=row['label'], cell=row['cell'])
             for row in landing_rows if row['cell']]
    # public routes: every reader and every lift landing to every destination; junctions off these routes
    # (aisles inside store rooms, office rows) are not wayfinding points
    sources = sorted({v[0] for v in reader_cache.values() if v[0] is not None} |
                     {j for row in landing_rows if row['cell'] for j in [snap(c, K, row['cell'], 0)] if j is not None})
    on_route = set()
    for tkey, p in preds.items():
        for sidx in sources:
            cur, n = sidx, 0
            while cur >= 0 and n < 3000 and np.isfinite(dists[tkey][sidx]):
                on_route.add(int(cur))
                cur, n = p[cur], n + 1
    rk = np.array(sorted(K[i] for i in on_route), np.int64)
    for p in branch_points(c, K, floors, (PYRAMID[0] - 30, PYRAMID[1] + 30, PYRAMID[4] - 160, PYRAMID[5] + 30)):
        near_route = any(lookup(rk, np.array([key_of(p[0] + dx, p[1] + dy, p[2] + dz)]))[0] >= 0
                         for dx in range(-2, 3) for dz in range(-2, 3) for dy in (-1, 0, 1))
        if near_route:
            cands.append(dict(type='corridor_branch', cell=list(p)))
    landings = []
    for cd in cands:
        p = np.array(cd['cell'])
        dd = np.abs(board_pos - p)
        near = (np.maximum(dd[:, 0], dd[:, 2]) <= BRANCH_RADIUS) & (dd[:, 1] <= 4)
        if near.any():
            continue
        spot, face, glass = wall_spot(w, c, K, cd['cell'])
        cd.update(floor=floor_label(int(p[1])), wall_cell=spot, board_facing=face, wall_is_glass=glass,
                  in_pyramid_box=bool(PYRAMID[0] <= p[0] <= PYRAMID[1] and PYRAMID[4] <= p[2] <= PYRAMID[5]))
        landings.append(cd)
    (a.out / 'p-landings.json').write_text(json.dumps(landings, ensure_ascii=False, indent=1), 'utf8')

    st = Counter(e['status'] for e in entries)
    meta = dict(cells=N, seconds=round(time.time() - t0), statuses=st, missing_goals=missing, transit=transit,
                lift_landings_snapped=sum(1 for row in landing_rows if row['cell']), landings_total=len(landing_rows),
                unknown_states=w.unknown.most_common(40), landing_candidates=len(cands), unsigned=len(landings))
    (a.out / 'p-arrows-meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(meta, ensure_ascii=False)[:3000])


if __name__ == '__main__':
    main()
