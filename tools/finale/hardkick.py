"""Lay the hard kick on its row: python hardkick.py out.json [sheet.png|-] [table|-]

The kick the Unit has had since September is a captured one (eva_kick_side_left_v1.json: G1 Moves, MOVIN TRACIN
side kick, CC BY 4.0): out of a stance with the right foot ahead, the body sinks back, drives forward over the
right foot, and the left leg comes through from behind and is thrust out ahead at the height of the head. The
owner, 2026-11-18, after the kick written in its place (tools/finale/kick.py): "右键腿击现在像只抬了一下腿，不如之前
那一脚硬踹。那一脚只是连贯度和速度有问题，整体是合理的。所以改回那一脚硬踹，再修连贯度和速度。" This is that kick,
with what was wrong about how it was played put right. Measured in the game (flow group 1, 2026-11-18):

  - it was played from a stand by fading into the capture's stance in a tick and a half: both feet slid to their
    places, 8 blocks one way and 19 the other;
  - the capture's root carries the body 27 blocks forward over the planted right foot. The body's place through a
    blow was the server's, drawn two to three ticks late, and stopped short where the target stood: the planted
    foot slid back 13 blocks under the kick;
  - its wind-up was played at twice the captured pace and its return at six tenths of it (seven ticks to the
    live part, thirteen after it): the leg was thrown up, stood at the top through the hold, and crawled back;
  - the capture ends with the kicking foot still 20 blocks up; the game faded it to the stand in three ticks.

Here the capture is laid on the row so that each part has its time (F, in ticks at the pilot's speed of one):
the wind-up at 1.8 times the captured pace, the kick through its mark at 1.5, the return at 0.85, one curve whose
pace falls from first to last. And three things are written round it, with the capture's own trunk and arms:

  entry    from the stand: the pelvis square, the feet where the Unit stands. The left foot is drawn back and the
           right set forward in one change of feet while the pelvis turns its right side forward, into the
           capture's stance; the arms come up from where they hang.
  feet     a foot on the ground is on the ground at one place: the right from where it is set down to the end,
           the left until it leaves for the kick. (The game holds them there, EvaCombatSupportR33; they are
           written so here too.) The body's path is the capture's own, which kept the right foot still.
  landing  the left foot comes down ahead in the same motion as the leg's return, the right is brought up beside
           it, the pelvis turns square and the arms come down: it ends standing, both feet where the Unit
           stands, a stride and a half ahead of where it began.

The step in ("踢前上一步加在硬踹上"): the change of feet is made on the spot, or carried forward. stride_m is how far
ahead the body is carried through the change of feet, for the whole of it (STRIDE blocks); the game takes the
share that brings the mark to the leg's length (EvaCombatMachineR64.start). With the whole stride the left foot
stays where it stood and the right is set down 23 blocks ahead: a step in. The pose is the same for any share.

Nothing here is taken from the private profile: the rotations are the capture's, or solved here from it. The
rig's measures (bone pivots) are read from the private rig to solve with. The frames are written whole
(rotation_wxyz), not as differences: EvaGameplayMotionR32.addClipsR64 lays them over a frame of its own for the
bones the capture does not have.
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
X, Y, Z = np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])    # the Unit's left, up, ahead
ONE = np.array([1.0, 0, 0, 0])
HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, '..', '..', 'src', 'main', 'resources', 'assets', 'projectseele', 'motion', 'eva_kick_side_left_v1.json')

# The row as EvaMoveTableR64 has it ("kick"), and where its live part lies about the clip's contact.
STARTUP, LIVE, RECOVERY, LEAD, TAIL = 7, 4, 13, .078, .142
TOTAL = STARTUP + LIVE + RECOVERY
SECONDS, CONTACT, FRAMES = TOTAL / 20.0, .37, 3 * TOTAL + 1
# How the Unit stands under the planted movement model, which R64 ships with (a capture of 2026-11-18, standing
# between kicks: the hips over the middle, the ankles level either side of it, the toes 3 degrees out). Under the
# old model it stands with its left foot 2.7 ahead of its right and its hips 0.75 ahead (tools/finale/kick.py has
# those): written for that, this kick was followed under the planted model by a step of a block to tidy the feet.
STAND = dict(ankle={'l': (4.78, 0.0), 'r': (-4.78, 0.0)}, ankle_high=5.76, toes_out=3.0, hip_high=35.07, hips_ahead=0.0)
# The rest of how it stands, measured from the same kind of capture (2026-11-18, the stand with no guard), from the
# middle of the hips to its left, up, ahead: the chest's joint to the middle of the shoulders; each shoulder to its
# elbow and to its wrist.
CHEST = (0.0, 9.08, 2.61)
ELBOW = {'l': (2.64, -9.77, .91), 'r': (-2.68, -9.79, .46)}
WRIST = {'l': (3.83, -18.81, 1.76), 'r': (-3.90, -18.86, .91)}
BLOCKS_A_METRE = 35.0
LAST = 83                   # the capture's last frame
HELD = 76                   # its root goes back towards its start after this frame (a closing of the loop): held
FIRST = 4                   # the capture's root is brought from its start to the foot's lock over its first four frames
CONTACT_FRAME = 48          # the frame the capture's own contract names as the contact
# The change of feet at the start (ticks): each foot off the ground and on it again, and how high. One after the
# other, the left set down as the right leaves: the game stands a pose on whichever foot is lower (written with
# both feet in the air together, the body was let down by the lower foot's height and the feet were drawn sliding
# along the ground, measured 0.03 to 0.2 of a block up where the clip had them 2 to 3).
L_OFF, L_ON, L_LIFT = .3, 1.9, 2.6
R_OFF, R_ON, R_LIFT = 1.7, 3.3, 3.0
TURN = 2.6                  # the pelvis has turned into the capture's stance by this tick
HOP_FROM, HOP_TO = .3, 2.8  # the body's own shift through the change of feet, and the stride
STRIDE = 15.2               # blocks the whole step in carries the body forward
LIFT = 25.5                 # the capture's frame at which the left foot leaves the ground for the kick
# The landing (ticks): the left leg is taken from the capture's return down to the ground between these, then the
# right foot is brought up beside it.
DOWN_FROM, DOWN_TO = 13.5, 20.6
UP_OFF, UP_ON, UP_LIFT = 20.9, 23.4, 2.4
SQUARE_FROM = 17.0          # the pelvis turns square and comes to where it stands between this and the end
ARMS_UP, ARMS_DOWN = 2.4, 17.5


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


# ---- the row's curve (EvaRowClockR64.phase, smooth) ---------------------------------------------------------------

def _inner(before, after, pace_before, pace_after):
    if pace_before * pace_after <= 0:
        return 0.0
    a, b = 2 * after + before, after + 2 * before
    return (a + b) / (a / pace_before + b / pace_after)


def _edge(own, nxt, pace_own, pace_next):
    m = ((2 * own + nxt) * pace_own - own * pace_next) / (own + nxt)
    if m * pace_own <= 0:
        return 0.0
    return 3 * pace_own if abs(m) > 3 * abs(pace_own) else m


def row_phase(place, startup=STARTUP, live=LIVE, recovery=RECOVERY, open_=CONTACT - LEAD, close=CONTACT + TAIL):
    end = startup + live + max(1, recovery)
    if place <= 0:
        return 0.0
    if place >= end:
        return 1.0
    x, y = [0, startup, startup + live, end], [0, open_, close, 1]
    h = [x[1] - x[0], x[2] - x[1], x[3] - x[2]]
    d = [(y[1] - y[0]) / h[0], (y[2] - y[1]) / h[1], (y[3] - y[2]) / h[2]]
    m = [_edge(h[0], h[1], d[0], d[1]), _inner(h[0], h[1], d[0], d[1]), _inner(h[1], h[2], d[1], d[2]), _edge(h[2], h[1], d[2], d[1])]
    i = 0 if place <= x[1] else 1 if place <= x[2] else 2
    t = (place - x[i]) / h[i]
    t2, t3 = t * t, t * t * t
    return min(1.0, max(0.0, (2 * t3 - 3 * t2 + 1) * y[i] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * y[i + 1] + (t3 - t2) * h[i] * m[i + 1]))


def row_place(phase):
    lo, hi = 0.0, float(TOTAL)
    for _ in range(48):
        mid = .5 * (lo + hi)
        if row_phase(mid) < phase:
            lo = mid
        else:
            hi = mid
    return .5 * (lo + hi)


def curve(xs, ys):
    """A curve through the points that never turns back (Fritsch and Carlson), its pace at each end the pace of the stretch there."""
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    h, d = np.diff(xs), np.diff(ys) / np.diff(xs)
    m = np.zeros(len(xs))
    for i in range(1, len(xs) - 1):
        if d[i - 1] * d[i] > 0:
            a, b = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (a + b) / (a / d[i - 1] + b / d[i])
    m[0], m[-1] = d[0], d[-1]

    def f(x):
        x = min(max(x, xs[0]), xs[-1])
        i = min(len(xs) - 2, int(np.searchsorted(xs, x, side='right')) - 1)
        t = (x - xs[i]) / h[i]
        t2, t3 = t * t, t * t * t
        return float((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h[i] * m[i + 1])
    return f


def main():
    out = sys.argv[1]
    src = json.load(open(SOURCE, encoding='utf8'))
    bones = src['bones']
    cap = src['clips']['kick_side_left']
    toes = P.load()['support_toes']
    actors = S.Actors()
    rig = actors.eva_rig
    world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
    world_q = B.mat_rot(world)

    def fk(rot, pos):
        return rig.fk(rot, pos, world)

    def pt(m, name):
        return m[name][:3, :3] @ rig.pivot[name] + m[name][:3, 3]

    def wq(m, name):
        return B.mat_rot(m[name])

    def toe(m, s):
        """The point of the foot the game holds to the ground."""
        n = 'foot_' + s
        return m[n][:3, :3] @ (rig.pivot[n] + np.asarray(toes[s], float)) + m[n][:3, 3]

    def turned(m, name, q_world):
        """The bone's own rotation once it is turned by this in the world, about its pivot."""
        parent = rig.parent[name]
        pw = wq(m, parent) if parent else world_q
        return R.qnorm(R.qmul(R.qconj(pw), R.qmul(q_world, wq(m, name))))

    def shift(pos, by):
        """The whole body moved by this in the world."""
        pos['root'] = pos['root'] + np.array([-by[0], by[1], -by[2]]) / S.SCALE

    def hips_of(m):
        return .5 * (pt(m, 'leg_l') + pt(m, 'leg_r'))

    def line_of(m):
        """The way the pelvis is turned: degrees, from the right hip to the left, none when it is square."""
        across = pt(m, 'leg_l') - pt(m, 'leg_r')
        return math.degrees(math.atan2(across[2], across[0]))

    def heading(m, s):
        """The way a foot points over the ground: degrees to the Unit's left of straight ahead."""
        n = 'foot_' + s
        v = m[n][:3, :3] @ (np.asarray(toes[s], float) * np.array([0, 0, 1.0]))
        return math.degrees(math.atan2(v[0], v[2]))

    # ---- the capture, frame by frame ----
    frames = [P.frame_pose(bones, cap, f) for f in range(LAST + 1)]
    root = np.array([f['root_m'] for f in cap['frames']]) * BLOCKS_A_METRE
    ahead_c, left_c = -root[:, 2], root[:, 0]
    ahead_c[HELD:], left_c[HELD:] = ahead_c[HELD], left_c[HELD]
    # The capture's kick goes out 19 degrees to the left of the way the game takes it to face (the old kick was
    # landed by a table of its own, and nobody saw where the foot went: laid on the row, where the foot itself is
    # what lands, it passed a mark 49 blocks off on its left side). The whole capture is turned about where the
    # Unit stands, pose and path, until the foot's held point at the contact frame is straight ahead.
    rot_c, pos_c = frames[CONTACT_FRAME]
    at_c = toe(fk(rot_c, {'root': np.array([0.0, pos_c['root'][1], 0.0])}), 'l')
    aim = -math.atan2(at_c[0] + left_c[CONTACT_FRAME], at_c[2] + ahead_c[CONTACT_FRAME])
    turn_q = R.qmul(R.qconj(world_q), R.qmul(R.qaxis(Y, aim), world_q))
    for rot_f, _ in frames:
        rot_f['root'] = R.qnorm(R.qmul(turn_q, rot_f['root']))
    left_c, ahead_c = left_c * math.cos(aim) + ahead_c * math.sin(aim), -left_c * math.sin(aim) + ahead_c * math.cos(aim)
    print('  the capture is turned %.1f degrees to its right: its kick goes straight ahead' % -math.degrees(aim))

    def lerp(values, f):
        f = min(max(f, 0.0), float(LAST))
        a = int(math.floor(f))
        b = min(a + 1, LAST)
        return values[a] * (1 - (f - a)) + values[b] * (f - a)

    def source(f):
        f = min(max(f, 0.0), float(LAST))
        a = int(math.floor(f))
        b = min(a + 1, LAST)
        u = f - a
        (ra, pa), (rb, pb) = frames[a], frames[b]
        rot = {n: R.qnorm(R.qslerp(ra[n], rb[n], u)) for n in bones}
        return rot, {'root': np.array([0.0, pa['root'][1] * (1 - u) + pb['root'][1] * u, 0.0])}

    # ---- the capture on the row: which of its frames is played at a tick ----
    t_contact = row_place(CONTACT)
    knots = [(0.0, float(FIRST)), (float(STARTUP), 41.5), (t_contact, float(CONTACT_FRAME)), (9.9, 55.0), (12.2, 66.0), (16.3, 76.0), (20.0, float(LAST)), (float(TOTAL), float(LAST))]
    played = curve([k[0] for k in knots], [k[1] for k in knots])

    def hop(t):
        return smooth((t - HOP_FROM) / (HOP_TO - HOP_FROM))

    def path(t):
        """Where the body is at a tick, to its left and ahead of where it began, with no stride (the capture's own path)."""
        f = played(t)
        return np.array([lerp(left_c, f) - left_c[FIRST] * (1 - hop(t)), 0.0, lerp(ahead_c, f) - ahead_c[FIRST] * (1 - hop(t))])

    def stride(t):
        return STRIDE * hop(t)

    # ---- two bones to a point, from the pose they have ----
    def reach(rot, pos, upper, lower, end, target):
        m = fk(rot, pos)
        a_, k_, e_ = pt(m, upper), pt(m, lower), pt(m, end)
        a, b = np.linalg.norm(k_ - a_), np.linalg.norm(e_ - k_)
        d = min(max(np.linalg.norm(target - a_), abs(a - b) + .05), a + b - .12)
        want = math.acos(min(1.0, max(-1.0, (a * a + b * b - d * d) / (2 * a * b))))
        had = math.acos(min(1.0, max(-1.0, float(np.dot(a_ - k_, e_ - k_)) / (a * b))))
        axis = np.cross(a_ - k_, e_ - k_)
        if np.linalg.norm(axis) < 1e-4 * a * b:
            fwd = np.cross(pt(m, 'leg_l') - pt(m, 'leg_r'), Y)
            axis = np.cross(a_ - k_, -fwd if lower.startswith('shin') else fwd)
        rot[lower] = turned(m, lower, R.qaxis(unit(axis), want - had))
        m = fk(rot, pos)
        rot[upper] = turned(m, upper, R.q_between(pt(m, end) - a_, target - a_))

    def set_foot(rot, pos, s, q_foot):
        m = fk(rot, pos)
        rot['ankle_' + s] = R.qnorm(R.qmul(R.qconj(wq(m, rig.parent['ankle_' + s])), R.qmul(q_foot, R.qconj(rot['foot_' + s]))))

    def place_foot(rot, pos, s, toe_at, q_foot):
        """The leg solved so that the foot's held point is here, the foot turned this way in the world. -> how far off it is left"""
        err = np.zeros(3)
        for _ in range(8):
            set_foot(rot, pos, s, q_foot)
            m = fk(rot, pos)
            err = toe_at - toe(m, s)
            if np.linalg.norm(err) < .004:
                break
            reach(rot, pos, 'leg_' + s, 'shin_' + s, 'ankle_' + s, pt(m, 'ankle_' + s) + err)
        set_foot(rot, pos, s, q_foot)
        return float(np.linalg.norm(toe_at - toe(fk(rot, pos), s)))

    assert rig.parent['foot_l'] == 'ankle_l', rig.parent['foot_l']
    flat = fk({n: ONE for n in rig.pivot}, {})
    flat_heading = {s: heading(flat, s) for s in 'lr'}

    def foot_flat(s, degrees):
        """A foot flat on the ground, pointing this far to the left of straight ahead."""
        return R.qmul(R.qaxis(Y, D(degrees - flat_heading[s])), wq(flat, 'foot_' + s))

    # where the held point of each foot is when the Unit stands
    stand_q = {'l': foot_flat('l', STAND['toes_out']), 'r': foot_flat('r', -STAND['toes_out'])}
    stand_toe = {}
    for s in 'lr':
        m = flat
        v = R.qrot(R.qmul(stand_q[s], R.qconj(wq(flat, 'foot_' + s))), toe(m, s) - pt(m, 'ankle_' + s))
        stand_toe[s] = np.array([STAND['ankle'][s][0], STAND['ankle_high'], STAND['ankle'][s][1]]) + v
    ground = .5 * (stand_toe['l'][1] + stand_toe['r'][1])
    stand_hips = np.array([0.0, STAND['hip_high'], STAND['hips_ahead']])

    # the capture as it is, frame by frame: where its feet are from the body, and which way they point
    raw = []
    for f in range(LAST + 1):
        rot, pos = source(f)
        m = fk(rot, pos)
        raw.append({'toe': {s: toe(m, s) for s in 'lr'}, 'q': {s: wq(m, 'foot_' + s) for s in 'lr'}, 'heading': {s: heading(m, s) for s in 'lr'},
                    'line': line_of(m), 'hips': hips_of(m)})

    def raw_at(f, key, s=None):
        f = min(max(f, 0.0), float(LAST))
        a = int(math.floor(f))
        b = min(a + 1, LAST)
        u = f - a
        va, vb = (raw[a][key], raw[b][key]) if s is None else (raw[a][key][s], raw[b][key][s])
        if key == 'q':
            return R.qnorm(R.qslerp(va, vb, u))
        return va * (1 - u) + vb * u

    def flown(a, b, u, lift):
        """A foot carried from one place on the ground to another."""
        p = a + (b - a) * smooth(u)
        p[1] = ground + lift * math.sin(math.pi * min(1.0, max(0.0, u))) ** 1.2
        return p

    def level(s, f):
        """The capture's foot as the ground has it: flat, pointing the way the capture points it. (The capture
        stands on the ball of its right foot through the kick. Written so, the game still drew the foot flat,
        about its ankle: its held point went 4.5 blocks ahead of where it is held as the heel "came up", measured
        frame by frame. A foot that bears the Unit is flat on the ground here.)"""
        return foot_flat(s, float(raw_at(f, 'heading', s)))

    # the places the feet are held at over the ground, in the world the body's path is in (no stride)
    lo, hi = 0.0, float(TOTAL)
    for _ in range(40):
        mid = .5 * (lo + hi)
        if played(mid) < LIFT:
            lo = mid
        else:
            hi = mid
    t_lift = .5 * (lo + hi)
    f_on_r = played(R_ON)
    held_r = raw_at(f_on_r, 'toe', 'r') * np.array([1, 0, 1]) + path(R_ON)
    t_held = .5 * (L_ON + t_lift)
    held_l = raw_at(played(t_held), 'toe', 'l') * np.array([1, 0, 1]) + path(t_held)
    end_at = path(float(TOTAL))

    def pelvis(m):
        """The pelvis's own left, up and ahead in the world (level: the Unit stands on flat ground here)."""
        left = (pt(m, 'leg_l') - pt(m, 'leg_r')) * np.array([1, 0, 1])
        left = unit(left)
        return np.stack([left, Y, np.cross(left, Y)], axis=1)

    def swivel(rot, pos, upper, lower, end, pole):
        """The limb turned about the line from its root to its end until its middle joint is on the pole's side."""
        m = fk(rot, pos)
        a_, k_, e_ = pt(m, upper), pt(m, lower), pt(m, end)
        axis = unit(e_ - a_)
        had, want = B.perp(k_ - a_, axis), B.perp(np.asarray(pole, float), axis)
        if had is None or want is None:
            return
        angle = math.atan2(float(np.dot(np.cross(had, want), axis)), float(np.dot(had, want)))
        rot[upper] = turned(m, upper, R.qaxis(axis, angle))

    def chest_stands(rot, pos, share):
        """The chest this far towards how the Unit carries it over its hips when it stands."""
        if share <= 0:
            return
        m = fk(rot, pos)
        frame = pelvis(m)
        had = B.frame(.5 * (pt(m, 'arm_l') + pt(m, 'arm_r')) - pt(m, 'torso_upper'), pt(m, 'arm_l') - pt(m, 'arm_r'))
        want = B.frame(frame @ np.asarray(CHEST, float), frame[:, 0])
        rot['torso_upper'] = turned(m, 'torso_upper', R.qnorm(R.qslerp(ONE, R.matq(want @ had.T), share)))

    def arms_hang(rot, pos, share):
        """The arms this far from the capture's guard towards hanging as they do when the Unit stands."""
        if share <= 0:
            return
        hung = dict(rot)
        for s in 'lr':
            m = fk(hung, pos)
            frame = pelvis(m)
            shoulder = pt(m, 'arm_' + s)
            reach(hung, pos, 'arm_' + s, 'forearm_' + s, 'wrist_' + s, shoulder + frame @ np.asarray(WRIST[s], float))
            swivel(hung, pos, 'arm_' + s, 'forearm_' + s, 'wrist_' + s, frame @ np.asarray(ELBOW[s], float))
        for n in ('arm_l', 'forearm_l', 'arm_r', 'forearm_r'):
            rot[n] = R.qnorm(R.qslerp(rot[n], hung[n], share))

    def pose(t):
        f = played(t)
        rot, pos = source(f)
        info = {'f': f}
        # how much the pelvis is as the Unit stands: wholly at the start and at the end
        stood = max(1 - smooth(t / TURN), smooth((t - SQUARE_FROM) / (TOTAL - SQUARE_FROM)))
        m = fk(rot, pos)
        hips_c, line_c = hips_of(m), line_of(m)
        if stood > 0:
            rot['root'] = turned(m, 'root', R.qaxis(Y, D(line_c * stood)))
            for n in ('neck', 'head'):
                rot[n] = R.qnorm(R.qslerp(rot[n], ONE, stood))
            m = fk(rot, pos)
            shift(pos, hips_c + (stand_hips - hips_c) * stood - hips_of(m))
            chest_stands(rot, pos, stood)
        # the hips are down to where the Unit carries them by the time the left foot is on the ground again
        low = smooth((t - DOWN_FROM) / (DOWN_TO - .5 - DOWN_FROM))
        if low > stood:
            now = hips_of(fk(rot, pos))
            shift(pos, np.array([0, (stand_hips[1] - hips_c[1]) * low - (now[1] - hips_c[1]), 0]))
        arms_hang(rot, pos, max(1 - smooth(t / ARMS_UP), smooth((t - ARMS_DOWN) / (TOTAL - ARMS_DOWN))))
        here = path(t)
        on = {'l': t < L_OFF or L_ON <= t < t_lift - .15 or t >= DOWN_TO, 'r': t < R_OFF or R_ON <= t < UP_OFF or t >= UP_ON}
        # right foot: where it stands; carried to where the capture has it set down; held there; brought up at the end
        if t < R_OFF:
            at = stand_toe['r'] - here
            q_r = stand_q['r']
        elif t < R_ON:
            u = (t - R_OFF) / (R_ON - R_OFF)
            at = flown(stand_toe['r'] - path(R_OFF), held_r - path(R_ON) + np.array([0, ground, 0]), u, R_LIFT)
            q_r = R.qnorm(R.qslerp(stand_q['r'], level('r', f_on_r), smooth(u)))
        elif t < UP_OFF:
            at = held_r - here + np.array([0, ground, 0])
            q_r = level('r', f)
        else:
            u = (t - UP_OFF) / (UP_ON - UP_OFF)
            at = flown(held_r - end_at + np.array([0, ground, 0]), stand_toe['r'], u, UP_LIFT)
            q_r = R.qnorm(R.qslerp(level('r', played(UP_OFF)), stand_q['r'], smooth(u)))
        at_r = at
        # the pelvis no higher than lets the right leg reach its foot
        for _ in range(10):
            err = place_foot(rot, pos, 'r', at, q_r)
            if err < .03:
                break
            shift(pos, np.array([0, -1.05 * err, 0]))
        info['err_r'] = err
        # left foot: where it stands; drawn back to where the capture pushes off from; held; the capture's own
        # through the kick; then down ahead to where the Unit stands on it
        took = smooth((t - (t_lift - .15)) / .8)          # the share of the capture's own leg from the lift on
        if t < t_lift + .65:
            if t < L_OFF:
                at = stand_toe['l'] - here
                q_l = stand_q['l']
            elif t < L_ON:
                u = (t - L_OFF) / (L_ON - L_OFF)
                at = flown(stand_toe['l'] - path(L_OFF), held_l - path(L_ON) + np.array([0, ground, 0]), u, L_LIFT)
                q_l = R.qnorm(R.qslerp(stand_q['l'], level('l', LIFT - 1), smooth(u)))
            else:
                at = held_l - here + np.array([0, ground, 0])
                q_l = level('l', LIFT - 1)
            if took > 0:
                at = at + (raw_at(f, 'toe', 'l') - hips_c + hips_of(fk(rot, pos)) - at) * took
                q_l = R.qnorm(R.qslerp(q_l, raw_at(f, 'q', 'l'), took))
            info['err_l'] = place_foot(rot, pos, 'l', at, q_l)
            # held behind, the left foot is reached by the hips coming down for it (and the right leg is solved again under them)
            if L_ON <= t < t_lift - .15:
                for _ in range(10):
                    if info['err_l'] < .03:
                        break
                    shift(pos, np.array([0, -1.05 * info['err_l'], 0]))
                    place_foot(rot, pos, 'r', at_r, q_r)
                    info['err_l'] = place_foot(rot, pos, 'l', at, q_l)
        elif t > DOWN_FROM:
            down = smooth((t - DOWN_FROM) / (DOWN_TO - DOWN_FROM))
            free = toe(fk(rot, pos), 'l')
            at = free + (stand_toe['l'] + end_at - here - free) * down
            q_l = R.qnorm(R.qslerp(wq(fk(rot, pos), 'foot_l'), stand_q['l'], down))
            info['err_l'] = place_foot(rot, pos, 'l', at, q_l)
        else:
            info['err_l'] = 0.0
        m = fk(rot, pos)
        info['on'] = on
        return rot, pos, m, info

    times = [row_place(i / (FRAMES - 1)) for i in range(FRAMES)]
    times[0], times[-1] = 0.0, float(TOTAL)
    posed = [pose(t) for t in times]

    # ---- what it is, in numbers ----
    def knee(m, s):
        a_, k_, e_ = pt(m, 'leg_' + s), pt(m, 'shin_' + s), pt(m, 'ankle_' + s)
        return 180 - math.degrees(math.acos(min(1.0, max(-1.0, float(np.dot(unit(a_ - k_), unit(e_ - k_)))))))

    fine_t = np.arange(0, TOTAL + 1e-9, .25)
    fine = [pose(t) for t in fine_t]
    world_toe = {s: np.array([toe(p[2], s) + path(t) for p, t in zip(fine, fine_t)]) for s in 'lr'}
    for s in 'lr':
        on = np.array([p[3]['on'][s] for p in fine])
        runs, start = [], None
        for i, flag in enumerate(on):
            if flag and start is None:
                start = i
            if (not flag or i == len(on) - 1) and start is not None:
                end = i if not flag else i + 1
                seg = world_toe[s][start:end]
                runs.append('ticks %.2f to %.2f: moves %.2f over the ground, %.2f up and down' % (fine_t[start], fine_t[end - 1],
                            np.linalg.norm(seg[:, [0, 2]] - seg[0, [0, 2]], axis=1).max(), np.abs(seg[:, 1] - ground).max()))
                start = None
        print('  %s foot held: %s' % ('left' if s == 'l' else 'right', '; '.join(runs)))
    print('  solve left off by at most %.3f (right), %.3f (left); the ground is at %.2f' % (max(p[3]['err_r'] for p in fine), max(p[3]['err_l'] for p in fine), ground))
    watch = ('root', 'torso_lower', 'torso_upper', 'leg_l', 'shin_l', 'ankle_l', 'leg_r', 'shin_r', 'arm_l', 'forearm_l', 'arm_r', 'forearm_r', 'head')
    speed = np.array([[4 * 2 * math.degrees(math.acos(min(1, abs(float(np.dot(wq(fine[i][2], b), wq(fine[i - 1][2], b))))))) for b in watch] for i in range(1, len(fine))])
    foot_speed = 4 * np.linalg.norm(np.diff(world_toe['l'], axis=0), axis=1)
    worst = np.unravel_index(int(np.argmax(speed)), speed.shape)
    jump = np.abs(np.diff(speed, axis=0)).max(axis=0)
    print('  fastest joint %.0f degrees a tick (%s at tick %.2f); the left foot at most %.1f blocks a tick (tick %.2f); most a joint\'s speed changes in a quarter tick: %s' % (
        speed.max(), watch[worst[1]], fine_t[worst[0] + 1], foot_speed.max(), fine_t[int(np.argmax(foot_speed)) + 1],
        ', '.join('%s %.0f' % (b, j) for b, j in sorted(zip(watch, jump), key=lambda x: -x[1])[:4])))
    top = int(np.argmax(world_toe['l'][:, 1]))
    still = [fine_t[i + 1] for i in range(len(foot_speed)) if STARTUP - 2 < fine_t[i + 1] < DOWN_TO and foot_speed[i] < 1.0]
    print('  the kicking foot is highest at tick %.2f (%.1f up, %.1f ahead of where the body began); under a block a tick between leaving the ground and coming down: %s' % (
        fine_t[top], world_toe['l'][top, 1] - ground, world_toe['l'][top, 2], ('ticks %.2f to %.2f' % (still[0], still[-1])) if still else 'never'))
    down = [fine_t[i] for i in range(top, len(fine_t)) if world_toe['l'][i, 1] - ground < .15]
    print('  from its highest to the ground: %.1f ticks; the body ends %.1f ahead and %.1f to the left of where it began (and the stride on top)' % (
        (down[0] - fine_t[top]) if down else -1, end_at[2], end_at[0]))
    if len(sys.argv) > 3:
        for t in (0.0, float(TOTAL)):
            m = pose(t)[2]
            hips = hips_of(m)
            print('  tick %.0f from the hips (left, up, ahead): %s' % (t, '  '.join('%s %.1f %.1f %.1f' % ((n,) + tuple(pt(m, n) - hips)) for n in ('head', 'arm_l', 'forearm_l', 'wrist_l', 'arm_r', 'forearm_r', 'wrist_r'))))
        print(' tick  frame phase | body ahead left | pelvis line  hips up | L toe ahead left up  knee on | R toe ahead left up  knee on | L foot speed')
        for i, t in enumerate(fine_t):
            if abs(t - round(t)) > 1e-6 and '--fine' not in sys.argv:
                continue
            rot, pos, m, info = fine[i]
            here = path(t)
            print(' %5.2f %5.1f %.3f | %6.2f %6.2f | %6.1f  %5.2f | %6.2f %6.2f %5.2f  %5.1f %s | %6.2f %6.2f %5.2f  %5.1f %s | %5.1f' % (
                t, info['f'], row_phase(t), here[2], here[0], line_of(m), hips_of(m)[1],
                world_toe['l'][i, 2], world_toe['l'][i, 0], world_toe['l'][i, 1] - ground, knee(m, 'l'), 'x' if info['on']['l'] else ' ',
                world_toe['r'][i, 2], world_toe['r'][i, 0], world_toe['r'][i, 1] - ground, knee(m, 'r'), 'x' if info['on']['r'] else ' ',
                foot_speed[min(len(foot_speed) - 1, max(0, i - 1))]))

    # ---- written whole ----
    rows = []
    for i, (rot, pos, m, info) in enumerate(posed):
        p = pos['root']
        rows.append({'rotation_wxyz': [[round(float(x), 6) for x in R.baked_to_clip(R.qnorm(rot[n]))] for n in bones],
                     'root_m': [round(float(x), 6) for x in (-p[0] * 16 / 112, p[1] * 16 / 112, p[2] * 16 / 112)],
                     'foot_contact': [bool(info['on']['l']), bool(info['on']['r'])]})
    clip = {'duration_seconds': SECONDS, 'loop': False, 'leading_side': 'l', 'contact_phase': CONTACT,
            'trajectory_m': [[round(float(path(t)[0]) / BLOCKS_A_METRE, 6), 0.0, round(float(-path(t)[2]) / BLOCKS_A_METRE, 6)] for t in times],
            'stride_m': [[0.0, 0.0, round(-stride(t) / BLOCKS_A_METRE, 6)] for t in times],
            'step_contacts': [r['foot_contact'] for r in rows], 'contact_bone': 'foot_l', 'bones': bones, 'frames': rows}
    doc = {'source': 'G1 Moves MOVIN TRACIN Side Kick (CC BY 4.0, as eva_kick_side_left_v1.json), laid on its row with an entry from the stand and a landing: tools/finale/hardkick.py',
           'sample_rate': 60, 'form': 'each frame whole, for the bones named',
           'row': {'startup': STARTUP, 'live': LIVE, 'recovery': RECOVERY, 'lead': LEAD, 'tail': TAIL},
           'stride_blocks': STRIDE, 'clips': {'r32_kick_hard_r64': clip}}
    if out != '-':
        json.dump(doc, open(out, 'w', encoding='utf8'), separators=(',', ':'))
        print('wrote', out, os.path.getsize(out), 'bytes')
    if len(sys.argv) > 2 and sys.argv[2] != '-':
        shown = [0.0, 1.0, 2.0, 3.0, 4.2, 5.6, 7.0, t_contact, 9.9, 12.0, 14.0, 16.0, 18.0, 19.5, 21.2, 24.0]
        share = float(sys.argv[sys.argv.index('--stride') + 1]) if '--stride' in sys.argv else 0.0

        def drawn(t):
            rot, pos, m, info = pose(t)
            here = path(t)
            return rig.fk(rot, pos, R.entity_matrix([here[0], 0, here[2] + share * stride(t)], 0, S.SCALE))
        images = [P.views(actors, drawn(t), 'hard kick %.1f' % t, knife=False) for t in shown]
        R.sheet([row[v] for v in range(2) for row in images], len(shown) // 2).save(sys.argv[2])
        print('wrote', sys.argv[2])


if __name__ == '__main__':
    main()
