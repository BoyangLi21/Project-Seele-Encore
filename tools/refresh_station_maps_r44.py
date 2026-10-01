"""All retained full diagrams use actual Chinese sequences/flight transfers.

NBT-only exact inverse preserves the whole installed board. New door-adjacent
coverage, reader/mount corrections and free-gate controls are separate scope.
"""
from pathlib import Path
import copy, gzip, hashlib, json
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld, properties
from query_blocks import iter_block_entities
from station_route_contract_r44 import RouteDiagrams, NATIVE, CATALOGUE

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/station_map_text_v1"


def main(world=WORLD, out=OUT):
    world, out = Path(world), Path(out); out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("all_retained_native_chinese_diagrams/applied_*/receipt.json")):
        raise RuntimeError("Applied board text is immutable")
    diagrams = RouteDiagrams()
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf8"))
    w, tags = MeasuredWorld(world), {}
    for station in catalogue["stations"]:
        lo, hi = map(tuple, station["bounds"]); w.box(lo, hi)
        for q, tag in iter_block_entities(world, v.DIM, lo, hi):
            if str(tag.get("id", "")) == "projectseele:station_departure_board" and "MapRows" in tag:
                tags[q] = copy.deepcopy(tag)
    w.load(); v.WORLD, v.OUT = world, out
    p, inverse = v.Painter(), v.Painter(); updated, held = [], []
    for q, before in sorted(tags.items()):
        state = w.block(q)
        if state is None:
            raise RuntimeError(("Retained board state is unknown", q))
        pid = int(before.get("NativePlatformId", -1)); face = properties(state).get("facing")
        try:
            diagram = diagrams.diagram(pid, face, str(before.get("Route", "")))
        except (RuntimeError, KeyError) as reason:
            held.append({"position": q, "reason": str(reason), "whole_before_nbt": before.snbt()})
            continue
        after = copy.deepcopy(before)
        after["Station"] = nbtlib.String(diagram["station"])
        after["Route"] = nbtlib.String(diagram["line"] + " 全线站序 / 乘车方向")
        after["MapRows"] = nbtlib.List[nbtlib.String]([nbtlib.String(s) for s in diagram["rows"]])
        after["AirService"] = nbtlib.Byte(diagram["mode"] == "AIRPLANE")
        for i, row in enumerate(diagram["rows"][:3]):
            after[f"Row{i}"] = nbtlib.String(row)
        if after != before:
            p.update_block_entity(q, state, before, after, "r44/native_complete_station_diagram")
            inverse.update_block_entity(q, state, after, before, "inverse/r44/native_station_diagram")
            updated.append({"position": q, "state": state, **diagram})
    report = {"world": str(world), "retained_maps": len(tags), "updated": updated, "held": held,
        "native_snapshot": str(NATIVE), "native_sha256": hashlib.sha256(NATIVE.read_bytes()).hexdigest(),
        "authority": "Exact actual platform visit sequence, outgoing native rail and co-station TRAIN/AIR services. No hardcoded one-minute timetable or city-direction guess.",
        "coverage": f"{len(tags)} currently installed maps' content scope only. Every door-adjacent map, front/rear readership, real gates and all501 station paths remain independent obligations.",
        "native_visual_reload": "UNVERIFIED"}
    p.meta.update(report); p.save_plan("all_retained_native_chinese_diagrams")
    inverse.meta.update({"forward": "all_retained_native_chinese_diagrams", "held": held})
    inverse.save_plan("inverse_all_retained_native_chinese_diagrams")
    (out / "contract.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print("Retained full native diagrams:", len(tags), "updated", len(updated), "held", len(held), "; content only, no world mutation", flush=True)
    return p


if __name__ == "__main__":
    main()
