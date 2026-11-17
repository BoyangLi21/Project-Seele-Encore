"""New-town east edge: a north-south edge road on low fill between streets, and finished cul-de-sac ends.

edge road: for each z in the given spans, the cross-section of the existing edge stub is laid at deck height
  (footway, carriageway, footway across x0..x0+6): footways are concrete with a one-layer slope on top, the
  carriageway plain asphalt. Below the deck everything down to the ground becomes dirt; above it, up to CLEAR
  blocks, plants and tree parts go. Each side gets a 1:1 grass slope down to the ground. Where the new road
  crosses a street's footway, the footway under the carriageway becomes asphalt.
cul-de-sac: a street of centre z ending at x_end on a deck: the carriageway is cut back with rounded corners
  (like #5113), a footway two blocks wide closes round it, a one-block concrete parapet runs along the outer
  edge where the deck stops, and the paved tail beyond it goes back to grass. Two bushes stand on the ground
  past the parapet.
trees: a tree whose trunk stands in the fill or the road goes whole (leaves nearer to it than to any other
  trunk, within 4 blocks); other trees keep everything except leaves inside the road's clear space.
usage: plan_edge_road_and_ends.py <capture> <config.json> <out-dir>
config: {"deck_y": 104, "edge": {"x0": -1123, "spans": [[371, 420], ...]}, "ends": [{"z": 748, "x_end": -1117}, ...]}"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
cfg = json.load(open(sys.argv[2], encoding='utf8'))
out = Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
top = cap.measured['top']
bx, bz = map(int, cap.bounds[:2])
Y = cfg['deck_y']
CLEAR, SLOPE_MAX, TREE_R = 6, 10, 4
AIR = 'minecraft:air'
FOOT, FOOT_TOP = 'trafficcraft:concrete', 'trafficcraft:concrete_slope[layers=1,waterlogged=false]'
ROAD = 'trafficcraft:asphalt'
WALL = 'minecraft:light_gray_concrete'
PLANT_ENDS = ('grass', 'fern', 'flower', 'bush', 'sapling', 'vine', 'dandelion', 'poppy', 'tulip', 'bluet', 'orchid', 'allium', 'daisy', 'cornflower', 'lily', 'snow')
NATURAL = ('minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block', 'minecraft:coarse_dirt', 'minecraft:podzol', 'minecraft:gravel',
           'minecraft:andesite', 'minecraft:diorite', 'minecraft:granite', 'minecraft:rooted_dirt', 'minecraft:moss_block')
rows = {}
why = {}


def name(s):
    return s.split('[')[0]


def cur(x, y, z):
    return rows[x, y, z][4] if (x, y, z) in rows else cap.state(x, y, z)


def put(x, y, z, state, purpose):
    before = cap.state(x, y, z)
    if before == state:
        rows.pop((x, y, z), None)
        return
    rows[x, y, z] = [x, y, z, before, state]
    why[x, y, z] = purpose


def soft(s):
    n = name(s)
    return n in (AIR, 'minecraft:cave_air') or n.endswith(PLANT_ENDS) or n.endswith('_leaves') or n.endswith('_log')


def ground(x, z):
    """Top natural block of the column (the capture's soil top)."""
    return int(top[z - bz, x - bx])


trunks_gone = set()


def trunks_near(x0, z0, x1, z1):
    found = set()
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            g = ground(x, z)
            for y in range(g + 1, g + 4):
                if name(cap.state(x, y, z)).endswith('_log'):
                    found.add((x, z))
                    break
    return found


def remove_trees(cells):
    """Whole trees with a trunk in cells."""
    xs = [c[0] for c in cells]
    zs = [c[1] for c in cells]
    near = trunks_near(min(xs) - 8, min(zs) - 8, max(xs) + 8, max(zs) + 8)
    gone = {t for t in near if t in cells}
    for t in gone:
        g = ground(*t)
        for y in range(g + 1, g + 40):
            if name(cur(t[0], y, t[1])).endswith('_log'):
                put(t[0], y, t[1], AIR, 'tree')
        for dx in range(-TREE_R, TREE_R + 1):
            for dz in range(-TREE_R, TREE_R + 1):
                x, z = t[0] + dx, t[1] + dz
                d = math.hypot(dx, dz)
                if d > TREE_R or any(math.hypot(x - o[0], z - o[1]) < d for o in near if o not in gone):
                    continue
                for y in range(g + 1, g + 40):
                    n = name(cur(x, y, z))
                    if n.endswith('_leaves') or n.endswith('_log'):
                        put(x, y, z, AIR, 'tree')
    trunks_gone.update(gone)


def fill_column(x, z, top_y, top_state, purpose):
    """Natural fill from the ground up to top_y, top_state on top; plants and tree parts in the way go."""
    g = ground(x, z)
    for y in range(g + 1, top_y):
        if soft(cur(x, y, z)) or name(cur(x, y, z)) in NATURAL:
            put(x, y, z, 'minecraft:dirt', purpose)
    if top_y > g and (soft(cur(x, top_y, z)) or name(cur(x, top_y, z)) in NATURAL):
        put(x, top_y, z, top_state, purpose)
    if top_y > g and name(cap.state(x, g, z)) == 'minecraft:grass_block':
        put(x, g, z, 'minecraft:dirt', purpose)
    for y in range(top_y + 1, top_y + 3):
        n = name(cur(x, y, z))
        if n.endswith(PLANT_ENDS):
            put(x, y, z, AIR, purpose)


# ---- edge road
edge = cfg.get('edge')
report = Counter()
if edge:
    x0 = edge['x0']
    prof = [('foot', x0), ('foot', x0 + 1), ('road', x0 + 2), ('road', x0 + 3), ('road', x0 + 4), ('foot', x0 + 5), ('foot', x0 + 6)]
    foot_x = {x for k, x in prof}
    region = set()
    for z0, z1 in edge['spans']:
        for z in range(z0, z1 + 1):
            for x in range(x0 - SLOPE_MAX, x0 + 7 + SLOPE_MAX):
                region.add((x, z))
    remove_trees({(x, z) for (x, z) in region if x0 <= x <= x0 + 6 or (x0 - SLOPE_MAX <= x < x0 and Y - (x0 - x) > ground(x, z))
                  or (x0 + 6 < x and Y - (x - x0 - 6) > ground(x, z))})
    for z0, z1 in edge['spans']:
        for z in range(z0, z1 + 1):
            for kind, x in prof:
                g = ground(x, z)
                for y in range(min(g + 1, Y), Y):
                    if soft(cur(x, y, z)) or name(cur(x, y, z)) in NATURAL:
                        put(x, y, z, 'minecraft:dirt', 'edge fill')
                if kind == 'road':
                    put(x, Y, z, ROAD, 'edge road')
                    put(x, Y + 1, z, AIR, 'edge road')
                else:
                    put(x, Y, z, FOOT, 'edge footway')
                    put(x, Y + 1, z, FOOT_TOP, 'edge footway')
                for y in range(Y + 2, Y + CLEAR + 1):
                    if soft(cur(x, y, z)) and name(cur(x, y, z)) != AIR:
                        put(x, y, z, AIR, 'edge clear')
                report['edge columns'] += 1
            # 1:1 grass slopes
            for side in (-1, 1):
                for d in range(1, SLOPE_MAX + 1):
                    x = x0 - d if side < 0 else x0 + 6 + d
                    t = Y - d
                    if t <= ground(x, z):
                        break
                    fill_column(x, z, t, 'minecraft:grass_block[snowy=false]', 'edge slope')
                    report['slope columns'] += 1
    # carriageway through the street footways it crosses
    for z in edge.get('crossings', []):
        for kind, x in prof:
            if kind == 'road' and name(cap.state(x, Y, z)).startswith('trafficcraft:concrete'):
                put(x, Y, z, ROAD, 'edge crossing')
                put(x, Y + 1, z, AIR, 'edge crossing')
                report['crossing cells'] += 1

# ---- cul-de-sac ends
for e in cfg.get('ends', []):
    zc, xe = e['z'], e['x_end']
    half, fw = e.get('half', 4), e.get('foot', 2)
    # rounded carriageway end: outer two rows stop earlier
    road_end = {}
    for dz in range(-half, half + 1):
        cut = {half: 2, half - 1: 1}.get(abs(dz), 0)
        road_end[zc + dz] = xe - fw - 1 - cut
    x_ring = min(road_end.values()) + 1            # the ring: from the first cut-back cell to the parapet
    for z in range(zc - half - fw, zc + half + fw + 1):
        for x in range(x_ring, xe):
            if z in road_end and x <= road_end[z]:
                continue
            if not cap.state(x, Y, z).startswith('trafficcraft:'):
                continue                            # the ring stays on the street's own deck
            put(x, Y, z, FOOT, 'end footway')
            put(x, Y + 1, z, FOOT_TOP, 'end footway')
            for y in range(Y + 2, Y + 5):
                if soft(cur(x, y, z)) and name(cur(x, y, z)) != AIR:
                    put(x, y, z, AIR, 'end clear')
            report['end footway'] += 1
    # parapet along xe and back along the outer edges for the width of the ring
    for z in range(zc - half - fw, zc + half + fw + 1):
        put(xe, Y + 1, z, WALL, 'end parapet')
        for y in range(ground(xe, z) + 1, Y + 1):
            if soft(cur(xe, y, z)) or name(cur(xe, y, z)) in NATURAL or name(cur(xe, y, z)).startswith(('trafficcraft:', 'projectseele:road')):
                put(xe, y, z, WALL, 'end parapet')
        report['parapet'] += 1
    # paved tail beyond the parapet goes back to grass
    for z in range(zc - half - fw - 1, zc + half + fw + 2):
        for x in range(xe + 1, xe + 8):
            hit = False
            for y in range(Y - 3, Y + 3):
                s = cur(x, y, z)
                if s.startswith(('trafficcraft:', 'projectseele:road')) or name(s) == WALL:
                    put(x, y, z, AIR, 'end tail')
                    hit = True
            if hit:
                g = ground(x, z)
                if name(cur(x, g, z)) in ('minecraft:dirt', 'minecraft:coarse_dirt'):
                    put(x, g, z, 'minecraft:grass_block[snowy=false]', 'end tail')
                report['tail columns'] += 1
    # two bushes on the ground past the parapet
    for dz in (-3, 3):
        x, z = xe + 3, zc + dz
        g = ground(x, z)
        if name(cur(x, g, z)) == 'minecraft:grass_block' and name(cur(x, g + 1, z)) == AIR:
            put(x, g + 1, z, 'minecraft:azalea_leaves[distance=7,persistent=true,waterlogged=false]', 'end bush')
            report['bushes'] += 1

json.dump(list(rows.values()), open(out / 'rows.json', 'w', encoding='utf8'))
report['rows'] = len(rows)
report['trees removed'] = len(trunks_gone)
report['purposes'] = Counter(why.values())
json.dump(report, open(out / 'report.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(report, ensure_ascii=False, default=str))
