"""Render frames of a SEELE motion pack clip (what the Java runtime samples).

blender -b --factory-startup --python render_pack_clip.py -- --assets <dir> --pack <pack.json> \
    --variant 1 --clip walk --frames 0:76:4 --views side,front --out <dir>
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


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--variant", type=int, default=1)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--frames", default="0")
    ap.add_argument("--views", default="side,front")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--res", default="360x400")
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


def main():
    a = parse()
    with open(a.pack, encoding="utf-8") as f:
        pack = json.load(f)
    clip = pack["variants"][str(a.variant)]["clips"][a.clip]
    names = clip["bones"]
    nb = len(names)
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
    cz, d = height * 0.5, height * 1.7
    cams = {
        "front": lab.add_camera("front", (0, d, cz), (0, 0, cz)),
        "side": lab.add_camera("side", (-d, 0, cz), (0, 0, cz)),
        "three": lab.add_camera("three", (-d * 0.7, d * 0.7, cz + height * 0.15), (0, 0, cz)),
    }
    tmp = os.path.join(a.out, "_frames")
    os.makedirs(tmp, exist_ok=True)
    frames = list(range(*[int(x) for x in a.frames.split(":")])) if ":" in a.frames else \
        [int(x) for x in a.frames.split(",")]
    rendered = {}
    for f in frames:
        f %= clip["frames"]
        o = f * nb * 4
        for i, n in enumerate(names):
            pb = arm.pose.bones.get(n)
            if pb is None:
                continue
            w, x, y, z = clip["rot"][o + i * 4:o + i * 4 + 4]
            pb.rotation_quaternion = lab.quat_model_to_blender(mathutils.Quaternion((w, x, y, z)))
        r = clip["root"][f * 3:f * 3 + 3]
        arm.pose.bones["root"].location = lab.model_to_blender(mathutils.Vector(r))
        bpy.context.view_layer.update()
        for v in a.views.split(","):
            p = os.path.join(tmp, f"{a.clip}_{f:03d}_{v}.png")
            lab.render_still(cams[v], p)
            rendered.setdefault(v, []).append(p)
    for v, paths in rendered.items():
        lab.contact_sheet(paths, a.cols, os.path.join(a.out, f"{a.clip}_v{a.variant}_{v}_sheet.png"))


if __name__ == "__main__":
    main()
