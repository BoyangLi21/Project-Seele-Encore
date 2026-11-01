"""Fit a closed fist for an anatomical EVA hand rig.

python fist_fit.py --rigs <hand_rigs dir> --units 0,1,2,4 --out hand_poses.json

For each finger the (MCP, PIP, DIP) flexion is searched inside the joint
limits so the fingertip lands on the palm just behind its own knuckle and
stays in front of the palm plane; the thumb is searched so its tip rests
across the front face of the index and middle middle phalanges.  The result is a pose
override (explicit per-joint flex, twist, splay) that the motion pack carries
and the runtime merges over the contract's controls; the contract file, and
with it every recorded contract fingerprint, stays unchanged.
"""

import argparse
import itertools
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender"))


def qmat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def rot_zyx(z, y, x):
    cz, sz, cy, sy, cx, sx = math.cos(z), math.sin(z), math.cos(y), math.sin(y), math.cos(x), math.sin(x)
    return (np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
            @ np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]))


class Hand:
    def __init__(self, contract, side):
        self.sign = 1.0 if side == "l" else -1.0
        self.specs = {b["name"]: b for b in contract["new_bones"]}
        self.joints = {}
        self.digits = {}
        for digit, dv in contract["hands"][side]["digits"].items():
            for j in dv["joints"]:
                self.joints[j["name"]] = dict(j, digit=digit)
                self.digits.setdefault(digit, []).append(j["name"])
        for d in self.digits:
            self.digits[d].sort(key=lambda n: self.joints[n]["index"])
        self.pivot = {n: np.array(s["pivot"], float) * np.array([-1, 1, 1]) / 16 for n, s in self.specs.items()}

    def neutral(self, name):
        j = self.joints[name]
        return qmat(j.get("neutral_local_quaternion_xyzw") or j.get("local_bind_quaternion_xyzw"))

    def local(self, name, flex, twist=0.0, splay=0.0):
        lim = self.joints[name]["anatomical_limits_degrees"]
        flex = min(max(flex, lim[0][0]), lim[0][1])
        twist = min(max(twist, lim[1][0]), lim[1][1])
        splay = min(max(splay, lim[2][0]), lim[2][1])
        return self.neutral(name) @ rot_zyx(math.radians(self.sign * splay), math.radians(self.sign * twist),
                                            math.radians(-flex))

    def chain(self, names, angles):
        """World 4x4 of each joint for local angles [(flex, twist, splay)...] (hand at rest)."""
        M = np.eye(4)
        out = []
        for name, (f, t, s) in zip(names, angles):
            p = self.pivot[name]
            L = np.eye(4)
            L[:3, :3] = self.local(name, f, t, s)
            T1 = np.eye(4); T1[:3, 3] = p
            T2 = np.eye(4); T2[:3, 3] = -p
            M = M @ T1 @ L @ T2
            out.append(M.copy())
        return out

    def ib(self, name):
        return np.array(self.joints[name]["inverse_bind_column_major"], float).reshape(4, 4).T

    def posed(self, name, M, bind_point):
        """A point given at the bind pose, carried by joint `name` posed as M.
        Bind points (head_bind/tip_bind) already include the neutral rotation;
        the pivots are the unrotated rest skeleton, so go through the inverse bind."""
        return (M @ self.ib(name) @ np.append(np.asarray(bind_point, float), 1.0))[:3]

    def tip(self, names, angles):
        Ms = self.chain(names, angles)
        last = self.joints[names[-1]]
        return self.posed(names[-1], Ms[-1], last["tip_bind"]), Ms

    def head(self, name):
        return np.array(self.joints[name]["head_bind"], float)


def frange(lo, hi, n):
    return np.linspace(lo, hi, n)


def fit(contract, side, base_pose="fist"):
    h = Hand(contract, side)
    fingers = [d for d in ("index", "middle", "ring", "little") if d in h.digits]
    wrist = np.array(h.specs[h.specs[h.digits["index"][0]]["parent"]]["pivot"], float) * np.array([-1, 1, 1]) / 16 \
        if h.specs[h.digits["index"][0]]["parent"] in h.specs else None
    if wrist is None:
        # finger bases hang from hand_<side>; use the mean base minus the finger direction
        wrist = np.mean([h.head(h.digits[d][0]) for d in fingers], 0)
    bases = {d: h.head(h.digits[d][0]) for d in fingers}
    across = bases[fingers[0]] - bases[fingers[-1]]
    # palm side: the direction a positive MCP flexion carries the fingertip
    probe0, _ = h.tip(h.digits["middle"], [(0, 0, 0)] * 3)
    probe1, _ = h.tip(h.digits["middle"], [(60, 0, 0), (0, 0, 0), (0, 0, 0)])
    along = probe0 - bases["middle"]
    along /= np.linalg.norm(along)
    normal = np.cross(across, along)
    normal -= along * np.dot(normal, along)
    normal /= np.linalg.norm(normal)
    if np.dot(probe1 - probe0, normal) < 0:
        normal = -normal
    result = {}
    for d in fingers:
        names = h.digits[d]
        length = sum(h.joints[n]["length"] for n in names)
        # tip target: on the palm, one third of the finger length behind its knuckle,
        # lifted off the palm plane by a finger thickness
        target = bases[d] - along * (0.34 * length) + normal * (0.09 * length)
        best = None
        lims = [h.joints[n]["anatomical_limits_degrees"][0] for n in names]
        for a, b, c in itertools.product(frange(max(40, lims[0][0]), lims[0][1], 12),
                                         frange(max(50, lims[1][0]), lims[1][1], 12),
                                         frange(max(20, lims[2][0]), lims[2][1], 10)):
            tip, Ms = h.tip(names, [(a, 0, 0), (b, 0, 0), (c, 0, 0)])
            err = np.linalg.norm(tip - target)
            # never through the palm, and keep the curl natural: DIP follows PIP
            depth = np.dot(tip - bases[d], normal)
            pen = max(0.0, 0.03 * length - depth) * 4
            nat = abs(c - 0.72 * b) / 90 * 0.15 * length
            cost = err + pen + nat
            if best is None or cost < best[0]:
                best = (cost, (a, b, c), err)
        result[d] = best
    # thumb: tip across the front of the index/middle middle phalanges
    if "thumb" in h.digits:
        idx_M = h.chain(h.digits["index"], [(result["index"][1][0], 0, 0), (result["index"][1][1], 0, 0),
                                            (result["index"][1][2], 0, 0)])
        mid_M = h.chain(h.digits["middle"], [(result["middle"][1][0], 0, 0), (result["middle"][1][1], 0, 0),
                                             (result["middle"][1][2], 0, 0)])
        # middle phalanx midpoints (PIP -> DIP) of the fitted index and middle
        # fingers: in a fist they form the front face the thumb lies across
        def phalanx_mid(d, M):
            a = h.posed(h.digits[d][1], M[1], h.head(h.digits[d][1]))
            b = h.posed(h.digits[d][2], M[2], h.head(h.digits[d][2]))
            return 0.5 * (a + b)
        p_idx = phalanx_mid("index", idx_M)
        p_mid = phalanx_mid("middle", mid_M)
        flen = sum(h.joints[n]["length"] for n in h.digits["middle"])
        target = 0.5 * (p_idx + p_mid) + along * (0.12 * flen)
        names = h.digits["thumb"]
        lim = [h.joints[n]["anatomical_limits_degrees"] for n in names]
        best = None
        for f1, s1, t1, f2, f3 in itertools.product(frange(lim[0][0][0], lim[0][0][1], 9),
                                                    frange(lim[0][2][0], lim[0][2][1], 7),
                                                    frange(lim[0][1][0], lim[0][1][1], 5),
                                                    frange(max(0, lim[1][0][0]), lim[1][0][1], 7),
                                                    frange(max(0, lim[2][0][0]), lim[2][0][1], 7)):
            tip, _ = h.tip(names, [(f1, t1, s1), (f2, 0, 0), (f3, 0, 0)])
            err = np.linalg.norm(tip - target)
            if best is None or err < best[0]:
                best = (err, (f1, t1, s1, f2, f3), err)
        result["thumb"] = best
    angles = {}
    for d in fingers:
        a, b, c = result[d][1]
        for n, v in zip(h.digits[d], (a, b, c)):
            angles[n] = [round(float(v), 2), 0.0, 0.0]
    if "thumb" in result:
        f1, t1, s1, f2, f3 = result["thumb"][1]
        n1, n2, n3 = h.digits["thumb"]
        angles[n1] = [round(float(f1), 2), round(float(t1), 2), round(float(s1), 2)]
        angles[n2] = [round(float(f2), 2), 0.0, 0.0]
        angles[n3] = [round(float(f3), 2), 0.0, 0.0]
    return angles, {d: round(float(v[2]) * 16, 3) for d, v in result.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rigs", required=True, help="hand_rigs directory (unit0X/hand_rig_contract.json)")
    ap.add_argument("--units", default="0,1,2,4")
    ap.add_argument("--out", required=True, help="hand pose overrides json for the motion pack")
    ap.add_argument("--pose", default="fist")
    a = ap.parse_args()
    out = {}
    for unit in a.units.split(","):
        with open(os.path.join(a.rigs, f"unit0{unit}", "hand_rig_contract.json"), encoding="utf-8") as f:
            contract = json.load(f)
        bone = {}
        for side in ("l", "r"):
            angles, err = fit(contract, side)
            bone.update(angles)
            print(f"unit0{unit} {side} tip error (px): {err}")
        out[unit] = {a.pose: {"bone_angles": bone}}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
