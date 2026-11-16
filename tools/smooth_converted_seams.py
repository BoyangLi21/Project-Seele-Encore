"""Smooth the seams where converted paving meets paving the conversion did not touch.

convert_roads_trafficcraft smooths steps inside its own network but leaves the edge against roads it did
not convert (a bridge deck, a road converted earlier): a step of three quarters of a block can remain there.
Walking heights (in eighths) are read from a capture taken after the list was written to a copy. Every
column of the list whose top is TrafficCraft paving may move, the rest are fixed: columns are relaxed until
no listed column differs from a paved neighbour of the same kind (carriageway or footway; the kerb
between them is left as it is) by more than half a block, each moving at most MAX_MOVE
eighths. A moved column is rebuilt as a full block under a slope of the new layers, keeping its kind
(asphalt or concrete) and its marking pattern and paint. Stone bricks (bridge decks) are never replaced.
usage: smooth_converted_seams.py <capture-before> <capture-after> <rows.json> <out-rows.json>"""
import json
import re
import sys

from plan_station_access_corridor import CapturedSurface

before = CapturedSurface(sys.argv[1], partial=True)
after = CapturedSurface(sys.argv[2], partial=True)
rows = json.load(open(sys.argv[3], encoding='utf8'))
STEP, MAX_MOVE = 4, 10
hi = after.measured['highest']
ax, az = map(int, after.bounds[:2])
SKIP = ('_leaves', '_log', 'grass', 'fern', 'flower', 'snow')
KEEP = ('minecraft:stone_bricks', 'minecraft:stone_brick_slab', 'minecraft:stone_brick_stairs', 'minecraft:stone_brick_wall')


def top(x, z):
    """(walking height in eighths, y of the top paving block, its state) or None when the column is not paved."""
    y0 = int(hi[z - az, x - ax]) + 2
    for y in range(y0, y0 - 16, -1):
        s = after.state(x, y, z)
        n = s.split('[')[0]
        if n in ('minecraft:air', 'minecraft:cave_air') or n.endswith(SKIP):
            continue
        if not (n.startswith('trafficcraft:') or n.startswith('projectseele:road')):
            return None
        m = re.search(r'layers=(\d)', s)
        return 8 * y + (int(m.group(1)) if m else (4 if 'type=bottom' in s else 8)), y, s
    return None


inside = [r for r in rows if ax + 2 <= r[0] < ax + hi.shape[1] - 2 and az + 2 <= r[2] < az + hi.shape[0] - 2]
listed = {(r[0], r[2]) for r in inside}
T = {}
for (x, z) in listed:
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            p = (x + dx, z + dz)
            if p not in T:
                T[p] = top(*p)
movable = {p for p in listed if T.get(p) and T[p][2].startswith('trafficcraft:')}
H = {p: v[0] for p, v in T.items() if v}
KIND = {p: ('concrete' if 'concrete' in v[2].split('[')[0] else 'road') for p, v in T.items() if v}
H0 = dict(H)


def relax():
    for it in range(60):
        changed = 0
        for p in movable:
            changed += settle(p)
        if not changed:
            return


def settle(p):
    nb = [H[q] for q in ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)) if q in H and KIND[q] == KIND[p]]
    if not nb:
        return 0
    lo, hi_ = max(nb) - STEP, min(nb) + STEP
    if lo > hi_:
        h = (lo + hi_) // 2             # between two levels a block apart: halve the worst step
    else:
        h = min(max(H[p], lo), hi_)
    h = min(max(h, H0[p] - MAX_MOVE), H0[p] + MAX_MOVE)
    if h != H[p]:
        H[p] = h
        return 1
    return 0


relax()
# A seam still over half a block: the unconverted plain TrafficCraft column across it may move too (not a
# marked one, whose paint is not in the list).
extra = set()
for p in listed:
    for q in ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)):
        if (q not in listed and q in H and p in H and KIND[q] == KIND[p] and abs(H[q] - H[p]) > STEP
                and T[q][2].startswith('trafficcraft:') and 'pattern' not in T[q][2]):
            extra.add(q)
for q in extra:
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        r = (q[0] + dx, q[1] + dz)
        if r not in T:
            T[r] = top(*r)
            if T[r]:
                H[r] = H0[r] = T[r][0]
                KIND[r] = 'concrete' if 'concrete' in T[r][2].split('[')[0] else 'road'
movable |= extra
relax()

byxyz = {(r[0], r[1], r[2]): r for r in rows}
moved = 0
for p in movable:
    if H[p] == H0[p]:
        continue
    x, z = p
    _, yt, st = T[p]
    kind = 'concrete' if 'concrete' in st.split('[')[0] else 'asphalt'
    pm = re.match(r'trafficcraft:asphalt(?:_slope)?_pattern_(\d+)', st)
    facing = re.search(r'facing=(\w+)', st)
    ent = next((r[5] for y in (yt, yt - 1, yt + 1) for r in [byxyz.get((x, y, z))] if r and len(r) > 5), None)
    Y, L = divmod(H[p], 8)
    want = {}
    for y in range(Y - 1, max(Y, yt) + 2):     # full block under the surface, slope layers on top, air above
        if y == Y - 1:
            want[y] = f'trafficcraft:{kind}'
        elif y == Y and L:
            want[y] = f'trafficcraft:{kind}_slope[layers={L},waterlogged=false]'
        else:
            want[y] = 'minecraft:air'
    top_y = Y if L else Y - 1
    if pm and kind == 'asphalt':
        f = facing.group(1) if facing else 'north'
        want[top_y] = (f'trafficcraft:asphalt_slope_pattern_{pm.group(1)}[facing={f},layers={L},waterlogged=false]' if L
                       else f'trafficcraft:asphalt_pattern_{pm.group(1)}[facing={f}]')
    for y, s in want.items():
        cur = after.state(x, y, z)
        if cur.split('[')[0] in KEEP:
            continue
        if s == 'minecraft:air' and not (cur.startswith('trafficcraft:') or cur.split('[')[0] in ('minecraft:air', 'minecraft:cave_air')):
            continue                    # only paving is cleared above the new surface
        old = byxyz.get((x, y, z))
        b = old[3] if old else before.state(x, y, z)
        row = [x, y, z, b, s]
        if y == top_y and pm and ent:
            row.append(ent)
        if row[3] == row[4] and len(row) == 5:
            byxyz.pop((x, y, z), None)
        else:
            byxyz[(x, y, z)] = row
    moved += 1
out = list(byxyz.values())
json.dump(out, open(sys.argv[4], 'w', encoding='utf8'))
left = 0
for p in listed:
    if p not in H:
        continue
    for q in ((p[0] + 1, p[1]), (p[0], p[1] + 1), (p[0] - 1, p[1]), (p[0], p[1] - 1)):
        if q in H and KIND[q] == KIND[p] and abs(H[q] - H[p]) > STEP and abs(H[q] - H[p]) <= 13:
            left += 1
print(json.dumps({'listed_columns': len(listed), 'movable': len(movable), 'moved': moved, 'rows': len(out), 'steps_left_over_half': left // 1}))
