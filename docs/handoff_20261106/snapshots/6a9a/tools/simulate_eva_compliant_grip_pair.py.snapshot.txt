#!/usr/bin/env python3
"""Simulate two grounded EVAs coupled by a breakable compliant 6D grip."""

from __future__ import annotations

import argparse
import json
import math
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--actor-a", required=True, type=Path)
    parser.add_argument("--actor-b", required=True, type=Path)
    parser.add_argument("--output-a", required=True, type=Path)
    parser.add_argument("--output-b", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--sample-hz", type=float, default=50.0)
    parser.add_argument("--linear-stiffness", type=float, default=42000.0)
    parser.add_argument("--linear-damping", type=float, default=9000.0)
    parser.add_argument("--angular-stiffness", type=float, default=2800.0)
    parser.add_argument("--angular-damping", type=float, default=900.0)
    parser.add_argument("--break-force", type=float, default=6500.0)
    parser.add_argument("--break-torque", type=float, default=2600.0)
    parser.add_argument("--maximum-pull-force", type=float, default=9000.0)
    parser.add_argument("--pull-direction", type=float, nargs=3,
                        default=(0.0, -1.0, 0.0))
    parser.add_argument("--grip-activation-time", type=float, default=0.05)
    parser.add_argument("--grip-ramp-seconds", type=float, default=0.30)
    parser.add_argument("--root-frequency", type=float, default=1.25)
    parser.add_argument("--root-damping-ratio", type=float, default=1.0)
    parser.add_argument("--root-horizontal-force-limit", type=float,
                        default=18000.0)
    parser.add_argument("--root-vertical-force-limit", type=float,
                        default=24000.0)
    parser.add_argument("--root-torque-limit", type=float, default=12000.0)
    parser.add_argument("--actor-b-horizontal-root-scale", type=float,
                        default=0.30)
    parser.add_argument("--nominal-height", type=float, default=4.0)
    args = parser.parse_args()
    pull_direction = np.asarray(args.pull_direction, dtype=np.float64)
    pull_norm = float(np.linalg.norm(pull_direction))
    if pull_norm <= 1.0e-12:
        raise RuntimeError("--pull-direction must be non-zero")
    pull_direction /= pull_norm

    models = [
        mujoco.MjModel.from_xml_path(str(args.model.resolve())),
        mujoco.MjModel.from_xml_path(str(args.model.resolve())),
    ]
    data = [mujoco.MjData(model) for model in models]
    sources = [np.load(args.actor_a), np.load(args.actor_b)]
    target_qpos = [
        np.asarray(source["qpos"], dtype=np.float64)[-1].copy()
        for source in sources
    ]
    for actor in range(2):
        data[actor].qpos[:] = target_qpos[actor]
        data[actor].qvel[:] = 0.0
        mujoco.mj_forward(models[actor], data[actor])

    tangent_names = [str(value) for value in sources[0]["tangent_names"]]
    actuator_frequencies = np.asarray([
        5.8 if any(token in name for token in ("hip", "knee", "ankle"))
        else 5.0 if any(token in name for token in (
            "lumbar", "thoracic", "shoulder"
        )) else 6.5
        for name in tangent_names
    ], dtype=np.float64)

    hand_site = models[0].site("palm_grip_r").id
    hand_body = models[0].body("hand_r").id
    elbow_body = models[1].body("elbow_link_l").id
    pelvis_ids = [model.body("pelvis").id for model in models]
    pelvis_b = models[1].body("pelvis").id
    target_pelvis_positions = [
        actor_data.xpos[pelvis_ids[actor]].copy()
        for actor, actor_data in enumerate(data)
    ]
    target_pelvis_rotations = [
        actor_data.xmat[pelvis_ids[actor]].reshape(3, 3).copy()
        for actor, actor_data in enumerate(data)
    ]
    total_masses = [float(np.sum(model.body_mass)) for model in models]

    def point_velocity(actor: int, point: np.ndarray, body_id: int):
        jacobian = np.zeros((3, models[actor].nv), dtype=np.float64)
        mujoco.mj_jac(
            models[actor], data[actor], jacobian, None, point, body_id
        )
        return jacobian @ data[actor].qvel

    def angular_velocity(actor: int, point: np.ndarray, body_id: int):
        jacobian = np.zeros((3, models[actor].nv), dtype=np.float64)
        mujoco.mj_jac(
            models[actor], data[actor], None, jacobian, point, body_id
        )
        return jacobian @ data[actor].qvel

    position_a = data[0].site_xpos[hand_site].copy()
    position_b = data[1].xpos[elbow_body].copy()
    rest_offset = position_b - position_a
    rotation_a = data[0].xmat[hand_body].reshape(3, 3).copy()
    rotation_b = data[1].xmat[elbow_body].reshape(3, 3).copy()
    rest_relative_rotation = rotation_a.T @ rotation_b

    def pd_control(actor: int) -> None:
        model = models[actor]
        actor_data = data[actor]
        error = np.zeros(model.nv, dtype=np.float64)
        mujoco.mj_differentiatePos(
            model, error, 1.0, actor_data.qpos, target_qpos[actor]
        )
        mass_matrix = np.zeros((model.nv, model.nv), dtype=np.float64)
        mujoco.mj_fullM(model, actor_data, mass_matrix)
        inertia = np.maximum(np.diag(mass_matrix), 1.0e-5)
        desired = np.zeros(model.nv, dtype=np.float64)
        for actuator in range(model.nu):
            joint_id = int(model.actuator_trnid[actuator, 0])
            dof_address = int(model.jnt_dofadr[joint_id])
            joint_type = int(model.jnt_type[joint_id])
            dof_count = 3 if joint_type == mujoco.mjtJoint.mjJNT_BALL else 1
            frequency = actuator_frequencies[actuator]
            omega = 2.0 * math.pi * frequency
            for offset in range(dof_count):
                dof = dof_address + offset
                kp = inertia[dof] * omega * omega
                kd = 2.0 * inertia[dof] * omega
                desired[dof] = (
                    kp * error[dof] - kd * actor_data.qvel[dof]
                )
        for actuator in range(model.nu):
            joint_id = int(model.actuator_trnid[actuator, 0])
            dof_address = int(model.jnt_dofadr[joint_id])
            joint_type = int(model.jnt_type[joint_id])
            if joint_type == mujoco.mjtJoint.mjJNT_BALL:
                moment = np.asarray(
                    model.actuator_gear[actuator, :3], dtype=np.float64
                )
                denominator = float(np.dot(moment, moment))
                control = (
                    float(np.dot(moment, desired[dof_address:dof_address + 3]))
                    / denominator if denominator > 1.0e-12 else 0.0
                )
            else:
                gear = float(model.actuator_gear[actuator, 0])
                control = (desired[dof_address] / gear
                           if abs(gear) > 1.0e-12 else 0.0)
            actor_data.ctrl[actuator] = np.clip(
                control,
                model.actuator_ctrlrange[actuator, 0],
                model.actuator_ctrlrange[actuator, 1],
            )

    def apply_root_support(actor: int) -> tuple[float, float]:
        """Apply a bounded physical balance wrench; never write free-root state."""
        model = models[actor]
        actor_data = data[actor]
        pelvis_id = pelvis_ids[actor]
        position = actor_data.xpos[pelvis_id].copy()
        velocity = point_velocity(actor, position, pelvis_id)
        omega = angular_velocity(actor, position, pelvis_id)
        frequency = args.root_frequency
        omega_n = 2.0 * math.pi * frequency
        mass = total_masses[actor]
        kp = mass * omega_n * omega_n
        kd = 2.0 * args.root_damping_ratio * mass * omega_n
        position_error = position - target_pelvis_positions[actor]
        force = -kp * position_error - kd * velocity
        horizontal_scale = (1.0 if actor == 0
                            else args.actor_b_horizontal_root_scale)
        force[:2] *= horizontal_scale
        horizontal_norm = float(np.linalg.norm(force[:2]))
        if horizontal_norm > args.root_horizontal_force_limit:
            force[:2] *= args.root_horizontal_force_limit / horizontal_norm
        force[2] = float(np.clip(
            force[2], -args.root_vertical_force_limit,
            args.root_vertical_force_limit,
        ))

        current_rotation = actor_data.xmat[pelvis_id].reshape(3, 3)
        rotation_error = Rotation.from_matrix(
            target_pelvis_rotations[actor].T @ current_rotation
        ).as_rotvec()
        # The pelvis body inertia alone badly underestimates the angular
        # inertia of the articulated whole character.  Use the full-body
        # gameplay proxy inertia for this test-only balance wrench.
        inertia_scale = max(
            mass * (0.32 * args.nominal_height) ** 2, 1.0
        )
        angular_kp = inertia_scale * omega_n * omega_n
        angular_kd = (2.0 * args.root_damping_ratio
                      * inertia_scale * omega_n)
        torque = target_pelvis_rotations[actor] @ (
            -angular_kp * rotation_error
        ) - angular_kd * omega
        torque_norm = float(np.linalg.norm(torque))
        if torque_norm > args.root_torque_limit:
            torque *= args.root_torque_limit / torque_norm
        mujoco.mj_applyFT(
            model, actor_data, force, torque, position, pelvis_id,
            actor_data.qfrc_applied,
        )
        return float(np.linalg.norm(force)), float(np.linalg.norm(torque))

    target_names = [str(value) for value in sources[0]["target_landmark_names"]]
    object_ids = []
    for model in models:
        rows = []
        for name in target_names:
            object_type, object_name = TARGET_OBJECTS[name]
            object_id = mujoco.mj_name2id(
                model,
                (mujoco.mjtObj.mjOBJ_BODY if object_type == "body"
                 else mujoco.mjtObj.mjOBJ_GEOM), object_name,
            )
            rows.append((object_type, object_id))
        object_ids.append(rows)

    dt = float(models[0].opt.timestep)
    physics_steps = int(round(args.seconds / dt))
    sample_stride = max(1, int(round(1.0 / (args.sample_hz * dt))))
    grip_active = False
    grip_armed = False
    grip_activation_time = args.grip_activation_time
    grip_ramp_seconds = args.grip_ramp_seconds
    break_time = None
    break_reason = None
    break_attempted_force = None
    break_attempted_torque = None
    samples = [[], []]
    velocity_samples = [[], []]
    actual_samples = [[], []]
    contact_samples = [[], []]
    times = []
    grip_errors = []
    active_grip_errors = []
    active_contact_distances = []
    grip_forces = []
    grip_torques = []
    attempted_grip_forces = []
    attempted_grip_torques = []
    pelvis_displacement_b = []
    root_support_forces = []
    root_support_torques = []
    initial_pelvis_b = data[1].xpos[pelvis_b].copy()
    initial_contact_distance = float(np.linalg.norm(
        data[1].xpos[elbow_body] - data[0].site_xpos[hand_site]
    ))
    root_state_write_violations = 0
    last_root_positions = [actor_data.qpos[:3].copy() for actor_data in data]
    maximum_root_position_step = 0.0

    for step in range(physics_steps + 1):
        time = step * dt
        root_state_before_control = [
            actor_data.qpos[:7].copy() for actor_data in data
        ]
        for actor in range(2):
            data[actor].qfrc_applied[:] = 0.0
            pd_control(actor)
            support_force, support_torque = apply_root_support(actor)
            root_support_forces.append(support_force)
            root_support_torques.append(support_torque)

        position_a = data[0].site_xpos[hand_site].copy()
        position_b = data[1].xpos[elbow_body].copy()
        velocity_a = point_velocity(0, position_a, hand_body)
        velocity_b = point_velocity(1, position_b, elbow_body)
        if not grip_armed and time >= grip_activation_time:
            rest_offset = position_b - position_a
            rotation_a = data[0].xmat[hand_body].reshape(3, 3).copy()
            rotation_b = data[1].xmat[elbow_body].reshape(3, 3).copy()
            rest_relative_rotation = rotation_a.T @ rotation_b
            grip_armed = True
            grip_active = True
        error = (position_b - position_a) - rest_offset
        relative_velocity = velocity_b - velocity_a
        force = np.zeros(3, dtype=np.float64)
        torque = np.zeros(3, dtype=np.float64)
        if grip_active:
            ramp_phase = min(
                1.0, max(0.0, (time - grip_activation_time)
                         / grip_ramp_seconds)
            )
            grip_gain = ramp_phase * ramp_phase * (3.0 - 2.0 * ramp_phase)
            force = (
                args.linear_stiffness * error
                + args.linear_damping * relative_velocity
            ) * grip_gain
            rotation_a = data[0].xmat[hand_body].reshape(3, 3)
            rotation_b = data[1].xmat[elbow_body].reshape(3, 3)
            current_relative = rotation_a.T @ rotation_b
            rotation_error = Rotation.from_matrix(
                rest_relative_rotation.T @ current_relative
            ).as_rotvec()
            omega_a = angular_velocity(0, position_a, hand_body)
            omega_b = angular_velocity(1, position_b, elbow_body)
            torque_local = (
                args.angular_stiffness * rotation_error
                + args.angular_damping * rotation_a.T @ (omega_b - omega_a)
            )
            torque = (rotation_a @ torque_local) * grip_gain
            attempted_grip_forces.append(float(np.linalg.norm(force)))
            attempted_grip_torques.append(float(np.linalg.norm(torque)))
            active_grip_errors.append(float(np.linalg.norm(error)))
            active_contact_distances.append(float(np.linalg.norm(
                position_b - position_a
            )))
            if (grip_gain > 0.80 and (
                    np.linalg.norm(force) > args.break_force
                    or np.linalg.norm(torque) > args.break_torque)):
                grip_active = False
                break_time = time
                break_attempted_force = float(np.linalg.norm(force))
                break_attempted_torque = float(np.linalg.norm(torque))
                break_reason = (
                    "force" if break_attempted_force > args.break_force
                    else "torque"
                )
                force[:] = 0.0
                torque[:] = 0.0
            else:
                mujoco.mj_applyFT(
                    models[0], data[0], force, torque,
                    position_a, hand_body, data[0].qfrc_applied,
                )
                mujoco.mj_applyFT(
                    models[1], data[1], -force, -torque,
                    position_b, elbow_body, data[1].qfrc_applied,
                )

        if 1.00 <= time <= 2.50:
            phase = (time - 1.00) / 1.50
            pull = args.maximum_pull_force * phase * phase
            mujoco.mj_applyFT(
                models[1], data[1], pull_direction * pull,
                np.zeros(3), data[1].xpos[pelvis_b], pelvis_b,
                data[1].qfrc_applied,
            )

        for actor in range(2):
            if not np.array_equal(
                    data[actor].qpos[:7], root_state_before_control[actor]):
                root_state_write_violations += 1

        grip_errors.append(float(np.linalg.norm(error)))
        grip_forces.append(float(np.linalg.norm(force)))
        grip_torques.append(float(np.linalg.norm(torque)))
        pelvis_displacement_b.append(float(np.linalg.norm(
            data[1].xpos[pelvis_b] - initial_pelvis_b
        )))
        if step % sample_stride == 0:
            times.append(time)
            for actor in range(2):
                samples[actor].append(data[actor].qpos.copy())
                velocity_samples[actor].append(data[actor].qvel.copy())
                actual_samples[actor].append(np.stack([
                    (data[actor].xpos[object_id] if object_type == "body"
                     else data[actor].geom_xpos[object_id]).copy()
                    for object_type, object_id in object_ids[actor]
                ]))
                ground_id = models[actor].geom("ground").id
                side_contact = []
                for side in ("l", "r"):
                    ids = {
                        models[actor].geom(f"heel_{side}").id,
                        models[actor].geom(f"forefoot_{side}").id,
                        models[actor].geom(f"toe_{side}_collision").id,
                    }
                    side_contact.append(any(
                        ground_id in {int(contact.geom1), int(contact.geom2)}
                        and bool(ids & {int(contact.geom1), int(contact.geom2)})
                        for contact in data[actor].contact
                    ))
                contact_samples[actor].append(side_contact)
        if step < physics_steps:
            for actor in range(2):
                mujoco.mj_step(models[actor], data[actor])
                root_step = float(np.linalg.norm(
                    data[actor].qpos[:3] - last_root_positions[actor]
                ))
                maximum_root_position_step = max(
                    maximum_root_position_step, root_step
                )
                last_root_positions[actor] = data[actor].qpos[:3].copy()

    for path, actor in zip((args.output_a, args.output_b), range(2)):
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            qpos=np.asarray(samples[actor], dtype=np.float64),
            qvel=np.asarray(velocity_samples[actor], dtype=np.float64),
            timestep=np.asarray([1.0 / args.sample_hz], dtype=np.float64),
            source_frames=np.asarray(times, dtype=np.float64),
            target_landmark_names=np.asarray(target_names),
            actual_positions=np.asarray(actual_samples[actor], dtype=np.float64),
            foot_contact=np.asarray(contact_samples[actor], dtype=np.bool_),
        )
    report = {
        "schema": 1,
        "model": str(args.model.resolve()),
        "actor_a": str(args.actor_a.resolve()),
        "actor_b": str(args.actor_b.resolve()),
        "physics_hz": 1.0 / dt,
        "sample_hz": args.sample_hz,
        "seconds": args.seconds,
        "grip": {
            "linear_stiffness_N_per_m": args.linear_stiffness,
            "linear_damping_Ns_per_m": args.linear_damping,
            "angular_stiffness_Nm_per_rad": args.angular_stiffness,
            "angular_damping_Nms_per_rad": args.angular_damping,
            "break_force_N": args.break_force,
            "break_torque_Nm": args.break_torque,
            "break_time_s": break_time,
            "break_reason": break_reason,
            "break_attempted_force_N": break_attempted_force,
            "break_attempted_torque_Nm": break_attempted_torque,
            "survival_after_activation_s": (
                (break_time if break_time is not None else args.seconds)
                - grip_activation_time
            ),
            "activation_time_s": grip_activation_time,
            "activation_ramp_seconds": grip_ramp_seconds,
            "maximum_error_m": max(grip_errors),
            "maximum_error_while_active_m": max(
                active_grip_errors, default=0.0
            ),
            "initial_contact_distance_m": initial_contact_distance,
            "maximum_contact_distance_while_active_m": max(
                active_contact_distances, default=initial_contact_distance
            ),
            "maximum_force_N": max(grip_forces),
            "maximum_torque_Nm": max(grip_torques),
            "maximum_attempted_force_N": max(
                attempted_grip_forces, default=0.0
            ),
            "maximum_attempted_torque_Nm": max(
                attempted_grip_torques, default=0.0
            ),
        },
        "target_pull": {
            "maximum_force_N": args.maximum_pull_force,
            "direction_world": pull_direction.tolist(),
            "maximum_pelvis_displacement_m": max(pelvis_displacement_b),
        },
        "test_root_support": {
            "type": "bounded_physical_wrench_no_root_state_writes",
            "natural_frequency_hz": args.root_frequency,
            "damping_ratio": args.root_damping_ratio,
            "horizontal_force_limit_N": args.root_horizontal_force_limit,
            "vertical_force_limit_N": args.root_vertical_force_limit,
            "torque_limit_Nm": args.root_torque_limit,
            "actor_b_horizontal_scale": args.actor_b_horizontal_root_scale,
            "maximum_applied_force_N": max(root_support_forces),
            "maximum_applied_torque_Nm": max(root_support_torques),
        },
        "finite": bool(all(
            np.all(np.isfinite(data[actor].qpos))
            and np.all(np.isfinite(data[actor].qvel))
            for actor in range(2)
        )),
        "root_authority": {
            "direct_root_state_write_violations": root_state_write_violations,
            "maximum_physics_step_translation_m": maximum_root_position_step,
        },
        "status": "two_independent_worlds_coupled_by_equal_opposite_6D_wrench_prototype",
        "limitations": [
            "actors do not yet share body-body collision broadphase",
            "joint PD is a test stabilizer, not a trained tracking policy",
            "pelvis balance wrench is a bounded test stabilizer, not a product controller",
            "damage is not emitted",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
