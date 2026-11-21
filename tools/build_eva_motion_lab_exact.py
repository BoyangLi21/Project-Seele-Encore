#!/usr/bin/env python3
"""Build the exact-matrix Blender EVA runtime review lab."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_eva_motion_lab_3d import (
    CORE_SEQUENCE,
    add_readme,
    add_source_human,
    add_stage,
    load_geo,
    make_collection,
    make_material,
    move_to_collection,
    iter_action_fcurves,
    principled_node,
    reset_scene,
    runtime_pivot,
    target_to_blender,
)
from build_eva_motion_lab_armature import (
    deformation_matrices,
    geometry_bind_rotations,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", required=True, type=Path)
    parser.add_argument("--geo", required=True, type=Path)
    parser.add_argument("--texture", required=True, type=Path)
    parser.add_argument("--knife-mesh", type=Path)
    parser.add_argument("--knife-texture", type=Path)
    parser.add_argument("--rifle-mesh", type=Path)
    parser.add_argument("--rifle-texture", type=Path)
    parser.add_argument("--lance-mesh", type=Path)
    parser.add_argument("--lance-texture", type=Path)
    parser.add_argument("--motion-db", required=True, type=Path)
    parser.add_argument("--source-human", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--display-scale", type=float, default=0.05)
    parser.add_argument("--gap-frames", type=int, default=12)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def build_parts(path: Path, master: bpy.types.Object,
                collection: bpy.types.Collection,
                material: bpy.types.Material) -> dict[str, bpy.types.Object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    stride = int(payload["stride"])
    if stride != 8:
        raise ValueError(f"unsupported mesh stride {stride}")
    objects = {}
    for bone_name, part in payload["parts"].items():
        pivot = runtime_pivot(part["pivot"])
        values = [float(value) for value in part["vertices"]]
        vertices = []
        uvs = []
        for offset in range(0, len(values), stride):
            local = Vector((-values[offset], values[offset + 1],
                            values[offset + 2]))
            vertices.append(tuple(target_to_blender(pivot + local)))
            uvs.append((values[offset + 3], 1.0 - values[offset + 4]))
        faces = [tuple(range(index, index + 3))
                 for index in range(0, len(vertices), 3)]
        mesh = bpy.data.meshes.new(f"EXACT::{bone_name}")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for polygon in mesh.polygons:
            polygon.use_smooth = False
            for loop_index in polygon.loop_indices:
                uv_layer.data[loop_index].uv = uvs[mesh.loops[loop_index].vertex_index]
        obj = bpy.data.objects.new(f"PART::{bone_name}", mesh)
        collection.objects.link(obj)
        obj.parent = master
        obj.rotation_mode = "QUATERNION"
        obj.data.materials.append(material)
        objects[bone_name] = obj
    return objects


def make_joint(name: str, pivot: Vector, master: bpy.types.Object,
               collection: bpy.types.Collection) -> bpy.types.Object:
    joint = bpy.data.objects.new(f"JOINT::{name}", None)
    joint.empty_display_type = "ARROWS"
    joint.empty_display_size = 2.2
    joint.location = target_to_blender(pivot)
    joint.rotation_mode = "QUATERNION"
    joint.parent = master
    collection.objects.link(joint)
    return joint


def make_contact_marker(name: str,
                        color: tuple[float, float, float, float],
                        master: bpy.types.Object,
                        collection: bpy.types.Collection) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10, radius=2.2)
    marker = bpy.context.object
    marker.name = name
    move_to_collection(marker, collection)
    marker.parent = master
    marker.rotation_mode = "QUATERNION"
    material = bpy.data.materials.new(f"MAT::{name}")
    material.diffuse_color = color
    material.use_nodes = True
    shader = principled_node(material)
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Emission Color" if "Emission Color" in shader.inputs else "Emission"].default_value = color
    shader.inputs["Emission Strength"].default_value = 2.5
    marker.data.materials.append(material)
    return marker


def key_transform(obj: bpy.types.Object, matrix: Matrix, frame: int,
                  group: str) -> None:
    obj.matrix_basis = matrix
    obj.keyframe_insert("location", frame=frame, group=group)
    obj.keyframe_insert("rotation_quaternion", frame=frame, group=group)
    obj.keyframe_insert("scale", frame=frame, group=group)


def animate_exact(motion: dict, bone_order: list[str],
                  pivots: dict[str, Vector], parents: dict[str, str],
                  bind_rotations: dict[str, Quaternion],
                  parts: dict[str, bpy.types.Object],
                  joints: dict[str, bpy.types.Object],
                  contacts: dict[str, tuple[bpy.types.Object, bpy.types.Object]],
                  hand_contacts: dict[str, tuple[bpy.types.Object, bpy.types.Object]],
                  gap_frames: int,
                  attachment_names: set[str] | None = None,
                  ) -> dict[str, tuple[int, int]]:
    attachment_names = attachment_names or set()
    sequence = [name for name in CORE_SEQUENCE if name in motion["clips"]]
    sequence.extend(sorted(set(motion["clips"]) - set(sequence)))
    db_bones = motion["bones"]
    ranges = {}
    frame_cursor = 1
    for clip_name in sequence:
        clip = motion["clips"][clip_name]
        start = frame_cursor
        root_travel = Vector(tuple(float(value) for value in
                                   clip.get("root_travel_m", (0.0, 0.0, 0.0))))
        def show_attachment(name: str) -> bool:
            if name == "knife":
                return (clip_name.startswith("cmu_sword_")
                        or clip_name.startswith("knife"))
            if name == "cannon":
                return ("rifle" in clip_name or "cannon" in clip_name
                        or "aim" in clip_name)
            if name == "lance":
                return "lance" in clip_name
            return False
        bpy.context.scene.timeline_markers.new(clip_name.upper(), frame=start)
        last_matrices = None
        last_contacts = None
        last_hand_contacts = None
        for local_index, frame_data in enumerate(clip["frames"]):
            frame = start + local_index
            display_frame = frame_data
            if root_travel.length_squared > 1.0e-12:
                phase = local_index / max(1, len(clip["frames"]) - 1)
                display_frame = dict(frame_data)
                display_frame["root_m"] = [
                    float(frame_data["root_m"][axis])
                    + float(root_travel[axis]) * phase
                    for axis in range(3)
                ]
            matrices = deformation_matrices(
                display_frame, db_bones, bone_order, pivots, parents,
                bind_rotations
            )
            for bone_name, obj in parts.items():
                key_transform(obj, matrices[bone_name], frame, clip_name)
                if bone_name in attachment_names:
                    visible = show_attachment(bone_name)
                    obj.hide_viewport = obj.hide_render = not visible
                    obj.keyframe_insert("hide_viewport", frame=frame,
                                        group=clip_name)
                    obj.keyframe_insert("hide_render", frame=frame,
                                        group=clip_name)
            for bone_name, obj in joints.items():
                joint_matrix = (matrices[bone_name]
                                @ Matrix.Translation(
                                    target_to_blender(pivots[bone_name])))
                key_transform(obj, joint_matrix, frame, clip_name)
            for side, planted in zip(("l", "r"), frame_data["foot_contact"]):
                point = matrices[f"foot_{side}"] @ target_to_blender(
                    pivots[f"foot_{side}"]
                )
                green, red = contacts[side]
                for marker, hidden in ((green, not planted), (red, planted)):
                    marker.location = point
                    marker.hide_viewport = marker.hide_render = bool(hidden)
                    marker.keyframe_insert("location", frame=frame,
                                           group=clip_name)
                    marker.keyframe_insert("hide_viewport", frame=frame,
                                           group=clip_name)
                    marker.keyframe_insert("hide_render", frame=frame,
                                           group=clip_name)
            for side, planted in zip(
                    ("l", "r"), frame_data.get("hand_contact", (False, False))):
                point = matrices[f"hand_{side}"] @ target_to_blender(
                    pivots[f"hand_{side}"]
                )
                green, red = hand_contacts[side]
                for marker, hidden in ((green, not planted), (red, planted)):
                    marker.location = point
                    marker.hide_viewport = marker.hide_render = bool(hidden)
                    marker.keyframe_insert("location", frame=frame,
                                           group=clip_name)
                    marker.keyframe_insert("hide_viewport", frame=frame,
                                           group=clip_name)
                    marker.keyframe_insert("hide_render", frame=frame,
                                           group=clip_name)
            last_matrices = matrices
            last_contacts = frame_data["foot_contact"]
            last_hand_contacts = frame_data.get("hand_contact", (False, False))
        end = start + len(clip["frames"]) - 1
        hold = end + gap_frames
        if last_matrices is not None:
            for bone_name, obj in parts.items():
                key_transform(obj, last_matrices[bone_name], hold, clip_name)
                if bone_name in attachment_names:
                    visible = show_attachment(bone_name)
                    obj.hide_viewport = obj.hide_render = not visible
                    obj.keyframe_insert("hide_viewport", frame=hold,
                                        group=clip_name)
                    obj.keyframe_insert("hide_render", frame=hold,
                                        group=clip_name)
            for bone_name, obj in joints.items():
                joint_matrix = (last_matrices[bone_name]
                                @ Matrix.Translation(
                                    target_to_blender(pivots[bone_name])))
                key_transform(obj, joint_matrix, hold, clip_name)
            for side, planted in zip(("l", "r"), last_contacts):
                point = last_matrices[f"foot_{side}"] @ target_to_blender(
                    pivots[f"foot_{side}"]
                )
                green, red = contacts[side]
                for marker, hidden in ((green, not planted), (red, planted)):
                    marker.location = point
                    marker.hide_viewport = marker.hide_render = bool(hidden)
                    marker.keyframe_insert("location", frame=hold,
                                           group=clip_name)
                    marker.keyframe_insert("hide_viewport", frame=hold,
                                           group=clip_name)
                    marker.keyframe_insert("hide_render", frame=hold,
                                           group=clip_name)
            for side, planted in zip(("l", "r"), last_hand_contacts):
                point = last_matrices[f"hand_{side}"] @ target_to_blender(
                    pivots[f"hand_{side}"]
                )
                green, red = hand_contacts[side]
                for marker, hidden in ((green, not planted), (red, planted)):
                    marker.location = point
                    marker.hide_viewport = marker.hide_render = bool(hidden)
                    marker.keyframe_insert("location", frame=hold,
                                           group=clip_name)
                    marker.keyframe_insert("hide_viewport", frame=hold,
                                           group=clip_name)
                    marker.keyframe_insert("hide_render", frame=hold,
                                           group=clip_name)
        ranges[clip_name] = (start, end)
        frame_cursor = hold + 1

    animated = [*parts.values(), *joints.values(),
                *(marker for pair in contacts.values() for marker in pair),
                *(marker for pair in hand_contacts.values() for marker in pair)]
    for obj in animated:
        if obj.animation_data is None or obj.animation_data.action is None:
            continue
        for curve in iter_action_fcurves(obj.animation_data.action):
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = max(1, frame_cursor - 1)
    scene.frame_set(1)
    return ranges


def main() -> None:
    args = parse_args()
    for path in (args.mesh, args.geo, args.texture, args.motion_db):
        if not path.is_file():
            raise SystemExit(f"missing input: {path}")
    reset_scene()
    scene = bpy.context.scene
    scene.world.color = (0.008, 0.012, 0.02)
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        scene.view_settings.look = "Medium High Contrast"
    stage = make_collection("00_STAGE")
    visual_collection = make_collection("10_EXACT_RUNTIME_MESH")
    attachment_collection = make_collection("15_EXACT_ATTACHMENTS")
    joint_collection = make_collection("20_EXACT_RUNTIME_JOINTS")
    contact_collection = make_collection("30_CONTACT_DEBUG")
    source_collection = make_collection("40_CC0_HUMAN_REFERENCE")
    add_stage(stage)
    master = bpy.data.objects.new("EVA_EXACT_ROOT", None)
    master.scale = (args.display_scale,) * 3
    visual_collection.objects.link(master)
    bones, pivots, parents = load_geo(args.geo)
    bind_rotations = geometry_bind_rotations(bones)
    parts = build_parts(args.mesh, master, visual_collection,
                        make_material(args.texture))
    attachment_names: set[str] = set()
    attachment_inputs = (
        ("knife", args.knife_mesh, args.knife_texture),
        ("rifle", args.rifle_mesh, args.rifle_texture),
        ("lance", args.lance_mesh, args.lance_texture),
    )
    for label, mesh_path, texture_path in attachment_inputs:
        if mesh_path is None and texture_path is None:
            continue
        if (mesh_path is None or texture_path is None
                or not mesh_path.is_file() or not texture_path.is_file()):
            raise SystemExit(f"{label} mesh and texture must both exist")
        new_parts = build_parts(
            mesh_path, master, attachment_collection,
            make_material(texture_path),
        )
        overlap = set(parts) & set(new_parts)
        if overlap:
            raise SystemExit("attachment/body part collision: "
                             + ", ".join(sorted(overlap)))
        parts.update(new_parts)
        attachment_names.update(new_parts)
    joints = {
        name: make_joint(name, pivot, master, joint_collection)
        for name, pivot in pivots.items()
    }
    contacts = {
        side: (
            make_contact_marker(f"CONTACT_{side.upper()}_PLANTED",
                                (0.05, 1.0, 0.18, 1.0), master,
                                contact_collection),
            make_contact_marker(f"CONTACT_{side.upper()}_AIR",
                                (1.0, 0.05, 0.03, 1.0), master,
                                contact_collection),
        )
        for side in ("l", "r")
    }
    hand_contacts = {
        side: (
            make_contact_marker(f"HAND_CONTACT_{side.upper()}_PLANTED",
                                (0.05, 0.85, 1.0, 1.0), master,
                                contact_collection),
            make_contact_marker(f"HAND_CONTACT_{side.upper()}_AIR",
                                (1.0, 0.05, 0.75, 1.0), master,
                                contact_collection),
        )
        for side in ("l", "r")
    }
    motion = json.loads(args.motion_db.read_text(encoding="utf-8"))
    ranges = animate_exact(
        motion, [bone["name"] for bone in bones], pivots, parents,
        bind_rotations,
        parts, joints, contacts, hand_contacts, args.gap_frames,
        attachment_names
    )
    if args.source_human is not None and args.source_human.is_file():
        add_source_human(args.source_human, ranges, source_collection)
    add_readme(motion, ranges)
    scene["project_seele_exact_runtime_lab"] = True
    scene["clip_count"] = len(ranges)
    scene["motion_db_sha256"] = hashlib.sha256(
        args.motion_db.read_bytes()
    ).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    print(
        f"EVA exact 3D lab: clips={len(ranges)} frames={scene.frame_end} "
        f"parts={len(parts)} joints={len(joints)} output={args.output}"
    )


if __name__ == "__main__":
    main()
