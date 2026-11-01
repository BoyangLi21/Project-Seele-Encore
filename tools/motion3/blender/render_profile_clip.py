"""Render frames of an existing runtime profile clip on the runtime EVA mesh.

blender -b --factory-startup --python render_profile_clip.py -- \
    --assets <dir with assets/projectseele> --profile <eva_body_r44.json|eva_gameplay_r44_N.json> \
    --variant 1 --clip walk --frames 0,10,20 --out <dir> [--view front|side|three]
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seele_lab as lab  # noqa: E402

UNIT = {0: "eva_unit00", 1: "eva_unit01", 2: "eva_unit02", 4: "eva_un01"}


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--variant", type=int, default=1)
    ap.add_argument("--clip", default="")
    ap.add_argument("--frames", default="0")
    ap.add_argument("--out", required=True)
    ap.add_argument("--view", default="three")
    ap.add_argument("--hands", action="store_true")
    return ap.parse_args(argv)


def main():
    a = parse()
    lab.clear_scene()
    base = os.path.join(a.assets, "assets", "projectseele")
    unit = UNIT[a.variant]
    rig = lab.geo_bones(os.path.join(base, "geo", unit + ".geo.json"))
    arm = lab.build_armature(rig, unit)
    objs = lab.load_mesh_parts(arm, os.path.join(base, "mesh", unit + ".mesh.json"),
                               os.path.join(base, "textures", "entity", unit + ".png"), "body")
    if a.hands:
        hands = os.path.join(base, "mesh", unit + "_anatomical_hands_r45.mesh.json")
        if os.path.isfile(hands):
            objs += lab.load_mesh_parts(arm, hands, os.path.join(base, "textures", "entity", unit + ".png"), "hands")
    lab.setup_render()
    lab.apply_bind_axes(arm)
    os.makedirs(a.out, exist_ok=True)
    clip = None
    names = None
    if a.clip:
        prof = lab.load_json(a.profile)
        motion = prof["motion"] if "motion" in prof else prof
        names = motion["bones"]
        clip = motion["clips"][a.clip]
        print("clip", a.clip, "frames", len(clip["frames"]), "duration", clip.get("duration_seconds"))
    (lo, hi) = lab.model_bounds(objs)
    height = hi[2] - lo[2]
    cz = height * 0.5
    d = height * 1.6
    cams = {
        "front": lab.add_camera("front", (0, -d, cz), (0, 0, cz)),
        "side": lab.add_camera("side", (d, 0, cz), (0, 0, cz)),
        "three": lab.add_camera("three", (d * 0.7, -d * 0.7, cz + height * 0.15), (0, 0, cz)),
    }
    print("model height blocks", round(height, 2))
    for fi in [int(x) for x in a.frames.split(",") if x != ""]:
        if clip is not None:
            frames = clip["frames"]
            lab.apply_frame(arm, names, frames[min(fi, len(frames) - 1)])
            lab.apply_bind_axes(arm)
        bpyctx_update()
        for view in a.view.split(","):
            lab.render_still(cams[view], os.path.join(a.out, f"{a.clip or 'rest'}_{fi:03d}_{view}.png"))


def bpyctx_update():
    import bpy
    bpy.context.view_layer.update()


if __name__ == "__main__":
    main()
