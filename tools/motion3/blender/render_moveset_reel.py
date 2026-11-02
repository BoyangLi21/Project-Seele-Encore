"""Render a continuous review reel of pack clips on one EVA.

blender -b --factory-startup --python render_moveset_reel.py -- --assets <dir> --pack <pack.json> \
    --variant 1 --reel <reel.json> --mesh <skinned mesh json> --out <frames dir>

reel.json: [{"clip": "walk_a", "seconds": 4, "label": "..."}, {"clip": "jab", "label": "..."}, ...]
A segment without "seconds" plays the clip once.  Each segment starts from
the previous one's last pose with a 0.25 s blend; loop clips travel their
stride per cycle, actions their stored trajectory, so the EVA moves through
the reel the way it would in game.  Writes frames plus labels.json
(frame -> label) for the caption pass.
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
BLEND = 0.25


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--variant", type=int, default=1)
    ap.add_argument("--reel", required=True)
    ap.add_argument("--mesh", default="")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=-1)
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


class Clip:
    def __init__(self, c):
        self.bones = c["bones"]
        self.frames = c["frames"]
        self.loop = c["loop"]
        self.duration = c["duration"]
        self.stride = c["stride"]
        self.rot = c["rot"]
        self.root = c["root"]
        self.traj = c.get("trajectory")

    def sample(self, t):
        """Pose at clip time t (seconds): ({bone: quat}, residual root, travel along -Z/x)."""
        if self.loop:
            cyc = t / self.duration
            fpos = (cyc - math.floor(cyc)) * self.frames
            travel = mathutils.Vector((0.0, 0.0, -self.stride * cyc))
        else:
            fpos = min(1.0, t / self.duration) * (self.frames - 1)
            travel = None
        f0 = int(math.floor(fpos))
        w = fpos - f0
        f1 = (f0 + 1) % self.frames if self.loop else min(f0 + 1, self.frames - 1)
        nb = len(self.bones)
        pose = {}
        for i, n in enumerate(self.bones):
            o0, o1 = (f0 * nb + i) * 4, (f1 * nb + i) * 4
            pose[n] = mathutils.Quaternion(self.rot[o0:o0 + 4]).slerp(mathutils.Quaternion(self.rot[o1:o1 + 4]), w)
        r = mathutils.Vector(self.root[f0 * 3:f0 * 3 + 3]).lerp(mathutils.Vector(self.root[f1 * 3:f1 * 3 + 3]), w)
        if travel is None:
            if self.traj:
                travel = mathutils.Vector(self.traj[f0 * 3:f0 * 3 + 3]).lerp(mathutils.Vector(self.traj[f1 * 3:f1 * 3 + 3]), w)
            else:
                travel = mathutils.Vector((0.0, 0.0, 0.0))
        return pose, r, travel

    def length(self, seconds):
        return seconds if seconds else self.duration


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def main():
    a = parse()
    with open(a.pack, encoding="utf-8") as f:
        clips = {k: Clip(v) for k, v in json.load(f)["variants"][str(a.variant)]["clips"].items()}
    with open(a.reel, encoding="utf-8") as f:
        reel = [s for s in json.load(f) if s["clip"] in clips]
    lab.clear_scene()
    base = os.path.join(a.assets, "assets", "projectseele")
    unit = UNIT[a.variant]
    geo = lab.geo_bones(os.path.join(base, "geo", unit + ".geo.json"))
    arm = lab.build_armature(geo, unit)
    lab.load_mesh_skinned(arm, a.mesh or os.path.join(base, "mesh", unit + ".mesh.json"),
                          os.path.join(base, "textures", "entity", unit + ".png"), "body")
    rw, rh = (int(x) for x in a.res.split("x"))
    setup_world(rw, rh)
    # the reel travels several hundred units: widen the floor, keep 2-unit checks
    floor = next(o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("Plane"))
    floor.scale = (10.0, 10.0, 1.0)
    floor.location.y = 1500.0
    for node in floor.data.materials[0].node_tree.nodes:
        if node.type == 'TEX_CHECKER':
            node.inputs["Scale"].default_value *= 10.0
    lab.apply_bind_axes(arm)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.lens = 29
    bpy.context.scene.camera = cam
    os.makedirs(a.out, exist_ok=True)

    # timeline
    timeline = []
    t0 = 0.0
    for seg in reel:
        d = clips[seg["clip"]].length(seg.get("seconds"))
        timeline.append((t0, d, seg))
        t0 += d
    total = int(t0 * a.fps)
    labels = {}
    origin = mathutils.Vector((0.0, 0.0, 0.0))   # accumulated travel (model space)
    seg_index = -1
    prev_pose, prev_root = None, None
    last_pose, last_root, last_travel = None, None, mathutils.Vector()
    cam_pos = None
    end = total if a.end < 0 else min(total, a.end)
    for fi in range(end):
        t = fi / a.fps
        while seg_index + 1 < len(timeline) and t >= timeline[seg_index + 1][0]:
            seg_index += 1
            if last_pose is not None:
                origin = origin + last_travel
                prev_pose, prev_root = last_pose, last_root
        start, dur, seg = timeline[seg_index]
        clip = clips[seg["clip"]]
        local = t - start
        pose, root, travel = clip.sample(local)
        w = smooth(local / BLEND) if prev_pose is not None else 1.0
        if w < 1.0:
            for n, q in pose.items():
                if n in prev_pose:
                    pose[n] = prev_pose[n].slerp(q, w)
            root = prev_root.lerp(root, w)
        last_pose, last_root, last_travel = pose, root, travel
        labels[fi] = seg.get("label", seg["clip"])
        if fi < a.start:
            continue
        for n, q in pose.items():
            pb = arm.pose.bones.get(n)
            if pb is not None:
                pb.rotation_quaternion = lab.quat_model_to_blender(q.normalized())
        world = origin + travel
        arm.pose.bones["root"].location = lab.model_to_blender(root)
        arm.location = lab.model_to_blender(world)
        bpy.context.view_layer.update()
        low = max(0.0, min(1.0, (6.0 - (root.y + 6.0)) / 4.0))
        target = arm.location + mathutils.Vector((0.0, 0.0, 6.0 - 3.5 * low))
        want = target + mathutils.Vector((-14.0, 17.0, 1.0 - 2.0 * low))
        cam_pos = want if cam_pos is None else cam_pos.lerp(want, 0.15)
        cam.location = cam_pos
        cam.rotation_euler = (target - cam_pos).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.scene.render.filepath = os.path.join(a.out, f"f{fi:05d}.png")
        bpy.ops.render.render(write_still=True)
    with open(os.path.join(a.out, "labels.json"), "w", encoding="utf-8") as f:
        json.dump({"fps": a.fps, "labels": labels}, f, ensure_ascii=False)
    print("rendered", end - a.start, "of", total, "frames")


if __name__ == "__main__":
    main()
