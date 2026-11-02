"""Render a paired EVA + Angel performance built by paired_exec.py.

blender -b --factory-startup --python render_paired.py -- --assets <dir> --paired <paired.json> \
    --variant 1 --angel sachiel --mesh <eva skinned mesh> --out <frames dir> [--fps 30] [--slow 1.25]
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import mathutils  # noqa: E402

import seele_lab as lab  # noqa: E402
from render_pack_sequence import setup_world  # noqa: E402

UNIT = {0: "eva_unit00", 1: "eva_unit01", 2: "eva_unit02", 4: "eva_un01"}


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True)
    ap.add_argument("--paired", required=True)
    ap.add_argument("--variant", type=int, default=1)
    ap.add_argument("--angel", default="sachiel")
    ap.add_argument("--mesh", default="")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--slow", type=float, default=1.0, help="giant timing: >1 plays slower")
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--view", default="side")
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


def apply(arm, tr, f, frames):
    bones = tr["bones"]
    nb = len(bones)
    f0 = int(math.floor(f))
    w = f - f0
    f0 = max(0, min(frames - 1, f0))
    f1 = min(frames - 1, f0 + 1)
    for i, n in enumerate(bones):
        pb = arm.pose.bones.get(n)
        if pb is None:
            continue
        o0, o1 = (f0 * nb + i) * 4, (f1 * nb + i) * 4
        q = mathutils.Quaternion(tr["rot"][o0:o0 + 4]).slerp(mathutils.Quaternion(tr["rot"][o1:o1 + 4]), w)
        pb.rotation_quaternion = lab.quat_model_to_blender(q.normalized())
    r = mathutils.Vector(tr["root"][f0 * 3:f0 * 3 + 3]).lerp(mathutils.Vector(tr["root"][f1 * 3:f1 * 3 + 3]), w)
    arm.pose.bones["root"].location = lab.model_to_blender(r)


def main():
    a = parse()
    with open(a.paired, encoding="utf-8") as f:
        P = json.load(f)
    lab.clear_scene()
    base = os.path.join(a.assets, "assets", "projectseele")
    unit = UNIT[a.variant]
    eva = lab.build_armature(lab.geo_bones(os.path.join(base, "geo", unit + ".geo.json")), unit)
    lab.load_mesh_skinned(eva, a.mesh or os.path.join(base, "mesh", unit + ".mesh.json"),
                          os.path.join(base, "textures", "entity", unit + ".png"), "body")
    angel = lab.build_armature(lab.geo_bones(os.path.join(base, "geo", a.angel + ".geo.json")), a.angel)
    lab.load_mesh_skinned(angel, os.path.join(base, "mesh", a.angel + ".mesh.json"),
                          os.path.join(base, "textures", "entity", a.angel + ".png"), a.angel)
    rw, rh = (int(x) for x in a.res.split("x"))
    setup_world(rw, rh)
    lab.apply_bind_axes(eva)
    lab.apply_bind_axes(angel)
    for arm, key in ((eva, "eva"), (angel, "angel")):
        arm.rotation_euler = (0.0, 0.0, math.radians(P[key]["yaw"]))
        arm.location = lab.model_to_blender(mathutils.Vector(P[key]["offset"]))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.lens = 30
    bpy.context.scene.camera = cam
    os.makedirs(a.out, exist_ok=True)
    frames = P["frames"]
    total = int(frames / P["fps"] * a.slow * a.fps)
    cam_pos = None
    for fi in range(total):
        f = fi / a.fps / a.slow * P["fps"]
        apply(eva, P["eva"], f, frames)
        apply(angel, P["angel"], f, frames)
        bpy.context.view_layer.update()
        pe = eva.matrix_world @ eva.pose.bones["torso_lower"].head
        pa = angel.matrix_world @ angel.pose.bones["torso_lower"].head
        mid = (pe + pa) * 0.5
        target = mathutils.Vector((mid.x, mid.y, max(3.0, mid.z * 0.8)))
        side = mathutils.Vector((-24.0, 0.0, 3.0)) if a.view == "side" else mathutils.Vector((-17.0, 17.0, 4.0))
        want = target + side
        cam_pos = want if cam_pos is None else cam_pos.lerp(want, 0.1)
        cam.location = cam_pos
        cam.rotation_euler = (target - cam_pos).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.scene.render.filepath = os.path.join(a.out, f"f{fi:05d}.png")
        bpy.ops.render.render(write_still=True)
    print("rendered", total, "frames")


if __name__ == "__main__":
    main()
