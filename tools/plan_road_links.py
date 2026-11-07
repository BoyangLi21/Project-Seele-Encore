"""Join separated public road components along surveyed roads.

`route` reads an installed public-route audit, finds the shortest set of links that
joins its components and follows the real road centrelines between them. `edits`
turns chosen links into a cell patch and the next planning network. Only soil and
plants are moved; a link that meets a structure is reported, never forced through.
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
from scipy.sparse.csgraph import dijkstra, minimum_spanning_tree
from scipy.spatial import cKDTree
import shapely
from shapely.geometry import LineString, shape
from shapely.ops import unary_union

from hakone_earthworks import road_blocks
from map_pipeline.native_rails import load_rails
from plan_ashi_landscape_r54 import PLANTS, SOIL
from plan_station_access_corridor import CapturedSurface
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

SIDEWALK, HEADROOM, EARTHWORK_REACH, ATTACH = 1, 5, 6, 8
MAX_GRADE = .08
SHORT_RAMP, SHORT_GRADE = 8, .5


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1), 'utf8')


def road_graph(features):
    with gzip.open(features, 'rt', encoding='utf8') as stream:
        rows = json.load(stream)['features']
    nodes, edges = {}, []
    def node(point):
        return nodes.setdefault((round(point[0], 1), round(point[1], 1)), len(nodes))
    for row in rows:
        if row['properties'].get('source_layer') != 'RdCL':
            continue
        geometry = shape(row['geometry'])
        for part in getattr(geometry, 'geoms', [geometry]):
            points = list(part.coords)
            for a, b in zip(points, points[1:]):
                edges.append((node(a), node(b), math.dist(a, b)))
    coords = np.array(list(nodes))
    # Tiles cut centrelines, so ends a few metres apart are the same road.
    extra = [(i, j, float(np.linalg.norm(coords[i] - coords[j]))) for i, j in cKDTree(coords).query_pairs(3)]
    u, v, w = map(np.array, zip(*(edges + extra)))
    graph = coo_matrix((np.r_[w, w], (np.r_[u, v], np.r_[v, u])), shape=(len(coords), len(coords))).tocsr()
    return coords, graph


def route(a):
    spec = read(a.config)
    with np.load(Path(spec['audit']) / 'actual-routes.npz') as f:
        component, (ax, az, _, _) = f['component'], map(int, f['bounds'])
    labels, sizes = np.unique(component[component >= 0], return_counts=True)
    kept = labels[sizes >= spec.get('minimum_columns', 300)]
    points = {}
    for label_ in kept:
        zz, xx = np.nonzero(component == label_)
        points[int(label_)] = np.c_[xx + ax, zz + az]
    order = list(points)
    trees = {k: cKDTree(v) for k, v in points.items()}
    gaps, pairs = [], {}
    for i, p in enumerate(order):
        for j in range(i + 1, len(order)):
            d, k = trees[order[j]].query(points[p][::5])
            n = int(np.argmin(d))
            gaps.append((i, j, float(d[n]) + .01))
            pairs[i, j] = (points[p][::5][n].tolist(), points[order[j]][k[n]].tolist(), float(d[n]))
    r, c, w = map(np.array, zip(*gaps))
    tree = minimum_spanning_tree(coo_matrix((w, (r, c)), shape=(len(order), len(order)))).tocoo()
    coords, graph = road_graph(spec['features'])
    gis = cKDTree(coords)
    links = []
    for i, j in zip(tree.row, tree.col):
        i, j = min(i, j), max(i, j)
        start, finish, gap = pairs[i, j]
        near_a = np.unique(gis.query(points[order[i]][::3], distance_upper_bound=ATTACH)[1])
        near_b = np.unique(gis.query(points[order[j]][::3], distance_upper_bound=ATTACH)[1])
        near_a, near_b = near_a[near_a < len(coords)], near_b[near_b < len(coords)]
        path = None
        if len(near_a) and len(near_b):
            dist, previous, source_index = dijkstra(graph, indices=near_a, min_only=True, return_predecessors=True)
            end = near_b[int(np.argmin(dist[near_b]))]
            if np.isfinite(dist[end]) and dist[end] < spec.get('longest_detour', 4) * max(gap, 60):
                chain = [int(end)]
                while previous[chain[-1]] >= 0:
                    chain.append(int(previous[chain[-1]]))
                path = coords[chain[::-1]].tolist()
        links.append(dict(id=f'link-{len(links)}', gap=round(gap), start=start, finish=finish, sizes=[int(sizes[labels == order[i]][0]), int(sizes[labels == order[j]][0])],
                          surveyed=path is not None, points=path or [start, finish]))
    links.sort(key=lambda q: q['gap'])
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / 'links.json', links)
    print(len(links), 'links', sum(q['gap'] for q in links), 'm of gaps,', sum(q['surveyed'] for q in links), 'surveyed')


def edits(a):
    spec = read(a.config)
    source = CapturedSurface(spec['source'], partial=True)
    links = read(spec['links'])
    with np.load(Path(spec['authority']) / 'network.npz') as f:
        network = {k: f[k].copy() for k in f.files}
    ax, az, _, _ = map(int, network['bounds'])
    sx, sz, sX, sZ = source.bounds
    catalog = read(Path(spec['authority']) / 'catalog.json')
    volumes = read(Path(spec['authority']) / 'station-volumes.json')
    rails = [r for r in load_rails(spec['native_snapshot']) if r['mode'] == 'TRAIN']
    rows, report, errors, writes = [], [], [], {}
    for link in links:
        line = LineString(link['points'])
        samples = np.array([line.interpolate(float(d)).coords[0] for d in np.arange(0, line.length + .5, .5)])
        width = link.get('width', 6)
        area = line.buffer(width / 2, cap_style=2)
        wide = area.buffer(SIDEWALK)
        x0, z0, x1, z1 = wide.buffer(EARTHWORK_REACH + 2).bounds
        bx, bz, bX, bZ = max(sx, math.floor(x0)), max(sz, math.floor(z0)), min(sX, math.ceil(x1)), min(sZ, math.ceil(z1))
        if bx >= bX or bz >= bZ:
            errors.append([link['id'], 'Link leaves the capture'])
            continue
        zz, xx = np.mgrid[bz:bZ + 1, bx:bX + 1]
        cells = shapely.box(xx, zz, xx + 1, zz + 1)
        shapely.prepare(area)
        shapely.prepare(wide)
        road, walk = shapely.intersects(area, cells), shapely.intersects(wide, cells)
        window = np.s_[bz - az:bZ - az + 1, bx - ax:bX - ax + 1]
        old_walk, old_grade = network['walk'][window], network['grade2'][window]
        def end_height(point):
            iz, ix = int(point[1]) - bz, int(point[0]) - bx
            candidates = np.argwhere(old_walk[max(0, iz - 12):iz + 13, max(0, ix - 12):ix + 13])
            if not len(candidates):
                return None
            offset = np.array([max(0, iz - 12), max(0, ix - 12)])
            best = candidates[np.argmin(np.linalg.norm(candidates + offset - [iz, ix], axis=1))] + offset
            return float(old_grade[tuple(best)]) / 2 + 1
        ends = end_height(link['points'][0]), end_height(link['points'][-1])
        if None in ends:
            errors.append([link['id'], 'No retained road at an end'])
            continue
        along = np.arange(len(samples)) * .5
        pins = [(0.0, ends[0]), (float(along[-1]), ends[1])]
        for rail in rails:
            chord = LineString([(rail['a'][0], rail['a'][2]), (rail['b'][0], rail['b'][2])])
            if chord.intersects(line) and abs(rail['a'][1] - rail['b'][1]) <= 6:
                at = line.project(chord.intersection(line).representative_point())
                y = rail['a'][1] + (rail['b'][1] - rail['a'][1]) * chord.project(chord.intersection(line).representative_point()) / max(1, chord.length)
                ground = source.measured['top'][int(line.interpolate(at).y) - sz, int(line.interpolate(at).x) - sx]
                if y - ground < 5:
                    pins.append((float(at), float(round(y))))
        pins.sort()
        feet = np.interp(along, *zip(*pins))
        grade = np.abs(np.diff(feet)).max() / .5 if len(feet) > 1 else 0
        tree = cKDTree(samples)
        nearest = tree.query(np.c_[xx.ravel() + .5, zz.ravel() + .5])[1].reshape(xx.shape)
        height = np.ceil(feet[nearest] * 2 - 1e-9) / 2
        new_grade = np.rint(2 * (height - 1)).astype(np.int16)
        floor, slab = road_blocks(new_grade)
        top = source.measured['top'][bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1].astype(int)
        known = source.measured['full'][bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1]
        build = walk & ~old_walk
        if road.sum() == 0 or not known[walk].all():
            errors.append([link['id'], 'Link leaves the capture'])
            continue
        blocked = Counter()
        def put(x, y, z, state, purpose):
            before = source.state(x, y, z)
            if before.split('[')[0] not in SOIL | PLANTS | AIR and not before.split('[')[0].endswith(('_leaves', '_log')):
                # Grading simply stops at a structure; only the road itself may not pass one.
                if purpose != 'link earthworks':
                    blocked[before.split('[')[0]] += 1
                return
            if before != state:
                writes[x, y, z] = dict(pos=[x, y, z], before=before, after=state, purpose=purpose)
        d, near = distance_transform_edt(~walk, return_indices=True)
        base = (floor - 1)[tuple(near)]
        target = np.rint(np.clip(top, base - d * .5, base + d * .5)).astype(int)
        for iz, ix in np.argwhere((target != top) & (d <= EARTHWORK_REACH) & ~walk & ~old_walk & known):
            x, z, old, new = int(xx[iz, ix]), int(zz[iz, ix]), int(top[iz, ix]), int(target[iz, ix])
            for y in range(min(old, new) - 2, max(old, new) + 1):
                put(x, y, z, 'minecraft:air' if y > new else 'minecraft:grass_block[snowy=false]' if y == new else 'minecraft:dirt' if y >= new - 2 else 'minecraft:stone', 'link earthworks')
        centre = np.floor(samples).astype(int)
        stroke = {(int(p[0]), int(p[1])) for p, s in zip(centre, along) if int(s // 6) % 2 == 0}
        for iz, ix in np.argwhere(build):
            x, z, y = int(xx[iz, ix]), int(zz[iz, ix]), int(floor[iz, ix])
            for yy in range(min(int(top[iz, ix]) - 1, y - 1), y):
                put(x, yy, z, 'minecraft:stone', 'link bearing')
            for yy in range(y + 1, y + HEADROOM + 1):
                if source.state(x, yy, z).split('[')[0] not in AIR:
                    put(x, yy, z, 'minecraft:air', 'link headroom')
            on_road = road[iz, ix]
            if slab[iz, ix]:
                state = ('projectseele:road_marking_slab' if (x, z) in stroke else 'projectseele:road_asphalt_slab' if on_road else 'minecraft:smooth_stone_slab') + '[type=bottom,waterlogged=false]'
            else:
                state = 'minecraft:white_concrete' if (x, z) in stroke else 'minecraft:black_concrete' if on_road else 'minecraft:smooth_stone'
            put(x, y, z, state, 'link carriageway' if on_road else 'link footway')
            network['walk'][iz + bz - az, ix + bx - ax] = True
            network['road'][iz + bz - az, ix + bx - ax] = bool(on_road)
            network['grade2'][iz + bz - az, ix + bx - ax] = new_grade[iz, ix]
        footprint = shapely.buffer(line, width / 2 + SIDEWALK)
        structures = [r.get('id') for r in catalog if r.get('occupied_bounds') and footprint.intersects(shapely.box(r['occupied_bounds'][0], r['occupied_bounds'][2], r['occupied_bounds'][3], r['occupied_bounds'][5]))]
        stations = [v for v in volumes if footprint.intersects(shapely.box(v[0], v[2], v[3], v[5]))]
        fail = [] if not (blocked or structures) and grade <= (SHORT_GRADE if line.length <= SHORT_RAMP else spec.get('max_grade', MAX_GRADE)) else [dict(blocked=dict(blocked), structures=structures[:4], grade=round(float(grade), 3))]
        report.append(dict(id=link['id'], length=round(line.length), ends=ends, pins=len(pins) - 2, grade=round(float(grade), 3), blocked=dict(blocked), structures=structures[:4], stations=len(stations)))
        if fail:
            errors.append([link['id'], fail[0]])
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
