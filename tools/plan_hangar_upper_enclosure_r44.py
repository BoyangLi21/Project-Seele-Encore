"""Measured common upper pressure envelope and roof/transfer step joint.

The complete roof follows the actual copied R20 component, not an invented
lower ceiling. Internal upper bay openings are kept for the real shared
observation/crane space. This CLI produces exact reversible candidates only.
"""
from pathlib import Path
from collections import Counter
import copy, hashlib, json
import regional_voxels as v
from query_blocks import AIR, iter_block_entities
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from hangar_tv_design_r44 import upper_pressure_members, FULL_CUBE

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/hangar_upper_enclosure_v2"
PUBLIC_FLOORS = {"projectseele:clear_glass", "projectseele:nerv_floor_panel",
    "minecraft:polished_deepslate", "minecraft:sea_lantern"}


def plan(world=WORLD, out=OUT):
    world, out = Path(world), Path(out); out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("common_upper_pressure_envelope/applied_*/receipt.json")):
        raise RuntimeError("Applied upper envelope is immutable")
    w = MeasuredWorld(world)
    lo, hi = (-45, -399, -294), (110, -347, -205)
    w.box(lo, hi); w.load(); g = Geometry(w)
    tags = {q: copy.deepcopy(t) for q, t in iter_block_entities(world, v.DIM, lo, hi)}
    frames = json.loads((ROOT / "artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json").read_text(encoding="utf8"))
    surfaces = json.loads((ROOT / "artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2/actual_render_body_surfaces.json").read_text(encoding="utf8"))
    members = upper_pressure_members()
    kept, ports, changes, roof_bearings = Counter(), [], {}, []
    for x in (-40, 104):
        for z in range(-286, -213):
            q = (x, -355, z)
            if g.boxes(w.block(q)) != FULL_CUBE:
                raise RuntimeError(("The real copied roof does not carry the upper cladding", q, w.block(q)))
            roof_bearings.append({"position": q, "state": w.block(q)})
    for x in range(-40, 105):
        q = (x, -355, -286)
        if g.boxes(w.block(q)) != FULL_CUBE:
            raise RuntimeError(("The real copied front roof edge is not complete", q, w.block(q)))
        roof_bearings.append({"position": q, "state": w.block(q)})
    # Explicit authored personnel levels, with a real nine-point slab and
    # source collision clearance. Protect full standing cells, not a centre.
    protected_public = set()
    for x in range(lo[0], hi[0] + 1):
        for z in range(lo[2], hi[2] + 1):
            for fy in (-394, -367):
                floor = w.block((x, fy - 1, z))
                if floor is None or floor.partition("[")[0] not in PUBLIC_FLOORS:
                    continue
                if g.standing((x, fy, z))["status"] == "STATIC_STANDING":
                    protected_public.update((x, y, z) for y in (fy - 1, fy, fy + 1, fy + 2))
    for q, target in sorted(members.items()):
        before = w.block(q)
        if before is None:
            raise RuntimeError(("Unmeasured complete pressure member", q))
        if q in protected_public:
            ports.append({"position": q, "state": before,
                "role": "Retained actual authored personnel slab/three-metre headroom"})
            continue
        if q in tags or before.partition("[")[0] not in AIR:
            kept[before.partition("[")[0]] += 1
            continue
        if g.boxes(target) != FULL_CUBE:
            raise RuntimeError(("No real complete pressure material", target))
        for b in frames["bays"]:
            negative = b["capsule_sweep_negative"]
            if all(q[i] + 1 > negative[0][i] and q[i] < negative[1][i] for i in range(3)):
                raise RuntimeError(("Cladding enters the complete capsule motion", q, b["variant"]))
        for actor in surfaces["actors"].values():
            for name, part in actor["parts"].items():
                bounds = part["world_bounds"]
                if all(q[i] + 1 > bounds[i] and q[i] < bounds[i + 3] for i in range(3)):
                    raise RuntimeError(("Pressure member intersects actual submitted armour", q, actor["variant"], name))
        changes[q] = target
    v.WORLD, v.OUT = world, out
    p, inverse = v.Painter(), v.Painter()
    for q, after in sorted(changes.items()):
        before = w.block(q)
        p.match((*q, *q), before, after, "r44/hangar/actual_shared_upper_pressure_envelope")
        inverse.match((*q, *q), after, before, "inverse/r44/hangar/upper_pressure_envelope")
    # Every sampled roof column has actual nonfluid cube bearing above it.
    # Read the candidate overlay separately from the exact source snapshot.
    original_get = w.get
    def get(x, y, z):
        return changes.get((x, y, z), original_get(x, y, z))
    w.get = get
    open_columns = []
    for x in range(-40, 105):
        for z in range(-286, -212):
            if not any(g.boxes(w.block((x, y, z))) == FULL_CUBE for y in range(-355, -347)):
                open_columns.append((x, z))
    for q in protected_public:
        if w.block(q) != original_get(*q):
            raise RuntimeError(("Candidate changes a real full-width public interface", q))
    w.get = original_get
    if open_columns:
        raise RuntimeError(("Retained common wet roof has unresolved open columns", open_columns[:8]))
    report = {"world": str(world), "cells": len(changes),
        "authority": "R20 copied component SOURCE X-40..104, measured complete roof Z-286..-214 Y-355. The real upper lift pocket floor reaches Z-288; a same-height three-metre roof extension and outside front closure at Z-289 preserve it. New upper industrial enclosure and one-row transfer joint are within the user's whole-hangar reconstruction scope",
        "common_volume": "Internal X±20 bay openings above the older vessels are shared inspection/crane space, not each an outside leak; no six new internal partitions",
        "roof": {"actual_y": -355, "common_x": [-40, 104], "actual_z": [-286, -214],
            "same_height_north_extension_z": [-289,-287], "north_closure_z": -289,
            "step_join": [-213, -212], "transfer_roof_low_y": -357, "candidate_open_vertical_columns": open_columns},
        "roof_bearings": roof_bearings, "retained_complete_components": dict(kept),
        "retained_actual_personnel_ports": ports,
        "original_complete_nbt": [{"position": q, "snbt": t.snbt()} for q, t in sorted(tags.items())],
        "body_evidence": "All original submitted material-part AABBs were checked; capsule121poses checked; no actor transforms or UUID changed",
        "status": "STATIC_CANDIDATE only; actual full views, operating machinery, all personnel paths and cold reload unverified"}
    p.meta.update(report); p.save_plan("common_upper_pressure_envelope")
    inverse.meta.update({"forward": "common_upper_pressure_envelope", "cells": len(changes),
        "original_complete_nbt": report["original_complete_nbt"]})
    inverse.save_plan("inverse_common_upper_pressure_envelope")
    report["sha256"] = hashlib.sha256((out / "common_upper_pressure_envelope/ops.json.gz").read_bytes()).hexdigest()
    (out / "contract.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print("Actual common upper enclosure:", len(changes), "exact air cells; public interfaces retained", len(ports), "; no low roof, actor or world mutation", flush=True)
    return p


if __name__ == "__main__":
    plan()
