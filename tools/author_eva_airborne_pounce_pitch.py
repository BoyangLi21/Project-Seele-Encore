#!/usr/bin/env python3
"""Author a predatory airborne root pitch after an audited pounce takeoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation


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


def rotation(qpos):
    return Rotation.from_quat((qpos[4], qpos[5], qpos[6], qpos[3]))


def wxyz(value):
    x, y, z, w = value.as_quat()
    return np.asarray((w, x, y, z), dtype=np.float64)


def smooth(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--pitch-degrees", type=float, default=55.0)
    parser.add_argument("--ramp-frames", type=int, default=30)
    args = parser.parse_args()

    model = mujoco.MjModel.from_xml_path(str(args.model.resolve()))
    data = mujoco.MjData(model)
    state = np.load(args.state)
    qpos = np.asarray(state["qpos"], dtype=np.float64).copy()
    desired = np.asarray(state["desired_positions"], dtype=np.float64).copy()
    contacts = np.asarray(state["foot_contact"], dtype=np.bool_)
    flight_start = next((
        index for index in range(len(contacts))
        if not np.any(contacts[index:])
    ), None)
    if flight_start is None:
        raise RuntimeError("state has no terminal airborne interval")
    ramp_frames = max(1, args.ramp_frames)
    pitch_radians = np.radians(args.pitch_degrees)
    applied_pitch = np.zeros(len(qpos), dtype=np.float64)
    for frame in range(flight_start, len(qpos)):
        phase = smooth((frame - flight_start) / ramp_frames)
        applied_pitch[frame] = pitch_radians * phase
        original = rotation(qpos[frame])
        authored = original * Rotation.from_euler(
            "y", applied_pitch[frame]
        )
        world_delta = authored * original.inv()
        root = qpos[frame, :3].copy()
        qpos[frame, 3:7] = wxyz(authored)
        desired[frame] = root + world_delta.apply(
            desired[frame] - root
        )

    names = [str(value) for value in state["target_landmark_names"]]
    object_ids = []
    for name in names:
        object_type, object_name = TARGET_OBJECTS[name]
        enum = (mujoco.mjtObj.mjOBJ_BODY if object_type == "body"
                else mujoco.mjtObj.mjOBJ_GEOM)
        object_ids.append((object_type,
                           mujoco.mj_name2id(model, enum, object_name)))
    actual = []
    for row in qpos:
        data.qpos[:] = row
        mujoco.mj_forward(model, data)
        actual.append(np.stack([
            (data.xpos[object_id] if object_type == "body"
             else data.geom_xpos[object_id]).copy()
            for object_type, object_id in object_ids
        ]))
    actual = np.asarray(actual, dtype=np.float64)
    dt = float(state["timestep"][0])
    qvel = np.zeros((len(qpos), model.nv), dtype=np.float64)
    for frame in range(len(qpos)):
        before = max(0, frame - 1)
        after = min(len(qpos) - 1, frame + 1)
        mujoco.mj_differentiatePos(
            model, qvel[frame], max(dt, (after - before) * dt),
            qpos[before], qpos[after],
        )
    fields = {key: state[key] for key in state.files}
    fields.update({
        "qpos": qpos, "qvel": qvel,
        "desired_positions": desired, "actual_positions": actual,
        "authored_airborne_pitch_rad": applied_pitch,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **fields)
    root_steps = []
    for frame in range(1, len(qpos)):
        root_steps.append((
            rotation(qpos[frame - 1]).inv() * rotation(qpos[frame])
        ).magnitude())
    report = {
        "schema": 1,
        "source_state": str(args.state.resolve()),
        "output_state": str(args.output.resolve()),
        "flight_start_frame": flight_start,
        "pitch_degrees": args.pitch_degrees,
        "ramp_frames": ramp_frames,
        "maximum_root_rotation_step_degrees": float(np.degrees(
            max(root_steps, default=0.0)
        )),
        "contacts_changed": False,
        "root_translation_changed": False,
        "status": "project_authored_airborne_pounce_candidate",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
