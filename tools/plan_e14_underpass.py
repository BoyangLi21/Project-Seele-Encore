"""E14: lower the Kirisato yard tunnel road under the through line, which crosses it at grade.

The road band is the declared walk+road piece holding the seed cell inside the box. Along the band's
axis, every cell within DECK_REACH of a rail centre line marks the crossing; the walking height there
drops to LOW, and on each side it climbs back to the old height at RAMP_GRADE (TrafficCraft slope
layers, eighths). Each lowered column keeps its surface material (asphalt or concrete, plain), is cleared
above, and the road declaration takes the new height.
Under each rail across the band a light grey concrete trackbed deck goes in at DECK_Y (top level with the
existing trackbed, below the rails; a smooth stone bottom slab where the rail is lower than the block top), with a one-block parapet on its edges outside the car envelope.
Where the lowered road meets floor that stays high (the rail tunnels' floor), a one-block curb is set on
the high side, again only outside the car envelope. Hanging ceiling lights like the cavity's own are
hung from the cavity roof at both ramp mouths.
usage: plan_e14_underpass.py <capture> <network.npz> <samples.json> <outdir> x0 z0 x1 z1 seed_x seed_z"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import ndimage

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
net = np.load(sys.argv[2])
network = {k: net[k].copy() for k in net.files}
samples = json.load(open(sys.argv[3], encoding='utf8'))
out = Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
X0, Z0, X1, Z1, SX, SZ = map(int, sys.argv[5:11])
ax, az = map(int, network['bounds'][:2])
road, walk, g2 = network['road'], network['walk'], network['grade2']
LOW, DECK_Y, DECK_REACH, PARAPET_FROM, RAMP_GRADE, MARGIN = 92.0, 96, 2.5, 2.0, 3 / 16, 1.0
LIGHT = 'projectseele:nerv_ceiling_light[hanging=true,lit=true]'
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')


def name(s):
    return s.split('[')[0]


writes, errors, notes = {}, [], Counter()


def put(x, y, z, state, purpose):
    before = cap.state(x, y, z)
    if before != state:
        writes[x, y, z] = [x, y, z, before, state, purpose]


# Road band inside the box.
sub = (road | walk)[Z0 - az:Z1 - az + 1, X0 - ax:X1 - ax + 1]
lab, _ = ndimage.label(sub, np.ones((3, 3)))
band = lab == lab[SZ - Z0, SX - X0]
bz, bx = np.nonzero(band)
cells = np.c_[bx + X0, bz + Z0]
centre = cells.mean(0)
u = np.linalg.svd(cells - centre, full_matrices=False)[2][0]
s_of = (cells - centre) @ u
# Rails near the box.
rail = np.concatenate([np.array(s['points']) for s in samples if any(X0 - 10 <= p[0] <= X1 + 10 and Z0 - 10 <= p[2] <= Z1 + 10 for p in s['points'][::20])])
rail = rail[(rail[:, 0] >= X0 - 10) & (rail[:, 0] <= X1 + 10) & (rail[:, 2] >= Z0 - 10) & (rail[:, 2] <= Z1 + 10)]
from scipy.spatial import cKDTree
tree = cKDTree(rail[:, [0, 2]])


def rail_at(x, z):
    d, i = tree.query([x + .5, z + .5])
    return float(d), float(rail[i, 1])


d_band = np.array([rail_at(x, z)[0] for x, z in cells])
cross = d_band <= DECK_REACH + .5
sA, sB = float(s_of[cross].min()) - MARGIN, float(s_of[cross].max()) + MARGIN
lowered = {}
for (x, z), s in zip(cells.tolist(), s_of.tolist()):
    old = g2[z - az, x - ax] / 2 + 1
    target = LOW + max(0.0, sA - s, s - sB) * RAMP_GRADE
    new = math.floor(min(old, target) * 8) / 8
    if new < old - 1 / 16:
        lowered[x, z] = (old, new)
# Rebuild lowered columns.
for (x, z), (old, new) in lowered.items():
    # Surface material from the old top: asphalt if any asphalt in the old surface, else concrete.
    olds = [cap.state(x, y, z) for y in range(math.floor(old) - 3, math.floor(old) + 1)]
    mat = 'trafficcraft:asphalt' if any('asphalt' in s for s in olds) else 'trafficcraft:concrete'
    base = math.floor(new) - 1
    layers = int(round((new - math.floor(new)) * 8))
    put(x, base, z, mat, 'E14 lowered road')
    if layers:
        put(x, base + 1, z, f'{mat}_slope[layers={layers},waterlogged=false]', 'E14 lowered road')
    for y in range(base + (2 if layers else 1), math.floor(old) + 2):
        n = name(cap.state(x, y, z))
        if n in AIR:
            continue
        if n.startswith('trafficcraft:') or n in ('minecraft:stone', 'minecraft:dirt', 'minecraft:gravel', 'minecraft:light_gray_concrete', 'minecraft:grass_block'):
            put(x, y, z, 'minecraft:air', 'E14 cut')
        elif n == 'projectseele:nerv_ceiling_light' and all(name(cap.state(x + dx, y, z + dz)) not in AIR for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            put(x, y, z, 'minecraft:air', 'E14 cut buried light')
        else:
            errors.append(['blocked cut', [x, y, z], n])
    g2[z - az, x - ax] = int(round((new - 1) * 2))
    if new <= LOW + 1e-6:
        for y in range(base + 1 + (1 if layers else 0), DECK_Y):
            if name(cap.state(x, y, z)) not in AIR and (x, y, z) not in writes:
                errors.append(['headroom', [x, y, z], name(cap.state(x, y, z))])
# Deck under the rails over the lowered band.
deck = set()
for (x, z), (old, new) in lowered.items():
    d, ry = rail_at(x, z)
    if d <= DECK_REACH:
        if DECK_Y + 1 <= ry + 1e-6:
            put(x, DECK_Y, z, 'minecraft:light_gray_concrete', 'E14 trackbed deck')
        elif DECK_Y + .5 <= ry + 1e-6:
            # Rail lower than the full block top: a bottom slab keeps the deck under the rail.
            put(x, DECK_Y, z, 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]', 'E14 trackbed deck (slab)')
        else:
            errors.append(['deck above rail', [x, z], ry])
        deck.add((x, z))
        if new > DECK_Y - 4 + 1e-6:
            errors.append(['deck headroom under 4', [x, z], new])
for (x, z) in deck:
    d, ry = rail_at(x, z)
    edge = any((x + dx, z + dz) not in deck and (x + dx, z + dz) in lowered for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    if edge and d >= PARAPET_FROM:
        put(x, DECK_Y + 1, z, 'minecraft:light_gray_concrete', 'E14 deck parapet')
# Curbs where high floor meets the lowered road.
for (x, z), (old, new) in lowered.items():
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        q = (x + dx, z + dz)
        if q in lowered or q in deck:
            continue
        # Floor height of the neighbour: first solid going down from DECK_Y + 2.
        y = DECK_Y + 2
        while y > new - 2 and name(cap.state(q[0], y, q[1])) in AIR:
            y -= 1
        if y + 1 - new < 1.5 or name(cap.state(q[0], y + 1, q[1])) not in AIR:
            continue
        d, ry = rail_at(*q)
        if d < PARAPET_FROM:
            # Centre within 2 means the block edge may be within the 1.3 car envelope at any height near the rail.
            notes['curb skipped inside the car envelope'] += 1
            continue
        put(q[0], y + 1, q[1], 'minecraft:light_gray_concrete', 'E14 curb')
# Lights at both ramp mouths: hang from the roof above band cells at s = sA - 2 and sB + 2.
for s_mouth in (sA - 2, sB + 2):
    picks = [tuple(c) for c, s in zip(cells.tolist(), s_of.tolist()) if abs(s - s_mouth) < .5]
    for x, z in picks[::4]:
        for y in range(DECK_Y, DECK_Y + 14):
            if name(cap.state(x, y + 1, z)) not in AIR:
                if name(cap.state(x, y, z)) in AIR and y > DECK_Y:
                    put(x, y, z, LIGHT, 'E14 light')
                break
rows = [w[:5] for w in writes.values()]
json.dump(rows, open(out / 'rows.json', 'w', encoding='utf8'))
np.savez_compressed(out / 'network.npz', **network)
check = dict(errors=errors, cells=len(rows), purposes=Counter(w[5] for w in writes.values()), lowered_columns=len(lowered), deck_columns=len(deck),
             axis=u.round(3).tolist(), crossing_s=[round(sA, 1), round(sB, 1)], notes=notes)
json.dump(check, open(out / 'check.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print(json.dumps(check, ensure_ascii=False))
