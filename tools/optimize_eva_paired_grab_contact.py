#!/usr/bin/env python3
"""Jointly close a paired EVA hand/limb contact without moving either root."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix


UPPER_NAMES = [
    "lumbar_roll", "lumbar_pitch", "lumbar_yaw",
    "thoracic_roll", "thoracic_pitch", "thoracic_yaw",
    "neck_roll", "neck_pitch", "neck_yaw",
    "clavicle_l_protract", "clavicle_l_elevate",
    "shoulder_l_abduct", "shoulder_l_flex", "shoulder_l_twist",
    "elbow_l", "forearm_twist_l", "wrist_l_deviation", "wrist_l_flex",
    "clavicle_r_protract", "clavicle_r_elevate",
    "shoulder_r_abduct", "shoulder_r_flex", "shoulder_r_twist",
    "elbow_r", "forearm_twist_r", "wrist_r_deviation", "wrist_r_flex",
]

TARGET_OBJECTS = {
    "abdomen": ("body", "abdomen"), "thorax": ("body", "thorax"),
    "neck": ("body", "neck"), "head": ("body", "head"),
    "shoulder_l": ("body", "upper_arm_l"),
    "elbow_l": ("body", "elbow_link_l"),
    "wrist_l": ("body", "wrist_link_l"),
    "hand_l": ("geom", "knuckle_l"),
    "shoulder_r": ("body", "upper_arm_r"),
    "elbow_r": ("body", "elbow_link_r"),
    "wrist_r": ("body", "wrist_link_r"),
    "hand_r": ("geom", "knuckle_r"),
    "hip_l": ("body", "thigh_l"), "knee_l": ("body", "shin_l"),
    "ankle_l": ("body", "ankle_link_l"), "toe_l": ("body", "toe_l"),
    "hip_r": ("body", "thigh_r"), "knee_r": ("body", "shin_r"),
    "ankle_r": ("body", "ankle_link_r"), "toe_r": ("body", "toe_r"),
}


def metadata(model_path: Path):
    root = ET.parse(model_path).getroot()
    custom = root.find("custom")
    names = next(
        item.attrib["data"].split() for item in custom.findall("text")
        if item.attrib["name"] == "tangent_joint_names"
    )
    numeric = {
        item.attrib["name"]: np.asarray(
            [float(value) for value in item.attrib["data"].split()],
            dtype=np.float64,
        )
        for item in custom.findall("numeric")
    }
    return names, numeric["tangent_joint_lower_rad"], numeric[
        "tangent_joint_upper_rad"
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--actor-a", required=True, type=Path)
    parser.add_argument("--actor-b", required=True, type=Path)
    parser.add_argument("--output-a", required=True, type=Path)
    parser.add_argument("--output-b", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--target-distance-H", type=float, default=0.035)
    parser.add_argument("--contact-weight", type=float, default=28.0)
    parser.add_argument("--pose-weight", type=float, default=0.8)
    parser.add_argument("--marker-weight", type=float, default=2.0)
    parser.add_argument("--delta-velocity-weight", type=float, default=5.0)
    parser.add_argument("--delta-acceleration-weight", type=float, default=8.0)
    parser.add_argument("--max-nfev", type=int, default=32)
    args = parser.parse_args()

    model = mujoco.MjModel.from_xml_path(str(args.model.resolve()))
    data = [mujoco.MjData(model), mujoco.MjData(model)]
    states = [np.load(args.actor_a), np.load(args.actor_b)]
    frame_count = len(states[0]["qpos"])
    if frame_count != len(states[1]["qpos"]):
        raise RuntimeError("actor frame counts differ")
    frames_a = np.asarray(states[0]["source_frames"], dtype=np.float64)
    frames_b = np.asarray(states[1]["source_frames"], dtype=np.float64)
    if not np.allclose(frames_a, frames_b, atol=1.0e-4):
        raise RuntimeError("actor source timelines differ")
    tangent_names, lower, upper = metadata(args.model)
    for state in states:
        if tangent_names != [str(value) for value in state["tangent_names"]]:
            raise RuntimeError("tangent contract mismatch")
    upper_indices = [tangent_names.index(name) for name in UPPER_NAMES]
    upper_count = len(upper_indices)
    frame_width = upper_count * 2
    tangent_source = [
        np.asarray(state["tangent"], dtype=np.float64) for state in states
    ]
    qpos_source = [
        np.asarray(state["qpos"], dtype=np.float64) for state in states
    ]
    target_names = [str(value) for value in states[0]["target_landmark_names"]]
    if target_names != [str(value) for value in states[1]["target_landmark_names"]]:
        raise RuntimeError("landmark contract mismatch")
    desired_source = [
        np.asarray(state["desired_positions"], dtype=np.float64)
        for state in states
    ]
    height = 3.466729315

    joint_groups = {}
    for tangent_index, name in enumerate(tangent_names):
        actuator_id = model.actuator(f"a_{name}").id
        joint_id = int(model.actuator_trnid[actuator_id, 0])
        joint_groups.setdefault(joint_id, []).append({
            "index": tangent_index,
            "axis": np.asarray(model.actuator_gear[actuator_id, :3],
                               dtype=np.float64).copy(),
        })

    def set_tangent(actor: int, value: np.ndarray) -> None:
        actor_data = data[actor]
        for joint_id, specs in joint_groups.items():
            address = int(model.jnt_qposadr[joint_id])
            if int(model.jnt_type[joint_id]) == mujoco.mjtJoint.mjJNT_BALL:
                vector = sum(
                    (spec["axis"] * value[spec["index"]] for spec in specs),
                    np.zeros(3, dtype=np.float64),
                )
                angle = float(np.linalg.norm(vector))
                if angle < 1.0e-10:
                    actor_data.qpos[address:address + 4] = (
                        1.0, 0.0, 0.0, 0.0
                    )
                else:
                    axis = vector / angle
                    actor_data.qpos[address:address + 4] = np.concatenate((
                        [math.cos(angle * 0.5)],
                        axis * math.sin(angle * 0.5),
                    ))
            else:
                actor_data.qpos[address] = value[specs[0]["index"]]

    objects = []
    for name in target_names:
        object_type, object_name = TARGET_OBJECTS[name]
        object_id = mujoco.mj_name2id(
            model,
            (mujoco.mjtObj.mjOBJ_BODY if object_type == "body"
             else mujoco.mjtObj.mjOBJ_GEOM), object_name,
        )
        objects.append((object_type, object_id))

    def apply(actor: int, frame: int, upper_value: np.ndarray):
        full = tangent_source[actor][frame].copy()
        full[upper_indices] = upper_value
        actor_data = data[actor]
        actor_data.qpos[:] = qpos_source[actor][frame]
        set_tangent(actor, full)
        mujoco.mj_forward(model, actor_data)
        actual = np.stack([
            (actor_data.xpos[object_id] if object_type == "body"
             else actor_data.geom_xpos[object_id]).copy()
            for object_type, object_id in objects
        ])
        return full, actor_data.qpos.copy(), actual

    hand_index = target_names.index("hand_r")
    elbow_index = target_names.index("elbow_l")
    initial_actual = [[], []]
    for frame in range(frame_count):
        for actor in range(2):
            _, _, actual = apply(
                actor, frame, tangent_source[actor][frame, upper_indices]
            )
            initial_actual[actor].append(actual)
    initial_actual = [np.asarray(value) for value in initial_actual]
    initial_vector = (
        initial_actual[1][0, elbow_index]
        - initial_actual[0][0, hand_index]
    )
    final_vector = (
        initial_actual[1][-1, elbow_index]
        - initial_actual[0][-1, hand_index]
    )
    final_direction = final_vector / max(np.linalg.norm(final_vector), 1.0e-8)
    target_final_vector = final_direction * args.target_distance_H * height
    target_vectors = []
    for frame in range(frame_count):
        phase = frame / max(1, frame_count - 1)
        smooth = phase * phase * (3.0 - 2.0 * phase)
        target_vectors.append(
            initial_vector * (1.0 - smooth) + target_final_vector * smooth
        )
    target_vectors = np.asarray(target_vectors, dtype=np.float64)

    initial = np.zeros((frame_count, 2, upper_count), dtype=np.float64)
    for actor in range(2):
        initial[:, actor] = tangent_source[actor][:, upper_indices]
    x0 = initial.reshape(frame_count, frame_width).ravel()
    lower_frame = np.concatenate((lower[upper_indices], lower[upper_indices]))
    upper_frame = np.concatenate((upper[upper_indices], upper[upper_indices]))
    bounds = (
        np.tile(lower_frame, frame_count),
        np.tile(upper_frame, frame_count),
    )
    dependencies = []

    marker_names = [
        "head", "elbow_l", "wrist_l", "hand_l",
        "elbow_r", "wrist_r", "hand_r",
    ]

    def residual(flat: np.ndarray, record: bool = False):
        values = flat.reshape(frame_count, 2, upper_count)
        rows = []

        def add(array, frames):
            flattened = np.asarray(array, dtype=np.float64).ravel()
            rows.extend(flattened)
            if record:
                dependencies.extend([tuple(frames)] * len(flattened))

        for frame in range(frame_count):
            actual = []
            for actor in range(2):
                _, _, actor_actual = apply(actor, frame, values[frame, actor])
                actual.append(actor_actual)
                add(args.pose_weight * (
                    values[frame, actor] - initial[frame, actor]
                ), (frame,))
                for marker_name in marker_names:
                    index = target_names.index(marker_name)
                    add(args.marker_weight * (
                        actor_actual[index]
                        - desired_source[actor][frame, index]
                    ) / height, (frame,))
            contact_vector = actual[1][elbow_index] - actual[0][hand_index]
            add(args.contact_weight * (
                contact_vector - target_vectors[frame]
            ) / height, (frame,))
            if frame > 0:
                correction_velocity = (
                    values[frame] - initial[frame]
                    - values[frame - 1] + initial[frame - 1]
                )
                add(args.delta_velocity_weight * correction_velocity,
                    (frame - 1, frame))
            if frame > 1:
                correction_acceleration = (
                    values[frame] - initial[frame]
                    - 2.0 * (values[frame - 1] - initial[frame - 1])
                    + values[frame - 2] - initial[frame - 2]
                )
                add(args.delta_acceleration_weight * correction_acceleration,
                    (frame - 2, frame - 1, frame))
        return np.asarray(rows, dtype=np.float64)

    residual(x0, record=True)
    sparsity = lil_matrix((len(dependencies), len(x0)), dtype=np.int8)
    for row, frames in enumerate(dependencies):
        for frame in frames:
            first = frame * frame_width
            sparsity[row, first:first + frame_width] = 1
    result = least_squares(
        residual, x0, bounds=bounds, jac_sparsity=sparsity.tocsr(),
        method="trf", max_nfev=args.max_nfev, verbose=1,
        ftol=1.0e-6, xtol=1.0e-6, gtol=1.0e-6,
    )
    solved = result.x.reshape(frame_count, 2, upper_count)
    outputs = []
    final_distances = []
    for actor in range(2):
        tangent = tangent_source[actor].copy()
        tangent[:, upper_indices] = solved[:, actor]
        qpos = []
        actual = []
        for frame in range(frame_count):
            _, qpos_row, actual_row = apply(actor, frame, solved[frame, actor])
            qpos.append(qpos_row)
            actual.append(actual_row)
        qpos = np.asarray(qpos, dtype=np.float64)
        actual = np.asarray(actual, dtype=np.float64)
        qvel = np.zeros((frame_count, model.nv), dtype=np.float64)
        dt = float(states[actor]["timestep"][0])
        for frame in range(frame_count):
            before = max(0, frame - 1)
            after = min(frame_count - 1, frame + 1)
            interval = max(dt, (after - before) * dt)
            mujoco.mj_differentiatePos(
                model, qvel[frame], interval, qpos[before], qpos[after]
            )
        fields = {key: states[actor][key] for key in states[actor].files}
        fields.update({
            "tangent": tangent, "qpos": qpos, "qvel": qvel,
            "actual_positions": actual,
        })
        outputs.append((fields, actual))
    final_distances = np.linalg.norm(
        outputs[1][1][:, elbow_index] - outputs[0][1][:, hand_index], axis=1
    ) / height
    desired_actor_a = np.asarray(
        outputs[0][0]["desired_positions"], dtype=np.float64
    ).copy()
    desired_actor_a[:, hand_index] = (
        outputs[1][1][:, elbow_index] - target_vectors
    )
    wrist_index = target_names.index("wrist_r")
    desired_actor_a[:, wrist_index] = (
        desired_actor_a[:, hand_index]
        + outputs[0][1][:, wrist_index]
        - outputs[0][1][:, hand_index]
    )
    outputs[0][0]["desired_positions"] = desired_actor_a
    outputs[0][0]["paired_hand_target_positions"] = (
        desired_actor_a[:, hand_index]
    )
    for path, (fields, _) in zip((args.output_a, args.output_b), outputs):
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **fields)
    report = {
        "schema": 1,
        "actor_a": str(args.actor_a.resolve()),
        "actor_b": str(args.actor_b.resolve()),
        "output_a": str(args.output_a.resolve()),
        "output_b": str(args.output_b.resolve()),
        "frames": frame_count,
        "target_distance_H": args.target_distance_H,
        "distance_H": {
            "initial": float(final_distances[0]),
            "final": float(final_distances[-1]),
            "minimum": float(np.min(final_distances)),
        },
        "cost_before": float(0.5 * np.dot(residual(x0), residual(x0))),
        "cost_after": float(result.cost),
        "nfev": int(result.nfev),
        "success": bool(result.success),
        "maximum_upper_tangent_change_rad": float(np.max(np.abs(
            solved - initial
        ))),
        "roots_changed": False,
        "status": "paired_kinematic_contact_candidate_not_physical_constraint",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
