"""Retarget a BVH onto an EVA and render preview frames.

blender -b --factory-startup --python preview_retarget.py -- \
    --assets <private asset root> --body <eva_body_r44.json> --variant 1 \
    --bvh <file.bvh> --skeleton bandai --calib-bvh <neutral.bvh> --frames 0,20,40 --out <dir>
"""

import argparse
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
from evarig import Rig, mat_to_quat  # noqa: E402
from retarget import Calibration, Retargeter, Source, foot_contacts  # noqa: E402

UNIT = {0: "eva_unit00", 1: "eva_unit01", 2: "eva_unit02", 4: "eva_un01"}


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--variant", type=int, default=1)
    ap.add_argument("--bvh", required=True)
    ap.add_argument("--skeleton", default="bandai")
    ap.add_argument("--calib-bvh", default="")
    ap.add_argument("--calib-frame", type=int, default=0)
    ap.add_argument("--frames", default="0")
    ap.add_argument("--views", default="three,side")
    ap.add_argument("--out", required=True)
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--res", default="480x400")
    return ap.parse_args(argv)


def apply_pose(arm, rig, local, root, f):
    for name in rig.names:
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        q = mat_to_quat(local[name][f:f + 1])[0]
        pb.rotation_quaternion = lab.quat_model_to_blender(mathutils.Quaternion(q))
        pb.location = (0, 0, 0)
    pb = arm.pose.bones.get("root")
    if pb is not None:
        pb.location = lab.model_to_blender(mathutils.Vector(root[f]))


def main():
    a = parse()
    rig = Rig.from_body_profile(a.body, a.variant)
    bvh = Bvh(a.bvh)
    src = Source(bvh, a.skeleton)
    if a.calib_bvh:
        cal = Calibration(Source(Bvh(a.calib_bvh), a.skeleton), a.calib_frame)
    else:
        cal = Calibration(src, a.calib_frame)
    res = Retargeter(rig).run(src, cal, root_motion=not a.in_place)
    contacts = {s: foot_contacts(src, s) for s in ("l", "r")}
    print("frames", src.n, "rate", src.rate, "scale", round(res["scale"], 3))

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
    (lo, hi) = lab.model_bounds(objs)
    height = hi[2] - lo[2]
    cz = height * 0.5
    d = height * 1.7
    os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.bvh))[0]
    a.tmp = os.path.join(a.out, "_frames")
    os.makedirs(a.tmp, exist_ok=True)
    rendered = {}
    frames = [int(x) for x in a.frames.split(",") if x] if ":" not in a.frames else         list(range(*[int(x) for x in a.frames.split(":")]))
    for fi in frames:
        f = min(fi, src.n - 1)
        apply_pose(arm, rig, res["local"], res["root"], f)
        bpy.context.view_layer.update()
        rx, rz = res["root"][f][0], -res["root"][f][2]
        # the EVA faces model -Z = Blender +Y
        cams = {
            "front": lab.add_camera("front", (rx, rz + d, cz), (rx, rz, cz)),
            "side": lab.add_camera("side", (rx - d, rz, cz), (rx, rz, cz)),
            "three": lab.add_camera("three", (rx - d * 0.7, rz + d * 0.7, cz + height * 0.15), (rx, rz, cz)),
        }
        for v in a.views.split(","):
            p = os.path.join(a.tmp, f"{tag}_{f:03d}_{v}.png")
            lab.render_still(cams[v], p)
            rendered.setdefault(v, []).append(p)
        print("frame", f, "contact", bool(contacts["l"][f]), bool(contacts["r"][f]))
    for v, paths in rendered.items():
        lab.contact_sheet(paths, a.cols, os.path.join(a.out, f"{tag}_{v}_sheet.png"))


if __name__ == "__main__":
    main()
