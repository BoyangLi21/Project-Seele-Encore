"""Landmark + rotation-delta retargeting from human mocap onto the EVA pivot rig.

Directions of the trunk and limbs come from source joint positions; twist
comes from the source joint rotations relative to a neutral calibration frame
(standing, arms down) that matches the EVA rest pose.  Legs are solved with
two-bone IK so the scaled ankle trajectory, and with it ground contact, is
preserved despite the EVA's different thigh/shin proportions.
"""

import numpy as np

from evarig import align, axis_angle, basis, swing_to

UP = np.array([0.0, 1.0, 0.0])
FWD = np.array([0.0, 0.0, -1.0])   # EVA faces -Z in model space
RIGHT = np.array([1.0, 0.0, 0.0])


# Source skeleton descriptions: semantic joint -> source joint name.
SKELETONS = {
    "bandai": {
        "hips": "Hips", "spine": "Spine", "chest": "Chest", "neck": "Neck", "head": "Head",
        "clav_l": "Shoulder_L", "arm_l": "UpperArm_L", "fore_l": "LowerArm_L", "hand_l": "Hand_L",
        "clav_r": "Shoulder_R", "arm_r": "UpperArm_R", "fore_r": "LowerArm_R", "hand_r": "Hand_R",
        "thigh_l": "UpperLeg_L", "shin_l": "LowerLeg_L", "foot_l": "Foot_L", "toe_l": "Toes_L",
        "thigh_r": "UpperLeg_R", "shin_r": "LowerLeg_R", "foot_r": "Foot_R", "toe_r": "Toes_R",
        "unit": 0.01,  # cm -> m
    },
    # G1 Moves (MOVIN TRACIN capture, CC BY 4.0): Mixamo naming, metres, T-pose rest
    "g1": {
        "hips": "Hips", "spine": "Spine", "chest": "Spine1", "neck": "Neck", "head": "Head",
        "clav_l": "LeftShoulder", "arm_l": "LeftArm", "fore_l": "LeftForeArm", "hand_l": "LeftHand",
        "clav_r": "RightShoulder", "arm_r": "RightArm", "fore_r": "RightForeArm", "hand_r": "RightHand",
        "thigh_l": "LeftUpLeg", "shin_l": "LeftLeg", "foot_l": "LeftFoot", "toe_l": "LeftToeBase",
        "thigh_r": "RightUpLeg", "shin_r": "RightLeg", "foot_r": "RightFoot", "toe_r": "RightToeBase",
        "hand_tip_l": "LeftHandMiddle1", "hand_tip_r": "RightHandMiddle1",
        "unit": 1.0,
    },
}
# Mixamo FBX baked by blender/bake_fbx.py (prefix stripped, metres)
SKELETONS["mixamo"] = SKELETONS["g1"]


def _n(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def yaw_matrix(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


class Source:
    """Source motion in a facing-normalised, metre, Y-up frame."""

    def __init__(self, bvh, skel, align_frame=0, heading=None, travel=None):
        self.skel = SKELETONS[skel] if isinstance(skel, str) else skel
        self.bvh = bvh
        unit = self.skel["unit"]
        P = {k: bvh.pos(v) * unit for k, v in self.skel.items() if k != "unit"}
        R = {k: bvh.rot(v) for k, v in self.skel.items() if k != "unit"}
        if travel is not None:
            # face along the hip displacement between two frames
            a, b = travel
            fwd = P["hips"][b] - P["hips"][a]
            fwd[1] = 0
            fwd = _n(fwd)
            align_frame = a
        else:
            # facing at the alignment frame: forward = up x right (pelvis)
            right = P["thigh_r"][align_frame] - P["thigh_l"][align_frame]
            right[1] = 0
            fwd = np.cross(UP, _n(right))
        ang = np.arctan2(fwd[0], fwd[2]) if heading is None else heading
        # rotate so that fwd -> -Z: yaw by (pi - ang) about Y
        G = yaw_matrix(np.pi - ang)
        origin = P["hips"][align_frame].copy()
        origin[1] = 0.0
        self.G = G
        self.P = {k: np.einsum("ij,nj->ni", G, v - origin) for k, v in P.items()}
        self.R = {k: np.einsum("ij,njk->nik", G, v) for k, v in R.items()}
        self.n = bvh.frames
        self.rate = bvh.rate

    def window(self, a, b):
        """Frames [a, b] as a new source (same alignment)."""
        out = Source.__new__(Source)
        out.skel, out.bvh, out.G, out.rate = self.skel, self.bvh, self.G, self.rate
        out.P = {k: v[a:b + 1].copy() for k, v in self.P.items()}
        out.R = {k: v[a:b + 1].copy() for k, v in self.R.items()}
        out.n = b - a + 1
        return out

    def mirrored(self):
        """Left/right mirror across the sagittal (x = 0) plane of the aligned frame."""
        M = np.diag([-1.0, 1.0, 1.0])
        out = Source.__new__(Source)
        # aligned = G raw; mirrored aligned = (M G M)(M raw)
        out.skel, out.bvh, out.G, out.n, out.rate = self.skel, self.bvh, M @ self.G @ M, self.n, self.rate
        swap = lambda k: k[:-2] + ("_r" if k.endswith("_l") else "_l") if k[-2:] in ("_l", "_r") else k  # noqa: E731
        out.P = {swap(k): v * np.array([-1.0, 1.0, 1.0]) for k, v in self.P.items()}
        out.R = {swap(k): np.einsum("ij,njk,kl->nil", M, v, M) for k, v in self.R.items()}
        return out


class Calibration:
    """Source joint world rotations at a neutral pose (aligned frame)."""

    def __init__(self, source, frame=0):
        # stored in the raw capture frame so any clip alignment can use it
        Gt = source.G.T
        self.R = {k: Gt @ v[frame] for k, v in source.R.items()}
        self.P = {k: Gt @ v[frame] for k, v in source.P.items()}

    def delta(self, source, key):
        """World rotation change since the neutral pose, in the source's aligned frame:
        G R_raw(f) R_raw(cal)^T G^T."""
        return np.einsum("nij,kj->nik", source.R[key], self.R[key]) @ source.G.T

    def dir(self, source, a, b):
        """Neutral-pose direction a -> b expressed in the source's aligned frame."""
        return source.G @ _n(self.P[b] - self.P[a])


def two_bone(hip, ankle, l1, l2, pole):
    """Knee position for a two-bone chain; pole is a direction hint."""
    d = ankle - hip
    dist = np.linalg.norm(d, axis=-1)
    dist_c = np.clip(dist, 1e-6, (l1 + l2) * 0.9999)
    dn = d / np.maximum(dist[:, None], 1e-9)
    # law of cosines: distance along d to the knee projection
    a = (l1 * l1 - l2 * l2 + dist_c * dist_c) / (2 * dist_c)
    h = np.sqrt(np.maximum(l1 * l1 - a * a, 0))
    p = pole - dn * np.sum(pole * dn, axis=-1, keepdims=True)
    p = _n(p)
    return hip + dn * a[:, None] + p * h[:, None]


class Retargeter:
    def __init__(self, rig, side_names=("l", "r")):
        self.rig = rig
        piv = rig.pivot
        self.hip_mid_rest = 0.5 * (piv["leg_l"] + piv["leg_r"])
        self.l_thigh = {s: np.linalg.norm(piv["shin_" + s] - piv["leg_" + s]) for s in side_names}
        self.l_shin = {s: np.linalg.norm(piv["ankle_" + s] - piv["shin_" + s]) for s in side_names}
        self.ankle_h = piv["ankle_l"][1]

    def rest_dir(self, a, b):
        return _n(self.rig.pivot[b] - self.rig.pivot[a])

    def run(self, src, cal, root_motion=True):
        rig = self.rig
        n = src.n
        P = src.P
        # --- scale: source leg length (hip->knee->ankle) at calibration vs EVA
        s_leg = []
        for s in ("l", "r"):
            s_leg.append(np.linalg.norm(P["shin_" + s] - P["thigh_" + s], axis=-1).mean()
                         + np.linalg.norm(P["foot_" + s] - P["shin_" + s], axis=-1).mean())
        t_leg = np.mean([self.l_thigh[s] + self.l_shin[s] for s in ("l", "r")])
        scale = t_leg / np.mean(s_leg)
        # ground: the lowest ankle height of the clip maps to the EVA rest ankle height
        src_ankle_floor = min(P["foot_l"][:, 1].min(), P["foot_r"][:, 1].min())
        def to_t(p):
            q = p * scale
            q[..., 1] += self.ankle_h - src_ankle_floor * scale
            return q
        hip_mid_s = 0.5 * (P["thigh_l"] + P["thigh_r"])
        hip_mid_t = to_t(hip_mid_s)
        W = {}
        # --- trunk
        right_p = _n(P["thigh_r"] - P["thigh_l"])
        up_p = _n(P["spine"] - P["hips"])
        W["torso_lower"] = align(UP, FWD, up_p, np.cross(up_p, right_p))
        right_c = _n(P["clav_r"] - P["clav_l"])
        up_c = _n(P["neck"] - P["chest"])
        W["torso_upper"] = align(self.rest_dir("torso_upper", "neck") if "neck" in rig.pivot else UP,
                                 FWD, up_c, np.cross(up_c, right_c))
        # head: tilt follows the neck line, facing follows the chest (no
        # calibration-frame rotation, which is unreliable for end joints)
        chest_fwd = np.einsum("nij,j->ni", W["torso_upper"], FWD)
        neck_up = _n(P["head"] - P["neck"]) if np.linalg.norm(P["head"] - P["neck"], axis=-1).min() > 1e-4 else up_c
        W["head"] = align(UP, FWD, neck_up, chest_fwd)
        W["neck"] = slerp_mats(W["torso_upper"], W["head"], 0.5)
        W["aim_pitch"] = W["torso_upper"]
        # --- arms: the elbow is a hinge shared by upper arm and forearm; the
        # hand follows the forearm with a limited wrist bend.
        for s in ("l", "r"):
            W["clavicle_" + s] = swing_to(W["torso_upper"], self.rest_dir("clavicle_" + s, "arm_" + s),
                                          P["arm_" + s] - P["clav_" + s])
            up_dir = P["fore_" + s] - P["arm_" + s]
            lo_dir = P["hand_" + s] - P["fore_" + s]
            rest_up = self.rest_dir("arm_" + s, "forearm_" + s)
            rest_lo = self.rest_dir("forearm_" + s, "wrist_" + s)
            hinge_rest = _n(np.cross(rest_up, FWD))
            # seed: the chest's lateral axis, then carried frame to frame
            seed = np.einsum("nij,j->ni", W["torso_upper"], hinge_rest)
            hinge = hinge_track(up_dir, lo_dir, seed)
            W["arm_" + s] = align(rest_up, hinge_rest, up_dir, hinge)
            W["forearm_" + s] = align(rest_lo, hinge_rest, lo_dir, hinge)
            W["wrist_" + s] = W["forearm_" + s]
            tip = "hand_tip_" + s
            if tip in P:
                rest_hand = self.rest_dir("hand_" + s, "finger_middle_axis_" + s) \
                    if "finger_middle_axis_" + s in rig.pivot else rest_lo
                W["hand_" + s] = limited_swing(W["forearm_" + s], rest_hand, P[tip] - P["hand_" + s], np.radians(35))
            else:
                W["hand_" + s] = W["forearm_" + s]
        # --- legs: IK on scaled ankle targets, knee plane from source knee
        knees = {}
        for s in ("l", "r"):
            hip_t_rest = rig.pivot["leg_" + s] - self.hip_mid_rest
            ankle_t = to_t(P["foot_" + s])
            # hips follow the pelvis orientation around the scaled hip centre
            hip_t = hip_mid_t + np.einsum("nij,j->ni", W["torso_lower"], hip_t_rest)
            knee_src_dir = P["shin_" + s] - 0.5 * (P["thigh_" + s] + P["foot_" + s])
            # straight-leg fallback: knees point along the pelvis forward
            fwd_pelvis = np.einsum("nij,j->ni", W["torso_lower"], FWD)
            bent = np.linalg.norm(knee_src_dir, axis=-1, keepdims=True)
            w = np.clip(bent / 0.04, 0, 1)
            pole = _n(knee_src_dir) * w + fwd_pelvis * (1 - w)
            knee_t = two_bone(hip_t, ankle_t, self.l_thigh[s], self.l_shin[s], pole)
            knees[s] = (hip_t, knee_t, ankle_t)
            thigh_d = knee_t - hip_t
            shin_d = ankle_t - knee_t
            W["leg_" + s] = align(self.rest_dir("leg_" + s, "shin_" + s), FWD, thigh_d, _n(pole))
            W["shin_" + s] = align(self.rest_dir("shin_" + s, "ankle_" + s), FWD, shin_d, _n(pole))
            W["ankle_" + s] = W["shin_" + s]
            # Foot: in the air it hinges about the shin's lateral axis toward
            # the source toe line (limited plantar/dorsal flexion, no roll or
            # twist against the shin); planted it lies level along the source
            # heading.  The source's own planted pitch defines "flat".
            toe = P["toe_" + s] - P["foot_" + s]
            contact = foot_contacts(src, s)
            tn = _n(toe)
            pitches = np.arcsin(np.clip(-tn[:, 1], -1, 1))
            flat = np.median(pitches[contact]) if contact.any() else np.median(pitches)
            toe_rest = np.array([0.0, -np.sin(flat), -np.cos(flat)])
            W["foot_" + s] = foot_orientation(W["shin_" + s], toe_rest, tn, contact)
        # --- convert world rotations to local
        local = {}
        world = {}
        for name in rig.names:
            p = rig.parent[name]
            pw = world.get(p) if p else None
            w = W.get(name)
            if w is None:
                # unmapped: inherit parent (identity local) except bind axes
                lr = np.tile(rig.bind[name] if "_axis_" in name else np.eye(3), (n, 1, 1))
                world[name] = lr if pw is None else pw @ lr
                local[name] = lr
                continue
            world[name] = w
            local[name] = w if pw is None else np.einsum("nji,njk->nik", pw, w)
        # root: translate so the posed hip centre lands on the scaled source hip centre
        wr, wp = rig.fk(local)
        posed_mid = 0.5 * (wp["leg_l"] + wp["leg_r"])
        root_t = hip_mid_t - posed_mid
        if not root_motion:
            root_t[:, 0] = 0
            root_t[:, 2] = 0
        return {"local": local, "root": root_t, "scale": scale, "knees": knees, "rate": src.rate}


def foot_orientation(shin, toe_rest, toe_dir, contact, plantar=np.radians(50), dorsal=np.radians(30),
                     settle=6):
    """Foot world rotation per frame (see Retargeter.run)."""
    from evarig import mat_to_quat, quat_to_mat
    n = shin.shape[0]
    hinge = shin[:, :, 0]  # the shin frame's lateral axis
    rest_toe = np.einsum("nij,j->ni", shin, toe_rest)
    d = toe_dir - hinge * np.sum(toe_dir * hinge, axis=1, keepdims=True)
    d = _n(d)
    # signed angle rest_toe -> d about the hinge; + lifts the toes (dorsal)
    ang = np.arctan2(np.sum(np.cross(rest_toe, d) * hinge, axis=1), np.sum(rest_toe * d, axis=1))
    ang = np.clip(ang, -plantar, dorsal)
    air = np.empty_like(shin)
    for i in range(n):
        air[i] = axis_angle(hinge[i], ang[i]) @ shin[i]
    # level foot along the source heading (planted frames)
    flat = toe_dir.copy()
    flat[:, 1] = 0
    fl = np.linalg.norm(flat, axis=1, keepdims=True)
    shin_fwd = np.einsum("nij,j->ni", shin, FWD)
    shin_fwd[:, 1] = 0
    flat = np.where(fl > 0.2, flat, shin_fwd)
    # the rest foot is level, so a planted foot is the rest foot turned in yaw
    ground = align(FWD, UP, _n(flat), np.tile(UP, (n, 1)))
    # contact weight eased over a few frames so landing and lift-off blend
    w = contact.astype(float)
    k = np.ones(settle) / settle
    w = np.convolve(np.pad(w, (settle // 2, settle - 1 - settle // 2), mode="edge"), k, mode="valid")
    w = w * w * (3 - 2 * w)
    qa, qg = mat_to_quat(air), mat_to_quat(ground)
    dot = np.sum(qa * qg, axis=1, keepdims=True)
    qg = np.where(dot < 0, -qg, qg)
    q = qa * (1 - w)[:, None] + qg * w[:, None]
    return quat_to_mat(q / np.linalg.norm(q, axis=1, keepdims=True))


def hinge_track(upper, lower, seed, bend_on=np.radians(12), bend_full=np.radians(30)):
    """Elbow hinge axis per frame: the bend plane normal while the elbow is bent,
    otherwise the previous axis kept perpendicular to the upper arm (continuous,
    no dependence on a calibration pose)."""
    n = upper.shape[0]
    u = _n(upper)
    lo = _n(lower)
    out = np.empty((n, 3))
    prev = None
    for i in range(n):
        geo = np.cross(u[i], lo[i])
        s = np.linalg.norm(geo)
        bend = np.arctan2(s, np.dot(u[i], lo[i]))
        carried = seed[i] if prev is None else prev
        carried = carried - u[i] * np.dot(carried, u[i])
        carried /= max(np.linalg.norm(carried), 1e-9)
        if s > 1e-6:
            geo = geo / s
            if np.dot(geo, carried) < 0:
                geo = -geo
            w = np.clip((bend - bend_on) / (bend_full - bend_on), 0, 1)
            h = geo * w + carried * (1 - w)
            h = h - u[i] * np.dot(h, u[i])
            h /= max(np.linalg.norm(h), 1e-9)
        else:
            h = carried
        out[i] = h
        prev = h
    return out


def limited_swing(parent_world, d_rest, d_post, max_angle):
    """Child = parent rotated by the swing toward d_post, clamped to max_angle."""
    cur = _n(np.einsum("nij,j->ni", parent_world, d_rest))
    tgt = _n(d_post)
    axis = np.cross(cur, tgt)
    s = np.linalg.norm(axis, axis=-1)
    c = np.clip(np.sum(cur * tgt, axis=-1), -1, 1)
    ang = np.minimum(np.arctan2(s, c), max_angle)
    out = np.empty_like(parent_world)
    for i in range(parent_world.shape[0]):
        out[i] = parent_world[i] if s[i] < 1e-9 else axis_angle(axis[i] / s[i], ang[i]) @ parent_world[i]
    return out


def slerp_mats(a, b, t):
    from evarig import mat_to_quat, quat_to_mat
    qa, qb = mat_to_quat(a), mat_to_quat(b)
    dot = np.sum(qa * qb, axis=1, keepdims=True)
    qb = np.where(dot < 0, -qb, qb)
    dot = np.abs(dot)
    th = np.arccos(np.clip(dot, -1, 1))
    s = np.sin(th)
    w1 = np.where(s > 1e-6, np.sin((1 - t) * th) / np.maximum(s, 1e-9), 1 - t)
    w2 = np.where(s > 1e-6, np.sin(t * th) / np.maximum(s, 1e-9), t)
    return quat_to_mat(qa * w1 + qb * w2)


def foot_contacts(src, key, height=0.06, speed=0.35):
    """Boolean contact per frame from source ankle/toe height and speed (metres)."""
    p = src.P["toe_" + key] if ("toe_" + key) in src.P else src.P["foot_" + key]
    a = src.P["foot_" + key]
    floor = min(src.P["foot_l"][:, 1].min(), src.P["foot_r"][:, 1].min())
    v = np.zeros(src.n)
    v[1:] = np.linalg.norm(np.diff(a, axis=0), axis=1) * src.rate
    v[0] = v[1]
    return ((a[:, 1] - floor) < height) & (v < speed)
