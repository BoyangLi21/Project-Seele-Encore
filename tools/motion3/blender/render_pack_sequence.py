"""Render an in-game-equivalent locomotion sequence from a SEELE motion pack.

The server signals are simulated the way EvaUnit01Entity produces them
(friction-limited ground speed, move/run/dash blends approached per tick,
gait phase advanced by distance / pack stride) and the pose is blended the
way com.projectseele.anim.EvaAnimator blends it, so the frames show what the
game draws.

blender -b --factory-startup --python render_pack_sequence.py -- --assets <dir> --pack <pack.json> \
    --variant 1 --script "idle:3,walk:6,run:5,dash:4,run:2,walk:3,idle:3" --view three --out <frames dir>
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

UNIT = {0: "eva_unit00", 1: "eva_unit01", 2: "eva_unit02", 4: "eva_un01"}
# EvaUnit01Entity.drivingSpeedR30 walk/sprint per variant; dash multiplies by 1.2
SPEED = {0: (0.36, 0.65), 1: (0.42, 0.78), 2: (0.48, 0.90), 4: (0.42, 0.78)}
RENDER_SCALE = 5.0
FRICTION = 0.6 * 0.91


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--variant", type=int, default=1)
    ap.add_argument("--script", default="idle:3,walk:6,run:5,dash:4,run:2,walk:3,idle:3")
    ap.add_argument("--view", default="three")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mesh", default="", help="override body mesh json")
    ap.add_argument("--offset-x", type=float, default=0.0)
    return ap.parse_args(argv)


def simulate(script, variant):
    """Per-tick server state: distance (world blocks), phase, move, run, dash, speed."""
    walk_speed, sprint_speed = SPEED[variant]
    ticks = []
    v = 0.0
    dist = 0.0
    phase = 0.0
    move = run = dash = 0.0
    for mode, seconds in script:
        for _ in range(int(round(seconds * 20))):
            moving_input = mode != "idle"
            sprinting = mode in ("run", "dash")
            dashing = mode == "dash"
            dash = approach(dash, 1.0 if dashing else 0.0, 0.1)
            speed = (sprint_speed if sprinting else walk_speed) * (1 + 0.2 * dash)
            a = speed * 0.21600002 / FRICTION ** 3 if moving_input else 0.0
            step = v + a
            v = step * FRICTION
            moving = step > 0.006
            move = approach(move, 1.0 if moving else 0.0, 0.16)
            run = approach(run, 1.0 if moving and sprinting else 0.0, 0.14)
            ticks.append({"dist": dist, "step": step, "move": move, "run": run, "dash": dash, "phase": phase})
            dist += step
            # stride in world blocks from the pack (filled in later)
            ticks[-1]["advance"] = step
    return ticks


def approach(x, target, d):
    return min(target, x + d) if x < target else max(target, x - d)


class Clip:
    def __init__(self, c):
        self.bones = c["bones"]
        self.frames = c["frames"]
        self.rate = c["rate"]
        self.loop = c["loop"]
        self.duration = c["duration"]
        self.stride = c["stride"]
        self.rot = c["rot"]
        self.root = c["root"]

    def pos(self, phase):
        p = phase - math.floor(phase)
        return p * self.frames

    def accumulate(self, frame_pos, w, acc, root):
        f0 = int(math.floor(frame_pos))
        t = frame_pos - f0
        f0 %= self.frames
        f1 = (f0 + 1) % self.frames
        nb = len(self.bones)
        for i, n in enumerate(self.bones):
            o0 = (f0 * nb + i) * 4
            o1 = (f1 * nb + i) * 4
            qa = mathutils.Quaternion(self.rot[o0:o0 + 4])
            qb = mathutils.Quaternion(self.rot[o1:o1 + 4])
            q = qa.slerp(qb, t)
            if n in acc:
                s = w if acc[n].dot(q) >= 0 else -w
                acc[n] = mathutils.Quaternion((acc[n].w + q.w * s, acc[n].x + q.x * s,
                                               acc[n].y + q.y * s, acc[n].z + q.z * s))
            else:
                acc[n] = mathutils.Quaternion((q.w * w, q.x * w, q.y * w, q.z * w))
        r0, r1 = f0 * 3, f1 * 3
        for k in range(3):
            root[k] += w * (self.root[r0 + k] + (self.root[r1 + k] - self.root[r0 + k]) * t)


def main():
    a = parse()
    script = [(s.split(":")[0], float(s.split(":")[1])) for s in a.script.split(",")]
    with open(a.pack, encoding="utf-8") as f:
        pack = json.load(f)
    clips = {k: Clip(v) for k, v in pack["variants"][str(a.variant)]["clips"].items()}
    ticks = simulate(script, a.variant)
    # gait phase: distance over the blended stride (EvaAnimator.strideWorld)
    phase = 0.0
    for tk in ticks:
        tk["phase"] = phase
        if tk["step"] > 0.006:
            stride = lerp(clips["walk"].stride, clips["run"].stride, tk["run"])
            stride = lerp(stride, clips["sprint"].stride, tk["dash"] * tk["run"])
            phase = (phase + tk["step"] / (stride * RENDER_SCALE)) % 1.0

    lab.clear_scene()
    base = os.path.join(a.assets, "assets", "projectseele")
    unit = UNIT[a.variant]
    geo = lab.geo_bones(os.path.join(base, "geo", unit + ".geo.json"))
    arm = lab.build_armature(geo, unit)
    objs = lab.load_mesh_skinned(arm, a.mesh or os.path.join(base, "mesh", unit + ".mesh.json"),
                               os.path.join(base, "textures", "entity", unit + ".png"), "body")
    rw, rh = (int(x) for x in a.res.split("x"))
    setup_world(rw, rh)
    lab.apply_bind_axes(arm)
    arm.location.x = a.offset_x
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.lens = 32
    bpy.context.scene.camera = cam
    os.makedirs(a.out, exist_ok=True)
    total = len(ticks) / 20.0
    nframes = int(total * a.fps)
    cam_pos = None
    for fi in range(nframes):
        t = fi / a.fps
        tick = min(len(ticks) - 2, int(t * 20))
        partial = t * 20 - tick
        s0, s1 = ticks[tick], ticks[tick + 1]
        move = lerp(s0["move"], s1["move"], partial)
        run = lerp(s0["run"], s1["run"], partial)
        dash = lerp(s0["dash"], s1["dash"], partial)
        ph1 = s1["phase"] if s1["phase"] >= s0["phase"] else s1["phase"] + 1
        ph = lerp(s0["phase"], ph1, partial) % 1.0
        dist = lerp(s0["dist"], s1["dist"], partial) / RENDER_SCALE  # model units
        w_idle = 1 - move
        w_walk = move * (1 - run)
        w_run = move * run * (1 - dash)
        w_sprint = move * run * dash
        acc, root = {}, [0.0, 0.0, 0.0]
        if w_idle > 1e-3:
            idle = clips["idle"]
            idle.accumulate(((t / idle.duration) % 1.0) * idle.frames, w_idle, acc, root)
        for name, w in (("walk", w_walk), ("run", w_run), ("sprint", w_sprint)):
            if w > 1e-3:
                clips[name].accumulate(clips[name].pos(ph), w, acc, root)
        for n, q in acc.items():
            pb = arm.pose.bones.get(n)
            if pb is not None:
                pb.rotation_quaternion = lab.quat_model_to_blender(q.normalized())
        arm.pose.bones["root"].location = lab.model_to_blender(mathutils.Vector(root))
        # travel along the EVA's forward (model -Z = Blender +Y)
        arm.location.y = dist
        bpy.context.view_layer.update()
        target = mathutils.Vector((a.offset_x, dist, 6.0))
        if a.view == "side":
            want = target + mathutils.Vector((-30.0, 0.0, -2.5))
        elif a.view == "lineup":
            want = target + mathutils.Vector((-30.0, 26.0, 2.0))
        else:
            want = target + mathutils.Vector((-18.0, 23.0, 2.0))
        cam_pos = want if cam_pos is None else cam_pos.lerp(want, 0.25)
        cam.location = cam_pos
        cam.rotation_euler = (target - cam_pos).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.scene.render.filepath = os.path.join(a.out, f"f{fi:05d}.png")
        bpy.ops.render.render(write_still=True)
    print("rendered", nframes, "frames")


def lerp(x, y, t):
    return x + (y - x) * t


def setup_world(w, h):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    try:
        sc.eevee.taa_render_samples = 16
    except AttributeError:
        pass
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.58, 0.66, 0.78, 1.0)
    bg.inputs[1].default_value = 0.8
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", type='SUN'))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(42), math.radians(-18), math.radians(-35))
    sc.collection.objects.link(sun)
    # 400 x 400 model-unit floor, 2-unit checker (10 world blocks) to read foot planting
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 150, 0))
    floor = bpy.context.active_object
    m = bpy.data.materials.new("floor")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.9
    chk = nt.nodes.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = 200.0
    chk.inputs["Color1"].default_value = (0.42, 0.43, 0.42, 1)
    chk.inputs["Color2"].default_value = (0.30, 0.31, 0.30, 1)
    nt.links.new(chk.outputs["Color"], bsdf.inputs["Base Color"])
    floor.data.materials.append(m)


if __name__ == "__main__":
    main()
