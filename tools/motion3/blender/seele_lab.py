"""Project SEELE motion lab: rebuild the runtime EVA rig and meshes in Blender.

The runtime skeleton is Bedrock-style: every bone has an absolute model-space
pivot and its local matrix is T(pos) T(pivot) R T(-pivot), chained to the
parent.  A Blender armature whose bones all keep an identity rest orientation
reproduces that exactly, so pose rotations here are the runtime quaternions
expressed in Blender axes.

Axes: model space is Minecraft (Y up).  Blender = rotate +90 deg about X, i.e.
(x, y, z)_model -> (x, -z, y)_blender.  Geo/mesh pixels map to model blocks as
(-px, py, pz) / 16 before that rotation.

Run inside Blender:  blender -b --python seele_lab.py -- <args>
Only the library functions are used by the other motion3 scripts.
"""

import json
import math
import os

import bpy
import mathutils

BONE_LENGTH = 0.25  # display only; rest orientation must stay identity

# model (Minecraft) space -> Blender space
M2B = mathutils.Matrix.Rotation(math.radians(90.0), 4, 'X')
M2B3 = M2B.to_3x3()
B2M3 = M2B3.inverted()


def px_to_model(p):
    return mathutils.Vector((-p[0] / 16.0, p[1] / 16.0, p[2] / 16.0))


def model_to_blender(v):
    return M2B3 @ mathutils.Vector(v)


def blender_to_model(v):
    return B2M3 @ mathutils.Vector(v)


def quat_model_to_blender(q):
    """q is a mathutils.Quaternion in model axes."""
    m = M2B3 @ q.to_matrix() @ B2M3
    return m.to_quaternion()


def quat_blender_to_model(q):
    m = B2M3 @ q.to_matrix() @ M2B3
    return m.to_quaternion()


def runtime_quat(wxyz):
    """Profile rotation_wxyz -> model-space quaternion (EvaBodyPose.reload)."""
    w, x, y, z = wxyz
    return mathutils.Quaternion((w, -x, -y, z)).normalized()


def runtime_wxyz(q_model):
    """Inverse of runtime_quat: model quaternion -> profile rotation_wxyz."""
    q = q_model.normalized()
    return [q.w, -q.x, -q.y, q.z]


def bind_quat(deg):
    """Geo bindRotation degrees -> model quaternion (rotationZYX(z, -y, -x))."""
    x, y, z = (math.radians(a) for a in deg)
    # JOML rotationZYX(a, b, c) = Rz(a) * Ry(b) * Rx(c)
    rz = mathutils.Quaternion((0, 0, 1), z)
    ry = mathutils.Quaternion((0, 1, 0), -y)
    rx = mathutils.Quaternion((1, 0, 0), -x)
    return rz @ ry @ rx


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def geo_bones(geo_path):
    g = load_json(geo_path)
    bones = g["minecraft:geometry"][0]["bones"]
    return [{"name": b["name"], "parent": b.get("parent"), "pivot": b.get("pivot", [0, 0, 0]),
             "rotation": b.get("rotation")} for b in bones]


def build_armature(rig, name="EVA"):
    """rig: list of {name, parent, pivot(px), rotation(deg)?} in parent-first or any order."""
    arm_data = bpy.data.armatures.new(name + "_rig")
    arm = bpy.data.objects.new(name, arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    by_name = {b["name"]: b for b in rig}
    edit = {}
    for b in rig:
        eb = arm_data.edit_bones.new(b["name"])
        head = model_to_blender(px_to_model(b["pivot"]))
        eb.head = head
        eb.tail = head + mathutils.Vector((0, BONE_LENGTH, 0))
        eb.roll = 0.0
        eb.use_deform = False
        edit[b["name"]] = eb
    for b in rig:
        p = b.get("parent")
        if p and p in edit:
            edit[b["name"]].parent = edit[p]
            edit[b["name"]].use_connect = False
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    bpy.ops.object.mode_set(mode='OBJECT')
    arm["seele_bind"] = json.dumps({b["name"]: b.get("rotation") for b in rig if b.get("rotation")})
    return arm


def load_mesh_parts(arm, mesh_path, texture_path=None, name="body"):
    mesh = load_json(mesh_path)
    stride = mesh.get("stride", 8)
    mat = None
    if texture_path and os.path.isfile(texture_path):
        mat = bpy.data.materials.new(name + "_mat")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(texture_path)
        tex.interpolation = 'Closest'
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.55
    objs = []
    for bone_name, part in mesh["parts"].items():
        if bone_name not in arm.data.bones:
            continue
        verts_raw = part["vertices"]
        piv = part["pivot"]
        n = len(verts_raw) // stride
        if n < 3:
            continue
        verts, uvs = [], []
        for i in range(n):
            o = i * stride
            p = px_to_model((verts_raw[o] + piv[0], verts_raw[o + 1] + piv[1], verts_raw[o + 2] + piv[2]))
            verts.append(model_to_blender(p))
            uvs.append((verts_raw[o + 3], 1.0 - verts_raw[o + 4]))
        faces = [(i, i + 1, i + 2) for i in range(0, n - 2, 3)]
        me = bpy.data.meshes.new(f"{name}_{bone_name}")
        me.from_pydata(verts, [], faces)
        uv = me.uv_layers.new(name="UV")
        for poly in me.polygons:
            for li in poly.loop_indices:
                uv.data[li].uv = uvs[me.loops[li].vertex_index]
        me.update()
        ob = bpy.data.objects.new(f"{name}_{bone_name}", me)
        bpy.context.scene.collection.objects.link(ob)
        if mat:
            ob.data.materials.append(mat)
        # Rigid bone parenting while keeping the rest-space placement.
        bone = arm.data.bones[bone_name]
        ob.parent = arm
        ob.parent_type = 'BONE'
        ob.parent_bone = bone_name
        rest = arm.matrix_world @ bone.matrix_local @ mathutils.Matrix.Translation((0, bone.length, 0))
        ob.matrix_parent_inverse = rest.inverted()
        objs.append(ob)
    return objs


SEAM_JOINTS = (("elbow", "arm_{s}", "forearm_{s}"), ("ankle", "shin_{s}", "foot_{s}"),
               ("wrist", "forearm_{s}", "hand_{s}"), ("hip", "torso_lower", "leg_{s}"),
               ("waist", "torso_lower", "torso_upper"))


def runtime_seam_weights(parts):
    """Port of LocalTriangleMeshLayer.jointSkins: per part, {other bone: weights}
    plus snapped rest points for welded seam vertices (pixel space)."""
    import mathutils.kdtree as kdt
    stride = 8
    eps = 0.002
    out = {}  # part -> {"influence": {bone: [w...]}, "rest": [[x,y,z]...]}

    def rest_points(name):
        p = parts[name]
        v, piv = p["vertices"], p["pivot"]
        return [(v[i] + piv[0], v[i + 1] + piv[1], v[i + 2] + piv[2]) for i in range(0, len(v), stride)]

    def entry(name):
        if name not in out:
            pts = rest_points(name)
            out[name] = {"own": [1.0] * len(pts), "influence": {}, "rest": pts}
        return out[name]

    for joint, up_t, lo_t in SEAM_JOINTS:
        for s in ("l", "r"):
            if joint == "waist" and s == "r":
                continue
            upper, lower = up_t.format(s=s), lo_t.format(s=s)
            if upper not in parts or lower not in parts:
                continue
            a_pts, b_pts = rest_points(upper), rest_points(lower)
            tree = kdt.KDTree(len(b_pts))
            for i, p in enumerate(b_pts):
                tree.insert(p, i)
            tree.balance()
            seam = []
            for p in a_pts:
                co, idx, dist = tree.find(p)
                if dist is not None and dist <= eps:
                    c = (mathutils.Vector(p) + co) * 0.5
                    if all((c - q).length > eps for q in seam[-64:]):
                        seam.append(c)
            if len(seam) < 3:
                continue
            st = kdt.KDTree(len(seam))
            for i, p in enumerate(seam):
                st.insert(p, i)
            st.balance()
            for name, other in ((upper, lower), (lower, upper)):
                e = entry(name)
                infl = e["influence"].setdefault(other, [0.0] * len(e["rest"]))
                for i, p in enumerate(e["rest"]):
                    co, _, dist = st.find(p)
                    if dist <= eps:
                        w = 0.5
                        e["rest"][i] = tuple(co)
                    else:
                        t = max(0.0, 1.0 - dist / 6.0)
                        w = 0.5 * t * t * (3 - 2 * t)
                    take = min(e["own"][i], w)
                    e["own"][i] -= take
                    infl[i] += take
    if "head" in parts and "torso_upper" in parts:
        e = entry("head")
        piv = parts["head"]["pivot"]
        infl = e["influence"].setdefault("torso_upper", [0.0] * len(e["rest"]))
        for i, (x, y, z) in enumerate(e["rest"]):
            blend = max(0.0, min(1.0, (piv[1] + 1.5 - y) / 7.0))
            if y > piv[1] - 3 and z < -6:
                blend = 0.0
            w = blend * blend * (3 - 2 * blend)
            take = min(e["own"][i], w)
            e["own"][i] -= take
            infl[i] += take
    return out


def load_mesh_skinned(arm, mesh_path, texture_path=None, name="body"):
    """Mesh parts deformed like the game: rigid per bone plus dual-quaternion
    seams (Armature modifier, preserve volume) from runtime_seam_weights."""
    mesh = load_json(mesh_path)
    stride = mesh.get("stride", 8)
    seams = runtime_seam_weights(mesh["parts"])
    # authored influences (pivot-rig rest = identity, no inverse bind) take precedence
    for part, js in (mesh.get("jointSkins") or {}).items():
        if "influences" in js and "inverseBindColumnMajor" not in js and part in mesh["parts"]:
            p = mesh["parts"][part]
            raw, piv = p["vertices"], p["pivot"]
            pts = [(raw[i] + piv[0], raw[i + 1] + piv[1], raw[i + 2] + piv[2]) for i in range(0, len(raw), stride)]
            infl = dict(js["influences"])
            own = infl.pop(part, [0.0] * len(pts))
            seams[part] = {"own": list(own), "influence": infl, "rest": pts}
    mat = None
    if texture_path and os.path.isfile(texture_path):
        mat = bpy.data.materials.new(name + "_mat")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(texture_path)
        tex.interpolation = 'Closest'
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.55
    for b in arm.data.bones:
        b.use_deform = True
    objs = []
    for bone_name, part in mesh["parts"].items():
        if bone_name not in arm.data.bones:
            continue
        raw, piv = part["vertices"], part["pivot"]
        n = len(raw) // stride
        if n < 3:
            continue
        sk = seams.get(bone_name)
        pts = sk["rest"] if sk else [(raw[i * stride] + piv[0], raw[i * stride + 1] + piv[1], raw[i * stride + 2] + piv[2])
                                      for i in range(n)]
        verts = [model_to_blender(px_to_model(p)) for p in pts]
        uvs = [(raw[i * stride + 3], 1.0 - raw[i * stride + 4]) for i in range(n)]
        faces = [(i, i + 1, i + 2) for i in range(0, n - 2, 3)]
        me = bpy.data.meshes.new(f"{name}_{bone_name}")
        me.from_pydata(verts, [], faces)
        uv = me.uv_layers.new(name="UV")
        for poly in me.polygons:
            for li in poly.loop_indices:
                uv.data[li].uv = uvs[me.loops[li].vertex_index]
        me.update()
        ob = bpy.data.objects.new(f"{name}_{bone_name}", me)
        bpy.context.scene.collection.objects.link(ob)
        if mat:
            ob.data.materials.append(mat)
        own = ob.vertex_groups.new(name=bone_name)
        if sk:
            for i, w in enumerate(sk["own"]):
                if w > 0:
                    own.add([i], w, 'REPLACE')
            for other, ws in sk["influence"].items():
                if other not in arm.data.bones:
                    continue
                g = ob.vertex_groups.new(name=other)
                for i, w in enumerate(ws):
                    if w > 0:
                        g.add([i], w, 'REPLACE')
        else:
            own.add(list(range(n)), 1.0, 'REPLACE')
        ob.parent = arm
        mod = ob.modifiers.new("arm", 'ARMATURE')
        mod.object = arm
        mod.use_deform_preserve_volume = True
        objs.append(ob)
    return objs


def apply_frame(arm, bone_names, frame, frame_index=None):
    """Write one profile frame (EvaBodyPose schema 2) onto the armature pose."""
    rots = frame["rotation_wxyz"]
    pos = frame.get("bone_position_xyz", {}) or {}
    for i, name in enumerate(bone_names):
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        pb.rotation_quaternion = quat_model_to_blender(runtime_quat(rots[i]))
        loc = mathutils.Vector((0, 0, 0))
        if name == "root" and "root_m" in frame:
            v = [c * 112.0 for c in frame["root_m"]]
            loc = model_to_blender(px_to_model(v))
        elif name in pos:
            loc = model_to_blender(px_to_model(pos[name]))
        pb.location = loc
        if frame_index is not None:
            pb.keyframe_insert("rotation_quaternion", frame=frame_index)
            pb.keyframe_insert("location", frame=frame_index)


def apply_bind_axes(arm):
    """The runtime keeps *_axis_* bones at their bind rotation."""
    bind = json.loads(arm.get("seele_bind", "{}"))
    for name, deg in bind.items():
        if "_axis_" in name and name in arm.pose.bones:
            arm.pose.bones[name].rotation_quaternion = quat_model_to_blender(bind_quat(deg))


def setup_render(width=960, height=540, film_transparent=False):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x = width
    sc.render.resolution_y = height
    sc.render.film_transparent = film_transparent
    world = bpy.data.worlds.new("lab_world") if not sc.world else sc.world
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.62, 0.68, 0.76, 1.0)
        bg.inputs[1].default_value = 0.9
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", type='SUN'))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
    sc.collection.objects.link(sun)
    # ground grid: 1 block squares
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=40, y_subdivisions=40, size=40)
    g = bpy.context.active_object
    g.name = "ground"
    gm = bpy.data.materials.new("ground_mat")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.36, 0.35, 1)
    g.data.materials.append(gm)
    bpy.ops.object.modifier_add(type='WIREFRAME')
    g.modifiers[-1].thickness = 0.03
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -0.01))
    p = bpy.context.active_object
    pm = bpy.data.materials.new("plane_mat")
    pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.56, 0.55, 1)
    p.data.materials.append(pm)


def add_camera(name, location, target):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    bpy.context.scene.collection.objects.link(cam)
    cam.location = location
    direction = mathutils.Vector(target) - mathutils.Vector(location)
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 40
    return cam


def render_still(cam, path):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def contact_sheet(paths, cols, out_path, label_every=None):
    """Tile rendered PNGs (same size) into one image using bpy image buffers."""
    import numpy as np
    imgs = [bpy.data.images.load(p) for p in paths]
    w, h = imgs[0].size
    rows = (len(imgs) + cols - 1) // cols
    sheet = np.ones((rows * h, cols * w, 4), dtype=np.float32)
    for i, im in enumerate(imgs):
        px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        r, c = divmod(i, cols)
        # bpy pixel rows start at the bottom
        y0 = (rows - 1 - r) * h
        sheet[y0:y0 + h, c * w:(c + 1) * w] = px
    out = bpy.data.images.new("sheet", cols * w, rows * h, alpha=True)
    out.pixels = sheet.ravel()
    out.filepath_raw = out_path
    out.file_format = 'PNG'
    out.save()
    for im in imgs:
        bpy.data.images.remove(im)


def model_bounds(objs):
    xs, ys, zs = [], [], []
    for ob in objs:
        for c in ob.bound_box:
            w = ob.matrix_world @ mathutils.Vector(c)
            xs.append(w.x); ys.append(w.y); zs.append(w.z)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))
