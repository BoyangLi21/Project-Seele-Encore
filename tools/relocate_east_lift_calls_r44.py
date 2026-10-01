"""Exact ordinary-button consoles for all eight installed east lift stops.

This planner never writes the save or creates an elevator group. Ordinary
buttons are routed by S20PhysicalElevatorDirector's declared call API; native
controller, in-car remote/display and group NBT remain in place.
"""
from pathlib import Path
import argparse
import copy
import json

import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities, AIR
from audit_facility_transit_r44 import Geometry

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/east_call_consoles"
LEVELS = (-461, -448, -434, -420, -406, -392, -378, -364)


def plan(world=WORLD, out=OUT):
    world, out = Path(world), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("ordinary_call_consoles/applied_*/receipt.json")):
        raise RuntimeError("Applied console stage is immutable; use a new output directory for a new revision")
    w = MeasuredWorld(world)
    tags = {}
    for y in LEVELS:
        lo, hi = (62, y - 1, 300), (70, y + 4, 313)
        w.box(lo, hi)
        tags.update((q, copy.deepcopy(t)) for q, t in iter_block_entities(world, v.DIM, lo, hi))
    w.load()
    geometry = Geometry(w)
    p, inverse = v.Painter(), v.Painter()
    changes, cases, controls = [], [], []
    old_button = "minecraft:polished_blackstone_button[face=wall,facing=south,powered=false]"
    new_button = "minecraft:polished_blackstone_button[face=wall,facing=east,powered=false]"
    for y in LEVELS:
        old_input, old_back = (63, y + 1, 307), (63, y + 1, 306)
        backing, button, stand = (64, y + 1, 308), (65, y + 1, 308), (66, y, 309)
        targets = [(old_input, "minecraft:air", {old_button}),
                   (old_back, "minecraft:air", {"minecraft:black_concrete"}),
                   (backing, "minecraft:black_concrete", AIR | {"projectseele:clear_glass"}),
                   (button, new_button, AIR)]
        foot = (64, y, 308)
        if w.block(foot) in AIR:
            targets.append((foot, "projectseele:nerv_wall_panel", AIR))
        elif w.block(foot) != "projectseele:nerv_wall_panel":
            raise RuntimeError(("Console base owner changed", foot, w.block(foot)))
        for q, after, allowed in targets:
            before = w.block(q)
            if before is None or before not in allowed or q in tags:
                raise RuntimeError(("Unexpected state or NBT; preserve whole device", q, before))
            changes.append((q, before, after))
        for q in ((66, y, 309), (66, y, 310), (65, y, 310)):
            if geometry.standing(q)["status"] != "STATIC_STANDING":
                raise RuntimeError(("No full ordinary operating clearance", q, geometry.standing(q)))
        path = [[66.5, y, 310.5], [66.5, y, 309.5]]
        cases += [{"id": f"r44/east_lift_call/{y}/approach", "path": path},
                  {"id": f"r44/east_lift_call/{y}/return", "path": path[::-1]}]
        controls.append({"floor_y": y, "button": button, "facing": "east", "backing": backing,
                         "stand": stand, "retired_input": old_input, "retired_dedicated_backing": old_back,
                         "controller_preserved": [63, y, 302], "native_remote_preserved": [64, y + 1, 302],
                         "native_stages": {k: "UNVERIFIED" for k in ("approach", "press", "wait", "door_open",
                             "enter", "ride", "arrival_door_open", "exit", "return", "cold_reload")}})
    v.WORLD, v.OUT = world, out
    for q, before, after in changes:
        p.match((*q, *q), before, after, "r44/east_lift/complete_accessible_call_console")
        inverse.match((*q, *q), after, before, "inverse/r44/east_lift/call_console")
    for y in LEVELS:
        p.protect((63, y, 300, 69, y + 4, 305), "native_controller_car_and_display")
        p.protect((64, y, 306, 68, y + 2, 306), "interlocked_landing_door_plane")
    contract = {"cells": len(changes), "controls": controls, "walk_nodes": cases,
                "source": "Five middle stops' old west-side controls had no flat access from their floor; original shafts and floors remain",
                "binding": "Ordinary non-BE button -> S20 declared exterior call position/facing -> existing native group; no private group rebuild or NBT mutation",
                "scope": "All eight actual R26 east lift stops; two higher levels gain a grounded console base",
                "validation": "Native input, call, cabin travel, egress and reload all UNVERIFIED"}
    p.meta.update(contract)
    p.save_plan("ordinary_call_consoles")
    inverse.meta.update({"forward": "ordinary_call_consoles", "cells": len(changes)})
    inverse.save_plan("inverse_ordinary_call_consoles")
    (out / "contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf8")
    (out / "preserved_complete_nbt.json").write_text(json.dumps([
        {"position": q, "nbt": t.snbt()} for q, t in sorted(tags.items())], ensure_ascii=False, indent=2), encoding="utf8")
    (out / "native_cases.json").write_text(json.dumps(cases, indent=2), encoding="utf8")
    print("Eight grounded ordinary lift call consoles:", len(changes), "exact cells,", len(tags), "native NBT entries preserved", flush=True)
    return p


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, default=WORLD)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    plan(args.world, args.out)
