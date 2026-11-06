"""Author a bounded station layout from JSON and frozen, complete block captures.

No live-world, native registry, renderer, Simulator or game entry point exists.
The JSON owns geography and geometry; this tool owns source protection, exact
patches, public grades and grounded components. Use a fresh output directory.
"""
import argparse
import collections
import copy
import json
import math
import shutil
from pathlib import Path

import nbtlib
import numpy as np
from scipy.ndimage import label
from shapely.geometry import box, shape
from shapely.ops import unary_union

from author_hakone_lakefront import Editor
from author_hakone_togendai import Station
from author_kamonomiya_station import ALLOWED, OPEN, voxel_box
from prepare_hakone_city_cross import packed


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')


def inside(p, bounds):
    return all(bounds[i] <= p[i] <= bounds[i + 3] for i in range(3))


def route_columns(centres, width):
    """Cardinal profiles: full perpendicular rows and square turn landings."""
    if width < 3 or width % 2 != 1 or len(centres) < 2:
        raise ValueError('Route needs an odd width >= 3 and multiple centres')
    result = {}; half = width // 2
    for i, (x, z, grade) in enumerate(centres):
        directions = set()
        for j in (i - 1, i + 1):
            if not 0 <= j < len(centres):
                continue
            X, Z, G = centres[j]
            if abs(X - x) + abs(Z - z) != 1 or abs(G - grade) > 1:
                raise ValueError('Route contains a gap, diagonal or >0.5 m step')
            directions.add('z' if Z != z else 'x')
        offsets = range(-half, half + 1)
        cells = ([(x + d, z) for d in offsets] if directions == {'z'} else
                 [(x, z + d) for d in offsets] if directions == {'x'} else
                 [(x + dx, z + dz) for dx in offsets for dz in offsets])
        for p in cells:
            if p in result and result[p] != grade:
                raise ValueError(('Overlapping route grades', p, result[p], grade))
            result[p] = grade
    return result


def open_state(state):
    return state.split('[')[0] in OPEN or '_wall_sign[' in state


def collision(state):
    if open_state(state):
        return []
    if '_slab[' in state and 'type=bottom' in state:
        return [[0, 0, 0, 1, .5, 1]]
    if '_slab[' in state and 'type=top' in state:
        return [[0, .5, 0, 1, 1, 1]]
    if '_stairs[' in state:
        raise ValueError('Exact stair collision must be supplied by native export')
    # The JSON author uses full blocks and slabs for all public surfaces and
    # guards. Decorative non-full blocks cannot silently become walking floors.
    return [[0, 0, 0, 1, 1, 1]]


def author(a):
    spec = read(a.plan)
    if spec['schema'] != 'station-layout-author-v1':
        raise ValueError('Unsupported station author schema')
    source = Path(spec['source']); authority = Path(spec['authority'])
    if any(p.lower() == 'saves' for p in source.parts + a.out.parts):
        raise ValueError('Only offline captures and candidates are accepted')
    cap = read(source / 'capture.json'); l, t, r, b = cap['bounds_xz']
    if cap.get('unavailable_chunks') or cap.get('actors'):
        raise ValueError('Source has missing chunks or unhandled actors')
    if set(cap['chunk_statuses']) != {'full'}:
        raise ValueError('Every captured chunk must have FULL status')
    with np.load(source / 'measured.npz') as f:
        if list(map(int, f['bounds'])) != [l, t, r, b] or not f['full'].all() or f['actors'].any():
            raise ValueError('Measured bounds or complete capture mask differs')
        ground = f['top'].copy(); highest = f['highest'].copy()
    with np.load(authority / 'network.npz') as f:
        ax, az, aX, aZ = map(int, f['bounds'])
        old_public = f['walk'] | f['road']; oldgrade = f['grade2'].copy()
    if not (ax <= l <= r <= aX and az <= t <= b <= aZ):
        raise ValueError('Capture is outside authoritative network')
    captured = nbtlib.load(source / 'captured-devices.dat')
    devices = {tuple(int(d[k]) for k in ('x', 'y', 'z')) for d in captured['Devices']}
    water = unary_union([shape(q['geometry']) for q in spec['water_features']]).buffer(spec['water_buffer'])
    wet = {(x, z) for x in range(spec['bounds'][0], spec['bounds'][3] + 1)
           for z in range(spec['bounds'][2], spec['bounds'][5] + 1)
           if water.intersects(box(x, z, x + 1, z + 1))}
    a.out.mkdir(exist_ok=False)
    shutil.copytree(source / 'source', a.out / 'source'); (a.out / 'delta').mkdir()
    for name in ('capture.json', 'captured-devices.dat', 'measured.npz'):
        shutil.copy2(source / name, a.out / name)
    write(a.out / 'layout-authoring.json', spec)
    e = Editor(a.out); signs = Station(e); public = set(); routes = []; guards = []
    expected_chunks = {(x, z) for x in range(l // 16, r // 16 + 1) for z in range(t // 16, b // 16 + 1)}
    actual_chunks = set()
    for file in (source / 'source').glob('*.npz'):
        with np.load(file) as f:
            actual_chunks.update(tuple(map(int, p)) for p in f['coordinates'])
            if f['blocks'].shape[1:] != (448, 16, 16):
                raise ValueError('Capture is not a complete vertical section')
    if actual_chunks != expected_chunks or len(actual_chunks) != cap['chunk_statuses']['full']:
        raise ValueError('Captured chunk set does not cover the whole declared bounds')

    def put(x, y, z, state):
        p = x, y, z
        if not inside(p, spec['bounds']) or not l <= x <= r or not t <= z <= b or not -128 <= y <= 319:
            raise ValueError(('Unknown/outside declared source', p))
        if e.state(*p) == state:
            return
        before = e.state(*p, original=True)
        if before.split('[')[0] not in ALLOWED or p in devices or old_public[z - az, x - ax]:
            raise ValueError(('Protected source', p, before))
        if (x, z) in wet and (not any(inside(p, q) for q in spec['airborne_water_spans']) or before.split('[')[0] not in OPEN):
            raise ValueError(('Water terrain/buffer is protected', p, before))
        e.put(*p, state)

    def fill(bounds, state):
        x, y, z, X, Y, Z = bounds
        for xx in range(x, X + 1):
            for zz in range(z, Z + 1):
                for yy in range(y, Y + 1):
                    put(xx, yy, zz, state)

    def surface(x, z, grade, policy, declare):
        if policy not in ('ground', 'deck'):
            raise ValueError('Unknown surface support policy')
        if old_public[z - az, x - ax]:
            if int(oldgrade[z - az, x - ax]) != grade:
                raise ValueError(('Retained street grade differs', x, z, grade))
            if declare: public.add((x, z, grade))
            return
        top = (grade + 1) // 2; terrain = int(ground[z - t, x - l])
        base = terrain - 1 if policy == 'ground' else top - 1
        if policy == 'ground' and (abs(top - terrain) > spec['maximum_ground_earthwork'] or (x, z) in wet):
            raise ValueError(('Unbounded earthwork or water fill', x, z, terrain, top))
        for y in range(base, top): put(x, y, z, 'minecraft:stone_bricks')
        put(x, top, z, 'minecraft:smooth_stone' if grade % 2 == 0 else 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
        clear_top = max(top + 3, int(highest[z - t, x - l]) + 1) if policy == 'ground' else top + 3
        for y in range(top + 1, clear_top + 1):
            put(x, y, z, 'minecraft:air')
        if declare:
            public.add((x, z, grade))

    for op in spec['operations']:
        kind = op['kind']
        if kind == 'fill':
            fill(op['bounds'], op['state'])
        elif kind == 'foundation':
            for x, z in op['columns']:
                floor = int(ground[z - t, x - l])
                if (x, z) in wet or floor > op['top'] or op['top'] - floor > spec['maximum_support_height']:
                    raise ValueError(('Invalid measured foundation', x, z, floor))
                fill([x, floor - 1, z, x, op['top'], z], op['state'])
        elif kind in ('surface', 'route'):
            rows = ({(x, z): g for x, z, g in op['columns']} if kind == 'surface'
                    else route_columns(op['centres'], op['width']))
            for (x, z), grade in rows.items(): surface(x, z, grade, op['support'], op.get('public', True))
            if kind == 'route':
                routes.append(dict(id=op['id'], width=op['width'], centres=op['centres'], columns=[[x, z, g] for (x, z), g in sorted(rows.items())]))
        elif kind == 'guard':
            if op['support'] not in ('ground', 'deck'):
                raise ValueError('Unknown guard support policy')
            for x, z, grade in op['columns']:
                if old_public[z - az, x - ax]: continue
                top = (grade + 1) // 2; terrain = int(ground[z - t, x - l])
                base = min(terrain - 1, top - 1) if op['support'] == 'ground' else top - 1
                if op['support'] == 'ground' and (x, z) in wet: raise ValueError('Guard foundation in water buffer')
                end = max(top, terrain) if op['support'] == 'ground' else top
                fill([x, base, z, x, end, z], 'minecraft:stone_bricks')
                put(x, end + 1, z, 'minecraft:light_gray_stained_glass')
                guards.append([x, end + 1, z])
        elif kind == 'sign':
            p = op['pos']; facing = op['facing']
            put(*p, 'minecraft:oak_wall_sign[facing=' + facing + ',waterlogged=false]')
            signs.sign(*p, op['lines'], facing)
        else:
            raise ValueError('Unsupported author operation: ' + kind)
    blocked = []
    for x, z, grade in list(public):
        y = (grade + 1) // 2
        if any(not open_state(e.state(x, yy, z)) for yy in (y + 1, y + 2)):
            blocked.append([x, z, grade]); public.remove((x, z, grade))
    for route in routes:
        if any((x, z, g) not in public for x, z, g in route['columns']):
            raise ValueError('A required full-width route was obstructed by later geometry')
    regions = e.save(); changes = []
    for region in e.regions.values():
        for (cx, cz), before, after in zip(region['coords'], region['before'], region['after']):
            for iy, iz, ix in np.argwhere(before != after):
                p = [int(cx) * 16 + int(ix), int(iy) - 128, int(cz) * 16 + int(iz)]
                changes.append(dict(pos=p, before=region['names'][int(before[iy, iz, ix])], after=region['names'][int(after[iy, iz, ix])]))
    if len(changes) > spec['maximum_changes']:
        raise ValueError('Candidate exceeds explicitly bounded edit count')
    write(a.out / 'exact-edits.json', changes)
    payload = [nbtlib.Compound({'Pos': nbtlib.Long(packed(tuple(int(d['After'][k]) for k in ('x', 'y', 'z')))), 'After': copy.deepcopy(d['After'])}) for d in signs.devices]
    nbtlib.File({'Changes': nbtlib.List[nbtlib.Compound](payload)}).save(a.out / 'block-entities.dat', gzipped=True)
    rows = [list(p) for p in sorted(public)]
    design = copy.deepcopy(spec['design'])
    ground_set = {tuple(v) for v in spec['ground_access_columns']}
    ground_rows = [q for q in rows if old_public[q[1] - az, q[0] - ax] or tuple(q) in ground_set]
    design.update(public_columns=rows, station_multi_level_nodes=[[x, g, z] for x, z, g in rows], ground_access_columns=ground_rows,
                  ground_access_format=['x', 'z', 'grade2'], station_multi_level_node_format=['x', 'grade2', 'z'],
                  source_authority=str(authority), world_written=False, through_service_complete=False,
                  native_registry_pending=True, physical_scope_complete=False, full_width_routes=routes, guard_cells=guards,
                  excluded_furniture_wall_columns=blocked, parts=[{'kind': 'JSON declared station and approach', 'bounds': spec['bounds']}])
    write(a.out / 'station-design.json', design)
    shapes = {}
    for region in e.regions.values():
        for state in region['names']:
            if '_stairs[' not in state: shapes[state] = collision(state)
    write(a.out / 'authored-collision-shapes.json', shapes)
    layout = copy.deepcopy(spec['release_layout'])
    layout.update(collision_shapes=str(a.out / 'authored-collision-shapes.json'), station_multi_level_nodes=design['station_multi_level_nodes'], ground_access_columns=ground_rows, device_changes=len(payload))
    write(a.out / 'release-layout.json', layout)
    for filename, key in [('native-station-plan.json', 'native_plan'), ('station-set-plan.json', 'station_set_plan'), ('station-verification-config.json', 'verification_config'), ('stage-three-interfaces.json', 'stage_three_interfaces')]:
        write(a.out / filename, spec[key])
    write(a.out / 'manifest.json', dict(world=cap['world'], kind='measured-regional-station', bounds_xz=cap['bounds_xz'], regions=regions, cells=len(changes), native_station_pending=True, world_written=False))
    print('JSON station candidate:', len(changes), 'cells;', len(rows), 'public surfaces;', len(routes), 'full-width routes')


def verify(a):
    from map_pipeline.station_layout import verify as verify_layout
    from audit_hakone_station_walks import Walker
    e = Editor(a.out); spec = read(a.out / 'layout-authoring.json'); d = read(a.out / 'station-design.json')
    changes = read(a.out / 'exact-edits.json'); errors = []
    proof = verify_layout(a.out, Path(spec['authority']), read(a.out / 'release-layout.json'))
    with np.load(Path(spec['authority']) / 'network.npz') as f:
        ax, az, _, _ = map(int, f['bounds']); old_public = f['walk'] | f['road']
    devices = {tuple(int(q[k]) for k in ('x', 'y', 'z')) for q in nbtlib.load(a.out / 'captured-devices.dat')['Devices']}
    water = unary_union([shape(q['geometry']) for q in spec['water_features']]).buffer(spec['water_buffer'])
    def protected(p, before):
        x, y, z = p
        return before.split('[')[0] not in ALLOWED or tuple(p) in devices or bool(old_public[z - az, x - ax])
    def reserved(p, before):
        x, y, z = p
        return water.intersects(box(x, z, x + 1, z + 1)) and (not any(inside(p, q) for q in spec['airborne_water_spans']) or before.split('[')[0] not in OPEN)
    for q in changes:
        if e.state(*q['pos'], original=True) != q['before'] or e.state(*q['pos']) != q['after']:
            errors.append(['exact-edit-mismatch', q['pos']])
        if protected(q['pos'], q['before']): errors.append(['protected-source-change', q['pos']])
        if reserved(q['pos'], q['before']): errors.append(['reserved-water-change', q['pos']])
    actual_count = 0
    for region in e.regions.values():
        actual_count += int(np.count_nonzero(region['before'] != region['after']))
    if actual_count != len(changes) or actual_count != read(a.out / 'manifest.json')['cells']:
        errors.append(['exact-edit-scope-count', actual_count, len(changes)])
    shapes = read(a.out / 'authored-collision-shapes.json')
    def walker():
        w = Walker.__new__(Walker); w.reader = e; w.shapes = shapes; w.cache = {}; return w
    w = walker(); nodes = {tuple(q) for q in d['station_multi_level_nodes']}; adjacency = collections.defaultdict(set); edge_checks = 0
    # Actual 0.6 m player footprint swept at 1/8 m intervals; centre adjacency
    # by itself cannot establish a valid step, corner or wall-side passage.
    for x, g, z in sorted(nodes):
        for dx, dz in ((1, 0), (0, 1)):
            for dg in (-1, 0, 1):
                q = x + dx, g + dg, z + dz
                if q not in nodes: continue
                edge_checks += 1
                path = [[x + .5, g / 2 + 1, z + .5], [q[0] + .5, q[1] / 2 + 1, q[2] + .5]]
                result = w.follow(path)
                if result['kind'] == 'static_clear_provisional':
                    adjacency[x, g, z].add(q); adjacency[q].add((x, g, z))
                else: errors.append(['swept-public-edge', path, result])
    p = d['retained_street_anchor']; start = p[0], round((p[1] - 1) * 2), p[2]
    reached = {start}; parents = {start: None}; queue = collections.deque([start])
    while queue:
        for q in adjacency[queue.popleft()]:
            if q not in reached: reached.add(q); parents[q] = True; queue.append(q)
    if reached != nodes: errors.append(['swept-unreachable-surfaces', len(nodes - reached)])
    permitted_edges = {tuple(q) for q in d.get('allowed_open_edges', [])}; exposed = []
    for x, g, z in sorted(nodes):
        feet = g / 2 + 1
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if any((x + dx, g + dg, z + dz) in nodes for dg in (-1, 0, 1)) or (x, g, z, dx, dz) in permitted_edges: continue
            if w.body(x + dx + .5, feet, z + dz + .5): continue
            heights, unknown = w.floors(x + dx + .5, feet, z + dz + .5)
            if unknown or not any(abs(h - feet) <= .50001 for h in heights): exposed.append([x, g, z, dx, dz])
    if exposed: errors.append(['unguarded-public-drop-edge', exposed[:20]])
    edge_rows = []
    if 'full_boarding_edge' in d:
        edge = d['full_boarding_edge']; along = 0 if edge['axis'] == 'x' else 2; across = 2 - along
        rail = read(a.out / 'native-station-plan.json')['rails'][0]; coordinate = edge['edge_z' if across == 2 else 'edge_x']
        direction = 1 if coordinate > rail['from'][across] else -1; start_column = coordinate if direction > 0 else coordinate - 1
        for value in edge['samples']:
            width = 0
            for offset in range(64):
                p = [0, edge['floor_y'] * 2, 0]; p[along] = value; p[across] = start_column + offset * direction
                if tuple(p) not in reached: break
                width += 1
            edge_rows.append(dict(along=value, continuous_width=width))
        if not edge_rows or min(q['continuous_width'] for q in edge_rows) < 3: errors.append(['platform-full-length-width'])
    bounds = spec['support_check_bounds']; data, palette = voxel_box(e, bounds)
    solids = np.asarray([not open_state(p) for p in palette])[data]
    labels, _ = label(solids); roots = set(map(int, np.unique(labels[0]))); roots.discard(0)
    floating = []
    for q in changes:
        x, y, z = q['pos']
        if not open_state(q['after']) and int(labels[y - bounds[1], z - bounds[2], x - bounds[0]]) not in roots:
            floating.append(q['pos'])
    if floating: errors.append(['new-floating-component', floating[:12]])
    # Detect cut-off retained terrain, independently of the author's new solids.
    before_data = data.copy(); ids = {p: i for i, p in enumerate(palette)}
    for q in changes:
        x, y, z = q['pos']; before_data[y - bounds[1], z - bounds[2], x - bounds[0]] = ids[q['before']]
    before_solids = np.asarray([not open_state(p) for p in palette])[before_data]
    before_labels, _ = label(before_solids); before_roots = np.unique(before_labels[0]); before_roots = before_roots[before_roots != 0]
    detached = np.argwhere((data == before_data) & solids & np.isin(before_labels, before_roots) & ~np.isin(labels, list(roots)))
    if len(detached): errors.append(['newly-detached-retained-cells', len(detached)])
    missing_guards = [p for p in d['guard_cells'] if e.state(*p) != 'minecraft:light_gray_stained_glass']
    if missing_guards: errors.append(['guard-missing', missing_guards[:12]])
    payload = nbtlib.load(a.out / 'block-entities.dat')['Changes']; tags = {tuple(int(q['After'][k]) for k in ('x', 'y', 'z')): q['After'] for q in payload}
    offsets = {'north': (0, 1), 'south': (0, -1), 'west': (1, 0), 'east': (-1, 0)}
    for q in d['expected_signs']:
        x, y, z = q['pos']; dx, dz = offsets[q['facing']]
        if tuple(q['pos']) not in tags or open_state(e.state(x + dx, y, z + dz)):
            errors.append(['sign-payload-or-backing', q['pos']])
    negative = []
    def fault(name, p, value, check):
        old = e.state(*p); e.put(*p, value)
        try: rejected = bool(check())
        finally: e.put(*p, old)
        negative.append(dict(name=name, rejected=rejected, pos=list(p)))
    if not d['full_width_routes'] or not d['guard_cells']:
        raise ValueError('A station needs a declared full-width approach and edge guards')
    sample_route = d['full_width_routes'][-1]; centre = sample_route['centres'][0]; following = sample_route['centres'][1]
    x, z, g = centre; half = sample_route['width'] // 2
    if following[1] != z: x += half
    else: z += half
    y = (g + 1) // 2
    def invalid_floor():
        probe = walker(); floors, unknown = probe.floors(x + .5, g / 2 + 1, z + .5)
        return unknown or not any(abs(v - (g / 2 + 1)) < 1e-6 for v in floors)
    fault('full-width-outer-cell-bearing-removed', (x, y, z), 'minecraft:air', invalid_floor)
    fault('public-headroom-blocked', (x, y + 1, z), 'minecraft:stone', lambda: walker().body(x + .5, g / 2 + 1, z + .5))
    guard = tuple(d['guard_cells'][0]); fault('declared-guard-removed', guard, 'minecraft:air', lambda: e.state(*guard) != 'minecraft:light_gray_stained_glass')
    street_anchor = d['retained_street_anchor']
    street = (street_anchor[0], math.floor(street_anchor[1]) - 1, street_anchor[2])
    negative.append(dict(name='retained-public-paving-change', rejected=protected(street, e.state(*street, original=True)), pos=list(street)))
    wet_ground = next((q for q in changes if water.intersects(box(q['pos'][0], q['pos'][2], q['pos'][0] + 1, q['pos'][2] + 1))), None)
    if wet_ground:
        wx, _, wz = wet_ground['pos']
        with np.load(a.out / 'measured.npz') as measured:
            mx, mz, _, _ = map(int, measured['bounds'])
            wy = int(measured['top'][wz - mz, wx - mx])
        wp = (wx, wy, wz)
        if open_state(e.state(*wp, original=True)):
            raise ValueError('Water rejection test requires measured original terrain')
        negative.append(dict(name='foundation-in-reserved-water-strip', rejected=reserved(wp, e.state(*wp, original=True)), pos=list(wp)))
    # An isolated test solid must not be accepted merely because it is inside
    # the candidate volume. This uses the same independent ground labels.
    fp = next(((xx, spec['bounds'][4], zz) for xx in range(spec['bounds'][0], spec['bounds'][3] + 1)
               for zz in range(spec['bounds'][2], spec['bounds'][5] + 1)
               if all(open_state(e.state(xx + dx, spec['bounds'][4] + dy, zz + dz))
                      for dx, dy, dz in ((0, 0, 0), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))), None)
    if fp is None: raise ValueError('No isolated air cell available for support rejection test')
    def floating_fault():
        test, pal = voxel_box(e, bounds); test_labels, _ = label(np.asarray([not open_state(v) for v in pal])[test]); test_roots = set(map(int, np.unique(test_labels[0]))); test_roots.discard(0)
        return int(test_labels[fp[1] - bounds[1], fp[2] - bounds[2], fp[0] - bounds[0]]) not in test_roots
    fault('unsupported-solid-inside-declared-volume', fp, 'minecraft:stone_bricks', floating_fault)
    if not all(q['rejected'] for q in negative): errors.append(['negative-fault-detection-failed'])
    report = dict(errors=errors, cells=len(changes), public_nodes=proof['nodes'], reachable_public_nodes=proof['reachable_nodes'],
                  full_width_routes=len(d['full_width_routes']), new_floating_solids=floating[:40], newly_detached_retained_cells=len(detached),
                  swept_player_edges=edge_checks, swept_reachable_surfaces=len(reached), negative_cases=negative,
                  full_length_boarding_edge=edge_rows, minimum_boarding_aisle_width=min((q['continuous_width'] for q in edge_rows), default=None),
                  unguarded_public_drop_edges=exposed, intentional_open_boarding_edges=len(permitted_edges),
                  grounded_component_method='Six-face voxel connectivity to measured lower terrain; not a structural engineering calculation',
                  exact_capture_chunks=read(a.out / 'capture.json')['chunk_statuses']['full'], world_written=False,
                  native_registration_pending=True, through_service_complete=False)
    write(a.out / 'offline-verification.json', report)
    print('JSON layout checks:', len(errors), 'errors;', proof['nodes'], 'reachable public surfaces')
    if errors: raise ValueError(errors)


def vehicle(a):
    """Continuous visible-model sweep for one declared cardinal platform.

    The native saved rail and live door callbacks remain separate evidence.
    A diagonal layout must use a separate oriented sampled-model verifier.
    """
    from check_kamonomiya_visible_models import clipped_half_width
    e = Editor(a.out); d = read(a.out / 'station-design.json'); plan = read(a.out / 'native-station-plan.json')
    model = a.out / 'vehicle-model'; report = read(model / (d['vehicle'] + '.json')); packs = read(model / 'active-pack-check.json')
    if any(q['mtr_overrides'] for q in packs['packs']) or not report['all_selected_conditions_enclosed']:
        raise ValueError('Model conditions or active asset provenance incomplete')
    if len(plan['rails']) != 1: raise ValueError('One compact platform expected')
    rail = plan['rails'][0]; pa, pb = rail['from'], rail['to']; along = 0 if pa[2] == pb[2] else 2; across = 2 - along
    if pa[1] != pb[1] or pa[across] != pb[across] or pa[along] == pb[along]: raise ValueError('Only level cardinal vehicle sweep is supported')
    with np.load(model / (d['vehicle'] + '-visible-cubes.npz')) as f:
        cubes, slides, names = f['cubes'], f['door_slides'], list(map(str, f['names']))
    bands = []; low, high = np.asarray(report['visible_motion_bounds']); horizontal, longitudinal, vertical = .15, .15, .03
    extent = max(abs(low[2]), abs(high[2])) + longitudinal
    for y in range(math.floor(low[1] - vertical), math.ceil(high[1] + vertical)):
        widths = [(w, name) for v, s, name in zip(cubes, slides, names) if (w := clipped_half_width(v, s, y - vertical, y + 1 + vertical)) is not None]
        if widths:
            width, name = max(widths); bands.append(dict(y=[y, y + 1], visible_half_width=width, swept_half_width=width + horizontal, widest_part=name))
    obstacles = []; tested = 0
    for band in bands:
        lo = [0., pa[1] + band['y'][0], 0.]; hi = [0., pa[1] + band['y'][1], 0.]
        lo[along] = min(pa[along], pb[along]) + .5 - extent; hi[along] = max(pa[along], pb[along]) + .5 + extent
        lo[across] = pa[across] + .5 - band['swept_half_width']; hi[across] = pa[across] + .5 + band['swept_half_width']
        for x in range(math.floor(lo[0]), math.ceil(hi[0])):
            for z in range(math.floor(lo[2]), math.ceil(hi[2])):
                y = int(lo[1]); state = e.state(x, y, z); tested += 1
                for bounds in collision(state):
                    if all(lo[i] < (x, y, z)[i] + bounds[i + 3] and hi[i] > (x, y, z)[i] + bounds[i] for i in range(3)):
                        obstacles.append(dict(pos=[x, y, z], state=state, band=band['y']))
    floors = [p for p in report['parts'] if p['kind'] == 'FLOOR']; doors = [p for p in report['parts'] if p['kind'] == 'DOORWAY']
    floor_half = max(abs(p['closed_bounds'][s][0]) for p in floors for s in (0, 1)); doorway_half = max(abs(p['closed_bounds'][s][0]) for p in doors for s in (0, 1))
    edge = d['boarding_edge_z' if across == 2 else 'boarding_edge_x']; distance = abs(edge - pa[across] - .5)
    gap = distance - floor_half; floor_y = pa[1] + min(p['closed_bounds'][0][1] for p in floors); doorway_span = max(p['closed_bounds'][1][2] - p['closed_bounds'][0][2] for p in doors)
    errors = []
    if obstacles: errors.append('visible swept vehicle intersects saved blocks')
    if gap >= .6 or gap < 0 or floor_y != d['rail_level'] + 1 or doorway_span < .9: errors.append('doorway/floor geometric boarding condition failed')
    result = dict(errors=errors, model=d['vehicle'], selected_parts=report['selected_part_instances'], bands=bands,
                  visible_cube_count=len(cubes), source_visible_bounds=report['visible_motion_bounds'], tested_saved_blocks=tested,
                  obstacle_count=len(obstacles), obstacles=obstacles[:40], continuous_straight_sweep=True,
                  native_rail_math_verified=False, native_boarding_runtime_verified=False, rendered_frame_verified=False,
                  horizontal_margin=horizontal, vertical_margin=vertical, longitudinal_margin=longitudinal,
                  visible_platform_gap=distance-max(abs(low[0]),abs(high[0])), residual_horizontal_clearance=distance-max(abs(low[0]),abs(high[0]))-horizontal,
                  boarding_support=dict(gap=gap, player_footprint=.6, floor_y=floor_y, platform_feet_y=d['rail_level']+1,
                                        doorway_longitudinal_span=doorway_span, doorway_trigger_halfwidth=doorway_half,
                                        minimum_overlap_at_gap_midpoint=(.6-gap)/2, open_doors_required=True),
                  world_written=False, through_service_complete=False)
    write(a.out / 'visible-model-sweep.json', result)
    print('Visible model:', len(obstacles), 'obstacles;', gap, 'm floor-support gap; native callbacks pending')
    if errors: raise ValueError(errors)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('mode', choices=('author', 'verify', 'vehicle'))
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    globals()[args.mode](args)
