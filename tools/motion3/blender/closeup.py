"""Close-up diagnostic renders of one body region, rest pose vs pack clip frames.

blender -b --factory-startup --python closeup.py -- --assets <dir> --pack <pack> --variant 1 \
    --clip walk --frames 0,20,40 --focus foot_l --out <dir>
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import mathutils  # noqa: E402

import seele_lab as lab  # noqa: E402

UNIT = {0: "eva_unit00", 1: "eva_unit01", 2: "eva_unit02", 4: "eva_un01"}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--variant", type=int, default=1)
    ap.add_argument("--clip", default="walk")
    ap.add_argument("--frames", default="0")
    ap.add_argument("--focus", default="foot_l")
    ap.add_argument("--dist", type=float, default=7.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mesh", default="", help="override body mesh json")
    ap.add_argument("--hands", action="store_true")
    a = ap.parse_args(argv)
    with open(a.pack, encoding="utf-8") as f:
        clip = json.load(f)["variants"][str(a.variant)]["clips"][a.clip]
    lab.clear_scene()
    base = os.path.join(a.assets, "assets", "projectseele")
    unit = UNIT[a.variant]
    geo = lab.geo_bones(os.path.join(base, "geo", unit + ".geo.json"))
    arm = lab.build_armature(geo, unit)
    lab.load_mesh_skinned(arm, a.mesh or os.path.join(base, "mesh", unit + ".mesh.json"),
                        os.path.join(base, "textures", "entity", unit + ".png"), "body")
    if a.hands:
        hp = os.path.join(base, "mesh", unit + "_anatomical_hands_r45.mesh.json")
        if os.path.isfile(hp):
            lab.load_mesh_parts(arm, hp, os.path.join(base, "textures", "entity", unit + ".png"), "hands")
    lab.setup_render(640, 640)
    lab.apply_bind_axes(arm)
    os.makedirs(a.out, exist_ok=True)
    names, nb = clip["bones"], len(clip["bones"])
    shots = [("rest", None)] + [(f"f{int(x):03d}", int(x)) for x in a.frames.split(",")]
    paths = []
    for tag, f in shots:
        for pb in arm.pose.bones:
            if "_axis_" not in pb.name:
                pb.rotation_quaternion = (1, 0, 0, 0)
            pb.location = (0, 0, 0)
        lab.apply_bind_axes(arm)
        if f is not None:
            o = f * nb * 4
            for i, n in enumerate(names):
                pb = arm.pose.bones.get(n)
                if pb is not None:
                    pb.rotation_quaternion = lab.quat_model_to_blender(mathutils.Quaternion(clip["rot"][o + i * 4:o + i * 4 + 4]))
            arm.pose.bones["root"].location = lab.model_to_blender(mathutils.Vector(clip["root"][f * 3:f * 3 + 3]))
        bpy.context.view_layer.update()
        pb = arm.pose.bones[a.focus]
        c = arm.matrix_world @ pb.head
        for vname, off in (("front", (0, a.dist, 0.4)), ("out", (-a.dist if a.focus.endswith("_l") else a.dist, 0.0, 0.4)),
                           ("back", (0, -a.dist, 0.4))):
            cam = lab.add_camera("c_" + tag + vname, c + mathutils.Vector(off), c)
            p = os.path.join(a.out, f"{a.focus}_{tag}_{vname}.png")
            lab.render_still(cam, p)
            paths.append(p)
    lab.contact_sheet(paths, 3, os.path.join(a.out, f"{a.focus}_v{a.variant}_{a.clip}_closeup.png"))


if __name__ == "__main__":
    main()
