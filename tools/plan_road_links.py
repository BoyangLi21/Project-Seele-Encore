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
from plan_ashi_landscape_r54 import PLANTS, SOIL
from plan_rail_corridor import existing_track
from plan_station_access_corridor import CapturedSurface
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

SIDEWALK, HEADROOM, EARTHWORK_REACH = 1, 5, 6
MAX_GRADE = .08
# Half-slab steps climb half a block per block, which a player walks without jumping.
STEP_GRADE = .5
ROAD_WIDTH, FOOTWAY_WIDTH = 6, 2


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
            # Track at ground level is crossed on the level, with the road at rail height.
            crossing[at_grade] = rail_y[at_grade]
        for iz, ix in np.argwhere(full & (highest > top) & ~core & ~walk):
            x, z, ground = int(xx[iz, ix]), int(zz[iz, ix]), int(top[iz, ix])
            for y in range(ground + 1, min(int(highest[iz, ix]), ground + HEADROOM) + 1):
                name = capture.state(x, y, z)
                bare = name.split('[')[0]
                if 'water' in bare or 'waterlogged=true' in name:
                    core[iz, ix] = True
                    break
                if not natural(bare):
                    # Paving with headroom is ground a link may cross; anything else stands in the way.
                    grade = 2 * y - 1 if 'type=bottom' in name else 2 * y
                    if paved_floor(capture.state, x, z, grade, 2, uncover=True) is None:
                        core[iz, ix] = True
                    break
        passable = (distance_transform_edt(~core) >= need + 1) | walk
        near_centre = np.zeros(xx.shape, bool)
        c = self.centre_points
        inside = c[(c[:, 0] >= x0) & (c[:, 0] < x1 + 1) & (c[:, 1] >= z0) & (c[:, 1] < z1 + 1)]
        near_centre[(inside[:, 1] - z0).astype(int), (inside[:, 0] - x0).astype(int)] = True
        cost = 1 + 1.5 * (distance_transform_edt(~near_centre) > 4)
        cost = np.where(walk, .3, cost + 8 * np.isfinite(crossing))
        # Height in half blocks: a declared road's own grade, else the ground under foot.
        level = np.where(walk, self.grade[own] + 2, 2 * (top + 1))
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
        feet = np.interp(along, *zip(*pins))
        tree = cKDTree(samples)
        nearest = tree.query(np.c_[xx.ravel() + .5, zz.ravel() + .5])[1].reshape(xx.shape)
        height = np.ceil(feet[nearest] * 2 - 1e-9) / 2
        new_grade = np.rint(2 * (height - 1)).astype(np.int16)
        floor, slab = road_blocks(new_grade)
        top = source.measured['top'][bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1].astype(int)
        known = source.measured['full'][bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1]
        if not known[walk].all():
            errors.append([link['id'], 'Link leaves the capture'])
            continue
        blocked, adopted, built = Counter(), 0, 0
        def put(x, y, z, state, purpose):
            before = source.state(x, y, z)
            if not natural(before.split('[')[0]):
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
        d, near = distance_transform_edt(~walk, return_indices=True)
        base = (floor - 1)[tuple(near)]
        target = np.rint(np.clip(top, base - d * .5, base + d * .5)).astype(int)
        for iz, ix in np.argwhere((target != top) & (d <= EARTHWORK_REACH) & ~walk & ~old_walk & known):
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
            column = [(yy, 'minecraft:stone', 'link bearing') for yy in range(min(int(top[iz, ix]) - 1, y - 1), y)]
            column += [(yy, 'minecraft:air', 'link headroom') for yy in range(y + 1, y + HEADROOM + 1) if source.state(x, yy, z).split('[')[0] not in EMPTY]
            column.append((y, state, 'link carriageway' if on_road else 'link footway'))
            # A column that meets a structure is left whole and stays undeclared; the joint
            # check below decides whether the link still connects around it.
            stuck = [source.state(x, yy, z).split('[')[0] for yy, _, _ in column]
            stuck = [name for name in stuck if not natural(name)]
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('route', 'edits'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args()
    globals()[arguments.mode](arguments)
