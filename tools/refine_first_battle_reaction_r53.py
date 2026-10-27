"""Offline paired performance candidate; never installs or alters a world.

Retains the captured 23-second sequence and its event times. Replaces the
nearly static grounded receiver with connected torso/head/limb reactions,
and gives the striker an explicit wind-up and recovery around each contact.
The measured contact and support surfaces are solved after the acting pass.
"""
from pathlib import Path
import argparse
import copy
import json
import zipfile

import numpy as np
from scipy.spatial.transform import Rotation as R

from refine_first_battle_contacts_r53 import (
    Pose, UNIT, MIRROR, sha, ease, mesh_points, transformed, contact_point,
)

HITS = (12.75, 14.15, 16.05)


def bump(t, start, peak, end):
    if t <= start or t >= end:
        return 0.
    return ease((t-start)/(peak-start)) if t < peak else 1-ease((t-peak)/(end-peak))


def multiply(a, b):
    return np.concatenate((
        a[..., 3:]*b[..., :3]+b[..., 3:]*a[..., :3]+np.cross(a[..., :3], b[..., :3]),
        a[..., 3:]*b[..., 3:]-np.sum(a[..., :3]*b[..., :3], axis=-1, keepdims=True),
    ), axis=-1)


class Surface:
    """Same dual-quaternion convention as the installed weighted angel mesh."""
    def __init__(self, mesh):
        part = mesh["parts"]["root"]
        vertices = np.array(part["vertices"]).reshape(-1, mesh["stride"])[:, :3]
        vertices = (vertices+part["pivot"])*[-1, 1, 1]
        self.names = mesh["skin"]["bones"]
        ids = np.array(mesh["skin"]["indices"]).reshape(-1, 4)
        weights = np.array(mesh["skin"]["weights"]).reshape(-1, 4)
        _, unique = np.unique(np.round(np.column_stack((vertices, ids, weights)), 7),
                              axis=0, return_index=True)
        self.vertices, self.ids, self.weights = vertices[unique], ids[unique], weights[unique]

    def skin(self, pose):
        matrices = np.array([pose.matrix(n) for n in self.names])
        q = R.from_matrix(matrices[:, :3, :3]).as_quat()
        d = .5*multiply(np.column_stack((matrices[:, :3, 3], np.zeros(len(q)))), q)
        qs, ds = q[self.ids], d[self.ids]
        sign = np.where(np.sum(qs*qs[:, :1], axis=-1, keepdims=True) < 0, -1, 1)
        q = np.sum(qs*self.weights[..., None]*sign, axis=1)
        d = np.sum(ds*self.weights[..., None]*sign, axis=1)
        norm = np.linalg.norm(q, axis=1, keepdims=True)
        q, d = q/norm, d/norm
        d -= q*np.sum(q*d, axis=1, keepdims=True)
        return R.from_quat(q).apply(self.vertices)+2*multiply(d, q*[-1, -1, -1, 1])[:, :3]


CURVE_BONES = {
    "eye_blocks": "head", "look_blocks": "head",
    "socket_blocks": "torso_upper", "socket_outward_blocks": "torso_upper",
    "socket_up_blocks": "torso_upper", "hand_l_blocks": "hand_l",
    "hand_r_blocks": "hand_r", "foot_l_blocks": "foot_l", "foot_r_blocks": "foot_r",
    "core_blocks": "torso_upper", "waist_blocks": "torso_lower",
    "rib_tip_blocks": "torso_upper", "rib_side_blocks": "torso_upper",
}


def remap_point(old, new, root, value, bone, mirror):
    model = (np.asarray(value)-root)*mirror/UNIT
    bind = np.linalg.solve(old.matrix(bone), np.r_[model, 1])
    return root+(new.matrix(bone)@bind)[:3]*mirror*UNIT


def remap_direction(old, new, value, bone, mirror):
    direction = np.asarray(value)*mirror
    direction = new.matrix(bone)[:3, :3]@old.matrix(bone)[:3, :3].T@direction
    return direction*mirror/np.linalg.norm(direction)


def rotate(pose, bone, xyz):
    pose.setq(bone, pose.q[bone]*R.from_euler("xyz", xyz, degrees=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", type=Path, required=True)
    ap.add_argument("--clip", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    clip = json.loads(args.clip.read_text("utf8"))
    result = copy.deepcopy(clip)
    with zipfile.ZipFile(args.jar) as archive:
        load = lambda p: json.loads(archive.read("assets/projectseele/"+p))
        rigs = {role: {b["name"]: b for b in load("geo/"+name+".geo.json")[
            "minecraft:geometry"][0]["bones"]} for role, name in (("eva", "eva_unit01"), ("angel", "sachiel"))}
        hand = load("hand_rigs/unit01/hand_rig_contract.json")
        eva_mesh = load("mesh/eva_unit01.mesh.json")
        angel_surface = Surface(load("mesh/sachiel.mesh.json"))
    feet = {s: mesh_points(eva_mesh, "foot_"+s) for s in ("l", "r")}
    rows = []
    for i in range(len(clip["eva"]["frames"])):
        t = i/clip["fps"]
        if not 11.78 < t < 16.73:
            continue
        old = {role: Pose(rigs[role], clip[role]["bones"], clip[role]["frames"][i], role == "eva")
               for role in rigs}
        poses = {role: Pose(rigs[role], clip[role]["bones"], clip[role]["frames"][i], role == "eva")
                 for role in rigs}
        roots = {role: np.array(clip[role]["root_blocks"][i]) for role in rigs}
        a, e = poses["angel"], poses["eva"]
        # The receiver reacts after contact; head and distal limbs lag the
        # chest, rather than all bones receiving one synchronized pulse.
        recoil = sum(bump(t, at, at+.105, at+.64) for at in HITS)
        head_lag = sum(bump(t, at+.045, at+.19, at+.72) for at in HITS)
        limbs_lag = sum(bump(t, at+.085, at+.29, at+.68) for at in HITS)
        strain = bump(t, 11.86, 12.22, 12.65)+bump(t, 13.30, 13.63, 14.05)
        strain += bump(t, 14.80, 15.26, 15.90)
        window = ease((t-11.78)/.18)*(1-ease((t-16.5)/.23))
        rotate(a, "torso_lower", [3.5*recoil, 0, -3*strain])
        rotate(a, "torso_upper", [-12*recoil+5*strain, 4*strain, 5*recoil])
        rotate(a, "neck", [5*head_lag, -5*strain, -4*head_lag])
        rotate(a, "head", [7*head_lag, 3*strain, 2*head_lag])
        rotate(a, "arm_l", [-13*limbs_lag, 0, -8*strain])
        rotate(a, "forearm_l", [-17*limbs_lag, 0, 0])
        rotate(a, "arm_r", [-7*limbs_lag, 0, 11*strain])
        rotate(a, "forearm_r", [-12*limbs_lag, 0, 0])
        rotate(a, "leg_l", [6*limbs_lag, 0, -3*strain])
        rotate(a, "shin_l", [-12*limbs_lag, 0, 0])
        rotate(a, "leg_r", [3*limbs_lag, 0, 3*strain])
        # Keep the recorded resting contact plane. No arbitrary world root
        # animation or snapping the whole receiver to a new horizontal place.
        before_low = angel_surface.skin(old["angel"])[:, 1].min()
        after_low = angel_surface.skin(a)[:, 1].min()
        a.setp("root", a.p["root"]+[0, before_low-after_low, 0])
        core_before = np.asarray(clip["angel"]["core_blocks"][i])
        core_after = remap_point(old["angel"], a, roots["angel"], core_before, "torso_upper", np.ones(3))
        core_delta = core_after-core_before
        wind = sum(bump(t, at-.78, at-.19, at) for at in HITS)*window
        follow = sum(bump(t, at, at+.11, at+.46) for at in HITS)*window
        # Hip -> chest -> fist. The left hand remains the support contact;
        # actual knuckles and rigid soles are resolved after the trunk change.
        rotate(e, "torso_lower", [-3*wind+1.4*follow, -3.5*wind, 0])
        rotate(e, "torso_upper", [-10*wind+5*follow, -9*wind+3*follow, 3*wind])
        rotate(e, "neck", [3*wind-2*follow, 4*wind, 0])
        row = {"frame": i, "seconds": t, "windup": wind, "receiver_recoil": recoil,
               "receiver_core_shift": float(np.linalg.norm(core_delta))}
        for side, sign in (("l", -1), ("r", 1)):
            fist = side == "r"
            original_hand = contact_point(old["eva"], hand, side, fist)
            wanted_world = roots["eva"]+original_hand*MIRROR*UNIT+core_delta*window
            if fist:
                wanted_world += np.array([1.5, 3.5, -2.5])*wind
            wanted = (wanted_world-roots["eva"])*MIRROR/UNIT
            rotation = R.from_matrix(old["eva"].matrix("hand_"+side)[:3, :3])
            # The palm offset belongs to the requested world orientation.
            # Computing it before restoring that orientation makes a wrist
            # solution miss the actual knuckles even when it is reachable.
            e.setq("hand_"+side, R.from_matrix(e.parent("hand_"+side)[:3, :3]).inv()*rotation)
            current = contact_point(e, hand, side, fist)
            target = e.point("hand_"+side)+wanted-current
            e.reach("arm_"+side, "forearm_"+side, "hand_"+side, "wrist_"+side,
                    np.array([sign*23.489652, 123.435069, 7.737214]), target, rotation)
            row["contact_"+side+"_error"] = float(np.linalg.norm(contact_point(e, hand, side, fist)-wanted)*UNIT)
            foot = "foot_"+side
            rotation = R.from_matrix(old["eva"].matrix(foot)[:3, :3])
            target = old["eva"].point(foot)
            e.reach("leg_"+side, "shin_"+side, foot, "ankle_"+side,
                    e.P["shin_"+side]+[0, 11.4, 0], target, rotation)
            row["sole_"+side+"_height"] = float(roots["eva"][1]+transformed(e, foot, feet[side])[:, 1].min()*UNIT)
            row["support_"+side+"_error"] = float(np.linalg.norm(e.point(foot)-target)*UNIT)
        for role, pose in poses.items():
            result[role]["frames"][i] = pose.frame(clip[role]["frames"][i], clip[role]["bones"])
            mirror = MIRROR if role == "eva" else np.ones(3)
            for curve, bone in CURVE_BONES.items():
                if curve in clip[role]:
                    if curve in ("socket_outward_blocks", "socket_up_blocks"):
                        value = remap_direction(old[role], pose, clip[role][curve][i], bone, mirror)
                    else:
                        value = remap_point(old[role], pose, roots[role], clip[role][curve][i], bone, mirror)
                    result[role][curve][i] = value.tolist()
        for side in ("l", "r"):
            result["eva"]["hand_"+side+"_blocks"][i] = (
                roots["eva"]+contact_point(e, hand, side, side == "r")*MIRROR*UNIT).tolist()
        rows.append(row)
    result["paired_reaction_r53"] = {
        "source_sha256": sha(args.clip), "jar_sha256": sha(args.jar),
        "method": "Original authored acting over captured prior, shared measured contact and support solve",
        "hit_seconds": list(HITS), "status": "CANDIDATE_REQUIRES_NATIVE_VISUAL_REVIEW",
        "unchanged": ["event timing", "world root paths", "camera", "sequence outside 11.78–16.73 seconds"],
    }
    (args.out/"first_battle_r44.json").write_text(json.dumps(result, separators=(",", ":")), "utf8")
    report = {"source_sha256": sha(args.clip), "candidate_sha256": sha(args.out/"first_battle_r44.json"),
              "samples": rows, "angular_steps": {}}
    for role in rigs:
        report["angular_steps"][role] = {}
        for name in clip[role]["bones"]:
            if name.startswith(("finger_", "dorsal_", "anatomical_")):
                continue
            j = clip[role]["bones"].index(name)
            values = {}
            for label, document in (("before", clip), ("after", result)):
                q = np.array([f["rotation_wxyz"][j] for f in document[role]["frames"]])
                q = R.from_quat(q[:, [1, 2, 3, 0]])
                step = (q[:-1].inv()*q[1:]).magnitude()*180/np.pi
                values[label] = {"max": float(step.max()), "frame": int(step.argmax())}
            report["angular_steps"][role][name] = values
    (args.out/"reaction-report.json").write_text(json.dumps(report, indent=2), "utf8")
    print(json.dumps({
        "changed_frames": len(rows),
        "max_contact_error": max(max(r["contact_l_error"], r["contact_r_error"]) for r in rows),
        "max_support_error": max(max(r["support_l_error"], r["support_r_error"]) for r in rows),
        "lowest_sole": min(min(r["sole_l_height"], r["sole_r_height"]) for r in rows),
        "candidate_sha256": report["candidate_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
