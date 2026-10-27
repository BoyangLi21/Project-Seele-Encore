"""Stage a source-preserving Unit03 rig, measured physics and motion deltas.

The output is an isolated review bundle, never an installer. Geometry is only
uniformly scaled/reflected. In particular, no deformation fit or dorsal boolean
is applied. Runtime rig-key routing and native review remain explicit gates.
"""
import argparse
import copy
import hashlib
import json
import math
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import ConvexHull, cKDTree
from scipy.spatial.transform import Rotation as R


def read(path):
    return json.loads(path.read_text('utf8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), 'utf8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unit(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-12)


def matrix(bones, name, cache, rotations=None, positions=None):
    if name in cache:
        return cache[name]
    bone = bones[name]
    p = np.asarray(bone['pivot']) * [-1, 1, 1] / 16
    rot = R.from_euler('xyz', np.asarray(bone.get('rotation', [0, 0, 0])) * [-1, -1, 1], degrees=True).as_matrix()
    if rotations is not None and name in rotations:
        rot = rotations[name]
    m = np.eye(4)
    m[:3, :3] = rot
    m[:3, 3] = p - rot @ p
    if positions is not None and name in positions:
        m[:3, 3] += positions[name]
    if bone.get('parent'):
        m = matrix(bones, bone['parent'], cache, rotations, positions) @ m
    cache[name] = m
    return m


FINGERS = {
    'index': [[.623, 2.129, -.006], [.626, 2.065, -.004], [.595, 1.990, .022], [.540, 1.912, .065]],
    'middle': [[.590, 2.125, -.040], [.601, 2.055, -.030], [.568, 1.980, -.011], [.490, 1.888, .025]],
    'ring': [[.560, 2.125, -.090], [.568, 2.056, -.100], [.536, 1.980, -.060], [.462, 1.894, -.017]],
    'little': [[.526, 2.125, -.135], [.533, 2.060, -.133], [.497, 1.990, -.105], [.455, 1.938, -.070]],
    'thumb': [[.560, 2.215, -.010], [.543, 2.187, .010], [.501, 2.112, .055], [.480, 2.055, .089]],
}


def skeleton(reference, to_geo):
    # Authored seeds are in the user's OBJ coordinates. All are recorded for
    # review; unlike the rejected binder they move the rig, never the surface.
    seeds = {'root': [0, -.004059, 0], 'torso_lower': [0, 2.66, 0],
             'torso_upper': [0, 3.02, 0], 'aim_pitch': [0, 3.57, -.09],
             'neck': [0, 3.75, .015], 'head': [0, 3.75, .015],
             'horn': [0, 4.10, .1], 'entry_plug': [0, 3.78, -.27],
             'plug_hatch_l': [0, 3.78, -.27], 'plug_hatch_r': [0, 3.78, -.27],
             'dorsal_cover': [0, 3.78, -.27], 'dorsal_liner': [0, 3.78, -.27]}
    for side, sign in [('l', 1), ('r', -1)]:
        for name, point in {'clavicle': [0, 3.57, -.09], 'arm': [.45, 3.57, -.09],
                            'forearm': [.54, 2.95, -.13], 'wrist': [.585, 2.242, -.09],
                            'hand': [.585, 2.242, -.09], 'pylon': [.45, 3.57, -.18],
                            'leg': [.18, 2.66, -.04], 'shin': [.315, 1.57, -.07],
                            'ankle': [.49, .32, -.07], 'foot': [.49, .32, -.07]}.items():
            seeds[name + '_' + side] = np.asarray(point) * [sign, 1, 1]
    for n in ('knife', 'cannon', 'lance', 'n2'):
        seeds[n] = [-.565, 2.08, -.035]
    bones = {}
    for b in reference:
        name = b['name']
        if name.startswith('r45_hand_') or name.startswith('r45_knife_'):
            continue
        if name in seeds:
            point = to_geo(seeds[name])
        elif name.startswith('finger_'):
            side = name[-1]
            digit = name.split('_')[1]
            if digit not in FINGERS:
                continue
            joint = 2 if '_distal' in name else 1 if '_tip' in name else 0
            point = to_geo(np.asarray(FINGERS[digit][joint]) * ([1, 1, 1] if side == 'l' else [-1, 1, 1]))
        else:
            # Decorative compatibility aliases are empty and inherit their
            # measured parent's pivot; no copied Unit01 dimensions survive.
            parent = b.get('parent', 'root')
            point = np.asarray(bones.get(parent, bones.get('root', {'pivot': [0, 0, 0]}))['pivot'])
        row = dict(name=name, pivot=np.asarray(point).tolist())
        if b.get('parent'):
            row['parent'] = b['parent']
        bones[name] = row
    for side in ('l', 'r'):
        for joint, owner in [('elbow', 'forearm'), ('knee', 'shin')]:
            name = f'r30_{joint}_socket_{side}'
            bones[name] = dict(name=name, parent=owner+'_'+side, pivot=bones[owner+'_'+side]['pivot'])
    bones['unit03_shared_unit01_r53'] = dict(name='unit03_shared_unit01_r53', parent='root', pivot=[0, 0, 0])
    return bones, {k: np.asarray(v).tolist() for k, v in seeds.items()}


def hands(bones, to_native, source_hand_points, reference_contract):
    result = dict(schema='projectseele.anatomical-hands.r45.v1', rig=4,
                  source='Original supplied Unit03 curved hand surface', hands={}, new_bones=[],
                  angle_convention='Source curled bind is zero. Controls are local delta rotations, not Unit01 absolute flex.')
    chains, audit = {}, []
    for side, sign in [('l', 1), ('r', -1)]:
        native_points = to_native(source_hand_points[source_hand_points[:, 0] * sign > 0])
        tree = cKDTree(native_points)
        roots = {digit: to_native(np.asarray(points[0])*[sign, 1, 1]) for digit, points in FINGERS.items()}
        across = unit(roots['index']-roots['little'])
        along = np.mean([roots[d] for d in ('index', 'middle', 'ring', 'little')], axis=0)-to_native([sign*.585, 2.242, -.09])
        along = unit(along-across*(along@across))
        palm_normal = unit(np.cross(across, along))
        if palm_normal[0]*sign < 0: palm_normal = -palm_normal
        hand = dict(parent='hand_'+side, palmar_normal_bind=palm_normal.tolist(),
                    longitudinal_bind=along.tolist(), digits={})
        for digit, seed in FINGERS.items():
            points = to_native(np.asarray(seed) * [sign, 1, 1])
            names = []
            records = []
            parent = 'hand_'+side
            cache = {}
            for j in range(3):
                y = unit(points[j+1] - points[j])
                normal = unit(palm_normal - y * (palm_normal @ y))
                x = unit(np.cross(normal, y)); z = unit(np.cross(x, y))
                frame = np.column_stack((x, y, z))
                pm = matrix(bones, parent, cache)
                pivot = (np.linalg.inv(pm) @ np.r_[points[j], 1])[:3]
                local = pm[:3, :3].T @ frame
                name = f'r45_hand_{side}_{digit}_{j+1}'
                spec = dict(name=name, parent=parent, pivot=(pivot*[-1, 1, 1]*16).tolist(),
                            rotation=(R.from_matrix(local).as_euler('xyz', degrees=True)*[-1, -1, 1]).tolist())
                bones[name] = spec
                bind = matrix(bones, name, cache)
                distance = float(tree.query(points[j])[0])*16
                audit.append(dict(bone=name, nearest_surface_distance_pixels=distance,
                                  joint_native=points[j].tolist(), basis_determinant=float(np.linalg.det(frame))))
                records.append(dict(name=name, index=j, head_bind=points[j].tolist(), tip_bind=points[j+1].tolist(),
                                    length=float(np.linalg.norm(points[j+1]-points[j])), rest_flex_degrees=0,
                                    anatomical_limits_degrees=[[-25, 35], [-15, 15], [-20, 20]] if j == 0 else [[-25, 35], [0, 0], [0, 0]],
                                    neutral_local_quaternion_xyzw=R.from_matrix(local).as_quat().tolist(),
                                    inverse_bind_column_major=np.linalg.inv(bind).T.ravel().tolist()))
                result['new_bones'].append(spec)
                names.append(name); parent = name
            hand['digits'][digit] = dict(joints=records)
            chains[side, digit] = dict(points=points, names=names)
        result['hands'][side] = hand
    # The donor supplies action intent, not its anatomical rest angles. Keep
    # deltas deliberately bounded for the already flexed source fingers.
    poses = {}
    base = reference_contract['pose_controls']['relaxed']
    for name, control in reference_contract['pose_controls'].items():
        row = dict(bone_angles={})
        for side in ('l', 'r'):
            for digit in FINGERS:
                for j in range(3):
                    if digit == 'thumb':
                        a = np.asarray(control.get('thumb', base['thumb'])[j], float)
                        b = np.asarray(base['thumb'][j], float)
                    else:
                        a = np.array([control.get(digit, control.get('fingers', [0, 0, 0]))[j], 0, 0.])
                        b = np.array([base.get(digit, base.get('fingers', [0, 0, 0]))[j], 0, 0.])
                    delta = (a-b)*.32
                    limits = np.asarray(result['hands'][side]['digits'][digit]['joints'][j]['anatomical_limits_degrees'])
                    row['bone_angles'][f'r45_hand_{side}_{digit}_{j+1}'] = np.clip(delta, limits[:, 0], limits[:, 1]).tolist()
        poses[name] = row
    result['pose_controls'] = poses
    result['review_limits'] = 'Bounded source-rest deltas only; exact weapon grip and full opening not admitted.'
    return result, chains, audit


def hand_pose(contract, pose):
    rotations = {}
    controls = contract['pose_controls'][pose]['bone_angles']
    for side in ('l', 'r'):
        sign = 1 if side == 'l' else -1
        for digit in contract['hands'][side]['digits'].values():
            for joint in digit['joints']:
                value = np.asarray(controls[joint['name']])*[-1, sign, sign]
                rotations[joint['name']] = (R.from_quat(joint['neutral_local_quaternion_xyzw'])*R.from_euler('xyz', value, degrees=True)).as_matrix()
    return rotations


def segment_distance(p, a, b):
    t = np.clip((p-a)@(b-a)/max((b-a)@(b-a), 1e-12), 0, 1)
    return np.linalg.norm(p-(a+t*(b-a))), t


def hand_weights(point, side, chains):
    options = []
    for digit in FINGERS:
        c = chains[side, digit]
        for j in range(3):
            dist, t = segment_distance(point, c['points'][j], c['points'][j+1])
            options.append((dist, digit, j, t))
    distance, digit, j, t = min(options)
    c = chains[side, digit]
    # Width comes from the original low-poly finger radius, not rig1 surface.
    if point[1] > c['points'][0][1]+.025 or distance > .15:
        return {'hand_'+side: 1.}
    out = {c['names'][j]: 1.}
    if j == 0 and t < .3:
        weight = t/.3
        out = {'hand_'+side: 1-weight, c['names'][j]: weight}
    elif t > .78 and j < 2:
        weight = (t-.78)/.44
        out = {c['names'][j]: 1-weight, c['names'][j+1]: weight}
    elif t < .22 and j > 0:
        weight = (.22-t)/.44
        out = {c['names'][j]: 1-weight, c['names'][j-1]: weight}
    return out


def component_owner(group, material, raw):
    lo, hi = np.asarray(group['bounds'])
    side = 'l' if raw[:, 0].mean() > 0 else 'r'
    if material:
        return ('forearm_' if lo[1] >= 2.23 else 'hand_')+side
    if hi[1] < .5: return 'foot_'+side
    if hi[1] < 1.78: return 'shin_'+side
    if hi[1] < 2.73 and lo[1] >= 1.5: return 'leg_'+side
    if lo[1] >= 3.66 and max(abs(lo[0]), abs(hi[0])) < .16: return 'head'
    if hi[1] > 4.2 or (lo[1] > 3.3 and min(abs(lo[0]), abs(hi[0])) > .275 and lo[2] < -.27): return 'pylon_'+side
    if lo[1] > 2.9 and max(abs(lo[0]), abs(hi[0])) > .53: return 'arm_'+side
    return 'torso_upper' if lo[1] > 2.8 else 'torso_lower'


def surface(a, bones, chains, source, to_native):
    documents = {d['name']: d for d in read(a.old/'COMPONENTS.json')}
    raw = source['source_corners']; norm = source['normalized_corners']
    owners, corner_weights, measurements = [], [], []
    for material, obj in enumerate(('e03_201_0_Untitled.079', 'w03_201_0_Untitled.077')):
        doc = documents[obj]; data = np.load(a.old/(obj+'.npz'))
        labels = data['components'][data['triangles'][:, 0]]
        group_map = {g['id']: g for g in doc['groups']}
        selected = np.flatnonzero(source['material'] == material)
        for local, fi in enumerate(selected):
            group = group_map[int(labels[local])]
            owner = component_owner(group, material, raw[fi, :, :3])
            owners.append(owner)
            for point in raw[fi, :, :3]:
                if owner.startswith('hand_'):
                    weights = hand_weights(to_native(point), owner[-1], chains)
                    # Welded wrist copies on both source submeshes must agree.
                    if 2.2398 <= point[1] <= 2.2442:
                        weights = {'hand_'+owner[-1]: .5, 'forearm_'+owner[-1]: .5}
                elif material and 2.2398 <= point[1] <= 2.2442:
                    weights = {'hand_'+owner[-1]: .5, 'forearm_'+owner[-1]: .5}
                elif material == 0 and group['id'] == 2113:
                    head = float(np.clip((point[1]-3.70)/.14, 0, 1))
                    upper = float(np.clip((point[1]-2.85)/.35, 0, 1))*(1-head)
                    weights = {'head': head, 'torso_upper': upper, 'torso_lower': 1-head-upper}
                else:
                    weights = {owner: 1.}
                corner_weights.append(weights)
        for g in doc['groups']:
            ids = np.flatnonzero(labels == g['id'])
            measurements.append(dict(object=obj, component=g['id'], triangles=len(ids), bounds=g['bounds'],
                                     owner=owners[len(owners)-len(selected)+int(ids[0])]))
    # The same geometric vertex receives the same skin across disconnected UV
    # seams and part owners. This is measured welding, not face removal.
    keys = [tuple(v) for v in raw[:, :, :3].reshape(-1, 3)]
    groups = {}
    for i, key in enumerate(keys): groups.setdefault(key, []).append(i)
    welded = 0
    for ids in groups.values():
        total = {}
        for i in ids:
            for name, w in corner_weights[i].items(): total[name] = total.get(name, 0.)+w/len(ids)
        welded += len(ids)-1
        for i in ids: corner_weights[i] = total
    parts, skins, indices = {}, {}, {}
    cache = {}
    for owner in sorted(set(owners)):
        ids = np.flatnonzero(np.asarray(owners) == owner)
        values = norm[ids].copy()
        values[:, :, :3] -= bones[owner]['pivot']
        values[:, :, 3] = (values[:, :, 3]+source['material'][ids, None])/2
        values[:, :, 4] = 1-values[:, :, 4]
        parts[owner] = dict(pivot=bones[owner]['pivot'], vertices=values.ravel().tolist())
        ci = (ids[:, None]*3+np.arange(3)).ravel()
        palette = sorted({n for i in ci for n, w in corner_weights[i].items() if w > 1e-12})
        skins[owner] = dict(influences={n: [corner_weights[i].get(n, 0.) for i in ci] for n in palette},
                            inverseBindColumnMajor={n: np.linalg.inv(matrix(bones, n, cache)).T.ravel().tolist() for n in palette})
        indices[owner] = ids.tolist()
    mesh = dict(format_version=1, stride=8, model_height=192, triangleCount=3909,
                source='User supplied Unit03 unique source triangles, uniform normalization only', parts=parts, jointSkins=skins)
    return mesh, indices, measurements, welded


def inspect_source_identity(mesh, source, indices):
    issues = []
    ids = [i for row in indices.values() for i in row]
    if sorted(ids) != list(range(len(source['source_corners']))):
        issues.append('face-coverage')
    position_error = uv_error = normal_error = 0.
    count = 0
    for name, part in mesh['parts'].items():
        v = np.asarray(part['vertices'])
        if v.size % 24 or v.size//24 != len(indices.get(name, [])):
            issues.append('face-count:'+name)
            continue
        v = v.reshape(-1, 3, 8); count += len(v)
        selected = indices[name]
        position_error = max(position_error, float(abs(v[:, :, :3]+part['pivot']-source['normalized_corners'][selected, :, :3]).max()))
        uv = v[:, :, 3:5].copy(); uv[:, :, 0] = uv[:, :, 0]*2-source['material'][selected, None]; uv[:, :, 1] = 1-uv[:, :, 1]
        uv_error = max(uv_error, float(abs(uv-source['source_corners'][selected, :, 3:5]).max()))
        normal_error = max(normal_error, float(abs(v[:, :, 5:]-source['normalized_corners'][selected, :, 5:]).max()))
    if count != len(source['source_corners']): issues.append('total-triangles')
    if position_error > 1e-9: issues.append('source-position')
    if uv_error > 1e-12: issues.append('source-UV')
    if normal_error > 1e-12: issues.append('source-normal')
    return dict(accepted=not issues, issues=issues, measured_triangles=count,
                position_max_error_pixels=position_error, UV_roundtrip_error=uv_error, normal_max_error=normal_error)


def posed(mesh, bones, rotations=None, positions=None):
    cache = {}; out = {}
    for name, part in mesh['parts'].items():
        v = np.asarray(part['vertices']).reshape(-1, 8)
        p = (v[:, :3]+part['pivot'])*[-1, 1, 1]/16
        skin = mesh['jointSkins'][name]; palette = sorted(skin['influences'])
        weights = np.asarray([skin['influences'][n] for n in palette]).T
        transforms = np.asarray([matrix(bones, n, cache, rotations, positions) @ np.asarray(skin['inverseBindColumnMajor'][n]).reshape(4, 4).T for n in palette])
        quats = R.from_matrix(transforms[:, :3, :3]).as_quat()
        # Same dominant-bone hemisphere rule as LocalTriangleMeshLayer.
        dominant = weights.argmax(1); signs = np.where(np.einsum('ij,kj->ik', quats[dominant], quats) < 0, -1., 1.)
        xyz, w = quats[:, :3], quats[:, 3:]
        t = transforms[:, :3, 3]
        dual = .5*np.column_stack((w*t+np.cross(t, xyz), -np.einsum('ij,ij->i', t, xyz)))
        q = (weights*signs) @ quats; d = (weights*signs) @ dual
        length = np.linalg.norm(q, axis=1, keepdims=True); q /= length; d /= length
        d -= q*np.sum(q*d, axis=1, keepdims=True)
        translation = 2*(-d[:, 3:]*q[:, :3]+q[:, 3:]*d[:, :3]+np.cross(q[:, :3], d[:, :3]))
        out[name] = R.from_quat(q).apply(p)+translation
    return out


def donor_basis(reference, bones):
    ref = {b['name']: b for b in reference}
    out = {}
    lengths = {}
    for side in ('l', 'r'):
        for name, child in [('arm', 'forearm'), ('forearm', 'hand'), ('leg', 'shin'), ('shin', 'foot'), ('hand', None)]:
            n = name+'_'+side
            if child:
                v1 = (np.asarray(ref[child+'_'+side]['pivot'])-ref[n]['pivot'])*[-1, 1, 1]
                v2 = (np.asarray(bones[child+'_'+side]['pivot'])-bones[n]['pivot'])*[-1, 1, 1]
                axis = np.cross(unit(v1), unit(v2)); angle = math.acos(float(np.clip(unit(v1)@unit(v2), -1, 1)))
                out[n] = R.from_rotvec(unit(axis)*angle).as_matrix() if np.linalg.norm(axis) > 1e-10 else np.eye(3)
                lengths[n] = float(np.linalg.norm(v2)/np.linalg.norm(v1))
            else:
                out[n] = out['forearm_'+side]
    return out, lengths


def decode_frame(frame, names):
    rotations = {n: R.from_quat(np.asarray(q)[[1, 2, 3, 0]]*[-1, -1, 1, 1]).as_matrix() for n, q in zip(names, frame['rotation_wxyz'])}
    positions = {n: np.asarray(p)*[-1, 1, 1]/16 for n, p in frame.get('bone_position_xyz', {}).items()}
    positions['root'] = np.asarray(frame['root_m'])*[-1, 1, 1]*7
    return rotations, positions


def align_vector(before, after):
    first, second = unit(before), unit(after)
    axis = np.cross(first, second); dot = float(np.clip(first@second, -1, 1))
    if np.linalg.norm(axis) < 1e-10:
        if dot > 0: return np.eye(3)
        axis = unit(np.cross(first, [1, 0, 0] if abs(first[0]) < .9 else [0, 1, 0]))
    return R.from_rotvec(unit(axis)*math.acos(dot)).as_matrix()


def pin_foot(side, bones, mesh, rotations, positions):
    cache = {}
    upper, lower, end = ['leg_'+side, 'shin_'+side, 'foot_'+side]
    pivots = {n: np.asarray(bones[n]['pivot'])*[-1, 1, 1]/16 for n in (upper, lower, end)}
    ms = {n: matrix(bones, n, cache, rotations, positions).copy() for n in (upper, lower, end)}
    point = lambda n: (ms[n]@np.r_[pivots[n], 1])[:3]
    origin, middle, ankle = [point(n) for n in (upper, lower, end)]
    foot_orientation = ms[end][:3, :3].copy()
    v = np.asarray(mesh['parts'][end]['vertices']).reshape(-1, 8)
    foot = (v[:, :3]+mesh['parts'][end]['pivot'])*[-1, 1, 1]/16
    target = ankle.copy(); target[1] = -float(((foot-pivots[end])@foot_orientation.T)[:, 1].min())
    a = np.linalg.norm(pivots[lower]-pivots[upper]); b = np.linalg.norm(pivots[end]-pivots[lower])
    direction = unit(target-origin); length = float(np.linalg.norm(target-origin))
    maximum = (a+b)*.99995
    if length > maximum:
        # Root height is selected before pinning both feet, so this only
        # guards genuinely unreachable frames, rather than stretching bones.
        return dict(reachable=False, excess_native=length-maximum)
    length = max(length, abs(a-b)+1e-5)
    along = (a*a-b*b+length*length)/(2*length)
    pole = middle-origin; pole -= direction*(pole@direction)
    if np.linalg.norm(pole) < 1e-7:
        pole = np.array([0., 0., -1.]); pole -= direction*(pole@direction)
    desired_middle = origin+direction*along+unit(pole)*math.sqrt(max(0., a*a-along*along))
    upper_world = align_vector(middle-origin, desired_middle-origin)@ms[upper][:3, :3]
    parent = matrix(bones, bones[upper]['parent'], {}, rotations, positions)
    rotations[upper] = parent[:3, :3].T@upper_world
    lower_matrix = matrix(bones, lower, {}, rotations, positions)
    lower_current = lower_matrix[:3, :3]@(pivots[end]-pivots[lower])
    lower_world = align_vector(lower_current, target-desired_middle)@lower_matrix[:3, :3]
    parent = matrix(bones, bones[lower]['parent'], {}, rotations, positions)
    rotations[lower] = parent[:3, :3].T@lower_world
    parent = matrix(bones, bones[end]['parent'], {}, rotations, positions)
    rotations[end] = parent[:3, :3].T@foot_orientation
    actual = matrix(bones, end, {}, rotations, positions)
    achieved = (actual@np.r_[pivots[end], 1])[:3]
    return dict(reachable=True, ankle_error_native=float(np.linalg.norm(achieved-target)),
                sole_error_native=float((foot@actual[:3, :3].T+actual[:3, 3])[:, 1].min()))


def retarget_frame(frame, names, bases, lengths, bones, mesh):
    rotations, positions = decode_frame(frame, names)
    for n in rotations:
        if n.startswith('finger_'):
            rotations[n] = np.eye(3)
        elif n in bases:
            rotations[n] = bases[n]@rotations[n]@bases[n].T
    # Old lower-joint offsets compensated rig1's displaced socket. Our pivots
    # are the measured sockets themselves, so transplanting those offsets
    # would separate the same joint a second time.
    for n in list(positions):
        if n.startswith(('forearm_', 'shin_')): positions.pop(n)
        elif n != 'root': positions[n] *= lengths.get(n, 1.)
    contact = frame.get('foot_contact', [True, True])
    cache = {}; lows = []
    for side, active in zip(('l', 'r'), contact):
        if not active: continue
        part = mesh['parts']['foot_'+side]
        v = (np.asarray(part['vertices']).reshape(-1, 8)[:, :3]+part['pivot'])*[-1, 1, 1]/16
        m = matrix(bones, 'foot_'+side, cache, rotations, positions)
        lows.append(float((v@m[:3, :3].T+m[:3, 3])[:, 1].min()))
    correction = -min(lows) if lows else 0.
    positions['root'][1] += correction
    # Both contacts require their own ankle targets. A global lift alone left
    # the other sole floating in v2. Lower the root only enough to keep both
    # measured leg lengths reachable, then preserve each foot orientation.
    for _ in range(8):
        trial = []
        for side, active in zip(('l', 'r'), contact):
            if active:
                trial.append(pin_foot(side, bones, mesh, rotations.copy(), {k: v.copy() for k, v in positions.items()}))
        excess = max([x.get('excess_native', 0.) for x in trial]+[0.])
        if excess <= 0: break
        positions['root'][1] -= excess+.002
        correction -= excess+.002
    pins = {side: pin_foot(side, bones, mesh, rotations, positions) for side, active in zip(('l', 'r'), contact) if active}
    result = copy.deepcopy(frame)
    result['rotation_wxyz'] = []
    for n in names:
        q = R.from_matrix(rotations[n]).as_quat()*[-1, -1, 1, 1]
        result['rotation_wxyz'].append(q[[3, 0, 1, 2]].tolist())
    result['root_m'] = (positions['root']*[-1, 1, 1]/7).tolist()
    result['bone_position_xyz'] = {n: (p*[-1, 1, 1]*16).tolist() for n, p in positions.items() if n != 'root'}
    result['unit03_contact_review_r53'] = pins
    return result, correction


def physical_profile(source_physics, bones, mesh):
    names = [x['name'] for x in source_physics['bodies']]
    groups = {n: [] for n in names}
    for owner, part in mesh['parts'].items():
        name = owner
        while name not in groups: name = bones[name]['parent']
        v = np.asarray(part['vertices']).reshape(-1, 8)
        groups[name].extend(((v[:, :3]+part['pivot'])*[-1, 1, 1]*.0125).tolist())
    bodies = []
    for old in source_physics['bodies']:
        name = old['name']; points = np.unique(np.asarray(groups[name]), axis=0)
        centre = (points.min(0)+points.max(0))/2
        pivot = np.asarray(bones[name]['pivot'])*[-1, 1, 1]*.0125
        rotation = np.eye(3)
        if name.startswith(('arm_', 'forearm_', 'leg_', 'shin_')):
            side = name[-1]
            child = {'arm': 'forearm', 'forearm': 'hand', 'leg': 'shin', 'shin': 'foot'}[name.rsplit('_', 1)[0]]+'_'+side
            end = np.asarray(bones[child]['pivot'])*[-1, 1, 1]*.0125
            y = unit(end-pivot); x = unit(np.array([1., 0, 0])-y*y[0]); z = unit(np.cross(x, y))
            rotation = np.column_stack((x, y, z))
        bind = np.eye(4); bind[:3, :3] = rotation; bind[:3, 3] = centre
        local = (points-centre)@rotation; hull = ConvexHull(local)
        joint = np.eye(4); joint[:3, :3] = rotation; joint[:3, 3] = pivot
        row = dict(name=name, parent=old['parent'], shape='box',
                   size=np.maximum(abs(local.min(0)), abs(local.max(0))).tolist(),
                   mass=old['mass'], bind=bind.ravel().tolist(), initial=bind.ravel().tolist(),
                   joint=joint.ravel().tolist(), cone=old['cone'],
                   hulls=[local[hull.vertices].tolist()], hull_planes=[hull.equations.tolist()])
        # Limits retain gameplay policy; the frame, origins and hulls above
        # are independently rebuilt from Unit03. Zero rest fits both knees.
        if 'hinge' in old:
            from anatomical_hinge_r35 import limits
            side = name[-1]
            previous = 'arm_'+side if name.startswith('forearm') else 'leg_'+side
            next_bone = 'hand_'+side if name.startswith('forearm') else 'foot_'+side
            before = np.asarray(bones[previous]['pivot'])*[-1, 1, 1]*.0125
            after = np.asarray(bones[next_bone]['pivot'])*[-1, 1, 1]*.0125
            # Native hinge adapter consumes its local Z axis. Set it to the
            # measured sagittal flexion axis, not the long bone direction.
            axis = np.array([1., 0, 0]) if name.startswith('forearm') else np.array([-1., 0, 0])
            x = unit(np.cross([0, 1, 0], axis)); y = unit(np.cross(axis, x))
            joint[:3, :3] = np.column_stack((x, y, axis))
            row['joint'] = joint.ravel().tolist()
            row['hinge'] = list(limits(pivot-before, after-pivot, axis))
        bodies.append(row)
    return dict(scale_from_pixels=.0125, bones=source_physics['bones'], render_rig=list(bones.values()),
                initial_visual_pose={}, bodies=bodies, policy=copy.deepcopy(source_physics['policy']),
                source_preservation_r53='Measured source hulls, pivots, centres and joint frames; no Unit01 bind/joint copied',
                recovery_review_pending=True)


def render_sheet(path, mesh, positions_by_pose, width=1200):
    # Small CPU-only orthographic QA sheet; never a promotional render.
    from PIL import ImageDraw
    names = list(positions_by_pose)
    cell_width, cell_height = width//len(names), 460
    canvas = Image.new('RGB', (width, cell_height*2), '#1e2530')
    draw = ImageDraw.Draw(canvas)
    for col, name in enumerate(names):
        posed_parts = positions_by_pose[name]
        for row, (horizontal, title) in enumerate([(0, 'front'), (2, 'side')]):
            faces = np.concatenate([v.reshape(-1, 3, 3) for v in posed_parts.values()])*16
            depth = faces[:, :, 2 if horizontal == 0 else 0].mean(1)
            order = np.argsort(depth)[::-1]
            color = np.tile([110., 118., 180.], (len(faces), 1))
            norm = np.cross(faces[:, 1]-faces[:, 0], faces[:, 2]-faces[:, 0]); norm /= np.maximum(np.linalg.norm(norm, axis=1, keepdims=True), 1e-10)
            light = .5+.5*abs(norm@unit([1, 1, -2])); color *= light[:, None]
            factor = min((cell_width-10)/130, (cell_height-50)/205)
            x0 = col*cell_width+cell_width/2; y0 = (row+1)*cell_height-20
            draw.line([(col*cell_width, y0), ((col+1)*cell_width, y0)], fill='#4ba19c')
            for i in order:
                tri = faces[i][:, [horizontal, 1]]*np.array([factor, -factor])+[x0, y0]
                draw.polygon([tuple(v) for v in tri], fill=tuple(color[i].astype(int)))
            draw.text((col*cell_width+8, row*cell_height+8), name+' / '+title, fill='white')
    canvas.save(path)


def detail_sheet(path, mesh, positions, atlas):
    from PIL import ImageDraw
    canvas = Image.new('RGB', (1350, 800), '#202832'); draw = ImageDraw.Draw(canvas)
    raw_texture = np.asarray(atlas)
    tiles = [('source/front', 'source_rest', None, [1, 0, 0], [0, 0, -1]),
             ('source/back', 'source_rest', None, [-1, 0, 0], [0, 0, 1]),
             ('source/side', 'source_rest', None, [0, 0, 1], [1, 0, 0]),
             ('hand/source-rest', 'source_rest', 'hand_l', [0, 0, 1], [1, 0, 0]),
             ('hand/bounded-fist', 'hand_fist', 'hand_l', [0, 0, 1], [1, 0, 0]),
             ('hand/bounded-open', 'hand_open', 'hand_l', [0, 0, 1], [1, 0, 0])]
    for index, (label, pose, part, u, view) in enumerate(tiles):
        column, row = index % 3, index//3
        selected = [part] if part else list(mesh['parts'])
        faces = np.concatenate([positions[pose][n].reshape(-1, 3, 3) for n in selected])*16
        tex = np.concatenate([np.asarray(mesh['parts'][n]['vertices']).reshape(-1, 3, 8)[:, :, 3:5] for n in selected]).mean(1)
        colors = raw_texture[np.clip((tex[:, 1]*511).astype(int), 0, 511), np.clip((tex[:, 0]*1023).astype(int), 0, 1023), :3].astype(float)
        normal = np.cross(faces[:, 1]-faces[:, 0], faces[:, 2]-faces[:, 0]); normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-10)
        colors *= (.6+.4*abs(normal@unit(np.asarray(view)+[.4, .7, 0])))[:, None]
        projection = np.stack((faces@u, faces[:, :, 1]), axis=-1)
        lo = projection.min((0, 1)); hi = projection.max((0, 1))
        factor = min(410/(hi[0]-lo[0]), 350/(hi[1]-lo[1]))
        projection = (projection-(lo+hi)/2)*[factor, -factor]+[column*450+225, row*400+215]
        order = np.argsort((faces@view).mean(1))
        for i in order:
            draw.polygon([tuple(v) for v in projection[i]], fill=tuple(np.clip(colors[i], 0, 255).astype(int)))
        draw.text((column*450+12, row*400+12), label, fill='white')
    canvas.save(path)


def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ('source', 'old', 'client', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    a = parser.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    source = np.load(a.source/'unit03_source_surface.npz')
    scale = float(source['scale']); ymin = float(source['source_ymin'])
    to_geo = lambda p: (np.asarray(p)-[0, ymin, 0])*[scale, scale, -scale]
    to_native = lambda p: to_geo(p)*[-1, 1, 1]/16
    runtime = a.client/'projectseele-local-maps'
    body = read(runtime/'eva_body_r44.json'); gameplay = read(runtime/'eva_gameplay_r44_1.json')
    physics = read(runtime/'articulated_bodies_r35.json')
    reference = body['rigs']['1']
    bones, seeds = skeleton(reference, to_geo)
    hand_reference = read(a.old/'baseline/assets/projectseele/hand_rigs/unit01/hand_rig_contract.json')
    hand_points = source['source_corners'][source['material'] == 1, :, :3].reshape(-1, 3)
    hand_contract, chains, hand_audit = hands(bones, to_native, hand_points, hand_reference)
    mesh, indices, component_audit, welded = surface(a, bones, chains, source, to_native)
    assets = a.out/'assets/projectseele'
    write(assets/'mesh/eva_un01.mesh.json', mesh)
    hand_mesh = copy.deepcopy(mesh)
    hand_mesh['parts'] = {k: v for k, v in mesh['parts'].items() if k.startswith('hand_')}
    hand_mesh['jointSkins'] = {k: mesh['jointSkins'][k] for k in hand_mesh['parts']}
    hand_mesh['triangleCount'] = sum(len(v['vertices'])//24 for v in hand_mesh['parts'].values())
    write(assets/'mesh/eva_un01_anatomical_hands_r53.mesh.json', hand_mesh)
    geo = {'format_version': '1.12.0', 'minecraft:geometry': [dict(description=dict(identifier='geometry.eva_un01', texture_width=1024, texture_height=512, visible_bounds_width=20, visible_bounds_height=20, visible_bounds_offset=[0, 6, 0]), bones=list(bones.values()))]}
    write(assets/'geo/eva_un01.geo.json', geo)
    write(assets/'hand_rigs/unit04/hand_rig_contract.json', hand_contract)
    atlas = Image.new('RGBA', (1024, 512))
    for i, texture in enumerate(('e03_201.png', 'w03_001.png')):
        atlas.paste(Image.open(a.source/texture).convert('RGBA'), (i*512, 0))
    (assets/'textures/entity').mkdir(parents=True)
    atlas.save(assets/'textures/entity/eva_un01.png')
    # Emission is preserved independently; do not darken original base pixels.
    glow = Image.new('RGBA', atlas.size)
    original_glow = Image.open(a.source/'e03_201_glow.png').convert('RGBA').resize((512, 512), Image.Resampling.NEAREST)
    rgba = np.asarray(original_glow).copy(); rgba[:, :, 3] = np.where(rgba[:, :, :3].max(2) > 20, 255, 0)
    glow.paste(Image.fromarray(rgba), (0, 0)); glow.save(assets/'textures/entity/eva_un01_eyes.png')
    with zipfile.ZipFile(a.client/'mods/projectseele-0.1.0-all.jar') as jar:
        animation = jar.read('assets/projectseele/animations/eva_unit01.animation.json')
    (assets/'animations').mkdir(); (assets/'animations/eva_un01.animation.json').write_bytes(animation)
    bases, lengths = donor_basis(reference, bones)
    # Retarget whole shared clip selections as deltas. A new baseline cannot
    # silently fall back to an unrelated UN01 or rig1 stance after review.
    all_clips = copy.deepcopy(body['motion']['clips'])
    sources = {k: body['motion']['bones'] for k in all_clips}
    for key, clip in body['stance_clips_by_rig']['1']['clips'].items():
        all_clips[key] = clip; sources[key] = body['stance_clips_by_rig']['1']['bones']
    for key, clip in gameplay['clips'].items():
        all_clips[key] = clip; sources[key] = gameplay['bones']
    selected = ['idle', 'walk', 'run', 'rifle_stance', 'r32_jab']
    # Initial candidate is intentionally a finite inspection subset. Publishing
    # 45 unreviewed poses as finished would hide actual contact failures.
    reviews = {}; retargeted = {}; corrections = {}
    common_names = gameplay['bones']
    for key in selected:
        clip = all_clips[key]; frames = []
        for frame in clip['frames']:
            new, correction = retarget_frame(frame, sources[key], bases, lengths, bones, mesh)
            by_name = dict(zip(sources[key], new['rotation_wxyz']))
            new['rotation_wxyz'] = [by_name.get(n, [1, 0, 0, 0]) for n in common_names]
            frames.append(new); corrections.setdefault(key, []).append(correction)
        retargeted[key] = dict(duration_seconds=clip['duration_seconds'], frames=frames)
        at = 0 if key in ('idle', 'rifle_stance') else len(frames)//2
        rots, pos = decode_frame(frames[at], common_names)
        reviews[key] = posed(mesh, bones, rots, pos)
    neutral = posed(mesh, bones)
    reviews = {'source_rest': neutral, **reviews}
    reviews['hand_fist'] = posed(mesh, bones, hand_pose(hand_contract, 'fist'))
    reviews['hand_open'] = posed(mesh, bones, hand_pose(hand_contract, 'open'))
    support = {}
    for name, part in mesh['parts'].items():
        v = np.asarray(part['vertices']).reshape(-1, 8)
        points = np.unique((v[:, :3]+part['pivot'])*[-1, 1, 1], axis=0)
        support[name] = points[ConvexHull(points).vertices].tolist()
    body['rigs']['4'] = list(bones.values()); body['rig_support']['4'] = support
    body['carrier_hulls']['4'] = [(np.r_[np.asarray(v).min(0), np.asarray(v).max(0)]*5/16).tolist() for v in support.values()]
    body['eye_positions']['4'] = (to_geo([0, 3.96, .22])*[-1, 1, 1]).tolist()
    body['stance_clips_by_rig']['4'] = dict(bones=common_names, clips=retargeted)
    body['locomotion_contract_r43'].pop('4', None)
    body['unit03_review_scope_r53'] = dict(unreviewed_clips='No locomotion stride admission; temporary-actor keypose review only', source_preserved=True)
    write(a.out/'projectseele-local-maps/eva_body_r44.json', body)
    review_gameplay = dict(schema=gameplay['schema'], sample_rate=gameplay['sample_rate'], rig_key=4,
                          bones=common_names, clips=retargeted, rig_contract_r44=list(bones.values()),
                          source='Unit01 motion deltas on source-proportioned Unit03; finite review subset')
    write(a.out/'projectseele-local-maps/eva_gameplay_r44_4.json', review_gameplay)
    physics['models']['4'] = physical_profile(physics['models']['1'], bones, mesh)
    write(a.out/'projectseele-local-maps/articulated_bodies_r35.json', physics)
    write(a.out/'MEASURED_RIG.json', dict(source_body_landmarks=seeds, hand_axes=hand_audit,
        components=component_audit, body_delta_bases={n: x.tolist() for n, x in bases.items()}, segment_length_ratios=lengths))
    errors = []
    for name, points in neutral.items():
        expected = source['normalized_corners'][indices[name], :, :3].reshape(-1, 3)*[-1, 1, 1]/16
        errors.append(float(np.max(np.abs(points-expected))))
    pose_report = {}
    for key, parts in reviews.items():
        points = np.concatenate(list(parts.values()))*16
        pose_report[key] = dict(bounds=[points.min(0).tolist(), points.max(0).tolist()], finite=bool(np.isfinite(points).all()),
                               foot_minimum_y={s: float(parts['foot_'+s][:, 1].min())*16 for s in ('l', 'r')})
    render_sheet(a.out/'KEYPOSES.png', mesh, {k: reviews[k] for k in ('source_rest', 'idle', 'rifle_stance', 'r32_jab')})
    detail_sheet(a.out/'SOURCE_AND_HANDS.png', mesh, reviews, atlas)
    # Store full posed geometry for independent visual/physics interrogation.
    np.savez_compressed(a.out/'KEYPOSES.npz', **{key+'__'+n: v for key, parts in reviews.items() for n, v in parts.items()})
    write(a.out/'SOURCE_FACE_MAPPING.json', indices)
    # These checks read the exported fields back, rather than relying on the
    # source arrays that generated them.
    exported = read(assets/'mesh/eva_un01.mesh.json')
    source_gates = inspect_source_identity(exported, source, indices)
    source_gates['source_rest_max_error_native'] = max(errors)
    first = next(iter(exported['parts']))
    negative_controls = {}
    for label in ('moved_source_vertex', 'missing_source_face', 'altered_source_UV'):
        bad = copy.deepcopy(exported)
        if label == 'moved_source_vertex': bad['parts'][first]['vertices'][0] += .001
        elif label == 'missing_source_face': del bad['parts'][first]['vertices'][:24]
        else: bad['parts'][first]['vertices'][3] += .001
        negative_controls[label] = inspect_source_identity(bad, source, indices)
        assert not negative_controls[label]['accepted']
    assert source_gates['accepted']
    welded_positions = {}
    for name, ids in indices.items():
        for at, key in enumerate(map(tuple, source['source_corners'][ids, :, :3].reshape(-1, 3))):
            welded_positions.setdefault(key, []).append((name, at))
    seam_errors = {}
    for pose, parts in reviews.items():
        seam_errors[pose] = max(float(np.linalg.norm(parts[n][i]-parts[rows[0][0]][rows[0][1]])) for rows in welded_positions.values() for n, i in rows)
    contact_gates = {}
    for key, clip in retargeted.items():
        pins = [p for f in clip['frames'] for p in f.get('unit03_contact_review_r53', {}).values()]
        contact_gates[key] = dict(checked_contacts=len(pins), failed_reach=sum(not p['reachable'] for p in pins),
                                 max_ankle_error_native=max([p.get('ankle_error_native', 0.) for p in pins]+[0.]),
                                 max_sole_error_native=max([abs(p.get('sole_error_native', 0.)) for p in pins]+[0.]),
                                 scope='Dual-foot targets only; other-body floor penetration and skating not admitted')
    joint_errors = []
    old_joint_errors = []
    old_bodies = {r['name']: r for r in physics['models']['1']['bodies']}
    for row in physics['models']['4']['bodies']:
        expected = np.asarray(bones[row['name']]['pivot'])*[-1, 1, 1]*.0125
        actual = np.asarray(row['joint']).reshape(4, 4)[:3, 3]
        joint_errors.append(float(np.linalg.norm(expected-actual)))
        old = np.asarray(old_bodies[row['name']]['joint']).reshape(4, 4)[:3, 3]
        old_joint_errors.append(float(np.linalg.norm(expected-old)))
    write(a.out/'OFFLINE_GATES.json', dict(source=source_gates, weld_gap_native=seam_errors,
        foot_contact=contact_gates, physics_joint_max_error=max(joint_errors),
        negative_controls={**negative_controls, 'donor_joint_copy_rejected': max(old_joint_errors) > .01,
                           'donor_joint_max_error': max(old_joint_errors)},
        native_not_tested=True, source_world_unmodified=True))
    runtime_out = a.out/'projectseele-local-maps'
    write(runtime_out/'combat_bundle_r44.json', dict(revision=44, bundle_id='unit03-source-rig-keypose-review-r53',
        files={p.name: sha(p) for p in runtime_out.glob('*.json')},
        scope='Partial review overlay only; not a complete runtime directory'))
    native_samples = []
    for key in ('idle', 'rifle_stance', 'r32_jab'):
        clip = retargeted[key]; at = len(clip['frames'])//2 if key == 'r32_jab' else 0
        native_samples.append(dict(name=key, frame_index=at, frame=clip['frames'][at],
                                   hand_pose='fist' if key == 'r32_jab' else 'relaxed',
                                   extra_weapon_IK_applied=False))
    write(a.out/'NATIVE_KEYPOSE_SELECTION.json', dict(schema='projectseele.unit03-offline-keypose-review.v1',
        body_rig_key=4, entity_type='EvaPrototypeEntity', UNSerial=1, bones=common_names,
        samples=native_samples, original_source_rest='Use authored geo rest with hand relaxed controls',
        forbid_original_world_actors=True, combat_gameplay_admitted=False,
        resource_manifest='assets/projectseele/eva/source_surface_r53.json'))
    hashes = {role: sha(assets/path) for role, path in dict(mesh='mesh/eva_un01.mesh.json', geo='geo/eva_un01.geo.json', animation='animations/eva_un01.animation.json', texture='textures/entity/eva_un01.png').items()}
    write(assets/'eva/source_surface_r53.json', dict(schema='projectseele.source-surface-r53.v1', models=dict(eva_un01=dict(source_triangles=3909, added_triangles=0, triangles=3909, parts=len(mesh['parts']), resources=hashes))))
    write(a.out/'pack.mcmeta', dict(pack=dict(pack_format=15, description='PRIVATE Unit03 source-preserving keypose review; isolated actor only')))
    with zipfile.ZipFile(a.out/'unit03-source-keypose-resources.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(a.out/'pack.mcmeta', 'pack.mcmeta')
        for file in assets.rglob('*'):
            if file.is_file(): archive.write(file, file.relative_to(a.out).as_posix())
    report = dict(status='ISOLATED_NATIVE_REVIEW_CANDIDATE_NOT_INSTALLED', triangles=3909,
        source_rest_max_error_native=max(errors), welded_corner_copies=welded,
        part_count=len(mesh['parts']), hand_triangles=hand_mesh['triangleCount'], bones=len(bones),
        measured_physics_bodies=len(physics['models']['4']['bodies']), poses=pose_report,
        ground_correction_native={k: [min(v), max(v)] for k, v in corrections.items()},
        candidate_clips={k: len(v['frames']) for k, v in retargeted.items()},
        preserved=dict(surface=True, UV_mapping='Reversible 2-image atlas affine only', normals=True, uniform_scale=scale, original_back=True),
        unresolved=['Runtime hand contract currently uses getUnitVariant; must route independent rig4 before native review.',
                    'Only five review clips supplied; full combat, recovery and locomotion contact/stride admission remains.',
                    'Source dorsal surface preserved; new socket/hatch geometry not cut or admitted.',
                    'Measured hand seeds and bounded source-rest controls require native close-up acceptance.',
                    'Rig4 recovery policy deliberately absent; no rig1 recovery record copied.'],
        source_sha256={n: sha(runtime/n) for n in ('eva_body_r44.json', 'eva_gameplay_r44_1.json', 'articulated_bodies_r35.json')},
        world_written=False, installed=False)
    write(a.out/'REVIEW_RECEIPT.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'triangles', 'source_rest_max_error_native', 'hand_triangles', 'bones', 'candidate_clips')}))


if __name__ == '__main__':
    main()
