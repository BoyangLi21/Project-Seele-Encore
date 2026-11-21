#!/usr/bin/env python3
"""Directly connect normalized human landmarks to the active Tiger EVA rig."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


BONES = (
    "root", "torso_lower", "torso_upper", "aim_pitch", "neck", "head",
    "clavicle_l", "arm_l", "forearm_l", "wrist_l", "hand_l",
    "clavicle_r", "arm_r", "forearm_r", "wrist_r", "hand_r",
    "leg_l", "shin_l", "ankle_l", "foot_l",
    "leg_r", "shin_r", "ankle_r", "foot_r",
)
PARENT = {
    "root": None,
    "torso_lower": "root",
    "torso_upper": "torso_lower",
    "aim_pitch": "torso_upper",
    "neck": "torso_upper",
    "head": "neck",
    "clavicle_l": "aim_pitch",
    "arm_l": "clavicle_l",
    "forearm_l": "arm_l",
    "wrist_l": "forearm_l",
    "hand_l": "wrist_l",
    "clavicle_r": "aim_pitch",
    "arm_r": "clavicle_r",
    "forearm_r": "arm_r",
    "wrist_r": "forearm_r",
    "hand_r": "wrist_r",
    "leg_l": "torso_lower",
    "shin_l": "leg_l",
    "ankle_l": "shin_l",
    "foot_l": "ankle_l",
    "leg_r": "torso_lower",
    "shin_r": "leg_r",
    "ankle_r": "shin_r",
    "foot_r": "ankle_r",
}

# Source landmarks: +X forward, +Y left, +Z up.
# Tiger runtime: +X right, +Y up, -Z forward.
SOURCE_TO_RUNTIME = np.asarray((
    (0.0, -1.0, 0.0),
    (0.0, 0.0, 1.0),
    (-1.0, 0.0, 0.0),
), dtype=np.float64)
TARGET_LEFT = np.asarray((-1.0, 0.0, 0.0))
TARGET_UP = np.asarray((0.0, 1.0, 0.0))
TARGET_FRONT = np.asarray((0.0, 0.0, -1.0))
MODEL_UNITS_PER_METRE = 112.0
TIGER_THUMB_FIST_AUTHORED = {
    "l": [0.2390750, 0.3781518, 0.8934102, -0.0407756],
    "r": [0.2393413, 0.3768066, -0.8939208, 0.0404731],
}


def normalize(value):
    value = np.asarray(value, dtype=np.float64)
    length = float(np.linalg.norm(value))
    if length < 1.0e-8:
        raise RuntimeError("zero-length anatomical direction")
    return value / length


def frame(primary, secondary):
    first = normalize(primary)
    second = np.asarray(secondary, dtype=np.float64)
    second -= first * float(np.dot(first, second))
    if np.linalg.norm(second) < 1.0e-8:
        fallback = TARGET_FRONT.copy()
        fallback -= first * float(np.dot(first, fallback))
        if np.linalg.norm(fallback) < 1.0e-8:
            fallback = TARGET_LEFT.copy()
            fallback -= first * float(np.dot(first, fallback))
        second = fallback
    second = normalize(second)
    third = normalize(np.cross(first, second))
    second = normalize(np.cross(third, first))
    return np.column_stack((first, second, third))


def map_frame(bind_primary, bind_secondary, desired_primary,
              desired_secondary):
    return frame(desired_primary, desired_secondary) @ frame(
        bind_primary, bind_secondary).T


def authored_wxyz(runtime_matrix):
    runtime_euler = Rotation.from_matrix(runtime_matrix).as_euler("xyz")
    authored = Rotation.from_euler("xyz", (
        -runtime_euler[0], -runtime_euler[1], runtime_euler[2]
    )).as_quat()
    return [round(float(authored[3]), 7), round(float(authored[0]), 7),
            round(float(authored[1]), 7), round(float(authored[2]), 7)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--landmarks", required=True, type=Path)
    parser.add_argument("--geo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--clip", default="ordinary_attack_right")
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--license", required=True)
    parser.add_argument("--hand-pose", choices=("neutral", "fist"),
                        default="neutral")
    args = parser.parse_args()

    source = np.load(args.landmarks)
    names = [str(value) for value in source["landmark_names"]]
    index = {name: offset for offset, name in enumerate(names)}
    positions = np.asarray(source["positions_H"], dtype=np.float64)
    contacts = np.asarray(source["foot_contact"], dtype=np.bool_)
    fps = float(source["fps"][0])
    required = {
        "pelvis", "abdomen", "thorax", "neck", "head",
        "clavicle_l", "shoulder_l", "elbow_l", "wrist_l", "hand_l",
        "clavicle_r", "shoulder_r", "elbow_r", "wrist_r", "hand_r",
        "hip_l", "knee_l", "ankle_l", "toe_l",
        "hip_r", "knee_r", "ankle_r", "toe_r",
    }
    missing = required - set(index)
    if missing:
        raise RuntimeError("missing source landmarks: "
                           + ", ".join(sorted(missing)))

    geometry = json.loads(args.geo.read_text(
        encoding="utf-8"))["minecraft:geometry"][0]["bones"]
    pivot = {}
    for row in geometry:
        raw = np.asarray(row.get("pivot", (0.0, 0.0, 0.0)),
                         dtype=np.float64)
        pivot[row["name"]] = np.asarray((-raw[0], raw[1], raw[2]))
    missing_target = set(BONES) - set(pivot)
    if missing_target:
        raise RuntimeError("active Tiger rig is missing bones: "
                           + ", ".join(sorted(missing_target)))

    finger_bones = []
    if args.hand_pose == "fist":
        finger_bones = [
            row["name"] for row in geometry
            if row["name"].startswith("finger_")
            and "_axis_" not in row["name"]
            and not row["name"].startswith("finger_thumb_tip_")
        ]
    output_bones = list(BONES) + finger_bones

    def fist_rotation(bone):
        if "thumb" in bone:
            # The thumb is the retained asymmetric Tiger source island, not
            # one of the canonical-Z long-finger chains. This opposition pose
            # maps its distal surface onto the index/middle stack while its
            # measured palm-seam pivot keeps the original mesh continuous.
            return TIGER_THUMB_FIST_AUTHORED[bone[-1]]
        elif "_distal_" in bone:
            angle = 58.0
        elif "_tip_" in bone:
            angle = 78.0
        else:
            angle = 92.0
        return authored_wxyz(
            Rotation.from_euler("z", np.radians(angle)).as_matrix()
        )
    finger_pose = {bone: fist_rotation(bone) for bone in finger_bones}

    target_height = max(point[1] for point in pivot.values()) - min(
        point[1] for point in pivot.values())
    source_origin = positions[0, index["pelvis"]].copy()
    output_frames = []
    maximum_step = 0.0
    maximum_step_location = None
    minimum_segment_alignment = 1.0
    previous_local = None
    # Seed twist branches from the target bind orientation. The raw landmark
    # stream has positions but no axial-roll channel; choosing the nearest
    # bind-equivalent branch at frame zero prevents a 180-degree first-frame
    # twist without altering any source joint direction.
    previous_global = {bone: np.identity(3) for bone in BONES}
    twist_branch = {}

    for frame_index, row in enumerate(positions):
        mapped = {
            name: SOURCE_TO_RUNTIME @ row[offset]
            for name, offset in index.items()
        }

        lower_up = mapped["abdomen"] - mapped["pelvis"]
        lower_left = mapped["hip_l"] - mapped["hip_r"]
        upper_up = mapped["neck"] - mapped["abdomen"]
        upper_left = mapped["shoulder_l"] - mapped["shoulder_r"]
        neck_up = mapped["head"] - mapped["neck"]

        def continuous_map(bone, bind_primary, bind_secondary,
                           desired_primary, desired_secondary):
            candidates = {
                sign: map_frame(
                    bind_primary, bind_secondary, desired_primary,
                    np.asarray(desired_secondary) * sign
                )
                for sign in (1.0, -1.0)
            }
            if bone not in twist_branch:
                twist_branch[bone] = min(
                    candidates,
                    key=lambda sign: float((
                        Rotation.from_matrix(previous_global[bone]).inv()
                        * Rotation.from_matrix(candidates[sign])
                    ).magnitude()),
                )
            return candidates[twist_branch[bone]]

        desired_global = {
            "root": np.identity(3),
            "torso_lower": continuous_map("torso_lower",
                pivot["torso_upper"] - pivot["torso_lower"], TARGET_LEFT,
                lower_up, lower_left),
            "torso_upper": continuous_map("torso_upper",
                pivot["neck"] - pivot["torso_upper"], TARGET_LEFT,
                upper_up, upper_left),
        }
        desired_global["aim_pitch"] = desired_global["torso_upper"]
        desired_global["neck"] = continuous_map("neck",
            TARGET_UP, TARGET_LEFT, neck_up, upper_left)
        desired_global["head"] = desired_global["neck"]

        for side in ("l", "r"):
            clavicle = f"clavicle_{side}"
            arm = f"arm_{side}"
            forearm = f"forearm_{side}"
            wrist = f"wrist_{side}"
            hand = f"hand_{side}"
            shoulder_direction = (
                mapped[f"shoulder_{side}"] - mapped[clavicle]
            )
            upper_direction = (
                mapped[f"elbow_{side}"] - mapped[f"shoulder_{side}"]
            )
            lower_direction = (
                mapped[f"wrist_{side}"] - mapped[f"elbow_{side}"]
            )
            hand_direction = (
                mapped[f"hand_{side}"] - mapped[f"wrist_{side}"]
            )
            desired_global[clavicle] = continuous_map(clavicle,
                pivot[arm] - pivot[clavicle], TARGET_FRONT,
                shoulder_direction, upper_up)
            desired_global[arm] = continuous_map(arm,
                pivot[forearm] - pivot[arm], TARGET_FRONT,
                upper_direction, lower_direction)
            desired_global[forearm] = continuous_map(forearm,
                pivot[wrist] - pivot[forearm], TARGET_FRONT,
                lower_direction, upper_up)
            desired_global[wrist] = desired_global[forearm]
            desired_global[hand] = desired_global[forearm]

            leg = f"leg_{side}"
            shin = f"shin_{side}"
            ankle = f"ankle_{side}"
            foot = f"foot_{side}"
            upper_leg = mapped[f"knee_{side}"] - mapped[f"hip_{side}"]
            lower_leg = mapped[f"ankle_{side}"] - mapped[f"knee_{side}"]
            foot_forward = mapped[f"toe_{side}"] - mapped[f"ankle_{side}"]
            desired_global[leg] = continuous_map(leg,
                pivot[shin] - pivot[leg], TARGET_FRONT,
                upper_leg, lower_leg)
            desired_global[shin] = continuous_map(shin,
                pivot[ankle] - pivot[shin], TARGET_FRONT,
                lower_leg, foot_forward)
            desired_global[ankle] = desired_global[shin]
            desired_global[foot] = continuous_map(foot,
                TARGET_FRONT, TARGET_UP, foot_forward, TARGET_UP)

        alignment_checks = [
            ("torso_lower", pivot["torso_upper"] - pivot["torso_lower"],
             lower_up),
            ("torso_upper", pivot["neck"] - pivot["torso_upper"],
             upper_up),
        ]
        for side in ("l", "r"):
            alignment_checks.extend((
                (f"clavicle_{side}",
                 pivot[f"arm_{side}"] - pivot[f"clavicle_{side}"],
                 mapped[f"shoulder_{side}"] - mapped[f"clavicle_{side}"]),
                (f"arm_{side}",
                 pivot[f"forearm_{side}"] - pivot[f"arm_{side}"],
                 mapped[f"elbow_{side}"] - mapped[f"shoulder_{side}"]),
                (f"forearm_{side}",
                 pivot[f"wrist_{side}"] - pivot[f"forearm_{side}"],
                 mapped[f"wrist_{side}"] - mapped[f"elbow_{side}"]),
                (f"leg_{side}",
                 pivot[f"shin_{side}"] - pivot[f"leg_{side}"],
                 mapped[f"knee_{side}"] - mapped[f"hip_{side}"]),
                (f"shin_{side}",
                 pivot[f"ankle_{side}"] - pivot[f"shin_{side}"],
                 mapped[f"ankle_{side}"] - mapped[f"knee_{side}"]),
                (f"foot_{side}", TARGET_FRONT,
                 mapped[f"toe_{side}"] - mapped[f"ankle_{side}"]),
            ))
        for bone, bind_direction, source_direction in alignment_checks:
            predicted = normalize(desired_global[bone] @ bind_direction)
            wanted = normalize(source_direction)
            minimum_segment_alignment = min(
                minimum_segment_alignment,
                float(np.dot(predicted, wanted)),
            )

        local = {}
        for bone in BONES:
            parent = PARENT[bone]
            local[bone] = (desired_global[bone] if parent is None else
                           desired_global[parent].T @ desired_global[bone])

        if previous_local is not None:
            for bone in BONES:
                step = float((
                    Rotation.from_matrix(previous_local[bone]).inv()
                    * Rotation.from_matrix(local[bone])
                ).magnitude())
                if step > maximum_step:
                    maximum_step = step
                    maximum_step_location = {
                        "frame": frame_index,
                        "bone": bone,
                    }
        previous_local = {bone: local[bone].copy() for bone in BONES}
        previous_global = {
            bone: desired_global[bone].copy() for bone in BONES
        }

        source_delta = row[index["pelvis"]] - source_origin
        runtime_pixels = SOURCE_TO_RUNTIME @ source_delta * target_height
        root_m = np.asarray((
            -runtime_pixels[0], runtime_pixels[1], runtime_pixels[2]
        )) / MODEL_UNITS_PER_METRE
        output_frames.append({
            "root_m": [round(float(value), 7) for value in root_m],
            "rotation_wxyz": (
                [authored_wxyz(local[bone]) for bone in BONES]
                + [finger_pose[bone] for bone in finger_bones]
            ),
            "foot_contact": [bool(value) for value in contacts[frame_index]],
        })

    payload = {
        "schema": 2,
        "coordinate_system": (
            "raw_human_plus_x_forward_to_tiger_runtime_negative_z_front"
        ),
        "quaternion_order": "wxyz",
        "sample_rate": fps,
        "preview_only": True,
        "authority": "direct_raw_human_skeleton_retarget_review_only",
        "sources": [{
            "name": args.source_name,
            "url": args.source_url,
            "license": args.license,
            "modifications": [
                "uniform anatomical basis conversion",
                "direct source-to-target segment orientation",
                "target limb-length substitution",
            ],
        }] + ([{
            "name": "DFKI Hand Motion Embodiment grasp reference",
            "url": "https://github.com/dfki-ric/hand_embodiment",
            "license": "CC BY 4.0",
            "modifications": [
                "static anatomical fist fitted to existing Tiger digits"
            ],
        }] if args.hand_pose == "fist" else []),
        "bones": output_bones,
        "clips": {
            args.clip: {
                "duration_seconds": round((len(output_frames) - 1) / fps, 7),
                "loop": False,
                "role": "direct_raw_human_capture_review_only",
                "frames": output_frames,
            }
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ) + "\n", encoding="utf-8")
    report = {
        "schema": 1,
        "source": str(args.landmarks.resolve()),
        "target_geo": str(args.geo.resolve()),
        "frames": len(output_frames),
        "fps": fps,
        "bones": len(output_bones),
        "hand_pose": args.hand_pose,
        "finger_bones": len(finger_bones),
        "source_to_runtime_determinant": float(np.linalg.det(
            SOURCE_TO_RUNTIME)),
        "maximum_local_rotation_step_degrees": float(np.degrees(
            maximum_step)),
        "maximum_local_rotation_step_location": maximum_step_location,
        "minimum_segment_alignment_dot": minimum_segment_alignment,
        "manual_pose_keyframes": 0,
        "ik_or_physics_repair": False,
        "status": "direct_raw_capture_human_review_required",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(
        report, ensure_ascii=False, indent=2
    ) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
