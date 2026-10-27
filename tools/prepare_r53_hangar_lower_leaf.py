"""Prepare only the original three front-door lower-leaf installation; never write the save."""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import math
from pathlib import Path

from query_blocks import read_box, iter_block_entities


def cells(box):
    lo, hi = box[:3], box[3:]
    for x in range(math.floor(lo[0] + 1e-8), math.ceil(hi[0] - 1e-8)):
        for y in range(math.floor(lo[1] + 1e-8), math.ceil(hi[1] - 1e-8)):
            for z in range(math.floor(lo[2] + 1e-8), math.ceil(hi[2] - 1e-8)):
                yield x, y, z


def lower_sweep(cx, cy, cz):
    # Each stage is axis-aligned and monotone, so these boxes are exact sweeps.
    result = set()
    width, pocket = 33 / 8, 16.65
    for side in (-1, 1):
        for index in range(4):
            closed, depth = index * width, 1.1 + (3 - index) * 1.1
            for x0, x1, z0, z1 in ((closed, closed + width, 0, depth + .98),
                                  (closed, pocket + width, depth, depth + .98)):
                xs = sorted((cx + side * x0, cx + side * x1))
                result.update(cells((*xs[:1], cy - 5, cz - z1, xs[1], cy, cz - z0)))
    return result


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("world", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--carrier-candidate", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    owner = json.loads((args.world / "ROOT_MECHANICAL_OWNER.json").read_bytes())
    changed_owner = copy.deepcopy(owner)
    summaries, forward, overlaps = [], [], []
    allowed = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:barrier",
               "minecraft:iron_block", "projectseele:nerv_floor_panel", "projectseele:nerv_structural_panel",
               "projectseele:nerv_machine_edge", "projectseele:nerv_machine_hazard"}
    for variant in range(3):
        gate = next(g for g in changed_owner["gates"] if g["resource"] == f"bay_{variant}_front")
        cx, cy, cz = gate["frame"]["position"]
        assert gate["width"] == 33 and gate["height"] == 72
        assert gate["frame"]["quaternion"] == [0, 1, 0, 0] and cy == -1062 and cz == 301.5
        assert gate["hangar_stack"].get("depth_direction", 1) == 1
        swept = lower_sweep(cx, cy, cz)
        lo = tuple(min(p[a] for p in swept) for a in range(3))
        hi = tuple(max(p[a] for p in swept) for a in range(3))
        source_path = args.output / f"source-unit{variant}.json"
        if source_path.exists():
            saved = json.loads(source_path.read_bytes())
            assert saved["world"] == str(args.world) and saved["lo"] == list(lo) and saved["hi"] == list(hi)
            measured = {tuple(r["pos"]): r["state"] for r in saved["cells"]}
            devices = set(map(tuple, saved["devices"]))
        else:
            measured = read_box(args.world, "projectseele:geofront", lo, hi)
            devices = {tuple(p) for p, _ in iter_block_entities(args.world, "projectseele:geofront", lo, hi)}
            write(source_path, {"world": str(args.world), "lo": lo, "hi": hi,
                  "cells": [{"pos": p, "state": s} for p, s in measured.items()], "devices": list(devices)})
        assert swept <= measured.keys(), "Incomplete actual source cells"
        assert not devices.intersection(swept), "Original device occupies new lower-leaf travel"
        supports = {tuple(s["position"]) for s in gate["supports"]}
        assert not supports.intersection(swept), "Original gate bearing would be removed"
        carrier = json.loads((args.carrier_candidate / f"unit{variant}" / "forwardPatch.json").read_bytes())
        carrier_by_pos = {tuple(r["pos"]): r for r in carrier}
        desired = {p: "minecraft:air" for p in swept}
        proxy = {(x, y, 301) for x in range(round(cx - 16.5), round(cx + 16.5))
                 for y in range(-1067, -1062)}
        assert proxy <= swept
        for p in proxy:
            desired[p] = "minecraft:barrier"
        edits = []
        for p, state in sorted(desired.items()):
            before = measured[p]
            assert before in allowed, f"Unclassified original material {p}: {before}"
            if p in carrier_by_pos and carrier_by_pos[p]["after"] != state:
                overlaps.append({"pos": list(p), "carrier_after": carrier_by_pos[p]["after"], "door_after": state})
            if before != state:
                edits.append({"pos": list(p), "before": before, "after": state,
                              "before_nbt": None, "after_nbt": None,
                              "purpose": "original_hangar_lower_leaf_proxy" if p in proxy else "original_side_stack_lower_travel"})
        reference = gate["collision_steps"]
        steps = json.loads(gzip.decompress((args.world / reference["cells_file"]).read_bytes())) if isinstance(reference, dict) else reference
        retired = {tuple(p) for p in gate.pop("floor_seal_original_cells", [])}
        steps = [[c for c in row if tuple(c["position"]) not in retired] for row in steps]
        existing = {tuple(c["position"]) for row in steps for c in row}
        assert not proxy.intersection(existing)
        steps[0].extend({"position": list(p), "closed": "minecraft:barrier", "open": "minecraft:air"} for p in sorted(proxy))
        gate["collision_steps"] = steps
        gate["hangar_stack"].pop("floor_seal", None)
        gate["hangar_stack"]["leaf_lower_extension_m"] = 5
        forward.extend(edits)
        summaries.append({"gate": gate["resource"], "actual_cells_read": len(measured), "swept_lower_cells": len(swept),
                          "closed_proxy_cells": len(proxy), "changed_cells": len(edits), "original_supports_retained": len(supports)})
    write(args.output / "ROOT_MECHANICAL_OWNER.json", changed_owner)
    write(args.output / "forwardPatch.json", forward)
    write(args.output / "inversePatch.json", [{**r, "before": r["after"], "after": r["before"]} for r in forward])
    write(args.output / "positiveEditMask.json", [r["pos"] for r in forward])
    write(args.output / "carrier-overrides.json", overlaps)
    write(args.output / "construction.json", {"world": str(args.world), "installed": False, "gates": summaries,
          "merge": "Merge by position against actual source; door_after wins at listed carrier overlaps. Original frame, upper leaves, supports and identities retained.",
          "geometry": "Original eight leaves gain joined 5m lower plates; original frame and 72m top unchanged.",
          "native_pending": "Door open/close with the coordinated retracting rail bridges and original loaded carrier."})
    print(json.dumps({"gates": summaries, "changed_cells": len(forward), "carrier_overrides": len(overlaps)}))


if __name__ == "__main__":
    main()
