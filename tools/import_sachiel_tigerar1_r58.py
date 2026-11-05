"""Bind the supplied Sachiel (allanromanreyes on Sketchfab, CC BY-SA) to the 17-bone Sachiel rig.

python tools/import_sachiel_tigerar1_r58.py <Sachiel.obj> <m01_001.png> --output-pack <assets/projectseele>

The source is a rigid-part model (87 separate pieces) standing with its arms
hanging. Its own proportions are kept: the skeleton is fitted to its joints
instead of squeezing it into the old mesh's shorter legs. Only the forearms
and hands are swung about the elbows to point forward, because every Sachiel
animation is authored against that rest pose (idle lowers them by 90 degrees).

Pieces that sit on one body part are bound rigidly to that bone; the pieces
that run across a joint (arms, the thigh/pelvis body, lower legs) blend across
a narrow window at the joint, and only their triangles near a joint are split
once so the bend has samples. No third-party geometry is written into src/.
"""
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np

BONES = ['root', 'torso_lower', 'torso_upper', 'neck', 'head',
         'arm_l', 'forearm_l', 'hand_l', 'leg_l', 'shin_l', 'foot_l',
         'arm_r', 'forearm_r', 'hand_r', 'leg_r', 'shin_r', 'foot_r']
PARENT = dict(torso_lower='root', torso_upper='torso_lower', neck='torso_upper', head='neck',
              arm='torso_upper', forearm='arm', hand='forearm', leg='torso_lower', shin='leg', foot='shin')
HEIGHT_PX = 192.0

# Joints measured on the source (OBJ units, +z forward, +x = the left side).
J = dict(root=[0, 0, 0], torso_lower=[0, 3.15, 0], torso_upper=[0, 3.62, 0],
         neck=[0, 4.2, .05], head=[0, 4.4, .3],
         arm=[1.18, 4.82, -.15], forearm=[1.45, 2.9, -.18], hand=[1.68, 1.9, .22], hand_tip=[1.75, 1.0, .5],
         leg=[.33, 2.98, 0], shin=[.52, 1.38, -.1], foot=[.65, .3, -.13], toe=[.72, 0, .5])


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def window(s, half):
    """0 below -half, 1 above +half along a signed distance s."""
    return smooth((s + half) / (2 * half))


def joint(name, sign=1):
    return np.array(J[name], float) * [sign, 1, 1]


def load_obj(path):
    v, vt, vn, faces = [], [], [], []
    for line in Path(path).read_text(encoding='utf8').splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == 'v':
            v.append([float(x) for x in p[1:4]])
        elif p[0] == 'vt':
            vt.append([float(x) for x in p[1:3]])
        elif p[0] == 'vn':
            vn.append([float(x) for x in p[1:4]])
        elif p[0] == 'f':
            q = [[int(k) - 1 for k in c.split('/')] for c in p[1:]]
            for i in range(1, len(q) - 1):
                faces.append([q[0], q[i], q[i + 1]])
    return np.array(v), np.array(vt), np.array(vn), faces


def components(nv, faces):
    parent = list(range(nv))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for f in faces:
        for c in f[1:]:
            parent[find(c[0])] = find(f[0][0])
    return np.array([find(i) for i in range(nv)])


def classify(points):
    """Name the body part a separate source piece belongs to."""
    lo, hi, c = points.min(0), points.max(0), points.mean(0)
    side = 'l' if c[0] > 0 else 'r'
    ax = abs(c[0])
    if hi[1] - lo[1] > 1.5 and ax > .95 and lo[1] < 2.3:
        return 'arm_chain_' + side             # arm, and the blade along it
    if ax > 1.2 and 3.0 < lo[1] and hi[1] < 3.7:
        return 'arm_chain_' + side             # knob behind the upper arm
    if ax > 1.3 and hi[1] < 2.15:
        return 'hand_' + side                 # claws
    if hi[1] < 1.2 and ax > .4:
        return 'lower_leg_' + side            # shin and foot
    if lo[1] < 1.3 and hi[1] > 3.3:
        return 'body'                         # waist, pelvis, both thighs
    if ax > .15 and hi[1] < 3.2 and lo[1] > 2.0:
        return 'leg_' + side                  # thigh plates
    if hi[1] < 3.5 and lo[1] > 2.8:
        return 'torso_lower'                  # pelvis plates
    if ax < .3 and lo[1] > 4.0 and c[2] > .5:
        return 'head'                         # the mask
    if ax < .45 and lo[1] > 4.1 and hi[1] < 4.4 and c[2] > .4:
        return 'head'                         # the mask's eye pieces
    return 'torso_upper'                      # shoulders, chest, back, ribs, core


def weights_for(part, p):
    """Bone weights for a rest-space point of a source piece."""
    w = {}
    if part.startswith('arm_chain_') or part.startswith('hand_'):
        side = part[-1]
        s = 1 if side == 'l' else -1
        if part.startswith('hand_'):
            return {'hand_' + side: 1.0}
        sh, el, wr, tip = joint('arm', s), joint('forearm', s), joint('hand', s), joint('hand_tip', s)
        fore = window(np.dot(p - el, (wr - el) / np.linalg.norm(wr - el)), .1)
        hand = window(np.dot(p - wr, (tip - wr) / np.linalg.norm(tip - wr)), .06)
        w['arm_' + side] = 1 - fore
        w['forearm_' + side] = fore * (1 - hand)
        w['hand_' + side] = fore * hand
        return w
    if part.startswith('lower_leg_'):
        side = part[-1]
        foot = window(.3 - p[1], .07)
        return {'shin_' + side: 1 - foot, 'foot_' + side: foot}
    if part.startswith('leg_'):
        return {part: 1.0}
    if part == 'body':
        side = 'l' if p[0] > 0 else 'r'
        s = 1 if side == 'l' else -1
        upper = window(p[1] - 3.55, .08)
        leg = window(2.95 - p[1], .1) * window(abs(p[0]) - .06, .05)
        kn = joint('shin', s)
        shin = window(np.dot(p - kn, (joint('foot', s) - kn) / np.linalg.norm(joint('foot', s) - kn)), .1)
        trunk = 1 - leg
        w['torso_upper'] = trunk * upper
        w['torso_lower'] = trunk * (1 - upper)
        w['leg_' + side] = leg * (1 - shin)
        w['shin_' + side] = leg * shin
        return w
    return {part: 1.0}


def canonical(w):
    items = [(BONES.index(n), x) for n, x in w.items() if x > 1e-6]
    items.sort(key=lambda t: (-t[1], t[0]))
    items = items[:4]
    total = sum(x for _, x in items)
    items = [(i, round(x / total, 7)) for i, x in items]
    items = [(i, x) for i, x in items if x > 0]
    items[0] = (items[0][0], round(items[0][1] + 1 - sum(x for _, x in items), 7))
    items.sort(key=lambda t: (-t[1], t[0]))
    ids = [i for i, _ in items] + [items[0][0]] * (4 - len(items))
    ws = [x for _, x in items] + [0.0] * (4 - len(items))
    return ids, ws


def axis_angle_rotation(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    axis = np.cross(a, b)
    angle = math.atan2(np.linalg.norm(axis), float(np.dot(a, b)))
    return axis / max(np.linalg.norm(axis), 1e-12), angle


def rotate(v, axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    return v * c + np.cross(axis, v) * s + axis * np.dot(axis, v) * (1 - c)


def repose(p, n, w, side_swing):
    """Swing forearm and hand weights about the elbow by their share of the turn."""
    for side, (axis, angle) in side_swing.items():
        share = w.get('forearm_' + side, 0) + w.get('hand_' + side, 0)
        if share <= 0:
            continue
        el = joint('forearm', 1 if side == 'l' else -1)
        p = el + rotate(p - el, axis, angle * share)
        n = rotate(n, axis, angle * share)
    return p, n


def build(obj_path, texture_path, out):
    v, vt, vn, faces = load_obj(obj_path)
    comp = components(len(v), faces)
    part_of = {}
    for root in np.unique(comp):
        part_of[root] = classify(v[comp == root])
    report = {}
    for root, name in part_of.items():
        report.setdefault(name, 0)
        report[name] += int((comp == root).sum())

    swing = {}
    for side, s in (('l', 1), ('r', -1)):
        el, wr = joint('forearm', s), joint('hand', s)
        swing[side] = axis_angle_rotation(wr - el, np.array([0, 0, 1.0]))

    floor = v[:, 1].min()
    height = v[:, 1].max() - floor
    scale = HEIGHT_PX / height

    def out_point(p):
        return (p - [0, floor, 0]) * scale * [1, 1, -1]

    def corner(face_corner):
        vi, ti, ni = face_corner
        return v[vi], vt[ti], vn[ni], part_of[comp[vi]]

    vertices, ids, ws = [], [], []
    split = 0

    def emit(p, uv, n, part):
        w = weights_for(part, p)
        q, nn = repose(p, n, w, swing)
        nn = nn / max(np.linalg.norm(nn), 1e-12)
        o = out_point(q)
        vertices.extend([*o, uv[0], 1 - uv[1], nn[0], nn[1], -nn[2]])
        i, x = canonical(w)
        ids.extend(i)
        ws.extend(x)

    for f in faces:
        cs = [corner(c) for c in f]
        blended = any(max(weights_for(c[3], c[0]).values()) < .995 for c in cs)
        if not blended:
            for p, uv, n, part in cs:
                emit(p, uv, n, part)
            continue
        split += 1
        part = cs[0][3]
        pts = [c[0] for c in cs] + [(cs[a][0] + cs[b][0]) / 2 for a, b in ((0, 1), (1, 2), (2, 0))]
        uvs = [c[1] for c in cs] + [(cs[a][1] + cs[b][1]) / 2 for a, b in ((0, 1), (1, 2), (2, 0))]
        ns = [c[2] for c in cs] + [(cs[a][2] + cs[b][2]) / 2 for a, b in ((0, 1), (1, 2), (2, 0))]
        for tri in ((0, 3, 5), (3, 1, 4), (5, 4, 2), (3, 4, 5)):
            for k in tri:
                emit(pts[k], uvs[k], ns[k], part)

    pivots = dict(root=joint('root'), torso_lower=joint('torso_lower'), torso_upper=joint('torso_upper'),
                  neck=joint('neck'), head=joint('head'))
    for side, s in (('l', 1), ('r', -1)):
        axis, angle = swing[side]
        el = joint('forearm', s)
        pivots['arm_' + side] = joint('arm', s)
        pivots['forearm_' + side] = el
        pivots['hand_' + side] = el + rotate(joint('hand', s) - el, axis, angle)
        pivots['leg_' + side] = joint('leg', s)
        pivots['shin_' + side] = joint('shin', s)
        pivots['foot_' + side] = joint('foot', s)
    geo_bones = []
    for name in BONES:
        entry = dict(name=name, pivot=np.round(out_point(pivots[name]), 6).tolist())
        if name != 'root':
            stem = name.rsplit('_', 1)[0] if name[-2:] in ('_l', '_r') else name
            par = PARENT[stem]
            entry['parent'] = par + name[-2:] if par in ('arm', 'forearm', 'leg', 'shin') else par
        geo_bones.append(entry)

    out = Path(out)
    for sub in ('geo', 'mesh', 'textures/entity'):
        (out / sub).mkdir(parents=True, exist_ok=True)
    src_bytes = Path(obj_path).read_bytes()
    tex_bytes = Path(texture_path).read_bytes()
    mesh = dict(format='weighted_angel_r10', stride=8,
                parts={'root': dict(pivot=[0, 0, 0], vertices=np.round(vertices, 6).tolist())},
                skin=dict(bones=BONES, indices=ids, weights=ws, binding_version='r58-tigerar1-rigid-parts-v1',
                          weight_field='Separate source pieces bound rigidly to their part; arms, thigh/pelvis and lower legs blend in narrow joint windows'),
                provenance=dict(source='allanromanreyes "Sachiel" (Sketchfab b2b9e4844351447bb267f705de8e3c27), CC BY-SA', source_sha256=hashlib.sha256(src_bytes).hexdigest(),
                                texture_sha256=hashlib.sha256(tex_bytes).hexdigest(), source_height=float(height),
                                rest_pose='forearms and hands swung about the elbows to point forward',
                                private_test_only=False))
    geo = {'format_version': '1.12.0', 'minecraft:geometry': [dict(
        description=dict(identifier='geometry.sachiel', texture_width=512, texture_height=512,
                         visible_bounds_width=40, visible_bounds_height=40, visible_bounds_offset=[0, 12, 0]),
        bones=geo_bones)]}
    (out / 'mesh/sachiel.mesh.json').write_text(json.dumps(mesh, separators=(',', ':')), encoding='utf8')
    (out / 'geo/sachiel.geo.json').write_text(json.dumps(geo, separators=(',', ':')), encoding='utf8')
    shutil.copyfile(texture_path, out / 'textures/entity/sachiel.png')
    print(json.dumps(dict(triangles=len(vertices) // 24, split_triangles=split, source_triangles=len(faces),
                          parts=report, height_units=round(float(height), 4), scale_px=round(scale, 4),
                          forearm_swing_deg={k: round(math.degrees(a), 1) for k, (_, a) in swing.items()},
                          max_weight_error=float(np.max(np.abs(np.array(ws).reshape(-1, 4).sum(1) - 1)))), indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('obj')
    ap.add_argument('texture')
    ap.add_argument('--output-pack', required=True)
    a = ap.parse_args()
    build(a.obj, a.texture, a.output_pack)
