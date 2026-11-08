"""Convert declared roads to TrafficCraft blocks.

Surfaces go from half-block steps to eighth-block layers: `asphalt` below, `asphalt_slope
[layers=k]` on top. Steps are smoothed into ramps of at most two layers per block and never
move a surface more than half a block from where it was, so doors, platforms and bridges
still meet it. Footways become `concrete` one layer above the carriageway beside them, with
no half-block kerb. Markings follow Japanese practice: a yellow solid centre line on mountain
roads, a white dashed one in town, white edge lines beside footways, none on lanes under four
blocks wide and none inside junctions. Each marking carries its paint colour as a block entity.
Only paving, slabs, plants and air are replaced; anything else is reported and left.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

import numpy as np
from scipy.ndimage import center_of_mass, distance_transform_edt, label, mean, uniform_filter

from plan_ashi_landscape_r54 import PLANTS, SOIL
from plan_station_access_corridor import CapturedSurface
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

LAYERS = 8
# Only these floors are road. Tactile strips, platforms, concourses and anything else keep what they are.
ROAD_FLOORS = {'minecraft:black_concrete', 'minecraft:white_concrete', 'minecraft:gray_concrete', 'minecraft:smooth_stone', 'minecraft:smooth_stone_slab',
               'projectseele:road_asphalt_slab', 'projectseele:road_marking_slab'}
FOOT_FLOORS = {'minecraft:smooth_stone', 'minecraft:smooth_stone_slab'}
MAX_STEP = 2            # layers between neighbours, 25%, where the road's own gradient allows it
STEEP_STEP = 4          # layers: a ramp too steep for MAX_STEP keeps its half-block steps
DRIFT = 4               # layers a surface may move from where it was
WHITE, YELLOW = 0, 4
DASH = 5                # painted, then the same unpainted
ZEBRA = 4               # cells of zebra along an approach
ZEBRA_SKEW = 20         # degrees off the block grid beyond which a crossing has no clean bars
EIGHT = np.ones((3, 3), int)
# Town: buildings on a tenth of the ground nearby, or streets on a fifth (a street grid whose towers rise from carriers).
BUILT_WINDOW, BUILT_SHARE, STREET_WINDOW, STREET_SHARE = 61, .1, 121, .2
MIN_JUNCTIONS, MIN_ZEBRA, TALLY_WIDTH = 20, 8, 1024       # a plan with fewer than MIN_ZEBRA cells per town junction has lost its crossings
ENTITY = 'trafficcraft:colored_block_entity'
REPLACEABLE = PAVEMENT | AIR | PLANTS | SOIL | {'minecraft:light', 'minecraft:snow'}
# Facing that puts pattern 23's offset line on a side: it lies east when the texture faces north.
# Single-line pieces: where each line meets the cell edges with the texture facing north, as
# (east, south) in 0..1, read from the pattern textures.
LINE_PIECES = {1: ((0.5, 0.0), (0.5, 1.0)), 2: ((1.0, 0.531), (0.531, 1.0)), 3: ((1.0, 0.5), (0.5, 1.0)),
               9: ((1.0, 0.562), (0.75, 1.0)), 10: ((0.688, 0.0), (0.5, 1.0)), 11: ((0.312, 0.0), (0.5, 1.0)),
               12: ((0.25, 1.0), (0.0, 0.562)), 14: ((0.594, 0.0), (0.5, 1.0)), 15: ((0.406, 0.0), (0.5, 1.0)),
               23: ((0.688, 0.0), (0.688, 1.0)), 24: ((1.0, 0.312), (0.312, 1.0)), 25: ((1.0, 0.75), (0.75, 1.0)),
               29: ((0.5, 0.0), (0.688, 1.0)), 30: ((0.5, 0.0), (0.312, 1.0))}


def paved(state):
    """A road surface block, ours or TrafficCraft's, so a converted road can be converted again."""
    return state.split('[')[0] in PAVEMENT or state.startswith('trafficcraft:')


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1), 'utf8')


def smooth(height, walk, joined, passes=40):
    """Ramps instead of half-block steps: relax towards the neighbours' mean, staying within
    DRIFT of the original, then round and limit each step to MAX_STEP layers."""
    h = height.astype(float)
    low, high = height - DRIFT, height + DRIFT
    for _ in range(passes):
        total, count = np.zeros_like(h), np.zeros_like(h)
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            n = np.roll(h, shift, axis)
            ok = np.roll(joined[axis][..., 0 if shift == 1 else 1], 0)
            total += np.where(ok, n, 0)
            count += ok
        h = np.where(walk & (count > 0), np.clip((h + total) / (1 + count), low, high), h)
    out = np.rint(h).astype(int)
    for _ in range(10 * passes):
        changed = False
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            n = np.roll(out, shift, axis)
            ok = joined[axis][..., 0 if shift == 1 else 1]
            # Never below the drift floor: a ramp steeper than MAX_STEP would otherwise sink without end.
            target = np.maximum(n + MAX_STEP, low)
            too_high = ok & (out > target)
            if too_high.any():
                out[too_high] = target[too_high]
                changed = True
        if not changed:
            break
    return out


def limit(surface, joined, movable, lowest, rounds=400):
    """Lower `movable` cells, never under `lowest`, until no neighbour pair steps more than MAX_STEP within one class."""
    out = surface.copy()
    for _ in range(rounds):
        changed = False
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            n = np.roll(out, shift, axis)
            same = movable & np.roll(movable, shift, axis)
            target = np.maximum(n + MAX_STEP, lowest)
            ok = joined[axis][..., 0 if shift == 1 else 1] & same & (out > target)
            if ok.any():
                out[ok] = target[ok]
                changed = True
        if not changed:
            break
    return out


def adjacency(walk, grade):
    """Neighbour pairs that are one surface (within half a block), per axis and direction."""
    joined = []
    for axis in (0, 1):
        forward = walk & np.roll(walk, 1, axis) & (np.abs(grade - np.roll(grade, 1, axis)) <= 1)
        backward = walk & np.roll(walk, -1, axis) & (np.abs(grade - np.roll(grade, -1, axis)) <= 1)
        if axis == 0:
            forward[0], backward[-1] = False, False
        else:
            forward[:, 0], backward[:, -1] = False, False
        joined.append(np.stack([forward, backward], -1))
    return joined


def direction(road, iz, ix, radius=4):
    """Principal axis of the carriageway around a cell, and how clearly it runs one way."""
    z0, x0 = max(0, iz - radius), max(0, ix - radius)
    zz, xx = np.nonzero(road[z0:iz + radius + 1, x0:ix + radius + 1])
    if len(xx) < 4:
        return None, 0.0
    pts = np.c_[xx + x0 - ix, zz + z0 - iz].astype(float)
    pts -= pts.mean(0)
    w, v = np.linalg.eigh(pts.T @ pts)
    return v[:, 1], float(1 - w[0] / max(w[1], 1e-9))


def longest_chain(cells):
    """The longest path through 8-connected cells: a centre or edge line's own order."""
    cells = set(cells)

    def farthest(start):
        parent, frontier, last = {start: None}, [start], start
        while frontier:
            following = []
            for iz, ix in frontier:
                for dz in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        n = (iz + dz, ix + dx)
                        if n in cells and n not in parent:
                            parent[n] = (iz, ix)
                            following.append(n)
            if following:
                last = following[-1]
            frontier = following
        return last, parent
    a, _ = farthest(next(iter(cells)))
    b, parent = farthest(a)
    path = [b]
    while parent[path[-1]] is not None:
        path.append(parent[path[-1]])
    return path


def rotated(point, facing):
    """A texture point (east, south in 0..1) after turning the texture to `facing`."""
    u, v = point
    return {'north': (u, v), 'east': (1 - v, u), 'south': (1 - u, 1 - v), 'west': (v, 1 - u)}[facing]


def piece_for(entry, leave):
    """Line piece and facing whose line meets the cell edges nearest to where the line does."""
    best, choice = np.inf, None
    for pattern, (a, b) in LINE_PIECES.items():
        for facing in ('north', 'east', 'south', 'west'):
            ra, rb = np.array(rotated(a, facing)), np.array(rotated(b, facing))
            cost = min(np.abs(entry - ra).sum() + np.abs(leave - rb).sum(), np.abs(entry - rb).sum() + np.abs(leave - ra).sum())
            if cost < best:
                best, choice = cost, (pattern, facing)
    return choice


def trace(path, allowed, smoothing=2, step=.05):
    """Cells along a centre or edge line, each with its piece and the arc length at its middle.

    The 8-connected chain becomes a 4-connected one, so every cell is entered and left through
    an edge, never a corner; the crossing point on each shared edge comes from the smoothed line,
    which keeps a solid line solid round bends and dashes measured along the road.
    """
    pts = np.array([(ix + .5, iz + .5) for iz, ix in path], float)
    if len(pts) > 2 * smoothing + 1:
        kernel = np.ones(2 * smoothing + 1) / (2 * smoothing + 1)
        inner = np.c_[np.convolve(pts[:, 0], kernel, 'valid'), np.convolve(pts[:, 1], kernel, 'valid')]
        pts = np.vstack([pts[:1], inner, pts[-1:]])
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    run = np.r_[0, np.cumsum(seg)]
    dense_run = np.arange(0, run[-1] + step, step)
    dense = np.c_[np.interp(dense_run, run, pts[:, 0]), np.interp(dense_run, run, pts[:, 1])]

    def near(cell):
        d = np.hypot(dense[:, 0] - cell[1] - .5, dense[:, 1] - cell[0] - .5)
        i = int(np.argmin(d))
        return d[i], dense_run[i]
    chain = [path[0]]
    for cell in path[1:]:
        last = chain[-1]
        if cell[0] != last[0] and cell[1] != last[1]:
            options = [(last[0], cell[1]), (cell[0], last[1])]
            options.sort(key=lambda c: (not (0 <= c[0] < allowed.shape[0] and 0 <= c[1] < allowed.shape[1] and allowed[c]), near(c)[0]))
            chain.append(options[0])
        chain.append(cell)

    def crossing(a, b):
        """Where the line crosses the edge shared by cells a and b, in a's cell coordinates."""
        if a[1] != b[1]:
            x_edge = max(a[1], b[1])
            close = np.abs(dense[:, 0] - x_edge) < step * 1.5
            close &= (dense[:, 1] > a[0] - .5) & (dense[:, 1] < a[0] + 1.5)
            v = np.clip(dense[close, 1].mean() - a[0], .15, .85) if close.any() else .5
            return np.array([x_edge - a[1], v])
        z_edge = max(a[0], b[0])
        close = np.abs(dense[:, 1] - z_edge) < step * 1.5
        close &= (dense[:, 0] > a[1] - .5) & (dense[:, 0] < a[1] + 1.5)
        u = np.clip(dense[close, 0].mean() - a[1], .15, .85) if close.any() else .5
        return np.array([u, z_edge - a[0]])
    out = []
    for i, cell in enumerate(chain):
        entry = crossing(cell, chain[i - 1]) if i > 0 else None
        leave = crossing(cell, chain[i + 1]) if i + 1 < len(chain) else None
        if entry is None and leave is None:
            continue
        if entry is None:
            entry = 1 - leave if (leave == 0).any() or (leave == 1).any() else leave
        if leave is None:
            leave = 1 - entry
        if 0 <= cell[0] < allowed.shape[0] and 0 <= cell[1] < allowed.shape[1] and allowed[cell]:
            out.append((tuple(int(v) for v in cell), piece_for(entry, leave), near(cell)[1]))
    return out


def plan_marks(road, walk, built):
    """Every painted cell: {(iz, ix): (pattern, facing, colour)}, its kind, and the road segments.

    Line type and colour are decided once per segment between junctions; centre and edge lines
    are traced as smooth curves and drawn cell by cell with the piece whose line meets the cell
    edges where the curve does, so a solid line stays solid round bends.
    """
    edge = distance_transform_edt(np.pad(road, 1))[1:-1, 1:-1]
    marks, kinds = {}, {}
    shape_ = road.shape

    def inside(iz, ix):
        return 0 <= iz < shape_[0] and 0 <= ix < shape_[1]

    def value(iz, ix):
        return edge[iz, ix] if inside(iz, ix) else 0.0

    junction = np.zeros(shape_, bool)
    centre_cells = np.zeros(shape_, bool)
    kerb_cells = np.zeros(shape_, bool)
    axes = {}
    for iz, ix in np.argwhere(road):
        half = edge[max(0, iz - 4):iz + 5, max(0, ix - 4):ix + 5].max()
        if 2 * half - 1 < 4:
            continue                           # narrow lanes carry no lines
        # The window must be long against the width, or a wide road looks the same every way.
        axis, clarity = direction(road, iz, ix, radius=max(5, int(round(2.5 * half))))
        if axis is None or clarity < .65:
            junction[iz, ix] = True            # a junction, a plaza or a sharp bend
            continue
        if axis[0] < 0 or (axis[0] == 0 and axis[1] < 0):
            axis = -axis
        axes[iz, ix] = axis
        perp = np.rint([-axis[1], axis[0]]).astype(int)
        here = edge[iz, ix]
        # One cell of the two in the middle of an even width: not below the one behind, above the one ahead.
        if here >= value(iz - perp[1], ix - perp[0]) and here > value(iz + perp[1], ix + perp[0]) and here > 1:
            centre_cells[iz, ix] = True
        elif here == 1 and any(inside(iz + dz, ix + dx) and walk[iz + dz, ix + dx] and not road[iz + dz, ix + dx]
                               for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            kerb_cells[iz, ix] = True
    segments, _ = label(road & ~junction, EIGHT)
    town_cells = (uniform_filter(built.astype(float), BUILT_WINDOW, mode='constant') >= BUILT_SHARE) | (uniform_filter(road.astype(float), STREET_WINDOW, mode='constant') >= STREET_SHARE)
    town_segment = {int(k): town_cells[segments == k].mean() > .5 for k in np.unique(segments[segments > 0])}
    # A chain is painted segment by segment, so a chain that grazes two segments cannot mix them.
    for mask, centre in ((centre_cells, True), (kerb_cells, False)):
        chains, count = label(mask, EIGHT)
        for k in range(1, count + 1):
            cells = [tuple(c) for c in np.argwhere(chains == k)]
            if len(cells) < 3:
                continue
            path = longest_chain(cells)
            owner = Counter(int(segments[c]) for c in path).most_common(1)[0][0]
            town = town_segment.get(owner, False)
            colour = WHITE if (town or not centre) else YELLOW
            crossed = trace(path, segments == owner)
            dashes = Counter(run // DASH for _, _, run in crossed)
            for cell, piece, run in crossed:
                # The gap of a dashed town centre line, and a dash the end of the line cut short.
                if centre and town and ((run // DASH) % 2 or dashes[run // DASH] < 3):
                    continue
                if centre or cell not in marks:
                    marks[cell] = (piece[0], piece[1], colour)
                    kinds[cell] = 'centre' if centre else 'edge'

    # A bend reads as a junction too; only a blob that three or more arms leave is one.
    blobs, _ = label(junction, EIGHT)
    reach = np.full(shape_, 99, int)
    owner = np.where(junction, blobs, 0)
    frontier = [tuple(c) for c in np.argwhere(junction)]
    for c in frontier:
        reach[c] = 0
    for step in range(1, ZEBRA + 2):
        following = []
        for iz, ix in frontier:
            for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (iz + dz, ix + dx)
                if inside(*n) and road[n] and reach[n] == 99 and n in axes:
                    reach[n] = step
                    owner[n] = owner[iz, ix]
                    following.append(n)
        frontier = following
    zones, zone_count = label((reach >= 1) & (reach <= ZEBRA + 1), EIGHT)
    arms = Counter(int(owner[tuple(np.argwhere(zones == k)[0])]) for k in range(1, zone_count + 1))
    crossings = []
    for k in range(1, zone_count + 1):
        cells = [tuple(c) for c in np.argwhere(zones == k)]
        ring = [c for c in cells if reach[c] == 1]
        far = [c for c in cells if reach[c] == ZEBRA + 1]
        if arms[int(owner[cells[0]])] < 3 or not ring or not far:
            continue
        # One heading for the whole crossing; a crossing skewed off the block grid has no clean bars.
        first = axes[cells[0]]
        heading = np.mean([axes[c] * (1 if axes[c] @ first >= 0 else -1) for c in cells], axis=0)
        if math.degrees(math.atan2(min(abs(heading)), max(abs(heading)))) > ZEBRA_SKEW:
            continue
        along = 1 if abs(heading[0]) >= abs(heading[1]) else 0       # index of the row coordinate in (iz, ix)
        across = 1 - along
        sign = 1 if np.mean([c[along] for c in far]) > np.mean([c[along] for c in ring]) else -1
        middle = int(round(np.mean([c[across] for c in cells])))
        start = max(sign * c[along] for c in ring)

        def row(signed):
            found = []
            for step in (1, -1):
                lateral = middle if step == 1 else middle - 1
                while True:
                    c = (signed * sign, lateral) if along == 0 else (lateral, signed * sign)
                    if not inside(*c) or not road[c] or junction[c]:
                        break
                    found.append(c)
                    lateral += step
            return found
        town = town_segment.get(int(segments[far[0]]), False)
        rows = [row(start + i) for i in range(ZEBRA + 1)] if town else [row(start)]
        if min(map(len, rows)) < 4:
            continue
        for c in cells:
            if reach[c] <= ZEBRA + 1 and (town or sign * c[along] <= start):
                marks.pop(c, None)
                kinds.pop(c, None)
        stripes, cross = ('north', 'east') if along == 0 else ('east', 'north')
        if town:
            for cells_ in rows[:-1]:
                for c in cells_:
                    marks[c], kinds[c] = (108, stripes, WHITE), 'zebra'
        # The stop line crosses the inbound lane: keep left, travelling towards the junction.
        travel = (-sign, 0) if along == 0 else (0, -sign)             # (dz, dx)
        left = (-travel[1], travel[0])                                # (dz, dx), left of travel with z south
        centre_line = np.mean([c[across] for c in rows[-1]])
        for c in rows[-1]:
            if (c[across] - centre_line) * left[across] > 0:
                marks[c], kinds[c] = (1, cross, WHITE), 'stop'
            else:
                marks.pop(c, None)
                kinds.pop(c, None)
        crossings.append(dict(zone=k, facing=stripes, town=bool(town)))
    real = [b for b, n in arms.items() if n >= 3]
    share = mean(town_cells, blobs, real) if real else []
    places = center_of_mass(junction, blobs, real) if real else []
    junctions = [dict(ix=int(p[1]), town=bool(t > .5)) for p, t in zip(places, share)]
    return dict(marks=marks, kinds=kinds, segments=segments, town_segment=town_segment, crossings=crossings, junctions=junctions)


def junction_tally(planned, x0):
    """Junctions, town junctions and painted crossings, overall and per 1024 blocks of x."""
    areas = {}

    def add(x, key):
        area = areas.setdefault((x + x0) // TALLY_WIDTH * TALLY_WIDTH, Counter())
        area[key] += 1
    for j in planned['junctions']:
        add(j['ix'], 'junctions')
        if j['town']:
            add(j['ix'], 'town_junctions')
    for (iz, ix), kind in planned['kinds'].items():
        if kind in ('zebra', 'stop'):
            add(ix, kind + '_cells')
    total = Counter()
    for area in areas.values():
        total.update(area)
    return dict({k: total[k] for k in ('junctions', 'town_junctions', 'zebra_cells', 'stop_cells')}, by_area={str(k): dict(v) for k, v in sorted(areas.items())})


def built_up(source, x0, z0, x1, z1):
    """Columns with something built on them, read from the world: the catalogue lists only some buildings."""
    sx, sz = source.bounds[:2]
    window = np.s_[z0 - sz:z1 - sz + 1, x0 - sx:x1 - sx + 1]
    top, highest, full = (source.measured[k][window].astype(int) for k in ('top', 'highest', 'full'))
    built = np.zeros(top.shape, bool)
    for iz, ix in np.argwhere((full > 0) & (highest >= top + 3) & (top > -120)):
        name = source.state(int(ix + x0), int(highest[iz, ix]), int(iz + z0)).split('[')[0]
        built[iz, ix] = not name.endswith(('_leaves', '_log')) and name not in ('minecraft:water', 'minecraft:barrier', 'minecraft:vine', 'minecraft:snow')
    return built


def convert(a):
    spec = read(a.config)
    source = CapturedSurface(spec['source'], partial=True)
    sx, sz, sX, sZ = source.bounds
    x0, z0, x1, z1 = spec.get('bounds', [sx, sz, sX, sZ])
    with np.load(spec['network']) as f:
        net = {k: f[k] for k in ('walk', 'road', 'grade2', 'bounds')}
    ax, az = map(int, net['bounds'][:2])
    window = np.s_[z0 - az:z1 - az + 1, x0 - ax:x1 - ax + 1]
    walk, road, grade = net['walk'][window].copy(), net['road'][window] & net['walk'][window], net['grade2'][window].astype(int)
    full = source.measured['full'][z0 - sz:z1 - sz + 1, x0 - sx:x1 - sx + 1]
    walk &= full
    road &= walk
    # What is not road stays out of everything below: surfaces, kerbs and markings.
    volumes = read(spec['station_volumes'])
    keep = np.zeros(walk.shape, bool)
    for iz, ix in np.argwhere(walk):
        x, z, g = int(ix + x0), int(iz + z0), int(grade[iz, ix])
        y = (g + 1) // 2
        names = [source.state(x, v, z).split('[')[0] for v in (y - 1, y, y + 1)]
        ours = (ROAD_FLOORS if road[iz, ix] else FOOT_FLOORS)
        # A station's box takes in the streets around it; only its footways are station floor.
        station = not road[iz, ix] and any(v[0] <= x <= v[3] and v[2] <= z <= v[5] and v[1] - 1 <= y <= v[4] for v in volumes)
        keep[iz, ix] = station or not (names[1] in ours or any(n.startswith('trafficcraft:') for n in names))
    kept = int(keep.sum())
    walk &= ~keep
    road &= walk
    joined = adjacency(walk, grade)
    height = 4 * grade + 8                     # eighths: grade2 is twice the foot height minus two
    surface = smooth(height, walk, joined)
    # Footways ride one layer over the carriageway beside them, so their steps line up with its
    # steps; a footway away from any carriageway rides one layer over its own surface.
    gap, near = distance_transform_edt(~road, return_indices=True)
    beside = walk & ~road & (gap <= 3) & (np.abs(height - height[tuple(near)]) <= DRIFT)
    surface = np.where(walk & ~road, np.where(beside, surface[tuple(near)], surface) + 1, surface)
    surface = np.clip(limit(surface, joined, walk & ~road, height - DRIFT), height - DRIFT, height + DRIFT)

    planned = plan_marks(road, walk | keep, built_up(source, x0, z0, x1, z1))   # a kept footway is still a kerb
    marks = planned['marks']

    rows, skipped = {}, Counter()
    paint = {tuple(int(d[k]) for k in 'xyz'): int(d.get('color', -1)) for d in source.devices if str(d.get('id')) == ENTITY}

    def put(x, y, z, state, purpose, entity=None):
        before = source.state(x, y, z)
        if before == state and (entity is None or paint.get((x, y, z)) == entity):
            return True
        if before.split('[')[0] not in REPLACEABLE and not before.startswith('trafficcraft:'):
            skipped[before.split('[')[0]] += 1
            return False
        row = dict(pos=[x, y, z], before=before, after=state, purpose=purpose)
        if entity is not None:
            row['block_entity'] = dict(id=ENTITY, color=entity)
        rows[x, y, z] = row
        return True

    for iz, ix in np.argwhere(walk):
        x, z = int(ix + x0), int(iz + z0)
        g = int(grade[iz, ix])
        old_y = (g + 1) // 2                   # the block the current surface sits on
        h = int(surface[iz, ix])
        top, part = divmod(h, LAYERS)
        carriage = bool(road[iz, ix])
        solid = 'trafficcraft:asphalt' if carriage else 'trafficcraft:concrete'
        slope = 'trafficcraft:asphalt_slope' if carriage else 'trafficcraft:concrete_slope'
        mark = marks.get((iz, ix))
        # States are written in full, as the game saves them, so readbacks stay exact.
        base = top - 1
        for y in range(min(base, old_y), base):
            put(x, y, z, solid, 'road base')
        if part == 0:
            if mark:
                put(x, base, z, f'trafficcraft:asphalt_pattern_{mark[0]}[facing={mark[1]}]', 'road marking', mark[2])
            else:
                put(x, base, z, solid, 'road surface')
            cap = base + 1
        else:
            put(x, base, z, solid, 'road surface')
            if mark:
                put(x, top, z, f'trafficcraft:asphalt_slope_pattern_{mark[0]}[facing={mark[1]},layers={part},waterlogged=false]', 'road marking', mark[2])
            else:
                put(x, top, z, f'{slope}[layers={part},waterlogged=false]', 'road surface')
            cap = top + 1
        # The old surface may stand above the new one: clear what is left of it.
        for y in range(cap, old_y + 2):
            if paved(source.state(x, y, z)):
                put(x, y, z, 'minecraft:air', 'old surface removed')

    steps, steep = [], 0
    for axis in (0, 1):
        # A kerb between carriageway and footway is one layer more than the slope allows.
        ok = joined[axis][..., 0] & (road == np.roll(road, 1, axis))
        d = np.abs(surface - np.roll(surface, 1, axis))[ok]
        steps.append(int(d.max()) if len(d) else 0)
        steep += int((d > MAX_STEP).sum())
    moved = np.abs(surface - height)[walk]
    tally = junction_tally(planned, x0)
    errors = [f'Step over {STEEP_STEP} layers'] * (max(steps) > STEEP_STEP) + [f'Surface moved {int(moved.max())} layers'] * bool((moved > DRIFT).any())
    if tally['junctions'] >= MIN_JUNCTIONS and tally['town_junctions'] == 0:
        errors.append('No junction counted as town')
    if tally['town_junctions'] >= MIN_JUNCTIONS and tally['zebra_cells'] < MIN_ZEBRA * tally['town_junctions']:
        errors.append(f"{tally['zebra_cells']} zebra cells for {tally['town_junctions']} town junctions")
    report = dict(errors=errors, cells=len(rows), walk=int(walk.sum()), steep_steps=steep, surface_moved_layers={int(k): int(v) for k, v in zip(*np.unique(moved, return_counts=True))}, junctions=tally,
                  carriageway=int(road.sum()), markings=len(marks), marking_colours=dict(Counter(m[2] for m in marks.values())),
                  largest_step=max(steps), kept_as_built=kept, skipped=dict(skipped.most_common(12)), world_written=False)
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / 'conversion-check.json', report)
    write(a.out / 'patch.json', dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'],
          edits=[rows[k] for k in sorted(rows)], native_snapshot=spec['native_snapshot'], error_reports=[str(a.out / 'conversion-check.json')],
          views_reviewed_by_root=False, continuation_work=spec['continuation_work']))
    print(json.dumps({k: report[k] for k in ('errors', 'cells', 'walk', 'carriageway', 'kept_as_built', 'markings', 'marking_colours', 'largest_step', 'steep_steps', 'surface_moved_layers', 'junctions', 'skipped')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    convert(parser.parse_args())
