"""Join separated public road components.

`route` reads an installed public-route audit, picks the links that join its components
with a height-aware spanning tree and routes each one on the ground grid around
buildings, stations, at-grade track and water, preferring surveyed road centrelines.
A link too steep for a road becomes a stepped footway. `edits` turns the links into a
cell patch and the next planning network. Existing paving at the right height is
declared as it stands; only soil and plants are moved, and a link that meets a
structure is reported, never forced through.
"""
import argparse
from collections import Counter
import gzip
import json
import math
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra, minimum_spanning_tree
from scipy.spatial import cKDTree
import shapely
from shapely.geometry import LineString

from hakone_earthworks import road_blocks
from map_pipeline.road_crossings import TRACKBED, real_level_crossings
from plan_ashi_landscape_r54 import PLANTS, SOIL
from plan_rail_corridor import existing_track
from plan_station_access_corridor import CapturedSurface
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

SIDEWALK, HEADROOM, EARTHWORK_REACH = 1, 5, 16
MAX_GRADE = .08
# Half-slab steps climb half a block per block, which a player walks without jumping.
STEP_GRADE = .5
ROAD_WIDTH, FOOTWAY_WIDTH = 6, 2
# Channels up to twice this wide are bridged; wider water is not crossed.
BRIDGE_HALF_SPAN = 6


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1), 'utf8')


def natural(name):
    return name in SOIL | PLANTS | AIR or name.endswith(('_leaves', '_log'))


# What the audit accepts as headroom: street lights and short grass do not block a route.
EMPTY = AIR | {'minecraft:light', 'minecraft:grass', 'minecraft:tall_grass', 'minecraft:fern'}


def paved_floor(state, x, z, want, clearance, uncover=False):
    """Paving within half a block of `want` as (grade, floor y), else None.

    Its headroom must be clear, or with `uncover` only soil and plants that can be dug off:
    a later terrain pass buried stretches of older road under a block or two of ground.
    """
    for y in range(max(-127, (want + 1) // 2 - 1), min(312, (want + 1) // 2 + 2)):
        name = state(x, y, z)
        bare = name.split('[')[0]
        if bare not in PAVEMENT:
            continue
        grade = 2 * y - 1 if 'type=bottom' in name else 2 * y
        above = [state(x, y + k, z).split('[')[0] for k in range(1, clearance + 1)]
        if abs(grade - want) <= 1 and all(n in EMPTY or (uncover and natural(n)) for n in above):
            return grade, y
    return None


class Ground:
    """Routing context: audit components, captures, buildings, track and surveyed roads."""

    def __init__(self, spec):
        self.spec = spec
        with np.load(Path(spec['audit']) / 'actual-routes.npz') as f:
            self.ax, self.az = map(int, f['bounds'][:2])
            self.component, xs, zs, grades, roads = f['component'], f['x'], f['z'], f['grade2'], f['road']
        self.grade = np.full(self.component.shape, -9999, np.int32)
        self.grade[zs - self.az, xs - self.ax] = grades
        labels = self.component[zs - self.az, xs - self.ax]
        ids, sizes = np.unique(labels[labels >= 0], return_counts=True)
        self.size = dict(zip(ids.tolist(), sizes.tolist()))
        self.kept = [int(k) for k in ids[sizes >= spec.get('minimum_columns', 300)]]
        self.points = {k: np.c_[xs[labels == k], zs[labels == k], grades[labels == k] / 2 + 1] for k in self.kept}
        self.carries_traffic = {k: bool(roads[labels == k].any()) for k in self.kept}
        self.captures = [CapturedSurface(s, partial=True) for s in spec['sources']]
        # Station volumes are not walls: platforms and forecourts inside them are reached on foot,
        # and their real structures are found block by block like any other.
        self.blocks = [r['occupied_bounds'] for r in read(Path(spec['authority']) / 'catalog.json') if r.get('occupied_bounds')]
        centrelines = []
        for features in spec['features']:
            with gzip.open(features, 'rt', encoding='utf8') as stream:
                for row in json.load(stream)['features']:
                    if row['properties'].get('source_layer') == 'RdCL':
                        g = row['geometry']
                        centrelines += [np.array(p) for p in ([g['coordinates']] if g['type'] == 'LineString' else g['coordinates'])]
        self.centre_points = np.vstack([np.vstack([p[0] + (p[1] - p[0]) * t for t in np.linspace(0, 1, max(2, int(np.linalg.norm(p[1] - p[0])) + 1))])
                                        for line in centrelines for p in zip(line[:-1], line[1:])])
        self.level_crossings = real_level_crossings(spec['features'], spec['native_snapshot'], spec.get('crossing_snap', 12))

    def capture(self, lo, hi):
        return next((c for c in self.captures if c.bounds[0] <= lo[0] and c.bounds[1] <= lo[1] and c.bounds[2] >= hi[0] and c.bounds[3] >= hi[1]), None)

    def grid(self, lo, hi, capture, need):
        """Passability, step cost, height, component and level-crossing height over a window.

        Existing declared roads always pass; elsewhere a link keeps `need` clear of buildings,
        water and structures.
        """
        (x0, z0), (x1, z1) = lo, hi
        cx, cz, _, _ = capture.bounds
        cut = np.s_[z0 - cz:z1 - cz + 1, x0 - cx:x1 - cx + 1]
        top, highest = (capture.measured[k][cut].astype(int) for k in ('top', 'highest'))
        full = capture.measured['full'][cut]
        own = np.s_[z0 - self.az:z1 - self.az + 1, x0 - self.ax:x1 - self.ax + 1]
        comp = self.component[own]
        walk = comp >= 0
        zz, xx = np.mgrid[z0:z1 + 1, x0:x1 + 1]
        # A column without captured soil is a void or a solid structure, not ground.
        core = ~full | (top < -120)
        for b in self.blocks:
            core[max(0, b[2] - z0):max(0, b[5] - z0 + 1), max(0, b[0] - x0):max(0, b[3] - x0 + 1)] = True
        tracks, heights = existing_track(self.spec['native_snapshot'], shapely.box(x0 - 3, z0 - 3, x1 + 4, z1 + 4))
        crossing = np.full(xx.shape, np.nan)
        if tracks is not None:
            gap, near = tracks.query(np.c_[xx.ravel() + .5, zz.ravel() + .5])
            rail_y = heights[near].reshape(xx.shape)
            at_grade = (gap.reshape(xx.shape) < 2.5) & (rail_y >= top - 3) & (rail_y <= top + 6)
            # Track at ground level is crossed on the level, with the road at rail height, and
            # only at a real level crossing: elsewhere the track is a wall, so a link neither
            # cuts across nor runs along it.
            window = np.zeros(xx.shape, bool)
            lc = self.level_crossings
            for wx, wz, _ in lc[(lc[:, 0] > x0 - 20) & (lc[:, 0] < x1 + 21) & (lc[:, 1] > z0 - 20) & (lc[:, 1] < z1 + 21)]:
                window |= np.hypot(xx + .5 - wx, zz + .5 - wz) <= need + 3
            crossing[at_grade & window] = rail_y[at_grade & window]
            core |= at_grade & ~window
        else:
            window = np.zeros(xx.shape, bool)
        wet = np.full(xx.shape, -9999)
        for iz, ix in np.argwhere(full & (highest > top) & ~core & ~walk):
            x, z, ground = int(xx[iz, ix]), int(zz[iz, ix]), int(top[iz, ix])
            for y in range(ground + 1, min(int(highest[iz, ix]), ground + HEADROOM) + 1):
                name = capture.state(x, y, z)
                bare = name.split('[')[0]
                if 'water' in bare or 'waterlogged=true' in name:
                    surface = y
                    while 'water' in capture.state(x, surface + 1, z):
                        surface += 1
                    wet[iz, ix] = surface
                    break
                if window[iz, ix] and bare in TRACKBED:
                    continue
                if not natural(bare):
                    # Paving with headroom is ground a link may cross; anything else stands in the way.
                    grade = 2 * y - 1 if 'type=bottom' in name else 2 * y
                    if paved_floor(capture.state, x, z, grade, 2, uncover=True) is None:
                        core[iz, ix] = True
                    break
        # A narrow channel is bridged with the deck one block over the water; wide water stays out.
        water = wet > -9999
        narrow = water & (distance_transform_edt(water) <= BRIDGE_HALF_SPAN)
        core |= water & ~narrow
        passable = (distance_transform_edt(~core) >= need + 1) | walk
        near_centre = np.zeros(xx.shape, bool)
        c = self.centre_points
        inside = c[(c[:, 0] >= x0) & (c[:, 0] < x1 + 1) & (c[:, 1] >= z0) & (c[:, 1] < z1 + 1)]
        near_centre[(inside[:, 1] - z0).astype(int), (inside[:, 0] - x0).astype(int)] = True
        cost = 1 + 1.5 * (distance_transform_edt(~near_centre) > 4)
        cost = np.where(walk, .3, cost + 8 * np.isfinite(crossing) + 3 * narrow)
        # Height in half blocks: a declared road's own grade, else the ground under foot, or a
        # deck over the water.
        level = np.where(walk, self.grade[own] + 2, np.where(narrow, 2 * (wet + 2), 2 * (top + 1)))
        return passable, cost, level, comp, crossing

    def link(self, p, q, start, finish):
        """Route one link between components p and q, as a road if both carry traffic, else a footway."""
        plan = float(np.linalg.norm(start[:2] - finish[:2]))
        rise = abs(float(start[2] - finish[2]))
        row = dict(components=[p, q], sizes=[self.size[p], self.size[q]], plan=round(plan, 1), rise=round(rise, 1),
                   start=[float(v) for v in start], finish=[float(v) for v in finish])
        margin = int(np.clip(max(40, plan * .6, rise / MAX_GRADE * .5), 40, 300))
        lo = np.minimum(start[:2], finish[:2]).astype(int) - margin
        hi = np.maximum(start[:2], finish[:2]).astype(int) + margin
        capture = self.capture(lo + margin - 8, hi - margin + 8)
        if capture is None:
            return dict(row, error='No capture holds the link')
        lo, hi = np.maximum(lo, capture.bounds[:2]), np.minimum(hi, capture.bounds[2:])
        found = None
        for footway in (False, True):
            if not footway and not (self.carries_traffic[p] and self.carries_traffic[q]):
                continue
            width = FOOTWAY_WIDTH if footway else ROAD_WIDTH
            passable, cost, level, comp, crossing = self.grid(lo, hi, capture, width / 2 + SIDEWALK)
            shape_ = passable.shape
            ids_ = np.full(shape_, -1, np.int64)
            ids_[passable] = np.arange(int(passable.sum()))
            u, v, w = [], [], []
            for dz, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
                aa = np.s_[0:shape_[0] - dz, max(0, -dx):shape_[1] - max(0, dx)]
                bb = np.s_[dz:shape_[0], max(0, dx):shape_[1] + min(0, dx)]
                step_rise = np.abs(level[aa] - level[bb])
                paved = (comp[aa] >= 0) & (comp[bb] >= 0)
                leaving = (comp[aa] >= 0) != (comp[bb] >= 0)
                # Two declared roads join only within half a block, as the audit counts them. A
                # link leaves a raised platform or road on fill, but not a bridge deck, and
                # crosses ground no steeper than a three-block bank.
                ok = (ids_[aa] >= 0) & (ids_[bb] >= 0) & np.where(paved, step_rise <= 1, step_rise <= np.where(leaving, 16, 6))
                u.append(ids_[aa][ok])
                v.append(ids_[bb][ok])
                w.append(math.hypot(dz, dx) * (cost[aa][ok] + cost[bb][ok]) / 2 + .25 * step_rise[ok] * ~paved[ok])
            u, v, w = map(np.concatenate, (u, v, w))
            graph = coo_matrix((np.r_[w, w] + 1e-3, (np.r_[u, v], np.r_[v, u])), shape=(int(passable.sum()),) * 2).tocsr()
            sources, targets = ids_[(comp == p) & passable], ids_[(comp == q) & passable]
            if not len(sources) or not len(targets):
                continue
            dist, previous, _ = dijkstra(graph, indices=sources, min_only=True, return_predecessors=True)
            end = targets[int(np.argmin(dist[targets]))]
            if not np.isfinite(dist[end]):
                continue
            cells = np.argwhere(passable)
            chain = [int(end)]
            while previous[chain[-1]] >= 0:
                chain.append(int(previous[chain[-1]]))
            path = cells[chain[::-1]]
            owner = comp[path[:, 0], path[:, 1]]
            first_b = int(np.argmax(owner == q))
            last_a = int(np.nonzero(owner[:first_b] == p)[0][-1])
            gap = path[last_a:first_b + 1]
            run = np.r_[0, np.cumsum(np.hypot(*np.diff(gap, axis=0).T))]
            length = float(run[-1])
            ends = [float(self.grade[c[0] + lo[1] - self.az, c[1] + lo[0] - self.ax]) / 2 + 1 for c in (gap[0], gap[-1])]
            rails = [(float(s_), float(crossing[c[0], c[1]]), c) for s_, c in zip(run, gap) if np.isfinite(crossing[c[0], c[1]])]
            pins = [(0.0, ends[0])] + [(s_, y) for s_, y, _ in rails] + [(length, ends[1])]
            grade = max(abs(b[1] - a_[1]) / max(1.0, b[0] - a_[0]) for a_, b in zip(pins, pins[1:]))
            kind = 'Footway' if footway else 'Road'
            if grade <= (STEP_GRADE if footway else self.spec.get('max_grade', MAX_GRADE)):
                line = LineString(gap[:, ::-1] + lo + .5)
                return dict(row, footway=footway, width=width, length=round(length, 1), ends=ends, grade=round(grade, 3), points=line.simplify(.5).coords[:], source=str(capture.source),
                            crossings=[[int(c[1] + lo[0]), int(c[0] + lo[1]), y] for _, y, c in rails])
            found = dict(row, error=f'{kind} grade {grade:.2f} over {length:.0f} m')
        return found or dict(row, error='No passable route')


def water_surface(source, x, z):
    """Top water block over the ground of a column, or None for a dry column."""
    bx, bz, _, _ = source.bounds
    y = int(source.measured['top'][z - bz, x - bx]) + 1
    try:
        if 'water' not in source.state(x, y, z):
            return None
    except ValueError:
        return None
    while 'water' in source.state(x, y + 1, z):
        y += 1
    return y


def ground_profile(source, samples, along, pins, grade):
    """Feet height along a link: as close to the ground as the grade allows, through every pin.

    A straight line between the ends would stand the road on a bank or sink it in a cut
    wherever the ground dips or rises between them.
    """
    bx, bz, _, _ = source.bounds
    if along[-1] > 8:
        # A short landing at each end meets the existing road at its own height.
        pins = sorted(pins + [(2.0, pins[0][1]), (float(along[-1]) - 2, pins[-1][1])])
    ground = []
    for x, z in samples:
        x, z = int(np.floor(x)), int(np.floor(z))
        surface = water_surface(source, x, z)
        # Over water the deck lies one block above the surface: feet two above it.
        ground.append(source.measured['top'][z - bz, x - bx] + 1 if surface is None else surface + 2)
    ground = np.array(ground, float)
    pin_s, pin_y = map(np.array, zip(*pins))
    upper = np.min(pin_y[None, :] + grade * np.abs(along[:, None] - pin_s[None, :]), axis=1)
    lower = np.max(pin_y[None, :] - grade * np.abs(along[:, None] - pin_s[None, :]), axis=1)
    feet = np.clip(ground, lower, upper)
    step = grade * .5
    for _ in range(2):
        for i in range(1, len(feet)):
            feet[i] = np.clip(feet[i], feet[i - 1] - step, feet[i - 1] + step)
        for i in range(len(feet) - 2, -1, -1):
            feet[i] = np.clip(feet[i], feet[i + 1] - step, feet[i + 1] + step)
    for s_, y in pins:
        feet[int(round(s_ / .5))] = y
    return feet


def route(a):
    spec = read(a.config)
    ground = Ground(spec)
    kept, points = ground.kept, ground.points
    trees = {k: cKDTree(v[:, :2]) for k, v in points.items()}
    # A pair costs the longer of its plan gap and the run its rise needs, so two roads
    # stacked on a bridge are not mistaken for neighbours.
    search = spec.get('search_grade', .25)
    best = {}
    for i, p in enumerate(kept):
        sample = points[p][::2]
        for q in kept[i + 1:]:
            d, k = trees[q].query(sample[:, :2], k=24, distance_upper_bound=600)
            ok = np.isfinite(d)
            if not ok.any():
                continue
            rise = np.abs(sample[:, 2, None] - points[q][np.minimum(k, len(points[q]) - 1), 2])
            cost = np.where(ok, np.maximum(d, rise / search), np.inf)
            n = np.unravel_index(np.argmin(cost), cost.shape)
            best[p, q] = (float(cost[n]), sample[n[0]], points[q][k[n]])
    index = {k: i for i, k in enumerate(kept)}
    r, c, w = zip(*[(index[p], index[q], v[0] + .01) for (p, q), v in best.items()])
    tree = minimum_spanning_tree(coo_matrix((w, (r, c)), shape=(len(kept), len(kept)))).tocoo()
    links = []
    for i, j in zip(tree.row, tree.col):
        p, q = sorted((kept[i], kept[j]))
        _, start, finish = best[p, q]
        links.append(dict(id=f'link-{len(links)}', **ground.link(p, q, start, finish)))
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / 'links.json', links)
    print(json.dumps(dict(links=len(links), routed=sum('points' in q for q in links), footways=sum(bool(q.get('footway')) for q in links),
                          errors=Counter(q['error'].split(' ')[0] for q in links if 'error' in q)), ensure_ascii=False))


def edits(a):
    spec = read(a.config)
    source = CapturedSurface(spec['source'], partial=True)
    # Each link is built from the capture it was routed on.
    links = [q for q in read(spec['links']) if 'points' in q and Path(q['source']) == Path(spec['source'])]
    # A run over a second capture continues from the first run's network.
    with np.load(spec.get('network', Path(spec['authority']) / 'network.npz')) as f:
        network = {k: f[k].copy() for k in f.files}
    ax, az, _, _ = map(int, network['bounds'])
    sx, sz, sX, sZ = source.bounds
    catalog = read(Path(spec['authority']) / 'catalog.json')
    volumes = read(Path(spec['authority']) / 'station-volumes.json')
    report, errors, writes = [], [], {}
    # Cells a pending batch owns (planned river channels) are never written, and a link does
    # not lay its road on a column that is to become water; it waits for that batch.
    keep_out = set(map(tuple, np.load(spec['keep_out']).tolist())) if spec.get('keep_out') else set()
    wet = set(map(tuple, np.load(spec['keep_out_columns']).tolist())) if spec.get('keep_out_columns') else set()
    for link in links:
        line = LineString(link['points'])
        width = link['width']
        area = line.buffer(width / 2, cap_style=2)
        wide = area.buffer(SIDEWALK)
        x0, z0, x1, z1 = wide.buffer(EARTHWORK_REACH + 2).bounds
        if x0 < sx or x1 > sX + 1 or z0 < sz or z1 > sZ + 1:
            errors.append([link['id'], 'Link leaves the capture'])
            continue
        bx, bz, bX, bZ = max(sx, math.floor(x0)), max(sz, math.floor(z0)), min(sX, math.ceil(x1)), min(sZ, math.ceil(z1))
        zz, xx = np.mgrid[bz:bZ + 1, bx:bX + 1]
        cells = shapely.box(xx, zz, xx + 1, zz + 1)
        shapely.prepare(area)
        shapely.prepare(wide)
        road, walk = shapely.intersects(area, cells), shapely.intersects(wide, cells)
        window = np.s_[bz - az:bZ - az + 1, bx - ax:bX - ax + 1]
        old_walk = network['walk'][window].copy()
        samples = np.array([line.interpolate(float(d)).coords[0] for d in np.arange(0, line.length + .5, .5)])
        along = np.arange(len(samples)) * .5
        pins = sorted([(0.0, link['ends'][0]), (float(along[-1]), link['ends'][1])]
                      + [(line.project(shapely.Point(x + .5, z + .5)), y) for x, z, y in link['crossings']])
        feet = ground_profile(source, samples, along, pins, STEP_GRADE if link['footway'] else spec.get('max_grade', MAX_GRADE))
        tree = cKDTree(samples)
        nearest = tree.query(np.c_[xx.ravel() + .5, zz.ravel() + .5])[1].reshape(xx.shape)
        height = np.ceil(feet[nearest] * 2 - 1e-9) / 2
        new_grade = np.rint(2 * (height - 1)).astype(np.int16)
        # Cells on the inside of a sharp bend take heights from both legs; raise any cell more
        # than half a block below a neighbour so every step stays walkable.
        while True:
            masked = np.where(walk, new_grade, -32000).astype(np.int32)
            reach = masked.copy()
            reach[1:, :] = np.maximum(reach[1:, :], masked[:-1, :] - 1)
            reach[:-1, :] = np.maximum(reach[:-1, :], masked[1:, :] - 1)
            reach[:, 1:] = np.maximum(reach[:, 1:], masked[:, :-1] - 1)
            reach[:, :-1] = np.maximum(reach[:, :-1], masked[:, 1:] - 1)
            raise_ = walk & (reach > masked)
            if not raise_.any():
                break
            new_grade[raise_] = reach[raise_]
        floor, slab = road_blocks(new_grade)
        top = source.measured['top'][bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1].astype(int)
        known = source.measured['full'][bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1]
        if not known[walk].all():
            errors.append([link['id'], 'Link leaves the capture'])
            continue
        blocked, adopted, built = Counter(), 0, 0
        # The crossing deck replaces ballast under the rails; the rails themselves are native data.
        deck = {(int(x + dx), int(z + dz)) for x, z, _ in link['crossings'] for dx in range(-4, 5) for dz in range(-4, 5)}
        def replaceable(x, z, name):
            return natural(name) or ((x, z) in deck and name in TRACKBED)
        def put(x, y, z, state, purpose):
            if (x, y, z) in keep_out:
                if purpose != 'link earthworks':
                    blocked['planned water'] += 1
                return
            before = source.state(x, y, z)
            if not replaceable(x, z, before.split('[')[0]):
                # Grading simply stops at a structure; only the road itself may not pass one.
                if purpose != 'link earthworks':
                    blocked[before.split('[')[0]] += 1
                return
            if before != state:
                writes[x, y, z] = dict(pos=[x, y, z], before=before, after=state, purpose=purpose)
        build = walk & ~old_walk
        for iz, ix in np.argwhere(build):
            x, z = int(xx[iz, ix]), int(zz[iz, ix])
            clearance = 4 if road[iz, ix] and not link['footway'] else 2
            found = paved_floor(source.state, x, z, int(new_grade[iz, ix]), clearance, uncover=True)
            if found is not None:
                # Paving already at this height is part of the link as it stands, dug out if buried.
                grade, y = found
                for yy in range(y + 1, y + HEADROOM + 1):
                    name = source.state(x, yy, z).split('[')[0]
                    if name not in EMPTY and natural(name):
                        put(x, yy, z, 'minecraft:air', 'link uncovered')
                build[iz, ix] = False
                adopted += 1
                network['walk'][iz + bz - az, ix + bx - ax] = True
                network['road'][iz + bz - az, ix + bx - ax] = bool(road[iz, ix]) and not link['footway']
                network['grade2'][iz + bz - az, ix + bx - ax] = grade
        # Declared roads the link joins may lie under a later layer of soil; the audit counts
        # them as open, a player meets a wall. Dig them out where the link reaches them.
        old_grade = network['grade2'][window]
        for iz, ix in np.argwhere(walk & old_walk):
            x, z = int(xx[iz, ix]), int(zz[iz, ix])
            feet = int(old_grade[iz, ix]) // 2 + 1
            for yy in range(feet, feet + (4 if road[iz, ix] else 2) + (old_grade[iz, ix] % 2)):
                name = source.state(x, yy, z).split('[')[0]
                if name not in EMPTY and natural(name) and not name.endswith(('_leaves', '_log')):
                    put(x, yy, z, 'minecraft:air', 'link uncovered')
        d, near = distance_transform_edt(~walk, return_indices=True)
        base = (floor - 1)[tuple(near)]
        target = np.rint(np.clip(top, base - d * .5, base + d * .5)).astype(int)
        # Wider slopes for deep cuts and fills, but never against a building or a protected column:
        # grading next to them would leave a foundation on a cliff.
        guarded = source.measured['protected'][bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1].copy()
        for b in catalog:
            ob = b.get('occupied_bounds')
            if ob:
                guarded[max(0, ob[2] - bz):max(0, ob[5] - bz + 1), max(0, ob[0] - bx):max(0, ob[3] - bx + 1)] = True
        guarded = distance_transform_edt(~guarded) <= 2
        dry = np.array([[water_surface(source, int(x), int(z)) is None for x, z in zip(rx, rz)] for rx, rz in zip(xx, zz)]) if ((target != top) & (d <= EARTHWORK_REACH)).any() else np.ones(xx.shape, bool)
        for iz, ix in np.argwhere((target != top) & (d <= EARTHWORK_REACH) & ~walk & ~old_walk & known & ~guarded & dry):
            x, z, old, new = int(xx[iz, ix]), int(zz[iz, ix]), int(top[iz, ix]), int(target[iz, ix])
            for y in range(min(old, new) - 2, max(old, new) + 1):
                put(x, y, z, 'minecraft:air' if y > new else 'minecraft:grass_block[snowy=false]' if y == new else 'minecraft:dirt' if y >= new - 2 else 'minecraft:stone', 'link earthworks')
        centre = np.floor(samples).astype(int)
        stroke = {(int(p[0]), int(p[1])) for p, s in zip(centre, along) if int(s // 6) % 2 == 0} if not link['footway'] else set()
        for iz, ix in np.argwhere(build):
            x, z, y = int(xx[iz, ix]), int(zz[iz, ix]), int(floor[iz, ix])
            on_road = bool(road[iz, ix]) and not link['footway']
            if slab[iz, ix]:
                state = ('projectseele:road_marking_slab' if (x, z) in stroke else 'projectseele:road_asphalt_slab' if on_road else 'minecraft:smooth_stone_slab') + '[type=bottom,waterlogged=false]'
            else:
                state = 'minecraft:white_concrete' if (x, z) in stroke else 'minecraft:black_concrete' if on_road else 'minecraft:smooth_stone'
            surface = water_surface(source, x, z)
            if surface is not None and y <= surface:
                blocked['deck below water'] += 1
                continue
            # Over water the deck stands alone; filling under it would dam the channel.
            # Only empty or plant-filled cells under the deck need fill; any solid block already
            # there, old paving included, carries it as it is.
            column = [] if surface is not None else [(yy, 'minecraft:stone', 'link bearing') for yy in range(min(int(top[iz, ix]) - 1, y - 1), y)
                                                     if source.state(x, yy, z).split('[')[0] in EMPTY | PLANTS or source.state(x, yy, z).split('[')[0].endswith(('_leaves', '_log'))]
            # A road in cutting is open to the sky: clearing only its headroom would leave a lid of
            # ground over it.
            column += [(yy, 'minecraft:air', 'link headroom') for yy in range(y + 1, max(y + HEADROOM, int(top[iz, ix])) + 1)
                       if source.state(x, yy, z).split('[')[0] not in EMPTY]
            column.append((y, state, 'link carriageway' if on_road else 'link footway'))
            # A column that meets a structure is left whole and stays undeclared; the joint
            # check below decides whether the link still connects around it.
            stuck = [source.state(x, yy, z).split('[')[0] for yy, _, _ in column]
            stuck = [name for name in stuck if not replaceable(x, z, name)]
            if (x, z) in wet or any((x, yy, z) in keep_out for yy, _, _ in column):
                stuck.append('planned water')
            if stuck:
                blocked.update(stuck)
                continue
            for yy, block, purpose in column:
                put(x, yy, z, block, purpose)
            built += 1
            network['walk'][iz + bz - az, ix + bx - ax] = True
            network['road'][iz + bz - az, ix + bx - ax] = on_road
            network['grade2'][iz + bz - az, ix + bx - ax] = new_grade[iz, ix]
        # Height-aware joint check on the new network around the link, as the audit counts it.
        new_walk, grades = network['walk'][window], network['grade2'][window].astype(np.int32)
        nodes = np.full(new_walk.shape, -1, np.int64)
        nodes[new_walk] = np.arange(int(new_walk.sum()))
        u, v = [], []
        for dz, dx in ((0, 1), (1, 0)):
            aa, bb = np.s_[0:nodes.shape[0] - dz, 0:nodes.shape[1] - dx], np.s_[dz:nodes.shape[0], dx:nodes.shape[1]]
            ok = (nodes[aa] >= 0) & (nodes[bb] >= 0) & (np.abs(grades[aa] - grades[bb]) <= 1)
            u.append(nodes[aa][ok])
            v.append(nodes[bb][ok])
        u, v = np.concatenate(u), np.concatenate(v)
        _, parts = connected_components(coo_matrix((np.ones(len(u)), (u, v)), shape=(int(new_walk.sum()),) * 2), directed=False)
        ends_ = [nodes[int(p[1]) - bz, int(p[0]) - bx] for p in (link['points'][0], link['points'][-1])]
        joined = min(ends_) >= 0 and parts[ends_[0]] == parts[ends_[1]]
        footprint = shapely.buffer(line, width / 2 + SIDEWALK)
        structures = [r.get('id') for r in catalog if r.get('occupied_bounds') and footprint.intersects(shapely.box(r['occupied_bounds'][0], r['occupied_bounds'][2], r['occupied_bounds'][3] + 1, r['occupied_bounds'][5] + 1))]
        stations = [v for v in volumes if footprint.intersects(shapely.box(v[0], v[2], v[3] + 1, v[5] + 1))]
        report.append(dict(id=link['id'], components=link['components'], footway=link['footway'], length=link['length'], ends=link['ends'], grade=link['grade'],
                           built=built, adopted=adopted, joined=bool(joined), blocked=dict(blocked), structures=structures[:4], stations=len(stations)))
        if not joined:
            errors.append([link['id'], dict(blocked=dict(blocked), structures=structures[:4], joined=False)])
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / 'link-check.json', dict(errors=errors, links=report, cells=len(writes), world_written=False))
    np.savez_compressed(a.out / 'network.npz', **network)
    write(a.out / 'patch.json', dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'], edits=list(writes.values()),
          native_snapshot=spec['native_snapshot'], error_reports=[str(a.out / 'link-check.json')], views_reviewed_by_root=False, continuation_work=spec['continuation_work']))
    print(json.dumps(dict(cells=len(writes), links=len(report), errors=len(errors)), ensure_ascii=False))


def steps(a):
    """Half-slab steps where two declared roads meet across a one-block curb.

    The audit joins neighbours within half a block, so a kerb a full block high splits two
    roads that touch. A bottom slab on the lower side halves the step both ways. Only the
    lower cell changes, only onto a full floor with clear headroom, and the next planning
    network carries the new half-block height.
    """
    spec = read(a.config)
    sources = [CapturedSurface(s, partial=True) for s in spec['sources']]
    with np.load(Path(spec['audit']) / 'actual-routes.npz') as f:
        ax, az = map(int, f['bounds'][:2])
        component, xs, zs, grades, roads = f['component'], f['x'], f['z'], f['grade2'], f['road']
    grade = np.full(component.shape, -9999, np.int32)
    grade[zs - az, xs - ax] = grades
    road = np.zeros(component.shape, bool)
    road[zs - az, xs - ax] = roads
    with np.load(spec.get('network', Path(spec['authority']) / 'network.npz')) as f:
        network = {k: f[k].copy() for k in f.files}
    nx_, nz_ = map(int, network['bounds'][:2])
    links = {q['id']: q for q in read(spec['links'])}

    def state(x, y, z):
        for c in sources:
            if c.bounds[0] <= x <= c.bounds[2] and c.bounds[1] <= z <= c.bounds[3]:
                return c.state(x, y, z), c
        raise ValueError(('Outside every capture', x, z))

    writes, report, errors = {}, [], []
    for link_id in spec['steps']:
        p, q = links[link_id]['components']
        rows = np.argwhere((component == p) | (component == q))
        placed, refused, sources_used = [], Counter(), set()
        for iz, ix in rows:
            for dz, dx in ((0, 1), (1, 0), (0, -1), (-1, 0), (0, 2), (2, 0), (0, -2), (-2, 0)):
                jz, jx = iz + dz, ix + dx
                if not (0 <= jz < component.shape[0] and 0 <= jx < component.shape[1]):
                    continue
                if {int(component[iz, ix]), int(component[jz, jx])} != {p, q}:
                    continue
                if grade[jz, jx] - grade[iz, ix] != 2:
                    continue
                # The step goes on the lower side, or on the one undeclared cell between them when
                # it stands at the lower height: a whole floor block with room above a slab.
                mz, mx = (iz + dz // 2, ix + dx // 2) if abs(dz) + abs(dx) == 2 else (iz, ix)
                if (mz, mx) != (iz, ix) and component[mz, mx] >= 0:
                    continue
                x, z = int(mx + ax), int(mz + az)
                feet = int(grade[iz, ix]) // 2 + 1
                if grade[iz, ix] % 2:
                    refused['lower side is already a slab'] += 1
                    continue
                floor_state, capture = state(x, feet - 1, z)
                if (mz, mx) != (iz, ix) and state(x, feet, z)[0].split('[')[0] not in EMPTY:
                    refused['middle cell is not at the lower height'] += 1
                    continue
                sources_used.add(str(capture.source))
                above = [state(x, feet + k, z)[0].split('[')[0] for k in range(3)]
                if floor_state.split('[')[0] in AIR or 'slab' in floor_state or 'stairs' in floor_state:
                    refused['no whole floor block'] += 1
                    continue
                if any(n not in EMPTY for n in above):
                    refused['no headroom over the step'] += 1
                    continue
                slab = 'projectseele:road_asphalt_slab' if road[iz, ix] and road[jz, jx] else 'minecraft:smooth_stone_slab'
                key = (x, feet, z)
                if key not in writes:
                    writes[key] = dict(pos=[x, feet, z], before=state(x, feet, z)[0], after=slab + '[type=bottom,waterlogged=false]', purpose='curb step')
                    network['grade2'][z - nz_, x - nx_] = grade[iz, ix] + 1
                    network['walk'][z - nz_, x - nx_] = True
                    placed.append([x, feet, z])
        report.append(dict(id=link_id, components=[p, q], steps=len(placed), refused=dict(refused), sources=sorted(sources_used)))
        if not placed:
            errors.append([link_id, 'No curb to step'])
    if len({tuple(r['sources']) for r in report if r['sources']}) > 1:
        errors.append(['Steps span several captures; split the config'])
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / 'steps-check.json', dict(errors=errors, links=report, cells=len(writes), world_written=False))
    np.savez_compressed(a.out / 'network.npz', **network)
    source = next((r['sources'][0] for r in report if r['sources']), spec['sources'][0])
    write(a.out / 'patch.json', dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=source, edits=list(writes.values()),
          native_snapshot=spec['native_snapshot'], error_reports=[str(a.out / 'steps-check.json')], views_reviewed_by_root=False, continuation_work=spec['continuation_work']))
    print(json.dumps(dict(cells=len(writes), links=[(r['id'], r['steps']) for r in report], errors=errors), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('route', 'edits', 'steps'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args()
    globals()[arguments.mode](arguments)
