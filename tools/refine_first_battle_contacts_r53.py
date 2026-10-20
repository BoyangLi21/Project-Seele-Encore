"""Rebind the existing paired performance to the installed contact surfaces.

Reads a private clip and the exact delivery JAR. Never imports historical
authoring modules with implicit asset directories, and never edits a world.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import zipfile

import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp

UNIT = 5 / 16
MIRROR = np.array([-1., 1., -1.])


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def ease(x):
    x = float(np.clip(x, 0, 1))
    return x*x*x*(10+x*(-15+6*x))


class Pose:
    def __init__(self, rig, names, frame, eva=True):
        self.rig = rig
        self.P = {n: np.array(b["pivot"], float)*[-1, 1, 1] for n, b in rig.items()}
        self.q = {n: R.identity() for n in rig}
        self.p = {n: np.zeros(3) for n in rig}
        self.cache = {}
        for n, (w, x, y, z) in zip(names, frame["rotation_wxyz"]):
            if n in rig:
                self.q[n] = R.from_quat([-x, -y, z, w])
        for n, v in frame.get("bone_position_xyz", {}).items():
            if n in rig:
                self.p[n] = np.array(v)*[-1, 1, 1]
        self.p["root"] = np.array(frame["root_m"])*112*[-1, 1, 1]
        if eva:
            for side, sign in (("l", -1), ("r", 1)):
                self.hinge("shin_"+side, self.P["shin_"+side]+[0, 11.4, 0])
                self.hinge("forearm_"+side, np.array([sign*23.489652, 123.435069, 7.737214]))

    def matrix(self, name):
        if name not in self.cache:
            q = self.q[name].as_matrix()
            m = np.eye(4)
            m[:3, :3] = q
            m[:3, 3] = self.p[name]+self.P[name]-q@self.P[name]
            parent = self.rig[name].get("parent")
            self.cache[name] = self.matrix(parent)@m if parent else m
        return self.cache[name]

    def parent(self, name):
        parent = self.rig[name].get("parent")
        return self.matrix(parent) if parent else np.eye(4)

    def point(self, name, point=None):
        return (self.matrix(name)@np.r_[self.P[name] if point is None else point, 1])[:3]

    def setq(self, name, q):
        self.q[name] = q
        self.cache.clear()

    def setp(self, name, p):
        self.p[name] = np.asarray(p)
        self.cache.clear()

    def hinge(self, name, centre):
        delta = centre-self.P[name]
        self.setp(name, delta-self.q[name].apply(delta))

    def frame(self, original, names):
        result = copy.deepcopy(original)
        result["rotation_wxyz"] = []
        for name in names:
            x, y, z, w = self.q[name].as_quat()
            result["rotation_wxyz"].append([float(w), float(-x), float(-y), float(z)])
        result["root_m"] = (self.p["root"]*[-1, 1, 1]/112).tolist()
        result["bone_position_xyz"] = {
            n: (p*[-1, 1, 1]).tolist() for n, p in self.p.items()
            if n != "root" and n in names and np.linalg.norm(p) > 1e-8
        }
        return result

    def reach(self, upper, lower, end, intermediate, centre, target, orientation):
        """Keep the current elbow/knee side while moving a measured endpoint."""
        origin = self.point(upper)
        u = centre-self.P[upper]
        # Keep the authored wrist/ankle rotation. Flattening it into the
        # forearm/shin introduces a new twist even for an infinitesimal goal.
        v = (np.linalg.inv(self.matrix(lower))@np.r_[self.point(end), 1])[:3]-centre
        a, b = np.linalg.norm(u), np.linalg.norm(v)
        direction = target-origin
        requested = np.linalg.norm(direction)
        direction /= max(requested, 1e-12)
        distance = np.clip(requested, abs(a-b)+1e-5, a+b-1e-5)
        pole = self.point(lower, centre)-origin
        pole -= direction*np.dot(direction, pole)
        if np.linalg.norm(pole) < 1e-6:
            pole = self.matrix(upper)[:3, :3]@np.array([0., 0., -1.])
            pole -= direction*np.dot(direction, pole)
        pole /= np.linalg.norm(pole)
        along = (a*a-b*b+distance*distance)/(2*distance)
        middle = origin+direction*along+pole*np.sqrt(max(0, a*a-along*along))
        bounded = origin+direction*distance
        du, dv = middle-origin, bounded-middle
        def orient(name, rest, desired):
            old = R.from_matrix(self.matrix(name)[:3, :3])
            a = old.apply(rest)
            a /= np.linalg.norm(a)
            b = desired/np.linalg.norm(desired)
            dot = np.clip(a@b, -1, 1)
            if dot < -.999999:
                axis = old.apply([1., 0., 0.])
                axis -= a*(a@axis)
                axis /= np.linalg.norm(axis)
                delta = R.from_rotvec(np.pi*axis)
            else:
                delta = R.from_quat(np.r_[np.cross(a, b), 1+dot])
            world = delta*old
            self.setq(name, R.from_matrix(self.parent(name)[:3, :3]).inv()*world)
        orient(upper, u, du)
        orient(lower, v, dv)
        self.hinge(lower, centre)
        self.setq(end, R.from_matrix(self.parent(end)[:3, :3]).inv()*orientation)
        return float(np.linalg.norm(self.point(end)-target))


def mesh_points(mesh, name):
    part = mesh["parts"][name]
    vertices = np.array(part["vertices"]).reshape(-1, mesh["stride"])[:, :3]
    return np.unique((vertices+part["pivot"])*[-1, 1, 1], axis=0)


def transformed(pose, bone, points):
    m = pose.matrix(bone)
    return points@m[:3, :3].T+m[:3, 3]


def hand_joints(hand):
    for side, spec in hand["hands"].items():
        for digit, data in spec["digits"].items():
            for joint in data["joints"]:
                yield side, digit, joint


def controls(hand, selection, side, digit, joint):
    pose = hand["pose_controls"][selection]
    index = joint["index"]
    if joint["name"] in pose.get("bone_angles", {}):
        value = np.array(pose["bone_angles"][joint["name"]], float)
    elif digit == "thumb":
        value = np.array(pose["thumb"][index], float)
    else:
        value = np.array([pose.get(digit, pose["fingers"])[index], 0., 0.])
        if index == 0:
            value[2] = pose.get("splay", {}).get(digit, 0)
    limits = np.array(joint["anatomical_limits_degrees"])
    return np.clip(value, limits[:, 0], limits[:, 1])


def hand_schedule(seconds, side):
    # The original paired action already owns the wrist trajectory. These are
    # its hand phases, baked into that same clock instead of a gameplay state.
    phases = [(0., "fist"), (.35, "spread"), (5.35, "grab"),
              (8.55, "fist"), (11.45, "support" if side == "l" else "fist"),
              (16.65, "grab"), (18.6, "relaxed")]
    previous = phases[0][1]
    for at, selection in phases[1:]:
        if seconds < at:
            return previous, previous, 0.
        if seconds < at+.28:
            return previous, selection, ease((seconds-at)/.28)
        previous = selection
    return previous, previous, 0.


def pose_hands(pose, hand, seconds):
    for side, digit, joint in hand_joints(hand):
        first, last, w = hand_schedule(seconds, side)
        a = controls(hand, first, side, digit, joint)
        b = controls(hand, last, side, digit, joint)
        flex, twist, splay = a*(1-w)+b*w
        sign = 1 if side == "l" else -1
        q = R.from_quat(joint["neutral_local_quaternion_xyzw"])
        q *= R.from_euler("ZYX", [sign*splay, sign*twist, -flex], degrees=True)
        pose.setq(joint["name"], q)
        pose.setp(joint["name"], np.zeros(3))


def contact_point(pose, hand, side, fist):
    if not fist:
        bind = np.array(hand["weapon_grip_frames"][side]["palm_bind"])*16
        return pose.point("hand_"+side, bind)
    joint = hand["hands"][side]["digits"]["middle"]["joints"][1]
    inverse = np.array(joint["inverse_bind_column_major"]).reshape(4, 4).T
    # The contract is in blocks; the authoring FK is in model units.
    inverse[:3, 3] *= 16
    bind = np.r_[np.array(joint["head_bind"])*16, 1]
    return (pose.matrix(joint["name"])@inverse@bind)[:3]


def hand_weight(t, side):
    field = ease((t-.35)/.8)*(1-ease((t-5.1)/.4))
    grip = ease((t-5.5)/.7)*(1-ease((t-8.1)/.4)) if side == "r" else 0
    assault = ease((t-11.68)/.42)*(1-ease((t-16.55)/.35))
    return max(field, grip, assault)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", type=Path, required=True)
    ap.add_argument("--clip", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bake", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    clip = json.loads(args.clip.read_text(encoding="utf-8"))
    with zipfile.ZipFile(args.jar) as archive:
        load = lambda p: json.loads(archive.read("assets/projectseele/"+p))
        geo = load("geo/eva_unit01.geo.json")
        rig = {b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]}
        mesh = load("mesh/eva_unit01.mesh.json")
        hand = load("hand_rigs/unit01/hand_rig_contract.json")
    feet = {s: mesh_points(mesh, "foot_"+s) for s in ("l", "r")}
    palms = {s: np.array(hand["weapon_grip_frames"][s]["palm_bind"])*16 for s in ("l", "r")}
    role = clip["eva"]
    rows = []
    for i, frame in enumerate(role["frames"]):
        p = Pose(rig, role["bones"], frame)
        root = np.array(role["root_blocks"][i])
        row = {"frame": i, "seconds": i/clip["fps"]}
        for side in ("l", "r"):
            target = np.array(role["hand_"+side+"_blocks"][i])
            actual = root+p.point("hand_"+side, palms[side])*MIRROR*UNIT
            row["palm_"+side+"_error"] = float(np.linalg.norm(actual-target))
            sole = root[1]+transformed(p, "foot_"+side, feet[side])[:, 1].min()*UNIT
            row["sole_"+side+"_height"] = float(sole)
        rows.append(row)
    identity = {"jar_sha256": sha(args.jar), "clip_sha256": sha(args.clip)}
    (args.out/"contact_before.json").write_text(json.dumps({**identity, "samples": rows}, indent=2), encoding="utf-8")
    for key in ("palm_l_error", "palm_r_error", "sole_l_height", "sole_r_height"):
        values = [r[key] for r in rows]
        print(key, "min/median/p95/max", np.percentile(values, [0, 50, 95, 100]).tolist())
    if not args.bake:
        return
    result = copy.deepcopy(clip)
    names = [n for n in role["bones"] if n in rig]
    names += [j["name"] for _, _, j in hand_joints(hand) if j["name"] not in names]
    result["eva"]["bones"] = names
    after = []
    for i, frame in enumerate(role["frames"]):
        t = i/clip["fps"]
        p = Pose(rig, role["bones"], frame)
        pose_hands(p, hand, t)
        root = np.array(role["root_blocks"][i])
        row = {"frame": i, "seconds": t}
        for side, sign in (("l", -1), ("r", 1)):
            weight = hand_weight(t, side)
            fist = side == "r" and 11.4 <= t < 16.65
            current = contact_point(p, hand, side, fist)
            wanted = (np.array(role["hand_"+side+"_blocks"][i])-root)*MIRROR/UNIT
            if weight > 1e-8:
                orientation = R.from_matrix(p.matrix("hand_"+side)[:3, :3])
                goal = p.point("hand_"+side)+(wanted-current)*weight
                centre = np.array([sign*23.489652, 123.435069, 7.737214])
                p.reach("arm_"+side, "forearm_"+side, "hand_"+side, "wrist_"+side,
                        centre, goal, orientation)
            actual = contact_point(p, hand, side, fist)
            row["hand_"+side+"_weight"] = weight
            row["hand_"+side+"_error"] = float(np.linalg.norm(actual-wanted)*UNIT)
            result["eva"]["hand_"+side+"_blocks"][i] = (root+actual*MIRROR*UNIT).tolist()

        # A flat scene floor is part of the existing 23-second choreography.
        # Preserve all airborne and planted positive-height samples.
        for side in ("l", "r"):
            foot = "foot_"+side
            before_point = p.point(foot)
            low = root[1]+transformed(p, foot, feet[side])[:, 1].min()*UNIT
            if low < 0:
                orientation = R.from_matrix(p.matrix(foot)[:3, :3])
                goal = p.point(foot)+[0, -low/UNIT, 0]
                p.reach("leg_"+side, "shin_"+side, foot, "ankle_"+side,
                        p.P["shin_"+side]+[0, 11.4, 0], goal, orientation)
            low = root[1]+transformed(p, foot, feet[side])[:, 1].min()*UNIT
            row["sole_"+side+"_height"] = float(low)
            result["eva"]["foot_"+side+"_blocks"][i] = (
                np.array(role["foot_"+side+"_blocks"][i])+(p.point(foot)-before_point)*MIRROR*UNIT
            ).tolist()
        result["eva"]["frames"][i] = p.frame(frame, names)
        after.append(row)
    result["contact_rebind_r53"] = {
        **identity, "hand_contract_sha256": hashlib.sha256(json.dumps(hand, sort_keys=True).encode()).hexdigest(),
        "method": "Current measured palm/knuckle and rigid sole FK; shared baked contact clock",
        "preserved": ["duration", "world roots", "angel performance", "camera", "event timing"],
        "units": "world blocks", "hand_owner": "first_battle_clip",
    }
    output = args.out/"first_battle_r44.json"
    output.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    (args.out/"contact_after.json").write_text(json.dumps({
        **identity, "candidate_sha256": sha(output), "samples": after}, indent=2), encoding="utf-8")
    for side in ("l", "r"):
        full = [r["hand_"+side+"_error"] for r in after if r["hand_"+side+"_weight"] > .99999]
        print("corrected", side, "full contact median/max", np.percentile(full, [50, 100]).tolist(),
              "sole_min", min(r["sole_"+side+"_height"] for r in after))
    rotations = {}
    for name in ("arm_l", "arm_r", "forearm_l", "forearm_r", "leg_l", "leg_r", "shin_l", "shin_r"):
        rotations[name] = {}
        for label, data in (("before", role), ("after", result["eva"])):
            index = data["bones"].index(name)
            q = np.array([f["rotation_wxyz"][index] for f in data["frames"]])
            spin = R.from_quat(q[:, [1, 2, 3, 0]])
            step = (spin[:-1].inv()*spin[1:]).magnitude()*180/np.pi
            rotations[name][label] = {"p95": float(np.percentile(step, 95)), "max": float(step.max()),
                                      "max_frame": int(step.argmax())}
    (args.out/"angular_continuity.json").write_text(json.dumps(rotations, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
