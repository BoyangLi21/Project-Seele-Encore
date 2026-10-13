"""Apply the verified palette-chart repair to the actual Unit01 mouth lining."""
import argparse
import copy
import json
from pathlib import Path

import numpy as np
from PIL import Image
from repair_hand_uv_material_r52 import ROOT, bilinear, chart, sha, without_uv

PARTS = ("r37_red_upper", "r37_red_lower", "r37_lining")
BASELINE = "4959ebdec86cfea2b4cacb052ec0a374c1a39e48360880a29584b4754bbf1377"


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--selected-assets", type=Path, required=True)
    parser.add_argument("--repair-directory", type=Path,
                        default=ROOT / "artifacts/r52_hand_uv_material_repair")
    args = parser.parse_args()
    output = args.repair_directory.resolve()
    assert output == (ROOT / "artifacts/r52_hand_uv_material_repair").resolve()
    revision = output / "mouth_lining_revision2"
    assert not revision.exists(), "Preserve previous receipts"
    revision.mkdir()
    selected = args.selected_assets.resolve() / "assets/projectseele"
    source = selected / "mesh/eva_unit01.mesh.json"
    assert sha(source) == BASELINE
    before = json.loads(source.read_text(encoding="utf-8"))
    after = copy.deepcopy(before)
    images = {suffix or "albedo": np.asarray(Image.open(selected / "textures/entity" /
              f"eva_unit01{suffix}.png").convert("RGBA"), dtype=np.float64)
              for suffix in ("", "_n", "_s")}
    height, width = images["albedo"].shape[:2]
    report = {"schema": "projectseele.r52.mouth-lining-uv-repair.v1",
              "extends": "../UV_REPAIR_RECEIPT.json", "path": "assets/projectseele/mesh/eva_unit01.mesh.json",
              "baseline_sha256": BASELINE, "changed_parts_only": list(PARTS),
              "parts": {}, "material_sampling": {}, "native_visual_validation": "pending"}
    old_uv, new_uv = [], []
    for name in PARTS:
        vertices = np.array(before["parts"][name]["vertices"]).reshape(-1, 8)
        repaired, checks = chart(vertices, width, height)
        report["parts"][name] = checks
        after["parts"][name]["vertices"] = repaired.reshape(-1).tolist()
        old_uv.append(vertices[:, 3:5]); new_uv.append(repaired[:, 3:5])
    old_uv, new_uv = np.concatenate(old_uv), np.concatenate(new_uv)
    assert without_uv(after) == without_uv(before)
    for name, part in before["parts"].items():
        if name not in PARTS:
            assert after["parts"][name] == part
    for name, image in images.items():
        h, w = image.shape[:2]
        nearest_before = image[np.floor(old_uv[:, 1] * h).astype(int), np.floor(old_uv[:, 0] * w).astype(int)]
        nearest_after = image[np.floor(new_uv[:, 1] * h).astype(int), np.floor(new_uv[:, 0] * w).astype(int)]
        assert np.array_equal(nearest_before, nearest_after)
        delta = np.abs(bilinear(image, old_uv) - bilinear(image, new_uv))
        assert delta.max() < 1
        report["material_sampling"][name] = {"nearest_rgba_unchanged": True,
                "baseline_nearest_rgba": np.unique(nearest_before, axis=0).astype(int).tolist(),
                "bilinear_max_rgba_byte_error": delta.max(axis=0).tolist()}
    destination = output / "overlay/assets/projectseele/mesh/eva_unit01.mesh.json"
    assert not destination.exists()
    destination.write_text(json.dumps(after, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    readback = json.loads(destination.read_text(encoding="utf-8"))
    assert without_uv(readback) == without_uv(before)
    assert all(readback["parts"][name] == part for name, part in before["parts"].items() if name not in PARTS)
    report["sha256"] = sha(destination)
    report["bytes"] = destination.stat().st_size
    report["all_non_uv_tree_equal_after_readback"] = True
    report["all_unselected_parts_equal_including_uv"] = True
    report["inherited_geometry_comparison"] = "unchanged original position, pivot, normal, topology, weights and bones"
    (revision / "MOUTH_LINING_UV_REPAIR_RECEIPT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(destination), "sha256": report["sha256"], "parts": report["changed_parts_only"]}))


if __name__ == "__main__":
    main()
