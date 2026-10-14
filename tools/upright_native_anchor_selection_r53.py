"""Finite current-lining anchor candidates, never WORLD writes or admission."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import numpy as np
from measure_world_r40 import MeasuredWorld

ROOT = Path(__file__).resolve().parents[1]
AIR = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}
LINING = {'projectseele:nerv_shaft_panel', 'projectseele:nerv_machine_edge',
          'projectseele:nerv_strip_light[lit=true]'}
BEARING = {'projectseele:nerv_shaft_panel', 'projectseele:nerv_machine_edge',
           'projectseele:nerv_structural_panel', 'projectseele:nerv_wall_panel',
           'projectseele:nerv_floor_panel', 'minecraft:iron_block',
           'minecraft:black_concrete', 'minecraft:gray_concrete',
           'minecraft:deepslate_bricks', 'minecraft:polished_basalt[axis=y]'}
RADIUS = math.sqrt(2) * .06 + .0002


class NativeBearingCells:
    """Sparse measured bearing cells; ownership remains a separate predicate."""
    def __init__(self, world):
        self.world, self.cache = world, {}

    def near(self, origin, span):
        low, high = np.floor(origin).astype(int)-span, np.floor(origin).astype(int)+span
        for cx, sy, cz in itertools.product(range(low[0]//16, high[0]//16+1),
                                            range(low[1]//16, high[1]//16+1),
                                            range(low[2]//16, high[2]//16+1)):
            key = cx, sy, cz
            if key not in self.cache:
                data = self.world.tiles.get(key)
                if data is None or self.world.status.get((cx, cz)) != 'full':
                    self.cache[key] = np.empty((0, 3), dtype=int)
                else:
                    palette, ids = data
                    bearing = [i for i, state in enumerate(palette) if state in BEARING]
                    indices = np.flatnonzero(np.isin(ids, bearing))
                    self.cache[key] = np.column_stack([(indices & 15)+cx*16,
                        (indices >> 8)+sy*16, ((indices >> 4) & 15)+cz*16])
            points = self.cache[key]
            for point in points[np.all((points >= low) & (points <= high), axis=1)]:
                yield tuple(map(int, point))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_applied(world, npz, receipt):
    doc = read(receipt)
    root_receipt = doc.get('receipt', {})
    verified_root_apply = (doc.get('world_written') is True and doc.get('root_author') is True
                           and root_receipt.get('verified') is True and doc.get('sections', 0) > 0
                           and doc.get('full_selected_sections_read_back') == doc['sections'])
    require(doc.get('applied') is True or doc.get('APPLIED') is True or verified_root_apply,
            'Explicit applied:true receipt required; unbuilt lining is forbidden')
    actual_world = doc.get('world', root_receipt.get('world', ''))
    require(actual_world and Path(actual_world).resolve() == world.resolve(), 'Receipt belongs to another WORLD')
    digest = sha(npz)
    require(doc.get('npz_sha256', doc.get('candidate_sha256')) == digest, 'Applied lining NPZ hash mismatch')
    return digest


class Ownership:
    def __init__(self, path):
        self.file = np.load(path, allow_pickle=False)
        keys = self.file['section_keys']
        self.before, self.after = self.file['before'], self.file['after']
        self.palette = tuple(map(str, self.file['palette']))
        self.file.close()
        require(keys.ndim == 2 and keys.shape[1] == 3, 'section_keys must be [cx,cz,sy]')
        require(self.before.shape == self.after.shape == (len(keys), 4096), 'Complete y,z,x arrays required')
        self.index = {tuple(map(int, k)): i for i, k in enumerate(keys)}
        require(len(self.index) == len(keys), 'Duplicate ownership sections')
        require(int(self.before.min()) >= 0 and int(self.after.min()) >= 0
                and int(self.before.max()) < len(self.palette)
                and int(self.after.max()) < len(self.palette), 'Invalid palette index')

    def expected(self, p):
        x, y, z = p
        i = self.index.get((x // 16, z // 16, y // 16))
        if i is None:
            return None
        at = ((y & 15) << 8) | ((z & 15) << 4) | (x & 15)
        before, after = int(self.before[i, at]), int(self.after[i, at])
        state = self.palette[after]
        return state if before != after and state in LINING else None


def retained_city(p):
    x, y, z = p
    if x >= 89 and -56 <= z <= -46:
        return False
    return -410 <= y <= 80 and -54 <= z <= -18 and any(cx-18 <= x <= cx+18 for cx in (-12, 30, 72))


def retained_banks(p):
    x, y, z = p
    chambers = -29 <= x <= 89 and -1064 <= y <= -930 and any(a <= z <= b for a, b in ((106, 142), (58, 94), (10, 46)))
    connectors = -54 <= x <= 108 and -1037 <= y <= -945 and (95 <= z <= 105 or 47 <= z <= 57)
    return chambers or connectors


def segment_box(a, b, box, radius=0):
    a, b, box = np.asarray(a), np.asarray(b), np.asarray(box)
    low, high, delta = box[:3]-radius, box[3:]+radius, b-a
    lo, hi = 0., 1.
    for axis in range(3):
        if abs(delta[axis]) < 1e-12:
            if a[axis] <= low[axis] or a[axis] >= high[axis]:
                return False
        else:
            x, y = (low[axis]-a[axis])/delta[axis], (high[axis]-a[axis])/delta[axis]
            lo, hi = max(lo, min(x, y)), min(hi, max(x, y))
            if lo >= hi:
                return False
    return lo < hi


class Gates:
    def __init__(self, candidate, interface):
        doc, native = read(candidate), read(interface)
        require(native['root_gate_candidate']['sha256'] == sha(candidate), 'Gate interface/source mismatch')
        declared = {g['resource']: g for g in doc['gates']}
        actual = {g['resource']: g for g in native['gates']}
        require(declared.keys() == actual.keys(), 'Incomplete actual gate interface')
        self.boxes, self.grid, self.proxies = [], defaultdict(set), set()
        for name, gate in actual.items():
            require(gate['visual'] == declared[name]['visual'], 'Gate UUID changed')
            box = list(map(float, gate['complete_mesh_motion_broadphase_bounds']))
            require(len(box) == 6 and all(math.isfinite(v) for v in box)
                    and all(box[j] < box[j+3] for j in range(3)), 'Full gate-motion envelope required')
            n = len(self.boxes)
            self.boxes.append((name, box))
            for key in self.keys(box[:3], box[3:]):
                self.grid[key].add(n)
            table = gate['collision_steps']
            file = (interface.parent / table['cells_file']).resolve()
            require(file.is_relative_to(interface.parent.resolve()), 'Gate table path escape')
            require(sha(file) == table['sha256'], 'Gate proxy hash mismatch')
            for step in json.loads(gzip.decompress(file.read_bytes())):
                for row in step:
                    self.proxies.add(tuple(row['position']))

    @staticmethod
    def keys(low, high):
        return itertools.product(*(range(math.floor(low[j]/32), math.floor(high[j]/32)+1) for j in range(3)))

    def intersects(self, a, b, radius):
        candidates = set()
        for key in self.keys(np.minimum(a, b)-radius, np.maximum(a, b)+radius):
            candidates.update(self.grid.get(key, ()))
        return next((self.boxes[i][0] for i in candidates if segment_box(a, b, self.boxes[i][1], radius)), None)

    def excludes_cell(self, p):
        centre = np.asarray(p, float)+.5
        return tuple(p) in self.proxies or bool(self.intersects(centre, centre, .500001))


def source_check(source, model_file, transfer_file):
    require(sha(model_file) == source['model_source_sha256'], 'Capture model SHA differs')
    require(sha(transfer_file) == source['head_transfer_source_sha256'], 'Head-transfer SHA differs')
    model, transfer = read(model_file), read(transfer_file)
    require(transfer['outer_source_sha256'] == source['model_source_sha256'], 'Wrong outer model dependency')
    parts = {p['name']: p for p in model['parts']}
    parts.update({p['name']: p for p in transfer['parts']})
    vertices = np.concatenate([np.array(p['triangles_rgb']).reshape(-1, 6)[:, :3]
                               for p in parts.values() if p['frame'] in ('RUNNER_NEG', 'RUNNER_POS')])
    minimum = float(vertices[:, 1].min())
    web = float(model['rail_web_section'][1])
    require(minimum-web > RADIUS+.05, 'No source-proven web-front capture escape')
    for row in source['sockets']:
        tri = np.asarray(row['actual_rail_weld_triangle'], float)
        point, normal = np.asarray(row['rail_bearing']), np.asarray(row['normal'])
        require(tri.shape == (3, 3) and np.isfinite(tri).all(), 'Actual finite weld triangle required')
        cross = np.cross(tri[1]-tri[0], tri[2]-tri[0])
        require(np.linalg.norm(cross) > 1e-8 and abs(np.linalg.norm(normal)-1) < 1e-7, 'Invalid weld face/normal')
        require(np.linalg.norm(cross/np.linalg.norm(cross)-normal) < 1e-6
                and np.linalg.norm(tri.mean(axis=0)-point) < 1e-6, 'Socket differs from source facet')
    return dict(capture_minimum_local_y=minimum, web_front_local_y=web, source_halfspace_margin_m=minimum-web,
                capture_cross_section=[float(vertices[:, 0].min()), minimum,
                                       float(vertices[:, 0].max()), float(vertices[:, 1].max())],
                weld_centroid_local_x=(model['rail_web_section'][0]+2*model['rail_web_section'][2])/3)


def folded_path(origin, outward, bearing, normal):
    origin, outward, bearing, normal = map(np.asarray, (origin, outward, bearing, normal))
    first, approach = origin+outward*.5, bearing+normal*.15
    if min(np.dot(approach-origin, outward), np.dot(bearing-origin, outward)) < .25:
        return None
    path = [origin, first, approach, bearing]
    lengths = [np.linalg.norm(b-a) for a, b in zip(path, path[1:])]
    return path if min(lengths) > 1e-6 and sum(lengths) <= 8 else None


def source_folded_paths(row, bearing, native_normal, proof, limit=8., radius=RADIUS, source_exit=.12):
    """Avoid the complete moving capture cross-section along its whole rail.

    The prism is conservative over longitudinal head motion. It uses selected
    source vertices, not an inferred empty channel or a point-only clearance.
    """
    origin, normal = np.asarray(row['rail_bearing']), np.asarray(row['normal'])
    triangle = np.asarray(row['actual_rail_weld_triangle'])
    x = triangle[1]-triangle[0]; x /= np.linalg.norm(x)
    y = -normal; z = np.cross(x, y)
    basis = np.stack([x, y, z], axis=1)
    centre = origin-x*proof['weld_centroid_local_x']-y*proof['web_front_local_y']
    section = proof['capture_cross_section']
    prism = [section[0], section[1], -1e6, section[2], section[3], 1e6]
    bearing, native_normal = np.asarray(bearing), np.asarray(native_normal)
    first, approach = origin+normal*source_exit, bearing+native_normal*max(.15, radius+.03)
    exterior = first+x*row['side']*1.5
    # Keep the middle traverse outside the real head's lateral cross-section.
    lateral = np.dot(exterior-centre, x)
    around = approach+x*(lateral-np.dot(approach-centre, x))
    proposals = [[origin, first, approach, bearing],
                 [origin, first, exterior, around, approach, bearing]]
    for proposal in proposals:
        path = [proposal[0]]
        for p in proposal[1:]:
            if np.linalg.norm(p-path[-1]) > 1e-6:
                path.append(p)
        lengths = [np.linalg.norm(b-a) for a, b in zip(path, path[1:])]
        if len(path) < 3 or sum(lengths) > limit:
            continue
        local = [(p-centre)@basis for p in path]
        if any(segment_box(a, b, prism, radius) for a, b in zip(local, local[1:])):
            continue
        if segment_box(local[-1], local[-1], prism, .150001):
            continue
        yield path


def finite_face(shapes, point, normal, half_width=.100001):
    point, normal = np.asarray(point), np.asarray(normal)
    require(abs(np.linalg.norm(normal)-1) < 1e-8 and np.count_nonzero(normal) == 1, 'Cardinal actual face required')
    axis = int(np.flatnonzero(normal)[0])
    for raw in shapes:
        box = np.asarray(raw)
        plane = box[axis+3] if normal[axis] > 0 else box[axis]
        if abs(point[axis]-plane) <= .0002 and all(box[j]+half_width <= point[j] <= box[j+3]-half_width
                                                for j in range(3) if j != axis):
            return True
    return False


def path_clear(path, target, world, shapes, gates, radius=RADIUS):
    for index, (a, b) in enumerate(zip(path, path[1:])):
        if gates.intersects(a, b, radius):
            return False, 'complete_gate_envelope'
        low, high = np.floor(np.minimum(a, b)-radius).astype(int), np.floor(np.maximum(a, b)+radius).astype(int)
        for p in itertools.product(*(range(low[j], high[j]+1) for j in range(3))):
            state = world.block(p)
            if state in AIR:
                continue
            if state is None or state not in shapes:
                return False, 'unknown_chunk_or_native_shape'
            for raw in shapes[state]:
                box = np.asarray(raw)+np.tile(p, 2)
                if not segment_box(a, b, box, radius):
                    continue
                if not rod_box_intersects_native(a, b, box, radius):
                    continue
                # Only the last perpendicular cap mates with this exact face.
                if target is not None and tuple(p) == tuple(target) and index == len(path)-2:
                    continue
                return False, 'native_collision'
    return True, ''


def rod_box_intersects_native(a, b, box, radius=RADIUS):
    """Exact finite square rod OBB versus one actual native AABB after pruning."""
    a, b, box = np.asarray(a, float), np.asarray(b, float), np.asarray(box, float)
    delta = b-a; length = np.linalg.norm(delta)
    require(length > 1e-9, 'Finite nonzero actual rod required')
    z = delta/length; x = np.cross(z, [0., 1, 0])
    if np.linalg.norm(x) < .1:
        x = np.cross(z, [1., 0, 0])
    x /= np.linalg.norm(x); y = np.cross(z, x)
    basis = np.stack([x, y, z], axis=1)
    half_width = (radius-.0002)/math.sqrt(2)+.0002
    half = np.array([half_width, half_width, length/2+.0002])
    native_half = (box[3:]-box[:3])/2
    centres = (box[3:]+box[:3]-a-b)/2
    axes = [*basis.T, *np.eye(3), *[np.cross(axis, unit) for axis in basis.T for unit in np.eye(3)]]
    for axis in axes:
        if np.linalg.norm(axis) < 1e-12:
            continue
        extent = np.abs(axis@basis)@half+np.abs(axis)@native_half
        if abs(centres@axis) >= extent-1e-9:
            return False
    return True


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'sockets', 'gates', 'terminal-seats', 'lining-npz', 'applied-receipt', 'native-shapes', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--gate-interface', type=Path)
    p.add_argument('--model', type=Path, default=ROOT/'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json')
    p.add_argument('--head-transfer', type=Path, default=ROOT/'src/main/resources/assets/projectseele/mesh/outer_head_transfer_r53.json')
    p.add_argument('--include-retained-city-shafts', action='store_true')
    p.add_argument('--include-retained-banks', action='store_true')
    p.add_argument('--bank-plan', type=Path)
    p.add_argument('--deep-applied', type=Path)
    p.add_argument('--exclude-slots', type=Path)
    p.add_argument('--resume-current', type=Path)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    args.base = args.base.resolve()
    require(args.base.is_dir() and (args.base/'level.dat').is_file(), 'Explicit actual WORLD required')
    require(not args.output.exists() and not args.output.resolve().is_relative_to(args.base), 'Fresh output outside WORLD required')
    lining_sha = verify_applied(args.base, args.lining_npz, args.applied_receipt)
    source, terminal, shapes = read(args.sockets), read(args.terminal_seats), read(args.native_shapes)
    geometry_check = source_check(source, args.model, args.head_transfer)
    require(source['model_source_sha256'] == terminal['model_source_sha256']
            and source['directory_geometry_sha256'] == terminal['directory_geometry_sha256'], 'Wrong terminal source')
    requests, fixed = {r['socket_id']: r for r in source['sockets']}, {r['socket_id']: r for r in terminal['seats']}
    require(len(requests) == len(source['sockets']), 'Duplicate socket identity')
    end_ids = set()
    for v in range(3):
        for bank in range(1, 4):
            for side in (-1, 1):
                rows = [r for r in requests.values() if r['leg'] == f'unit{v}/exit{bank}/upright_continuous' and r['side'] == side]
                require(rows, 'Missing current terminal source')
                end_ids.add(max(rows, key=lambda r: r['along_curve_m'])['socket_id'])
    require(len(fixed) == 18 and set(fixed) == end_ids, 'Exactly the current proven 18 terminals required')
    for key, seat in fixed.items():
        require(seat['status'] == 'FULL_CARRIER_STROKE_FULL_HATCH_AND_FIXED_FRAME_SOURCE_CLEAR'
                and seat['leg'] == requests[key]['leg'] and seat['side'] == requests[key]['side']
                and np.allclose(seat['rail_bearing'], requests[key]['rail_bearing'], atol=1e-9, rtol=0), 'Terminal proof changed')
    interface = args.gate_interface or args.gates.parent/'CURRENT_TYPED_GATE_INTERFACE.json'
    gates, ownership = Gates(args.gates, interface), Ownership(args.lining_npz)
    if args.include_retained_banks:
        require(args.bank_plan and args.deep_applied and args.exclude_slots,
                'Retained banks require explicit original plan, deep APPLIED and future slot exclusions')
        plan, deep = read(args.bank_plan), read(args.deep_applied)
        require(plan.get('world_written') is True and plan.get('full_component_exact_readback') is True
                and plan.get('source') == 'frozen original bank geometry' and plan.get('chamber_depth') == 37
                and plan.get('connector_length') == 11 and deep.get('world_written') is True
                and deep.get('dy') == -384 and deep.get('complete_source_and_target_exact_readback') is True,
                'Retained bank source/deep placement not verified')
    if args.exclude_slots:
        gates.proxies.update(tuple(c['position']) for c in read(args.exclude_slots)['changes'])
    world = MeasuredWorld(args.base, 'projectseele:geofront')
    for row in requests.values():
        origin = np.floor(row['rail_bearing']).astype(int)
        world.box(tuple(origin-9), tuple(origin+9))
    for row in fixed.values():
        world.box(tuple(row['at']), tuple(row['at']))
    world.load()
    seats, pending = [], []
    for key, seat in fixed.items():
        state = world.block(tuple(seat['at']))
        native = [np.asarray(box)+np.tile(seat['at'], 2) for box in shapes.get(state, [])]
        if state != seat['state'] or not finite_face(native, seat['bearing'], seat['normal']):
            pending.append(dict(socket_id=key, reason='terminal_native_foundation_not_current', at=seat['at'], actual=state))
        else:
            seats.append(dict(seat, selected_by='immutable_18_source_checked_terminal_input'))
    preserved = set()
    if args.resume_current:
        prior = read(args.resume_current)
        prior_sha = sha(args.resume_current)
        expected = dict(model_source_sha256=source['model_source_sha256'],
                        directory_geometry_sha256=source['directory_geometry_sha256'],
                        head_transfer_source_sha256=source['head_transfer_source_sha256'],
                        socket_requests_sha256=sha(args.sockets), gate_candidate_sha256=sha(args.gates),
                        gate_interface_sha256=sha(interface), native_shapes_sha256=sha(args.native_shapes),
                        lining_npz_sha256=lining_sha, terminal_seats_sha256=sha(args.terminal_seats))
        require(prior.get('world') == str(args.base) and all(prior.get(k) == v for k, v in expected.items()),
                'Explicit resume is not this current WORLD/source candidate')
        for seat in prior['seats']:
            key = seat['socket_id']
            if key in fixed:
                continue
            require(key in requests and key not in preserved, 'Duplicate/foreign resumed socket')
            at = tuple(seat['at']); state = world.block(at)
            native = [np.asarray(box)+np.tile(at, 2) for box in shapes.get(state, [])]
            if state == seat['state'] and not gates.excludes_cell(at) and finite_face(native, seat['bearing'], seat['normal']):
                seats.append(dict(seat, preserved_clearance_receipt_sha256=prior_sha))
                preserved.add(key)
    offsets = tuple(itertools.product(range(-8, 9), repeat=3))
    for number, row in enumerate(requests.values(), 1):
        if row['socket_id'] in fixed or row['socket_id'] in preserved:
            continue
        origin, outward = np.asarray(row['rail_bearing']), np.asarray(row['normal'])
        ox, oy, oz = map(int, np.floor(origin))
        near, candidates, failures = origin+outward*.5, [], Counter()
        for dx, dy, dz in offsets:
            at = (ox+dx, oy+dy, oz+dz)
            state = world.block(at)
            if state not in BEARING or gates.excludes_cell(at):
                continue
            expected = ownership.expected(at)
            purpose = 'applied_current_lining' if expected == state else 'retained_original_city_shaft' if (
                args.include_retained_city_shafts and retained_city(at)) else 'retained_original_bank_or_connector' if (
                args.include_retained_banks and retained_banks(at)) else None
            if purpose is None or state not in shapes:
                continue
            for raw in shapes[state]:
                box = np.asarray(raw)+np.tile(at, 2)
                for axis in range(3):
                    if any(box[j+3]-box[j] < .220001 for j in range(3) if j != axis):
                        continue
                    for sign in (-1, 1):
                        face = np.clip(near, box[:3]+.11, box[3:]-.11)
                        face[axis] = box[axis+3] if sign > 0 else box[axis]
                        normal = np.zeros(3); normal[axis] = sign
                        distance = float(np.linalg.norm(face-origin))
                        if not .15 <= distance <= 7.98 or (origin-face)[axis]*sign <= .12:
                            continue
                        for path in source_folded_paths(row, face, normal, geometry_check):
                            length = sum(float(np.linalg.norm(b-a)) for a, b in zip(path, path[1:]))
                            candidates.append((length, distance, at, state, face, normal, path, purpose))
        chosen = None
        for candidate in sorted(candidates, key=lambda c: (c[0], c[1], c[2])):
            clear, reason = path_clear(candidate[6], candidate[2], world, shapes, gates)
            if clear:
                chosen = candidate
                break
            failures[reason] += 1
        if chosen is None:
            pending.append(dict(socket_id=row['socket_id'], leg=row['leg'], side=row['side'],
                                reason='no_source_safe_folded_path_to_owned_native_face', failures=dict(failures)))
        else:
            length, distance, at, state, face, normal, path, purpose = chosen
            seats.append(dict(socket_id=row['socket_id'], at=list(at), state=state, bearing=face.tolist(), normal=normal.tolist(),
                              connector_via_world=[p.tolist() for p in path[1:-1]], connector_distance_m=distance,
                              connector_path_length_m=length, finite_connector_limit_m=7.98, selected_by=purpose,
                              actual_weld_normal=row['normal'], source_exit_metres=.5,
                              capture_halfspace_source_checked=True, native_capsule_clear=True,
                              complete_gate_envelope_clear=True, full_carrier_mesh_admission_pending=True))
        if number % 100 == 0:
            print(f'current folded anchors {number}/{len(requests)} selected={len(seats)} pending={len(pending)}', flush=True)
    result = dict(schema='projectseele.r52.upright-native-seat-selection.v1',
                  status='CURRENT_NATIVE_FACES_FOLDED_LOCAL_SOURCE_CANDIDATE', world=str(args.base),
                  world_written=False, production_enable=False, model_source_sha256=source['model_source_sha256'],
                  directory_geometry_sha256=source['directory_geometry_sha256'], head_transfer_source_sha256=source['head_transfer_source_sha256'],
                  socket_requests_sha256=sha(args.sockets), terminal_seats_sha256=sha(args.terminal_seats),
                  gate_candidate_sha256=sha(args.gates), gate_interface_sha256=sha(interface),
                  applied_receipt_sha256=sha(args.applied_receipt), lining_npz_sha256=lining_sha,
                  native_shapes_sha256=sha(args.native_shapes), source_model_check=geometry_check,
                  finite_connector_limit_m=7.98, seats=seats, pending=pending,
                  pending_final_full_carrier_and_fixed_steel_source_review=True,
                  no_old_world_or_partial_candidate_fallback=True)
    result['explicit_current_resume_sha256'] = sha(args.resume_current) if args.resume_current else None
    result['preserved_current_seats'] = len(preserved)
    result['retained_bank_plan_sha256'] = sha(args.bank_plan) if args.include_retained_banks else None
    result['retained_bank_deep_receipt_sha256'] = sha(args.deep_applied) if args.include_retained_banks else None
    result['excluded_future_slot_sha256'] = sha(args.exclude_slots) if args.exclude_slots else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n', 'utf-8')
    print(json.dumps(dict(seats=len(seats), pending=len(pending), world_written=False)), flush=True)


if __name__ == '__main__':
    main()
