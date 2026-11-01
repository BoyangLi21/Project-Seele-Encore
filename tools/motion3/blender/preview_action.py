"""Side-by-side review of a retargeted action: EVA (pack clip), the source capture
as a stick figure scaled to EVA size, and a red target post straight ahead of
the EVA, so retarget errors can be told apart from what the actor did.

blender -b --factory-startup --python preview_action.py -- --assets <dir> --pack <pack> --variant 1 \
    --clip jab --bvh <file.bvh> --skeleton g1 --window 1036:1081 [--mirror] --out <dir>
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
import mathutils  # noqa: E402
import numpy as np  # noqa: E402

import seele_lab as lab  # noqa: E402
from bvh import Bvh  # noqa: E402
from retarget import Source  # noqa: E402

UNIT = {0: "eva_unit00", 1: "eva_unit01", 2: "eva_unit02", 4: "eva_un01"}
BONES = [("hips", "spine"), ("spine", "chest"), ("chest", "neck"), ("neck", "head"),
         ("chest", "clav_l"), ("clav_l", "arm_l"), ("arm_l", "fore_l"), ("fore_l", "hand_l"),
         ("chest", "clav_r"), ("clav_r", "arm_r"), ("arm_r", "fore_r"), ("fore_r", "hand_r"),
         ("hips", "thigh_l"), ("thigh_l", "shin_l"), ("shin_l", "foot_l"), ("foot_l", "toe_l"),
         ("hips", "thigh_r"), ("thigh_r", "shin_r"), ("shin_r", "foot_r"), ("foot_r", "toe_r")]


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--variant", type=int, default=1)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--bvh", required=True)
    ap.add_argument("--skeleton", default="g1")
    ap.add_argument("--window", required=True)
    ap.add_argument("--mirror", action="store_true")
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--views", default="front,side,top")
    ap.add_argument("--res", default="420x420")
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


def stick_object(name):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = 0.16
    cu.bevel_resolution = 2
    for _ in BONES:
        sp = cu.splines.new('POLY')
        sp.points.add(1)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new(name + "_m")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.95, 0.75, 0.1, 1)
    cu.materials.append(mat)
    return ob


def set_sticks(ob, pts):
    for sp, (a, b) in zip(ob.data.splines, BONES):
        pa, pb = pts[a], pts[b]
        sp.points[0].co = (pa.x, pa.y, pa.z, 1.0)
        sp.points[1].co = (pb.x, pb.y, pb.z, 1.0)


def main():
    a = parse()
    with open(a.pack, encoding="utf-8") as f:
        clip = json.load(f)["variants"][str(a.variant)]["clips"][a.clip]
    fa, fb = (int(x) for x in a.window.split(":"))
    bvh = Bvh(a.bvh)
    src = Source(bvh, a.skeleton, align_frame=fa)
    if a.mirror:
        src = src.mirrored()
    # scale the source to EVA leg length (same as the retargeter)
    lab.clear_scene()
    base = os.path.join(a.assets, "assets", "projectseele")
    unit = UNIT[a.variant]
    geo = lab.geo_bones(os.path.join(base, "geo", unit + ".geo.json"))
    arm = lab.build_armature(geo, unit)
    objs = lab.load_mesh_parts(arm, os.path.join(base, "mesh", unit + ".mesh.json"),
                               os.path.join(base, "textures", "entity", unit + ".png"), "body")
    rw, rh = (int(x) for x in a.res.split("x"))
    lab.setup_render(rw, rh)
    lab.apply_bind_axes(arm)
    piv = {g["name"]: lab.px_to_model(g["pivot"]) for g in geo}
    leg_t = (piv["shin_l"] - piv["leg_l"]).length + (piv["ankle_l"] - piv["shin_l"]).length
    P = src.P
    leg_s = np.mean(np.linalg.norm(P["shin_l"] - P["thigh_l"], axis=1) + np.linalg.norm(P["foot_l"] - P["shin_l"], axis=1))
    scale = leg_t / leg_s
    floor = min(P["foot_l"][:, 1].min(), P["foot_r"][:, 1].min())
    stick = stick_object("source")
    # target post 9 model units straight ahead of the EVA (model -Z = Blender +Y)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.6, depth=14, location=(0, 9, 7))
    post = bpy.context.active_object
    pm = bpy.data.materials.new("post")
    pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.9, 0.08, 0.05, 1)
    post.data.materials.append(pm)
    names, nb = clip["bones"], len(clip["bones"])
    tmp = os.path.join(a.out, "_frames")
    os.makedirs(tmp, exist_ok=True)
    cams = {
        "front": lab.add_camera("front", (0, 34, 7), (0, 0, 6)),
        "side": lab.add_camera("side", (-34, 2, 7), (0, 2, 6)),
        "top": lab.add_camera("top", (0.01, 3, 40), (0, 3, 0)),
    }
    cams["top"].data.lens = 30
    rendered = {}
    L = fb - fa
    for k in range(a.samples):
        t = k / (a.samples - 1)
        f = min(clip["frames"] - 1, int(round(t * (clip["frames"] - 1))))
        o = f * nb * 4
        for i, n in enumerate(names):
            pb = arm.pose.bones.get(n)
            if pb is not None:
                pb.rotation_quaternion = lab.quat_model_to_blender(mathutils.Quaternion(clip["rot"][o + i * 4:o + i * 4 + 4]))
        tr = clip.get("trajectory", [0.0] * (3 * clip["frames"]))
        root = mathutils.Vector(clip["root"][f * 3:f * 3 + 3]) + mathutils.Vector(tr[f * 3:f * 3 + 3])
        arm.pose.bones["root"].location = lab.model_to_blender(root)
        sf = fa + int(round(t * L))
        pts = {}
        for key in {x for pair in BONES for x in pair}:
            p = P[key][sf] * scale
            p[1] -= floor * scale
            p[0] += 9.0  # stand the source figure to the EVA's right
            pts[key] = lab.model_to_blender(mathutils.Vector(p))
        set_sticks(stick, pts)
        bpy.context.view_layer.update()
        for v in a.views.split(","):
            p = os.path.join(tmp, f"{a.clip}_{k:02d}_{v}.png")
            lab.render_still(cams[v], p)
            rendered.setdefault(v, []).append(p)
    for v, paths in rendered.items():
        lab.contact_sheet(paths, 6, os.path.join(a.out, f"{a.clip}_{v}_compare.png"))


if __name__ == "__main__":
    main()
