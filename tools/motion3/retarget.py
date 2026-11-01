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
}


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


class Calibration:
    """Source joint world rotations at a neutral pose (aligned frame)."""

    def __init__(self, source, frame=0):
        self.R = {k: v[frame].copy() for k, v in source.R.items()}
        self.P = {k: v[frame].copy() for k, v in source.P.items()}

    def delta(self, source, key):
        # world rotation change since the neutral pose
        return np.einsum("nij,kj->nik", source.R[key], self.R[key])


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
        # head from its rotation delta, neck halfway
        Wh = np.einsum("nij,njk->nik", cal.delta(src, "head"), np.tile(np.eye(3), (n, 1, 1)))
        hd = np.einsum("nij,j->ni", Wh, UP)
        hf = np.einsum("nij,j->ni", Wh, FWD)
        W["head"] = align(UP, FWD, hd, hf)
        W["neck"] = slerp_mats(W["torso_upper"], W["head"], 0.5)
        # --- arms: direction from positions, twist from rotation delta
        for s in ("l", "r"):
            W["aim_pitch"] = W["torso_upper"]
            W["clavicle_" + s] = swing_to(W["torso_upper"], self.rest_dir("clavicle_" + s, "arm_" + s),
                                          P["arm_" + s] - P["clav_" + s])
            for bone, a, b, key in (("arm_", "arm_", "fore_", "arm_"), ("forearm_", "fore_", "hand_", "fore_")):
                base = cal.delta(src, key + s)
                d_rest = self.rest_dir(bone + s, ("forearm_" if bone == "arm_" else "wrist_") + s)
                W[bone + s] = swing_to(base, d_rest, P[b + s] - P[a + s])
            W["wrist_" + s] = W["forearm_" + s]
            W["hand_" + s] = cal.delta(src, "hand_" + s)
        # --- legs: IK on scaled ankle targets, knee plane from source knee
        knees = {}
        for s in ("l", "r"):
            hip_t_rest = rig.pivot["leg_" + s] - self.hip_mid_rest
            ankle_t = to_t(P["foot_" + s])
            # hips follow the pelvis orientation around the scaled hip centre
            hip_t = hip_mid_t + np.einsum("nij,j->ni", W["torso_lower"], hip_t_rest)
            knee_src_dir = P["shin_" + s] - 0.5 * (P["thigh_" + s] + P["foot_" + s])
            # straight-leg fallback: knee forward from the thigh rotation delta
            fwd_delta = np.einsum("nij,j->ni", cal.delta(src, "thigh_" + s), FWD)
            bent = np.linalg.norm(knee_src_dir, axis=-1, keepdims=True)
            w = np.clip(bent / 0.04, 0, 1)
            pole = _n(knee_src_dir) * w + fwd_delta * (1 - w)
            knee_t = two_bone(hip_t, ankle_t, self.l_thigh[s], self.l_shin[s], pole)
            knees[s] = (hip_t, knee_t, ankle_t)
            thigh_d = knee_t - hip_t
            shin_d = ankle_t - knee_t
            W["leg_" + s] = align(self.rest_dir("leg_" + s, "shin_" + s), FWD, thigh_d, _n(pole))
            W["shin_" + s] = align(self.rest_dir("shin_" + s, "ankle_" + s), FWD, shin_d, _n(pole))
            W["ankle_" + s] = W["shin_" + s]
            foot_delta = cal.delta(src, "foot_" + s)
            # the neutral source foot maps onto the EVA rest foot
            toe_rest = _n(cal.P["toe_" + s] - cal.P["foot_" + s])
            W["foot_" + s] = swing_to(foot_delta, toe_rest, P["toe_" + s] - P["foot_" + s])
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
