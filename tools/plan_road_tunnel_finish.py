"""Finish a raw road tunnel: ease its approach ramp, raise thin headroom, line it with stone bricks, light it
and give its mouth a portal face.

The road is flooded from a seed over TrafficCraft paving (steps of at most one block) inside the box. Its main
axis comes from the roofed cells (a column is roofed when something solid stands within 40 blocks over the
road). Positions along the road are t (along the axis) and w (across it).
  ramp:     between t0 and the point where a line rising at GRADE from the paving height at t0 meets the old
            paving, every paved column is lowered to that line (never raised); its surface type stays
            (asphalt or concrete), the old deck goes and the cut is cleared to the new height.
  headroom: roofed columns get clear space up to HEAD blocks over the new surface where the rock allows it:
            only natural blocks are cut and at least COVER natural blocks stay above the new ceiling.
  lining:   every natural block touching the road's clear space from the side or from above (walls, roof,
            the faces of the cut) becomes stone bricks; the road surface and what lies under it are not
            touched. Built blocks stay as they are.
  lights:   a sea lantern set into the roof on the centre line about every LIGHT blocks of t.
  portal:   at the west mouth (the first roofed t from t0) a stone brick face one block thick around the
            opening, from the road up to PORTAL blocks over the opening, plus a stone brick slab cornice.
usage: plan_road_tunnel_finish.py <capture> <seed x z y> <box x0 z0 x1 z1> <t0> <out-dir> [grade]"""
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
sx, sz, sy = map(int, sys.argv[2:5])
bx0, bz0, bx1, bz1 = map(int, sys.argv[5:9])
T0 = float(sys.argv[9])
out = Path(sys.argv[10])
out.mkdir(parents=True, exist_ok=True)
GRADE = float(sys.argv[11]) if len(sys.argv) > 11 else 0.20
HEAD, COVER, LIGHT, PORTAL = 6, 2, 8, 4
AIR = ('minecraft:air', 'minecraft:cave_air')
NATURAL = ('minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block', 'minecraft:coarse_dirt', 'minecraft:gravel', 'minecraft:andesite',
           'minecraft:diorite', 'minecraft:granite', 'minecraft:tuff', 'minecraft:deepslate', 'minecraft:podzol', 'minecraft:rooted_dirt',
           'minecraft:clay', 'minecraft:sand', 'minecraft:calcite', 'minecraft:coal_ore', 'minecraft:iron_ore', 'minecraft:copper_ore')
SOFT = ('grass', 'fern', 'flower', 'bush', 'sapling', 'vine', 'roots', '_leaves', '_log', 'dandelion', 'poppy', 'tulip', 'snow')
BRICK = 'minecraft:stone_bricks'


def name(s):
    return s.split('[')[0]


def st(x, y, z):
    return cap.state(x, y, z)


def is_air(x, y, z):
    n = name(st(x, y, z))
    return n in AIR or n.endswith(SOFT)


def natural(x, y, z):
    return name(st(x, y, z)) in NATURAL


def surf(x, z, yref):
    for y in range(yref + 2, yref - 3, -1):
        s = st(x, y, z)
        if s.startswith('trafficcraft:') and is_air(x, y + 1, z):
            m = re.search(r'layers=(\d)', s)
            return y, (y + int(m.group(1)) / 8 if m else y + 1.0), s
    return None


# ---- the road
seen = {(sx, sz): surf(sx, sz, sy)}
q = deque([(sx, sz)])
while q:
    p = q.popleft()
    y = seen[p][0]
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        r = (p[0] + dx, p[1] + dz)
        if r in seen or not (bx0 <= r[0] <= bx1 and bz0 <= r[1] <= bz1):
            continue
        s = surf(r[0], r[1], y)
        if s and abs(s[0] - y) <= 1:
            seen[r] = s
            q.append(r)


def roofed(p, y):
    return any(not is_air(p[0], yy, p[1]) for yy in range(y + 2, y + 40))


roof = {p for p, s in seen.items() if roofed(p, s[0])}
tc = np.array(sorted(roof), float)
ctr = tc.mean(0)
ax = np.linalg.svd(tc - ctr)[2][0]
if ax[0] < 0:
    ax = -ax
perp = np.array([-ax[1], ax[0]])
T = {p: float((np.array(p) - ctr) @ ax) for p in seen}
Wd = {p: float((np.array(p) - ctr) @ perp) for p in seen}

rows = {}


def put(x, y, z, state, why):
    before = st(x, y, z)
    if before != state:
        rows[x, y, z] = [x, y, z, before, state, why]


# ---- ramp profile: old height by t bins
bins = {}
for p, (y, h, s) in seen.items():
    if abs(Wd[p]) <= 6:
        bins.setdefault(int(math.floor(T[p])), []).append(h)
old = {k: float(np.median(v)) for k, v in bins.items()}
k0 = min(old, key=lambda k: (abs(k - T0), k))          # nearest bin with paving on the centre line
T0 = float(k0)
h0 = old[k0]
t_end = None
for k in sorted(old):
    if k <= T0:
        continue
    if h0 + GRADE * (k - T0) >= old[k]:
        t_end = k
        break
report = dict(cells=len(seen), roofed=len(roof), axis=ax.round(3).tolist(), t0=T0, h0=h0, grade=GRADE, ramp_end_t=t_end)
new_h = {}
for p, (y, h, s) in seen.items():
    t = T[p]
    if t_end is not None and T0 <= t <= t_end:
        target = math.floor((h0 + GRADE * (t - T0)) * 8) / 8
        if target < h - 1e-9:
            new_h[p] = target
lowered = 0
for p, nh in new_h.items():
    y, h, s = seen[p]
    x, z = p
    kind = 'trafficcraft:concrete' if 'concrete' in name(s) else 'trafficcraft:asphalt'
    base = math.floor(nh) - 1
    layers = int(round((nh - math.floor(nh)) * 8))
    for yy in range(base + 1, y + 2):          # clear the old deck and the cut above the new one
        put(x, yy, z, 'minecraft:air', 'ramp cut')
    put(x, base, z, kind, 'ramp deck')
    if layers:
        put(x, base + 1, z, f'{kind}_slope[layers={layers},waterlogged=false]', 'ramp deck')
    lowered += 1
report['ramp_columns'] = lowered


def floor_top(p):
    """(block y of the walking surface, first clear y above it) after the ramp."""
    if p in new_h:
        nh = new_h[p]
        lay = (nh - math.floor(nh)) > 1e-9
        return math.floor(nh) - 1, math.floor(nh) + (1 if lay else 0)
    y, h, s = seen[p]
    return y, y + 1


# ---- the tunnel itself: roofed columns and the ramp, from t0 east (other roads in the box are left alone)
work = {p for p in seen if T[p] >= T0 - 2 and (p in roof or p in new_h)}

# ---- clear space per column (after ramp), headroom raise in roofed columns
space = {}
raised = 0
for p in work:
    x, z = p
    fy, y = floor_top(p)
    top = y
    while top < y + 40 and (is_air(x, top, z) or (x, top, z) in rows and rows[x, top, z][4] in AIR):
        top += 1
    # top is the first solid block over the road (or y+40 under the sky)
    if p in roof and top - y < HEAD:
        want = y + HEAD
        ok = all(natural(x, yy, z) for yy in range(top, want)) and all(natural(x, yy, z) for yy in range(want, want + COVER))
        if ok:
            for yy in range(top, want):
                put(x, yy, z, 'minecraft:air', 'headroom')
            top = want
            raised += 1
    space[p] = (y, top)
report['headroom_raised_columns'] = raised

# ---- lining: natural blocks touching the clear space from the side or from above
lined = 0
for p, (y, top) in space.items():
    x, z = p
    hi = top if p in roof else min(top, y + HEAD)
    for yy in range(y, hi):
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            r = (x + dx, z + dz)
            if r in seen:
                continue
            if natural(r[0], yy, r[1]) and not ((r[0], yy, r[1]) in rows):
                put(r[0], yy, r[1], BRICK, 'lining wall')
                lined += 1
    if p in roof and top < y + 40 and natural(x, top, z) and (x, top, z) not in rows:
        put(x, top, z, BRICK, 'lining roof')
        lined += 1
report['lining_cells'] = lined

# ---- lights in the roof along the centre line
lights = 0
by_t = {}
for p in roof:
    if p in space:
        by_t.setdefault(int(math.floor(T[p] / LIGHT)), []).append(p)
for k, ps in sorted(by_t.items()):
    mid = float(np.median([Wd[q] for q in ps]))      # the tunnel bends off the axis: centre of this stretch
    p = min(ps, key=lambda q: (round(abs(Wd[q] - mid)), abs(T[q] - (k + .5) * LIGHT)))
    y, top = space[p]
    if top >= y + 40:
        continue
    cur = rows.get((p[0], top, p[1]), [None] * 5)[4] or st(p[0], top, p[1])
    if name(cur) in (BRICK,) or natural(p[0], top, p[1]):
        put(p[0], top, p[1], 'minecraft:sea_lantern', 'light')
        lights += 1
report['lights'] = lights

# ---- portal face at the west mouth
mouth_t = min(T[p] for p in roof if T[p] >= T0)
ring = [p for p in work if mouth_t - 0.5 <= T[p] < mouth_t + 0.5]
if ring:
    ws = [Wd[p] for p in ring]
    wlo, whi = min(ws), max(ws)
    open_top = max(space[p][1] for p in ring if p in space)
    floor_lo = min(space[p][0] for p in ring if p in space)
    face = 0
    for wi in range(int(math.floor(wlo)) - 2, int(math.ceil(whi)) + 3):
        c = ctr + ax * mouth_t + perp * wi
        x, z = int(round(c[0])), int(round(c[1]))
        inside = wlo - 0.5 <= wi <= whi + 0.5
        for yy in range(floor_lo, open_top + PORTAL + 1):
            if inside and (x, z) in space and space[(x, z)][0] <= yy < space[(x, z)][1]:
                continue                       # the opening stays clear
            n = name(rows.get((x, yy, z), [None] * 5)[4] or st(x, yy, z))
            if n in AIR or n in NATURAL or n.endswith(SOFT):
                put(x, yy, z, BRICK, 'portal face')
                face += 1
        yy = open_top + PORTAL + 1
        if name(st(x, yy, z)) in AIR:
            put(x, yy, z, 'minecraft:stone_brick_slab[type=bottom,waterlogged=false]', 'portal cornice')
    report.update(portal_t=mouth_t, portal_cells=face, portal_width=[wlo, whi], portal_opening_top=open_top)

json.dump([r[:5] for r in rows.values()], open(out / 'rows.json', 'w', encoding='utf8'))
from collections import Counter
report['rows'] = len(rows)
report['purposes'] = Counter(r[5] for r in rows.values())
json.dump(report, open(out / 'report.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(report, ensure_ascii=False, default=str))
