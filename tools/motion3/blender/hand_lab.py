"""Render an anatomical EVA hand exactly as the game skins it.

blender -b --factory-startup --python hand_lab.py -- --assets <dir> --unit 01 --side l \
    --poses relaxed,fist,open,grab --out <dir>

The hand rig contract gives each r45 joint a pivot, a neutral local rotation
and limits; a pose control gives (flex, twist, splay) per joint and the local
rotation is neutral * Rz(side*splay) * Ry(side*twist) * Rx(-flex), exactly as
EvaAnatomicalHandsR45.rotation.  The hand mesh carries authored influences
with inverse binds; vertices are skinned here with dual quaternions over
model(b) * IB(b) (model space: pivots X-flipped / 16), the runtime's formula.
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
import numpy as np  # noqa: E402

import seele_lab as lab  # noqa: E402

STRIDE = 8
TEXTURE = {"00": "eva_unit00", "01": "eva_unit01", "02": "eva_unit02", "04": "eva_un01"}
HANDS = {"00": "eva_unit00_anatomical_hands_r45", "01": "eva_unit01_anatomical_hands_r45",
         "02": "eva_unit02_anatomical_hands_r45", "04": "eva_un01_anatomical_hands_r53"}


def qmat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def rot_zyx(z, y, x):
    cz, sz, cy, sy, cx, sx = math.cos(z), math.sin(z), math.cos(y), math.sin(y), math.cos(x), math.sin(x)
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    return Rz @ Ry @ Rx


def affine(R=None, t=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if t is not None:
        M[:3, 3] = t
    return M


def mat_quat(R):
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        return np.array([0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s])
    i = int(np.argmax([R[0, 0], R[1, 1], R[2, 2]]))
    if i == 0:
        s = math.sqrt(1 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        return np.array([(R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s])
    if i == 1:
        s = math.sqrt(1 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        return np.array([(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s])
    s = math.sqrt(1 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
    return np.array([(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s])


def qmul(a, b):
    w1, x1, y1, z1 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    w2, x2, y2, z2 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], axis=-1)


def dq_skin(points, weights, mats):
    """points (n,3); weights {bone: (n,)}; mats {bone: 4x4}. Dual-quaternion blend."""
    names = list(weights)
    real = np.array([mat_quat(mats[b][:3, :3]) for b in names])  # w,x,y,z
    t = np.array([mats[b][:3, 3] for b in names])
    tq = np.concatenate([np.zeros((len(names), 1)), t], axis=1)
    dual = 0.5 * qmul(tq, real)
    W = np.stack([weights[b] for b in names], axis=1)  # n, k
    dom = np.argmax(W, axis=1)
    sign = np.sign(np.einsum("kd,nd->nk", real, real[dom]))
    sign[sign == 0] = 1
    W = W * sign
    r = W @ real
    d = W @ dual
    norm = np.linalg.norm(r, axis=1, keepdims=True)
    r /= norm
    d /= norm
    # translation = 2 * d * conj(r)
    rc = r * np.array([1, -1, -1, -1])
    tt = 2 * qmul(d, rc)[:, 1:]
    w_, x_, y_, z_ = r[:, 0], r[:, 1], r[:, 2], r[:, 3]
    R = np.stack([np.stack([1 - 2 * (y_ * y_ + z_ * z_), 2 * (x_ * y_ - z_ * w_), 2 * (x_ * z_ + y_ * w_)], -1),
                  np.stack([2 * (x_ * y_ + z_ * w_), 1 - 2 * (x_ * x_ + z_ * z_), 2 * (y_ * z_ - x_ * w_)], -1),
                  np.stack([2 * (x_ * z_ - y_ * w_), 2 * (y_ * z_ + x_ * w_), 1 - 2 * (x_ * x_ + y_ * y_)], -1)], 1)
    return np.einsum("nij,nj->ni", R, points) + tt


class HandRig:
    def __init__(self, contract, side):
        self.side = side
        self.sign = 1.0 if side == "l" else -1.0
        self.specs = {b["name"]: b for b in contract["new_bones"]}
        self.joints = {}
        for digit, dv in contract["hands"][side]["digits"].items():
            for j in dv["joints"]:
                self.joints[j["name"]] = dict(j, digit=digit)
        self.poses = contract["pose_controls"]

    def controls(self, pose):
        p = self.poses[pose]
        out = {}
        for name, j in self.joints.items():
            v = [0.0, 0.0, 0.0]
            explicit = None
            if "bone_angles" in p and name in p["bone_angles"]:
                explicit = p["bone_angles"][name]
            elif j["digit"] == "thumb" and "thumb" in p:
                explicit = p["thumb"][j["index"]]
            if explicit is not None:
                v = [float(x) for x in explicit]
            elif j["digit"] in p or "fingers" in p:
                arr = p[j["digit"]] if j["digit"] in p else p["fingers"]
                v[0] = float(arr[j["index"]]) if j["index"] < len(arr) else 0.0
                if j["index"] == 0 and "splay" in p and j["digit"] in p["splay"]:
                    v[2] = float(p["splay"][j["digit"]])
            lim = j["anatomical_limits_degrees"]
            out[name] = [min(max(v[i], lim[i][0]), lim[i][1]) for i in range(3)]
        return out

    def local(self, name, flex, twist, splay):
        j = self.joints[name]
        q = j.get("neutral_local_quaternion_xyzw") or j.get("local_bind_quaternion_xyzw")
        R = qmat(q) @ rot_zyx(math.radians(self.sign * splay), math.radians(self.sign * twist), math.radians(-flex))
        return R

    def model_mats(self, pose):
        return self.model_mats_from(self.controls(pose) if pose else None)

    def model_mats_from(self, ctl):
        pose = ctl is not None
        mats = {}

        def model(name):
            if name in mats:
                return mats[name]
            spec = self.specs.get(name)
            if spec is None:  # hand / forearm: at rest
                mats[name] = np.eye(4)
                return mats[name]
            p = np.array(spec["pivot"], float) * np.array([-1, 1, 1]) / 16.0
            if pose:
                f, tw, sp = ctl[name]
                R = self.local(name, f, tw, sp)
            else:
                j = self.joints[name]
                R = qmat(j.get("neutral_local_quaternion_xyzw") or j.get("local_bind_quaternion_xyzw"))
            mats[name] = model(spec["parent"]) @ affine(t=p) @ affine(R) @ affine(t=-p)
            return mats[name]
        for name in self.joints:
            model(name)
        return mats


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True)
    ap.add_argument("--unit", default="01")
    ap.add_argument("--side", default="l")
    ap.add_argument("--poses", default="relaxed,fist,open,grab")
    ap.add_argument("--hands", default="", help="override hands mesh json")
    ap.add_argument("--contract", default="", help="override hand rig contract")
    ap.add_argument("--overrides", default="", help="fitted hand poses (fist_fit.py) merged over the contract")
    ap.add_argument("--sequence", default="", help="A:B -> frames A..B..A for a video")
    ap.add_argument("--frames", type=int, default=36)
    ap.add_argument("--hold", type=int, default=12)
    ap.add_argument("--res", type=int, default=480)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    base = os.path.join(a.assets, "assets", "projectseele")
    contract = lab.load_json(a.contract or os.path.join(base, "hand_rigs", "unit" + a.unit, "hand_rig_contract.json"))
    mesh = lab.load_json(a.hands or os.path.join(base, "mesh", HANDS[a.unit] + ".mesh.json"))
    part = mesh["parts"]["hand_" + a.side]
    js = mesh["jointSkins"]["hand_" + a.side]
    raw = np.asarray(part["vertices"], float).reshape(-1, STRIDE)
    piv = np.asarray(part["pivot"], float)
    pts = np.stack([-(raw[:, 0] + piv[0]) / 16, (raw[:, 1] + piv[1]) / 16, (raw[:, 2] + piv[2]) / 16], 1)
    weights = {b: np.asarray(w, float) for b, w in js["influences"].items()}
    ib = {b: np.array(v).reshape(4, 4).T for b, v in js.get("inverseBindColumnMajor", {}).items()}
    if a.overrides:
        fitted = lab.load_json(a.overrides).get(str(int(a.unit)), {})
        for pose, ctl in fitted.items():
            if pose in contract["pose_controls"]:
                merged = dict(contract["pose_controls"][pose])
                merged["bone_angles"] = dict(merged.get("bone_angles", {}), **ctl["bone_angles"])
                contract["pose_controls"][pose] = merged
    rig = HandRig(contract, a.side)
    lab.clear_scene()
    lab.setup_render(640, 640)
    for ob in list(bpy.data.objects):
        if ob.name in ("ground", "Plane", "Grid"):
            bpy.data.objects.remove(ob)
    tex = os.path.join(base, "textures", "entity", TEXTURE[a.unit] + ".png")
    mat = bpy.data.materials.new("hand")
    mat.use_nodes = True
    t = mat.node_tree.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(tex)
    t.interpolation = 'Closest'
    mat.node_tree.links.new(t.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    os.makedirs(a.out, exist_ok=True)
    paths = []
    centre = pts.mean(0)
    if a.sequence:
        lab_sequence(a, rig, pts, raw, weights, ib, centre, mat)
        return
    for pose in a.poses.split(","):
        mats = rig.model_mats(pose)
        M = {b: (mats.get(b, np.eye(4)) @ ib.get(b, np.eye(4))) for b in weights}
        out = dq_skin(pts, weights, M)
        verts = [lab.model_to_blender(mathutils.Vector(p - centre)) for p in out]
        faces = [(i, i + 1, i + 2) for i in range(0, len(verts) - 2, 3)]
        me = bpy.data.meshes.new(pose)
        me.from_pydata(verts, [], faces)
        uv = me.uv_layers.new(name="UV")
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                uv.data[li].uv = (raw[vi, 3], 1.0 - raw[vi, 4])
        me.update()
        ob = bpy.data.objects.new(pose, me)
        ob.data.materials.append(mat)
        bpy.context.scene.collection.objects.link(ob)
        bpy.context.view_layer.update()
        for vname, loc in (("back", (0, 2.6, 0.4)), ("palm", (0, -2.6, 0.4)), ("side", (-2.6, 0, 0.4))):
            cam = lab.add_camera(pose + vname, loc, (0, 0, 0))
            cam.data.lens = 50
            p = os.path.join(a.out, f"u{a.unit}_{a.side}_{pose}_{vname}.png")
            lab.render_still(cam, p)
            paths.append(p)
        ob.hide_render = True
    lab.contact_sheet(paths, 3, os.path.join(a.out, f"hand_u{a.unit}_{a.side}.png"))


def lab_sequence(a, rig, pts, raw, weights, ib, centre, mat):
    """Frames easing pose A -> B, holding, and back, seen side-on to the finger curl."""
    pa, pb = a.sequence.split(":")
    ca, cb = rig.controls(pa), rig.controls(pb)
    ts = []
    for k in range(a.frames):
        ts.append(k / (a.frames - 1))
    ts = [0.0] * a.hold + ts + [1.0] * a.hold + ts[::-1] + [0.0] * a.hold
    sc = bpy.context.scene
    sc.render.resolution_x = sc.render.resolution_y = a.res
    cam = lab.add_camera("seq", (0.9, 2.4, 0.35), (0, 0, -0.1))
    cam.data.lens = 50
    sc.camera = cam
    me = bpy.data.meshes.new("hand")
    n = len(pts)
    me.from_pydata([(0, 0, 0)] * n, [], [(i, i + 1, i + 2) for i in range(0, n - 2, 3)])
    uv = me.uv_layers.new(name="UV")
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            uv.data[li].uv = (raw[vi, 3], 1.0 - raw[vi, 4])
    ob = bpy.data.objects.new("hand", me)
    ob.data.materials.append(mat)
    sc.collection.objects.link(ob)
    for f, t in enumerate(ts):
        e = t * t * (3 - 2 * t)
        ctl = {k: [ca[k][i] + (cb[k][i] - ca[k][i]) * e for i in range(3)] for k in ca}
        mats = rig.model_mats_from(ctl)
        M = {b: (mats.get(b, np.eye(4)) @ ib.get(b, np.eye(4))) for b in weights}
        out = dq_skin(pts, weights, M) - centre
        bl = np.stack([out[:, 0], -out[:, 2], out[:, 1]], 1)
        me.vertices.foreach_set("co", bl.ravel())
        me.update()
        sc.render.filepath = os.path.join(a.out, f"f{f:05d}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
