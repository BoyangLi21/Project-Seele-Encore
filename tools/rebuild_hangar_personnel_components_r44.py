"""Retire complete legacy forward decks and rebuild the real crew perimeter.

The canonical neck/boarding deck is on +Z. The copied -Z shelf assemblies
are retired as floors, frames and attached rails together. Original front
circulation, six side lanes, east lift vestibule, LCL and the actual rear
retractable boarding assembly remain. No world apply entry point exists.
"""
from pathlib import Path
from collections import Counter
import argparse, copy, hashlib, json, math
import nbtlib

import regional_voxels as v
from query_blocks import AIR, iter_block_entities
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from verify_main_r20 import entities

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/hangar_personnel_components_v1"
OLD_DECK = {"projectseele:nerv_machine_panel", "projectseele:nerv_machine_edge",
            "projectseele:nerv_machine_hazard", "minecraft:sea_lantern"}
FULL = [[0., 0., 0., 1., 1., 1.]]


def rail(*sides):
    return "projectseele:nerv_edge_rail[" + ",".join(f"{name}={'true' if name in sides else 'false'}" for name in ("east", "north", "south", "west")) + "]"


def occupancy_contract(world, w, g, changes, tags, out):
    """Persisted actors and authored posts/targets are independent owners."""
    retired = {q for q, (after, why) in changes.items() if after.partition("[")[0] in AIR and why == "retire_whole_obsolete_forward_shelf"}
    saved = entities(world)
    preserved, checks, conflicts = [], [], []

    def examine(kind, identity, feet, *, actual_feet=True, context=None):
        feet = list(map(float, feet))
        if len(feet) != 3 or not all(math.isfinite(value) for value in feet):
            raise RuntimeError(("Malformed authored actor/target position", kind, identity, feet))
        dependencies = []
        if actual_feet:
            # The full human footprint, not only its centre, is tested against
            # exact native top surfaces, including the old1.5m iron bars.
            for q in retired:
                if not (q[0] - .3 < feet[0] < q[0] + 1.3 and q[2] - .3 < feet[2] < q[2] + 1.3 and q[1] - .15 <= feet[1] <= q[1] + 1.65):
                    continue
                boxes = g.boxes(w.block(q))
                if boxes is None:
                    raise RuntimeError(("Unknown native former actor support", q, w.block(q)))
                if any(abs(q[1] + box[4] - feet[1]) <= .15 and q[0] + box[0] < feet[0] + .3 and q[0] + box[3] > feet[0] - .3
                       and q[2] + box[2] < feet[2] + .3 and q[2] + box[5] > feet[2] - .3 for box in boxes):
                    dependencies.append(q)
        else:
            cell = tuple(map(math.floor, feet))
            if cell in retired:
                dependencies.append(cell)
            if (cell[0], cell[1] - 1, cell[2]) in retired:
                dependencies.append((cell[0], cell[1] - 1, cell[2]))
        row = {"kind": kind, "identity": identity, "position": feet, "retired_component_dependencies": dependencies, "context": context}
        checks.append(row)
        if dependencies:
            conflicts.append(row)

    def unpack(value):
        value = int(value)
        def signed(number, bits):
            return number - (1 << bits) if number & (1 << (bits - 1)) else number
        return [signed((value >> 38) & ((1 << 26) - 1), 26), signed(value & 4095, 12), signed((value >> 12) & ((1 << 26) - 1), 26)]

    for uid, tag in saved.items():
        identity = ",".join(map(str, uid))
        preserved.append({"uuid_int_array": list(uid), "type": str(tag.get("id", "")), "snbt": copy.deepcopy(tag).snbt()})
        if len(tag.get("Pos", [])) == 3:
            examine("current_saved_entity_feet", identity, tag["Pos"], context={"type": str(tag.get("id", "")), "staff_id": str(tag.get("StaffId", ""))})
        if "StaffStation" in tag:
            q = unpack(tag["StaffStation"])
            examine("persistent_NPC_post", str(tag.get("StaffId", identity)), [q[0] + .5, q[1], q[2] + .5], context={"had_pending_task": bool(tag.get("HadPendingStaffTask", False))})
    (out / "original_all_saved_entities.json").write_text(json.dumps(preserved, ensure_ascii=False, indent=2), encoding="utf8")

    player_rows = []
    for path in (world / "playerdata").glob("*.dat"):
        player = nbtlib.load(path)
        player_rows.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "snbt": player.snbt()})
        if str(player.get("Dimension", "")) == v.DIM and len(player.get("Pos", [])) == 3:
            examine("current_saved_player_feet", path.stem, player["Pos"])
    (out / "original_saved_players.json").write_text(json.dumps(player_rows, ensure_ascii=False, indent=2), encoding="utf8")

    roster_path = world / "nerv_staff_r15.json"
    roster = json.loads(roster_path.read_text(encoding="utf8"))
    (out / "original_complete_staff_roster.json").write_bytes(roster_path.read_bytes())
    for row in roster["stations"]:
        examine("authored_staff_roster_post", row["id"], row["feet"], context={"role": row.get("role"), "room": row.get("room")})

    # Only explicitly named gameplay coordinates are interpreted as targets;
    # timestamps, platform identities and arbitrary numeric triples are not.
    fields = {"feet", "approach", "operator", "position", "control", "button", "reader", "exit", "gate", "head", "entry", "landing", "target"}
    manifests = []
    for path in world.glob("*.json"):
        if not any(token in path.name for token in ("access", "gate", "operator", "interface", "staff", "hangar")) or path == roster_path:
            continue
        if any(token in path.name for token in ("review", "body_surfaces", "contacts")):
            continue
        data = json.loads(path.read_text(encoding="utf8"))
        manifests.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        def visit(value, prefix=""):
            if isinstance(value, dict):
                for key, child in value.items():
                    name = prefix + "/" + key
                    if key.lower() in fields and isinstance(child, list) and len(child) == 3 and all(isinstance(n, (int, float)) for n in child):
                        kind = "authored_interaction_approach" if key.lower() in {"feet", "approach", "operator", "entry", "landing"} else "authored_interaction_target"
                        examine(kind, path.name + name, child, actual_feet=kind.endswith("approach"))
                    else:
                        visit(child, name)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, prefix + "/" + str(index))
        visit(data)
    for q, tag in tags.items():
        for name in ("Gate", "Exit", "Control", "Target", "Approach", "StaffStation"):
            if name in tag and isinstance(tag[name], nbtlib.Long):
                examine("installed_device_target", f"{q}/{name}", unpack(tag[name]), actual_feet=name in ("Approach", "StaffStation"))
    report = {"current_saved_entities": len(preserved), "complete_entity_nbt": "original_all_saved_entities.json",
              "saved_player_records": len(player_rows), "complete_player_nbt": "original_saved_players.json", "roster_posts": len(roster["stations"]),
              "complete_roster": "original_complete_staff_roster.json", "gameplay_manifest_sources": manifests, "checks": checks, "conflicts": conflicts,
              "status": "PERSISTED_AND_AUTHORED_DEPENDENCIES_CHECKED; live transient task/control state must be quiesced by root before cold world apply"}
    (out / "actor_and_interaction_conflicts.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    if conflicts:
        raise RuntimeError(("Whole retired component still owns actor/NPC/interaction support", conflicts))
    return {"current_saved_entities": len(preserved), "saved_player_records": len(player_rows), "roster_posts": len(roster["stations"]),
            "checks": len(checks), "conflicts": 0, "evidence": str((out / "actor_and_interaction_conflicts.json").resolve()),
            "evidence_sha256": hashlib.sha256((out / "actor_and_interaction_conflicts.json").read_bytes()).hexdigest(), "native_transient_tasks": "root must quiesce before apply"}


def plan(world=WORLD, out=OUT):
    world, out = Path(world), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("complete_personnel_components/applied_*/receipt.json")):
        raise RuntimeError("Applied personnel revision is immutable")
    w = MeasuredWorld(world)
    lo, hi = (-43, -398, -289), (107, -390, -212)
    w.box(lo, hi); w.load(); g = Geometry(w)
    tags = {q: copy.deepcopy(t) for q, t in iter_block_entities(world, v.DIM, lo, hi)}
    changes, components, paths, retained = {}, [], [], []
    original_bars = {(x, -394, z) for x in range(lo[0], hi[0] + 1) for z in range(lo[2], hi[2] + 1)
                     if w.get(x, -394, z).startswith("minecraft:iron_bars")}
    classified_bars = set()

    def put(q, after, purpose):
        before = w.block(q)
        if before is None or q in tags:
            raise RuntimeError(("Unmeasured/native component in personnel proposal", q, before))
        if after.partition("[")[0] not in AIR and g.boxes(after) is None:
            raise RuntimeError(("No exact native proposed shape", q, after))
        if before != after:
            changes[q] = (after, purpose)

    # This is the already authored arrival pocket for the real crew lift.
    # Its whole floor/structural shell/glazing is retained, including the
    # piece that intersects the old right-hand shelf of EVA-02.
    def east_port(q):
        return 85 <= q[0] <= 98 and -398 <= q[1] <= -390 and -262 <= q[2] <= -248

    for variant, cx in enumerate((-12, 30, 72)):
        old_cells = []
        for x in range(cx - 16, cx + 17):
            for z in range(-260, -247):
                for y in (-395, -394):
                    q = (x, y, z); before = w.block(q)
                    if east_port(q):
                        retained.append({"position": q, "state": before, "reason": "whole_original_east_lift_arrival_pocket"})
                        if q in original_bars:
                            raise RuntimeError(("Legacy rail belongs to a retained arrival pocket; classify separately", q))
                        continue
                    if before.partition("[")[0] in AIR:
                        continue
                    allowed = before.partition("[")[0] in OLD_DECK if y == -395 else before.startswith("minecraft:iron_bars")
                    if not allowed:
                        raise RuntimeError(("Other original component in retired forward shelf", q, before))
                    if y == -395 and g.boxes(before) != FULL:
                        raise RuntimeError(("Legacy deck has unknown bearing shape", q, before))
                    put(q, "minecraft:air", "retire_whole_obsolete_forward_shelf")
                    old_cells.append({"position": q, "state": before})
                    if q in original_bars:
                        classified_bars.add(q)
        components.append({"variant": variant, "purpose": "complete_retired_forward_service_shelves_and_capsule_well_frames",
                           "bounds": [[cx - 16, -395, -260], [cx + 16, -394, -248]], "members": old_cells,
                           "retained_crew_crossway_z": [-264, -261], "canonical_rear_boarding_z": [-224, -216],
                           "interpretation": "R44 engineering reconstruction of copied legacy shelf; not a new TV episode fact"})
        for side in (-1, 1):
            side_cells = []
            x = cx + side * 17
            for z in range(-260, -224):
                q = (x, -394, z)
                if q not in original_bars:
                    if east_port(q):
                        continue
                    raise RuntimeError(("Unclassified break in original complete side guard", q, w.block(q)))
                if g.boxes(w.get(x, -395, z)) != FULL:
                    raise RuntimeError(("Side guard has no actual complete lip", q))
                put(q, rail("east" if side < 0 else "west"), "whole_supported_side_work_guard")
                classified_bars.add(q)
                side_cells.append({"position": q, "old": w.block(q), "floor": w.get(x, -395, z)})
            components.append({"variant": variant, "side": side, "purpose": "fixed_side_work_deck_and_attached_guard",
                               "floor_y": -395, "two_clear_lanes": [cx + side * 18, cx + side * 19],
                               "lip_x": x, "retained_original_bearing_and_wall_brackets": True, "guard_members": side_cells})
        # The actual front crossway remains four metres deep. Its new open
        # metal guard sits on its south lip and follows the real drop edge.
        for dx in range(-17, 18):
            q = (cx + dx, -394, -261)
            if g.boxes(w.get(q[0], -395, q[2])) != FULL or w.block(q).partition("[")[0] not in AIR:
                raise RuntimeError(("Existing crossway lip is not a supported free boundary", q, w.block(q)))
            sides = ["south"]
            if abs(dx) == 17:
                sides.append("east" if dx < 0 else "west")
            put(q, rail(*sides), "whole_front_crossway_supported_perimeter")
    if classified_bars != original_bars:
        raise RuntimeError(("Incomplete original493 guard/component scope", sorted(original_bars - classified_bars)))
    occupancy = occupancy_contract(world, w, g, changes, tags, out)

    original_get = w.get
    w.get = lambda x, y, z: changes.get((x, y, z), (original_get(x, y, z), ""))[0]
    for cx in (-12, 30, 72):
        for side in (-1, 1):
            for offset in (18, 19):
                for z in range(-264, -215):
                    if g.standing((cx + side * offset, -394, z))["status"] != "STATIC_STANDING":
                        raise RuntimeError(("Candidate interrupts a complete two-lane crew deck", cx, side, offset, z))
                for z in (-264, -216):
                    target = (cx + side * offset, -394, z)
                    route = g.flat_path((-29, -394, -285), target, radius=180)
                    if route is None:
                        raise RuntimeError(("Candidate loses a real lift-to-work-deck route", target))
                    nodes = [[x + .5, y, zz + .5] for x, y, zz in route]
                    ident = f"r44/TV_personnel_components/{cx}/{side}/{offset}/{z}"
                    paths.extend(({"id": ident, "path": nodes}, {"id": ident + "/return", "path": nodes[::-1]}))
        for x in range(cx - 19, cx + 20):
            for z in range(-264, -260):
                if g.standing((x, -394, z))["status"] != "STATIC_STANDING":
                    raise RuntimeError(("Candidate obstructs a whole retained front crossway", x, z))
    w.get = original_get
    frames = json.loads((ROOT / "artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json").read_text(encoding="utf8"))
    for q, (after, _) in changes.items():
        if after.partition("[")[0] in AIR:
            continue
        for bay in frames["bays"]:
            bounds = bay["capsule_sweep_negative"]
            if all(q[i] + 1 > bounds[0][i] and q[i] < bounds[1][i] for i in range(3)):
                raise RuntimeError(("New personnel guard enters the121-pose capsule envelope", q, bay["variant"]))
    v.WORLD, v.OUT = world, out
    p, inverse = v.Painter(), v.Painter()
    for q, (after, purpose) in sorted(changes.items()):
        before = w.block(q)
        p.match((*q, *q), before, after, "r44/hangar_personnel/" + purpose)
        inverse.match((*q, *q), after, before, "inverse/r44/hangar_personnel/" + purpose)
    report = {"world": str(world), "cells": len(changes), "original_iron_bars": len(original_bars),
              "whole_original_bars_classified": len(classified_bars), "components": components, "retained_whole_arrival_pocket": retained,
              "actor_and_interaction_dependencies": occupancy,
              "original_complete_nbt": [{"position": q, "snbt": t.snbt()} for q, t in sorted(tags.items())],
              "purpose_counts": dict(Counter(purpose for _, purpose in changes.values())), "native_cases": paths,
              "negative": "Original LCL and all underlying fluid cells; three original actors/plugs/UUID; rear retractable boarding floor/capsule121 sweep; original east lift whole pocket and6 complete two-lane decks",
              "status": "STATIC_COMPONENT_CANDIDATE. All3 full journeys, view/lighting/sound, occupancy, cold reload and user visual approval remain required"}
    p.meta.update(report); p.save_plan("complete_personnel_components")
    inverse.meta.update({"forward": "complete_personnel_components", "cells": len(changes), "original_complete_nbt": report["original_complete_nbt"]})
    inverse.save_plan("inverse_complete_personnel_components")
    report["sha256"] = hashlib.sha256((out / "complete_personnel_components/ops.json.gz").read_bytes()).hexdigest()
    (out / "contract.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    (out / "native_cases.json").write_text(json.dumps(paths, ensure_ascii=False, indent=2), encoding="utf8")
    print("Whole personnel component candidate:", len(changes), "exact cells;", len(original_bars), "original bars fully classified;", len(paths), "whole crew paths", flush=True)
    return p


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, default=WORLD)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    plan(args.world, args.out)
