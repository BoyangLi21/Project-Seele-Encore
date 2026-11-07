"""Regional rail line from one JSON plan: native service first, then its track bed.

`fit` turns a surveyed path into rail nodes MTR can draw. `native` runs the MTR
engine on a copied snapshot, so rails, the route, the depot
and a moving train are proved before any block exists. `edits` lays the bed under
the exact native samples and writes a cell patch for release_map_patch.py. Mapped
future water stays open under the deck; `doors` buries the block MTR needs to open
train doors at a platform. Nothing here opens the actual world.
"""
import argparse
from collections import Counter
import gzip
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import shapely
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString, shape
from shapely.ops import unary_union

from native_transit_additions import inventory
from plan_ashi_landscape_r54 import PLANTS, SOIL
from plan_station_access_corridor import CapturedSurface
from prepare_mtr_member_patch_r52 import Parser
from prepare_station_set_native import classpath
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

NATURAL = SOIL | PLANTS | AIR
BALLAST, HALF = 'minecraft:gravel', 'minecraft:andesite_slab[type=bottom,waterlogged=false]'
DECK = 'minecraft:stone_bricks'
BED_RADIUS, CLEAR_RADIUS, BODY_RADIUS, BODY_HEIGHT = 2.6, 3.1, 1.9, 4.3
ANGLES = ('E', 'SEE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'SWW', 'W', 'NWW', 'NW', 'NNW', 'N', 'NNE', 'NE', 'NEE')
DOOR_TRIGGER = 'mtr:platform[door_type=none,facing=north,side=0]'
DOOR_LATERAL, DOOR_HALF_SPAN = (1.25, 1.5), .6875


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1), 'utf8')


def heading(name):
    """Unit (x, z) vector of an MTR rail angle; E is +x and S is +z."""
    radians = math.radians(ANGLES.index(name) * 22.5)
    return np.array([math.cos(radians), math.sin(radians)])


def arc(start, along, side, radius, length):
    """Points of a circular arc; side is +1 for a clockwise turn seen from above."""
    normal = np.array([-along[1], along[0]]) * side
    centre = start + normal * radius
    angles = np.arange(0, length, 1.0) / radius
    return (start + np.outer(np.sin(angles), along) * radius + np.outer(1 - np.cos(angles), normal) * radius,
            centre + radius * (math.sin(length / radius) * along - math.cos(length / radius) * normal))


def rail_shape(p, a, q, b):
    """Plan samples and tightest radius of a QUADRATIC rail, or None where MTR has no curve.

    Parallel ends give a straight or two equal arcs. Otherwise the rail turns along the
    whole of its shorter tangent and runs straight along the rest of the longer one.
    `native` still reads the engine's own samples before anything is built.
    """
    p, q = np.asarray(p, float), np.asarray(q, float)
    u, v = heading(a), -heading(b)
    d = q - p
    forward, side = float(d @ u), float(d @ np.array([-u[1], u[0]]))
    if abs(float(u @ v) - 1) < 1e-9:
        if forward <= 0:
            return None
        if abs(side) < .5:
            return np.linspace(p, q, max(2, int(forward))), math.inf
        radius = (forward ** 2 + side ** 2) / (4 * abs(side))
        half = 2 * radius * math.asin(min(1, math.hypot(forward, side) / (4 * radius)))
        first, middle = arc(p, u, math.copysign(1, side), radius, half)
        turned = (q - p) / np.linalg.norm(q - p)
        tangent = 2 * turned * (turned @ u) - u
        second, _ = arc(middle, tangent, -math.copysign(1, side), radius, half)
        return np.vstack([first, second, q]), radius
    if abs(float(u @ v) + 1) < 1e-9:
        return None
    t, s = np.linalg.solve(np.column_stack([u, v]), d)
    if t <= 0 or s <= 0:
        return None
    turn = math.acos(max(-1, min(1, float(u @ v))))
    leg = min(t, s)
    radius = leg / math.tan(turn / 2)
    length = radius * turn
    clockwise = math.copysign(1, u[0] * v[1] - u[1] * v[0])
    if t >= s:
        begin = p + u * (t - s)
        straight = np.linspace(p, begin, max(2, int(t - s)))
        return np.vstack([straight, arc(begin, u, clockwise, radius, length)[0], q]), radius
    points, end = arc(p, u, clockwise, radius, length)
    return np.vstack([points, np.linspace(end, q, max(2, int(s - t)))]), radius


def fit(a):
    """Shortest chain of MTR rails that stays on each surveyed path, by dynamic programming."""
    spec = read(a.config)
    spacing, reach, tolerance, minimum = (spec.get(k, d) for k, d in (('node_spacing', 30), ('longest_rail', 8), ('tolerance', 3), ('minimum_radius', 80)))
    from scipy.spatial import cKDTree
    rows = []
    for segment in spec['segments']:
        line = LineString(segment['path'])
        tree = cKDTree([line.interpolate(float(d)).coords[0] for d in np.arange(0, line.length + 1, 1)])
        start, finish = (tuple(segment[k]['pos']) for k in ('from', 'to'))
        count = max(2, round(line.length / spacing))
        layers = [[(start[0], start[2], segment['from']['angle'])]]
        for i in range(1, count):
            position = line.interpolate(i * line.length / count)
            ahead = line.interpolate(min(line.length, i * line.length / count + 8))
            behind = line.interpolate(max(0, i * line.length / count - 8))
            bearing = math.degrees(math.atan2(ahead.y - behind.y, ahead.x - behind.x)) % 360
            near = sorted(range(16), key=lambda k: abs((k * 22.5 - bearing + 180) % 360 - 180))[:3]
            layers.append([(round(position.x) + dx, round(position.y) + dz, ANGLES[k]) for k in near for dx in (-1, 0, 1) for dz in (-1, 0, 1)])
        layers.append([(finish[0], finish[2], ANGLES[(ANGLES.index(segment['to']['angle']) + 8) % 16])])
        best = {layers[0][0]: (0.0, None)}
        for i in range(1, len(layers)):
            for node in layers[i]:
                for j in range(max(0, i - reach), i):
                    for earlier in layers[j]:
                        if earlier not in best:
                            continue
                        shape_ = rail_shape(earlier[:2], earlier[2], node[:2], ANGLES[(ANGLES.index(node[2]) + 8) % 16])
                        if shape_ is None or shape_[1] < minimum:
                            continue
                        off = tree.query(shape_[0])[0]
                        if off.max() > tolerance:
                            continue
                        cost = best[earlier][0] + float((off ** 2).sum()) + spec.get('node_cost', 40)
                        if node not in best or cost < best[node][0]:
                            best[node] = (cost, earlier)
        node = layers[-1][0]
        if node not in best:
            raise ValueError(('No rail chain within tolerance', segment['id']))
        chain = []
        while node is not None:
            chain.append(node)
            node = best[node][1]
        chain.reverse()
        rise = (finish[1] - start[1]) / len(chain[:-1])
        for i, (u, w) in enumerate(zip(chain, chain[1:])):
            rows.append(dict(id=f"{segment['id']}-{i}", kind='rail', **{'from': [u[0], round(start[1] + rise * i), u[1]], 'to': [w[0], round(start[1] + rise * (i + 1)), w[1]]},
                             from_angle=u[2], to_angle=ANGLES[(ANGLES.index(w[2]) + 8) % 16], vertical_radius=100, speed=80, reverse_speed=80))
        print(segment['id'], 'length', round(line.length), 'rails', len(chain) - 1, flush=True)
    write(a.out / 'fitted-rails.json', rows)


def native(a):
    """Author on a copied snapshot; only brand-new members may leave staging."""
    spec = read(a.config)
    repo = Path(__file__).resolve().parents[1]
    work = repo / '.Codex' / ('rail-' + spec['id'])
    if work.exists():
        raise ValueError('Use a fresh native staging directory')
    (work / 'classes').mkdir(parents=True)
    staging, out = work / 'native', work / 'output'
    shutil.copytree(spec['native_snapshot'], staging)
    plan = {key: spec[key] for key in ('rails', 'stations', 'lines', 'warmup_seconds')}
    plan['commission_clock'] = True
    write(work / 'plan.json', plan)
    options = argparse.Namespace(work=work, mtr=a.mtr, java=a.java)
    subprocess.run([str(a.java / 'bin/javac.exe'), '-encoding', 'UTF-8', '-cp', classpath(options), '-d', str(work / 'classes'),
                    str(Path(__file__).with_name('java') / 'RegionalTransitAuthor.java')], check=True)
    subprocess.run([str(a.java / 'bin/java.exe'), '-cp', classpath(options), 'RegionalTransitAuthor', str(work / 'plan.json'),
                    str(staging), str(out), '--append'], check=True, cwd=work)
    before, after = inventory(Path(spec['native_snapshot'])), inventory(staging)
    # Staged trains keep moving, so sidings and the clock differ; neither is delivered.
    changed = sorted(k for k in before if k in after and after[k] != before[k]
                     and Path(k).parts[2] not in ('settings', 'sidings'))
    gone = sorted(set(before) - set(after))
    if changed or gone:
        raise ValueError(('Native authoring touched existing members', changed[:5], gone[:5]))
    additions = a.out / 'additions'
    for name in sorted(set(after) - set(before)):
        target = additions / 'mtr' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staging / name, target)
    shutil.copy2(out / 'native_transit_receipt.json', a.out / 'native_transit_receipt.json')
    shutil.copy2(out / 'track_samples.json', a.out / 'track_samples.json')
    receipt = read(a.out / 'native_transit_receipt.json')
    print('Native commissioning', json.dumps(receipt['validation'], ensure_ascii=False), 'new members', len(set(after) - set(before)))


def water_mask(features, spec, cells, bounds):
    with gzip.open(features, 'rt', encoding='utf8') as stream:
        rows = json.load(stream)['features']
    clip = shapely.box(*bounds)
    shapes = []
    for q in rows:
        if q['properties'].get('source_layer') in ('WA', 'RvrCL', 'WStrL'):
            g = shape(q['geometry'])
            if g.intersects(clip):
                shapes.append(g if q['properties']['source_layer'] == 'WA' else g.buffer(1))
    reserve = unary_union(shapes).buffer(spec.get('water_margin', 1))
    shapely.prepare(reserve)
    return shapely.intersects(reserve, cells)


def bed_heights(ys):
    """Ballast top under a rail: full gravel near a whole block, a slab near a half."""
    rounded = np.rint(np.asarray(ys, float) * 2) / 2
    block = np.floor(rounded).astype(int) - 1
    return block, rounded % 1 == .5


def edits(a):
    spec = read(a.config)
    samples = [r for r in read(a.out / 'track_samples.json') if r['mode'] == 'TRAIN']
    # A diagonal line's bounding box holds ungenerated corners; state() refuses those columns.
    source = CapturedSurface(spec['source'], partial=True)
    points = np.array([p for r in samples for p in r['points']])
    lines = unary_union([LineString(np.array(r['points'])[:, [0, 2]]) for r in samples])
    sx, sz, sX, sZ = source.bounds
    x0, z0, x1, z1 = lines.buffer(16).bounds
    bx, bz, bX, bZ = max(sx, math.floor(x0)), max(sz, math.floor(z0)), min(sX, math.ceil(x1)), min(sZ, math.ceil(z1))
    zz, xx = np.mgrid[bz:bZ + 1, bx:bX + 1]
    cells = shapely.box(xx, zz, xx + 1, zz + 1)
    def near(radius):
        g = lines.buffer(radius, cap_style=2)
        shapely.prepare(g)
        return shapely.intersects(g, cells)
    bed, clear, body = near(BED_RADIUS), near(CLEAR_RADIUS), near(BODY_RADIUS)
    from scipy.spatial import cKDTree
    _, nearest = cKDTree(points[:, [0, 2]]).query(np.c_[xx.ravel() + .5, zz.ravel() + .5])
    block, half = bed_heights(points[nearest, 1])
    block, half = block.reshape(xx.shape), half.reshape(xx.shape)
    with np.load(Path(spec['authority']) / 'network.npz') as f:
        ax, az, _, _ = map(int, f['bounds'])
        area = np.s_[bz - az:bZ - az + 1, bx - ax:bX - ax + 1]
        public = (f['walk'] | f['road'])[area].copy()
    station = np.zeros(public.shape, bool)
    for a0, _, c0, a1, _, c1 in read(Path(spec['authority']) / 'station-volumes.json'):
        station[(xx >= a0) & (xx <= a1) & (zz >= c0) & (zz <= c1)] = True
    original = source.measured['top'][bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1].astype(int)
    full = source.measured['full'][bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1]
    water = water_mask(spec['features'], spec, cells, (bx, bz, bX, bZ))
    d, near_bed = distance_transform_edt(~bed, return_indices=True)
    top = (block + 0)[tuple(near_bed)]
    target = np.rint(np.clip(original, top - d, top + d)).astype(int)
    active = (target != original) & (d <= spec.get('earthwork_reach', 10)) & ~bed & ~water & ~public & full
    writes, purposes, skipped, blocked = {}, {}, Counter(), []
    def put(x, y, z, state, purpose):
        before = source.state(x, y, z)
        if before.split('[')[0] not in NATURAL:
            skipped[before.split('[')[0]] += 1
            return
        if before != state:
            writes[x, y, z] = state
            purposes[x, y, z] = purpose
    for iz, ix in np.argwhere(active):
        x, z, old, new = int(xx[iz, ix]), int(zz[iz, ix]), int(original[iz, ix]), int(target[iz, ix])
        for y in range(min(old, new) - 2, max(old, new) + 1):
            state = 'minecraft:air' if y > new else 'minecraft:grass_block[snowy=false]' if y == new else 'minecraft:dirt' if y >= new - 2 else 'minecraft:stone'
            put(x, y, z, state, 'embankment slope')
    for iz, ix in np.argwhere(bed):
        x, z, y = int(xx[iz, ix]), int(zz[iz, ix]), int(block[iz, ix])
        if public[iz, ix]:
            continue
        if not full[iz, ix]:
            blocked.append([x, y, z])
            continue
        if water[iz, ix]:
            put(x, y - 1, z, DECK, 'open deck over a mapped channel')
        else:
            for yy in range(min(int(original[iz, ix]) - 1, y - 1), y):
                put(x, yy, z, 'minecraft:stone', 'track bed fill')
        put(x, y, z, BALLAST, 'ballast')
        if half[iz, ix]:
            put(x, y + 1, z, HALF, 'ballast half step')
    for iz, ix in np.argwhere(clear):
        x, z = int(xx[iz, ix]), int(zz[iz, ix])
        if not full[iz, ix]:
            if body[iz, ix]:
                blocked.append([x, 0, z])
            continue
        base = int(block[iz, ix]) + (2 if half[iz, ix] else 1)
        for y in range(base, base + 6):
            before = source.state(x, y, z)
            if before.split('[')[0] in AIR or (x, y, z) in writes:
                continue
            if before.split('[')[0] in NATURAL:
                put(x, y, z, 'minecraft:air', 'track clearance')
            elif body[iz, ix] and not public[iz, ix] and not station[iz, ix]:
                blocked.append([x, y, z])
    def state(x, y, z):
        return writes.get((x, y, z), source.state(x, y, z))
    floating, solid_in_body = [], []
    for x, y, z in points[::2]:
        cx, cz = math.floor(x), math.floor(z)
        if not state(cx, math.floor(y + .01) - 1, cz).split('[')[0] not in AIR:
            floating.append([cx, math.floor(y), cz])
    # Platform edges sit inside this radius by design; the real model sweep owns stations.
    for iz, ix in np.argwhere(body & full & ~public & ~station):
        px, pz = int(xx[iz, ix]), int(zz[iz, ix])
        base = int(block[iz, ix]) + (2 if half[iz, ix] else 1)
        for y in range(base, base + math.ceil(BODY_HEIGHT)):
            if state(px, y, pz).split('[')[0] not in AIR and state(px, y, pz).split('[')[0] not in PLANTS:
                solid_in_body.append([px, y, pz, state(px, y, pz)[:40]])
    devices = {tuple(int(t[k]) for k in 'xyz') for t in source.devices}
    errors = []
    if blocked:
        errors.append(['Track meets a public or unknown column', blocked[:10]])
    if floating:
        errors.append(['Rail without bed', floating[:10]])
    if solid_in_body:
        errors.append(['Solid inside the train body', solid_in_body[:10]])
    if devices & set(writes):
        errors.append('Track edits an original device')
    rows = [dict(pos=list(p), before=source.state(*p), after=s, purpose=purposes[p]) for p, s in sorted(writes.items())]
    report = dict(errors=errors, cells=len(rows), purposes=dict(Counter(r['purpose'] for r in rows)), skipped_foreign=dict(skipped),
                  length=float(lines.length), open_deck_columns=int((bed & water).sum()), world_written=False, train_run_in_game=False)
    write(a.out / 'bed-check.json', report)
    additions = a.out / 'additions'
    write(a.out / 'patch.json', dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'], edits=rows,
          native_snapshot=spec['native_snapshot'], native_additions=str(additions), error_reports=[str(a.out / 'bed-check.json')],
          views_reviewed_by_root=False, continuation_work=spec['continuation_work']))
    print(json.dumps({k: report[k] for k in ('cells', 'purposes', 'skipped_foreign', 'length', 'open_deck_columns')}, ensure_ascii=False))
    if errors:
        print(json.dumps(errors, ensure_ascii=False)[:1500])
        raise SystemExit(1)


def door_scan(point, along, out, y):
    """Cells RenderVehicleHelper.canOpenDoors reads for one stopped door on a level rail."""
    corners = np.array([point + along * s + out * w for s in (-DOOR_HALF_SPAN, DOOR_HALF_SPAN) for w in DOOR_LATERAL])
    low, high = corners.min(0) - 1, corners.max(0) + 1
    for x in np.arange(low[0], high[0] + 1e-9):
        for z in np.arange(low[1], high[1] + 1e-9):
            for level in range(y - 1, y + 4):
                yield math.floor(x), level, math.floor(z)


def platform_edge(source, start, along, length, out, y):
    """Walkable cells beside the rail, found by stepping outwards from the track."""
    row = {}
    for s in np.arange(0, length, .5):
        for w in np.arange(1, 3.6, .25):
            x, z = (math.floor(v) for v in start + along * s + out * w)
            if source.state(x, y, z).split('[')[0] in AIR:
                continue
            if all(source.state(x, y + h, z).split('[')[0] in AIR for h in (1, 2)):
                row[x, z] = source.state(x, y - 1, z)
            break
    return row


def doors(a):
    """MTR opens no door without a platform block in reach, and the regional stations have none.

    The trigger goes under the edge row, so the floor players see and walk on stays as built.
    """
    spec = read(a.config)
    source = CapturedSurface(spec['source'], partial=True)
    root = Path(spec['native_snapshot']) / 'projectseele/geofront'
    def members(kind):
        return [Parser(p.read_bytes()).node().value for p in (root / kind).rglob('*') if p.is_file()]
    stations = members('stations')
    sx, sz, sX, sZ = source.bounds
    full = source.measured['full']
    def station_at(x, z):
        for s in stations:
            a0, a1 = sorted((s['position1']['x'], s['position2']['x']))
            b0, b1 = sorted((s['position1']['z'], s['position2']['z']))
            if a0 - 2 <= x <= a1 + 2 and b0 - 2 <= z <= b1 + 2:
                return s['name']
    rows, report, errors = [], [], []
    for platform in members('platforms'):
        p, q = platform['position1'], platform['position2']
        x0, x1 = sorted((p['x'], q['x']))
        z0, z1 = sorted((p['z'], q['z']))
        y = p['y']
        inside = x0 - 6 >= sx and z0 - 6 >= sz and x1 + 6 <= sX and z1 + 6 <= sZ and full[z0 - 6 - sz:z1 + 7 - sz, x0 - 6 - sx:x1 + 7 - sx].all()
        name = station_at((x0 + x1) / 2, (z0 + z1) / 2)
        if platform['transportMode'] != 'TRAIN' or not inside or name is None:
            continue
        served = any(source.state(x, yy, z).startswith(('mtr:platform', 'mtr:apg_door', 'mtr:psd_door')) for x in range(x0 - 3, x1 + 4)
                     for z in range(z0 - 3, z1 + 4) for yy in range(y - 2, y + 3))
        if served:
            report.append(dict(station=name, position=[p['x'], y, p['z']], already_served=True))
            continue
        start = np.array([p['x'] + .5, p['z'] + .5])
        delta = np.array([q['x'] + .5, q['z'] + .5]) - start
        length = float(np.linalg.norm(delta))
        along = delta / length
        out = np.array([-along[1], along[0]])
        sides = {side: platform_edge(source, start, along, length, out * side, y) for side in (1, -1)}
        side = max(sides, key=lambda k: len(sides[k]))
        edge = sides[side]
        cells = set()
        for (x, z), below in sorted(edge.items()):
            if below.split('[')[0] in AIR or '[' in below:
                errors.append(['Edge has no solid block to replace', name, [x, y - 1, z], below])
                continue
            cells.add((x, y - 1, z))
            rows.append(dict(pos=[x, y - 1, z], before=below, after=DOOR_TRIGGER, purpose='platform door trigger'))
        # A door anywhere along the platform opens on the edge side and only there.
        stops = np.arange(DOOR_HALF_SPAN, length - DOOR_HALF_SPAN, .5)
        near = sum(any(c in cells for c in door_scan(start + along * s, along, out * side, y)) for s in stops)
        far = sum(any(c in cells for c in door_scan(start + along * s, along, -out * side, y)) for s in stops)
        if near != len(stops) or far or len(edge) < .7 * length:
            errors.append(['Door reach', name, [p['x'], y, p['z']], near, len(stops), far, len(edge)])
        report.append(dict(station=name, position=[p['x'], y, p['z']], length=length, cells=len(cells), side=side, doors_checked=len(stops),
                           doors_in_reach=near, far_side_in_reach=far))
    check = dict(errors=errors, cells=len(rows), platforms=report, world_written=False, door_opened_in_game=False)
    write(a.out / 'door-check.json', check)
    write(a.out / 'patch.json', dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'], edits=rows,
          native_snapshot=spec['native_snapshot'], error_reports=[str(a.out / 'door-check.json')], views_reviewed_by_root=False,
          continuation_work=spec['continuation_work']))
    print(json.dumps(dict(cells=len(rows), platforms=len(report), errors=errors[:5]), ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('fit', 'native', 'edits', 'doors'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--java', type=Path)
    parser.add_argument('--mtr', type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    globals()[args.mode](args)
