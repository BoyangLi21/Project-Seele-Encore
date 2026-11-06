"""Put a captured run on Unit-01 as a clip overlay.

python run_retarget.py <source> <mixamo|bandai|m2m> <out.json> [--sheet out.png] [--gain 1.0] [--lean 0] [--frames 41]

The source is a cycle of joint positions; the limbs of the EVA take the
directions of the performer's limbs at the EVA's own lengths, through the
hinges body.py solves, so elbows, knees and the swing of the arms stay as they
were captured while the body stays the EVA's.  The one change is to the arms'
sideways flare (--narrow), which reads as flapping on shoulders this wide.  Only
the overlay this writes is ever bundled: the capture files stay out of the
repository.
"""
import argparse
import json
import math
import sys

import numpy as np

sys.path.insert(0, '../motion3')
import body as B
import gait_clip as G
import rig as R
import scene as S

# The root and the aim bone are in the list because the clip this lands on carries a forward tilt
# on them; left alone, it adds to the lean of the performer.
BONES = ['root', 'aim_pitch', 'torso_lower', 'torso_upper', 'neck', 'head', 'clavicle_l', 'clavicle_r', 'arm_l', 'forearm_l', 'wrist_l',
         'hand_l', 'arm_r', 'forearm_r', 'wrist_r', 'hand_r', 'leg_l', 'shin_l', 'ankle_l', 'foot_l',
         'leg_r', 'shin_r', 'ankle_r', 'foot_r']
MAPS = {
    'mixamo': dict(hips='Hips', spine='Spine1', chest='Spine2', neck='Neck', head='Head', cl_l='LeftShoulder', sh_l='LeftArm', el_l='LeftForeArm',
                   wr_l='LeftHand', cl_r='RightShoulder', sh_r='RightArm', el_r='RightForeArm', wr_r='RightHand', hp_l='LeftUpLeg', kn_l='LeftLeg',
                   an_l='LeftFoot', to_l='LeftToeBase', hp_r='RightUpLeg', kn_r='RightLeg', an_r='RightFoot', to_r='RightToeBase'),
    'bandai': dict(hips='Hips', spine='Spine', chest='Chest', neck='Neck', head='Head', cl_l='Shoulder_L', sh_l='UpperArm_L', el_l='LowerArm_L',
                   wr_l='Hand_L', cl_r='Shoulder_R', sh_r='UpperArm_R', el_r='LowerArm_R', wr_r='Hand_R', hp_l='UpperLeg_L', kn_l='LowerLeg_L',
                   an_l='Foot_L', to_l='Toes_L', hp_r='UpperLeg_R', kn_r='LowerLeg_R', an_r='Foot_R', to_r='Toes_R'),
    'm2m': dict(hips='pelvis', spine='spine_01', chest='spine_03', neck='neck_01', head='head', cl_l='clavicle_l', sh_l='upperarm_l', el_l='lowerarm_l',
                wr_l='hand_l', cl_r='clavicle_r', sh_r='upperarm_r', el_r='lowerarm_r', wr_r='hand_r', hp_l='thigh_l', kn_l='calf_l',
                an_l='foot_l', to_l='ball_l', hp_r='thigh_r', kn_r='calf_r', an_r='foot_r', to_r='ball_r'),
}
UP = np.array([0, 1.0, 0])


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def load(path, kind):
    if path.endswith('.npz'):
        from baked import Baked
        t = Baked(path)
    else:
        from bvh import Bvh
        t = Bvh(path)
    P = {k: np.array(t.pos(v), dtype=float) for k, v in MAPS[kind].items()}
    return P, float(t.rate)


def orient(P):
    """To x the performer's left, y up, z forward."""
    d = (P['head'] - .5 * (P['an_l'] + P['an_r'])).mean(0)
    if int(np.argmax(np.abs(d))) == 2:
        P = {k: v[:, [0, 2, 1]] * np.array([1, 1, -1]) for k, v in P.items()}
    right = (P['hp_r'] - P['hp_l']).mean(0)
    right[1] = 0
    fwd = unit(np.cross(UP, unit(right)))
    travel = P['hips'][-1] - P['hips'][0]
    travel[1] = 0
    if np.linalg.norm(travel) > .5 * np.linalg.norm(P['hp_l'] - P['kn_l'], axis=1).mean():
        fwd = unit(travel)
    Rm = np.stack([np.cross(UP, fwd), UP, fwd])
    o = P['hips'][0].copy()
    o[1] = 0
    return {k: (v - o) @ Rm.T for k, v in P.items()}


def cycle(P, rate):
    """The stretch of one gait cycle whose ends match best."""
    hip = .5 * (P['hp_l'] + P['hp_r'])
    n = len(hip)
    rel = np.concatenate([P[k] - hip for k in ('wr_l', 'wr_r', 'an_l', 'an_r', 'kn_l', 'kn_r')], axis=1)
    best = None
    lo, hi = int(.4 * rate), min(n - 1, int(1.2 * rate))
    for period in range(lo, hi + 1):
        for a in range(0, n - period):
            e = float(np.linalg.norm(rel[a] - rel[a + period]))
            # Away from the ends of a take the performer is up to speed; a longer loop
            # of the same fit is the whole cycle rather than half of it.
            mid = abs((a + period / 2) / n - .5)
            score = e + .1 * mid
            if best is None or score < best[0]:
                best = (score, a, a + period)
    return best[1], best[2]


def resample(P, a, b, count):
    """Round the cycle at even phases, closing what the ends still miss."""
    hip = .5 * (P['hp_l'] + P['hp_r'])
    travel = hip[b] - hip[a]
    travel[1] = 0
    out = {}
    L = b - a
    t = np.arange(count) / count * L
    for k, v in P.items():
        rel = v[a:b + 1] - travel * (np.arange(L + 1) / L)[:, None]
        miss = rel[-1] - rel[0]
        rel = rel - miss * (np.arange(L + 1) / L)[:, None]
        rel = rel[:-1]
        i = np.floor(t).astype(int)
        u = (t - i)[:, None]
        p0, p1, p2, p3 = rel[(i - 1) % L], rel[i % L], rel[(i + 1) % L], rel[(i + 2) % L]
        out[k] = .5 * (2 * p1 + (p2 - p0) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (3 * p1 - p0 - 3 * p2 + p3) * u * u * u)
    return out, float(np.linalg.norm(travel[[0, 2]]))


def body_rotation(left, up):
    """World rotation of a body part from its left and up: model x is its right, model z its back."""
    up = unit(up)
    left = unit(left - up * (left @ up))
    return R.matq(np.stack([-left, up, -np.cross(left, up)], axis=1))


class Sole:
    def __init__(self, actors):
        self.parts = {s: np.concatenate([t.reshape(-1, 3) for b, t, _ in actors.eva_mesh.parts if b == 'foot_' + s]) for s in 'lr'}

    def low(self, m, s):
        b = 'foot_' + s
        return float((self.parts[s] @ m[b][:3, :3].T + m[b][:3, 3])[:, 1].min())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('kind')
    ap.add_argument('out')
    ap.add_argument('--sheet', default='')
    ap.add_argument('--frames', type=int, default=51, help='the dash_run clip it lands on has 51')
    ap.add_argument('--lean', type=float, default=0.0, help='extra forward lean of the trunk, degrees')
    ap.add_argument('--gain', type=float, default=1.0, help='swing of the arms about their mean')
    ap.add_argument('--turn', type=float, default=.7, help='how much of the captured twist of the trunk to keep')
    ap.add_argument('--narrow', type=float, default=.5, help='how much of the sideways flare of the arms to keep')
    ap.add_argument('--align', type=float, default=.955, help='phase of the middle of the left foot on the ground')
    ap.add_argument('--label', default='')
    ap.add_argument('--licence', default='')
    a = ap.parse_args()
    P, rate = load(a.source, a.kind)
    P = orient(P)
    first, last = cycle(P, rate)
    N = a.frames - 1
    Q, travel = resample(P, first, last, N)
    seconds = (last - first) / rate
    leg_s = float(np.mean([np.linalg.norm(Q['hp_' + s] - Q['kn_' + s], axis=1).mean() + np.linalg.norm(Q['kn_' + s] - Q['an_' + s], axis=1).mean() for s in 'lr']))
    actors = S.Actors()
    solver = B.EvaBody(actors.eva_rig)
    rig = actors.eva_rig
    pv = rig.pivot
    world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
    leg_e = float(np.linalg.norm(solver.limbs['leg_l'].a) + np.linalg.norm(solver.limbs['leg_l'].b)) * S.SCALE
    arm_u = float(np.linalg.norm(solver.limbs['arm_l'].a)) * S.SCALE
    arm_f = float(np.linalg.norm(solver.limbs['arm_l'].b)) * S.SCALE
    thigh = float(np.linalg.norm(solver.limbs['leg_l'].a)) * S.SCALE
    shin = float(np.linalg.norm(solver.limbs['leg_l'].b)) * S.SCALE
    scale = leg_e / leg_s
    hip = .5 * (Q['hp_l'] + Q['hp_r'])
    floor = min(Q['to_l'][:, 1].min(), Q['to_r'][:, 1].min(), Q['an_l'][:, 1].min(), Q['an_r'][:, 1].min())
    print('source %s frames %d..%d of %d, %.2f s, %d samples; stride %.1f blocks at the EVA scale, leg ratio %.2f' % (a.source.split('/')[-1], first, last, len(P['hips']), seconds, last - first, travel * scale, scale))
    # Feet: how flat is flat for this performer.
    flat = {}
    for s in 'lr':
        v = unit(Q['to_' + s] - Q['an_' + s])
        pitch = np.degrees(np.arctan2(v[:, 1], np.hypot(v[:, 0], v[:, 2])))
        low = np.argsort(Q['an_' + s][:, 1])[:max(3, N // 8)]
        flat[s] = float(np.median(pitch[low]))
    ident = np.array([1.0, 0, 0, 0])
    root_q = B.mat_rot(rig.fk({b: ident.copy() for b in rig.pivot}, {}, world)['root'])
    pelvis_yaw = []
    chest_yaw = []
    for f in range(N):
        l = Q['hp_l'][f] - Q['hp_r'][f]
        pelvis_yaw.append(math.atan2(-l[2], l[0]))
        l = Q['sh_l'][f] - Q['sh_r'][f]
        chest_yaw.append(math.atan2(-l[2], l[0]))
    pelvis_yaw = np.array(pelvis_yaw)
    chest_yaw = np.array(chest_yaw)
    lean_extra = R.qx(-math.radians(a.lean))
    hip_mean = hip.mean(0)

    def frame_pose(f, lift):
        rot = {b: ident.copy() for b in rig.pivot}
        pos = {}
        # Trunk: captured, with its twist scaled and any extra lean about the side axis.
        l = Q['hp_l'][f] - Q['hp_r'][f]
        u = Q['spine'][f] - Q['hips'][f]
        pelvis = R.qmul(lean_extra, body_rotation(l, u))
        pelvis = R.qmul(R.qy((a.turn - 1) * float(pelvis_yaw[f])), pelvis)
        l = Q['sh_l'][f] - Q['sh_r'][f]
        u = Q['neck'][f] - Q['chest'][f]
        chest = R.qmul(lean_extra, body_rotation(l, u))
        chest = R.qmul(R.qy((a.turn - 1) * float(chest_yaw[f])), chest)
        # Eyes ahead: the head takes back most of the lean.
        fwd = R.qmat(chest) @ np.array([0, 0, -1.0])
        pitch = math.degrees(math.atan2(-fwd[1], np.hypot(fwd[0], fwd[2])))
        head = B.body_q(0, min(22.0, .35 * pitch), 0, math.degrees(math.atan2(fwd[0], fwd[2])) * .4)
        neck = R.qslerp(chest, head, .5)
        rot['torso_lower'] = R.qmul(R.qconj(root_q), pelvis)
        rot['torso_upper'] = R.qmul(R.qconj(pelvis), chest)
        rot['neck'] = R.qmul(R.qconj(chest), neck)
        rot['head'] = R.qmul(R.qconj(neck), head)
        # The shoulder girdle pumps with the arm.
        cf = R.qmat(chest).T
        for s, sign in (('l', -1), ('r', 1)):
            v = cf @ (Q['sh_' + s][f] - Q['cl_' + s][f])
            mean = cf @ (Q['sh_' + s] - Q['cl_' + s]).mean(0)
            fwd_a = math.degrees(math.atan2(-v[2], abs(v[0])) - math.atan2(-mean[2], abs(mean[0])))
            shrug = math.degrees(math.atan2(v[1], abs(v[0])) - math.atan2(mean[1], abs(mean[0])))
            rot['clavicle_' + s] = R.qmul(R.qz(math.radians(sign * .6 * shrug)), R.qy(math.radians(sign * .6 * fwd_a)))
        m = rig.fk(rot, {'root': np.zeros(3)}, world)
        here = (B.point(m['leg_l'], pv['leg_l']) + B.point(m['leg_r'], pv['leg_r'])) / 2
        offset = (hip[f] - hip_mean) * scale * np.array([.8, 0, .6])
        target = np.array([offset[0], (hip[f, 1] - floor) * scale + lift, offset[2]])
        root = (target - here) / S.SCALE
        pos['root'] = root
        for s in 'lr':
            m = rig.fk(rot, pos, world)
            start = B.point(m['torso_lower'], pv['leg_' + s])
            du = unit(Q['kn_' + s][f] - Q['hp_' + s][f])
            dv = unit(Q['an_' + s][f] - Q['kn_' + s][f])
            ankle = start + thigh * du + shin * dv
            limb = solver.limbs['leg_' + s]
            # The knee points the way the captured bend does.
            pole = du - dv
            qu, ql, qw, ang, err = limb.solve(start, ankle, pole, B.mat_rot(m['torso_lower']))
            rot['leg_' + s], rot['shin_' + s] = qu, ql
            pos['shin_' + s] = R.Rig.hinge_offset(ql, pv['shin_' + s], solver.knee[s])
            # A foot pointing at the ground has no heading of its own: it takes its side axis from the shin.
            q_shin = R.qmul(qw, ql)
            side = R.qmat(q_shin) @ np.array([-1.0, 0, 0])
            toe = unit(Q['to_' + s][f] - Q['an_' + s][f])
            toe = R.qmat(R.qaxis(side, -math.radians(flat[s]))) @ toe
            q_foot = body_rotation(side, np.cross(toe, side))
            rot['ankle_' + s] = ident.copy()
            rot['foot_' + s] = R.qmul(R.qconj(R.qmul(qw, ql)), q_foot)
        for s in 'lr':
            m = rig.fk(rot, pos, world)
            start = B.point(m['clavicle_' + s], pv['arm_' + s])
            du = Q['el_' + s][f] - Q['sh_' + s][f]
            dv = Q['wr_' + s][f] - Q['el_' + s][f]
            du, dv = unit(du), unit(dv)
            if a.gain != 1.0:
                mid = unit((Q['el_' + s] - Q['sh_' + s]).mean(0))
                axis = np.cross(mid, du)
                n = np.linalg.norm(axis)
                if n > 1e-6:
                    extra = R.qaxis(axis / n, (a.gain - 1) * math.asin(min(1.0, n)))
                    du = R.qmat(extra) @ du
                    dv = R.qmat(extra) @ dv
            if a.lean:
                du = R.qmat(lean_extra) @ du
                dv = R.qmat(lean_extra) @ dv
            # A person's narrow shoulders carry this flare; on the EVA's it reads as flapping.
            out = 1.0 if s == 'l' else -1.0
            du = unit(du * np.array([1.0 if du[0] * out <= 0 else a.narrow, 1, 1]))
            dv = unit(dv * np.array([1.0 if dv[0] * out <= 0 else a.narrow, 1, 1]))
            wrist = start + arm_u * du + arm_f * dv
            pole = du - dv
            limb = solver.limbs['arm_' + s]
            qu, ql, qw, ang, err = limb.solve(start, wrist, pole, B.mat_rot(m['clavicle_' + s]))
            rot['arm_' + s], rot['forearm_' + s] = qu, ql
            pos['forearm_' + s] = R.Rig.hinge_offset(ql, pv['forearm_' + s], solver.elbow[s])
        return rot, pos, rig.fk(rot, pos, world)

    sole = Sole(actors)
    lows = np.array([[sole.low(frame_pose(f, 0.0)[2], s) for s in 'lr'] for f in range(N)])
    lift = -float(lows.min())
    # The left foot's time on the ground fixes where the cycle starts, so a
    # run blending into this finds its feet in the same places.
    down = {s: lows[:, i] - lows.min() < 2.0 for i, s in enumerate('lr')}

    def centre(mask):
        ang = np.arange(N)[mask] / N * 2 * math.pi
        return (math.atan2(np.sin(ang).mean(), np.cos(ang).mean()) / (2 * math.pi)) % 1.0
    shift = int(round((centre(down['l']) - a.align) * N)) % N
    print('feet down l %.3f (%d frames) r %.3f (%d frames), shift %d' % (centre(down['l']), down['l'].sum(), centre(down['r']), down['r'].sum(), shift))
    frames = []
    posed = []
    for i in range(N + 1):
        f = (i + shift) % N
        rot, pos, m = frame_pose(f, lift)
        posed.append((rot, pos, m))
        p = pos['root']
        row = {'root_m': [round(float(x), 6) for x in np.array([-p[0], p[1], p[2]]) * 16 / 112], 'rotation_wxyz': [], 'bone_position_xyz': {}}
        for n in BONES:
            row['rotation_wxyz'].append([round(float(x), 6) for x in R.baked_to_clip(R.qnorm(rot[n]))])
        for n in ('forearm_l', 'forearm_r', 'shin_l', 'shin_r'):
            t = pos[n]
            row['bone_position_xyz'][n] = [round(float(x), 4) for x in (-t[0] * 16, t[1] * 16, t[2] * 16)]
        frames.append(row)
    fast = 0.0
    for i in range(1, N + 1):
        for b in ('leg_l', 'leg_r', 'shin_l', 'shin_r', 'arm_l', 'arm_r', 'forearm_l', 'forearm_r', 'foot_l', 'foot_r', 'torso_upper'):
            d = abs(float(np.dot(B.mat_rot(posed[i][2][b]), B.mat_rot(posed[i - 1][2][b]))))
            fast = max(fast, 2 * math.degrees(math.acos(min(1, d))))
    print('fastest bone %.1f deg/frame over %d frames' % (fast, N))
    for s, i in (('l', 0), ('r', 1)):
        v = np.array([sole.low(posed[f][2], s) for f in range(N)])
        d = np.flatnonzero(v < 1.6)
        if len(d):
            gaps = np.flatnonzero(np.diff(d) > 1)
            start = d[gaps[-1] + 1] if len(gaps) else d[0]
            print(s, 'down from phase %.3f for %.3f' % (start / N, len(d) / N))
    doc = {'source': a.licence or a.label or a.source.split('/')[-1], 'clip': 'dash_run', 'first_frame': 0, 'bones': BONES, 'frames': frames}
    json.dump(doc, open(a.out, 'w', encoding='utf8'), separators=(',', ':'))
    print('wrote', a.out, len(frames), 'frames')
    if a.sheet:
        images = []
        side_cam = R.Camera(np.array([-105.0, 34, 8]), np.array([0, 30, 8]), 34, (300, 300))
        three = R.Camera(np.array([10.0, 36, 118]), np.array([0, 32, 6]), 30, (300, 300))
        for view, cam in (('side', side_cam), ('front', three)):
            for k in range(8):
                m = posed[k * N // 8][2]
                images.append(R.render(cam, [actors.eva_mesh.triangles(m, np.eye(4))], label='%s %d' % (view, k), ground=(-90, 90, -90, 90)))
        R.sheet(images, 8).save(a.sheet)
        print('sheet', a.sheet)


if __name__ == '__main__':
    main()
