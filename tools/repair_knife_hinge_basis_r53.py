"""Repair the imported knife thigh basis in isolated copies of current profiles.

Keep current upper-body/knife animation, timing, root motion and foot targets.
Use the original Phase-M performance to recover the authored thigh twist, then
solve the existing X-axis knee hinge to the same foot position and orientation.
No world files or in-place runtime profiles are written.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import numpy as np
from scipy.spatial.transform import Rotation as R

ROOT = Path(__file__).resolve().parents[1]
REFLECTION = np.array([-1., 1., 1.])


def unit(v):
    return v / np.linalg.norm(v)


def axes(up, right):
    y = unit(up)
    x = unit(right - y * np.dot(right, y))
    return np.column_stack((x, y, np.cross(x, y)))


def swing(a, b):
    a, b = unit(a), unit(b)
    dot = np.clip(a @ b, -1, 1)
    if dot < -.99999:
        raise ValueError("Unexpected antiparallel knee reach; inspect source frame")
    return R.from_quat(np.r_[np.cross(a, b), 1 + dot])


class Pose:
    def __init__(self, rig, names, frame):
        self.rig = {b["name"]: b for b in rig}
        self.pivot = {n: np.asarray(b["pivot"]) * REFLECTION for n, b in self.rig.items()}
        self.q = {n: R.identity() for n in self.rig}
        self.p = {n: np.zeros(3) for n in self.rig}
        self.cache = {}
        for n, (w, x, y, z) in zip(names, frame["rotation_wxyz"]):
            if n in self.q:
                self.q[n] = R.from_quat([-x, -y, z, w])
        for n, p in frame.get("bone_position_xyz", {}).items():
            if n in self.p:
                self.p[n] = np.asarray(p) * REFLECTION
        self.p["root"] = np.asarray(frame["root_m"]) * 112 * REFLECTION

    def parent(self, n):
        name = self.rig[n].get("parent")
        return self.matrix(name) if name else np.eye(4)

    def matrix(self, n):
        if n not in self.cache:
            m = np.eye(4)
            m[:3, :3] = self.q[n].as_matrix()
            m[:3, 3] = self.pivot[n] + self.p[n] - self.q[n].apply(self.pivot[n])
            self.cache[n] = self.parent(n) @ m
        return self.cache[n]

    def point(self, n):
        return (self.matrix(n) @ np.r_[self.pivot[n], 1])[:3]

    def knee(self, side):
        marker = "r30_knee_socket_" + side
        return self.pivot.get(marker, self.pivot["shin_" + side] + [0, 11.4, 0])


def repair_leg(pose, source, side):
    upper, lower, ankle, foot = (prefix + side for prefix in ("leg_", "shin_", "ankle_", "foot_"))
    goal = pose.point(foot).copy()
    orientation = R.from_matrix(pose.matrix(foot)[:3, :3])
    origin = pose.point(upper).copy()
    joint = pose.knee(side)
    u, v, axis = joint - pose.pivot[upper], pose.pivot[foot] - joint, np.array([-1., 0, 0])
    source_u = source.knee(side) - source.pivot[upper]
    calibration = R.from_matrix(axes(source_u, axis) @ axes(u, axis).T)
    authored = R.from_matrix(source.matrix(upper)[:3, :3]) * calibration

    parallel = axis * (axis @ v)
    a, b, c = u @ (v - parallel), u @ np.cross(axis, v), u @ parallel
    amplitude, neutral = np.hypot(a, b), np.arctan2(b, a)
    la, lb = np.linalg.norm(u), np.linalg.norm(v)
    maximum = np.sqrt(la * la + lb * lb + 2 * (amplitude + c)) * .9999
    minimum = np.sqrt(max(0, la * la + lb * lb + 2 * (a * np.cos(2.62) + b * np.sin(2.62) + c))) + .0001
    direction = unit(goal - origin)
    length = np.clip(np.linalg.norm(goal - origin), minimum, maximum)
    angle = neutral + np.arccos(np.clip(((length * length - la * la - lb * lb) / 2 - c) / amplitude, -1, 1))
    hinge = R.from_rotvec(axis * angle)
    world = swing(authored.apply(u + hinge.apply(v)), direction) * authored
    pose.q[upper] = R.from_matrix(pose.parent(upper)[:3, :3]).inv() * world
    pose.q[lower] = hinge
    pose.q[ankle] = R.identity()
    offset = joint - pose.pivot[lower]
    pose.p[lower] = offset - hinge.apply(offset)
    pose.cache.clear()
    pose.q[foot] = R.from_matrix(pose.parent(foot)[:3, :3]).inv() * orientation
    pose.cache.clear()
    error = np.linalg.norm(pose.point(foot) - goal)
    angular_error = (orientation.inv() * R.from_matrix(pose.matrix(foot)[:3, :3])).magnitude()
    if error > .03 or angular_error > 1e-6:
        raise ValueError(("Foot target changed", side, error, angular_error))
    return float(error)


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--runtime", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise ValueError("Fresh isolated output required")
    args.out.mkdir(parents=True)
    body_path = args.runtime / "eva_body_r44.json"
    body = json.loads(body_path.read_text("utf8"))
    source_path = ROOT / "src/main/resources/assets/projectseele/motion/eva_knife_attacks_phase_m_v1.json"
    source = json.loads(source_path.read_text("utf8"))
    clips = {"r32_knife_forward": "eva_locked_knife_stab_twist_forward",
             "r32_knife_reverse": "eva_short_knife_stab_twist_reverse"}
    rows = []
    changed = {prefix + s for prefix in ("leg_", "shin_", "ankle_", "foot_") for s in ("l", "r")}
    for variant in (0, 1, 2):
        path = args.runtime / f"eva_gameplay_r44_{variant}.json"
        before = json.loads(path.read_text("utf8"))
        output = copy.deepcopy(before)
        for name, source_name in clips.items():
            frames = output["clips"][name]["frames"]
            original_frames = source["clips"][source_name]["frames"]
            if len(frames) != len(original_frames):
                raise ValueError(("Source clock differs", variant, name))
            errors = []
            for index, frame in enumerate(frames):
                pose = Pose(body["rigs"][str(variant)], output["bones"], frame)
                original = Pose(body["rigs"]["1"], source["bones"], original_frames[index])
                for side in ("l", "r"):
                    errors.append(repair_leg(pose, original, side))
                for bone in changed:
                    x, y, z, w = pose.q[bone].as_quat()
                    frame["rotation_wxyz"][output["bones"].index(bone)] = [float(w), float(-x), float(-y), float(z)]
                    if bone.startswith("shin_"):
                        frame.setdefault("bone_position_xyz", {})[bone] = (pose.p[bone] * REFLECTION).tolist()
                old = before["clips"][name]["frames"][index]
                assert all(frame[k] == old[k] for k in old if k not in ("rotation_wxyz", "bone_position_xyz"))
                assert all(frame["rotation_wxyz"][i] == old["rotation_wxyz"][i]
                           for i, bone in enumerate(output["bones"]) if bone not in changed)
                old_positions = old.get("bone_position_xyz", {})
                assert all(frame.get("bone_position_xyz", {}).get(n, [0, 0, 0]) == p
                           for n, p in old_positions.items() if n not in ("shin_l", "shin_r"))
            rows.append(dict(variant=variant, clip=name, frames=len(frames),
                             maximum_foot_error_model_units=max(errors),
                             maximum_foot_error_world_blocks=max(errors) * 5 / 16))
        output["knife_hinge_basis_r53"] = {
            "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "input_profile_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "body_sha256": hashlib.sha256(body_path.read_bytes()).hexdigest(),
            "method": "Authored source X knee hinge, same current root/upper body and foot targets",
            "visual_acceptance": "Pending native review and user acceptance"}
        assert all(output["clips"][n] == clip for n, clip in before["clips"].items() if n not in clips)
        target = args.out / path.name
        target.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", "utf8")
    (args.out / "REPORT.json").write_text(json.dumps(rows, indent=2), "utf8")
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
