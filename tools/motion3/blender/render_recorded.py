"""Render an EVA from runtime pose records (the transition tour's poses.jsonl).

blender -b --factory-startup --python render_recorded.py -- --assets <dir> --poses <poses.jsonl> \
    --variant 1 --mesh <skinned body mesh> --weapons <dir with rifle/knife meshes> --out <frames dir>

Each record holds the final GeckoLib bone channels the game drew at one
tick (radians, model pixels; X position mirrored as GeckoLib applies it)
and the entity position.  Records are interpolated on their exact entity
time, so the frames show the runtime poses at a steady frame rate without
launching the game.  labels.json (frame -> label) follows the tour script.
"""

import argparse
import bisect
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
RENDER_SCALE = 5.0
# EvaConnectedActionReview.tour(): (first tick, label)
TOUR = [(0, "空手 · 待机"), (40, "空手 · 起步走"), (70, "空手 · 跑"), (110, "空手 · 跑→走"), (140, "空手 · 停下"),
        (170, "空手 · 普通攻击连击（左键×4）"), (230, "空手 · 重击（右键）"), (290, "空手 · 踢（B 键）"),
        (340, "空手 · 蹲下"), (360, "空手 · 蹲走"), (420, "空手 · 蹲姿"), (470, "空手 · 趴下"), (500, "空手 · 匍匐"),
        (580, "空手 · 趴姿"), (600, "空手 · 起身"), (660, "换枪"), (680, "持枪 · 站射"), (720, "持枪 · 行进射击"),
        (800, "持枪 · 停下射击"), (820, "持枪 · 蹲下"), (840, "持枪 · 蹲行射击"), (900, "持枪 · 蹲姿"),
        (920, "持枪 · 起身"), (940, "持枪 · 卧倒"), (970, "持枪 · 卧射"), (1000, "持枪 · 卧姿匍匐"),
        (1060, "持枪 · 卧姿"), (1080, "持枪 · 起身"), (1130, "换刀"), (1150, "持刀 · 连击（左键×3）"),
        (1220, "持刀 · 重击（右键）"), (1270, "持刀 · 走"), (1330, "持刀 · 停下")]


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True)
    ap.add_argument("--poses", required=True)
    ap.add_argument("--variant", type=int, default=1)
    ap.add_argument("--mesh", default="")
    ap.add_argument("--weapons", default="")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=-1)
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


def channel_quat(c):
    # rotationZYX(rz, ry, rx): X applied first
    return mathutils.Euler((c[0], c[1], c[2]), 'XYZ').to_quaternion()


def channel_pos(c):
    return mathutils.Vector((-c[3] / 16.0, c[4] / 16.0, c[5] / 16.0))


def label_at(tick):
    text = TOUR[0][1]
    for t, name in TOUR:
        if tick >= t:
            text = name
    return text


def main():
    a = parse()
    rows = [json.loads(line) for line in open(a.poses, encoding="utf-8") if line.strip()]
    rows.sort(key=lambda r: r["entityTick"])
    times = [r["entityTick"] for r in rows]
    t0 = times[0]
    origin = mathutils.Vector(rows[0]["world"])
    lab.clear_scene()
    base = os.path.join(a.assets, "assets", "projectseele")
    unit = UNIT[a.variant]
    arm = lab.build_armature(lab.geo_bones(os.path.join(base, "geo", unit + ".geo.json")), unit)
    lab.load_mesh_skinned(arm, a.mesh or os.path.join(base, "mesh", unit + ".mesh.json"),
                          os.path.join(base, "textures", "entity", unit + ".png"), "body")
    rifle = knife = []
    if a.weapons:
        rifle = lab.load_mesh_parts(arm, os.path.join(a.weapons, "eva_pallet_smg.mesh.json"),
                                    os.path.join(a.weapons, "eva_pallet_smg.png"), "rifle")
        knife = lab.load_mesh_parts(arm, os.path.join(a.weapons, "progressive_knife_anatomical_r45.mesh.json"),
                                    os.path.join(a.weapons, "progressive_knife.png"), "knife")
    rw, rh = (int(x) for x in a.res.split("x"))
    setup_world(rw, rh)
    floor = next(o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("Plane"))
    floor.scale = (10.0, 10.0, 1.0)
    floor.location.y = 0.0
    for node in floor.data.materials[0].node_tree.nodes:
        if node.type == 'TEX_CHECKER':
            node.inputs["Scale"].default_value *= 10.0
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.lens = 29
    bpy.context.scene.camera = cam
    os.makedirs(a.out, exist_ok=True)
    total = int((times[-1] - t0) / 20.0 * a.fps)
    end = total if a.end < 0 else min(total, a.end)
    labels = {}
    cam_pos = None
    for fi in range(end):
        t = t0 + fi / a.fps * 20.0
        i = max(0, min(len(rows) - 2, bisect.bisect_right(times, t) - 1))
        r0, r1 = rows[i], rows[i + 1]
        span = max(1e-6, r1["entityTick"] - r0["entityTick"])
        w = max(0.0, min(1.0, (t - r0["entityTick"]) / span))
        tick = r0["tick"] + (r1["tick"] - r0["tick"]) * w
        labels[fi] = label_at(tick)
        for name, c0 in r0["bones"].items():
            pb = arm.pose.bones.get(name)
            c1 = r1["bones"].get(name, c0)
            if pb is None:
                continue
            q = channel_quat(c0).slerp(channel_quat(c1), w)
            pb.rotation_quaternion = lab.quat_model_to_blender(q)
            pb.location = lab.model_to_blender(channel_pos(c0).lerp(channel_pos(c1), w))
        world = mathutils.Vector(r0["world"]).lerp(mathutils.Vector(r1["world"]), w) - origin
        # yaw 0 faces world +Z, which is model -Z: model = (-x, y, -z) / render scale
        arm.location = lab.model_to_blender(mathutils.Vector((-world.x, world.y, -world.z)) / RENDER_SCALE)
        for objs, lo, hi in ((rifle, 665, 1135), (knife, 1135, 10 ** 6)):
            for ob in objs:
                ob.hide_render = not (lo <= tick < hi)
        bpy.context.view_layer.update()
        pelvis = arm.matrix_world @ arm.pose.bones["torso_lower"].head
        target = mathutils.Vector((pelvis.x, pelvis.y, max(2.0, pelvis.z * 0.95 + 1.0)))
        want = target + mathutils.Vector((-14.0, 17.0, 1.5))
        cam_pos = want if cam_pos is None else cam_pos.lerp(want, 0.12)
        cam.location = cam_pos
        cam.rotation_euler = (target - cam_pos).to_track_quat('-Z', 'Y').to_euler()
        # frames before --start are posed only, so the follow camera arrives settled
        if fi < a.start:
            continue
        bpy.context.scene.render.filepath = os.path.join(a.out, f"f{fi:05d}.png")
        bpy.ops.render.render(write_still=True)
    with open(os.path.join(a.out, "labels.json"), "w", encoding="utf-8") as f:
        json.dump({"fps": a.fps, "labels": labels}, f, ensure_ascii=False)
    print("rendered", end - a.start, "of", total, "frames")


if __name__ == "__main__":
    main()
