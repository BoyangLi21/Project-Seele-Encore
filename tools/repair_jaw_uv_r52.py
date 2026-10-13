"""Repair only nonzero-area jaw triangles with collapsed UV, preserving texels."""
import argparse
import copy
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image
from repair_hand_uv_material_r52 import ROOT, bilinear, sha, without_uv


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--selected-assets", type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / "artifacts/r52_hand_uv_material_repair"
    revision = output / "jaw_revision3"
    assert not revision.exists()
    revision.mkdir()
    selected = args.selected_assets.resolve() / "assets/projectseele"
    source = selected / "mesh/eva_unit01.mesh.json"
    assert sha(source) == "4959ebdec86cfea2b4cacb052ec0a374c1a39e48360880a29584b4754bbf1377"
    destination = output / "overlay/assets/projectseele/mesh/eva_unit01.mesh.json"
    previous = output / "mouth_lining_revision2/eva_unit01.mesh.json"
    assert not previous.exists()
    receipt2 = json.loads((previous.parent / "MOUTH_LINING_UV_REPAIR_RECEIPT.json").read_text(encoding="utf-8"))
    assert sha(destination) == receipt2["sha256"]
    shutil.copyfile(destination, previous)
    before = json.loads(source.read_text(encoding="utf-8"))
    after = json.loads(destination.read_text(encoding="utf-8"))
    original = np.array(before["parts"]["r37_jaw"]["vertices"]).reshape(-1, 3, 8)
    floats = original.astype(np.float32)
    xyz, uv = floats[:, :, :3], floats[:, :, 3:5]
    edge1, edge2 = xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 0]
    face = np.cross(edge1, edge2)
    face_length = np.linalg.norm(face, axis=1)
    du, dv = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
    determinant = du[:, 0] * dv[:, 1] - du[:, 1] * dv[:, 0]
    selected_triangles = np.flatnonzero((determinant == 0) & (face_length > 0))
    assert len(selected_triangles) == 376
    repaired = original.copy()
    radii, minimum_cross = [], 1.
    for triangle in selected_triangles:
        p = xyz[triangle].astype(float)
        n = face[triangle].astype(float) / face_length[triangle]
        axis = np.array([0., 1., 0.]) if abs(n[1]) < 0.9 else np.array([1., 0., 0.])
        tangent = axis - n * (axis @ n)
        tangent /= np.linalg.norm(tangent)
        binormal = np.cross(n, tangent)
        offsets = p - p.mean(axis=0)
        chart = np.stack((offsets @ tangent, offsets @ binormal), axis=1)
        chart /= np.abs(chart).max()
        original_uv = original[triangle, :, 3:5]
        pixel = original_uv * [1024, 512]
        room = np.minimum(pixel % 1, 1 - pixel % 1).min()
        accepted = None
        # Increase separation only when float32 rounding collapses the area.
        # Every corner stays inside its own original texel; existing large
        # UV differences and atlas patterns remain in place.
        for requested in (0.00002, 0.00005, 0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01):
            radius = min(requested, room * 0.45)
            candidate = (original_uv + chart * radius / [1024, 512]).astype(np.float32)
            a, b = candidate[1] - candidate[0], candidate[2] - candidate[0]
            det = np.float32(a[0] * b[1] - b[0] * a[1])
            if det == 0:
                continue
            raw_tangent = (b[1] * edge1[triangle] - a[1] * edge2[triangle]) / det
            if not np.isfinite(raw_tangent).all() or np.linalg.norm(raw_tangent) == 0:
                continue
            t = raw_tangent / np.linalg.norm(raw_tangent)
            norms = floats[triangle, :, 5:8].astype(float)
            norms /= np.linalg.norm(norms, axis=1)[:, None]
            crossing = np.linalg.norm(np.cross(norms, t), axis=1).min()
            if crossing < 0.6:
                continue
            assert np.array_equal(np.floor(candidate * [1024, 512]), np.floor(pixel))
            accepted = candidate
            radii.append(radius)
            minimum_cross = min(minimum_cross, float(crossing))
            break
        assert accepted is not None, f"No valid original-texel jaw repair for triangle {triangle}"
        repaired[triangle, :, 3:5] = accepted
    after["parts"]["r37_jaw"]["vertices"] = repaired.reshape(-1).tolist()
    assert without_uv(before) == without_uv(after)
    unchanged = np.ones(len(original), dtype=bool); unchanged[selected_triangles] = False
    assert np.array_equal(repaired[unchanged], original[unchanged])
    destination.write_text(json.dumps(after, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    readback = json.loads(destination.read_text(encoding="utf-8"))
    assert without_uv(before) == without_uv(readback)
    old_uv = original[selected_triangles, :, 3:5].reshape(-1, 2)
    new_uv = repaired[selected_triangles, :, 3:5].reshape(-1, 2)
    report = {"schema": "projectseele.r52.jaw-uv-repair.v1", "extends": "../mouth_lining_revision2/MOUTH_LINING_UV_REPAIR_RECEIPT.json",
              "path": "assets/projectseele/mesh/eva_unit01.mesh.json", "baseline_sha256": sha(source),
              "previous_lining_only_sha256": sha(previous), "sha256": sha(destination),
              "repaired_jaw_triangles": selected_triangles.tolist(), "repaired_count": 376,
              "zero_geometry_triangles_preserved_count": int(np.count_nonzero(face_length == 0)),
              "unaltered_jaw_triangles_exact": True, "all_non_uv_tree_equal_after_readback": True,
              "minimum_analytic_normal_cross_length": minimum_cross,
              "maximum_chart_radius_texels": max(radii),
              "maximum_actual_texel_displacement": float(np.abs((new_uv - old_uv) * [1024, 512]).max()),
              "material_sampling": {}, "native_visual_validation": "pending"}
    for suffix in ("", "_n", "_s"):
        image = np.asarray(Image.open(selected / "textures/entity" / f"eva_unit01{suffix}.png").convert("RGBA"), dtype=float)
        old_rgba = image[np.floor(old_uv[:, 1] * 512).astype(int), np.floor(old_uv[:, 0] * 1024).astype(int)]
        new_rgba = image[np.floor(new_uv[:, 1] * 512).astype(int), np.floor(new_uv[:, 0] * 1024).astype(int)]
        assert np.array_equal(old_rgba, new_rgba)
        delta = np.abs(bilinear(image, old_uv) - bilinear(image, new_uv))
        assert delta.max() < 1
        report["material_sampling"][suffix or "albedo"] = {"nearest_rgba_unchanged": True,
                "bilinear_max_rgba_byte_error": delta.max(axis=0).tolist(),
                "over_one_byte_error_cases": []}
    (revision / "JAW_UV_REPAIR_RECEIPT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sha256": report["sha256"], "repaired_jaw_triangles": 376,
                      "maximum_actual_texel_displacement": report["maximum_actual_texel_displacement"]}))


if __name__ == "__main__":
    main()
