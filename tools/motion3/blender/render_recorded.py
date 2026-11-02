"""Render an EVA from runtime pose records (the transition tour's poses.jsonl).

blender -b --factory-startup --python render_recorded.py -- --assets <dir> --poses <poses.jsonl> \
    --variant 1 --mesh <skinned body mesh> --hands <anatomical hands mesh> \
    --weapons <dir with rifle/knife meshes> --fps 60 --out <frames dir>

Each record holds the final GeckoLib bone channels the game drew at one
tick (radians, model pixels; X position mirrored as GeckoLib applies it),
the hidden flag of every bone, and the entity position.  Records are
interpolated on their exact entity time, so the frames show the runtime
poses at a steady frame rate without launching the game.

The anatomical hands are skinned here the way the game skins them: dual
quaternions over model(bone) * inverse bind, with the recorded finger
joints.  Body parts the game hid, and its blocky hands while the anatomical
ones draw, stay hidden.  The weapon in hand follows the pose key's weapon
id.  labels.json (frame -> label) follows the tour script.
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
import numpy as np  # noqa: E402

import gecko_fk as fk  # noqa: E402
import seele_lab as lab  # noqa: E402
from hand_lab import dq_skin  # noqa: E402
from render_pack_sequence import setup_world  # noqa: E402

UNIT = {0: "eva_unit00", 1: "eva_unit01", 2: "eva_unit02", 4: "eva_un01"}
RENDER_SCALE = 5.0
WEAPON_KNIFE, WEAPON_RIFLE = 1, 4
# EvaConnectedActionReview.tour(): (first tick, label)
TOUR = [(0, "空手 · 待机"), (40, "空手 · 起步走"), (70, "空手 · 跑"), (110, "空手 · 跑→走"), (140, "空手 · 停下"),
        (170, "空手 · 普通攻击连击（左键×4）"), (230, "空手 · 重击（右键）"), (290, "空手 · 踢（B 键）"),
        (340, "空手 · 蹲下"), (360, "空手 · 蹲走"), (420, "空手 · 蹲姿"), (470, "空手 · 趴下"), (500, "空手 · 匍匐"),
        (580, "空手 · 趴姿"), (600, "空手 · 起身"), (610, "空手 · 原地转身"), (660, "换枪"), (680, "持枪 · 站射"), (720, "持枪 · 行进射击"),
        (800, "持枪 · 停下射击"), (820, "持枪 · 蹲下"), (840, "持枪 · 蹲行射击"), (900, "持枪 · 蹲姿"),
        (920, "持枪 · 起身"), (940, "持枪 · 卧倒"), (970, "持枪 · 卧射"), (1000, "持枪 · 卧姿匍匐"),
        (1060, "持枪 · 卧姿"), (1080, "持枪 · 起身、转身"), (1130, "换刀"), (1150, "持刀 · 连击（左键×3）"),
        (1220, "持刀 · 重击（右键）"), (1270, "持刀 · 走"), (1330, "持刀 · 停下"), (1340, "持刀 · 趴下"),
        (1370, "持刀 · 卧姿连击（左键×3）"), (1430, "持刀 · 卧姿重击（右键）"), (1470, "持刀 · 卧姿匍匐"),
        (1530, "持刀 · 卧姿"), (1550, "持刀 · 起身")]


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True)
    ap.add_argument("--poses", required=True)
    ap.add_argument("--variant", type=int, default=1)
    ap.add_argument("--mesh", default="")
    ap.add_argument("--hands", default="")
    ap.add_argument("--weapons", default="")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=-1)
    ap.add_argument("--focus", default="", help="JSON list of {from, to, bone, dist, az, el, label} close-up segments in tour ticks")
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


def label_at(tick):
    text = TOUR[0][1]
    for t, name in TOUR:
        if tick >= t:
            text = name
    return text


def angle_lerp(a, b, t):
    return a + ((b - a + 180.0) % 360.0 - 180.0) * t


def drawn(row):
    return row.get("drawnPosition", row["world"]), row.get("bodyYaw", row.get("yaw", 0.0))


def weapon_of(row):
    head = row.get("key", "").split(":", 1)[0]
    return int(head) if head.isdigit() else -1


class Hands:
    """Anatomical hands skinned per frame from the recorded joints."""

    def __init__(self, path, material):
        mesh = lab.load_json(path)
        stride = mesh.get("stride", 8)
        self.sides = []
        for side in ("l", "r"):
            part, skin = mesh["parts"]["hand_" + side], mesh["jointSkins"]["hand_" + side]
            raw = np.asarray(part["vertices"], float).reshape(-1, stride)
            piv = np.asarray(part["pivot"], float)
            pts = np.stack([-(raw[:, 0] + piv[0]) / 16, (raw[:, 1] + piv[1]) / 16, (raw[:, 2] + piv[2]) / 16], 1)
            # Unindexed triangles: weld equal rest corners so the surface shades smooth.
            key = np.round(pts, 6)
            unique, index = np.unique(key, axis=0, return_inverse=True)
            index = index.reshape(-1)
            first = np.zeros(len(unique), int)
            first[index[::-1]] = np.arange(len(index))[::-1]
            weights = {b: np.asarray(w, float)[first] for b, w in skin["influences"].items()}
            inverse = {b: np.array(v, float).reshape(4, 4).T for b, v in skin.get("inverseBindColumnMajor", {}).items()}
            me = bpy.data.meshes.new("anatomical_hand_" + side)
            me.from_pydata(pts[first].tolist(), [], index.reshape(-1, 3).tolist())
            uv = me.uv_layers.new(name="UV")
            uv.data.foreach_set("uv", np.stack([raw[:, 3], 1.0 - raw[:, 4]], 1).ravel())
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
            me.update()
            ob = bpy.data.objects.new("anatomical_hand_" + side, me)
            ob.data.materials.append(material)
            bpy.context.scene.collection.objects.link(ob)
            self.sides.append((side, pts[first], weights, inverse, ob))

    def pose(self, mats, placement, visible):
        for side, pts, weights, inverse, ob in self.sides:
            ob.hide_render = not visible[side]
            if not visible[side]:
                continue
            skin = {b: mats[b] @ inverse.get(b, np.eye(4)) for b in weights if b in mats}
            out = dq_skin(pts, weights, skin)
            bl = np.stack([out[:, 0], -out[:, 2], out[:, 1]], 1)
            ob.data.vertices.foreach_set("co", bl.ravel())
            ob.data.update()
            ob.matrix_world = placement


def main():
    a = parse()
    rows = [json.loads(line) for line in open(a.poses, encoding="utf-8") if line.strip()]
    rows.sort(key=lambda r: r["entityTick"])
    times = [r["entityTick"] for r in rows]
    t0 = times[0]
    origin = mathutils.Vector(drawn(rows[0])[0])
    lab.clear_scene()
    base = os.path.join(a.assets, "assets", "projectseele")
    unit = UNIT[a.variant]
    rig = fk.load_rig(os.path.join(base, "geo", unit + ".geo.json"))
    arm = lab.build_armature(lab.geo_bones(os.path.join(base, "geo", unit + ".geo.json")), unit)
    texture = os.path.join(base, "textures", "entity", unit + ".png")
    body = lab.load_mesh_skinned(arm, a.mesh or os.path.join(base, "mesh", unit + ".mesh.json"), texture, "body")
    parts = {ob.name[len("body_"):]: ob for ob in body}
    hands = None
    if a.hands:
        hands = Hands(a.hands, body[0].data.materials[0])
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
    cam_pos = cam_yaw = None
    focus = json.load(open(a.focus, encoding="utf-8")) if a.focus else []
    shot = None
    for fi in range(end):
        t = t0 + fi / a.fps * 20.0
        i = max(0, min(len(rows) - 2, bisect.bisect_right(times, t) - 1))
        r0, r1 = rows[i], rows[i + 1]
        span = max(1e-6, r1["entityTick"] - r0["entityTick"])
        w = max(0.0, min(1.0, (t - r0["entityTick"]) / span))
        near = r0 if w < 0.5 else r1
        tick = r0["tick"] + (r1["tick"] - r0["tick"]) * w
        labels[fi] = label_at(tick)
        if focus:
            current = next((s for s in focus if s["from"] <= tick < s["to"]), None)
            if current is None:
                shot = None
                continue
            if current is not shot:
                shot, cam_pos, cam_yaw = current, None, None
            labels[fi] = current.get("label", labels[fi])
        states = {}
        for name, c0 in r0["bones"].items():
            c1 = r1["bones"].get(name, c0)
            states[name] = fk.blend_states(fk.channel_state(c0), fk.channel_state(c1), w)
            pb = arm.pose.bones.get(name)
            if pb is None:
                continue
            q, pos = states[name]
            pb.rotation_quaternion = lab.quat_model_to_blender(mathutils.Quaternion(q))
            pb.location = lab.model_to_blender(mathutils.Vector(pos))
        # The game skips the blocky body hands while the anatomical ones draw.
        anatomical = hands is not None and near.get("anatomicalHands", True)
        for name, ob in parts.items():
            c = near["bones"].get(name)
            ob.hide_render = bool(c is not None and len(c) > 6 and c[6]) or anatomical and name.startswith(("hand_", "finger_"))
        (p0, y0), (p1, y1) = drawn(r0), drawn(r1)
        world = mathutils.Vector(p0).lerp(mathutils.Vector(p1), w) - origin
        yaw = angle_lerp(y0, y1, w)
        # The scene is the model frame of yaw 0, which faces world +Z: a world
        # offset maps to (-x, y, -z) / render scale, and a heading turns the
        # model by -yaw about its vertical (Blender Z).
        arm.location = lab.model_to_blender(mathutils.Vector((-world.x, world.y, -world.z)) / RENDER_SCALE)
        arm.rotation_mode = 'XYZ'
        arm.rotation_euler = (0.0, 0.0, math.radians(-yaw))
        weapon = weapon_of(near)
        for objs, held in ((rifle, WEAPON_RIFLE), (knife, WEAPON_KNIFE)):
            for ob in objs:
                ob.hide_render = weapon != held
        bpy.context.view_layer.update()
        if hands and fi >= a.start:
            mats = fk.model_matrices(rig, states)
            hands.pose(mats, arm.matrix_world.copy(), {"l": anatomical, "r": anatomical})
        pelvis = arm.matrix_world @ arm.pose.bones["torso_lower"].head
        target = mathutils.Vector((pelvis.x, pelvis.y, max(2.0, pelvis.z * 0.95 + 1.0)))
        ease = 1 - 0.88 ** (30.0 / a.fps)
        cam_yaw = yaw if cam_yaw is None else angle_lerp(cam_yaw, yaw, ease * 0.5)
        # front-left of the EVA, turning with it
        offset = mathutils.Vector((-14.0, 17.0, 1.5))
        if shot:
            names = shot["bone"].split("+")
            target = sum((arm.matrix_world @ arm.pose.bones[n].head for n in names), mathutils.Vector()) / len(names)
            az, el = math.radians(shot.get("az", -40)), math.radians(shot.get("el", 10))
            offset = mathutils.Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))) * shot.get("dist", 6)
        want = target + mathutils.Matrix.Rotation(math.radians(-cam_yaw), 3, 'Z') @ offset
        cam_pos = want if cam_pos is None else cam_pos.lerp(want, ease)
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
