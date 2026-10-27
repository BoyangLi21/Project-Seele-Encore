"""Restore every source triangle using measured installed weights as a transfer cage.

Run with Blender Python. This stages a candidate; it never edits the live pack.
Source geometry, normals and UVs remain intact under one uniform normalization.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def barycentric(point, triangle):
    a, b, c = triangle
    ab, ac, ap = b - a, c - a, point - a
    aa, bb, cc = ab @ ab, ab @ ac, ac @ ac
    denominator = aa * cc - bb * bb
    if abs(denominator) < 1e-12:
        weights = np.zeros(3)
        weights[np.argmin(np.linalg.norm(triangle - point, axis=1))] = 1
        return weights
    v = (cc * (ap @ ab) - bb * (ap @ ac)) / denominator
    w = (aa * (ap @ ac) - bb * (ap @ ab)) / denominator
    weights = np.maximum(0, np.array([1 - v - w, v, w]))
    return weights / weights.sum()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--installed", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    args.out.mkdir(parents=True, exist_ok=False)
    original = json.loads(args.installed.read_text("utf8"))
    geometry = np.load(args.source)
    vertices = geometry["vertices"].astype(np.float64)
    vertices[:, 1] -= vertices[:, 1].min()
    scale = 192 / np.ptp(vertices[:, 1])
    vertices *= scale
    triangles = geometry["triangles"]
    names = sorted({name.removeprefix("tripo_blend_") for name in original["parts"]
                    if name != "dorsal_liner"})
    index = {name: i for i, name in enumerate(names)}
    points, source_weights = [], []
    for name, part in original["parts"].items():
        if name == "dorsal_liner":
            continue
        array = np.asarray(part["vertices"], np.float32).reshape(-1, 8)
        points.append((array[:, :3] + part["pivot"]) * [-1, 1, 1])
        weights = np.zeros((len(array), len(names)), np.float32)
        definition = original["jointSkins"].get(name)
        if definition:
            assert set(definition) == {"influences"}, ("Preserve unsupported bind data", name)
            for joint, values in definition["influences"].items():
                weights[:, index[joint]] = values
        else:
            weights[:, index[name]] = 1
        source_weights.append(weights)
    points = np.concatenate(points).reshape(-1, 3, 3)
    source_weights = np.concatenate(source_weights).reshape(-1, 3, len(names))
    tree = BVHTree.FromPolygons(points.reshape(-1, 3).tolist(),
                               np.arange(len(points) * 3).reshape(-1, 3).tolist(),
                               all_triangles=True)
    # UV seam duplicates receive precisely the same binding.
    unique, inverse = np.unique(vertices, axis=0, return_inverse=True)
    weights = np.zeros((len(unique), len(names)), np.float32)
    distances = np.zeros(len(unique), np.float32)
    for at, vertex in enumerate(unique):
        location, normal, face, distance = tree.find_nearest(Vector(vertex))
        if face is None:
            raise ValueError("No installed transfer surface")
        row = barycentric(np.array(location), points[face]) @ source_weights[face]
        row /= row.sum()
        weights[at] = row
        distances[at] = distance
        if at % 100000 == 0:
            print("Transferred source vertices", at, "/", len(unique), flush=True)
    weights = weights[inverse]
    np.savez_compressed(args.out / "binding.npz", weights=weights, bones=names)
    owners = np.zeros(len(triangles), np.int16)
    best = np.full(len(triangles), -1, np.float32)
    for joint in range(len(names)):
        score = weights[triangles, joint].sum(axis=1)
        selected = score > best
        owners[selected] = joint
        best[selected] = score[selected]
    del source_weights, points, tree, unique
    parts, skins, counts = {}, {}, {}
    for joint, owner in enumerate(names):
        selected = np.flatnonzero(owners == joint)
        if not len(selected):
            continue
        faces = triangles[selected]
        nonzero = (weights[faces] != 0).sum(axis=2)
        rigid = (nonzero == 1).all(axis=1) & (weights[faces, joint] > 0).all(axis=1)
        for blended, mask in ((False, rigid), (True, ~rigid)):
            ids = selected[mask]
            if not len(ids):
                continue
            name = "tripo_blend_" + owner if blended else owner
            # Only measured existing bones can own a part.
            template = original["parts"].get(name, original["parts"].get(owner))
            if template is None:
                raise ValueError("Missing measured part " + name)
            pivot = np.asarray(template["pivot"])
            face = triangles[ids]
            uv = geometry["uv"][ids].copy()
            uv[:, :, 1] = 1 - uv[:, :, 1]
            data = np.concatenate((vertices[face] * [-1, 1, 1] - pivot, uv,
                                   geometry["normals"][ids] * [-1, 1, 1]), axis=2).astype(np.float32)
            np.save(args.out / (name + ".npy"), data.ravel())
            parts[name] = dict(pivot=pivot.tolist())
            counts[name] = len(ids)
            if blended:
                skin = {}
                for influence in np.flatnonzero((weights[face] != 0).any(axis=(0, 1))):
                    file = args.out / (name + "--" + names[influence] + ".npy")
                    np.save(file, weights[face, influence].ravel())
                    skin[names[influence]] = file
                skins[name] = skin
            print("Source part", name, len(ids), "triangles", flush=True)
    output = args.out / args.installed.name
    metadata = {k: v for k, v in original.items() if k not in ("parts", "jointSkins")}
    metadata["source"] = "Owner-supplied full source surface; barycentric binding transfer from measured installed rig"
    metadata["source_surface_r53"] = True
    metadata["triangleCount"] = int(len(triangles) + len(original["parts"]["dorsal_liner"]["vertices"]) // 24)
    with output.open("w", encoding="utf8") as out:
        out.write(json.dumps(metadata, separators=(",", ":"))[:-1] + ',"parts":{')
        for i, (name, part) in enumerate(parts.items()):
            if i:
                out.write(",")
            out.write(json.dumps(name) + ":" + json.dumps(part)[:-1] + ',"vertices":')
            json.dump(np.load(args.out / (name + ".npy")).tolist(), out, separators=(",", ":"))
            out.write("}")
        out.write(',"dorsal_liner":')
        json.dump(original["parts"]["dorsal_liner"], out, separators=(",", ":"))
        out.write('},"jointSkins":{')
        for i, (name, influences) in enumerate(skins.items()):
            if i:
                out.write(",")
            out.write(json.dumps(name) + ':{"influences":{')
            for j, (bone, file) in enumerate(influences.items()):
                if j:
                    out.write(",")
                out.write(json.dumps(bone) + ":")
                json.dump(np.load(file).tolist(), out, separators=(",", ":"))
            out.write("}}")
        out.write("}}")
    assert sum(counts.values()) == len(triangles)
    geo_path = args.installed.parent.parent / "geo" / args.installed.name.replace(".mesh.", ".geo.")
    geo = json.loads(geo_path.read_text("utf8"))
    bones = geo["minecraft:geometry"][0]["bones"]
    known = {bone["name"] for bone in bones}
    extra = []
    for name, part in parts.items():
        if name in known:
            continue
        owner = name.removeprefix("tripo_blend_")
        assert name.startswith("tripo_blend_") and owner in known
        bone = dict(name=name, parent=owner, pivot=part["pivot"])
        bones.append(bone)
        extra.append(bone)
    (args.out / geo_path.name).write_text(json.dumps(geo, indent=2), "utf8")
    report = dict(source_triangles=int(len(triangles)), candidate_source_triangles=sum(counts.values()),
                  added_liner_triangles=len(original["parts"]["dorsal_liner"]["vertices"]) // 24,
                  scale=scale, vertex_transfer_distance_p50_p95_max=np.quantile(distances, [.5, .95, 1]).tolist(),
                  geometry_pruned=False, normals_and_uv_preserved=True, model_warped=False,
                  installed=False, native_validation="pending",
                  mesh_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  extra_blend_bones=extra, parts=counts)
    (args.out / "RECEIPT.json").write_text(json.dumps(report, indent=2), "utf8")
    print(json.dumps({k: v for k, v in report.items() if k != "parts"}), flush=True)


if __name__ == "__main__":
    main()
