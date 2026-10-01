"""Six complete measured side-wall seam strips; exact forward and inverse only."""
from pathlib import Path
from collections import Counter
import argparse, copy, hashlib, json

import regional_voxels as v
from query_blocks import AIR, iter_block_entities
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from hangar_tv_design_r44 import lower_pressure_seam_members, FULL_CUBE

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/hangar_lower_pressure_seams_v1"


def plan(world=WORLD, out=OUT):
    world, out = Path(world), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("six_complete_sidewall_seams/applied_*/receipt.json")):
        raise RuntimeError("Applied seam revision is immutable")
    w = MeasuredWorld(world)
    lo, hi = (-33, -375, -268), (93, -371, -213)
    w.box(lo, hi); w.load(); g = Geometry(w)
    tags = {q: copy.deepcopy(tag) for q, tag in iter_block_entities(world, v.DIM, lo, hi)}
    frame_path = ROOT / "artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json"
    frames = json.loads(frame_path.read_text(encoding="utf8"))
    body_path = frame_path.with_name("actual_render_body_surfaces.json")
    bodies = json.loads(body_path.read_text(encoding="utf8"))["actors"]
    changes, retained, members = {}, Counter(), []
    for q, after in sorted(lower_pressure_seam_members().items()):
        before = w.block(q)
        if before is None:
            raise RuntimeError(("Unknown side-facade seam", q))
        neighbours = [{"position": [q[0], q[1] + dy, q[2]], "state": w.get(q[0], q[1] + dy, q[2])} for dy in (-1, 1)]
        if any(g.boxes(item["state"]) != FULL_CUBE for item in neighbours):
            raise RuntimeError(("Seam is not bounded by the actual whole pressure face", q, neighbours))
        if q in tags or before.partition("[")[0] not in AIR:
            retained[before] += 1
            members.append({"position": q, "state": before, "support": neighbours, "action": "retain_whole_existing_member"})
            continue
        if g.boxes(after) != FULL_CUBE:
            raise RuntimeError(("Unknown native pressure material", after))
        for bay in frames["bays"]:
            bounds = bay["capsule_sweep_negative"]
            if all(q[i] + 1 > bounds[0][i] and q[i] < bounds[1][i] for i in range(3)):
                raise RuntimeError(("Seam intersects complete 121-pose capsule envelope", q, bay["variant"]))
        for actor in bodies.values():
            for name, part in actor["parts"].items():
                bounds = part["world_bounds"]
                if all(q[i] + 1 > bounds[i] and q[i] < bounds[i + 3] for i in range(3)):
                    raise RuntimeError(("Seam intersects submitted original actor part", q, actor["variant"], name))
        changes[q] = after
        members.append({"position": q, "state": before, "support": neighbours, "action": "close_pressure_seam", "after": after})
    v.WORLD, v.OUT = world, out
    p, inverse = v.Painter(), v.Painter()
    for q, after in changes.items():
        before = w.block(q)
        p.match((*q, *q), before, after, "r44/hangar/whole_side_pressure_seam")
        inverse.match((*q, *q), after, before, "inverse/r44/hangar/whole_side_pressure_seam")
    report = {"world": str(world), "cells": len(changes), "whole_strip_cells": len(members), "members": members,
        "authority": "Six existing wet-vessel side-facade strips at authored X=cage+-20, Y-373, Z-260..-214. Every cell has measured full-cube pressure members immediately above and below; the complete strips are closed, not isolated image pixels.",
        "retained_existing_members": dict(retained), "source_frame_sha256": hashlib.sha256(frame_path.read_bytes()).hexdigest(),
        "source_body_sha256": hashlib.sha256(body_path.read_bytes()).hexdigest(),
        "original_complete_nbt": [{"position": q, "snbt": tag.snbt()} for q, tag in sorted(tags.items())],
        "negative": "Original personnel floors/ports, north observation glazing, rear shutter, actual crane wheel tracks, original actors/UUID and complete capsule121 envelope retained",
        "reference": "Original TV cage blue-grey enclosing pressure faces; current 182923 pictures show bright narrow holes. Pixel-to-world optical attribution is not claimed without a fresh native image.",
        "template": "Shared lower_pressure_seam_members also used by the future R20 source producer; commissioned/frozen worlds still use this explicit exact migration only",
        "status": "STATIC_COMPONENT_CANDIDATE; complete shader views, all3 operating journeys, sound/lighting/visual approval and cold reload remain pending"}
    p.meta.update(report); p.save_plan("six_complete_sidewall_seams")
    inverse.meta.update({"forward": "six_complete_sidewall_seams", "cells": len(changes), "original_complete_nbt": report["original_complete_nbt"]})
    inverse.save_plan("inverse_six_complete_sidewall_seams")
    report["sha256"] = hashlib.sha256((out / "six_complete_sidewall_seams/ops.json.gz").read_bytes()).hexdigest()
    (out / "contract.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print("Six measured complete side seams:", len(members), "strip cells;", len(changes), "exact air closures; no world mutation", flush=True)
    return p


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, default=WORLD)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    plan(args.world, args.out)
