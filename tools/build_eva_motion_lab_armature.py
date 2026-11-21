#!/usr/bin/env python3
"""Build the production-style armature edition of EVA Motion Lab."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

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
    quaternion_to_blender,
    reset_scene,
    runtime_pivot,
    target_to_blender,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", required=True, type=Path)
    parser.add_argument("--geo", required=True, type=Path)
    parser.add_argument("--texture", required=True, type=Path)
    parser.add_argument("--motion-db", required=True, type=Path)
    parser.add_argument("--source-human", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--display-scale", type=float, default=0.05)
    parser.add_argument("--gap-frames", type=int, default=12)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def build_armature(bones: list[dict], pivots: dict[str, Vector],
                   parents: dict[str, str], collection: bpy.types.Collection,
                   scale: float) -> tuple[bpy.types.Object, bpy.types.Object]:
    master = bpy.data.objects.new("EVA_MOTION_LAB_ROOT", None)
    master.empty_display_type = "PLAIN_AXES"
    master.scale = (scale, scale, scale)
    collection.objects.link(master)

    armature_data = bpy.data.armatures.new("EVA_RUNTIME_ARMATURE")
    armature = bpy.data.objects.new("EVA_RUNTIME_ARMATURE", armature_data)
    collection.objects.link(armature)
    armature.parent = master
    armature.show_in_front = True
    armature.data.display_type = "STICK"

    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = {}
    for spec in bones:
        name = spec["name"]
        bone = armature.data.edit_bones.new(name)
        head = target_to_blender(pivots[name])
        bone.head = head
        # Disconnected, globally aligned rest axes make the Bedrock nested
        # rotations directly editable without hidden per-bone roll.
        bone.tail = head + Vector((0.0, 0.0, 2.0))
        bone.use_connect = False
        edit_bones[name] = bone
    for name, parent in parents.items():
        edit_bones[name].parent = edit_bones[parent]
    bpy.ops.object.mode_set(mode="POSE")
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"
        pose_bone.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        if pose_bone.name in {"foot_l", "foot_r"}:
            pose_bone["contact"] = 0.0
    bpy.ops.object.mode_set(mode="OBJECT")
    armature.select_set(False)
    return master, armature


def build_weighted_mesh(path: Path, armature: bpy.types.Object,
                        master: bpy.types.Object,
                        collection: bpy.types.Collection,
                        material: bpy.types.Material) -> bpy.types.Object:
    payload = json.loads(path.read_text(encoding="utf-8"))
    stride = int(payload["stride"])
    if stride != 8:
        raise ValueError(f"unsupported mesh stride {stride}")
    vertices: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    faces: list[tuple[int, int, int]] = []
    groups: dict[str, list[int]] = {}
    for bone_name, part in payload["parts"].items():
        pivot = runtime_pivot(part["pivot"])
        values = [float(value) for value in part["vertices"]]
        indices = []
        for offset in range(0, len(values), stride):
            local = Vector((-values[offset], values[offset + 1],
                            values[offset + 2]))
            absolute = pivot + local
            indices.append(len(vertices))
            vertices.append(tuple(target_to_blender(absolute)))
            uvs.append((values[offset + 3], 1.0 - values[offset + 4]))
        groups.setdefault(bone_name, []).extend(indices)
        for start in range(indices[0], indices[-1] + 1, 3):
            faces.append((start, start + 1, start + 2))

    mesh = bpy.data.meshes.new("EVA_RUNTIME_SKINNED_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        polygon.use_smooth = False
        for loop_index in polygon.loop_indices:
            uv_layer.data[loop_index].uv = uvs[mesh.loops[loop_index].vertex_index]
    obj = bpy.data.objects.new("EVA_RUNTIME_SKINNED_MESH", mesh)
    collection.objects.link(obj)
    obj.parent = master
    obj.data.materials.append(material)
    for name, indices in groups.items():
        group = obj.vertex_groups.new(name=name)
        group.add(indices, 1.0, "REPLACE")
    modifier = obj.modifiers.new("EVA Runtime Armature", "ARMATURE")
    modifier.object = armature
    modifier.use_deform_preserve_volume = True
    return obj


def make_contact_marker(name: str,
                        color: tuple[float, float, float, float],
                        armature: bpy.types.Object, foot: str,
                        collection: bpy.types.Collection,
                        planted: bool) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10, radius=2.2)
    marker = bpy.context.object
    marker.name = name
    move_to_collection(marker, collection)
    marker.parent = armature
    marker.parent_type = "BONE"
    marker.parent_bone = foot
    marker.location = (0.0, 0.0, -18.2)
    material = bpy.data.materials.new(f"MAT::{name}")
    material.diffuse_color = color
    material.use_nodes = True
    shader = principled_node(material)
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Emission Color" if "Emission Color" in shader.inputs else "Emission"].default_value = color
    shader.inputs["Emission Strength"].default_value = 2.5
    marker.data.materials.append(material)
    for data_path in ("hide_viewport", "hide_render"):
        curve = marker.driver_add(data_path)
        variable = curve.driver.variables.new()
        variable.name = "contact"
        variable.type = "SINGLE_PROP"
        target = variable.targets[0]
        target.id = armature
        target.data_path = f'pose.bones["{foot}"]["contact"]'
        curve.driver.expression = "contact < 0.5" if planted else "contact >= 0.5"
    return marker


def deformation_matrices(frame_data: dict, db_bones: list[str],
                         bone_order: list[str], pivots: dict[str, Vector],
                         parents: dict[str, str],
                         bind_rotations: dict[str, Quaternion] | None = None,
                         ) -> dict[str, Matrix]:
    bind_rotations = bind_rotations or {}
    rotations = {
        name: quaternion_to_blender(frame_data["rotation_wxyz"][index])
        for index, name in enumerate(db_bones)
    }
    root_m = Vector(tuple(float(value) for value in frame_data["root_m"]))
    root_runtime = Vector((-root_m.x, root_m.y, root_m.z)) * 112.0
    root_yaw = float(frame_data.get("root_yaw_radians", 0.0))
    root_yaw_matrix = Matrix.Rotation(root_yaw, 4, "Z")
    animated_positions = frame_data.get("bone_position_xyz", {})
    matrices = {}
    for name in bone_order:
        pivot = target_to_blender(pivots[name])
        rotation = rotations.get(name, bind_rotations.get(
            name, Quaternion((1.0, 0.0, 0.0, 0.0))))
        position = (target_to_blender(root_runtime) if name == "root"
                    else Vector((0.0, 0.0, 0.0)))
        if name in animated_positions:
            raw = Vector(tuple(float(value)
                               for value in animated_positions[name]))
            position += target_to_blender(Vector((-raw.x, raw.y, raw.z)))
        local = (Matrix.Translation(position)
                 @ (root_yaw_matrix if name == "root" else Matrix.Identity(4))
                 @ Matrix.Translation(pivot)
                 @ rotation.to_matrix().to_4x4()
                 @ Matrix.Translation(-pivot))
        parent = parents.get(name)
        matrices[name] = local if parent is None else matrices[parent] @ local
    return matrices


def geometry_bind_rotations(bones: list[dict]) -> dict[str, Quaternion]:
    """Convert static Bedrock bone rotations through the exact Gecko basis."""
    result = {}
    for bone in bones:
        raw = bone.get("rotation")
        if raw is None:
            continue
        authored = Euler(tuple(
            math.radians(float(value)) for value in raw), "XYZ"
        ).to_quaternion()
        result[bone["name"]] = quaternion_to_blender([
            authored.w, authored.x, authored.y, authored.z
        ])
    return result


def make_clip_action(armature: bpy.types.Object, motion: dict,
                     clip_name: str, bone_order: list[str],
                     pivots: dict[str, Vector],
                     parents: dict[str, str],
                     bind_rotations: dict[str, Quaternion],
                     ) -> bpy.types.Action:
    clip = motion["clips"][clip_name]
    db_bones = motion["bones"]
    action = bpy.data.actions.new(f"EVA::{clip_name}")
    action.use_fake_user = True
    armature.animation_data.action = action
    for local_index, frame_data in enumerate(clip["frames"], start=1):
        matrices = deformation_matrices(
            frame_data, db_bones, bone_order, pivots, parents,
            bind_rotations
        )
        # PoseBone.matrix is armature-space. Multiplying the desired runtime
        # deformation by the edit-bone rest matrix lets Blender derive the
        # correct local basis while preserving Gecko's absolute-pivot chain.
        for bone_name in bone_order:
            pose_bone = armature.pose.bones[bone_name]
            rest = armature.data.bones[bone_name].matrix_local
            pose_bone.matrix = matrices[bone_name] @ rest
            pose_bone.keyframe_insert("location", frame=local_index,
                                      group=bone_name)
            pose_bone.keyframe_insert("rotation_quaternion", frame=local_index,
                                      group=bone_name)
            pose_bone.keyframe_insert("scale", frame=local_index,
                                      group=bone_name)
        for side, contact in zip(("l", "r"), frame_data["foot_contact"]):
            foot = armature.pose.bones[f"foot_{side}"]
            foot["contact"] = 1.0 if contact else 0.0
            foot.keyframe_insert('["contact"]', frame=local_index,
                                 group=f"foot_{side}")
    for curve in iter_action_fcurves(action):
        for point in curve.keyframe_points:
            point.interpolation = "LINEAR"
    armature.animation_data.action = None
    return action


def build_nla_review(armature: bpy.types.Object, motion: dict,
                     gap_frames: int, bone_order: list[str],
                     pivots: dict[str, Vector],
                     parents: dict[str, str],
                     bind_rotations: dict[str, Quaternion],
                     ) -> dict[str, tuple[int, int]]:
    sequence = [name for name in CORE_SEQUENCE if name in motion["clips"]]
    sequence.extend(sorted(set(motion["clips"]) - set(sequence)))
    actions = {
        name: make_clip_action(
            armature, motion, name, bone_order, pivots, parents,
            bind_rotations
        )
        for name in sequence
    }
    track = armature.animation_data.nla_tracks.new()
    track.name = "EVA REVIEW SEQUENCE"
    frame_cursor = 1
    ranges = {}
    for name in sequence:
        action = actions[name]
        strip = track.strips.new(name, frame_cursor, action)
        strip.extrapolation = "NOTHING"
        strip.blend_type = "REPLACE"
        strip.action_frame_start = 1.0
        strip.action_frame_end = float(len(motion["clips"][name]["frames"]))
        end = int(round(strip.frame_end))
        ranges[name] = (frame_cursor, end)
        bpy.context.scene.timeline_markers.new(name.upper(), frame=frame_cursor)
        frame_cursor = end + gap_frames + 1
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = max(1, frame_cursor - gap_frames - 1)
    bpy.context.scene.frame_set(1)
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
    rig_collection = make_collection("10_EVA_ARMATURE")
    mesh_collection = make_collection("20_EVA_WEIGHTED_MESH")
    contact_collection = make_collection("30_CONTACT_DEBUG")
    source_collection = make_collection("40_CC0_HUMAN_REFERENCE")
    add_stage(stage)

    bones, pivots, parents = load_geo(args.geo)
    bind_rotations = geometry_bind_rotations(bones)
    master, armature = build_armature(
        bones, pivots, parents, rig_collection, args.display_scale
    )
    build_weighted_mesh(args.mesh, armature, master, mesh_collection,
                        make_material(args.texture))
    for side in ("l", "r"):
        make_contact_marker(
            f"CONTACT_{side.upper()}_PLANTED", (0.05, 1.0, 0.18, 1.0),
            armature, f"foot_{side}", contact_collection, True
        )
        make_contact_marker(
            f"CONTACT_{side.upper()}_AIR", (1.0, 0.05, 0.03, 1.0),
            armature, f"foot_{side}", contact_collection, False
        )
    motion = json.loads(args.motion_db.read_text(encoding="utf-8"))
    armature.animation_data_create()
    ranges = build_nla_review(
        armature, motion, args.gap_frames,
        [bone["name"] for bone in bones], pivots, parents,
        bind_rotations
    )
    if args.source_human is not None and args.source_human.is_file():
        add_source_human(args.source_human, ranges, source_collection)
    add_readme(motion, ranges)
    scene["project_seele_motion_lab_armature"] = True
    scene["clip_count"] = len(ranges)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    print(
        f"EVA armature lab: clips={len(ranges)} actions={len(bpy.data.actions)} "
        f"frames={scene.frame_end} objects={len(scene.objects)} output={args.output}"
    )


if __name__ == "__main__":
    main()
