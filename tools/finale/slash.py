"""Author the knife's ordinary cuts: python slash.py out.json [sheet.png] [cut|back]

The knife had two blows, both long: a thrust that is wound up from behind the hip, driven in and held (2.9 seconds
as captured), and a reverse-grip blow held as long. These are the short ones a fight is mostly made of, in the
forward grip:

  cut   from the guard the hand is drawn up beside the right ear as the trunk coils to the right, then the hips
        turn into it and the blade comes down across the front, right to left, the arm out ahead at the height of
        the chest as it passes the middle, and goes on down to the left hip;
  back  from there (or from the guard, through there) the blade comes back up across, left to right, the back of
        the hand leading, and ends out to the right over the shoulder.

The feet stay where the guard has them: the pelvis turns and shifts over them and the legs are solved to them. The
left arm keeps its guard on the chest it hangs from, so it swings back as the right goes out. The head keeps most
of its own heading. Every bone the cut does not move keeps the guard's rotation (the fingers stay closed on the
knife, the knife stays in the hand).

Starts from the first frame of the forward thrust in Unit-01's private profile (rig 1), which is the knife's guard.
The guard is not this project's to publish, so what is written is only how each frame differs from it: for every
bone the cut moves, the rotation that takes the guard's to the frame's, and the offsets that differ. The game puts
that on the guard of the profile it has (EvaGameplayMotionR32.addKnifeCutsR64) and takes the profile's private
fields from the thrust the cuts stand beside.

The blade is given by its angle to the forearm, not as a direction in the world: a fist round a handle holds the
blade square to the forearm and a wrist gives some 40 degrees either way. A first version that pointed the blade
where the cut should reach asked 80 degrees of the wrist. And round the forearm the blade goes no further than a
forearm turns (TWIST_MOST): the report prints the wrist the way the capture meter has it.
"""
import json
import math
import os
import sys

import numpy as np

import body as B
import profile_clip as P
import rig as R
import scene as S

D = math.radians
FPS = 60
WHICH = sys.argv[3] if len(sys.argv) > 3 else 'cut'


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = min(1.0, max(0.0, t))
    return t ** 2.2


LENGTH = np.array([0.0, -1.0, 0.0])    # a hand's own length, in the hand (and a forearm's in the forearm)
# The most the knife hand is turned about its own length against its forearm, either way (degrees). In a body the
# forearm does this turn, some 85 either way from a thumb that points ahead as the arm hangs; on this model all of
# it shows between the forearm's armour and the hand. The keys as first handed in turned it 97 in the game (108
# here) for a tick at the top of the cut's wind-up, to lay the blade back over the shoulder.
TWIST_MOST = 75.0


def swing_twist(rel):
    """A hand's rotation against its forearm as the swing that carries its length to where it points, and the turn
    about that length (degrees, signed: thumb outward +)."""
    swing = R.q_between(LENGTH, R.qrot(rel, LENGTH))
    turn = R.qmul(R.qconj(swing), rel)
    angle = math.degrees(2 * math.atan2(float(np.dot(turn[1:4], LENGTH)), float(turn[0])))
    return swing, (angle + 180.0) % 360.0 - 180.0


def wrist_of(forearm, hand):
    """The right hand against its forearm (rotations in the world) the way the capture meter has it (fr_wrist.py):
    degrees bent back (+) or forward into the palm (-), bent sideways to the little finger (+) or the thumb (-),
    and turned about its own length."""
    rel = R.qnorm(R.qmul(R.qconj(forearm), hand))
    a = R.qrot(R.qconj(rel), LENGTH)    # the forearm's length as the hand has it; the right palm faces -X
    return (math.degrees(math.atan2(-a[0], -a[1])), math.degrees(math.asin(max(-1.0, min(1.0, float(a[2]))))), swing_twist(rel)[1])


# Keys: time (seconds), then what the body does at it. Places and directions are in the world (x to the Unit's
# left, y up, z ahead of it); yaws are added to the guard's (positive turns the body to its left).
#   wrist   where the right wrist is
#   blade   the angle between the blade and the forearm (the guard's is 92: a fist round a handle; a wrist gives
#           some 40 either way), and the way the blade leans from the forearm
#   pelvis  yaw added to the pelvis; chest: yaw added to the chest on top of that; lean: the chest's pitch added
#   hip     the pelvis's place added (x, y, z)
#   elbow   the way the elbow points from the line shoulder to wrist
#   ease    how the stretch that ends at this key is timed
GUARD = dict(wrist=None, blade=None, pelvis=0, chest=0, lean=0, hip=(0, 0, 0), elbow=None)
CUT = [
    (0.00, dict(GUARD)),
    # drawn back: the hand up by the right ear, the blade laid back over the shoulder, the trunk coiled, the weight back
    (0.24, dict(wrist=(-14.0, 50.5, -1.5), blade=(96, (-.25, .55, -.80)), pelvis=-9, chest=-17, lean=-2, hip=(-.6, -1.0, -1.2),
                elbow=(-.85, -.10, -.50), ease=smooth)),
    # down across the middle: the arm out ahead at the height of the chest, the blade standing ahead of the hand
    (0.34, dict(wrist=(-2.0, 43.5, 19.5), blade=(56, (.20, .95, .25)), pelvis=14, chest=24, lean=8, hip=(.5, -1.5, 1.6),
                elbow=(-.80, -.45, -.40), ease=ease_in)),
    # gone through: the hand down at the left hip, the blade ahead of it and low
    (0.44, dict(wrist=(10.0, 30.5, 11.5), blade=(72, (.45, -.15, .88)), pelvis=22, chest=38, lean=13, hip=(.9, -2.2, 2.0),
                elbow=(-.50, -.60, -.62), ease=ease_out)),
    # held a moment as the weight settles
    (0.56, dict(wrist=(10.6, 30.0, 10.8), blade=(76, (.45, -.15, .88)), pelvis=23, chest=39, lean=12, hip=(.9, -2.0, 1.9),
                elbow=(-.50, -.60, -.62), ease=smooth)),
    (1.00, dict(GUARD, ease=smooth)),
]
BACK = [
    (0.00, dict(GUARD)),
    # wound to the left and low: the hand at the left hip, the trunk coiled over it
    (0.24, dict(wrist=(10.0, 31.5, 10.0), blade=(80, (.45, -.10, .88)), pelvis=12, chest=26, lean=11, hip=(.7, -2.0, 1.2),
                elbow=(-.50, -.60, -.62), ease=smooth)),
    # up across the middle: the back of the hand leading, the blade standing behind it
    (0.34, dict(wrist=(-3.5, 42.5, 19.5), blade=(104, (-.10, .97, .20)), pelvis=-2, chest=-4, lean=6, hip=(.3, -1.4, 1.7),
                elbow=(-.70, -.60, -.38), ease=ease_in)),
    # gone through: the hand out to the right over the shoulder, the blade upright
    (0.44, dict(wrist=(-17.0, 51.0, 6.0), blade=(98, (.15, .90, -.40)), pelvis=-12, chest=-22, lean=1, hip=(-.3, -.9, .8),
                elbow=(-.85, -.35, -.40), ease=ease_out)),
    (0.56, dict(wrist=(-17.3, 50.6, 5.4), blade=(96, (.15, .90, -.40)), pelvis=-13, chest=-23, lean=1, hip=(-.3, -.8, .7),
                elbow=(-.85, -.35, -.40), ease=smooth)),
    (1.00, dict(GUARD, ease=smooth)),
]
KEYS = {'cut': CUT, 'back': BACK}
CONTACT = {'cut': 0.34, 'back': 0.34}


def main():
    out = sys.argv[1]
    data = P.load()
    bones = data['bones']
    guard = data['clips']['r32_knife_forward']
    actors = S.Actors()
    rig = actors.eva_rig
    body = B.EvaBody(rig)
    world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
    rot0, pos0 = P.frame_pose(bones, guard, 0)
    m0 = rig.fk(rot0, pos0, world)

    def pt(m, name, pivot=None):
        return m[name][:3, :3] @ (rig.pivot[name] if pivot is None else pivot) + m[name][:3, 3]

    def wq(m, name):
        return B.mat_rot(m[name])

    # the guard, in the terms the keys are written in
    wrist0 = pt(m0, 'wrist_r')
    grip0, tip0 = P.blade(rig, m0)
    blade0 = unit(tip0 - grip0)
    shoulder0 = pt(m0, 'arm_r')
    elbow0 = pt(m0, 'forearm_r', body.elbow['r'])
    line = unit(wrist0 - shoulder0)
    pole0 = unit((elbow0 - shoulder0) - line * np.dot(elbow0 - shoulder0, line))
    hand_w0 = wq(m0, 'hand_r')
    fore0 = unit(wrist0 - elbow0)
    angle0 = math.degrees(math.acos(float(np.dot(blade0, fore0))))
    far = body.limbs['arm_r'].reach(body.limbs['arm_r'].lo + 8.0)[0]
    # blade and forearm as the hand has them
    blade_local = R.qrot(R.qconj(hand_w0), blade0)
    fore_local = R.qrot(R.qconj(hand_w0), fore0)
    ankle0 = {s: pt(m0, 'ankle_' + s) for s in 'lr'}
    foot_w0 = {s: wq(m0, 'foot_' + s) for s in 'lr'}
    knee0 = {s: pt(m0, 'shin_' + s, body.knee[s]) for s in 'lr'}
    hip0 = {s: pt(m0, 'leg_' + s) for s in 'lr'}
    knee_pole = {s: unit(knee0[s] - hip0[s]) for s in 'lr'}
    keys = KEYS[WHICH]
    for _, k in keys:
        if k['wrist'] is None:
            k['wrist'], k['blade'], k['elbow'] = wrist0, (angle0, blade0), pole0
        k['angle'], k['blade'] = float(k['blade'][0]), unit(k['blade'][1])
        for name in ('wrist', 'elbow', 'hip'):
            k[name] = np.asarray(k[name], float)

    def at(t):
        """The keys' values at a time: eased between the two keys about it, the wrist and the blade along a
        curve through the keys either side as well (a straight line between keys is a push, not a sweep)."""
        i = max(j for j, (kt, _) in enumerate(keys) if kt <= t + 1e-9)
        if i == len(keys) - 1:
            return dict(keys[-1][1])
        (ta, a), (tb, b) = keys[i], keys[i + 1]
        u = b.get('ease', smooth)((t - ta) / (tb - ta))
        prev = keys[i - 1][1] if i > 0 else a
        nxt = keys[i + 2][1] if i + 2 < len(keys) else b
        res = {}
        for name in ('pelvis', 'chest', 'lean', 'angle'):
            res[name] = a[name] + (b[name] - a[name]) * u
        res['hip'] = a['hip'] + (b['hip'] - a['hip']) * u
        for name in ('wrist', 'blade', 'elbow'):
            p0, p1, p2, p3 = prev[name], a[name], b[name], nxt[name]
            # Catmull-Rom
            res[name] = .5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
        res['blade'] = unit(res['blade'])
        res['elbow'] = unit(res['elbow'])
        return res

    def turned(m, rot, name, q_delta_world):
        """The bone's own rotation once it is turned by this in the world, about its pivot."""
        parent = rig.parent[name]
        pw = wq(m, parent) if parent else R.qconj(R.qy(0))
        target = R.qmul(q_delta_world, wq(m, name))
        return R.qnorm(R.qmul(R.qconj(pw), target))

    def pose(t):
        c = at(t)
        rot, pos = dict(rot0), dict(pos0)
        # pelvis: turned about the vertical where it stands, and shifted
        m = rig.fk(rot, pos, world)
        rot['torso_lower'] = turned(m, rot, 'torso_lower', R.qy(D(c['pelvis'])))
        pos['root'] = pos0['root'] + np.array([-c['hip'][0], c['hip'][1], -c['hip'][2]]) / S.SCALE
        m = rig.fk(rot, pos, world)
        # chest: turned further, and leant into the cut about its own side-to-side axis
        side = R.qrot(wq(m, 'torso_upper'), np.array([1.0, 0, 0]))
        lean = R.qaxis(side, -D(c['lean']))
        rot['torso_upper'] = turned(m, rot, 'torso_upper', R.qmul(R.qy(D(c['chest'])), lean))
        m = rig.fk(rot, pos, world)
        # head: keeps most of its heading
        back = -(c['pelvis'] + c['chest'])
        rot['neck'] = turned(m, rot, 'neck', R.qy(D(.4 * back)))
        m = rig.fk(rot, pos, world)
        rot['head'] = turned(m, rot, 'head', R.qy(D(.4 * back)))
        # legs: to the feet where the guard has them
        m = rig.fk(rot, pos, world)
        parent_q = wq(m, 'torso_lower')
        info = {}
        for s in 'lr':
            limb = body.limbs['leg_' + s]
            hip = pt(m, 'leg_' + s)
            qu, ql, qw_, ang, err = limb.solve(hip, ankle0[s], knee_pole[s], parent_q)
            rot['leg_' + s], rot['shin_' + s] = qu, ql
            rot['ankle_' + s] = R.qmul(R.qconj(R.qmul(qw_, ql)), R.qmul(foot_w0[s], R.qconj(rot0['foot_' + s])))
            rot['foot_' + s] = rot0['foot_' + s]
            pos['shin_' + s] = R.Rig.hinge_offset(ql, rig.pivot['shin_' + s], body.knee[s])
            info['knee_' + s], info['leg_err_' + s] = ang, err
        # right arm: to the wrist, the hand turned so that the blade points where the key has it and the
        # forearm lies in the hand as nearly as it does in the guard
        m = rig.fk(rot, pos, world)
        limb = body.limbs['arm_r']
        shoulder = pt(m, 'arm_r')
        # (never further than the arm goes with the elbow a little bent: the curve between two keys bulges)
        reach = c['wrist'] - shoulder
        if np.linalg.norm(reach) > far:
            c['wrist'] = shoulder + reach * far / np.linalg.norm(reach)
        qu, ql, qw_, ang, err = limb.solve(shoulder, c['wrist'], c['elbow'], wq(m, 'clavicle_r'))
        rot['arm_r'], rot['forearm_r'] = qu, ql
        pos['forearm_r'] = R.Rig.hinge_offset(ql, rig.pivot['forearm_r'], body.elbow['r'])
        m = rig.fk(rot, pos, world)
        fore = unit(pt(m, 'wrist_r') - pt(m, 'forearm_r', body.elbow['r']))
        lean_to = c['blade'] - fore * np.dot(c['blade'], fore)
        blade = unit(math.cos(D(c['angle'])) * fore + math.sin(D(c['angle'])) * unit(lean_to))
        hand_w = R.matq(B.frame(blade, fore) @ B.frame(blade_local, fore_local).T)
        # The hand turns about its own length as far as putting the blade there takes, but no further than a forearm
        # turns: past TWIST_MOST the blade leans off where the key has it instead.
        lower = wq(m, 'forearm_r')
        swing, turn = swing_twist(R.qnorm(R.qmul(R.qconj(lower), hand_w)))
        info['twist_asked'] = turn
        if abs(turn) > TWIST_MOST:
            hand_w = R.qnorm(R.qmul(lower, R.qmul(swing, R.qaxis(LENGTH, D(math.copysign(TWIST_MOST, turn))))))
        rot['hand_r'] = R.qnorm(R.qmul(R.qconj(wq(m, 'wrist_r')), hand_w))
        info['elbow_r'], info['arm_err_r'] = ang, err
        info['wrist_bend'] = c['angle'] - angle0
        m = rig.fk(rot, pos, world)
        return rot, pos, m, info

    last = keys[-1][0]
    count = int(round(last * FPS)) + 1
    posed = [pose(f / FPS) for f in range(count)]
    # how well the solver gives the guard back, and how the cut goes
    rot, pos, m, info = posed[0]
    print('guard given back: wrist off by %.2f, elbow %.2f, knees %.2f %.2f, ankles %.2f %.2f' % (
        np.linalg.norm(pt(m, 'wrist_r') - wrist0), np.linalg.norm(pt(m, 'forearm_r', body.elbow['r']) - elbow0),
        np.linalg.norm(pt(m, 'shin_l', body.knee['l']) - knee0['l']), np.linalg.norm(pt(m, 'shin_r', body.knee['r']) - knee0['r']),
        np.linalg.norm(pt(m, 'ankle_l') - ankle0['l']), np.linalg.norm(pt(m, 'ankle_r') - ankle0['r'])))
    fastest, worst = 0, ''
    tips = []
    for i, (rot, pos, m, info) in enumerate(posed):
        g, tip = P.blade(rig, m)
        tips.append(tip)
        if i:
            for b in ('torso_lower', 'torso_upper', 'head', 'arm_r', 'forearm_r', 'hand_r', 'leg_l', 'leg_r', 'shin_l', 'shin_r'):
                d = abs(float(np.dot(wq(m, b), wq(posed[i - 1][2], b))))
                a = 2 * math.degrees(math.acos(min(1, d)))
                if a > fastest:
                    fastest, worst = a, '%s at frame %d' % (b, i)
    tips = np.array(tips)
    reach = int(np.argmax(tips[:, 2]))
    print('%d frames (%.2f s); fastest joint %.1f deg a frame (%s)' % (count, last, fastest, worst))
    print('tip furthest ahead %.1f at frame %d (height %.1f, %.1f to the left); tip speed at most %.1f a frame' % (
        tips[reach, 2], reach, tips[reach, 1], tips[reach, 0], np.linalg.norm(np.diff(tips, axis=0), axis=1).max()))
    print('arm error at most %.2f, leg error %.2f; elbow %.0f..%.0f, knees %.0f..%.0f / %.0f..%.0f; blade tilted from the guard %.0f..%.0f' % (
        max(p[3]['arm_err_r'] for p in posed), max(max(p[3]['leg_err_l'], p[3]['leg_err_r']) for p in posed),
        min(p[3]['elbow_r'] for p in posed), max(p[3]['elbow_r'] for p in posed),
        min(p[3]['knee_l'] for p in posed), max(p[3]['knee_l'] for p in posed), min(p[3]['knee_r'] for p in posed), max(p[3]['knee_r'] for p in posed),
        min(p[3]['wrist_bend'] for p in posed), max(p[3]['wrist_bend'] for p in posed)))
    met = np.array([wrist_of(wq(p[2], 'forearm_r'), wq(p[2], 'hand_r')) for p in posed])
    asked = [p[3]['twist_asked'] for p in posed]
    print('wrist: bent back %.0f..%.0f, sideways %.0f..%.0f, turned %.0f..%.0f (the keys asked %.0f..%.0f; held on %d frames); the guard %.0f, %.0f, %.0f' % (
        met[:, 0].min(), met[:, 0].max(), met[:, 1].min(), met[:, 1].max(), met[:, 2].min(), met[:, 2].max(), min(asked), max(asked),
        sum(1 for v in asked if abs(v) > TWIST_MOST), met[0, 0], met[0, 1], met[0, 2]))
    head = [pt(p[2], 'head') for p in posed]
    near = min((float(np.linalg.norm(tips[i] - head[i] - np.array([0, 4.0, 0]))), i) for i in range(count))
    print('the tip is never nearer the middle of the head than %.1f (frame %d)' % near)
    for t, _ in keys:
        f = int(round(t * FPS))
        m = posed[f][2]
        row = []
        for n in ('torso_lower', 'torso_upper', 'head'):
            fwd = R.qrot(wq(m, n), np.array([0, 0, -1.0]))
            row.append('%s %.0f' % (n, math.degrees(math.atan2(fwd[0], fwd[2]))))
        g, tip = P.blade(rig, m)
        print('  frame %2d faces (degrees to its left of ahead): %s; wrist %s tip %s' % (f, ', '.join(row), np.round(pt(m, 'wrist_r'), 1), np.round(tip, 1)))
    contact = int(round(CONTACT[WHICH] * FPS))
    # Only the bones a frame turns from the guard, and only by how much: the rotation that, put after the guard's
    # own (in the clip's own space, where the profile keeps it), gives the frame's.
    moved = [n for n in bones if any(R.qangle(R.qmul(R.qnorm(rot[n]), R.qconj(R.qnorm(rot0[n])))) > 1e-5 for rot, _, _, _ in posed)]
    shifted = [n for n in pos0 if any(np.linalg.norm(pos[n] - pos0[n]) > 1e-7 for _, pos, _, _ in posed)]
    frames = []
    for rot, pos, m, info in posed:
        row = {'rotation_delta_wxyz': [], 'position_delta_xyz': {}, 'foot_contact': [True, True]}
        for n in moved:
            delta = R.qnorm(R.qmul(R.baked_to_clip(R.qnorm(rot[n])), R.qconj(R.baked_to_clip(R.qnorm(rot0[n])))))
            row['rotation_delta_wxyz'].append([round(float(x), 6) for x in delta])
        for n in shifted:
            t = pos[n] - pos0[n]
            if n == 'root':
                row['root_delta_m'] = [round(float(x), 6) for x in np.array([-t[0], t[1], t[2]]) * 16 / 112]
            else:
                row['position_delta_xyz'][n] = [round(float(x), 4) for x in (-t[0] * 16, t[1] * 16, t[2] * 16)]
        frames.append(row)
    clip = {'duration_seconds': round((count - 1) / FPS, 7), 'loop': False, 'leading_side': 'r',
            'contact_phase': contact / (count - 1), 'trajectory_m': [[0.0, 0.0, 0.0]] * count,
            'step_contacts': [[True, True]] * count, 'contact_bone': 'knife', 'bones': moved, 'frames': frames}
    print('%d bones turned from the guard: %s; offsets changed: %s' % (len(moved), ' '.join(moved), ' '.join(shifted)))
    doc = {'source': 'Project SEELE original knife cuts (tools/finale/slash.py), MIT', 'sample_rate': FPS,
           'form': 'each frame as its difference from the first frame of r32_knife_forward',
           'clips': {'r32_knife_' + WHICH + '_r64': clip}}
    if os.path.exists(out):
        old = json.load(open(out, encoding='utf8'))
        old['clips'].update(doc['clips'])
        doc = old
    json.dump(doc, open(out, 'w', encoding='utf8'), separators=(',', ':'))
    print('wrote', out, list(doc['clips']))
    if len(sys.argv) > 2 and sys.argv[2] != '-':
        shown = [int(round(t * FPS)) for t, _ in keys]
        shown = sorted(set(shown + [int(round((keys[1][0] + keys[2][0]) / 2 * FPS)), int(round((keys[2][0] + keys[3][0]) / 2 * FPS))]))
        images = [P.views(actors, posed[f][2], '%s %d' % (WHICH, f)) for f in shown]
        R.sheet([row[v] for v in range(3) for row in images], len(shown)).save(sys.argv[2])
        print('wrote', sys.argv[2])


if __name__ == '__main__':
    main()
