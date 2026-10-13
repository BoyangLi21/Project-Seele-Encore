"""UV-only repair of the frozen R45 hand triangles; never edits the baseline."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = [
    "5ba609ad81f6ef0372527504348683cc510b0d923e53dd5f6bb70bf8fc041000",
    "cc835aaf2f7b090d92dc539a7c21257d8fd318ee3870be3aa11fe2086e439ae7",
    "438910bee1225a705b7705143d4b4b5a3ada8bf9e45744d928c105a5166e8067",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def without_uv(mesh: dict) -> dict:
    result = copy.deepcopy(mesh)
    for part in result["parts"].values():
        for i in range(0, len(part["vertices"]), 8):
            part["vertices"][i + 3:i + 5] = [None, None]
    return result


def bilinear(image: np.ndarray, uv: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    xy = uv * [width, height] - 0.5
    lo = np.floor(xy).astype(int)
    mix = xy - lo
    x, y = lo[:, 0] % width, lo[:, 1] % height
    xr, yr = (x + 1) % width, (y + 1) % height
    a = image[y, x] * (1 - mix[:, 0:1]) + image[y, xr] * mix[:, 0:1]
    b = image[yr, x] * (1 - mix[:, 0:1]) + image[yr, xr] * mix[:, 0:1]
    return a * (1 - mix[:, 1:2]) + b * mix[:, 1:2]


def chart(vertices: np.ndarray, width: int, height: int) -> tuple[np.ndarray, dict]:
    triangles = vertices.reshape(-1, 3, 8)
    xyz = triangles[:, :, :3]
    uv = triangles[:, :, 3:5]
    assert np.all(uv == uv[:, :1]), "Repair only the known constant-UV palette triangles"
    normal = triangles[:, :, 5:8]
    normal = normal / np.linalg.norm(normal, axis=2)[:, :, None]
    face = np.cross(xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 0])
    area = np.linalg.norm(face, axis=1)
    assert np.all(area > 0), "Cannot repair collapsed geometry by changing UV"
    face /= area[:, None]

    # A geometric chart follows a stable anatomical axis projected onto the
    # actual face. Prefer the hand's longitudinal Y axis. An alternate X/Z
    # projection is used only at its poles or when a smooth vertex normal
    # would otherwise make the shader's cross(normal,tangent) nearly zero.
    candidates = []
    scores = []
    for axis in ([0., 1., 0.], [1., 0., 0.], [0., 0., 1.]):
        tangent = np.array(axis)[None, :] - face * (face @ axis)[:, None]
        length = np.linalg.norm(tangent, axis=1)
        tangent /= np.maximum(length[:, None], 1e-30)
        cosine = np.abs(np.einsum("tvi,ti->tv", normal, tangent)).max(axis=1)
        scores.append(np.where(length > 0.1, cosine, 2.))
        candidates.append(tangent)
    scores = np.stack(scores, axis=1)
    chosen = np.where(scores[:, 0] <= 0.85, 0, np.argmin(scores, axis=1))
    tangent = np.stack(candidates, axis=1)[np.arange(len(xyz)), chosen]
    binormal = np.cross(face, tangent)
    centred = xyz - xyz.mean(axis=1)[:, None, :]
    local = np.stack((np.einsum("tvi,ti->tv", centred, tangent),
                      np.einsum("tvi,ti->tv", centred, binormal)), axis=2)

    pixel_centre = uv[:, 0] * [width, height]
    # Keep the original palette texel and original sample centroid. The
    # largest chart radius is one hundredth of a texel: enough float32 UV
    # separation for Oculus, while bilinear colour changes stay <1/255.
    edge_room = np.minimum(pixel_centre % 1, 1 - pixel_centre % 1).min(axis=1)
    radius = np.minimum(0.01, edge_room * 0.45)
    scale = radius / np.abs(local).max(axis=(1, 2))
    repaired = uv[:, :1] + local * scale[:, None, None] / [width, height]
    repaired = repaired.astype(np.float32)
    du = repaired[:, 1] - repaired[:, 0]
    dv = repaired[:, 2] - repaired[:, 0]
    determinants = du[:, 0] * dv[:, 1] - dv[:, 0] * du[:, 1]
    assert np.all(np.isfinite(repaired)) and np.all(determinants != 0), "Float32 chart collapsed"
    assert np.array_equal(np.floor(repaired * [width, height]),
                          np.broadcast_to(np.floor(pixel_centre)[:, None], repaired.shape))
    result = vertices.copy().reshape(-1, 3, 8)
    result[:, :, 3:5] = repaired
    return result.reshape(-1, 8), {
        "triangles": len(xyz), "original_degenerate_uv_triangles": len(xyz),
        "repaired_degenerate_uv_triangles": int(np.count_nonzero(determinants == 0)),
        "minimum_float32_uv_area_twice": float(np.abs(determinants).min()),
        "maximum_texel_displacement": float(np.abs((repaired - uv) * [width, height]).max()),
        "axis_counts_y_x_z": np.bincount(chosen, minlength=3).tolist(),
        "minimum_authored_normal_tangent_cross_length": float(np.sqrt(
            1 - np.square(np.abs(np.einsum("tvi,ti->tv", normal, tangent)).clip(0, 1))).min()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--selected-assets", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path,
                        default=ROOT / "artifacts/r52_hand_uv_material_repair")
    args = parser.parse_args()
    output = args.output_directory.resolve()
    permitted = (ROOT / "artifacts/r52_hand_uv_material_repair").resolve()
    assert output == permitted or permitted in output.parents
    assert not output.exists(), "Keep earlier evidence; choose a new child output directory"
    selected = args.selected_assets.resolve() / "assets/projectseele"
    assert selected not in output.parents
    overlay = output / "overlay/assets/projectseele"
    (overlay / "mesh").mkdir(parents=True)
    report = {"schema": "projectseele.r52.hand-uv-material-repair.v1",
              "selected_assets": str(args.selected_assets.resolve()),
              "overlay": str(output / "overlay"), "files": [],
              "method": "Face-plane projection of a stable anatomical axis, original palette texel and sample centroid retained",
              "native_visual_validation": "pending; no game opened by this tool"}
    for unit in range(3):
        relative = f"mesh/eva_unit0{unit}_anatomical_hands_r45.mesh.json"
        source = selected / relative
        assert sha(source) == EXPECTED[unit], "Frozen source mismatch"
        original = json.loads(source.read_text(encoding="utf-8"))
        repaired = copy.deepcopy(original)
        images = {suffix or "albedo": np.asarray(Image.open(selected / "textures/entity" /
                  f"eva_unit0{unit}{suffix}.png").convert("RGBA"), dtype=np.float64)
                  for suffix in ("", "_n", "_s")}
        height, width = images["albedo"].shape[:2]
        entry = {"path": "assets/projectseele/" + relative,
                 "baseline_sha256": sha(source), "parts": {}, "material_sampling": {}}
        all_old_uv, all_new_uv = [], []
        for name, part in original["parts"].items():
            before = np.array(part["vertices"]).reshape(-1, 8)
            after, checks = chart(before, width, height)
            repaired["parts"][name]["vertices"] = after.reshape(-1).tolist()
            entry["parts"][name] = checks
            all_old_uv.append(before[:, 3:5]); all_new_uv.append(after[:, 3:5])
        assert without_uv(original) == without_uv(repaired), "Non-UV data changed"
        destination = overlay / relative
        destination.write_text(json.dumps(repaired, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        readback = json.loads(destination.read_text(encoding="utf-8"))
        assert without_uv(readback) == without_uv(original), "Serialized geometry changed"
        old_uv, new_uv = np.concatenate(all_old_uv), np.concatenate(all_new_uv)
        for name, image in images.items():
            hh, ww = image.shape[:2]
            before_nearest = image[np.floor(old_uv[:, 1] * hh).astype(int), np.floor(old_uv[:, 0] * ww).astype(int)]
            after_nearest = image[np.floor(new_uv[:, 1] * hh).astype(int), np.floor(new_uv[:, 0] * ww).astype(int)]
            assert np.array_equal(before_nearest, after_nearest)
            delta = np.abs(bilinear(image, old_uv) - bilinear(image, new_uv))
            assert delta.max() < 1., "Changed material colour by a whole byte"
            entry["material_sampling"][name] = {
                "nearest_rgba_unchanged": True,
                "baseline_nearest_rgba": np.unique(before_nearest, axis=0).astype(int).tolist(),
                "bilinear_max_rgba_byte_error": delta.max(axis=0).tolist(),
            }
        entry["sha256"] = sha(destination)
        entry["bytes"] = destination.stat().st_size
        entry["non_uv_tree_equal_after_readback"] = True
        report["files"].append(entry)
    (output / "UV_REPAIR_RECEIPT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "files": [(f["path"], f["sha256"]) for f in report["files"]]}, indent=2))


if __name__ == "__main__":
    main()
