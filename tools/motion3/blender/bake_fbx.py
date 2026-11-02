"""Bake FBX / glTF skeletal animation (Mixamo, Mesh2Motion, ...) to joint world transforms.

blender -b --factory-startup --python bake_fbx.py -- --in <file|dir|list.txt> --out <dir>

One .npz per take (a glTF file holding several actions gives one per action,
named <file>__<action>): names, pos (F,J,3) metres, rot (F,J,3,3), rate.  Y-up,
right-handed (Blender x, z, -y).  Rotations are pose-bone world matrices with
the bone rest orientation included; consumers only use rotation deltas
between frames of the same take, where the rest orientation cancels.
Mixamo prefixes ("mixamorig:", "mixamorig1:") are stripped.
"""

import argparse
import os
import re
import sys

import bpy
import numpy as np

C = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


def clean(name):
    return re.sub(r"^mixamorig\d*:", "", name)


def sample(arm, f0, f1):
    scene = bpy.context.scene
    names = [pb.name for pb in arm.pose.bones]
    n = f1 - f0 + 1
    pos = np.zeros((n, len(names), 3))
    rot = np.zeros((n, len(names), 3, 3))
    for i, f in enumerate(range(f0, f1 + 1)):
        scene.frame_set(f)
        for j, pb in enumerate(arm.pose.bones):
            m = arm.matrix_world @ pb.matrix
            pos[i, j] = C @ np.array(m.translation)
            rot[i, j] = C @ np.array(m.to_3x3().normalized()) @ C.T
    return names, pos, rot


def save(out_dir, base, names, pos, rot, rate):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", base)
    np.savez_compressed(os.path.join(out_dir, safe + ".npz"), names=np.array([clean(x) for x in names]),
                        pos=pos, rot=rot, rate=rate)
    print("BAKED", safe, pos.shape[0], "frames", round(rate, 3), "fps", len(names), "joints")


def bake(path, out_dir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    gltf = path.lower().endswith((".glb", ".gltf"))
    if gltf:
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False, ignore_leaf_bones=True)
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if not arms:
        print("SKIP no armature", path)
        return
    arm = max(arms, key=lambda o: len(o.pose.bones))
    scene = bpy.context.scene
    rate = scene.render.fps / scene.render.fps_base
    base = os.path.splitext(os.path.basename(path))[0]
    if gltf:
        if arm.animation_data is None:
            arm.animation_data_create()
        arm.animation_data.action = None
        for track in list(arm.animation_data.nla_tracks):
            arm.animation_data.nla_tracks.remove(track)
        for act in bpy.data.actions:
            arm.animation_data.action = act
            if hasattr(act, "slots") and len(act.slots):
                arm.animation_data.action_slot = act.slots[0]
            f0, f1 = (int(round(x)) for x in act.frame_range)
            names, pos, rot = sample(arm, f0, f1)
            save(out_dir, base + "__" + act.name, names, pos, rot, rate)
        return
    act = arm.animation_data.action if arm.animation_data else None
    if act is None:
        print("SKIP no action", path)
        return
    f0, f1 = (int(round(x)) for x in act.frame_range)
    names, pos, rot = sample(arm, f0, f1)
    save(out_dir, base, names, pos, rot, rate)


def main():
    a = parse()
    os.makedirs(a.out, exist_ok=True)
    if a.src.lower().endswith(".txt"):
        with open(a.src, encoding="utf-8") as f:
            files = [line.strip() for line in f if line.strip()]
    elif os.path.isfile(a.src):
        files = [a.src]
    else:
        files = sorted(
        os.path.join(dp, f) for dp, _, fs in os.walk(a.src) for f in fs if f.lower().endswith((".fbx", ".glb", ".gltf")))
    for path in files:
        base = re.sub(r"[^A-Za-z0-9_.-]+", "_", os.path.splitext(os.path.basename(path))[0])
        if os.path.exists(os.path.join(a.out, base + ".npz")):
            continue
        try:
            bake(path, a.out)
        except Exception as exc:  # keep baking the remaining takes
            print("FAIL", path, exc)


if __name__ == "__main__":
    main()
